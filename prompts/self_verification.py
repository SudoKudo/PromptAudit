"""Self-verification prompt strategy with an explicit model self-check step."""

from .base_prompt import BasePrompt


class SelfVerification(BasePrompt):
    """Prompt strategy that adds an explicit self-check phase before the verdict."""

    name = "self_verification"

    template = (
        "You are a security analyst auditing source code for vulnerabilities.\n\n"
        "Analyze the code carefully.\n"
        "Then verify your own reasoning before giving a final verdict:\n"
        "1) Check whether you relied on any assumptions that are not supported by the code.\n"
        "2) Check whether you missed any unsafe memory handling, input validation, trust-boundary, or injection risk.\n"
        "3) Check whether your conclusion is consistent with your reasoning.\n"
        "4) If you find a mistake, revise your answer.\n\n"
        "When you respond, make sure the final classification reflects your verified conclusion.\n\n"
        "Code:\n{code}\n\n"
        "Verification notes:\n"
    )

    def apply(self, model, code, gen_cfg):
        """Build and return the self-verification prompt string."""
        return self.template.format(code=code)
