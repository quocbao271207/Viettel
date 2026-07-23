#!/usr/bin/env python3
"""Dựng gazetteer RxNorm + ICD-10 OFFLINE từ dữ liệu đã tải về data/.

Luật cấm gọi API ngoài lúc chạy => mọi thứ phải tra cứu cục bộ. Nguồn:
  data/rx_scd.json  17.552 SCD  (RxNav /REST/allconcepts?tty=SCD)
  data/rx_in.json   14.648 IN
  data/rx_SBD.json   9.696 SBD  -> suy ra brand->hoạt chất qua phần "[Brand]" trong tên
  data/icd10_raw/icd10cm_codes_2026.txt  74.719 mã (CMS, bản chính thức 2026)

Quy tắc 2 tầng (verify qua RxNav trên 11/11 mã của ví dụ đề):
  có liều + dạng bào chế  -> SCD   (10/11 mã)
  thiếu liều/dạng         -> IN    (nystatin=7597)

    python3 src/gazetteer.py --build     # dựng + cache vào data/gaz.json
    python3 src/gazetteer.py --selftest  # kiểm chứng lại 11 mã trong ví dụ đề
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "gaz.json"

# Liều: "10 MG", "0.5 MG", "325 MG", "103.4 MG/ML", "8.6 MG"
STRENGTH = re.compile(
    r"(\d+(?:\.\d+)?)\s*(MG/ML|MCG/ML|MG/HR|MG|MCG|ML|G|UNT|%|MEQ|MMOL)\b", re.I
)
# Tiền tố giải phóng kéo dài: "24 HR", "12 HR"
HR_PREFIX = re.compile(r"^\d+\s*HR\s+", re.I)
# Tiền tố thể tích: "2.67 ML furosemide ...", "0.05 ML aflibercept ..."
VOL_PREFIX = re.compile(r"^\d+(?:\.\d+)?\s*ML\s+", re.I)
BRACKET = re.compile(r"\s*\[([^\]]+)\]\s*$")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def parse_scd(name: str) -> tuple[str, str, str] | None:
    """'amlodipine 10 MG Oral Tablet' -> ('amlodipine', '10 mg', 'oral tablet')

    Cắt tại lần xuất hiện CUỐI của liều: trước là hoạt chất, sau là dạng bào chế.
    Xử lý được cả '24 HR metoprolol succinate 50 MG Extended Release Oral Tablet'.
    """
    matches = list(STRENGTH.finditer(name))
    if not matches:
        return None
    last = matches[-1]
    ing = name[: last.start()].strip()
    form = name[last.end() :].strip()
    if not ing or not form:
        return None
    ing = HR_PREFIX.sub("", ing).strip(" ,")
    ing = VOL_PREFIX.sub("", ing).strip(" ,")
    strength = f"{last.group(1)} {last.group(2)}"
    return norm(ing), norm(strength), norm(form)


def ingredients_only(ing_part: str) -> str:
    """'acetaminophen 325 MG / oxycodone hydrochloride' -> 'acetaminophen / oxycodone hydrochloride'

    Với thuốc đa hoạt chất, phần trước liều cuối vẫn còn lẫn liều của các hoạt chất
    khác. Bỏ hết liều còn sót để lấy danh sách hoạt chất thuần.
    """
    s = STRENGTH.sub("", ing_part)
    s = re.sub(r"\s*/\s*", " / ", s)
    return norm(re.sub(r"\s+", " ", s).strip(" ,/"))


def load_concepts(fname: str) -> list[dict]:
    path = DATA / fname
    if not path.exists():
        raise SystemExit(f"Thiếu {path}. Xem docstring để biết cách tải.")
    return json.loads(path.read_text())["minConceptGroup"]["minConcept"]


def build() -> dict:
    scd = load_concepts("rx_scd.json")
    ins = load_concepts("rx_in.json")
    sbd = load_concepts("rx_SBD.json")

    # --- SCD: (hoạt chất, liều, dạng) -> rxcui ; và (hoạt chất, liều) -> [rxcui]
    scd_full: dict[str, str] = {}
    scd_by_ing_strength: dict[str, list[str]] = {}
    scd_by_ing: dict[str, list[str]] = {}
    n_parsed = 0
    for c in scd:
        p = parse_scd(c["name"])
        if not p:
            continue
        n_parsed += 1
        ing, strength, form = p
        scd_full.setdefault(f"{ing}|{strength}|{form}", c["rxcui"])
        scd_by_ing_strength.setdefault(f"{ing}|{strength}", []).append(c["rxcui"])
        scd_by_ing.setdefault(ing, []).append(c["rxcui"])

    # --- IN: tên hoạt chất -> rxcui
    in_idx = {norm(c["name"]): c["rxcui"] for c in ins}

    # --- Brand -> hoạt chất, suy từ tên SBD: "X 10 MG Oral Tablet [Norvasc]"
    brand2ing: dict[str, str] = {}
    for c in sbd:
        m = BRACKET.search(c["name"])
        if not m:
            continue
        brand = norm(m.group(1))
        p = parse_scd(BRACKET.sub("", c["name"]))
        if p:
            brand2ing.setdefault(brand, ingredients_only(p[0]))

    # --- ICD-10-CM: mô tả tiếng Anh -> mã (dùng cho đối chiếu / verify)
    icd_path = DATA / "icd10_raw" / "icd10cm_codes_2026.txt"
    icd_en2code: dict[str, str] = {}
    icd_code2en: dict[str, str] = {}
    for ln in icd_path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        code, desc = ln[:8].strip(), ln[8:].strip()
        icd_en2code.setdefault(norm(desc), code)
        icd_code2en[code] = desc

    # --- Lọc "dispensable": token hoạt chất từng xuất hiện trong tên SCD nào đó.
    # Cần thiết vì RxNorm đặt tên SCD theo PIN ("metoprolol succinate"), nên
    # scd_by_ing["metoprolol"] = 0 dù metoprolol rõ ràng là thuốc. Lọc theo token
    # bắt được cả hai. Ngược lại creatinine/guaiac/troponin không xuất hiện trong
    # SCD nào -> loại được, chúng là chất xét nghiệm chứ không phải thuốc.
    scd_ing_words: set[str] = set()
    for key in scd_by_ing:
        for part in key.split(" / "):
            toks = part.split()
            if toks:
                scd_ing_words.add(toks[0])
            scd_ing_words.add(part)

    gaz = {
        "scd_full": scd_full,
        "scd_by_ing_strength": scd_by_ing_strength,
        "scd_by_ing": scd_by_ing,
        "scd_ing_words": sorted(scd_ing_words),
        "in": in_idx,
        "brand2ing": brand2ing,
        "icd_en2code": icd_en2code,
        "icd_code2en": icd_code2en,
    }
    CACHE.write_text(json.dumps(gaz, ensure_ascii=False))
    print(f"SCD parse được   : {n_parsed}/{len(scd)}  ({n_parsed/len(scd):.1%})")
    print(f"  scd_full       : {len(scd_full):,} khoá (hoạt chất|liều|dạng)")
    print(f"  scd_by_ing     : {len(scd_by_ing):,} hoạt chất")
    print(f"IN               : {len(in_idx):,}")
    print(f"brand -> hoạt chất: {len(brand2ing):,}")
    print(f"ICD-10-CM        : {len(icd_en2code):,} mô tả -> mã")
    print(f"-> cache: {CACHE.relative_to(ROOT)} ({CACHE.stat().st_size/1e6:.1f} MB)")
    return gaz


def load() -> dict:
    if not CACHE.exists():
        return build()
    gaz = json.loads(CACHE.read_text())
    gaz["scd_ing_words"] = set(gaz["scd_ing_words"])
    return gaz


# Gốc muối/ester trong tên PIN. Tên SCD và brand map dùng PIN ("warfarin sodium")
# còn index IN dùng tên gốc ("warfarin") -> phải bóc để tra được.
SALTS = ("sodium", "hydrochloride", "hcl", "calcium", "potassium", "sulfate", "sulphate",
         "tartrate", "bitartrate", "succinate", "maleate", "besylate", "mesylate",
         "citrate", "acetate", "phosphate", "fumarate", "hydrobromide", "bromide",
         "nitrate", "chloride", "gluconate", "carbonate", "lactate", "oxalate",
         "pamoate", "palmitate", "propionate", "valerate", "dipropionate", "mofetil")


def strip_salt(name: str) -> str:
    """'warfarin sodium' -> 'warfarin'. Bóc dần các đuôi gốc muối."""
    toks = name.split()
    while len(toks) > 1 and toks[-1] in SALTS:
        toks.pop()
    return " ".join(toks)


def lookup_in(gaz: dict, ingredient: str) -> str | None:
    """Tra IN, tự bóc gốc muối và thử từng hoạt chất nếu là thuốc phối hợp."""
    for cand in (ingredient, strip_salt(ingredient)):
        hit = gaz["in"].get(cand)
        if hit:
            return hit
    if " / " in ingredient:  # thuốc phối hợp -> lấy hoạt chất đầu
        return lookup_in(gaz, ingredient.split(" / ")[0])
    return None


def is_dispensable(gaz: dict, ingredient: str) -> bool:
    """Có phải chất thực sự được bào chế thành thuốc không (vs chất xét nghiệm)."""
    base = strip_salt(ingredient.split(" / ")[0])
    words = gaz["scd_ing_words"]
    return base in words or (base.split()[0] in words if base.split() else False)


def selftest(gaz: dict) -> None:
    """Kiểm chứng ngược 11 mã trong ví dụ đề: gazetteer có tái tạo được không?"""
    cases = [
        ("amlodipine", "10 mg", "oral tablet", "308135"),
        ("aspirin", "81 mg", "oral tablet", "243670"),
        ("metoprolol succinate", "50 mg", "extended release oral tablet", "866436"),
        ("acetaminophen", "325 mg", "oral tablet", "313782"),
        ("pravastatin sodium", "40 mg", "oral tablet", "904475"),
        ("docusate sodium", "100 mg", "oral tablet", "1099279"),
        ("clonazepam", "0.5 mg", "oral tablet", "197527"),
        ("clonazepam", "1 mg", "oral tablet", "197528"),
    ]
    print("\n=== SELFTEST: SCD 3 tầng (hoạt chất|liều|dạng) ===")
    ok = 0
    for ing, st, form, want in cases:
        got = gaz["scd_full"].get(f"{ing}|{st}|{form}")
        flag = "✅" if got == want else "❌"
        ok += got == want
        print(f"  {flag} {ing:22s} {st:8s} {form:30s} -> {got}  (đúng: {want})")
    print(f"  => {ok}/{len(cases)}")

    print("\n=== SELFTEST: fallback IN (không có liều) ===")
    for ing, want in [("nystatin", "7597")]:
        got = gaz["in"].get(ing)
        print(f"  {'✅' if got == want else '❌'} {ing:22s} -> {got}  (đúng: {want})")

    print("\n=== SELFTEST: brand -> hoạt chất (biệt dược có thật trong input/) ===")
    for brand in ["tylenol", "lasix", "coumadin", "gleevec", "prograf", "percocet",
                  "vicodin", "bactrim", "suboxone", "cellcept", "plavix", "ranexa",
                  "dilaudid", "norvasc"]:
        ing = gaz["brand2ing"].get(brand)
        print(f"  {'✅' if ing else '❌'} {brand:12s} -> {ing}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(load())
    else:
        selftest(build())
