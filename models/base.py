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
