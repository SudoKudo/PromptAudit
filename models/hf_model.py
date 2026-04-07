"""Transformers backend for local Hugging Face model inference."""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .base import BaseModel


class HFModel(BaseModel):
    """Hugging Face Transformers backend for local GPU/CPU inference."""

    def __init__(self, name: str, gen_cfg: dict):
        """
        Load tokenizer + model weights from Hugging Face.

        Args:
            name (str):
                Model identifier from Hugging Face Hub, for example:
                - "mistral-7b-instruct"
                - "codellama/CodeLlama-7b-Instruct"
                - "google/gemma-2b"

            gen_cfg (dict):
                Dictionary of generation settings (temperature, top_p, etc.).

        Behavior:
            - Automatically detects GPU (cuda) vs CPU.
            - Moves the model to the selected device.
            - Sets eval() mode for deterministic generation.
        """
        super().__init__(name, gen_cfg)

        print(f"[HFModel] Loading {name}...")

        self.tokenizer = AutoTokenizer.from_pretrained(name)
        self.model = AutoModelForCausalLM.from_pretrained(name)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self.model.to(self.device)  # type: ignore
        self.model.eval()

    def generate(self, prompt: str) -> str:
        """
        Run a text generation forward pass using the local HF model.

        Args:
            prompt (str): Input text to feed the model.

        Returns:
            str: Generated output string (processed and optionally truncated).

        Details:
            - Optional reproducibility via manual seed.
            - Proper sampling settings (temperature, top-p, etc.).
            - Optional stop sequence truncation (same behavior as API/Ollama backends).
        """

        if "seed" in self.gen_cfg:
            torch.manual_seed(int(self.gen_cfg["seed"]))

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        gen_args = {
            "temperature": self.gen_cfg.get("temperature", 0.2),
            "top_p": self.gen_cfg.get("top_p", 0.9),
            "top_k": self.gen_cfg.get("top_k", 40),
            "max_new_tokens": self.gen_cfg.get("max_new_tokens", 100),
            "repetition_penalty": self.gen_cfg.get("repetition_penalty", 1.0),
            "num_beams": self.gen_cfg.get("num_beams", 1),
            # If temperature > 0, use sampling mode; if 0, use greedy decoding.
            "do_sample": self.gen_cfg.get("temperature", 0.2) > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
        }

        with torch.no_grad():
            outputs = self.model.generate(**inputs, **gen_args)

        prompt_len = inputs["input_ids"].shape[-1]
        generated_ids = outputs[0][prompt_len:]
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        stop_list = self.gen_cfg.get("stop_sequences", [])
        for stop in stop_list:
            if stop in text:
                text = text.split(stop)[0] + stop
                break

        return text.strip()
