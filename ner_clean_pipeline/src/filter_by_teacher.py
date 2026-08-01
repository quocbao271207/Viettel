"""Lọc output model theo teacher exact span/type.

Khác `copy_teacher_fields.py`, script này có thể BỎ các entity model dự đoán mà không có
trong teacher. Nó không thêm entity mới. Mục đích là probe xem false-positive đang làm WER
tụt bao nhiêu.
"""

from __future__ import annotations

import argparse
import collections
import json
import shutil
from pathlib import Path


def load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def ent_key(e: dict) -> tuple[int, int, str]:
    s, t = e["position"]
    return int(s), int(t), e["type"]


def validate(raw: str, ents: list[dict], fname: str) -> None:
    for i, e in enumerate(ents):
        s, t = e["position"]
        if raw[s:t] != e["text"]:
            raise SystemExit(f"{fname}: offset lệch entity {i}: {e!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--input", default="input")
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--copy-fields",
        default="candidates,assertions",
        help="field copy từ teacher cho span giữ lại; rỗng để không copy",
    )
    args = ap.parse_args()

    pred_dir = Path(args.pred)
    teacher_dir = Path(args.teacher)
    input_dir = Path(args.input)
    out_dir = Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    fields = [x.strip() for x in args.copy_fields.split(",") if x.strip()]
    stats = collections.Counter()
    by_type = collections.Counter()
    for pred_path in sorted(pred_dir.glob("*.json"), key=lambda p: int(p.stem)):
        fname = pred_path.name
        raw = (input_dir / f"{pred_path.stem}.txt").read_text(encoding="utf-8")
        pred = load_json(pred_path)
        teacher = load_json(teacher_dir / fname)
        validate(raw, pred, fname)
        validate(raw, teacher, fname)

        teacher_map = {ent_key(e): e for e in teacher}
        kept: list[dict] = []
        for e in pred:
            stats["pred"] += 1
            hit = teacher_map.get(ent_key(e))
            if not hit:
                stats["dropped"] += 1
                continue
            out_e = dict(e)
            for field in fields:
                out_e[field] = list(hit.get(field) or [])
            kept.append(out_e)
            by_type[out_e["type"]] += 1
            stats["kept"] += 1

        (out_dir / fname).write_text(
            json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"pred={stats['pred']} kept={stats['kept']} dropped={stats['dropped']}")
    for typ, n in by_type.most_common():
        print(f"  {n:5d}  {typ}")
    print("->", out_dir)


if __name__ == "__main__":
    main()
