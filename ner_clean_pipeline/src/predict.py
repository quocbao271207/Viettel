"""Sinh 100 file output cho bản nộp thử. Luật thuần, không model, không mạng.

Mục đích của bản này KHÔNG phải điểm cao. Chỉ hai việc:
  1. Xác nhận format output được hệ thống chấm chấp nhận.
  2. Xác nhận khai thác Jaccard: để assertions rỗng thì có ăn J=1 không.
Điểm nhận được dùng làm mốc 0 để so các bản sau.

Thiết kế theo metric (PLAN.md §2):
  - text_score = mean(1-WER), WER không chặn trên -> chỉ xuất span rất chắc.
  - assertions_score: J=1 khi cả GT và pred rỗng -> để [] hết.
  - candidates_score: chia theo len(GT)+1 -> giữ 1-3 mã, không trả top-10.
  - Sai type bị trừ 2 lần -> span lưỡng lự thì BỎ, không đoán.
  - Output luôn sort theo position vì WER phụ thuộc thứ tự.

Chạy:  python3 src/predict.py           -> ghi vào submission/
       python3 src/predict.py --stats   -> in thống kê, không ghi file
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lexicon import SYMPTOM_STOP_NEXT, SYMPTOMS, load_drugs, load_icd  # noqa: E402
from sections import label_at, sections  # noqa: E402
from textnorm import normalize, to_raw_span  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
OUT_DIR = ROOT / "submission"

# ký tự có thể là phần của một từ tiếng Việt -> dùng để kiểm biên từ
WORD = r"[\wÀ-ỹ]"

# Tên xét nghiệm hay gặp trong corpus, dạng viết tắt. Chỉ nhận khi đứng ngay
# trước dấu ':' hoặc '=' và sau đó là một con số -> gần như không thể sai type.
LAB_NAMES = [
    # chỉ số định lượng và dấu hiệu sinh tồn — luôn kèm một con số
    "Bilirubin toàn phần",
    "LDL - cholesterol",
    "HDL - cholesterol",
    "Tỷ lệ prothrombin",
    "Cholesterol",
    "Triglycerid",
    "Creatinin",
    "Glucose",
    "Albumin",
    "Protein",
    "HbA1c",
    "HGB",
    "WBC",
    "PLT",
    "RBC",
    "CRP",
    "GOT",
    "GPT",
    "GGT",
    "AST",
    "ALT",
    "Ure",
    "Na+",
    "K+",
    "Cl-",
    "HC",
    "HST",
    "BC",
    "TC",
    # bổ sung sau khi đo recall = 0% trên GT tay (worklog/05)
    "Bilirubin",
    "Photpho",
    "Phospho",
    "Kali",
    "Natri",
    "Canxi",
    "Calci",
    "Lactat",
    "Glasgow",
    "Ferritin",
    "Procalcitonin",
    "Troponin",
    "NT-proBNP",
    "proBNP",
    "D-dimer",
    "Acid uric",
    "Axit uric",
    "eGFR",
    "GFR",
    "INR",
    "PT",
    "APTT",
    "NEUT%",
    "LYPH%",
    "MONO%",
    "EOS%",
    "BASO%",
    "MCV",
    "MCH",
    "MCHC",
    "HCT",
    "NEUT",
    "LYMPH",
    "SpO2",
    "SPO2",
    "PaO2",
    "PaCO2",
    "pCO2",
    "pO2",
    "HCO3",
    "pH",
    "đường huyết lúc đói",
    "đường huyết",
    "Glucose máu",
    "Ure máu",
    "Nhiệt độ",
    "Nhịp thở",
    "Nhịp tim",
    "Huyết áp tâm thu",
    "Huyết áp tâm trương",
    "Huyết áp",
    "Mạch",
    "Tần số",
    "HA",
    "Cân nặng",
    "Chiều cao",
    "BMI",
]

# Thủ thuật / chẩn đoán hình ảnh: là TÊN_XÉT_NGHIỆM nhưng KHÔNG có con số theo
# sau (đề: "Tên xét nghiệm bệnh nhân thực hiện"). Cụm phải khớp trọn, vì mở rộng
# theo số từ sẽ nuốt luôn phần kết quả ("chụp x-quang ngực cho thấy không có...").
PROCEDURES = [
    "chụp cắt lớp vi tính (ct)",
    "chụp cắt lớp vi tính",
    "chụp cộng hưởng từ",
    "chụp x-quang ngực",
    "chụp x-quang",
    "chụp xquang",
    "chụp ct sọ não",
    "chụp ct",
    "chụp mri",
    "chụp động mạch vành",
    "x-quang ngực",
    "x-quang",
    "điện tâm đồ",
    "điện não đồ",
    "siêu âm doppler tim",
    "siêu âm tim",
    "siêu âm ổ bụng",
    "siêu âm",
    "nội soi dạ dày",
    "nội soi thực quản",
    "nội soi đại tràng",
    "nội soi",
    "sinh thiết tuyến tiền liệt",
    "sinh thiết nội mạc tử cung",
    "sinh thiết",
    "cấy máu",
    "cấy nước tiểu",
    "chọc dò dịch não tủy",
    "tổng phân tích tế bào máu",
    "tổng phân tích nước tiểu",
    "công thức máu",
    "khí máu động mạch",
    "khí máu",
    "holter",
    "đo thính lực",
    "test hơi thở",
]

# Giá trị + đơn vị đi liền ngay sau tên xét nghiệm, có hoặc không có dấu ':'.
# Corpus viết cả ba kiểu: "WBC : 14.99 G/L", "photpho 8.4", "SpO2 99%".
_UNIT = (
    r"(?:mg/d[lL]|g/d[lL]|g/[lL]|mmol/[lL]|µmol/[lL]|umol/[lL]|mcmol/[lL]|nmol/[lL]"
    r"|mmHg|U/[lL]|UI/[lL]|IU/[lL]|ng/m[lL]|pg/m[lL]|µg/[lL]|mEq/[lL]"
    r"|[GT]/[lL]|K/µ[lL]|10\^\d+/[a-zA-Zµ]+|/µ[lL]|/u[lL]"
    r"|chu ?k[ìi]/phút|lần/phút|nhịp/phút|l[ầa]n/phút"
    r"|độ ?C|°C|kg|cm|%)"
)
LAB_VALUE = re.compile(
    rf"[:=]?\s*([<>≤≥]?\s?\d+(?:[.,]\d+)?(?:\s?[-–]\s?\d+(?:[.,]\d+)?)?"
    rf"(?:/\d+(?:[.,]\d+)?)?(?:\s{{0,2}}{_UNIT})?)",
)


def extract_labs(text: str) -> list[dict]:
    """TÊN_XÉT_NGHIỆM + KẾT_QUẢ_XÉT_NGHIỆM.

    Hai luật riêng vì corpus có hai nhóm khác nhau hẳn:
      1. chỉ số định lượng: tên rồi tới số, dấu ':' có thể có hoặc không.
         Xuất cả tên và giá trị.
      2. thủ thuật / chẩn đoán hình ảnh: chỉ có tên, không có số. Chỉ xuất tên.
    """
    out: list[dict] = []

    def add(a: int, b: int, typ: str) -> None:
        out.append(
            {"text": text[a:b], "position": [a, b], "type": typ,
             "assertions": [], "candidates": []}
        )

    for lab in LAB_NAMES:
        for a, b in find_all(text, lab):
            m = LAB_VALUE.match(text[b : b + 40])
            if not m:
                continue
            val = m.group(1).strip()
            # số trần 1 chữ số không có đơn vị thường là số thứ tự/liều, không
            # phải kết quả xét nghiệm -> bỏ để giữ precision
            if len(val) < 2 and not val.isdigit():
                continue
            add(a, b, "TÊN_XÉT_NGHIỆM")
            vs = b + m.start(1) + (len(m.group(1)) - len(m.group(1).lstrip()))
            add(vs, vs + len(val), "KẾT_QUẢ_XÉT_NGHIỆM")

    for proc in PROCEDURES:
        for a, b in find_all(text, proc):
            add(a, b, "TÊN_XÉT_NGHIỆM")

    return out


def find_all(text: str, needle: str, *, word_bound: bool = True) -> list[tuple[int, int]]:
    """Vị trí mọi lần xuất hiện của needle, không phân biệt hoa thường."""
    if not needle:
        return []
    pat = re.escape(needle)
    if word_bound:
        pat = rf"(?<!{WORD}){pat}(?!{WORD})"
    return [(m.start(), m.end()) for m in re.finditer(pat, text, re.IGNORECASE)]


def dedup_overlap(spans: list[dict]) -> list[dict]:
    """Giữ span dài nhất khi chồng nhau. 'đau bụng' thắng 'đau', 'sốt cao' thắng 'sốt'."""
    spans = sorted(spans, key=lambda s: (-(s["position"][1] - s["position"][0]), s["position"][0]))
    taken: list[tuple[int, int]] = []
    out: list[dict] = []
    for s in spans:
        a, b = s["position"]
        if any(a < y and x < b for x, y in taken):
            continue
        taken.append((a, b))
        out.append(s)
    return sorted(out, key=lambda s: s["position"][0])


# Đề: assertions chỉ áp cho 3 loại này. Gán cho loại khác là tự tạo lỗi.
ASSERTABLE = {"CHẨN_ĐOÁN", "THUỐC", "TRIỆU_CHỨNG"}


def assign_assertions(spans: list[dict], secs: list[tuple[int, int, set[str]]]) -> None:
    """isHistorical/isFamily theo phạm vi mục. Sửa tại chỗ.

    Đo trên GT tay 6 file: isHistorical precision 83%, recall 87% (worklog/06).
    Chưa làm isNegated ở đây vì phủ định là chuyện trong câu, không phải theo mục.
    """
    for s in spans:
        if s["type"] not in ASSERTABLE:
            continue
        labels = label_at(secs, s["position"][0])
        asserts = []
        if "history" in labels:
            asserts.append("isHistorical")
        if "family" in labels:
            asserts.append("isFamily")
        s["assertions"] = asserts


def extract_raw(raw: str, drugs: dict[str, str], icd: dict[str, list[str]]) -> list[dict]:
    """Khớp trên bản NFC nhưng xuất position theo file GỐC.

    20/100 file input viết dấu tiếng Việt ở dạng phân rã (NFD): `ỏ` là `o` +
    U+0309. Từ điển viết bằng NFC nên không bao giờ khớp -> 20 file đó chỉ ra
    9.2 entity/file so với 13.5 của các file NFC. Nhưng NFC hoá làm đổi độ dài
    chuỗi, còn BTC chấm `position` trên file gốc, nên phải map offset về.
    Xem src/textnorm.py.
    """
    norm, imap = normalize(raw)
    ents = extract(norm, drugs, icd)
    for e in ents:
        a, b = to_raw_span(imap, len(raw), *e["position"])
        e["position"] = [a, b]
        e["text"] = raw[a:b]
    return ents


def extract(text: str, drugs: dict[str, str], icd: dict[str, list[str]]) -> list[dict]:
    spans: list[dict] = []
    secs = sections(text)

    # --- THUỐC: tên trong RxNorm, mang sẵn RxCUI ---
    low = text.lower()
    for name, cui in drugs.items():
        if name not in low:
            continue
        for a, b in find_all(text, name):
            spans.append(
                {
                    "text": text[a:b],
                    "position": [a, b],
                    "type": "THUỐC",
                    "assertions": [],
                    "candidates": [cui],
                }
            )

    # --- CHẨN_ĐOÁN: tên bệnh VI khớp nguyên văn, đã bỏ chương R/Z ---
    for name, codes in icd.items():
        if name not in low:
            continue
        for a, b in find_all(text, name):
            spans.append(
                {
                    "text": text[a:b],
                    "position": [a, b],
                    "type": "CHẨN_ĐOÁN",
                    "assertions": [],
                    # giới hạn 3 mã: candidates_score chia theo len(GT)+1, GT
                    # thường 1-3, trả nhiều hơn là tự trừ điểm
                    "candidates": codes[:3],
                }
            )

    # --- TRIỆU_CHỨNG: danh sách viết tay, không có candidates (đề không yêu cầu) ---
    for sym in SYMPTOMS:
        if sym not in low:
            continue
        stops = SYMPTOM_STOP_NEXT.get(sym, ())
        for a, b in find_all(text, sym):
            tail = text[b : b + 12].lstrip().lower()
            if any(tail.startswith(s) for s in stops):
                continue
            # Corpus có lỗi template: gạch đầu dòng trong mục "Các bệnh lý mạn
            # tính" bị dính chữ "ho" ở đầu -> "- ho đái tháo đường", "- ho Rung
            # nhĩ". Trong mục đó mỗi dòng là một BỆNH, nên "ho" trần là rác.
            # Đo trên corpus: khoanh đúng 4/4 ca rác, không chạm ca thật nào.
            if sym == "ho" and "chronic" in label_at(secs, a):
                continue
            spans.append(
                {
                    "text": text[a:b],
                    "position": [a, b],
                    "type": "TRIỆU_CHỨNG",
                    "assertions": [],
                    "candidates": [],
                }
            )

    spans.extend(extract_labs(text))

    out = dedup_overlap(spans)
    assign_assertions(out, secs)
    # bất biến bắt buộc: text phải khớp đúng đoạn input tại position
    for s in out:
        a, b = s["position"]
        assert text[a:b] == s["text"], (s, text[a:b])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true", help="chỉ in thống kê, không ghi file")
    args = ap.parse_args()

    drugs = load_drugs()
    icd, _, _ = load_icd()
    print(f"lexicon: {len(drugs)} tên thuốc, {len(icd)} tên bệnh, {len(SYMPTOMS)} triệu chứng")

    if not args.stats:
        OUT_DIR.mkdir(exist_ok=True)

    by_type: Counter[str] = Counter()
    n_cand = 0
    total = 0
    for i in range(1, 101):
        raw = (INPUT_DIR / f"{i}.txt").read_text(encoding="utf-8")
        ents = extract_raw(raw, drugs, icd)
        by_type.update(e["type"] for e in ents)
        n_cand += sum(1 for e in ents if e["candidates"])
        total += len(ents)
        if not args.stats:
            (OUT_DIR / f"{i}.json").write_text(
                json.dumps(ents, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    print(f"\ntổng {total} entity trên 100 file, trung bình {total / 100:.1f}/file")
    for t, c in by_type.most_common():
        print(f"  {c:5d}  {t}")
    print(f"  {n_cand:5d}  entity có candidates ({n_cand / max(total, 1):.0%})")
    if not args.stats:
        print(f"\nđã ghi {OUT_DIR}/1.json .. 100.json")


if __name__ == "__main__":
    main()
