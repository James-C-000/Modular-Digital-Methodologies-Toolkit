from RAG.generation import chatml_fallback, completion_kwargs, model_kwargs, short_completion_kwargs


def test_sampling_params_follow_qwen_recommendations():
    thinking, instruct = completion_kwargs(True, max_tokens=8), completion_kwargs(False, max_tokens=8)
    assert thinking["temperature"] == 1.0 and thinking["top_p"] == 0.95
    assert instruct["temperature"] == 0.7 and instruct["top_p"] == 0.8


def test_fallback_template_switches_thinking_like_qwen():
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "Q"}]
    off = chatml_fallback(msgs, enable_thinking=False)
    on = chatml_fallback(msgs, enable_thinking=True)
    assert off.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n")  # empty block = no thinking
    assert on.endswith("<|im_start|>assistant\n<think>\n")
    assert "<|im_start|>system\nS<|im_end|>" in off


def test_every_argument_mdmt_passes_exists_in_the_installed_llama_cpp():
    # The JamePeng fork renamed presence_penalty to present_penalty; a mismatch
    # only shows up when a real model generates, so check the signatures here.
    # Runs in tests.yml's llama-cpp job and in build.yml, which install it.
    import inspect

    import pytest
    llama_cpp = pytest.importorskip("llama_cpp")

    def named_parameters(func):
        # Llama.__init__ also takes **kwargs, which would silently swallow a
        # misspelled argument, so only explicitly named parameters count.
        return {name for name, p in inspect.signature(func).parameters.items()
                if p.kind is not p.VAR_KEYWORD}

    constructor = named_parameters(llama_cpp.Llama.__init__)
    completion = named_parameters(llama_cpp.Llama.create_completion)
    assert set(model_kwargs("m.gguf", 8192, None, 0, False)) <= constructor
    for thinking in (False, True):
        assert set(completion_kwargs(thinking, max_tokens=8)) <= completion
    assert set(short_completion_kwargs(max_tokens=8)) <= completion
