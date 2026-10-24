from RAG.generation import chatml_fallback, sampling_params


def test_sampling_params_follow_qwen_recommendations():
    assert sampling_params(True)["temperature"] == 1.0 and sampling_params(True)["top_p"] == 0.95
    assert sampling_params(False)["temperature"] == 0.7 and sampling_params(False)["top_p"] == 0.8


def test_fallback_template_switches_thinking_like_qwen():
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "Q"}]
    off = chatml_fallback(msgs, enable_thinking=False)
    on = chatml_fallback(msgs, enable_thinking=True)
    assert off.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n")  # empty block = no thinking
    assert on.endswith("<|im_start|>assistant\n<think>\n")
    assert "<|im_start|>system\nS<|im_end|>" in off


def test_every_argument_mdmt_passes_exists_in_the_installed_llama_cpp():
    # The JamePeng fork renamed presence_penalty to present_penalty; a mismatch
    # only shows up when a real model generates, so check the signature here.
    # Runs in tests.yml's llama-cpp job and in build.yml, which install it.
    import inspect

    import pytest
    from RAG.generation import completion_kwargs
    llama_cpp = pytest.importorskip("llama_cpp")
    accepted = set(inspect.signature(llama_cpp.Llama.create_completion).parameters)
    for thinking in (False, True):
        assert set(completion_kwargs(thinking, max_tokens=8)) <= accepted
