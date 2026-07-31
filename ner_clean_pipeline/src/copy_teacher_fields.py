"""Copy candidates/assertions từ teacher cho các span model đã bắt đúng tuyệt đối.

Script này KHÔNG thêm entity và KHÔNG sửa position/text/type. Nó chỉ thay hai trường
`candidates` và `assertions` khi pred có cùng `(file, start, end, type)` với teacher.

Mục đích: tách lỗi model-span khỏi lỗi field. Nếu probe này tăng điểm, ta biết cần đầu tư
vào candidate/assertion; nếu không tăng, nút thắt chính vẫn là span/type.
"""

from __future__ import annotations

import argparse
import collections
import json
import shutil
from pathlib import Path


def read_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def key(e: dict) -> tuple[int, int, str]:
    return (int(e["position"][0]), int(e["position"][1]), e["type"])


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
        "--fields",
        default="candidates,assertions",
        help="danh sách field cần copy, ví dụ candidates hoặc candidates,assertions",
    )
    args = ap.parse_args()

    pred_dir = Path(args.pred)
    teacher_dir = Path(args.teacher)
    input_dir = Path(args.input)
    out_dir = Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    fields = [x.strip() for x in args.fields.split(",") if x.strip()]
    allowed = {"candidates", "assertions"}
    bad = set(fields) - allowed
    if bad:
        raise SystemExit(f"field không hỗ trợ: {sorted(bad)}")

    stats = collections.Counter()
    by_type = collections.Counter()
    for pred_path in sorted(pred_dir.glob("*.json"), key=lambda p: int(p.stem)):
        fname = pred_path.name
        raw = (input_dir / f"{pred_path.stem}.txt").read_text(encoding="utf-8")
        pred = read_json(pred_path)
        teacher = read_json(teacher_dir / fname)
        validate(raw, pred, fname)
        validate(raw, teacher, fname)

        tmap = {key(e): e for e in teacher}
        for e in pred:
            stats["pred"] += 1
            hit = tmap.get(key(e))
            if not hit:
                continue
            stats["exact_hit"] += 1
            by_type[e["type"]] += 1
            for field in fields:
                before = tuple(e.get(field) or [])
                after = list(hit.get(field) or [])
                e[field] = after
                if before != tuple(after):
                    stats[f"changed_{field}"] += 1
                if after:
                    stats[f"nonempty_{field}"] += 1

        (out_dir / fname).write_text(
            json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"pred: {stats['pred']}")
    print(f"exact-hit teacher: {stats['exact_hit']} ({stats['exact_hit'] / max(1, stats['pred']):.3f})")
    for typ, n in by_type.most_common():
        print(f"  {n:5d}  {typ}")
    for field in fields:
        print(
            f"{field}: changed {stats[f'changed_{field}']}, "
            f"nonempty copied {stats[f'nonempty_{field}']}"
        )
    print("->", out_dir)


if __name__ == "__main__":
    main()
