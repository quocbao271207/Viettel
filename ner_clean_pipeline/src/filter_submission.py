"""Filter obvious false-positive entities from an output submission.

The filters here are deliberately conservative and based on leaderboard lessons:

- Masked drugs made of `*****` are bait and should not be predicted.
- One-character drug spans are tokenizer debris.
- Vital signs/generic test words as lab names hurt in teammate submission 16.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
Entity = dict[str, Any]

VITAL_LAB_NAMES = {
    "huyết áp",
    "ha",
    "mạch",
    "nhiệt độ",
    "nhịp thở",
    "spo2",
    "sp02",
    "glasgow",
    "dấu hiệu sinh tồn",
    "vs",
}

GENERIC_LAB_PATTERNS = [
    re.compile(r"^xét nghiệm(?:\\s|$)", re.I),
    re.compile(r"^chụp kiểm tra$", re.I),
    re.compile(r"^chẩn đoán hình ảnh$", re.I),
]


def extract_if_zip(path: Path, tmp: Path) -> Path:
    if path.is_dir():
        return path / "output" if (path / "output").is_dir() else path
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(path) as zf:
        zf.extractall(tmp)
    return tmp / "output" if (tmp / "output").is_dir() else tmp


def is_bad_drug(e: Entity) -> bool:
    if e.get("type") != "THUỐC":
        return False
    text = e.get("text", "").strip()
    if "*" in text:
        return True
    if len(text) <= 2:
        return True
    if not re.search(r"[A-Za-zÀ-ỹ]", text):
        return True
    return False


def is_bad_lab(e: Entity) -> bool:
    if e.get("type") != "TÊN_XÉT_NGHIỆM":
        return False
    key = re.sub(r"\s+", " ", e.get("text", "").strip().lower())
    if key in VITAL_LAB_NAMES:
        return True
    return any(p.search(key) for p in GENERIC_LAB_PATTERNS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True, help="zip or directory")
    ap.add_argument("--out", required=True, help="output zip")
    ap.add_argument("--drop-mask-drugs", action="store_true")
    ap.add_argument("--drop-vital-labs", action="store_true")
    args = ap.parse_args()

    out_zip = ROOT / args.out
    out_dir = out_zip.with_suffix("")
    pred_dir = extract_if_zip(ROOT / args.pred, out_dir.parent / "_filter_extract")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "output").mkdir(parents=True)

    removed: dict[str, int] = {"drug": 0, "lab": 0}
    kept_total = 0
    for fid in map(str, range(1, 101)):
        arr = json.loads((pred_dir / f"{fid}.json").read_text(encoding="utf-8"))
        kept: list[Entity] = []
        raw = (ROOT / "input" / f"{fid}.txt").read_text(encoding="utf-8")
        for e in arr:
            if args.drop_mask_drugs and is_bad_drug(e):
                removed["drug"] += 1
                continue
            if args.drop_vital_labs and is_bad_lab(e):
                removed["lab"] += 1
                continue
            s, t = e["position"]
            if raw[s:t] != e["text"]:
                raise ValueError(f"{fid}: bad offset {e!r}")
            kept.append(e)
        kept_total += len(kept)
        (out_dir / "output" / f"{fid}.json").write_text(
            json.dumps(kept, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if out_zip.exists():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted((out_dir / "output").glob("*.json"), key=lambda x: int(x.stem)):
            zf.write(p, f"output/{p.name}")

    print("kept", kept_total)
    print("removed", removed)
    print("->", out_zip)


if __name__ == "__main__":
    main()
