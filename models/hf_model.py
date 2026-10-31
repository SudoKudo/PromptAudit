"""Transformers backend with the checkpoint's native chat formatting."""

import hashlib

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .base import BaseModel, merge_generation_settings


class HFModel(BaseModel):
    """Run a local causal language model without silently truncating its input."""

    def __init__(self, name: str, gen_cfg: dict):
        gen_cfg = merge_generation_settings(gen_cfg)
        super().__init__(name, gen_cfg)
        self.input_format = gen_cfg.get("input_format", "auto")
        if self.input_format not in {"auto", "chat", "raw"}:
            raise ValueError("input_format must be auto, chat, or raw")
        revision = {"revision": gen_cfg["revision"]} if gen_cfg.get("revision") else {}
        print(f"[HFModel] Loading {name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(name, **revision)
        if self.input_format == "chat" and not getattr(self.tokenizer, "chat_template", None):
            raise ValueError("input_format=chat requires a tokenizer chat template")
        self.model = AutoModelForCausalLM.from_pretrained(
            name, torch_dtype=gen_cfg.get("torch_dtype", "auto"), **revision)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self.model.to(self.device)
        self.model.eval()

    def get_model_info(self):
        return {
            "backend": "hf", "name": self.name, "input_format": self.input_format,
            "revision": self.gen_cfg.get("revision"),
            "resolved_revision": getattr(self.model.config, "_commit_hash", None),
            "chat_template": getattr(self.tokenizer, "chat_template", None),
            "chat_template_kwargs": self.gen_cfg.get("chat_template_kwargs", {}),
            "model_context_window": getattr(self.model.config, "max_position_embeddings", None),
            "dtype": str(getattr(self.model, "dtype", "unknown")),
            "device": str(self.device),
            "device_name": (torch.cuda.get_device_name(self.device)
                            if torch.cuda.is_available() and hasattr(torch.cuda, "get_device_name") else None),
            "hip_version": getattr(getattr(torch, "version", None), "hip", None),
            "cuda_version": getattr(getattr(torch, "version", None), "cuda", None),
            "generation_config": (self.model.generation_config.to_dict()
                                  if hasattr(self.model.generation_config, "to_dict") else None),
        }

    def generate(self, prompt: str) -> str:
        self._set_generation_info({"backend": "hf", "status": "pending"})
        try:
            return self._generate(prompt)
        except Exception as exc:
            info = self.get_generation_info()
            info.update(status="error", error_type=type(exc).__name__, error_message=str(exc))
            self._set_generation_info(info)
            raise

    def _generate(self, prompt):
        if "seed" in self.gen_cfg:
            torch.manual_seed(int(self.gen_cfg["seed"]))

        use_chat = self.input_format == "chat" or (
            self.input_format == "auto" and bool(getattr(self.tokenizer, "chat_template", None)))
        formatted = prompt
        if use_chat:
            formatted = self.tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True,
                **self.gen_cfg.get("chat_template_kwargs", {}))
        # Chat templates already supply their own control tokens.
        inputs = self.tokenizer(formatted, return_tensors="pt", add_special_tokens=not use_chat).to(self.device)
        prompt_len = inputs["input_ids"].shape[-1]
        max_new_tokens = int(self.gen_cfg.get("max_new_tokens", 100))
        if max_new_tokens < 1:
            raise ValueError("max_new_tokens must be positive")
        limits = [self.gen_cfg.get("context_window", self.gen_cfg.get("num_ctx")),
                  getattr(self.model.config, "max_position_embeddings", None),
                  getattr(self.tokenizer, "model_max_length", None)]
        limits = [int(value) for value in limits if value is not None and 0 < int(value) < 10**9]
        context_window = min(limits) if limits else None
        stop_sequences = self.gen_cfg.get("stop_sequences", [])
        info = {
            "backend": "hf", "model": self.name, "status": "pending",
            "input_format": "chat" if use_chat else "raw",
            "formatted_prompt_sha256": hashlib.sha256(formatted.encode("utf-8")).hexdigest(),
            "prompt_eval_count": prompt_len, "context_window": context_window,
            "num_predict": max_new_tokens, "seed": self.gen_cfg.get("seed"),
            "stop_sequences": list(stop_sequences),
        }
        self._set_generation_info(info)
        if context_window is not None and prompt_len + max_new_tokens > context_window:
            raise ValueError(f"Input ({prompt_len} tokens) plus output budget ({max_new_tokens}) "
                             f"exceeds context window ({context_window}); input was not truncated")

        temperature = self.gen_cfg.get("temperature", 0.2)
        gen_args = {
            "max_new_tokens": max_new_tokens,
            "repetition_penalty": self.gen_cfg.get("repetition_penalty", 1.0),
            "num_beams": self.gen_cfg.get("num_beams", 1), "num_return_sequences": 1,
            "do_sample": temperature > 0,
            # An empty project list disables any checkpoint-specific stop strings.
            "stop_strings": stop_sequences or None,
        }
        if temperature > 0:
            gen_args.update(temperature=temperature, top_p=self.gen_cfg.get("top_p", 0.9),
                            top_k=self.gen_cfg.get("top_k", 40))
        pad_id = self.tokenizer.pad_token_id
        if pad_id is None:
            pad_id = self.tokenizer.eos_token_id
        if pad_id is not None:
            gen_args["pad_token_id"] = pad_id
        if stop_sequences:
            gen_args["tokenizer"] = self.tokenizer
        with torch.no_grad():
            outputs = self.model.generate(**inputs, **gen_args)
        generated_ids = outputs[0][prompt_len:]
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        eos = getattr(self.model.generation_config, "eos_token_id", None)
        eos = eos if isinstance(eos, (list, tuple)) else [eos]
        final_token = int(generated_ids[-1]) if len(generated_ids) else None
        ended_at_eos = final_token is not None and final_token in eos
        forced_eos = getattr(self.model.generation_config, "forced_eos_token_id", None)
        forced_eos = forced_eos if isinstance(forced_eos, (list, tuple)) else [forced_eos]
        at_limit = len(generated_ids) >= max_new_tokens
        forced_at_limit = at_limit and final_token is not None and final_token in forced_eos
        stops = [text.index(stop) for stop in stop_sequences if stop in text]
        # A stop marker can itself be a special token removed from the visible text.
        stop_text = self.tokenizer.decode(generated_ids, skip_special_tokens=False) if stop_sequences and not stops else ""
        stopped = bool(stops) or any(stop in stop_text for stop in stop_sequences)
        limit_hit = forced_at_limit or (at_limit and not ended_at_eos and not stopped)
        if stops:
            text = text[:min(stops)]
        info.update(status="ok" if text.strip() else "empty_response", eval_count=len(generated_ids),
                    done_reason="length" if limit_hit else "stop_sequence" if stopped else "stop",
                    output_limit_reached=limit_hit, forced_eos_at_output_limit=forced_at_limit)
        self._set_generation_info(info)
        return text.strip()
