#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Track 2 — Chuẩn bị data train Qwen ≤9B từ gold đã curate.
gold_curated.json (100 file, 2006 concept) -> instruction JSONL để LoRA fine-tune.

    python3 src/track2_prep.py            # -> dev/track2/train.jsonl + dev.jsonl

Task: generative NER. Input = văn bản; Output = JSON array concept (text,type,assertion).
KHÔNG train mã (candidates) — mã gán sau bằng gazetteer/SapBERT ở inference (rẻ, chính xác hơn).
Qwen chỉ học TRÍCH concept + phân loại type + assertion theo phong cách gold.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402

SYSTEM = ("Bạn là chuyên gia gán nhãn NER y khoa tiếng Việt. Trích MỌI khái niệm y tế trong văn bản "
          "(THUỐC / CHẨN_ĐOÁN / TRIỆU_CHỨNG), mỗi lần nhắc là một mục, kèm assertion. "
          "assertion ∈ {\"\", isNegated, isHistorical, isFamily, isUncertain, isHypothetical}. "
          "Chỉ in JSON array [{\"text\",\"type\",\"assertion\"}], text nguyên văn.")


def main():
    gold = json.loads((ROOT / "dev/gold_curated.json").read_text(encoding="utf-8"))
    out = ROOT / "dev/track2"; out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(1, 101):
        raw = sections.read_raw(ROOT / "input" / f"{i}.txt")
        concepts = [{"text": e["text"], "type": e["type"],
                     "assertion": e["assertions"][0] if e["assertions"] else ""}
                    for e in gold.get(str(i), [])]
        rows.append({"messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": raw},
            {"role": "assistant", "content": json.dumps(concepts, ensure_ascii=False)},
        ], "file": i})
    # split 85/15 (giữ đa dạng: xen kẽ)
    dev_ids = set(range(1, 101, 7))  # ~15 file làm dev
    train = [r for r in rows if r["file"] not in dev_ids]
    dev = [r for r in rows if r["file"] in dev_ids]
    (out / "train.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in train), encoding="utf-8")
    (out / "dev.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in dev), encoding="utf-8")
    nc = sum(len(json.loads(r["messages"][2]["content"])) for r in rows)
    print(f"-> dev/track2/train.jsonl ({len(train)} mẫu) + dev.jsonl ({len(dev)} mẫu) | {nc} concept")
    print("LƯU Ý: 100 file ít cho train. Augment (khi có API/GPU): LLM sinh synthetic note lâm sàng + "
          "dùng gold làm few-shot. Hoặc thêm ViMedNER/PhoNER (map nhãn về 3 type).")


if __name__ == "__main__":
    main()
