#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dựng gold bằng 3-4 LLM triangulate — 1 lệnh. CẮM API KEY LÀ CHẠY.

  export OPENAI_API_KEY=sk-...   DEEPSEEK_API_KEY=sk-...   ANTHROPIC_API_KEY=sk-...
  python3 src/build_gold.py                 # chạy voter có key + voter rule + gộp (k=2)
  python3 src/build_gold.py --k 2 --sapbert --rule

Voter nào có key -> gọi API sinh phiếu (cache ở dev/votes/, chạy dở resume được).
Voter nào đã có sẵn file dev/votes/<name>.json (vd opus chạy rồi) -> tự dùng, khỏi key.
--rule thêm 1 voter rule-based miễn phí (từ out/baseline_all.json). Rồi triangulate.
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import gold_vote, gold_triangulate  # noqa: E402
import sections  # noqa: E402


def add_rule_voter():
    """Biến out/baseline_all.json (NER rule-based) thành 1 phiếu dev/votes/rule.json."""
    src = ROOT / "out/baseline_all.json"
    if not src.exists():
        print("[rule] chưa có out/baseline_all.json (chạy: python3 src/extract_all.py) — bỏ")
        return
    preds = json.loads(src.read_text(encoding="utf-8"))
    votes = {}
    for fid, ents in preds.items():
        raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
        rows = []
        for e in ents:
            s = e["position"][0]
            rows.append({"text": e["text"], "type": e["type"],
                         "assertion": (e["assertions"] or [""])[0],
                         "before": raw[max(0, s - 15):s]})
        votes[fid] = rows
    (ROOT / "dev/votes").mkdir(parents=True, exist_ok=True)
    (ROOT / "dev/votes/rule.json").write_text(json.dumps(votes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[rule] -> dev/votes/rule.json ({sum(len(v) for v in votes.values())} concept)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--sapbert", action="store_true")
    ap.add_argument("--rule", action="store_true", help="thêm voter rule-based miễn phí")
    args = ap.parse_args()

    gold_vote.load_env()   # nạp key từ .env
    voters = json.loads((ROOT / "dev/voters.json").read_text(encoding="utf-8"))
    print("=== Sinh phiếu ===")
    for cfg in voters:
        if os.environ.get(cfg.get("key_env", "")):
            gold_vote.run_voter(cfg["name"], cfg)
        elif (ROOT / "dev/votes" / f"{cfg['name']}.json").exists():
            print(f"[{cfg['name']}] dùng file phiếu có sẵn (không cần key)")
        else:
            print(f"[{cfg['name']}] không có key {cfg.get('key_env')} & chưa có file — bỏ qua")
    if args.rule:
        add_rule_voter()

    print("\n=== Triangulate ===")
    sys.argv = ["gold_triangulate", "--k", str(args.k)] + (["--sapbert"] if args.sapbert else [])
    gold_triangulate.main()


if __name__ == "__main__":
    main()
