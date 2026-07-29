#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Track 2 — Xây bảng tra mã text->code từ GOLD tốt nhất (bản 13) cho inference self-host.

    python3 src/track2_codes.py                 # -> dev/track2/code_map.json

Bảng tra: chuẩn hoá text (lower/strip) -> mã phổ biến nhất trong gold, TÁCH theo type
(CHẨN_ĐOÁN -> ICD, THUỐC -> RxNorm). TRIỆU_CHỨNG / xét nghiệm KHÔNG có mã (spec).
Đây là bảng tra tĩnh (không LLM/API) => hợp lệ cho hệ thống nộp bài ≤9B.
Inference: concept nào có trong bảng thì gán mã; không có -> để RỖNG (an toàn nhất).
"""
from __future__ import annotations
import argparse, json, sys, zipfile, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

CODED = {"CHẨN_ĐOÁN", "THUỐC"}


def load_gold(path: Path) -> dict[str, list]:
    if path.is_dir():
        return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in path.glob("*.json")}
    out = {}
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.endswith(".json"):
                out[Path(n).stem] = json.loads(z.read(n).decode("utf-8"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="out/submitted/14_repeat_36.4914.zip")
    ap.add_argument("--out", default="dev/track2/code_map.json")
    a = ap.parse_args()
    gold = load_gold(ROOT / a.gold)
    votes = {t: collections.defaultdict(collections.Counter) for t in CODED}
    for concepts in gold.values():
        for e in concepts:
            if e["type"] in CODED and e.get("candidates"):
                votes[e["type"]][e["text"].strip().lower()][tuple(e["candidates"])] += 1
    code_map = {t: {k: list(c.most_common(1)[0][0]) for k, c in d.items()} for t, d in votes.items()}
    outp = ROOT / a.out
    outp.write_text(json.dumps(code_map, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {outp}")
    for t in CODED:
        print(f"  {t}: {len(code_map[t])} text->code")


if __name__ == "__main__":
    main()
