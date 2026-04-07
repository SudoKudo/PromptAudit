"""Zero-shot prompt strategy for direct vulnerability classification."""

from .base_prompt import BasePrompt


class ZeroShot(BasePrompt):
    """Zero-shot classification prompt strategy."""

    # Logical name used in configs and reports.
    name = "zero_shot"

    # Single zero-shot template:
    #   - Assigns the model a security auditing role.
    #   - Asks it to examine the code and consider security implications.
    #   - Does not specify the exact SAFE/VULNERABLE output format; the runner
    #     appends the active verdict-placement protocol.
    template = (
        "You are a secure code auditor. Examine the following code and determine "
        "whether it is secure or vulnerable to potential exploits.\n"
        "Do not use step-by-step reasoning unless the selected prompt strategy explicitly asks for it.\n"
        "If you include any explanation, keep it brief.\n"
        "Briefly consider issues such as buffer overflows, injections, improper "
        "validation, and other common weaknesses.\n\n"
        "{code}\n\n"
    )

    def apply(self, model, code, gen_cfg):
        """
        Build and return the zero-shot prompt string.

        Args:
            model:
                Backend model instance (not used directly here, but kept in the
                signature for interface consistency with other strategies).
            code (str):
                The code snippet to be analyzed.
            gen_cfg (dict):
                Generation configuration (temperature, etc.). Not used here,
                since this strategy does not call model.generate() itself.

        Returns:
            str:
                A fully formatted prompt string. The ExperimentRunner will:
                    - Append the active SAFE/VULNERABLE output-protocol instructions.
                    - Call model.generate(full_prompt).
                    - Feed the raw output to parse_verdict().
        """
        return self.template.format(code=code)
