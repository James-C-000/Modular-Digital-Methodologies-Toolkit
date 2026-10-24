"""Compare Translation/bpe.py with subword-nmt's reference apply_bpe.py (dev-only).

    python tests/dev/check_bpe_parity.py <path/to/apply_bpe.py> <package.argosmodel> [text-file]

Uses a BPE-based Argos package's bpe.model and the Moses tokenizer, and fails on
the first token sequence that differs.
"""
import importlib.util
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from Translation.bpe import BPE  # noqa: E402


def main(ref_path, package, text_file=None):
    spec = importlib.util.spec_from_file_location("apply_bpe_ref", ref_path)
    ref_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ref_mod)
    with zipfile.ZipFile(package) as z:
        codes = z.read(next(n for n in z.namelist() if n.endswith("bpe.model"))).decode("utf-8")
    import io
    ref = ref_mod.BPE(io.StringIO(codes))
    ours = BPE(codes)
    from sacremoses import MosesPunctNormalizer, MosesTokenizer
    tok, norm = MosesTokenizer("en"), MosesPunctNormalizer("en")
    if text_file:
        with open(text_file, encoding="utf-8") as f:
            lines = f.read().splitlines()
    else:
        lines = [
            "The parish register records the baptism of the miller's second son in 1743.",
            "Antidisestablishmentarianism aaaaaa bbb ababab the the-the Ada Lovelace's notes.",
            "Zürich, Kraków and Łódź; naïve façades — “quoted” & <escaped> text!",
        ]
    count = 0
    for line in lines:
        tokens = tok.tokenize(norm.normalize(line), return_str=True).split(" ")
        a, b = ref.segment_tokens(tokens), ours.segment_tokens(tokens)
        if a != b:
            raise SystemExit(f"MISMATCH on {line!r}\nref:  {a}\nours: {b}")
        count += len(a)
    print(f"OK: {len(lines)} lines, {count} subword tokens identical")


if __name__ == "__main__":
    main(*sys.argv[1:])
