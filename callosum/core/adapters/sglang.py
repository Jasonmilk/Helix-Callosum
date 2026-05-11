"""SGLang backend adapter."""

from .vllm import VLLMAdapter


class SGLangAdapter(VLLMAdapter):
    """SGLang adapter shares the same OpenAI-compatible interface as vLLM."""

    def get_adapter_name(self) -> str:
        return "sglang"
