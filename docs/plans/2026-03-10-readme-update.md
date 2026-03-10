# README Update Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update README.md to match the current state of the project.

**Architecture:** Single file rewrite of `README.md` preserving the existing section structure.

**Tech Stack:** Markdown

**Spec:** `docs/specs/2026-03-10-readme-update-design.md`

---

## Chunk 1: Implementation

### Task 1: Rewrite README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README.md content**

Rewrite `README.md` with these changes (preserving section order):

1. Add logo image at top: `<p align="center"><img src="MDMT_logo.png" alt="MDMT Logo" width="200"></p>`
2. In Features > AI Integration: mention hardware auto-detection and model size recommendations, rename to "RAGBot"
3. In Usage section: fix module names to match actual sidebar ("Keyword Search", "Named Entities", "Relationships", "Co-Words", "RAGBot"), add dark mode mention
4. In Dependencies: add `googletrans`, `sentence-transformers`, `llama-cpp-python`
5. In Building: replace `pyinstaller mdmt.spec` with platform-specific commands, add CI/CD note
6. In License: reference the About page license attribution table
7. In Contact: add GitHub repo link

- [ ] **Step 2: Verify markdown renders correctly**

Run: `cat README.md` and visually check the structure is sound.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README to reflect current project state"
```
