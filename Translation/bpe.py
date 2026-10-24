"""Apply learned BPE merges to tokens (subword-nmt format, as used by some Argos packages).

Equivalent to subword-nmt's ``apply_bpe.BPE.segment_tokens`` with the options
Argos uses (no vocabulary filter, no glossaries, no dropout, separator "@@").
Checked token-for-token against the reference implementation by
tests/dev/check_bpe_parity.py.
"""


class BPE:
    def __init__(self, codes_text: str, separator: str = "@@"):
        lines = codes_text.rstrip("\n").split("\n")
        self.version = (0, 1)
        if lines and lines[0].startswith("#version:"):
            self.version = tuple(int(x) for x in lines[0].split()[-1].split("."))
            lines = lines[1:]
        merges = [tuple(line.strip("\r\n ").split(" ")) for line in lines]
        for i, merge in enumerate(merges):
            if len(merge) != 2:
                raise ValueError(f"line {i + 2} of the BPE codes is not a pair: {merge!r}")
        # Earlier lines win when a pair appears twice.
        self.ranks = {pair: rank for rank, pair in reversed(list(enumerate(merges)))}
        self.separator = separator
        self._cache = {}

    def _encode_word(self, word: str) -> tuple[str, ...]:
        if word in self._cache:
            return self._cache[word]
        if self.version == (0, 1):
            symbols = list(word) + ["</w>"]
        else:
            symbols = list(word[:-1]) + [word[-1] + "</w>"]
        while len(symbols) > 1:
            pairs = [(self.ranks[pair], i, pair) for i, pair in enumerate(zip(symbols, symbols[1:]))
                     if pair in self.ranks]
            if not pairs:
                break
            best = min(pairs)[2]
            positions = [i for _rank, i, pair in pairs if pair == best]
            merged, new_symbols, i = "".join(best), [], 0
            for j in positions:
                if j < i:  # overlaps the previous merge, e.g. "aaa"
                    continue
                new_symbols.extend(symbols[i:j])
                new_symbols.append(merged)
                i = j + 2
            new_symbols.extend(symbols[i:])
            symbols = new_symbols
        if symbols[-1] == "</w>":
            symbols = symbols[:-1]
        elif symbols[-1].endswith("</w>"):
            symbols[-1] = symbols[-1][:-4]
        result = tuple(symbols)
        self._cache[word] = result
        return result

    def segment_tokens(self, tokens: list[str]) -> list[str]:
        """Split each token into subword units, marking continuations with the separator."""
        output = []
        for word in tokens:
            if not word:
                continue
            pieces = self._encode_word(word)
            output.extend(piece + self.separator for piece in pieces[:-1])
            output.append(pieces[-1])
        return output
