"""Run matched template, component, and voting experiments."""

import argparse
import json
from pathlib import Path

import yaml

from core import __version__
from core.revision_study import ROOT, template_definitions, run_study
from evaluation.template_analysis import analyze_artifacts, analyze_study
from utils.privacy import safe_settings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"PromptAudit {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    templates = commands.add_parser("templates", help="Show template definitions")
    templates.add_argument("--output", type=Path, help="Save JSON to a file instead of printing it")
    run = commands.add_parser("run", help="Run a matched batch experiment")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--output", type=Path)
    run.add_argument("--pilot", action="store_true", help="Mark outputs as a smoke test")
    run.add_argument("--limit", type=int, help="Limit samples per dataset in a pilot only")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--bootstrap", type=int, default=1000)
    analyze = commands.add_parser("analyze", help="Analyze saved Standard runs or studies without inference")
    analyze.add_argument("output", type=Path, nargs="+", help="Run directories; provide repeated runs together for seed summaries")
    analyze.add_argument("--bootstrap", type=int, default=1000)
    analyze.add_argument("--group-by", choices=("cve_id", "repository"))
    analyze.add_argument("--prevalence-size", type=int)
    analyze.add_argument("--prevalence-repeats", type=int)
    analyze.add_argument("--review-case-limit", type=int)
    for flag in ("prevalence", "output-audit", "dataset-audit"):
        analyze.add_argument("--skip-" + flag, dest=flag.replace("-", "_"), action="store_false", default=None)
    audit = commands.add_parser("audit-datasets", help="Check evaluated cohorts for exact-code overlap without model calls")
    audit.add_argument("datasets", nargs="+", help="Dataset names registered in config.yaml")
    audit.add_argument("--output", type=Path, required=True, help="Write the audit as JSON")
    args = parser.parse_args(argv)
    if args.command == "templates":
        text = json.dumps(template_definitions(), indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(f"Wrote templates to {args.output}")
        else:
            print(text, end="")
        return
    if args.command == "audit-datasets":
        from code_datasets.dataset_loader import load_dataset
        from code_datasets.validation import validate_samples
        from evaluation.research_analysis import audit_dataset_cohorts
        import os
        args.output = args.output.resolve()
        if len(set(args.datasets)) != len(args.datasets):
            parser.error("Select each dataset only once")
        os.chdir(ROOT)
        def cohorts():
            for name in args.datasets:
                yield name, validate_samples(load_dataset(name), name)
        result = audit_dataset_cohorts(cohorts())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(safe_settings(result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(args.output)
        print(f"Wrote dataset audit to {args.output}")
        return
    if args.bootstrap < 0:
        parser.error("--bootstrap cannot be negative")
    if args.command == "analyze":
        options = {key: getattr(args, key) for key in ("group_by", "prevalence_size", "prevalence_repeats",
                   "review_case_limit", "prevalence", "output_audit", "dataset_audit") if getattr(args, key) is not None}
        outputs = [path.resolve() for path in args.output]
        analyze_artifacts(outputs[0] if len(outputs) == 1 else outputs, args.bootstrap, options=options)
        print(f"Updated analysis in {outputs[0]}")
        print(f"Paper tables: {outputs[0] / 'paper' / 'index.html'}")
        return
    if args.resume and args.output is None:
        parser.error("--resume requires --output")
    if args.output is not None:
        args.output = args.output.resolve()
    with args.config.open(encoding="utf-8") as stream:
        cfg = yaml.safe_load(stream)
    # Existing dataset paths are relative to the project, including when called elsewhere.
    import os
    os.chdir(ROOT)
    output = run_study(cfg, args.output, pilot=args.pilot, limit=args.limit, resume=args.resume)
    if not cfg.get("performance", {}).get("defer_analysis", False):
        analyze_study(output, args.bootstrap)
    else:
        print(f"Analysis deferred. Analyze saved predictions with: python run_revision_study.py analyze \"{output}\"")
    print(f"Study complete: {output}")


if __name__ == "__main__":
    main()
