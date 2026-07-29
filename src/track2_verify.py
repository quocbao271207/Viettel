#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Track 2 — VERIFY pipeline inference KHÔNG cần GPU.

    python3 src/track2_verify.py

Giả lập trường hợp lý tưởng: Qwen sinh ra ĐÚNG nhãn gold (đọc thẳng từ dev/track2/*.jsonl),
rồi chạy qua đúng đường ống inference thật (`to_records`: locate span + gán mã bằng bảng tra).
So kết quả với gold để đo TRẦN TRÊN của Track 2.

Ý nghĩa: nếu tỉ lệ khớp thấp thì lỗi nằm ở PIPELINE (định vị/bảng tra), phải sửa trước khi
tốn GPU train. Nếu cao thì pipeline đúng, điểm Track 2 chỉ còn phụ thuộc Qwen học lại nhãn tốt đến đâu.
"""
from __future__ import annotations
import argparse, json, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from track2_infer import to_records  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="out/submitted/14_repeat_36.4914.zip")
    ap.add_argument("--data", default="dev/track2")
    ap.add_argument("--codes", default="dev/track2/code_map.json")
    args = ap.parse_args()

    with zipfile.ZipFile(ROOT / args.gold) as z:
        gold = {Path(n).stem: json.loads(z.read(n).decode("utf-8"))
                for n in z.namelist() if n.endswith(".json")}
    code_map = json.loads((ROOT / args.codes).read_text("utf-8"))

    rows = []
    for split in ("train", "dev"):
        p = ROOT / args.data / f"{split}.jsonl"
        rows += [json.loads(l) for l in p.read_text("utf-8").splitlines() if l.strip()]

    n_gold = n_span = n_code_gold = n_code_ok = 0
    missing = []
    for row in rows:
        stem = str(row["file"])
        raw = (ROOT / "input" / f"{stem}.txt").read_text(encoding="utf-8")
        want = gold.get(stem, [])
        # nhãn vàng nằm ở lượt assistant cuối trong messages (đúng cái Qwen được dạy sinh ra)
        answer = next(m["content"] for m in reversed(row["messages"]) if m["role"] == "assistant")
        got = to_records(raw, json.loads(answer), code_map)
        got_pos = {(tuple(c["position"]), c["type"]) for c in got}
        got_by = {(tuple(c["position"]), c["type"]): c for c in got}
        for c in want:
            n_gold += 1
            k = (tuple(c["position"]), c["type"])
            if k in got_pos:
                n_span += 1
                if c["type"] in ("CHẨN_ĐOÁN", "THUỐC") and c["candidates"]:
                    n_code_gold += 1
                    if got_by[k]["candidates"] == c["candidates"]:
                        n_code_ok += 1
            else:
                missing.append((stem, c["text"], c["type"]))

    print(f"gold           : {n_gold} concept / {len(rows)} file")
    print(f"khớp span+type : {n_span}  ({n_span / n_gold:.1%})  <- trần trên của Track 2")
    print(f"khớp mã        : {n_code_ok}/{n_code_gold}  ({n_code_ok / max(n_code_gold, 1):.1%})")
    if missing:
        print(f"\n{len(missing)} concept KHÔNG định vị lại được (pipeline làm mất):")
        for stem, txt, typ in missing[:15]:
            print(f"   file {stem:>3}  {typ[:6]:8s} {txt!r}")


if __name__ == "__main__":
    main()
