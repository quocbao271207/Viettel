"""Từ điển tra cứu tĩnh cho bản nộp luật-thuần. KHÔNG gọi mạng.

Ba từ điển:
  DRUG  — tên thuốc, rút từ RXNCONSO.RRF các TTY: IN (hoạt chất), BN (biệt dược),
          PIN. Kèm sẵn RxCUI để làm candidates luôn.
  ICD   — tên bệnh tiếng Việt từ danh mục BYT, ĐÃ LOẠI chương R và Z.
          Lý do loại: chương R là "triệu chứng, dấu hiệu" — tên của nó ("khó thở",
          "đau đầu", "táo bón") trùng với mention triệu chứng. Nếu để lại thì span
          "khó thở" bị gán CHẨN_ĐOÁN trong khi GT là TRIỆU_CHỨNG, mà sai type bị
          trừ 2 lần. Chương Z là "yếu tố ảnh hưởng sức khỏe", không phải chẩn đoán.
  SYMPTOM — danh sách triệu chứng viết tay, đã đếm tần suất trên corpus
          (704 lần xuất hiện, xem worklog/03).

Vì sao dùng lookup tĩnh mà không gọi RxNav lúc inference: BTC chạy lại code trên
private test, môi trường có thể không có mạng, và NLM giới hạn 20 req/s. Mọi thứ
cần tra phải nằm trong file trên đĩa.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RXNCONSO = ROOT / "data" / "raw" / "rxnorm" / "RXNCONSO.RRF"
ICD_JSON = ROOT / "data" / "kb" / "icd10.json"

# Tên trong danh mục BYT bị cắt cụt thành từ vô nghĩa (lỗi nguồn CSV: tên nằm ở
# cột khác, cột 21 chỉ còn phần đuôi). Match những chuỗi này ra kết quả rác.
ICD_NAME_BLACKLIST = {
    "xác định",
    "sắc tố",
    "trẻ sơ sinh",
    "không xác định",
    "khác",
    "bệnh khác",
    "phần khác",
    "nguyên nhân khác",
    "vị trí khác",
    "biến chứng",
    "di chứng",
    "tổn thương",
    "chấn thương",
    "nhiễm khuẩn",
    "phẫu thuật",
    "thủ thuật",
    "điều trị",
    "theo dõi",
    "tiền sử",
    "gia đình",
    "mang thai",
    "sinh non",
    "người bệnh",
    # tên là bộ phận cơ thể, không phải bệnh (khớp vào là sai type)
    "niệu quản",
    "tim to",
    "giảm thể tích",
    "kháng vancomycin",
    "rối loạn thị giác",
}

# Tên bệnh trong danh mục bị cắt mất từ đứng đầu mà tiếng Việt luôn dùng kèm.
# "trứng cá" -> corpus luôn viết "mụn trứng cá". Nếu chỉ lấy "trứng cá" thì text
# lệch so với mention thật -> WER tính là substitution.
LEFT_EXTEND = {"trứng cá": "mụn "}

# Tên thuốc trùng với từ chỉ chất xét nghiệm / chất sinh hóa. Trong corpus chúng
# xuất hiện ở bảng xét nghiệm ("Cholesterol: 4,7 mmol/l"), không phải kê thuốc.
# Gán THUỐC ở đó là sai type -> trừ 2 lần.
DRUG_NAME_BLACKLIST = {
    "glucose",
    "glucose-6-phosphate",
    "cholesterol",
    "creatinine",
    "prothrombin",
    "fibrinogen",
    "lactate",
    "lipase",
    "guaiac",
    "albumin",
    "protein",
    "calcium",
    "caffeine",
    "urea",
    "sodium",
    "potassium",
    "chloride",
    "bilirubin",
    "insulin",
    "oxygen",
    "water",
    "alcohol",
    "ethanol",
}

# Cụm đứng ngay sau một từ triệu chứng làm nó KHÔNG còn là triệu chứng.
# "phù hợp" là tính từ, không phải phù nề. Đây là lỗi false positive nặng nhất
# đo được: 11/61 lần khớp "phù" thực ra là "phù hợp".
SYMPTOM_STOP_NEXT = {
    "phù": ("hợp",),
    "sốt": ("rét như",),
}

# Triệu chứng: đã đo tần suất thật trên 100 file input.
SYMPTOMS = [
    "đau vùng thượng vị",
    "đánh trống ngực",
    "tim đập nhanh",
    "đau mỏi vai",
    "yếu tay chân",
    "ho có đờm",
    "chướng bụng",
    "khàn tiếng",
    "vã mồ hôi",
    "ra mồ hôi",
    "khát nước",
    "tiểu nhiều",
    "tiểu buốt",
    "tiểu rắt",
    "chóng mặt",
    "buồn nôn",
    "buồn ngủ",
    "mệt mỏi",
    "tiêu chảy",
    "chán ăn",
    "sụt cân",
    "vàng da",
    "vàng mắt",
    "nổi mẩn",
    "mất ngủ",
    "hoa mắt",
    "co giật",
    "hôn mê",
    "chảy máu",
    "đau quặn",
    "khó nuốt",
    "nuốt đau",
    "đau nhức",
    "nhức đầu",
    "khó chịu",
    "lo lắng",
    "hồi hộp",
    "đau bụng",
    "đau ngực",
    "đau lưng",
    "đau khớp",
    "đau họng",
    "đau đầu",
    "khó thở",
    "khó tiêu",
    "đầy hơi",
    "rét run",
    "gai rét",
    "sốt cao",
    "sốt nhẹ",
    "ho khan",
    "táo bón",
    "run tay",
    "choáng",
    "tê bì",
    "ợ chua",
    "ợ hơi",
    "ngứa",
    "sưng",
    "ngất",
    "nôn",
    "phù",
    "sốt",
    "ho",
]


def strip_accent_lower(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower()


DRUG_CACHE = ROOT / "data" / "kb" / "rxnorm_drugs.json"


def load_drugs() -> dict[str, str]:
    """tên thuốc (lower) -> RxCUI. Ưu tiên IN > BN > PIN khi trùng tên.

    Dùng cache `data/kb/rxnorm_drugs.json` nếu có (324KB) thay cho RXNCONSO.RRF (29MB).
    Cần cache vì lúc suy luận (Colab, máy BTC dựng lại) không nên phải mang theo cả bản
    RxNorm gốc. Tạo cache: `python src/lexicon.py --dump`.
    """
    if DRUG_CACHE.exists():
        return json.loads(DRUG_CACHE.read_text(encoding="utf-8"))
    return _load_drugs_rrf()


def _load_drugs_rrf() -> dict[str, str]:
    out: dict[str, str] = {}
    tiers: dict[str, dict[str, str]] = {"IN": {}, "BN": {}, "PIN": {}}
    with RXNCONSO.open(encoding="utf-8") as fh:
        for line in fh:
            p = line.split("|")
            if p[11] != "RXNORM":
                continue
            tty = p[12]
            if tty in tiers:
                tiers[tty].setdefault(p[14].strip().lower(), p[0])
    for tty in ("PIN", "BN", "IN"):  # ghi sau thắng -> IN ưu tiên cao nhất
        out.update(tiers[tty])
    # chỉ giữ tên ASCII đủ dài; tên 3-4 ký tự ("ala", "iron") gây match rác
    keep = {}
    for name, cui in out.items():
        if len(name) < 5 or name in DRUG_NAME_BLACKLIST:
            continue
        if not re.fullmatch(r"[a-z][a-z0-9 \-']*", name):
            continue
        keep[name] = cui
    return keep


def load_icd() -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, dict]]:
    """tên bệnh VI (lower) -> list mã đã bung con. Trả cả children + entries."""
    kb = json.loads(ICD_JSON.read_text(encoding="utf-8"))
    entries, children = kb["entries"], kb["children"]

    def expand(code: str) -> list[str]:
        e = entries.get(code)
        if e is None:
            return []
        if e["has_specific"] and children.get(code):
            return sorted(children[code])
        return [code]

    names: dict[str, list[str]] = {}
    for code, e in entries.items():
        if code[0] in ("R", "Z"):  # chương triệu chứng + yếu tố ảnh hưởng
            continue
        vi = re.sub(r"\s+", " ", e["vi"]).strip().lower()
        if len(vi) < 6 or vi in ICD_NAME_BLACKLIST:
            continue
        vi = LEFT_EXTEND.get(vi, "") + vi
        names.setdefault(vi, []).extend(expand(code))
    return {k: sorted(set(v)) for k, v in names.items()}, children, entries


if __name__ == "__main__":  # pragma: no cover
    import sys

    if "--dump" in sys.argv:
        d = _load_drugs_rrf()
        DRUG_CACHE.parent.mkdir(parents=True, exist_ok=True)
        DRUG_CACHE.write_text(
            json.dumps(d, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        print(f"{DRUG_CACHE.relative_to(ROOT)}: {len(d)} thuốc")
    else:
        names, _, _ = load_icd()
        print(f"{len(load_drugs())} thuốc, {len(names)} tên bệnh")
