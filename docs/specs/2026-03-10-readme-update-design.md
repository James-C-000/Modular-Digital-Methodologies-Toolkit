# README Update Design

## Summary

Update README.md to reflect the current state of the project. Fix factual errors, add missing features, and include the MDMT logo.

## Changes

1. **Add MDMT logo** — `MDMT_logo.png` at the top
2. **Fix module names** — "RAG Chat" → "RAGBot", sidebar uses "Keyword Search" not "Advanced Keyword Search"
3. **Update Building section** — replace generic `mdmt.spec` with platform-specific specs (`mdmt-linux.spec`, `mdmt-macos.spec`, `mdmt-windows.spec`)
4. **Add CI/CD mention** — GitHub Actions cross-platform builds, automatic releases on version tags
5. **Add hardware detection note** — auto-detects GPU (NVIDIA, AMD, Apple Metal) and recommends Qwen model size
6. **Mention dark mode** — toggle in sidebar
7. **Update Dependencies section** — add `googletrans`, `sentence-transformers`, `llama-cpp-python`; these are significant runtime deps currently missing from the list
8. **Update Contact section** — add GitHub repo link (https://github.com/James-C-000/Modular-Digital-Methodologies-Toolkit)
9. **Update License section** — reference the license attribution table in the About page

## Constraints

- Same sections in the same order — no structural changes
- Single file edit: `README.md`
