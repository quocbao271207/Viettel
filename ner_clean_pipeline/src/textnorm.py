"""Unicode normalisation with offset mapping back to the raw file.

Why this module exists
----------------------
20 of the 100 input files store Vietnamese diacritics in **decomposed** form
(NFD): `ỏ` is `o` + U+0309 rather than a single codepoint. Some files mix both
forms inside the same file (`100.txt` matches "tiền sản giật" at 3 offsets but
not at the first one).

Two consequences, both measured:

1. **Missed matches.** A dictionary entry typed in NFC never matches NFD text.
   Measured on the 20 NFD files with the pipeline's own word-boundary matcher:
   symptom matches go 111 -> 122 (+11) after NFC normalisation. Drugs are
   unaffected (+0) because drug names are ASCII.

2. **Offsets shift.** Normalising changes the string length (e.g. `81.txt`
   1516 -> 1441 chars). BTC scores `position` against the *raw* file, so we
   cannot simply normalise and emit offsets from the normalised string — every
   span in those 20 files would be wrong.

So: match on normalised text, then map the offsets back. `normalize()` returns
the normalised string plus an index map.

Note on false positives: NFD *also* creates spurious matches when the needle is
a prefix of a longer syllable. In `81.txt`, plain substring search for "ho"
hits inside "khỏe" (`k`,`h`,`o`,U+0309) 4 times out of 10. The pipeline's
`(?<!WORD)needle(?!WORD)` guard does not catch this, because a bare combining
mark is not in the `[\\wÀ-ỹ]` class. Normalising to NFC fixes that class of
false positive too, which is why the total match count can go *down* on some
files while real recall goes up.
"""

from __future__ import annotations

import unicodedata as ud


def normalize(raw: str) -> tuple[str, list[int]]:
    """Return (NFC text, index map).

    `imap[i]` is the offset in `raw` where normalised character `i` starts.
    Normalisation is applied per raw character, so a base+mark pair collapsing
    into one composed character maps back to the base character's offset.

    len(imap) == len(norm), and imap is non-decreasing.
    """
    out: list[str] = []
    imap: list[int] = []
    i = 0
    n = len(raw)
    while i < n:
        # take the base char plus any following combining marks as one cluster
        j = i + 1
        while j < n and ud.combining(raw[j]):
            j += 1
        composed = ud.normalize("NFC", raw[i:j])
        out.append(composed)
        imap.extend([i] * len(composed))
        i = j
    return "".join(out), imap


def to_raw_span(imap: list[int], raw_len: int, start: int, end: int) -> tuple[int, int]:
    """Map a [start, end) span on the normalised string back to raw offsets.

    `end` maps to the raw offset where the *next* normalised character starts,
    so the returned span covers the full cluster (base + its combining marks).
    """
    a = imap[start] if start < len(imap) else raw_len
    b = imap[end] if end < len(imap) else raw_len
    return a, b


def check(raw: str) -> None:
    """Assert the mapping round-trips. Used by tests, cheap enough to call."""
    norm, imap = normalize(raw)
    assert len(norm) == len(imap), (len(norm), len(imap))
    assert norm == ud.normalize("NFC", raw), "normalize() must equal NFC of whole string"
    assert all(imap[i] <= imap[i + 1] for i in range(len(imap) - 1)), "imap must be sorted"
    # every normalised span must map back to a raw span with the same NFC form
    for a in range(0, len(norm), 7):
        b = min(a + 5, len(norm))
        ra, rb = to_raw_span(imap, len(raw), a, b)
        assert ud.normalize("NFC", raw[ra:rb]) == norm[a:b], (a, b, raw[ra:rb], norm[a:b])


if __name__ == "__main__":
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    nfd = []
    for p in sorted((root / "input").glob("*.txt"), key=lambda x: int(x.stem)):
        raw = p.read_text(encoding="utf-8")
        check(raw)
        norm, _ = normalize(raw)
        if norm != raw:
            nfd.append((p.name, len(raw), len(norm)))
    print(f"round-trip ok trên 100 file. {len(nfd)} file đổi độ dài sau NFC:")
    for name, a, b in nfd:
        print(f"  {name:9s} {a} -> {b}")
