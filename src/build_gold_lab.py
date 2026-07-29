#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gold mới = NỀN bản 11 (3 type) + THÊM 2 type xét nghiệm (spec §8a).

    python3 src/build_gold_lab.py \
        --base out/submitted/11_spec_both_31.1438.zip \
        --lab dev/votes/lab.json \
        --out out/candidates/gold_lab.zip

- Nền: giữ NGUYÊN mọi concept bản 11 (text/type/assertions/candidates/position).
- Lab: định vị span bằng "before"+text trên chuỗi read_raw (offset khớp BTC).
  Chỉ 2 type TÊN_XÉT_NGHIỆM / KẾT_QUẢ_XÉT_NGHIỆM. candidates = [] (spec: không mã).
  assertions: LIST con của {isNegated, isHistorical, isFamily}.
- Bỏ lab span trùng vị trí (chồng lấn) với concept nền cùng khoảng -> tránh nhân đôi.
- Kết quả sort theo position[0], ghi output/<n>.json + đóng zip.
"""
from __future__ import annotations
import argparse, io, json, re, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402  (read_raw)

LAB_TYPES = {"TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM"}
ALLOWED_ASSERT = {"isNegated", "isHistorical", "isFamily"}


def load_base(path: Path) -> dict[str, list]:
    """Đọc base gold -> {stem: [concepts]}. Nhận zip (output/*.json) hoặc thư mục."""
    out: dict[str, list] = {}
    if path.is_dir():
        for f in sorted(path.glob("*.json")):
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        return out
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".json"):
                stem = Path(name).stem
                out[stem] = json.loads(z.read(name).decode("utf-8"))
    return out


def _fuzzy_re(text: str) -> re.Pattern:
    """Regex khớp không phân biệt hoa-thường; run khoảng trắng/gạch nối linh hoạt.

    LLM voter hay viết thường ("AST"->"ast") hoặc đổi khoảng trắng/gạch nối
    ("NT-proBNP" vs "NT - proBNP", "-" vs en-dash "–"). Cho phép khớp lại để CỨU
    recall — nhưng span cuối cùng lấy raw[s:e] (đúng nguyên văn trong file).
    """
    parts = re.split(r"[\s\-–—]+", text.strip())
    pat = r"[\s\-–—]+".join(re.escape(p) for p in parts if p)
    return re.compile(pat, re.IGNORECASE)


def _free(s: int, e: int, used: list[tuple[int, int]]) -> bool:
    return not any(min(e, ue) > max(s, us) for us, ue in used)


def locate(raw: str, text: str, before: str, used: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Định vị span chưa dùng. Ưu tiên khớp CHÍNH XÁC (before+text -> text),
    rồi mới khớp fuzzy (hoa-thường + khoảng trắng) để cứu recall.
    Token ngắn (<=2 ký tự, vd 'K','PT','Na') BẮT BUỘC neo bằng before."""
    text = text.strip()
    if not text:
        return None
    before = (before or "")[-15:].strip()
    short = len(text) <= 2

    # --- pass 1: khớp chính xác, ưu tiên vị trí ngay sau before ---
    exact: list[int] = []
    if before:
        p = raw.find(before + text)
        if p >= 0:
            exact.append(p + len(before))
    i = raw.find(text)
    while i >= 0:
        exact.append(i)
        i = raw.find(text, i + 1)
    for p in exact:
        s, e = p, p + len(text)
        if raw[s:e] == text and _free(s, e, used):
            return s, e

    # --- pass 2: fuzzy (hoa-thường + khoảng trắng/gạch nối) ---
    rx = _fuzzy_re(text)
    # neo qua before nếu có (before khớp fuzzy để chọn đúng lần nhắc)
    anchored: list[tuple[int, int]] = []
    if before:
        brx = _fuzzy_re(before)
        for bm in brx.finditer(raw):
            m = rx.match(raw, bm.end())
            if m:
                anchored.append((m.start(), m.end()))
    generic = [(m.start(), m.end()) for m in rx.finditer(raw)]
    for s, e in anchored + generic:
        if _free(s, e, used):
            if short and (s, e) not in anchored:  # token ngắn phải neo bằng before
                continue
            return s, e
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="out/submitted/11_spec_both_31.1438.zip")
    ap.add_argument("--lab", default="dev/votes/lab.json")
    ap.add_argument("--input", default="input")
    ap.add_argument("--fixes", default="")   # JSON [{text,old,new}] sửa mã ICD sai
    ap.add_argument("--afixes", default="")  # JSON [{file,pos,assertions}] sửa assertion
    ap.add_argument("--out", default="out/candidates/gold_lab.zip")
    a = ap.parse_args()

    base = load_base(ROOT / a.base)
    lab = json.loads((ROOT / a.lab).read_text(encoding="utf-8"))
    inp = ROOT / a.input
    fixmap = {}  # (text.lower, old_code) -> new_code
    if a.fixes:
        for fx in json.loads((ROOT / a.fixes).read_text(encoding="utf-8")):
            fixmap[(fx["text"].strip().lower(), fx["old"])] = fx["new"]

    raws = {stem: sections.read_raw(inp / f"{stem}.txt") for stem in base}
    result = {stem: [dict(c) for c in cs] for stem, cs in base.items()}
    used = {stem: [tuple(c["position"]) for c in cs if c.get("position")]
            for stem, cs in result.items()}

    added = rescued = skipped_nofind = bad_assert = 0
    pending: list[dict] = []  # item drop ở file gốc -> thử cứu toàn cục

    def add(stem: str, s: int, e: int, typ: str, asserts: list) -> None:
        result[stem].append({
            "text": raws[stem][s:e], "type": typ,
            "candidates": [], "assertions": asserts, "position": [s, e],
        })
        used[stem].append((s, e))

    for stem, items in lab.items():
        if stem not in result:
            continue
        for item in items:
            typ = (item.get("type") or "").strip()
            if typ not in LAB_TYPES:
                continue
            asserts = [x for x in (item.get("assertions") or []) if x in ALLOWED_ASSERT]
            if len(asserts) != len(item.get("assertions") or []):
                bad_assert += 1
            pos = locate(raws[stem], item.get("text", ""), item.get("before", ""), used[stem])
            if pos is None:
                pending.append({"typ": typ, "asserts": asserts,
                                "text": item.get("text", ""), "before": item.get("before", "")})
                continue
            add(stem, pos[0], pos[1], typ, asserts)
            added += 1

    # --- cứu toàn cục: item bị gán nhầm file -> dò before+text trên MỌI file,
    #     chỉ nhận khi khớp DUY NHẤT một (file, vị trí) ---
    for it in pending:
        hits = []
        for stem in raws:
            pos = locate(raws[stem], it["text"], it["before"], used[stem])
            if pos is not None:
                hits.append((stem, pos))
        if len(hits) == 1:
            stem, (s, e) = hits[0]
            add(stem, s, e, it["typ"], it["asserts"])
            rescued += 1
        else:
            skipped_nofind += 1

    # --- sửa mã ICD sai (J_candidates) ---
    icd_fixed = 0
    for stem in result:
        for c in result[stem]:
            if c.get("type") == "CHẨN_ĐOÁN" and len(c.get("candidates", [])) == 1:
                new = fixmap.get((c["text"].strip().lower(), c["candidates"][0]))
                if new:
                    c["candidates"] = [new]
                    icd_fixed += 1

    # --- sửa assertion multi-label theo (file, vị trí) ---
    assert_fixed = 0
    if a.afixes:
        for fx in json.loads((ROOT / a.afixes).read_text(encoding="utf-8")):
            stem = str(fx["file"]); ps, pe = fx["pos"]
            for c in result.get(stem, []):
                if c["position"] == [ps, pe]:
                    c["assertions"] = [x for x in fx["assertions"] if x in ALLOWED_ASSERT]
                    assert_fixed += 1

    for stem in result:
        result[stem].sort(key=lambda c: (c["position"][0], c["position"][1]))

    outp = ROOT / a.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(outp, "w", zipfile.ZIP_DEFLATED) as z:
        for stem, concepts in result.items():
            z.writestr(f"output/{stem}.json",
                       json.dumps(concepts, ensure_ascii=False, indent=2))

    print(f"OK -> {outp}")
    print(f"  lab added    : {added}")
    print(f"  rescued(g)   : {rescued}")
    print(f"  not located  : {skipped_nofind}")
    print(f"  assert fixed : {bad_assert}")
    print(f"  icd fixed    : {icd_fixed}")
    print(f"  assert fixed2: {assert_fixed}")
    print(f"  total concepts: {sum(len(v) for v in result.values())}")


if __name__ == "__main__":
    main()
