"""Few-shot prompt strategy with built-in labeled examples."""

from .base_prompt import ROLE_INSTRUCTION, TASK_INSTRUCTION, BasePrompt, code_block


# Fixed synthetic before/after examples, separate from the evaluation datasets.
EXAMPLES = """Examples:
For these two examples only, assume buf points to len readable bytes.
Assess the buffer accesses shown under that assumption.

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
    """Show two labeled examples before asking for a direct classification."""

    name = "few_shot"
    code_placeholder = "<<TARGET_CODE>>"

    # The runner appends the selected verdict-placement instruction.
    template = (
        f"{ROLE_INSTRUCTION}\n{TASK_INSTRUCTION}\n\n"
        "Use the examples below as prior knowledge for classifying code security.\n"
        "First, review the examples and their labels. Then analyze the new code snippet.\n\n"
        "Give a direct classification without a step-by-step explanation.\n"
        "Return only the verdict word in the required position, without an explanation.\n\n"
        f"{EXAMPLES}\n"
        "Now analyze this code from a security perspective:\n\n"
        "<<TARGET_CODE>>\n\n"
    )

    def apply(self, model, code, gen_cfg):
        """Insert the target code after the fixed examples."""
        return self.template.replace(self.code_placeholder, code_block(code))
