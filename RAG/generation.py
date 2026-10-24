"""Text generation with llama.cpp (llama-cpp-python).

Prompts are rendered with the model's own chat template from the GGUF file
(Jinja2, sandboxed), which handles Qwen 3.5's thinking switch correctly: with
thinking off it pre-fills an empty <think></think> block, as Qwen documents.
A hand-written ChatML template is the fallback for GGUFs without a template.
(The previous hand-built prompt omitted the empty block, so "thinking off"
still let the model think: verified on Qwen3.5-0.8B.)
"""
import threading

# Qwen 3.5 recommended sampling (thinking / non-thinking modes).
THINKING_PARAMS = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "repeat_penalty": 1.0}
INSTRUCT_PARAMS = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "repeat_penalty": 1.0}
PRESENCE_PENALTY = 1.5
STOP = ["<|im_end|>", "<|im_start|>", "<|endoftext|>"]


def sampling_params(enable_thinking: bool) -> dict:
    return dict(THINKING_PARAMS if enable_thinking else INSTRUCT_PARAMS)


def completion_kwargs(enable_thinking: bool, max_tokens: int) -> dict:
    """Keyword arguments for Llama.create_completion when generating an answer."""
    return dict(sampling_params(enable_thinking), max_tokens=max_tokens, stop=STOP,
                presence_penalty=PRESENCE_PENALTY)


def chatml_fallback(messages, enable_thinking: bool) -> str:
    parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages]
    parts.append("<|im_start|>assistant\n" + ("<think>\n" if enable_thinking else "<think>\n\n</think>\n\n"))
    return "".join(parts)


class LlmEngine:
    def __init__(self, model_path: str, n_ctx: int = 8192, n_threads: int | None = None,
                 n_gpu_layers: int = 0, verbose: bool = False):
        from llama_cpp import Llama
        self.llm = Llama(model_path=model_path, n_ctx=n_ctx, n_batch=512, n_threads=n_threads,
                         n_gpu_layers=n_gpu_layers, verbose=verbose)
        self.n_ctx = n_ctx
        self._template = None
        source = self.llm.metadata.get("tokenizer.chat_template")
        if source:
            from jinja2.sandbox import ImmutableSandboxedEnvironment
            env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
            env.globals["raise_exception"] = _raise_template_error
            self._template = env.from_string(source)
        self.lock = threading.Lock()   # one generation at a time per model/context

    def render(self, messages, enable_thinking: bool) -> str:
        if self._template is None:
            return chatml_fallback(messages, enable_thinking)
        return self._template.render(messages=messages, add_generation_prompt=True,
                                     enable_thinking=enable_thinking, bos_token="", eos_token="<|im_end|>")

    def count_tokens(self, text: str) -> int:
        return len(self.llm.tokenize(text.encode("utf-8"), add_bos=False, special=True))

    def stream(self, prompt: str, enable_thinking: bool, max_tokens: int, stop_event=None):
        """Yield generated text pieces; stops early when *stop_event* is set.

        Afterwards ``last_finish_reason`` is "length" if generation ran out of
        tokens (max_tokens or the context window), "stop" if the model finished.
        """
        self.last_finish_reason = None
        with self.lock:
            for chunk in self.llm.create_completion(prompt, stream=True,
                                                    **completion_kwargs(enable_thinking, max_tokens)):
                if stop_event is not None and stop_event.is_set():
                    break
                choice = chunk["choices"][0]
                if choice.get("finish_reason"):
                    self.last_finish_reason = choice["finish_reason"]
                if choice["text"]:
                    yield choice["text"]

    def complete(self, prompt: str, max_tokens: int = 128) -> str:
        """Short deterministic completion (used for query rewriting)."""
        with self.lock:
            out = self.llm.create_completion(prompt, max_tokens=max_tokens, temperature=0.0, stop=STOP)
        return out["choices"][0]["text"]

    def close(self):
        llm, self.llm = self.llm, None
        if llm is not None:
            llm.close()


def _raise_template_error(message):
    raise ValueError(f"chat template error: {message}")
