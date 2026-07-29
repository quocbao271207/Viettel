#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CỔNG CỨNG — không có gì rời khỏi harness mà chưa qua đây.

    python3 -m src.harness.validate out/submitted/14_repeat_36.4914.zip

Kiểm mọi bất biến mà một bản nộp hợp lệ phải thoả. Bất kỳ vi phạm nào cũng là
lỗi CHẶN (exit 1) — vì mỗi lượt nộp là tài nguyên khan hiếm (5/ngày).
"""
from __future__ import annotations

import json
import sys
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import spec  # noqa: E402

_GAZ: dict | None = None


def gaz() -> dict:
    global _GAZ
    if _GAZ is None:
        _GAZ = json.loads((ROOT / "data/gaz.json").read_text(encoding="utf-8"))
    return _GAZ


def read_raw(i: int) -> str:
    """Y hệt src/sections.read_raw — offset của BTC tính trên chuỗi này."""
    raw = (ROOT / "input" / f"{i}.txt").read_text(encoding="utf-8")
    nfc = unicodedata.normalize("NFC", raw)
    return nfc if len(nfc) == len(raw) else raw


def code_exists(code: str, type_: str) -> bool:
    g = gaz()
    if type_ == "CHẨN_ĐOÁN":
        return spec.undot(code) in g["icd_code2en"]
    if type_ == "THUỐC":
        if not code.isdigit():
            return False
        return (code in set(g["in"].values())
                or code in set(g["scd_full"].values())
                or any(code in v for v in g["scd_by_ing"].values()))
    return False


def validate(preds: dict[str, list[dict]], strict_codes: bool = True) -> list[str]:
    """Trả danh sách lỗi. Rỗng = sạch."""
    errs: list[str] = []
    if set(preds) != {str(i) for i in range(1, 101)}:
        missing = {str(i) for i in range(1, 101)} - set(preds)
        extra = set(preds) - {str(i) for i in range(1, 101)}
        if missing:
            errs.append(f"THIẾU file: {sorted(missing, key=int)}")
        if extra:
            errs.append(f"THỪA file: {sorted(extra)}")

    for fid in sorted(preds, key=lambda x: int(x) if x.isdigit() else 0):
        raw = read_raw(int(fid)) if fid.isdigit() else ""
        spans: list[tuple[int, int, str]] = []
        for k, e in enumerate(preds[fid]):
            tag = f"file {fid} #{k}"
            # --- schema
            if set(e) != {"text", "type", "candidates", "assertions", "position"}:
                errs.append(f"{tag}: khoá sai {sorted(e)}")
                continue
            if e["type"] not in spec.TYPES:
                errs.append(f"{tag}: type lạ {e['type']!r}")
            bad = [a for a in (e["assertions"] or []) if a not in spec.ASSERTIONS]
            if bad:
                errs.append(f"{tag}: assertion lạ {bad}")
            if len(set(e["assertions"] or [])) != len(e["assertions"] or []):
                errs.append(f"{tag}: assertion trùng lặp {e['assertions']}")

            # --- vị trí phải khớp NGUYÊN VĂN
            pos = e["position"]
            if not (isinstance(pos, list) and len(pos) == 2 and 0 <= pos[0] < pos[1] <= len(raw)):
                errs.append(f"{tag}: position không hợp lệ {pos} (len raw={len(raw)})")
                continue
            s, t = pos
            if raw[s:t] != e["text"]:
                if unicodedata.normalize("NFC", raw[s:t]) != unicodedata.normalize("NFC", e["text"]):
                    errs.append(f"{tag}: raw[{s}:{t}]={raw[s:t]!r} != text {e['text']!r}")
            spans.append((s, t, e["type"]))

            # --- candidates
            cands = e["candidates"] or []
            if e["type"] not in spec.CODED_TYPES:
                if cands:
                    errs.append(f"{tag}: {e['type']} KHÔNG được có candidates (§5) {cands}")
            else:
                for c in cands:
                    if e["type"] == "CHẨN_ĐOÁN" and len(c) > 3 and "." not in c:
                        errs.append(f"{tag}: ICD THIẾU DẤU CHẤM {c!r} (mất nửa J_cand)")
                    if strict_codes and not code_exists(c, e["type"]):
                        errs.append(f"{tag}: mã {c!r} không tồn tại trong gaz.json ({e['type']})")

        # --- chồng lấn: cảnh báo (bản 11 đã có 1 ca hợp lệ), báo khi tăng bất thường
        spans.sort()
        ov = sum(1 for a, b in zip(spans, spans[1:]) if b[0] < a[1])
        if ov > 3:
            errs.append(f"file {fid}: {ov} cặp span CHỒNG LẤN (ngưỡng cảnh báo 3)")
    return errs


def load_zip(p: str | Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    with zipfile.ZipFile(p) as z:
        for n in z.namelist():
            if n.endswith(".json"):
                out[Path(n).stem] = json.loads(z.read(n).decode("utf-8"))
    return out


def summarize(preds: dict[str, list[dict]]) -> str:
    tot = sum(len(v) for v in preds.values())
    ty = Counter(e["type"] for v in preds.values() for e in v)
    coded = sum(1 for v in preds.values() for e in v
                if e["type"] in spec.CODED_TYPES and e.get("candidates"))
    codable = sum(1 for v in preds.values() for e in v if e["type"] in spec.CODED_TYPES)
    lines = [f"{tot} concept / {len(preds)} file"]
    lines += [f"   {k:22s} {n:5d}" for k, n in ty.most_common()]
    lines.append(f"   có mã: {coded}/{codable} concept được chấm J_cand")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("dùng: python3 -m src.harness.validate <file.zip | file.json>")
    p = Path(sys.argv[1])
    preds = load_zip(p) if p.suffix == ".zip" else json.loads(p.read_text(encoding="utf-8"))
    print(summarize(preds))
    errs = validate(preds)
    if errs:
        print(f"\n❌ {len(errs)} LỖI:")
        for e in errs[:60]:
            print("  -", e)
        if len(errs) > 60:
            print(f"  ... và {len(errs)-60} lỗi nữa")
        raise SystemExit(1)
    print("\n✅ SẠCH — qua toàn bộ cổng cứng.")


if __name__ == "__main__":
    main()
