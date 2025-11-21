# prompts/base_prompt.py — PromptAudit v2.0 (Unified Prompt Interface)
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Purpose:
#   This class defines a common interface that all prompt strategies inherit from.
#   It supports two main usages:
#
#     1) Prompt-building mode:
#           prompt_str = SomePrompt().apply(code)
#        → returns a fully formatted prompt string (no model call).
#
#     2) End-to-end inference mode:
#           result_str = SomePrompt().apply(model, code, gen_cfg)
#        → builds the prompt, sends it to the model, and returns the raw model output.
#
#   Advanced usage (for custom full prompts):
#     3) Raw prompt mode:
#           result_str = SomePrompt().apply(model, full_prompt, gen_cfg, raw_prompt=True)
#        → sends `full_prompt` directly to the model without wrapping it in
#          BasePrompt.template.
#
#   This lets simple strategies rely on the base template while giving more
#   complex strategies (CoT, SelfConsistency, AdaptiveCoT) full control when needed.


class BasePrompt:
    """Base class for all prompt strategies in Code v2.0."""

    # Logical name for the strategy (used in configs / reporting).
    name = "base"

    # Default template:
    #   - Simple binary classification
    #   - Explicitly asks for SAFE or VULNERABLE
    #   - Requests a single-word answer
    template = (
        "Analyze the following code snippet and determine whether it is secure or insecure.\n"
        "Provide your analysis if needed. Final classification instructions will follow.\n\n"
        "{code}\n\n"
    )

    def apply(self, *args, raw_prompt: bool = False, **kwargs):
        """
        Apply the prompt in one of three modes:

        1) Prompt-building only:
               apply(code)
           - args: [code]
           - Returns:
               A fully formatted prompt string with {code} filled in.
           - Use case:
               When I want to inspect or log the prompt, or manage
               model calls manually elsewhere.

        2) Model inference (template-based):
               apply(model, code, gen_cfg)
           - args: [model, code] or [model, code, gen_cfg]
           - kwargs: gen_cfg (optional, overrides positional gen_cfg)
           - Behavior:
               * Inserts `code` into `self.template`.
               * Calls model.generate(formatted_prompt).
               * Returns the raw model output string.

        3) Model inference (raw prompt mode):
               apply(model, full_prompt, gen_cfg, raw_prompt=True)
           - args: [model, full_prompt] or [model, full_prompt, gen_cfg]
           - Behavior:
               * Treats the second argument as a full prompt string.
               * Sends it directly to model.generate(), with NO extra formatting.

        This flexible signature keeps subclasses simple:
          - Basic strategies can just override `template`.
          - Advanced strategies can build their own full prompts and pass
            raw_prompt=True to avoid any wrapping.

        Raises:
            TypeError:
                If apply() is called with an unsupported argument pattern.
        """
        # ------------------------------------------------------------------
        # Case 1: apply(code)  → just build a prompt
        # ------------------------------------------------------------------
        if len(args) == 1:
            code = args[0]
            # Just return the formatted prompt; no model call in this mode.
            return self.template.format(code=code)

        # ------------------------------------------------------------------
        # Case 2 / 3: apply(model, code_or_prompt, gen_cfg, raw_prompt=...)
        # ------------------------------------------------------------------
        elif len(args) >= 2:
            # Expect at least:
            #   args[0] = model
            #   args[1] = code_or_prompt (depends on raw_prompt flag)
            model, code_or_prompt = args[:2]

            # gen_cfg is accepted for interface consistency, even though the
            # base implementation does not use it directly. Subclasses that
            # need gen_cfg can override apply() and pass it along or inspect it.
            gen_cfg = kwargs.get("gen_cfg") or (args[2] if len(args) > 2 else {})

            if raw_prompt:
                # Treat the second positional argument as a full prompt string.
                full_prompt = code_or_prompt
            else:
                # Treat the second positional argument as "code" to inject
                # into this prompt strategy's template.
                full_prompt = self.template.format(code=code_or_prompt)

            # Delegate to the model backend. This keeps BasePrompt generic:
            # any object with a .generate(prompt) method can be used here.
            return model.generate(full_prompt)

        # ------------------------------------------------------------------
        # Invalid usage
        # ------------------------------------------------------------------
        else:
            raise TypeError("Invalid call to apply(). Expected (code) or (model, code, gen_cfg).")
