# models/base.py — Abstract base class for all model backends in Glacier Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Every model backend (OllamaModel, HFModel, APIModel, etc.) inherits from this class.
#
# I use this BaseModel to enforce a common interface:
#   - All models must specify a name
#   - All models must accept generation settings (gen_cfg)
#   - All models must implement a `generate(prompt)` method
#
# The Experiment Runner and GUI rely on this uniform interface so they can call:
#       output = model.generate(prompt)
# without needing to know which backend is being used.


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
            I keep this class intentionally simple because the subclasses handle
            all backend-specific logic (e.g., HTTP requests, HF pipelines, Ollama).
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
