"""Tests for Qwen RAG system — parameter selection, prompts, response cleaning."""
import pytest
from unittest.mock import patch, MagicMock


class TestQwenParams:
    """Test that _get_llm_params returns correct values based on thinking mode."""

    def test_instruct_mode_params(self):
        from RAG.qwen_rag import QwenRAGSystem
        params = QwenRAGSystem._get_llm_params(enable_thinking=False)
        assert params["temperature"] == 0.7
        assert params["top_p"] == 0.8
        assert params["top_k"] == 20
        assert params["repeat_penalty"] == 1.0

    def test_thinking_mode_params(self):
        from RAG.qwen_rag import QwenRAGSystem
        params = QwenRAGSystem._get_llm_params(enable_thinking=True)
        assert params["temperature"] == 1.0
        assert params["top_p"] == 0.95
        assert params["top_k"] == 20
        assert params["repeat_penalty"] == 1.0

    def test_no_f16_kv_in_params(self):
        from RAG.qwen_rag import QwenRAGSystem
        params = QwenRAGSystem._get_llm_params(enable_thinking=False)
        assert "f16_kv" not in params

    def test_no_chat_format_in_params(self):
        from RAG.qwen_rag import QwenRAGSystem
        params = QwenRAGSystem._get_llm_params(enable_thinking=False)
        assert "chat_format" not in params


class TestPromptConstruction:
    """Test prompt template builds correct ChatML format."""

    def test_instruct_prompt_has_chatml_tokens(self):
        from RAG.qwen_rag import QwenRAGSystem
        prompt = QwenRAGSystem._build_prompt(
            question="What is X?",
            context="X is a thing.",
            enable_thinking=False,
        )
        assert "<|im_start|>system" in prompt
        assert "<|im_end|>" in prompt
        assert "<|im_start|>user" in prompt
        assert "<|im_start|>assistant" in prompt
        assert "What is X?" in prompt
        assert "X is a thing." in prompt

    def test_thinking_prompt_has_think_token(self):
        from RAG.qwen_rag import QwenRAGSystem
        prompt = QwenRAGSystem._build_prompt(
            question="What is X?",
            context="X is a thing.",
            enable_thinking=True,
        )
        assert "<|im_start|>assistant\n<think>" in prompt

    def test_instruct_prompt_no_think_token(self):
        from RAG.qwen_rag import QwenRAGSystem
        prompt = QwenRAGSystem._build_prompt(
            question="What is X?",
            context="X is a thing.",
            enable_thinking=False,
        )
        assert "<think>" not in prompt


class TestResponseCleaning:
    """Test _clean_llm_response handles Qwen-specific artifacts."""

    def _make_system(self):
        """Create a QwenRAGSystem without actually initializing models."""
        from RAG.qwen_rag import QwenRAGSystem
        system = QwenRAGSystem.__new__(QwenRAGSystem)
        system.verbose = False
        system.enable_thinking = False
        return system

    def test_strips_think_blocks(self):
        system = self._make_system()
        response = "<think>Let me reason about this...</think>\n\nThe answer is 42."
        cleaned = system._clean_llm_response(response)
        assert "<think>" not in cleaned
        assert "Let me reason" not in cleaned
        assert "The answer is 42." in cleaned

    def test_strips_chatml_tags(self):
        system = self._make_system()
        response = "<|im_start|>assistant\nHello world<|im_end|>"
        cleaned = system._clean_llm_response(response)
        assert "<|im_start|>" not in cleaned
        assert "<|im_end|>" not in cleaned
        assert "Hello world" in cleaned

    def test_strips_nested_think_blocks(self):
        system = self._make_system()
        response = "<think>step 1\nstep 2\nstep 3</think>\n\nFinal answer."
        cleaned = system._clean_llm_response(response)
        assert "step 1" not in cleaned
        assert "Final answer." in cleaned

    def test_empty_response_returns_fallback(self):
        system = self._make_system()
        cleaned = system._clean_llm_response("")
        assert len(cleaned) > 10

    def test_short_response_returns_fallback(self):
        system = self._make_system()
        cleaned = system._clean_llm_response("ok")
        assert len(cleaned) > 10


class TestModelValidation:
    """Test _validate_models accepts Qwen filenames."""

    def test_qwen_filename_no_warning(self, tmp_path, caplog):
        import logging
        from RAG.qwen_rag import QwenRAGSystem

        model_file = tmp_path / "Qwen3.5-4B-Q4_K_M.gguf"
        model_file.touch()

        system = QwenRAGSystem.__new__(QwenRAGSystem)
        system.llm_model_path = str(model_file)
        system.verbose = False

        with caplog.at_level(logging.WARNING, logger="qwen-rag"):
            system._validate_models()

        assert not any("doesn't indicate a Qwen" in r.message for r in caplog.records)

    def test_non_qwen_filename_warns(self, tmp_path, caplog):
        import logging
        from RAG.qwen_rag import QwenRAGSystem

        model_file = tmp_path / "some-other-model.gguf"
        model_file.touch()

        system = QwenRAGSystem.__new__(QwenRAGSystem)
        system.llm_model_path = str(model_file)
        system.verbose = False

        with caplog.at_level(logging.WARNING, logger="qwen-rag"):
            system._validate_models()

        assert any("doesn't indicate a Qwen" in r.message for r in caplog.records)

    def test_missing_model_raises(self, tmp_path):
        from RAG.qwen_rag import QwenRAGSystem

        system = QwenRAGSystem.__new__(QwenRAGSystem)
        system.llm_model_path = str(tmp_path / "nonexistent.gguf")
        system.verbose = False

        with pytest.raises(FileNotFoundError):
            system._validate_models()
