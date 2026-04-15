"""Few-shot prompt strategy with built-in labeled examples."""

from .base_prompt import BasePrompt


# Few-shot labeled examples shown to the model before the new sample.
# These are synthetic CVE-style before/after function snippets rather than
# single-line API calls, so they better match the function-level patch data
# used in PromptAudit without copying exact dataset rows into the prompt.
EXAMPLES = """Examples:
Example 1 (before patch):
Code:
int parse_message(const unsigned char *buf, size_t len) {
    unsigned int msg_len;
    char header[256];

    if (len < 2) {
        return -1;
    }

    msg_len = ((unsigned int)buf[0] << 8) | buf[1];
    memcpy(header, buf + 2, msg_len);
    return 0;
}
Label: VULNERABLE

Example 2 (after patch):
Code:
int parse_message(const unsigned char *buf, size_t len) {
    unsigned int msg_len;
    char header[256];

    if (len < 2) {
        return -1;
    }

    msg_len = ((unsigned int)buf[0] << 8) | buf[1];
    if (msg_len > len - 2 || msg_len > sizeof(header)) {
        return -1;
    }

    memcpy(header, buf + 2, msg_len);
    return 0;
}
Label: SAFE
"""


class FewShot(BasePrompt):
    """
    Few-shot prompt strategy.

    Behavior:
        - Provides two labeled examples (one VULNERABLE, one SAFE).
        - Then presents the new code snippet to be audited.
        - Uses the examples to guide classification without requesting step-by-step reasoning.
        - Returns ONLY the prompt string; the runner handles generation and
          label parsing.

    The runner will:
        - Append the active SAFE/VULNERABLE output-protocol instruction.
        - Call model.generate(full_prompt).
        - Pass the raw model output into parse_verdict().
    """

    # Logical name for this strategy (used in configs and reporting).
    name = "few_shot"
    code_placeholder = "<<TARGET_CODE>>"

    # Single canonical few-shot template:
    #   - Shows EXAMPLES with labels.
    #   - Then asks the model to analyze the new code.
    #   - Output formatting is NOT constrained here; the runner adds that.
    template = (
        "Use the examples below as prior knowledge for classifying code security.\n"
        "First, review the examples and their labels. Then analyze the new code snippet.\n\n"
        "Do not use step-by-step reasoning unless the selected prompt strategy explicitly asks for it.\n"
        "If you include any explanation, keep it brief.\n\n"
        f"{EXAMPLES}\n"
        "Now analyze this code from a security perspective:\n\n"
        "<<TARGET_CODE>>\n\n"
    )

    def apply(self, model, code, gen_cfg):
        """
        Build and return the few-shot prompt string.

        Args:
            model:
                Model object (not used directly here, but kept in the signature
                for consistency with other strategies).
            code (str):
                The code snippet to classify.
            gen_cfg (dict):
                Generation configuration (temperature, stop sequences, etc.).
                Not used here because this strategy does not call
                model.generate() itself.

        Returns:
            str:
                A fully formatted prompt string containing:
                    - The labeled examples, and
                    - The target code snippet to analyze.
                The ExperimentRunner will:
                    - Append SAFE/VULNERABLE task instructions,
                    - Call model.generate(full_prompt),
                    - Feed the raw output into parse_verdict().
        """
        return self.template.replace(self.code_placeholder, code)
