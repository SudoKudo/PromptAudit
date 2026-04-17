"""Common interface implemented by all PromptAudit model backends."""

class BaseModel:
    def __init__(self, name, gen_cfg):
        """
        Initialize a model backend.

        Args:
            name (str):
                A unique name for the model, such as:
                - "gemma:7b-instruct"
                - "codellama:7b"
                - "gpt-4o-mini"
                - "custom-api-model"

            gen_cfg (dict):
                A dictionary containing generation parameters such as:
                    - temperature
                    - top_p
                    - max_new_tokens
                    - stop_sequences
                    - api_host / api_key (for API models)
                    - etc.

        Notes:
            Subclasses own the backend-specific behavior such as HTTP requests,
            tokenizer and model setup, and runtime-specific generation details.
        """
        self.name = name
        self.gen_cfg = gen_cfg
        self._last_generation_info = {}

    def _set_generation_info(self, info):
        """Record backend-specific metadata for the most recent generation call."""
        self._last_generation_info = dict(info or {})

    def get_generation_info(self):
        """Return a copy of the most recent generation metadata without clearing it."""
        return dict(self._last_generation_info or {})

    def consume_generation_info(self):
        """Return and clear the most recent generation metadata."""
        info = self.get_generation_info()
        self._last_generation_info = {}
        return info

    def generate(self, prompt):
        """
        Abstract method: all subclasses MUST implement this.

        Args:
            prompt (str):
                The input prompt the model should generate a response for.

        Returns:
            str: The generated output text.

        Raises:
            NotImplementedError:
                This is raised if a subclass does not implement `generate()`.
        """
        raise NotImplementedError("Subclasses must implement `generate()`")
