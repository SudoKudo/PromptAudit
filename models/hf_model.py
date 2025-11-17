# models/hf_model.py — HuggingFace Transformers backend for Glacier Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# This backend allows Code v2.0 to run LLMs directly through the HuggingFace
# Transformers library (AutoModelForCausalLM + AutoTokenizer).
#
# I use this class when:
#   - Running local GPU models
#   - Evaluating open-source LLMs (Mistral, CodeLlama, Gemma, etc.)
#   - Performing offline experiments without API calls
#
# The interface matches BaseModel, so the GUI and experiment runner can treat
# HF models exactly like Ollama models or API models.


import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from .base import BaseModel


class HFModel(BaseModel):
    """Hugging Face Transformers backend for local GPU/CPU inference."""

    def __init__(self, name: str, gen_cfg: dict):
        """
        Load tokenizer + model weights from HuggingFace.

        Args:
            name (str):
                Model identifier from HuggingFace Hub, e.g.:
                - "mistral-7b-instruct"
                - "codellama/CodeLlama-7b-Instruct"
                - "google/gemma-2b"

            gen_cfg (dict):
                Dictionary of generation settings (temperature, top_p, etc.)

        Behavior:
            - Automatically detects GPU (cuda) vs CPU.
            - Moves the model to the selected device.
            - Sets eval() mode for deterministic generation.
        """
        super().__init__(name, gen_cfg)

        print(f"[HFModel] Loading {name}...")

        # Load pretrained tokenizer + causal LM
        self.tokenizer = AutoTokenizer.from_pretrained(name)
        self.model = AutoModelForCausalLM.from_pretrained(name)

        # Pick GPU if available, else CPU.
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Move weights to appropriate device.
        # I ignore Pylance complaints because HF models use dynamic typing.
        self.model = self.model.to(self.device)  # type: ignore

        # eval() disables dropout + training-only layers.
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

        # ---------------------------------------------------------------
        # Optional: set RNG seed for reproducible outputs
        # ---------------------------------------------------------------
        if "seed" in self.gen_cfg:
            torch.manual_seed(int(self.gen_cfg["seed"]))

        # Tokenize the input prompt and move tensors to the target device.
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        # Generation settings (mirrors HF's .generate kwargs)
        gen_args = {
            "temperature": self.gen_cfg.get("temperature", 0.2),
            "top_p": self.gen_cfg.get("top_p", 0.9),
            "top_k": self.gen_cfg.get("top_k", 40),
            "max_new_tokens": self.gen_cfg.get("max_new_tokens", 100),
            "repetition_penalty": self.gen_cfg.get("repetition_penalty", 1.0),
            "num_beams": self.gen_cfg.get("num_beams", 1),
            # If temperature > 0 → sampling mode; if 0 → greedy decoding.
            "do_sample": self.gen_cfg.get("temperature", 0.2) > 0,
            # Ensures padding doesn't break decode.
            "pad_token_id": self.tokenizer.eos_token_id,
        }

        # ---------------------------------------------------------------
        # Generate output (disable gradient computations for speed)
        # ---------------------------------------------------------------
        with torch.no_grad():
            outputs = self.model.generate(**inputs, **gen_args)

        # Decode token IDs → human-readable text.
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # ---------------------------------------------------------------
        # Optional manual stop-sequence truncation
        # ---------------------------------------------------------------
        # This ensures consistent behavior with API/Ollama backends.
        stop_list = self.gen_cfg.get("stop_sequences", [])
        for stop in stop_list:
            if stop in text:
                # Keep only everything before the stop token (plus the stop itself)
                text = text.split(stop)[0] + stop
                break

        return text.strip()
