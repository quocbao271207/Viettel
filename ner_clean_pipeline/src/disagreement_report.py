"""Xuất CSV các entity đang bất đồng giữa nhiều teacher.

Ví dụ:

    python src/disagreement_report.py --out artifacts/diagnostics/teacher_disagreement.csv

CSV này là bảng soi thủ công/LLM: mỗi dòng là một span, có cờ xuất hiện trong 82x/85/87/88,
field candidates/assertions và context quanh span.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEACHERS = ("82x", "85", "87", "88")


def load_teacher(tag: str) -> dict[str, list[dict]]:
    d = ROOT / "data" / f"teacher_{tag}"
    return {
        p.name: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(d.glob("*.json"), key=lambda x: int(x.stem))
    }


def key(e: dict) -> tuple[int, int, str]:
    return int(e["position"][0]), int(e["position"][1]), e["type"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "artifacts/diagnostics/teacher_disagreement.csv"))
    ap.add_argument("--ctx", type=int, default=90)
    args = ap.parse_args()

    teachers = {tag: load_teacher(tag) for tag in TEACHERS}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str | int]] = []
    for fid in range(1, 101):
        fname = f"{fid}.json"
        raw = (ROOT / "input" / f"{fid}.txt").read_text(encoding="utf-8")
        by_key: dict[tuple[int, int, str], dict[str, dict]] = {}
        for tag in TEACHERS:
            for e in teachers[tag][fname]:
                by_key.setdefault(key(e), {})[tag] = e
        for k, pres in sorted(by_key.items()):
            if len(pres) == len(TEACHERS):
                continue
            s, t, typ = k
            sample = next(iter(pres.values()))
            context = raw[max(0, s - args.ctx) : min(len(raw), t + args.ctx)]
            rows.append(
                {
                    "file": fname,
                    "start": s,
                    "end": t,
                    "type": typ,
                    "text": sample["text"],
                    "in_82x": int("82x" in pres),
                    "in_85": int("85" in pres),
                    "in_87": int("87" in pres),
                    "in_88": int("88" in pres),
                    "candidates": "|".join(sample.get("candidates") or []),
                    "assertions": "|".join(sample.get("assertions") or []),
                    "context": " ".join(context.split()),
                }
            )

    with out.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"{len(rows)} disagreement rows -> {out}")


if __name__ == "__main__":
    main()
