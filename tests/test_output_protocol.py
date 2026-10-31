"""Check that output formatting stays separate from prompting techniques."""

import unittest

from evaluation.label_parser import parse_verdict_details
from evaluation.output_protocol import AVAILABLE_OUTPUT_PROTOCOLS, build_output_instruction
from prompts.template_variants import COMPONENTS, FAMILIES, VARIANTS, render_component_template, render_prompt


class OutputProtocolTests(unittest.TestCase):
    def test_direct_families_request_one_word_without_changing_reasoning_families(self):
        instruction = "Return only the verdict word in the required position, without an explanation."
        for family in ("zero_shot", "few_shot"):
            for variant in VARIANTS:
                self.assertIn(instruction, render_prompt(family, variant, "int f(void) { return 0; }"))
        self.assertNotIn(instruction, render_prompt("cot", "reference", "int f(void) { return 0; }"))

    def test_placement_is_the_only_difference_in_the_format_contract(self):
        first_text = build_output_instruction("verdict_first")
        last_text = build_output_instruction("verdict_last")
        first = first_text.split("Required response layout")[0].splitlines()
        last = last_text.split("Required response layout")[0].splitlines()
        self.assertEqual(first[:-2], last[:-2])
        shared = "\n".join(first[:-2])
        self.assertIn("exactly one standalone verdict line", shared)
        self.assertIn("no prefix, punctuation, quotes, or formatting", shared)
        self.assertIn("For a direct answer, output only the verdict word", shared)
        self.assertIn("When reasoning or verification is requested", shared)
        self.assertNotIn("step by step", shared)
        self.assertIn("FIRST LINE ONLY", first[-2])
        self.assertIn("separate FINAL LINE", last[-1])
        self.assertLess(first_text.index("[verdict]"), first_text.index("[explanation"))
        self.assertGreater(last_text.index("[verdict]"), last_text.index("[explanation"))

    def test_every_matched_prompt_uses_one_format_contract(self):
        code = "int preserve(void) { return 7; }"
        for protocol in AVAILABLE_OUTPUT_PROTOCOLS:
            suffix = build_output_instruction(protocol)
            prompts = [render_prompt(family, variant, code, protocol)
                       for family in FAMILIES for variant in VARIANTS]
            prompts.extend(render_component_template(component, enabled, protocol)
                           for component in COMPONENTS for enabled in (False, True))
            for prompt in prompts:
                self.assertTrue(prompt.endswith(suffix))
                self.assertEqual(prompt.count("RESPONSE FORMAT:"), 1)

    def test_parser_still_measures_format_noncompliance(self):
        for protocol in AVAILABLE_OUTPUT_PROTOCOLS:
            valid = "SAFE\nThe access is bounded." if protocol == "verdict_first" else "The access is bounded.\nSAFE"
            prefixed = valid.replace("SAFE", "Verdict: SAFE")
            self.assertEqual(parse_verdict_details(valid, mode="strict", output_protocol=protocol)["label"], "safe")
            self.assertEqual(parse_verdict_details(prefixed, mode="strict", output_protocol=protocol)["label"], "unknown")
            self.assertEqual(parse_verdict_details(prefixed, mode="structured", output_protocol=protocol)["label"], "safe")


if __name__ == "__main__":
    unittest.main()
