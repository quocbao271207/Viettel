#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bản 16 = nền bản 14 + concept MỚI trích lại ở các file mật độ thấp.

    python3 src/build_reextract.py --new dev/reextract.json --out out/candidates/16_reextract.zip

Khác `build_repeat.py`: script kia chỉ nhân bản text ĐÃ có sang lần nhắc khác, còn script
này nhận concept HOÀN TOÀN MỚI do LLM trích lại (text chưa từng xuất hiện trong bộ nhãn).

Định vị: dùng "before" + text như `build_gold_lab.py` — LLM không đếm được offset.
Bỏ ca không định vị được DUY NHẤT (an toàn hơn đặt sai chỗ; bài học bản 12: lab gán nhầm file).

Mã ICD/RxNorm: chỉ COPY từ concept nền cùng (text, type) nếu có. Text mới hoàn toàn thì để
RỖNG — spec §8b FAQ 5: candidates không chắc thì để rỗng là an toàn nhất.
"""
from __future__ import annotations
import argparse, collections, json, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_ASSERT = {"isNegated", "isHistorical", "isFamily"}
TYPES = {"THUỐC", "CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM"}
CODED_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}


def load_base(path: Path) -> dict[str, list]:
    with zipfile.ZipFile(path) as z:
        return {Path(n).stem: json.loads(z.read(n).decode("utf-8"))
                for n in z.namelist() if n.endswith(".json")}


def locate(raw: str, text: str, before: str, taken: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Vị trí span bằng before+text. Chỉ nhận khi xác định được DUY NHẤT một chỗ trống."""
    if not text or text not in raw:
        return None
    spots = []
    start = 0
    while (i := raw.find(text, start)) != -1:
        spots.append(i)
        start = i + 1
    free = [i for i in spots if not any(min(i + len(text), b) > max(i, a) for a, b in taken)]
    if not free:
        return None
    if len(free) == 1:
        return free[0], free[0] + len(text)
    # nhiều chỗ trống -> dùng before để chọn, ưu tiên đuôi before dài nhất khớp
    for k in range(len(before), 2, -1):
        suffix = before[-k:]
        hit = [i for i in free if i >= k and raw[i - k:i] == suffix]
        if len(hit) == 1:
            return hit[0], hit[0] + len(text)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="out/submitted/14_repeat_36.4914.zip")
    ap.add_argument("--new", default="dev/reextract.json")
    ap.add_argument("--out", default="out/candidates/16_reextract.zip")
    ap.add_argument("--codes", default="dev/newcodes.json",
                    help="mã ICD gán tay cho cụm CHẨN_ĐOÁN mới (text -> {type, codes})")
    args = ap.parse_args()

    base = load_base(ROOT / args.base)
    raws = {p.stem: p.read_text(encoding="utf-8") for p in (ROOT / "input").glob("*.txt")}
    code_of = {(c["text"], c["type"]): c["candidates"]
               for cs in base.values() for c in cs if c.get("candidates")}

    # mã gán tay cho vốn từ MỚI (không có trong nền) — chỉ CHẨN_ĐOÁN, thuốc cố ý để rỗng
    manual = json.loads((ROOT / args.codes).read_text("utf-8")) if (ROOT / args.codes).exists() else {}
    for text, spec in manual.items():
        if isinstance(spec, dict) and "codes" in spec:
            code_of.setdefault((text, spec["type"]), spec["codes"])

    added, dropped = collections.Counter(), collections.Counter()
    for item in json.loads((ROOT / args.new).read_text("utf-8")):
        stem, text, typ = str(item.get("file")), item.get("text", ""), item.get("type")
        if stem not in raws or typ not in TYPES:
            dropped["file/type sai"] += 1
            continue
        # Bài học bản 15 (−0.075): cụm 1 âm tiết ngắn ("đau", "nang", "sẹo") nằm DƯỚI ngưỡng
        # hoà vốn — J phạt dự đoán thừa nhiều hơn phần WER kiếm được. Type xét nghiệm được
        # miễn trừ vì viết tắt ("HA", "PT") là tên xét nghiệm hợp lệ và lab luôn ăn điểm.
        if typ not in {"TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM"} and len(text.split()) < 2 and len(text) < 5:
            dropped["cụm 1 âm tiết ngắn"] += 1
            continue
        taken = [tuple(c["position"]) for c in base[stem]]
        if item.get("start") is not None:
            # ứng viên đã có offset sẵn (quét bằng script, không phải LLM đoán)
            s = int(item["start"])
            pos = (s, s + len(text))
            if raws[stem][s:pos[1]] != text or any(min(pos[1], b) > max(s, a) for a, b in taken):
                dropped["offset sai/chồng lấn"] += 1
                continue
        else:
            pos = locate(raws[stem], text, item.get("before", ""), taken)
        if pos is None:
            dropped["không định vị được"] += 1
            continue
        base[stem].append({
            "text": text, "type": typ,
            "candidates": list(code_of.get((text, typ), [])) if typ in CODED_TYPES else [],
            "assertions": [a for a in item.get("assertions", []) if a in ALLOWED_ASSERT],
            "position": [pos[0], pos[1]],
        })
        added[typ] += 1

    bad = 0
    for stem, cs in base.items():
        cs.sort(key=lambda c: c["position"][0])
        for c in cs:
            s, e = c["position"]
            if raws[stem][s:e] != c["text"]:
                bad += 1
            if c["type"] not in CODED_TYPES and c["candidates"]:
                bad += 1
            if set(c["assertions"]) - ALLOWED_ASSERT:
                bad += 1

    outp = ROOT / args.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(outp, "w", zipfile.ZIP_DEFLATED) as z:
        for stem, cs in sorted(base.items(), key=lambda kv: int(kv[0])):
            z.writestr(f"output/{stem}.json", json.dumps(cs, ensure_ascii=False, indent=1))

    print(f"thêm {sum(added.values())} concept -> tổng {sum(len(v) for v in base.values())}")
    print(" ", dict(added), "| bỏ:", dict(dropped))
    print(f"vi phạm verify: {bad}  ->  {outp}")


if __name__ == "__main__":
    main()
