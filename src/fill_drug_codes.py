#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Điền RxNorm cho concept THUỐC đang RỖNG mã trong 1 submission zip (cược 1 chiều).
KHÔNG đụng text/type/assertion/position, KHÔNG đụng concept đã có mã -> WER & J_assert giữ nguyên,
J_cand chỉ có thể tăng. LLM (gpt-4o) chuẩn hoá tên VN/lỗi -> hoạt chất tiếng Anh -> RXCUI qua gazetteer.

    python3 src/fill_drug_codes.py --in out/submitted/06_claude_rerank_30.2557.zip --out claude_filled
-> out/candidates/claude_filled.zip  (+ log các mã điền được)
"""
from __future__ import annotations
import argparse, json, os, sys, zipfile, shutil
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import gazetteer, extract  # noqa: E402
from gold_vote import load_env  # noqa: E402

SYSTEM = """Bạn chuẩn hoá tên thuốc để tra RxNorm. Với mỗi tên (có thể là biệt dược Việt Nam,
viết tắt, sai chính tả, hoặc dính chữ), trả về TÊN HOẠT CHẤT gốc bằng TIẾNG ANH chuẩn RxNorm
(dạng ingredient, chữ thường, KHÔNG liều/đường dùng). Nếu là nhóm thuốc chung chung
(vd "thuốc chống đông", "kháng sinh"), tên bịa, hoặc không chắc -> trả chuỗi rỗng "".
Ví dụ: "Omez 20mg"->"omeprazole", "paracetamol"->"acetaminophen", "levafloxacin"->"levofloxacin",
"cotrimoxazol"->"sulfamethoxazole / trimethoprim", "Berlthyrox"->"levothyroxine",
"magie hydroxid"->"magnesium hydroxide", "thuốc chống đông"->"", "Vastarel"->"trimetazidine".
Chỉ in JSON object {"tên gốc": "hoạt chất tiếng Anh", ...}."""


def call(key, batch):
    user = "Chuẩn hoá:\n" + "\n".join(f"- {t}" for t in batch) + "\n\nJSON:"
    r = requests.post("https://api.openai.com/v1/chat/completions", timeout=180,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gpt-4o", "temperature": 0, "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]})
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def code_for(gaz, idx, text, english):
    """Thử map hoạt chất tiếng Anh -> RXCUI (ưu tiên khớp có dose trong text gốc)."""
    for cand in [english] + [p.strip() for p in english.replace("/", " ").split() if len(p) > 3]:
        low = cand.lower()
        if low in idx:                                    # khớp trực tiếp ingredient/brand
            codes = extract.resolve_rxnorm(gaz, text, idx[low])
            if codes:
                return codes
        if low in gaz["in"]:                              # ingredient-level RXCUI
            codes = extract.resolve_rxnorm(gaz, text, low)
            if codes:
                return codes
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="out/submitted/06_claude_rerank_30.2557.zip")
    ap.add_argument("--out", default="claude_filled")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    load_env()
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise SystemExit("Thiếu OPENAI_API_KEY")
    gaz = gazetteer.load()
    idx = extract.build_drug_index(gaz)

    z = zipfile.ZipFile(ROOT / args.src)
    data = {i: json.loads(z.read(f"output/{i}.json")) for i in range(1, 101)}
    empty = sorted({e["text"] for arr in data.values() for e in arr
                    if e["type"] == "THUỐC" and not e["candidates"]})
    print(f"{len(empty)} tên thuốc distinct rỗng mã")

    norm = {}
    for i in range(0, len(empty), 30):
        norm.update(call(key, empty[i:i + 30]))
    mapping = {}
    for t in empty:
        eng = str(norm.get(t, "")).strip()
        codes = code_for(gaz, idx, t, eng) if eng else []
        if codes:
            mapping[t] = codes
        print(f"  {t!r:42s} -> {eng!r:32s} {codes}")
    print(f"\nmap được {len(mapping)}/{len(empty)} tên")

    if args.dry:
        return
    filled = 0
    for i in range(1, 101):
        for e in data[i]:
            if e["type"] == "THUỐC" and not e["candidates"] and e["text"] in mapping:
                e["candidates"] = mapping[e["text"]]
                filled += 1
    out = ROOT / f"out/candidates/{args.out}/output"
    shutil.rmtree(out.parent, ignore_errors=True)
    out.mkdir(parents=True)
    for i in range(1, 101):
        (out / f"{i}.json").write_text(json.dumps(data[i], ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.make_archive(str(ROOT / f"out/candidates/{args.out}"), "zip", root_dir=out.parent, base_dir="output")
    print(f"-> out/candidates/{args.out}.zip | điền mã cho {filled} concept thuốc (chỉ concept rỗng)")


if __name__ == "__main__":
    main()
