
from .zero_shot import ZeroShot
from .few_shot import FewShot
from .cot import CoT
from .adaptive_cot import AdaptiveCoT
from .self_consistency import SelfConsistency

def load_prompt_strategy(name: str):
    name = name.lower()
    if name == "zero_shot": return ZeroShot()
    if name == "few_shot": return FewShot()
    if name == "cot": return CoT()
    if name == "adaptive_cot": return AdaptiveCoT()
    if name == "self_consistency": return SelfConsistency()
    raise ValueError(f"Unknown prompt strategy: {name}")
