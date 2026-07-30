"""Compare two output submissions and write review-friendly delta reports."""

from __future__ import annotations

import argparse
import collections
import csv
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
Entity = dict[str, Any]


def extract_if_zip(path: Path, tmp: Path) -> Path:
    if path.is_dir():
        return path / "output" if (path / "output").is_dir() else path
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(path) as zf:
        zf.extractall(tmp)
    return tmp / "output" if (tmp / "output").is_dir() else tmp


def load(path: Path) -> dict[str, list[Entity]]:
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(path.glob("*.json"), key=lambda x: int(x.stem))
    }


def overlap(a: Entity, b: Entity) -> int:
    if a.get("type") != b.get("type"):
        return 0
    s1, t1 = a["position"]
    s2, t2 = b["position"]
    return max(0, min(t1, t2) - max(s1, s2))


def matched(e: Entity, arr: list[Entity], th: float) -> bool:
    for x in arr:
        ov = overlap(e, x)
        if not ov:
            continue
        le = e["position"][1] - e["position"][0]
        lx = x["position"][1] - x["position"][0]
        if ov / max(1, min(le, lx)) >= th:
            return True
    return False


def context(raw: str, start: int, end: int, n: int = 60) -> str:
    left = raw[max(0, start - n) : start].replace("\n", " ")
    mid = raw[start:end].replace("\n", " ")
    right = raw[end : min(len(raw), end + n)].replace("\n", " ")
    return f"{left}[[{mid}]]{right}"


def row(file_id: str, e: Entity, side: str) -> dict[str, str]:
    raw = (ROOT / "input" / f"{file_id}.txt").read_text(encoding="utf-8")
    s, t = e["position"]
    return {
        "side": side,
        "file": file_id,
        "type": e.get("type", ""),
        "text": e.get("text", ""),
        "start": str(s),
        "end": str(t),
        "assertions": "|".join(e.get("assertions") or []),
        "candidates": "|".join(e.get("candidates") or []),
        "context": context(raw, s, t),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="zip or directory, usually teammate/best")
    ap.add_argument("--b", required=True, help="zip or directory, usually NER/new")
    ap.add_argument("--name-a", default="a")
    ap.add_argument("--name-b", default="b")
    ap.add_argument("--out", default="artifacts/diagnostics/submission_delta.csv")
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    a_dir = extract_if_zip(ROOT / args.a, out.parent / "_a_extract")
    b_dir = extract_if_zip(ROOT / args.b, out.parent / "_b_extract")
    A = load(a_dir)
    B = load(b_dir)

    rows: list[dict[str, str]] = []
    summary: collections.Counter[tuple[str, str]] = collections.Counter()
    for fid in map(str, range(1, 101)):
        aa = A.get(fid, [])
        bb = B.get(fid, [])
        for e in aa:
            if not matched(e, bb, args.threshold):
                rows.append(row(fid, e, f"only_{args.name_a}"))
                summary[(f"only_{args.name_a}", e.get("type", ""))] += 1
        for e in bb:
            if not matched(e, aa, args.threshold):
                rows.append(row(fid, e, f"only_{args.name_b}"))
                summary[(f"only_{args.name_b}", e.get("type", ""))] += 1

    fields = [
        "side",
        "file",
        "type",
        "text",
        "start",
        "end",
        "assertions",
        "candidates",
        "context",
    ]
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print("side\ttype\tcount")
    for (side, typ), n in sorted(summary.items()):
        print(f"{side}\t{typ}\t{n}")
    print("->", out)


if __name__ == "__main__":
    main()
