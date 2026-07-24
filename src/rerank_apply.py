#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Áp mã ICD do LLM re-rank (dev/rerank_out/*.json) vào submission -> out/candidates/claude_rerank.zip

    python3 src/rerank_apply.py
Mã ICD xuất dạng CÓ CHẤM (gold cần: D55.0). RxNorm giữ nguyên số. Mã re-rank không hợp lệ -> giữ mã cũ.
"""
from __future__ import annotations
import argparse, glob, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402


def dot(code: str) -> str:
    return code[:3] + "." + code[3:] if code and code[0].isalpha() and len(code) > 3 else code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="dev/gold_resolved.json")
    ap.add_argument("--out", default="claude_rerank", help="tên zip trong out/candidates/")
    args = ap.parse_args()
    valid = set(json.loads((ROOT / "data/gaz.json").read_text(encoding="utf-8")).get("icd_code2en", {}))
    # gộp map text->code từ các batch
    rr = {}
    for f in sorted(glob.glob(str(ROOT / "dev/rerank_out/*.json"))):
        rr.update(json.loads(Path(f).read_text(encoding="utf-8")))
    good = {t: c for t, c in rr.items() if c in valid}
    print(f"re-rank: {len(rr)} cụm | mã hợp lệ {len(good)} | loại (mã lạ) {len(rr) - len(good)}")

    g = json.loads((ROOT / args.gold).read_text(encoding="utf-8"))
    out = ROOT / f"out/candidates/{args.out}/output"
    shutil.rmtree(out.parent, ignore_errors=True)
    out.mkdir(parents=True)
    changed = kept = bad = 0
    for i in range(1, 101):
        raw = sections.read_raw(ROOT / "input" / f"{i}.txt")
        clean = []
        for e in g.get(str(i), []):
            s, en = e["position"]
            if raw[s:en] != e["text"]:
                bad += 1
                continue
            cands = e["candidates"]
            if e["type"] != "THUỐC":
                if e["text"] in good:
                    cands = [dot(good[e["text"]])]
                    changed += 1
                else:  # không re-rank được -> giữ mã cũ nhưng thêm chấm
                    cands = [dot(c) for c in cands]
            clean.append({"text": e["text"], "type": e["type"], "candidates": cands,
                          "assertions": e["assertions"], "position": e["position"]})
        (out / f"{i}.json").write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.make_archive(str(ROOT / f"out/candidates/{args.out}"), "zip", root_dir=out.parent, base_dir="output")
    print(f"-> out/candidates/{args.out}.zip | concept phi-thuốc gán mã re-rank: {changed} | offset lệch {bad}")


if __name__ == "__main__":
    main()
