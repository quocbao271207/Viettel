"""Tách một submission zip thành thư mục nhãn teacher để distill NER.

Ví dụ:

    python src/teacher_from_zip.py \
        --zip artifacts/teammate_latest_candidates/82x_cleanroom4_k2.zip \
        --out data/teacher_82x

Script này KHÔNG sinh nhãn mới. Nó chỉ lấy output đã có điểm public tốt, kiểm lại offset
với `input/*.txt`, rồi lưu thành dạng giống `data/gt_block/*.json` để `src/ner_data.py`
có thể dựng dataset token-classification.
"""

from __future__ import annotations

import argparse
import collections
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALID_TYPES = {
    "TRIỆU_CHỨNG",
    "CHẨN_ĐOÁN",
    "TÊN_XÉT_NGHIỆM",
    "KẾT_QUẢ_XÉT_NGHIỆM",
    "THUỐC",
}


def display_path(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _json_members(zf: zipfile.ZipFile) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in zf.namelist():
        p = Path(name)
        if p.suffix != ".json":
            continue
        if not p.stem.isdigit():
            continue
        out[f"{int(p.stem)}.json"] = name
    return out


def normalize_entity(e: dict, raw: str, fname: str) -> dict:
    if not isinstance(e, dict):
        raise SystemExit(f"{fname}: entity không phải object: {e!r}")
    try:
        s, t = e["position"]
        typ = e["type"]
        text = e["text"]
    except Exception as exc:
        raise SystemExit(f"{fname}: entity thiếu trường bắt buộc: {e!r}") from exc
    if typ not in VALID_TYPES:
        raise SystemExit(f"{fname}: type lạ {typ!r}")
    if not (isinstance(s, int) and isinstance(t, int) and 0 <= s < t <= len(raw)):
        raise SystemExit(f"{fname}: position lỗi {e.get('position')!r}")
    if raw[s:t] != text:
        raise SystemExit(
            f"{fname}: offset lệch {s}-{t}: zip={text!r}, raw={raw[s:t]!r}"
        )
    return {
        "text": text,
        "position": [s, t],
        "type": typ,
        "assertions": list(e.get("assertions") or []),
        "candidates": list(e.get("candidates") or []),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--input", default=str(ROOT / "input"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    zpath = Path(args.zip)
    input_dir = Path(args.input)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zpath) as zf:
        members = _json_members(zf)
        if len(members) != 100:
            raise SystemExit(f"{zpath}: cần 100 file json, thấy {len(members)}")
        by_type: collections.Counter[str] = collections.Counter()
        total = ncand = nasrt = 0
        for i in range(1, 101):
            jname = f"{i}.json"
            raw = (input_dir / f"{i}.txt").read_text(encoding="utf-8")
            ents_raw = json.loads(zf.read(members[jname]).decode("utf-8"))
            if not isinstance(ents_raw, list):
                raise SystemExit(f"{jname}: nội dung không phải list")
            ents = [normalize_entity(e, raw, jname) for e in ents_raw]
            ents.sort(key=lambda e: (e["position"][0], e["position"][1], e["type"]))
            for a, b in zip(ents, ents[1:]):
                if b["position"][0] < a["position"][1]:
                    raise SystemExit(
                        f"{jname}: span chồng nhau {a['position']} và {b['position']}"
                    )
            (out_dir / jname).write_text(
                json.dumps(ents, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            by_type.update(e["type"] for e in ents)
            ncand += sum(1 for e in ents if e["candidates"])
            nasrt += sum(1 for e in ents if e["assertions"])
            total += len(ents)

    print(f"{display_path(out_dir)} <- {zpath.name}")
    print(f"{total} entity trên 100 file")
    for typ, n in by_type.most_common():
        print(f"  {n:5d}  {typ}")
    print(f"  {ncand:5d}  có candidates")
    print(f"  {nasrt:5d}  có assertions")


if __name__ == "__main__":
    main()
