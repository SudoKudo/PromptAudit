"""Base class shared by all PromptAudit prompt strategies."""


class BasePrompt:
    """Base class for all prompt strategies in PromptAudit."""

    name = "base"
    template = (
        "Analyze the following code snippet and determine whether it is secure or insecure.\n"
        "Provide your analysis if needed. Final classification instructions will follow.\n\n"
        "{code}\n\n"
    )

    def apply(self, *args, raw_prompt: bool = False, **kwargs):
        """
        Apply the prompt in one of three modes:

        1. Prompt-building only:
               apply(code)
           Returns a fully formatted prompt string with {code} filled in.

        2. Model inference (template-based):
               apply(model, code, gen_cfg)
           Inserts code into self.template, calls model.generate(), and
           returns the raw model output string.

        3. Model inference (raw prompt mode):
               apply(model, full_prompt, gen_cfg, raw_prompt=True)
           Treats the second argument as a complete prompt and sends it to
           model.generate() without any extra formatting.

        Raises:
            TypeError: If apply() is called with an unsupported argument pattern.
        """
        # Case 1: apply(code) -> just build a prompt.
        if len(args) == 1:
            code = args[0]
            return self.template.format(code=code)

        # Case 2 / 3: apply(model, code_or_prompt, gen_cfg, raw_prompt=...).
        if len(args) >= 2:
            model, code_or_prompt = args[:2]

            if raw_prompt:
                full_prompt = code_or_prompt
            else:
                full_prompt = self.template.format(code=code_or_prompt)

            return model.generate(full_prompt)

        raise TypeError("Invalid call to apply(). Expected (code) or (model, code, gen_cfg).")
