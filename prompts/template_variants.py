"""Reference prompt variants and matched component controls."""

import hashlib

from .adaptive_cot import ADAPTIVE_REASONING_INSTRUCTION, COMPLEXITY_GUIDANCE, AdaptiveCoT
from .base_prompt import ROLE_INSTRUCTION, TASK_INSTRUCTION, code_block
from .cot import COT_REASONING_INSTRUCTION, CoT
from .few_shot import EXAMPLES, FewShot
from .zero_shot import ZeroShot
from evaluation.output_protocol import AVAILABLE_OUTPUT_PROTOCOLS, build_output_instruction


TEMPLATE_VERSION = "10"
VARIANTS = ("reference", "paraphrase", "reworded", "task_first")
FAMILIES = ("zero_shot", "few_shot", "cot", "adaptive_cot", "self_consistency")
CODE_SLOT = "<<PROMPTAUDIT_TARGET_CODE_7F82>>"
COMPONENTS = ("examples", "reasoning", "adaptive")
_COMPONENT_TASK = f"{ROLE_INSTRUCTION}\n{TASK_INSTRUCTION}\n\n"
_COMPONENT_FACTORS = (
    "Assess these factors:\n"
    "1) Inputs and trust boundaries\n"
    "2) Validation and sanitization\n"
    "3) Memory safety and resource management\n"
    "4) Injection, race, and logic risks\n\n"
    + COMPLEXITY_GUIDANCE + "\n"
)
_COMPONENT_BLOCKS = {
    "examples": EXAMPLES + "\n",
    "reasoning": COT_REASONING_INSTRUCTION + "\n",
    "adaptive": ADAPTIVE_REASONING_INSTRUCTION + "\n",
}

_BUILDERS = {
    "zero_shot": ZeroShot,
    "few_shot": FewShot,
    "cot": CoT,
    "adaptive_cot": AdaptiveCoT,
}
_TASK_WORDINGS = {
    "reference": TASK_INSTRUCTION,
    "paraphrase": "Review the code below and decide whether it is SAFE or VULNERABLE.",
    "reworded": "Assess the code below and classify it as SAFE or VULNERABLE.",
    "task_first": "Determine whether the following code is SAFE or VULNERABLE by assessing its security.",
}


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def base_family(family):
    return "adaptive_cot" if family == "self_consistency" else family


def render_template(family, variant="reference", output_protocol="verdict_first"):
    """Render the prompt with a code placeholder, before inserting any user code."""
    if family not in FAMILIES or variant not in VARIANTS:
        raise ValueError(f"Unknown prompt template: {family}/{variant}")
    if output_protocol not in AVAILABLE_OUTPUT_PROTOCOLS:
        raise ValueError(f"Unknown output protocol: {output_protocol}")
    family = base_family(family)
    builder = _BUILDERS[family]()
    if hasattr(builder, "apply_with_context"):
        body = builder.apply_with_context(None, CODE_SLOT, {}, output_protocol=output_protocol)
    else:
        body = builder.apply(None, CODE_SLOT, {})

    # Replace only the task sentence, before inserting the target code.
    if variant != "reference":
        if body.count(TASK_INSTRUCTION) != 1:
            raise ValueError(f"The shared task instruction for {family} has changed")
        body = body.replace(TASK_INSTRUCTION, _TASK_WORDINGS[variant], 1)
    if body.count(CODE_SLOT) != 1:
        raise ValueError("Each template must contain one target-code placeholder")
    return body.rstrip() + build_output_instruction(output_protocol)


def render_prompt(family, variant, code, output_protocol="verdict_first"):
    return render_template(family, variant, output_protocol).replace(CODE_SLOT, code)


def render_component_template(component, enabled, output_protocol="verdict_first"):
    """Add or remove one block while keeping the rest of the prompt fixed."""
    if component not in COMPONENTS:
        raise ValueError(f"Unknown prompt component: {component}")
    if output_protocol not in AVAILABLE_OUTPUT_PROTOCOLS:
        raise ValueError(f"Unknown output protocol: {output_protocol}")
    block = _COMPONENT_BLOCKS[component] if enabled else ""
    body = _COMPONENT_TASK + _COMPONENT_FACTORS + block + f"Code:\n{code_block(CODE_SLOT)}\n"
    return body.rstrip() + build_output_instruction(output_protocol)


def template_manifest():
    """Describe rendered templates and hashes for experiment records."""
    entries = []
    for family in _BUILDERS:
        for variant in VARIANTS:
            prompts = {p: render_template(family, variant, p) for p in AVAILABLE_OUTPUT_PROTOCOLS}
            definition = "\n".join(prompts.values())
            entries.append({
                "id": f"{family}/{variant}",
                "family": family,
                "variant": variant,
                "version": TEMPLATE_VERSION,
                "sha256": text_hash(definition),
                "characters": {p: len(t) for p, t in prompts.items()},
                "prompts": prompts,
            })
    return {"version": TEMPLATE_VERSION, "role_instruction": ROLE_INSTRUCTION,
            "task_wordings": dict(_TASK_WORDINGS), "self_consistency_base": "adaptive_cot",
            "default_variants": list(VARIANTS),
            "templates": entries}
