"""Scientific controls and persistence checks for the B/C study path."""

import copy
import csv
from contextlib import nullcontext
import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from code_datasets import dataset_loader
from core.revision_study import build_conditions, draw_seed, run_study
from core.inference import InferenceEngine, ManagedModel
from evaluation.output_protocol import AVAILABLE_OUTPUT_PROTOCOLS, build_output_instruction
from evaluation.label_parser import parse_verdict_details
from evaluation.metrics import Metrics, refresh_record_accuracy
from evaluation.template_analysis import analyze_study, paired_comparison
from evaluation.voting import aggregate_votes
from models.base import BaseModel, ContextWindowExceeded, merge_generation_settings
from models import model_loader as model_loading
from models.ollama_model import OllamaModel
from prompts.adaptive_cot import AdaptiveCoT
from prompts.base_prompt import ROLE_INSTRUCTION, TASK_INSTRUCTION, BasePrompt
from prompts.cot import CoT
from prompts.few_shot import EXAMPLES, FewShot
from prompts.self_consistency import SelfConsistency
from prompts.self_verification import SelfVerification
from prompts.template_variants import (
    CODE_SLOT, COMPONENTS, VARIANTS, render_component_template, render_prompt, render_template,
)
from prompts.zero_shot import ZeroShot


SAMPLES = [
    {"id": 7, "cve_id": "CVE-A", "language": "C", "code": "int sample_a(void) { return 0; }", "label": "SAFE"},
    {"id": 8, "cve_id": "CVE-B", "language": "C", "code": "int sample_b(char *s) { gets(s); }", "label": "VULNERABLE"},
]


class RecordingModel(BaseModel):
    def __init__(self, item, cfg, calls, interrupt_at=None):
        super().__init__(item["name"], cfg)
        self.calls = calls
        self.interrupt_at = interrupt_at

    def generate(self, prompt):
        self.calls.append({"prompt": prompt, "settings": self.gen_cfg.copy()})
        if self.interrupt_at and len(self.calls) == self.interrupt_at:
            raise KeyboardInterrupt()
        self._set_generation_info({"eval_count": 4, "prompt_eval_count": 100, "done_reason": "stop"})
        return "Final answer: VULNERABLE" if self.gen_cfg["seed"] % 2 else "SAFE"


def config(section="B"):
    return {"section": section, "datasets": ["fixture"],
            "models": [{"name": "fixture", "backend": "dummy"}],
            "families": ["adaptive_cot", "self_consistency"], "variants": ["reference", "paraphrase"],
            "components": list(COMPONENTS), "voting_bases": ["cot", "adaptive_cot"],
            "protocols": ["verdict_first"], "parser_modes": ["strict", "structured", "full"],
            "seeds": [42], "votes": 5, "min_valid_votes": 3,
            "generation": {"temperature": 0.2, "seed": 999, "max_new_tokens": 250}}


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class AccuracyTests(unittest.TestCase):
    def test_unresolved_safe_sample_counts_in_accuracy_denominator(self):
        tracker = Metrics()
        tracker.add("safe", "safe")
        tracker.add("safe", "unknown")
        tracker.compute()
        self.assertEqual(tracker.Accuracy, 0.5)
        self.assertEqual(tracker.Coverage, 0.5)
        self.assertEqual(tracker.Incorrect, 1)

    def test_accuracy_includes_all_six_outcomes(self):
        tracker = Metrics(TP=1, TN=1, FP=1, FN=1, UnFN=1, Incorrect=1)
        tracker.compute()
        self.assertAlmostEqual(tracker.Accuracy, 2 / 6)
        self.assertEqual(tracker.Precision, 0.5)
        self.assertAlmostEqual(tracker.Recall, 1 / 3)
        self.assertAlmostEqual(tracker.F1, 0.4)
        self.assertAlmostEqual(tracker.AbstentionRate, 2 / 6)
        self.assertAlmostEqual(tracker.Coverage, 4 / 6)
        self.assertAlmostEqual(tracker.EffectiveF1, 0.4 * 4 / 6)

    def test_empty_and_all_unknown_accuracy_is_zero(self):
        for tracker in (Metrics(), Metrics(UnFN=2, Incorrect=3)):
            with self.subTest(tracker=tracker):
                tracker.compute()
                self.assertEqual(tracker.Accuracy, 0.0)

    def test_saved_counter_state_recomputes_accuracy(self):
        tracker = Metrics.from_state({"TP": 0, "TN": 1, "FP": 0, "FN": 0,
                                      "UnFN": 0, "Incorrect": 1, "Unknown": 1, "Accuracy": 1.0})
        self.assertEqual(tracker.Accuracy, 0.5)
        self.assertEqual(tracker.Unknown, 1)

    def test_record_refresh_changes_only_accuracy_without_mutating_source(self):
        record = {"TP": 1, "TN": 1, "FP": 1, "FN": 1, "UnFN": 1, "Incorrect": 1,
                  "Accuracy": 2 / 5, "Precision": 0.5, "Recall": 1 / 3, "F1": 0.4,
                  "Coverage": 4 / 6, "AbstentionRate": 2 / 6, "EffectiveF1": 0.4 * 4 / 6,
                  "params": {"seed": 42}, "predictions": []}
        original = copy.deepcopy(record)
        refreshed = refresh_record_accuracy(record)
        self.assertIsNot(refreshed, record)
        self.assertIs(refreshed["params"], record["params"])
        self.assertEqual(record, original)
        self.assertEqual(refreshed, {**record, "Accuracy": 2 / 6})

    def test_record_refresh_can_use_saved_predictions(self):
        record = {"Accuracy": 1.0, "TN": 1, "predictions": [
            {"gold": "safe", "pred": "safe"}, {"gold": "safe", "pred": "unknown"}]}
        refreshed = refresh_record_accuracy(record)
        self.assertEqual(refreshed["Accuracy"], 0.5)
        self.assertEqual(record["Accuracy"], 1.0)

    def test_record_refresh_preserves_scores_without_complete_evidence(self):
        for record in ({"Accuracy": 0.75}, {"Accuracy": 0.75, "TN": 1},
                       {"Accuracy": 0.75, "predictions": []},
                       {"Accuracy": 0.75, "predictions": [{"pred": "safe"}]}):
            with self.subTest(record=record):
                self.assertEqual(refresh_record_accuracy(record), record)


class DatasetTests(unittest.TestCase):
    def test_csv_keeps_ids_multiline_code_and_label_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "samples.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["id", "language", "code", "label"])
                writer.writeheader()
                writer.writerows([
                    {"id": 7, "language": " C ", "code": "  f(a, b);\nreturn 0;\n", "label": " vulnerable "},
                    {"id": 8, "language": " ", "code": "return 1;", "label": ""},
                ])
            samples = dataset_loader.load_dataset({"name": "fixture", "source": "local", "path": str(path)})
            self.assertEqual(samples, [
                {"id": 7, "language": "C", "code": "  f(a, b);\nreturn 0;\n", "label": "VULNERABLE"},
                {"id": 8, "language": "unknown", "code": "return 1;", "label": "UNKNOWN"},
            ])

    def test_names_and_hugging_face_aliases_select_the_expected_loader(self):
        fake_hf = Mock(return_value=[{"code": "x", "label": "SAFE"}])
        configured = {"registered": {"name": "registered", "source": "hf"}}
        module = SimpleNamespace(load_hf_dataset=fake_hf)
        with patch.object(dataset_loader, "_load_dataset_config", return_value=configured):
            with patch.dict(sys.modules, {"code_datasets.hf_loader": module}):
                for selection in ["registered", {"name": "direct", "source": "HF"}, "bigvul"]:
                    self.assertEqual(dataset_loader.load_dataset(selection), fake_hf.return_value)
        self.assertEqual([call.args[0] for call in fake_hf.call_args_list], ["registered", "direct", "bigvul"])

    def test_missing_csv_and_unknown_sources_keep_their_existing_behavior(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.csv"
            self.assertEqual(dataset_loader.load_dataset({"name": "fixture", "path": str(path)}), [])
        with self.assertRaisesRegex(ValueError, "Unknown dataset source"):
            dataset_loader.load_dataset({"name": "fixture", "source": "unsupported"})

    def test_csv_keeps_cluster_metadata_and_exact_code_through_the_study(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "samples.csv"
            code = "\n  int f(void) { return 0; }\n\n"
            with path.open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=["id", "language", "code", "label", "cve_id", "pair_id", "project"])
                writer.writeheader()
                for index in (1, 2):
                    writer.writerow({"id": index, "language": "C", "code": code, "label": "SAFE",
                                     "cve_id": f"CVE-{index}", "pair_id": f"pair-{index}", "project": " project "})
            samples = dataset_loader.load_dataset({"name": "fixture", "path": str(path)})
            self.assertTrue(all(s["code"] == code and s["project"] == "project" for s in samples))
            self.assertEqual([s["pair_id"] for s in samples], ["pair-1", "pair-2"])
            cfg = config()
            cfg["families"] = ["zero_shot"]
            output = Path(folder) / "study"
            run_study(cfg, output, pilot=True, dataset_loader=lambda _: samples,
                      model_loader=lambda item, settings: RecordingModel(item, settings, []), progress=lambda _: None)
            prompts = lines(output / "prompts.jsonl")
            self.assertTrue(all(code in p["text"] for p in prompts))
            result = analyze_study(output, bootstrap=20)
            paired = [r for r in result["template_summaries"] if "clusters" in r]
            self.assertTrue(paired)
            self.assertTrue(all(r["clusters"] == 2 and r["cve_bootstrap_ci95"] is not None for r in paired))

    def test_hf_loader_retains_available_matching_metadata_without_network(self):
        fake_load = Mock(return_value=[{"func_before": "  code\n", "target": 1,
                                       "cve_id": " CVE-A ", "pair_id": "pair-a", "commit_id": "commit-a"}])
        path = Path(__file__).resolve().parents[1] / "code_datasets" / "hf_loader.py"
        spec = importlib.util.spec_from_file_location("code_datasets._hf_loader_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"datasets": SimpleNamespace(load_dataset=fake_load),
                                      "huggingface_hub": SimpleNamespace(HfFolder=None)}):
            spec.loader.exec_module(module)
        module.ensure_hf_login = Mock()
        rows = module.load_hf_dataset("bigvul")
        self.assertEqual(rows[0]["code"], "  code\n")
        self.assertEqual(rows[0]["cve_id"], "CVE-A")
        self.assertEqual(rows[0]["pair_id"], "pair-a")

    def test_cve_pair_order_metadata_and_filtering_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            cve = Path(folder) / "CVE-A"
            cve.mkdir()
            (cve / "README.txt").write_text("Files changed:\n  1. sample.c\n  2. notes.txt\n  3. solo.py\n")
            (cve / "01_before_sample.c.txt").write_text("before\n")
            (cve / "01_after_sample.c.txt").write_text("after\n")
            (cve / "02_before_notes.txt.txt").write_text("documentation")
            (cve / "03_before_solo.py.txt").write_text("print(input())")
            samples = dataset_loader.load_dataset({"name": "cvefixes_fixture", "path": folder})
            self.assertEqual([(s["id"], s["filename"], s["language"], s["label"], s["code"]) for s in samples],
                             [(0, "sample.c", "C", "VULNERABLE", "before\n"),
                              (1, "sample.c", "C", "SAFE", "after\n"),
                              (2, "solo.py", "Python", "VULNERABLE", "print(input())")])
            self.assertTrue(all(s["cve_id"] == "CVE-A" for s in samples))


class TemplateTests(unittest.TestCase):
    def test_wording_variants_change_only_the_shared_task_line(self):
        task_lines = {variant: set() for variant in VARIANTS}
        for family in ("zero_shot", "few_shot", "cot", "adaptive_cot", "self_consistency"):
            for protocol in AVAILABLE_OUTPUT_PROTOCOLS:
                reference = render_template(family, "reference", protocol).split("\n", 2)
                for variant in VARIANTS:
                    prompt = render_template(family, variant, protocol)
                    role, task, rest = prompt.split("\n", 2)
                    self.assertEqual(role, ROLE_INSTRUCTION)
                    self.assertEqual(prompt.count(ROLE_INSTRUCTION), 1)
                    self.assertEqual(prompt.splitlines()[0], ROLE_INSTRUCTION)
                    self.assertEqual(rest, reference[2])
                    task_lines[variant].add(task)
        self.assertTrue(all(len(values) == 1 for values in task_lines.values()))
        self.assertEqual(len({next(iter(values)) for values in task_lines.values()}), 4)

    def test_dashboard_prompts_keep_the_shared_role_and_their_own_technique(self):
        header = f"{ROLE_INSTRUCTION}\n{TASK_INSTRUCTION}\n\n"
        prompts = {}
        for builder in (ZeroShot(), FewShot(), CoT(), AdaptiveCoT(), SelfVerification()):
            for protocol in AVAILABLE_OUTPUT_PROTOCOLS:
                if hasattr(builder, "apply_with_context"):
                    prompt = builder.apply_with_context(None, CODE_SLOT, {}, output_protocol=protocol)
                else:
                    prompt = builder.apply(None, CODE_SLOT, {})
                self.assertTrue(prompt.startswith(header))
                self.assertEqual(prompt.count(ROLE_INSTRUCTION), 1)
                self.assertEqual(prompt.count(EXAMPLES), int(builder.name == "few_shot"))
                prompts[builder.name] = prompt
        for family in ("zero_shot", "few_shot"):
            self.assertIn("Give a direct classification without a step-by-step explanation.", prompts[family])
            self.assertNotIn("Choose how much reasoning", prompts[family])
        self.assertIn("Reason through these factors step by step.", prompts["cot"])
        self.assertNotIn("Choose how much reasoning", prompts["cot"])
        self.assertIn("answer directly without a step-by-step explanation", prompts["adaptive_cot"])
        self.assertIn("Otherwise, reason through the security risks step by step.", prompts["adaptive_cot"])
        self.assertIn("If you find a mistake, revise your answer.", prompts["self_verification"])
        generic = BasePrompt().apply(CODE_SLOT)
        self.assertTrue(generic.startswith(header))
        self.assertIn(f"<target_code>\n{CODE_SLOT}\n</target_code>", generic)

    def test_reference_matches_current_prompt_builders(self):
        for family, builder in [("zero_shot", ZeroShot()), ("few_shot", FewShot()),
                                ("cot", CoT()), ("adaptive_cot", AdaptiveCoT())]:
            for protocol in AVAILABLE_OUTPUT_PROTOCOLS:
                if hasattr(builder, "apply_with_context"):
                    expected = builder.apply_with_context(None, CODE_SLOT, {}, output_protocol=protocol)
                else:
                    expected = builder.apply(None, CODE_SLOT, {})
                expected = expected.rstrip() + build_output_instruction(protocol)
                self.assertEqual(render_template(family, "reference", protocol), expected)

    def test_variants_leave_code_examples_and_protocol_unchanged(self):
        code = 'int special(void) {\n\n/* You are a secure code auditor. */\n return 9;\n}'
        for family in ("zero_shot", "few_shot", "cot", "adaptive_cot", "self_consistency"):
            for protocol in AVAILABLE_OUTPUT_PROTOCOLS:
                prompts = [render_prompt(family, variant, code, protocol) for variant in VARIANTS]
                self.assertEqual(len(set(prompts)), len(VARIANTS))
                for prompt in prompts:
                    self.assertEqual(prompt.count(code), 1)
                    self.assertIn(f"<target_code>\n{code}\n</target_code>", prompt)
                    self.assertNotIn("selected prompt strategy", prompt)
                    self.assertEqual(prompt.count(ROLE_INSTRUCTION), 1)
                    self.assertEqual(prompt.splitlines()[0], ROLE_INSTRUCTION)
                    self.assertTrue(prompt.endswith(build_output_instruction(protocol)))
                    if family == "few_shot":
                        self.assertEqual(prompt.count(EXAMPLES), 1)
                if family == "self_consistency":
                    for variant, prompt in zip(VARIANTS, prompts):
                        self.assertEqual(prompt, render_prompt("adaptive_cot", variant, code, protocol))

    def test_components_keep_the_same_shared_scaffold(self):
        for protocol in AVAILABLE_OUTPUT_PROTOCOLS:
            off_prompts = [render_component_template(c, False, protocol) for c in COMPONENTS]
            self.assertEqual(len(set(off_prompts)), 1)
            for component in COMPONENTS:
                on = render_component_template(component, True, protocol)
                self.assertEqual(on.count(CODE_SLOT), 1)
                self.assertTrue(on.endswith(build_output_instruction(protocol)))
                self.assertIn("1) Inputs and trust boundaries", on)
                self.assertIn("4) Injection, race, and logic risks", on)
                self.assertTrue(on.startswith(f"{ROLE_INSTRUCTION}\n{TASK_INSTRUCTION}\n\n"))
                self.assertTrue(off_prompts[0].startswith(f"{ROLE_INSTRUCTION}\n{TASK_INSTRUCTION}\n\n"))
            self.assertIn(EXAMPLES, render_component_template("examples", True, protocol))
            self.assertNotIn(EXAMPLES, off_prompts[0])
            self.assertIn("Reason through these factors step by step.",
                          render_component_template("reasoning", True, protocol))
            self.assertNotIn("Reason through", off_prompts[0])

    def test_default_matrix_uses_four_wordings_and_two_verdict_orders(self):
        cfg = {"section": "B", "protocols": ["verdict_first", "verdict_last"]}
        conditions = build_conditions(cfg)
        self.assertEqual(len(conditions), 40)
        self.assertEqual({c["variant"] for c in conditions}, set(VARIANTS))

    def test_unknown_template_variants_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown prompt template"):
            render_template("zero_shot", "unsupported_variant")
        with self.assertRaisesRegex(ValueError, "Unsupported variants"):
            build_conditions({"section": "B", "variants": ["reference", "unsupported_variant"]})


class VotingTests(unittest.TestCase):
    def test_protocol_aliases_use_the_same_position_for_instructions_and_parsing(self):
        for alias in ("strict", "verdict_first", "first_line"):
            self.assertIn("FIRST LINE ONLY", build_output_instruction(alias))
            self.assertEqual(parse_verdict_details("SAFE\nVULNERABLE", mode="strict", output_protocol=alias)["label"], "safe")
        for alias in ("verdict_last", "last_line", "reason_first"):
            self.assertEqual(build_output_instruction(alias), build_output_instruction("verdict_last"))
            self.assertEqual(parse_verdict_details("SAFE\nVULNERABLE", mode="strict", output_protocol=alias)["label"], "vulnerable")
        with self.assertRaisesRegex(ValueError, "Unknown output protocol"):
            build_output_instruction("misspelled")
        with self.assertRaisesRegex(ValueError, "Unknown output protocol"):
            parse_verdict_details("SAFE", output_protocol="misspelled")
        with self.assertRaisesRegex(ValueError, "Unknown parser mode"):
            parse_verdict_details("SAFE", mode="misspelled")

    def test_requested_and_valid_majorities_on_the_same_pool(self):
        labels = ["safe", "safe", "vulnerable", "unknown", "unknown"]
        self.assertEqual(aggregate_votes(labels, "majority_requested")["label"], "unknown")
        self.assertEqual(aggregate_votes(labels, "majority_valid")["label"], "safe")
        self.assertEqual(aggregate_votes(labels, "majority_valid", 4)["reason"], "too_few_valid_votes")

    def test_ties_and_unknown_first_draw_are_not_silently_resolved(self):
        labels = ["unknown", "safe", "vulnerable", "safe", "vulnerable"]
        for policy in ("first", "majority_requested", "majority_valid"):
            self.assertEqual(aggregate_votes(labels, policy)["label"], "unknown")
        self.assertEqual(aggregate_votes(["unknown"] * 5)["reason"], "no_valid_votes")

    def test_five_valid_binary_votes_always_have_a_requested_majority(self):
        import itertools
        for labels in itertools.product(("safe", "vulnerable"), repeat=5):
            self.assertIn(aggregate_votes(labels)["label"], {"safe", "vulnerable"})


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "study"
        self.calls = []
        self.models = []

    def tearDown(self):
        self.temp.cleanup()

    def model_loader(self, item, cfg):
        model = RecordingModel(item, cfg, self.calls)
        self.models.append(model)
        return model

    def run_fixture(self, cfg=None, **kwargs):
        kwargs.setdefault("model_loader", self.model_loader)
        return run_study(cfg or config(), self.output, pilot=True,
                         dataset_loader=lambda _: copy.deepcopy(SAMPLES),
                         progress=lambda _: None, **kwargs)

    def test_full_study_runs_without_author_approval_records(self):
        cfg = config()
        cfg["models"] = [{"name": "fixture", "backend": "ollama"}]
        run_study(cfg, self.output, dataset_loader=lambda _: copy.deepcopy(SAMPLES),
                  model_loader=self.model_loader, progress=lambda _: None)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertFalse(manifest["pilot"])
        self.assertNotIn("template_reviews", manifest)
        self.assertTrue(all("review_id" not in condition for condition in manifest["conditions"]))
        self.assertEqual(len(self.calls), 20)

    def test_b_reuses_a_cot_first_draw_and_replays_all_parsers(self):
        self.run_fixture()
        self.assertEqual(len(self.calls), 20)  # 2 samples x 2 variants x 5 shared draws
        rows = lines(self.output / "predictions.jsonl")
        self.assertEqual(len(rows), 24)
        for sample in SAMPLES:
            for variant in ("reference", "paraphrase"):
                matched = [r for r in rows if r["sample_id"] == str(sample["id"])
                           and r["variant"] == variant and r["parser_mode"] == "full"]
                single = next(r for r in matched if r["family"] == "adaptive_cot")
                voted = next(r for r in matched if r["family"] == "self_consistency")
                self.assertEqual(single["generation_ids"], voted["generation_ids"][:1])
        saved = lines(self.output / "generations.jsonl")
        self.assertTrue(all(r["settings"]["max_new_tokens"] == 250 for r in saved))
        self.assertTrue(all(r["generation_info"]["prompt_eval_count"] == 100 for r in saved))
        self.assertEqual(self.models[0].gen_cfg["seed"], 999)
        self.assertEqual(len({draw_seed(42, "sample", i) for i in range(5)}), 5)
        analyze_study(self.output, bootstrap=20)

    def test_c_policies_share_generations_and_off_controls_are_reused(self):
        self.run_fixture(config("C"))
        self.assertEqual(len(self.calls), 28)  # (one off + three on + two pools of five) x 2
        rows = lines(self.output / "predictions.jsonl")
        for family in ("cot", "adaptive_cot"):
            policies = [r for r in rows if r["comparison"] == "voting" and r["family"] == family
                        and r["sample_id"] == "7" and r["parser_mode"] == "full"]
            self.assertEqual(len(policies), 3)
            self.assertTrue(all(r["generation_ids"] == policies[0]["generation_ids"] for r in policies))
            self.assertEqual(sorted(r["decision_calls"] for r in policies), [1, 5, 5])
        result = analyze_study(self.output, bootstrap=20)
        contrasts = result["component_and_voting_contrasts"]
        self.assertEqual(len(contrasts), 30)
        adaptive = [r for r in contrasts if r["comparison"] == "adaptive_minus_unconditional_reasoning"]
        self.assertEqual(len(adaptive), 3)
        voting = [r for r in contrasts if r["comparison"] == "majority_valid_minus_requested"]
        self.assertTrue(all(r["same_decision_budget"] for r in voting))
        baseline = [r for r in contrasts if r["comparison"].endswith("_minus_first")]
        self.assertTrue(all(not r["same_decision_budget"] for r in baseline))

    def test_generation_diagnostics_count_only_decision_calls(self):
        self.run_fixture(config("C"))
        rows = lines(self.output / "predictions.jsonl")
        first = next(r for r in rows if r["comparison"] == "voting" and r["aggregation"]["policy"] == "first")
        voted = next(r for r in rows if r["comparison"] == "voting" and r["aggregation"]["policy"] == "majority_valid")
        self.assertEqual(first["decision_output_tokens"], 4)
        self.assertEqual(voted["decision_output_tokens"], 20)
        self.assertEqual(first["decision_prompt_tokens"], 100)
        self.assertEqual(first["decision_output_limit_hits"], 0)
        result = analyze_study(self.output, bootstrap=0)
        self.assertIn("diagnostics", result["design_notes"])

    def test_greedy_voting_is_rejected_before_loading_models(self):
        for override in ({"temperature": 0}, {"num_beams": 2}):
            cfg = config()
            cfg["models"][0].update(override)
            with self.assertRaisesRegex(ValueError, "Repeated voting"):
                self.run_fixture(cfg)
        self.assertFalse(self.models)
        self.assertFalse(self.output.exists())

    def test_resume_keeps_predictions_when_resolved_model_changes(self):
        self.run_fixture()
        before = (self.output / "predictions.jsonl").read_bytes()
        original_manifest = (self.output / "manifest.json").read_bytes()
        with patch.object(RecordingModel, "get_model_info", return_value={"revision": "new-weights"}):
            with self.assertRaisesRegex(ValueError, "resolved model"):
                self.run_fixture(resume=True)
        self.assertEqual((self.output / "predictions.jsonl").read_bytes(), before)
        self.assertEqual((self.output / "manifest.json").read_bytes(), original_manifest)
        self.assertFalse((self.output / "predictions.pending.jsonl").exists())
        analyze_study(self.output, bootstrap=0)

    def test_invalid_generation_settings_fail_before_any_calls(self):
        invalid = [
            {"max_new_tokens": 8.5}, {"context_window": 32.9}, {"num_ctx": True},
            {"context_window": 2048, "num_ctx": 4096}, {"temperature": float("nan")},
            {"stop_sequences": "END"}, {"chat_template_kwargs": {"add_generation_prompt": False}},
        ]
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                cfg = config()
                cfg["generation"].update(overrides)
                with self.assertRaises(ValueError):
                    self.run_fixture(cfg)
                self.assertFalse(self.output.exists())
        self.assertFalse(self.calls)

    def test_failed_resume_progress_preserves_a_completed_run(self):
        self.run_fixture()
        original = {name: (self.output / name).read_bytes()
                    for name in ("manifest.json", "predictions.jsonl", "generations.jsonl")}
        previous_calls = len(self.calls)
        with self.assertRaises(BrokenPipeError):
            run_study(config(), self.output, pilot=True, resume=True,
                      dataset_loader=lambda _: copy.deepcopy(SAMPLES), model_loader=self.model_loader,
                      progress=Mock(side_effect=BrokenPipeError("closed output pipe")))
        self.assertEqual(len(self.calls), previous_calls)
        for name, content in original.items():
            self.assertEqual((self.output / name).read_bytes(), content)
        analyze_study(self.output, bootstrap=0)

    def test_model_specific_context_alias_is_applied_and_recorded(self):
        cfg = config()
        cfg["generation"]["context_window"] = 2048
        cfg["models"][0]["num_ctx"] = 4096
        self.run_fixture(cfg)
        saved = lines(self.output / "generations.jsonl")
        self.assertTrue(all(c["settings"]["context_window"] == 4096 and "num_ctx" not in c["settings"] for c in saved))

    def test_analysis_rejects_incomplete_or_inconsistent_saved_predictions(self):
        self.run_fixture()
        analyze_study(self.output, bootstrap=0)
        predictions = self.output / "predictions.jsonl"
        original = predictions.read_bytes()
        rows = lines(predictions)
        old_metrics = (self.output / "metrics.csv").read_bytes()
        old_analysis = (self.output / "analysis.json").read_bytes()
        cases = {
            "missing approach": [r for r in rows if r["family"] != "self_consistency"],
            "missing sample": [r for r in rows if r["sample_id"] != "8"],
            "missing parser": [r for r in rows if r["parser_mode"] != "strict"],
            "missing row": rows[:-1], "duplicate row": rows + rows[:1],
        }
        for name, field, value in [("invalid label", "pred", "bad-label"),
                                   ("inconsistent outcome", "pred", "vulnerable" if rows[0]["pred"] == "safe" else "safe"),
                                   ("wrong CVE", "cve_id", "OTHER"),
                                   ("wrong model name", "model", "other-model"),
                                   ("wrong budget", "decision_calls", 99)]:
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            cases[name] = changed
        for name, changed in cases.items():
            with self.subTest(case=name):
                predictions.write_text("".join(json.dumps(row) + "\n" for row in changed), encoding="utf-8")
                with self.assertRaises(ValueError):
                    analyze_study(self.output, bootstrap=0)
                self.assertEqual((self.output / "metrics.csv").read_bytes(), old_metrics)
                self.assertEqual((self.output / "analysis.json").read_bytes(), old_analysis)
        predictions.write_bytes(original)

    def test_analysis_records_provenance_without_changing_generation_manifest(self):
        cfg = config()
        cfg["models"][0]["secret"] = "fixture-secret"
        self.run_fixture(cfg)
        original_manifest = (self.output / "manifest.json").read_bytes()
        result = analyze_study(self.output, bootstrap=0)
        provenance = result["analysis_provenance"]
        self.assertEqual(provenance["predictions_sha256"],
                         hashlib.sha256((self.output / "predictions.jsonl").read_bytes()).hexdigest())
        metrics_source = Path(__file__).resolve().parents[1] / "evaluation" / "metrics.py"
        self.assertEqual(provenance["source_hashes"]["evaluation/metrics.py"],
                         hashlib.sha256(metrics_source.read_text(encoding="utf-8").encode()).hexdigest())
        self.assertEqual((self.output / "manifest.json").read_bytes(), original_manifest)
        manifest = json.loads(original_manifest)
        manifest.pop("model_selections")
        (self.output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        analyze_study(self.output, bootstrap=0)

    def test_analysis_identifies_equal_budgets_for_one_draw_voting(self):
        cfg = config("C")
        cfg.update(votes=1, min_valid_votes=1)
        self.run_fixture(cfg)
        result = analyze_study(self.output, bootstrap=0)
        contrasts = [r for r in result["component_and_voting_contrasts"] if "same_decision_budget" in r]
        self.assertTrue(contrasts)
        self.assertTrue(all(r["same_decision_budget"] for r in contrasts))

    def test_backend_failure_preserves_diagnostics_and_remains_unknown(self):
        class FailedModel(RecordingModel):
            def generate(self, prompt):
                self._set_generation_info({"status": "error", "prompt_eval_count": 999})
                raise ValueError("context exceeded")
        cfg = config()
        cfg["families"] = ["zero_shot"]
        cfg["variants"] = ["reference"]
        self.run_fixture(cfg, model_loader=lambda item, settings: FailedModel(item, settings, []))
        saved = lines(self.output / "generations.jsonl")
        rows = lines(self.output / "predictions.jsonl")
        self.assertTrue(all(r["generation_info"]["prompt_eval_count"] == 999 for r in saved))
        self.assertTrue(all(r["pred"] == "unknown" and r["decision_generation_errors"] == 1 for r in rows))
        self.assertTrue(all(r["decision_output_limit_hits"] is None for r in rows))

    def test_models_and_run_seeds_use_the_same_samples_and_settings(self):
        cfg = config()
        cfg["families"] = ["zero_shot", "cot"]
        cfg["seeds"] = [42, 43]
        cfg["models"] = [{"name": name, "backend": "dummy"} for name in ("model_a", "model_b")]
        self.run_fixture(cfg)
        saved = lines(self.output / "generations.jsonl")
        self.assertEqual(len(saved), 32)
        matched = {}
        for call in saved:
            key = (call["run_seed"], call["sample_uid"], call["prompt_sha256"])
            matched.setdefault(key, []).append(call)
        self.assertTrue(all(len(group) == 2 for group in matched.values()))
        self.assertTrue(all(group[0]["settings"] == group[1]["settings"] for group in matched.values()))
        result = analyze_study(self.output, bootstrap=0)
        self.assertEqual(len(result["rankings"]), 36)  # 2 models x 2 seeds x 3 parsers x 3 metrics

    def test_resume_recovers_an_incomplete_tail_without_repeating_saved_calls(self):
        cfg = config()
        cfg["variants"] = ["reference"]
        def interrupted_loader(item, settings):
            return RecordingModel(item, settings, self.calls, interrupt_at=3)
        with self.assertRaises(KeyboardInterrupt):
            run_study(cfg, self.output, pilot=True, dataset_loader=lambda _: SAMPLES,
                      model_loader=interrupted_loader, progress=lambda _: None)
        self.assertEqual(len(lines(self.output / "generations.jsonl")), 2)
        with (self.output / "generations.jsonl").open("ab") as stream:
            stream.write(b'{"generation_id":')
        self.run_fixture(cfg, resume=True)
        self.assertEqual(len(self.calls), 11)  # includes the interrupted, unsaved request
        saved = lines(self.output / "generations.jsonl")
        self.assertEqual(len(saved), 10)
        self.assertEqual(len({r["generation_id"] for r in saved}), 10)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["new_calls_this_session"], 8)
        before = (self.output / "predictions.jsonl").read_bytes()
        cfg["generation"]["temperature"] = 0.7
        with self.assertRaisesRegex(ValueError, "Resume refused"):
            self.run_fixture(cfg, resume=True)
        self.assertEqual((self.output / "predictions.jsonl").read_bytes(), before)

    def test_verdict_placement_has_its_own_paired_contrasts(self):
        cfg = config("C")
        cfg["protocols"] = ["verdict_first", "verdict_last"]
        self.run_fixture(cfg)
        self.assertEqual(len(self.calls), 56)
        result = analyze_study(self.output, bootstrap=0)
        self.assertEqual(len(result["protocol_contrasts"]), 36)
        self.assertTrue(all(row["samples"] == 2 for row in result["protocol_contrasts"]))

    def test_template_study_also_compares_verdict_orders(self):
        cfg = config()
        cfg["protocols"] = ["verdict_first", "verdict_last"]
        self.run_fixture(cfg)
        result = analyze_study(self.output, bootstrap=0)
        self.assertEqual(len(result["protocol_contrasts"]), 12)

    def test_unknown_gold_and_duplicate_ids_fail_before_inference(self):
        bad = copy.deepcopy(SAMPLES)
        bad[0]["label"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "gold label"):
            run_study(config(), self.output, pilot=True, dataset_loader=lambda _: bad)
        bad[0]["label"] = "SAFE"
        bad[1]["id"] = bad[0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate sample"):
            run_study(config(), self.output, pilot=True, dataset_loader=lambda _: bad)
        self.assertFalse(self.output.exists())


class BackendTests(unittest.TestCase):
    def test_engine_reuses_a_defensive_copy_of_resolved_model_metadata(self):
        model = RecordingModel({"name": "fixture"}, {"seed": 42}, [])
        snapshot = {"backend": "dummy", "details": {"revision": "fixed"}}
        with patch.object(model, "get_model_info", side_effect=AssertionError("Metadata was already resolved")):
            engine = InferenceEngine(model, {"name": "fixture", "backend": "dummy"}, None,
                                     performance={"response_cache": False}, model_info=snapshot)
            try:
                managed = ManagedModel(engine)
                snapshot["details"]["revision"] = "changed"
                returned = managed.get_model_info()
                returned["details"]["revision"] = "also changed"
                self.assertEqual(managed.get_model_info()["details"]["revision"], "fixed")
            finally:
                engine.close()

    def test_study_resolves_model_metadata_once_per_loaded_model(self):
        cfg = {"section": "B", "models": [{"name": "fixture", "backend": "dummy"}],
               "datasets": ["fixture"], "families": ["zero_shot"], "variants": ["reference"],
               "protocols": ["verdict_first"], "parser_modes": ["strict"],
               "performance": {"response_cache": False}}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(RecordingModel, "get_model_info", return_value={"revision": "fixed"}) as info:
                run_study(cfg, Path(directory) / "study", pilot=True, dataset_loader=lambda _: SAMPLES,
                          model_loader=lambda item, settings: RecordingModel(item, settings, []),
                          progress=lambda _: None)
            self.assertEqual(info.call_count, 1)

    def test_context_aliases_preserve_model_override_precedence(self):
        base = {"context_window": 2048, "max_new_tokens": 8}
        override = {"num_ctx": 4096}
        self.assertEqual(merge_generation_settings(base, override), {"context_window": 4096, "max_new_tokens": 8})
        self.assertEqual(base, {"context_window": 2048, "max_new_tokens": 8})
        self.assertEqual(override, {"num_ctx": 4096})
        self.assertEqual(merge_generation_settings({"num_ctx": 2048}, {"context_window": 4096}),
                         {"context_window": 4096})
        with patch.object(model_loading, "OllamaModel") as factory:
            model_loading.load_model({"name": "fixture", "backend": "ollama", **override}, base)
        self.assertEqual(factory.call_args.args[1]["context_window"], 4096)
        self.assertNotIn("num_ctx", factory.call_args.args[1])

    def hf_backend(self, native_template="native-wrapper", **settings):
        class Batch(dict):
            def to(self, device):
                return self

        batch = Batch(input_ids=SimpleNamespace(shape=(1, 3)))
        self.tokenizer = Mock(chat_template=native_template, pad_token_id=None,
                              eos_token_id=99, model_max_length=64, return_value=batch)
        self.tokenizer.apply_chat_template.return_value = "native user prompt assistant"
        self.tokenizer.decode.return_value = "SAFE"
        self.weights = Mock(config=SimpleNamespace(max_position_embeddings=64, _commit_hash="resolved-sha"),
                            generation_config=SimpleNamespace(eos_token_id=99))
        self.weights.to.return_value = self.weights
        self.weights.generate.return_value = [[1, 2, 3, 4, 99]]
        self.tokenizer_loader = Mock(return_value=self.tokenizer)
        self.weights_loader = Mock(return_value=self.weights)
        fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False), device=lambda d: d,
                                     manual_seed=Mock(), no_grad=nullcontext)
        fake_transformers = SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=self.tokenizer_loader),
                                            AutoModelForCausalLM=SimpleNamespace(from_pretrained=self.weights_loader))
        path = Path(__file__).resolve().parents[1] / "models" / "hf_model.py"
        spec = importlib.util.spec_from_file_location("models._hf_backend_test", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"torch": fake_torch, "transformers": fake_transformers}):
            spec.loader.exec_module(module)
        return module.HFModel("fixture", {"max_new_tokens": 8, "temperature": 0.2, **settings})

    def test_hf_uses_native_chat_format_without_duplicate_control_tokens(self):
        model = self.hf_backend(revision="pinned-sha", chat_template_kwargs={"enable_thinking": False})
        self.assertEqual(model.generate("task and code"), "SAFE")
        self.tokenizer.apply_chat_template.assert_called_once_with(
            [{"role": "user", "content": "task and code"}], tokenize=False,
            add_generation_prompt=True, enable_thinking=False)
        self.tokenizer.assert_called_once_with("native user prompt assistant", return_tensors="pt",
                                              add_special_tokens=False)
        self.tokenizer_loader.assert_called_once_with("fixture", revision="pinned-sha")
        self.weights_loader.assert_called_once_with("fixture", torch_dtype="auto", revision="pinned-sha")
        self.assertEqual(model.get_model_info()["resolved_revision"], "resolved-sha")
        self.assertEqual(model.consume_generation_info()["eval_count"], 2)

    def test_hf_raw_mode_and_greedy_decoding_are_explicit(self):
        model = self.hf_backend(input_format="raw", temperature=0)
        model.generate("plain completion input")
        self.tokenizer.apply_chat_template.assert_not_called()
        self.tokenizer.assert_called_once_with("plain completion input", return_tensors="pt", add_special_tokens=True)
        args = self.weights.generate.call_args.kwargs
        self.assertFalse(args["do_sample"])
        self.assertNotIn("temperature", args)
        self.assertNotIn("top_p", args)

    def test_hf_base_models_and_required_chat_templates(self):
        model = self.hf_backend(native_template=None)
        model.generate("base completion input")
        self.tokenizer.apply_chat_template.assert_not_called()
        self.assertEqual(model.consume_generation_info()["input_format"], "raw")
        with self.assertRaisesRegex(ValueError, "requires a tokenizer chat template"):
            self.hf_backend(native_template=None, input_format="chat")
        self.weights_loader.assert_not_called()

    def test_hf_context_overflow_is_reported_without_truncation(self):
        model = self.hf_backend(context_window=10)
        with self.assertRaisesRegex(ContextWindowExceeded, "input was not truncated"):
            model.generate("too long with its output budget")
        self.weights.generate.assert_not_called()
        info = model.consume_generation_info()
        self.assertEqual(info["status"], "error")
        self.assertEqual(info["prompt_eval_count"], 3)

    def test_hf_stop_markers_are_excluded_and_earliest_match_wins(self):
        model = self.hf_backend(max_new_tokens=2, stop_sequences=["LATER", "<END>"])
        self.weights.generate.return_value = [[1, 2, 3, 4, 5]]
        self.tokenizer.decode.return_value = "SAFE<END>extra LATER"
        self.assertEqual(model.generate("task"), "SAFE")
        args = self.weights.generate.call_args.kwargs
        self.assertEqual(args["stop_strings"], ["LATER", "<END>"])
        self.assertIs(args["tokenizer"], self.tokenizer)
        info = model.consume_generation_info()
        self.assertEqual(info["done_reason"], "stop_sequence")
        self.assertFalse(info["output_limit_reached"])

    def test_hf_empty_stop_list_disables_checkpoint_stop_strings(self):
        model = self.hf_backend(stop_sequences=[])
        self.weights.generation_config.stop_strings = ["checkpoint-stop"]
        model.generate("task")
        args = self.weights.generate.call_args.kwargs
        self.assertIsNone(args["stop_strings"])
        self.assertNotIn("tokenizer", args)

    def test_hf_forced_eos_at_the_budget_is_reported_as_a_limit(self):
        model = self.hf_backend(max_new_tokens=2)
        self.weights.generation_config.forced_eos_token_id = 99
        model.generate("task")
        info = model.consume_generation_info()
        self.assertTrue(info["forced_eos_at_output_limit"])
        self.assertTrue(info["output_limit_reached"])
        self.assertEqual(info["done_reason"], "length")

    def test_hf_distinguishes_output_cap_from_eos(self):
        model = self.hf_backend(max_new_tokens=2)
        self.weights.generate.return_value = [[1, 2, 3, 4, 5]]
        model.generate("task")
        self.assertTrue(model.consume_generation_info()["output_limit_reached"])
        self.weights.generate.return_value = [[1, 2, 3, 4, 99]]
        model.generate("task")
        self.assertFalse(model.consume_generation_info()["output_limit_reached"])

    def test_ollama_forwards_context_and_preserves_separate_thinking(self):
        model = OllamaModel("fixture", {"context_window": 2048, "think": False})
        model.context_guard.ensure_verified = Mock()  # Input guards have separate behavioral tests.
        model.context_guard.loaded_window = Mock(return_value=2048)
        model.session = Mock()
        response = model.session.post.return_value
        response.status_code = 200
        response.json.return_value = {"response": "SAFE", "thinking": "separate reasoning", "done": True,
                                      "done_reason": "length", "prompt_eval_count": 100}
        self.assertEqual(model.generate("task and code"), "SAFE")
        payload = model.session.post.call_args.kwargs["json"]
        self.assertEqual(payload["options"]["num_ctx"], 2048)
        self.assertIs(payload["think"], False)
        info = model.consume_generation_info()
        self.assertEqual(info["thinking_output"], "separate reasoning")
        self.assertTrue(info["output_limit_reached"])

    def test_ollama_records_model_wrapper_digest_and_runtime(self):
        for selected, returned in (("fixture", "fixture:latest"), ("fixture:latest", "fixture")):
            model = OllamaModel(selected, {})
            model.session = Mock()
            model.session.post.return_value.json.return_value = {
                "template": "native-wrapper", "parameters": "num_ctx 4096", "template_source": "go_template"}
            tags = Mock()
            tags.json.return_value = {"models": [{"name": returned, "digest": "weights-digest"}]}
            version = Mock()
            version.json.return_value = {"version": "fixture-runtime"}
            model.session.get.side_effect = [tags, version]
            info = model.get_model_info()
            self.assertEqual(info["digest"], "weights-digest")
            self.assertEqual(info["template"], "native-wrapper")
            self.assertEqual(info["template_source"], "go_template")
            self.assertEqual(info["runtime_version"], "fixture-runtime")

    def test_dashboard_self_consistency_draws_use_distinct_seeds_and_restore_settings(self):
        calls = []
        original = {"seed": 17, "temperature": 0.2}
        model = RecordingModel({"name": "fixture"}, original, calls)
        result = SelfConsistency().apply_with_context(model, "code", {"sc_samples": 5})
        self.assertEqual([c["settings"]["seed"] for c in calls], list(range(17, 22)))
        self.assertIs(model.gen_cfg, original)
        self.assertTrue(all(c["prompt"].startswith(f"{ROLE_INSTRUCTION}\n{TASK_INSTRUCTION}\n\n") for c in calls))
        self.assertTrue(all(c["prompt"].count(ROLE_INSTRUCTION) == 1 for c in calls))
        self.assertEqual(result["label"], "vulnerable")
        model.gen_cfg = {"temperature": 0}
        with self.assertRaisesRegex(ValueError, "Self-consistency requires"):
            SelfConsistency().apply_with_context(model, "code", {"sc_samples": 5})

    def test_dashboard_self_consistency_keeps_other_votes_after_one_failure(self):
        calls = []
        original = {"seed": 17, "temperature": 0.2}
        class OneFailure(RecordingModel):
            def generate(self, prompt):
                super().generate(prompt)
                if len(calls) == 2:
                    self._set_generation_info({"status": "error", "seed": self.gen_cfg["seed"]})
                    raise RuntimeError("fixture failure")
                return "SAFE"
        model = OneFailure({"name": "fixture"}, original, calls)
        result = SelfConsistency().apply_with_context(model, "code", {"sc_samples": 5})
        self.assertEqual(len(calls), 5)
        self.assertEqual(result["label"], "safe")
        self.assertEqual(result["valid_votes"], 4)
        self.assertEqual(result["unknown_votes"], 1)
        self.assertIs(model.gen_cfg, original)
        error = result["generation_anomalies"][0]["generation_info"]
        self.assertEqual(error["error_type"], "RuntimeError")
        self.assertEqual(error["seed"], 18)

    def test_dashboard_self_consistency_still_honors_cancellation(self):
        calls = []
        original = {"seed": 17, "temperature": 0.2}
        model = RecordingModel({"name": "fixture"}, original, calls, interrupt_at=2)
        with self.assertRaises(KeyboardInterrupt):
            SelfConsistency().apply_with_context(model, "code", {"sc_samples": 5})
        self.assertEqual(len(calls), 2)
        self.assertIs(model.gen_cfg, original)


class AnalysisTests(unittest.TestCase):
    def test_clustered_interval_keeps_cve_pairs_together(self):
        reference, candidate = [], []
        for i, (gold, pred) in enumerate(zip(["vulnerable", "safe"] * 2,
                                            ["safe", "safe", "vulnerable", "vulnerable"])):
            shared = {"sample_uid": str(i), "cve_id": "A" if i < 2 else "B", "gold": gold}
            reference.append({**shared, "pred": pred})
            candidate.append({**shared, "pred": gold})
        result = paired_comparison(reference, candidate, bootstrap=200)
        self.assertEqual(result["label_disagreement"], 0.5)
        self.assertEqual(result["f1_difference"], 0.5)
        self.assertAlmostEqual(result["cve_bootstrap_ci95"][0], 1 / 3)
        self.assertEqual(result["cve_bootstrap_ci95"][1], 1)
        self.assertEqual(result["cve_bootstrap_ci95_by_metric"]["Coverage"], [0.0, 0.0])
        with self.assertRaisesRegex(ValueError, "same samples"):
            paired_comparison(reference, candidate[:-1])
        for row in reference + candidate:
            row.pop("cve_id")
        self.assertIsNone(paired_comparison(reference, candidate)["cve_bootstrap_ci95"])
        with self.assertRaisesRegex(ValueError, "one prediction per sample"):
            paired_comparison(reference + reference[:1], candidate)

    def test_rank_changes_are_reported_separately_for_each_run_seed(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            (output / "manifest.json").write_text(json.dumps({"pilot": True, "status": "completed"}))
            rows = []
            for seed in (42, 43):
                for family in ("zero_shot", "cot"):
                    for variant in ("reference", "paraphrase", "reworded"):
                        correct = (family == "cot") == (variant == "reference")
                        for i, gold in enumerate(("vulnerable", "safe")):
                            rows.append({"dataset": "fixture", "model_id": "m", "model": "fixture",
                                         "run_seed": seed, "protocol": "verdict_first", "parser_mode": "full",
                                         "condition": f"{family}/{variant}/verdict_first",
                                         "comparison": "templates", "family": family, "variant": variant,
                                         "sample_uid": str(i), "gold": gold,
                                         "pred": gold if correct else "safe",
                                         "aggregation": {"policy": "first"},
                                         "decision_calls": 1, "decision_seconds": 0.0})
            (output / "predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            result = analyze_study(output, bootstrap=0)
            ranks = [r for r in result["rankings"] if r["metric"] == "F1"]
            self.assertEqual({r["run_seed"] for r in ranks}, {42, 43})
            self.assertTrue(all(r["changed_from_reference"]["paraphrase"] for r in ranks))
            self.assertTrue(all(r["ranks"]["reference"]["cot"] == 1 for r in ranks))
            self.assertTrue(all(r["ranks"]["paraphrase"]["zero_shot"] == 1 for r in ranks))
            self.assertTrue(all(set(r["ranks"]) == {"reference", "paraphrase", "reworded"} for r in ranks))


if __name__ == "__main__":
    unittest.main()
