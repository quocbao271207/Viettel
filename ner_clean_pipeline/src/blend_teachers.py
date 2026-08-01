"""Sinh submission blend từ các teacher public.

Các mode chính:

- coded_dx: lấy nền 85, chỉ thêm 87-only CHẨN_ĐOÁN có candidates.
- coded: thêm mọi 87-only có candidates.
- asserted: thêm mọi 87-only có assertions.
- coded_or_asserted: union hai nhóm trên.
- safe: rule bảo thủ hơn coded_or_asserted, thêm một số symptom/lab/drug có vẻ thật.
- all87: nền 85 + toàn bộ 87-only, tương đương span của 87 nhưng field nền từ 85.
- drop88: nền 85, bỏ mọi span không có trong 88, copy field từ 88 nếu có.

Đây là probe leaderboard, không phải pipeline final/private.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VITAL_LABS = {
    "huyết áp",
    "ha",
    "mạch",
    "nhiệt độ",
    "nhịp thở",
    "spo2",
    "sp02",
    "glasgow",
}
BAD_TEST = {
    "n",
    "trực tiếp",
    "vi khuẩn",
    "ct",
}
BAD_DRUG_WORDS = {
    "thuốc cản quang",
    "truyền dịch tĩnh mạch 750cc",
    "chất gây nghiện opioid",
    "thở oxy tại nhà",
    "intravenous fluids",
}


def load_teacher(tag: str) -> dict[str, list[dict]]:
    d = ROOT / "data" / f"teacher_{tag}"
    return {
        p.name: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(d.glob("*.json"), key=lambda x: int(x.stem))
    }


def ent_key(e: dict) -> tuple[int, int, str]:
    s, t = e["position"]
    return int(s), int(t), e["type"]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def looks_bad(e: dict) -> bool:
    text = norm(e["text"])
    typ = e["type"]
    if not text:
        return True
    if typ == "THUỐC":
        if "*" in text or len(text) <= 2 or text in BAD_DRUG_WORDS:
            return True
        if not re.search(r"[a-zà-ỹ]", text):
            return True
    if typ == "TÊN_XÉT_NGHIỆM":
        if text in VITAL_LABS or text in BAD_TEST or len(text) <= 2:
            return True
        if text.startswith("xét nghiệm ") and len(text.split()) <= 3:
            return True
    if typ == "KẾT_QUẢ_XÉT_NGHIỆM":
        if re.fullmatch(r"[-+]?[0-9]+(?:[,.][0-9]+)?(?:\\s*[a-z/%]+)?", text):
            return True
    if typ in {"TRIỆU_CHỨNG", "CHẨN_ĐOÁN"} and len(text) <= 2:
        return True
    return False


def should_add(e: dict, mode: str) -> bool:
    if mode == "all87":
        return True
    if looks_bad(e):
        return False
    has_cand = bool(e.get("candidates"))
    has_assert = bool(e.get("assertions"))
    typ = e["type"]
    text = norm(e["text"])
    if mode == "coded_dx":
        return typ == "CHẨN_ĐOÁN" and has_cand
    if mode == "coded":
        return has_cand
    if mode == "asserted":
        return has_assert
    if mode == "coded_or_asserted":
        return has_cand or has_assert
    if mode == "safe":
        if has_cand:
            return True
        if has_assert and typ in {"TRIỆU_CHỨNG", "CHẨN_ĐOÁN", "KẾT_QUẢ_XÉT_NGHIỆM"}:
            return True
        if typ == "THUỐC":
            return text in {"insulin", "calcium", "sắt", "kẽm", "asa", "kháng sinh"}
        if typ == "TÊN_XÉT_NGHIỆM":
            good = {"điện tim", "ecg", "na+", "k+", "cl-", "na", "k", "cl", "sinh thiết"}
            return text in good
        if typ == "TRIỆU_CHỨNG":
            return any(w in text for w in ("sốt", "nôn", "sưng", "có mủ", "ngã"))
        if typ == "CHẨN_ĐOÁN":
            return len(text.split()) >= 2 and text not in {"stress", "chấn thương"}
        return False
    raise SystemExit(f"mode không hỗ trợ: {mode}")


def validate(raw: str, ents: list[dict], fname: str) -> None:
    last_end = -1
    for e in sorted(ents, key=ent_key):
        s, t = e["position"]
        if raw[s:t] != e["text"]:
            raise SystemExit(f"{fname}: offset lệch {e!r}")
        if s < last_end:
            raise SystemExit(f"{fname}: span chồng nhau quanh {e!r}")
        last_end = t


def write_zip(out_dir: Path, out_zip: Path) -> None:
    if out_zip.exists():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted((out_dir / "output").glob("*.json"), key=lambda x: int(x.stem)):
            zf.write(p, f"output/{p.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    base = load_teacher("85")
    add87 = load_teacher("87")
    keep88 = load_teacher("88")
    out_zip = ROOT / args.out
    out_dir = out_zip.with_suffix("")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "output").mkdir(parents=True)

    stats = collections.Counter()
    by_type = collections.Counter()
    for fid in range(1, 101):
        fname = f"{fid}.json"
        raw = (ROOT / "input" / f"{fid}.txt").read_text(encoding="utf-8")
        ents = [dict(e) for e in base[fname]]
        by_key = {ent_key(e): e for e in ents}

        if args.mode == "drop88":
            k88 = {ent_key(e): e for e in keep88[fname]}
            ents = []
            for e in base[fname]:
                hit = k88.get(ent_key(e))
                if hit:
                    out_e = dict(e)
                    out_e["candidates"] = list(hit.get("candidates") or [])
                    out_e["assertions"] = list(hit.get("assertions") or [])
                    ents.append(out_e)
                else:
                    stats["dropped"] += 1
        else:
            for e in add87[fname]:
                k = ent_key(e)
                if k in by_key:
                    continue
                if should_add(e, args.mode):
                    ents.append(dict(e))
                    stats["added"] += 1
                    by_type[e["type"]] += 1
                else:
                    stats["skipped"] += 1

        ents.sort(key=ent_key)
        validate(raw, ents, fname)
        stats["total"] += len(ents)
        (out_dir / "output" / fname).write_text(
            json.dumps(ents, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    write_zip(out_dir, out_zip)
    print(f"mode={args.mode} total={stats['total']} added={stats['added']} "
          f"skipped={stats['skipped']} dropped={stats['dropped']}")
    for typ, n in by_type.most_common():
        print(f"  {n:5d}  added {typ}")
    print("->", out_zip)


if __name__ == "__main__":
    main()
