"""So sánh output model với teacher theo exact span/type.

Đây không phải điểm BTC, chỉ là kính lúp để biết model distill còn thiếu/thừa gì so với
teacher 82x.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def load_dir(path: Path) -> dict[str, list[dict]]:
    return {
        p.name: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(path.glob("*.json"), key=lambda x: int(x.stem))
    }


def key(e: dict) -> tuple[int, int, str]:
    return (int(e["position"][0]), int(e["position"][1]), e["type"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--teacher", required=True)
    args = ap.parse_args()

    pred = load_dir(Path(args.pred))
    teacher = load_dir(Path(args.teacher))
    files = sorted(set(pred) & set(teacher), key=lambda x: int(Path(x).stem))

    tp = fp = fn = 0
    miss_by_type: collections.Counter[str] = collections.Counter()
    extra_by_type: collections.Counter[str] = collections.Counter()
    field_diff = collections.Counter()
    worst_files: list[tuple[int, str, int, int]] = []
    for fname in files:
        ps = {key(e): e for e in pred[fname]}
        ts = {key(e): e for e in teacher[fname]}
        hits = set(ps) & set(ts)
        miss = set(ts) - set(ps)
        extra = set(ps) - set(ts)
        tp += len(hits)
        fp += len(extra)
        fn += len(miss)
        worst_files.append((len(miss) + len(extra), fname, len(miss), len(extra)))
        for k in miss:
            miss_by_type[k[2]] += 1
        for k in extra:
            extra_by_type[k[2]] += 1
        for k in hits:
            pe, te = ps[k], ts[k]
            if (pe.get("candidates") or []) != (te.get("candidates") or []):
                field_diff["candidates"] += 1
            if (pe.get("assertions") or []) != (te.get("assertions") or []):
                field_diff["assertions"] += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    print(f"files: {len(files)}")
    print(f"exact span/type: tp={tp} fp={fp} fn={fn}")
    print(f"precision={precision:.4f} recall={recall:.4f} f1={f1:.4f}")
    print("\nmissing teacher by type:")
    for typ, n in miss_by_type.most_common():
        print(f"  {n:5d}  {typ}")
    print("\nextra pred by type:")
    for typ, n in extra_by_type.most_common():
        print(f"  {n:5d}  {typ}")
    print("\nfield diff on exact hits:")
    for name in ("candidates", "assertions"):
        print(f"  {field_diff[name]:5d}  {name}")
    print("\nworst files:")
    for total, fname, miss, extra in sorted(worst_files, reverse=True)[:10]:
        print(f"  {fname:>8s}  miss={miss:3d} extra={extra:3d} total={total:3d}")


if __name__ == "__main__":
    main()
