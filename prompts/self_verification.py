"""Self-verification prompt strategy with an explicit model self-check step."""

from .base_prompt import BasePrompt
from evaluation.output_protocol import normalize_output_protocol


class SelfVerification(BasePrompt):
    """Prompt strategy that adds an explicit self-check phase before the verdict."""

    name = "self_verification"

    def apply(self, model, code, gen_cfg):
        """Build and return the self-verification prompt string."""
        return self.apply_with_context(model, code, gen_cfg)

    def apply_with_context(
        self,
        model,
        code,
        gen_cfg,
        *,
        output_protocol="verdict_first",
        parser_mode="full",
    ):
        """Build a self-verification prompt that respects the selected verdict-placement protocol."""
        del model, gen_cfg, parser_mode

        protocol = normalize_output_protocol(output_protocol)
        placement_hint = (
            "Complete your analysis and self-check before answering. Then put the required verdict on the first line and summarize the checked reasoning on later lines."
            if protocol == "verdict_first"
            else "Do your analysis and verification before the final verdict line."
        )

        prompt = (
            "You are a security analyst auditing source code for vulnerabilities.\n\n"
            "Analyze the code carefully, then verify your own reasoning before committing to the final label:\n"
            "1) Check whether you relied on assumptions that are not supported by the code.\n"
            "2) Check whether you missed unsafe memory handling, input validation, trust-boundary, or injection risks.\n"
            "3) Check whether your conclusion is consistent with your reasoning.\n"
            "4) If you find a mistake, revise your answer.\n\n"
            f"{placement_hint}\n\n"
            f"Code:\n{code}\n"
        )
        return prompt
