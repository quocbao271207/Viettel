#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Track 2 — Chuẩn bị data train Qwen ≤9B từ GOLD MỚI NHẤT (bản 13, 5 type, spec §8a).

    python3 src/track2_prep.py                                   # nền bản tốt nhất
    python3 src/track2_prep.py --gold out/submitted/14_repeat_36.4914.zip

Task: generative NER. Input = văn bản; Output = JSON array {text,type,assertions,before}.
- 5 TYPE: THUỐC / CHẨN_ĐOÁN / TRIỆU_CHỨNG / TÊN_XÉT_NGHIỆM / KẾT_QUẢ_XÉT_NGHIỆM.
- assertions = LIST con của {isNegated, isHistorical, isFamily} (spec §8a, KHÔNG isUncertain/isHypothetical).
- "before" = 15 ký tự ngay trước span (suy từ position) -> inference dùng locate() map lại vị trí.
KHÔNG train mã (candidates) — gán sau bằng gazetteer/SapBERT ở inference (rẻ, chính xác hơn).
"""
from __future__ import annotations
import argparse, json, sys, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402

SYSTEM = (
    "Bạn là chuyên gia gán nhãn NER y khoa tiếng Việt (spec chính thức cuộc thi). "
    "Trích MỌI lần nhắc khái niệm y tế, gồm 5 loại: THUỐC (tên thuốc/hoạt chất kèm liều), "
    "CHẨN_ĐOÁN (tên bệnh), TRIỆU_CHỨNG (triệu chứng/dấu hiệu), TÊN_XÉT_NGHIỆM (WBC, creatinin, "
    "siêu âm...), KẾT_QUẢ_XÉT_NGHIỆM (giá trị + đơn vị: 14,43; 316 mg/dl...). "
    "QUY TẮC: (1) text nguyên văn, trích MỖI LẦN NHẮC riêng. (2) before = tối đa 15 ký tự ngay trước "
    "span. (3) assertions = LIST 0-3 nhãn CHỈ trong {isNegated, isHistorical, isFamily}; đang có/khẳng "
    "định = []; nhiều nhãn được (vd bố có tiền sử hen = [isFamily,isHistorical]). (4) KHÔNG xuất mã. "
    "Chỉ in JSON array [{\"text\",\"type\",\"assertions\",\"before\"}]."
)


def load_gold(path: Path) -> dict[str, list]:
    if path.is_dir():
        return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in path.glob("*.json")}
    out = {}
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".json"):
                out[Path(name).stem] = json.loads(z.read(name).decode("utf-8"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="out/submitted/14_repeat_36.4914.zip")
    a = ap.parse_args()

    gold = load_gold(ROOT / a.gold)
    out = ROOT / "dev/track2"; out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(1, 101):
        raw = sections.read_raw(ROOT / "input" / f"{i}.txt")
        concepts = sorted(gold.get(str(i), []), key=lambda e: tuple(e.get("position", [0, 0])))
        target = []
        for e in concepts:
            s = e.get("position", [0, 0])[0]
            target.append({
                "text": e["text"],
                "type": e["type"],
                "assertions": e.get("assertions", []),
                "before": raw[max(0, s - 15):s],
            })
        rows.append({"messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": raw},
            {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)},
        ], "file": i})

    dev_ids = set(range(1, 101, 7))  # ~15 file làm dev (xen kẽ giữ đa dạng)
    train = [r for r in rows if r["file"] not in dev_ids]
    dev = [r for r in rows if r["file"] in dev_ids]
    (out / "train.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in train), encoding="utf-8")
    (out / "dev.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in dev), encoding="utf-8")
    nc = sum(len(json.loads(r["messages"][2]["content"])) for r in rows)
    print(f"-> dev/track2/train.jsonl ({len(train)} mẫu) + dev.jsonl ({len(dev)} mẫu) | {nc} concept / 5 type")
    print("Augment (khi có GPU/API): synthetic note lâm sàng + ViMedNER/PhoNER (map 5 type). Train: colab/track2_train_qwen.py")


if __name__ == "__main__":
    main()
