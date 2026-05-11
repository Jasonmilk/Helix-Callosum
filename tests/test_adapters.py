"""Tests for Backend Adapters."""

import pytest
from callosum.core.adapters import load_adapters
from callosum.common.config import get_settings


def test_adapter_loader():
    """Test adapter loader loads all adapters."""
    settings = get_settings()
    adapters = load_adapters(settings.adapters_config_path)
    
    # Should load all enabled adapters
    assert "anthropic" in adapters
    assert "openai" in adapters
    assert "vllm" in adapters
    assert "sglang" in adapters


def test_anthropic_adapter(settings):
    """Test Anthropic adapter."""
    from callosum.core.adapters.anthropic import AnthropicAdapter
    adapter = AnthropicAdapter(settings)
    
    assert adapter.get_adapter_name() == "anthropic"
    assert adapter.base_url == "https://api.anthropic.com/v1"


def test_openai_adapter(settings):
    """Test OpenAI adapter."""
    from callosum.core.adapters.openai import OpenAIAdapter
    adapter = OpenAIAdapter(settings)
    
    assert adapter.get_adapter_name() == "openai"
    assert adapter.base_url == "https://api.openai.com/v1"


def test_vllm_adapter(settings):
    """Test vLLM adapter."""
    from callosum.core.adapters.vllm import VLLMAdapter
    adapter = VLLMAdapter(settings)
    
    assert adapter.get_adapter_name() == "vllm"
    assert adapter.base_url == settings.vllm_base_url.rstrip("/")


def test_sglang_adapter(settings):
    """Test SGLang adapter."""
    from callosum.core.adapters.sglang import SGLangAdapter
    adapter = SGLangAdapter(settings)
    
    assert adapter.get_adapter_name() == "sglang"