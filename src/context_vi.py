#!/usr/bin/env python3
"""ConText (medspaCy) port sang tiếng Việt -> sinh `assertions`.

Tập nhãn suy ra từ medspaCy `DEFAULT_ATTRIBUTES`, camelCase hoá:
    is_negated -> isNegated | is_historical -> isHistorical | is_family -> isFamily
    is_hypothetical -> isHypothetical | is_uncertain -> isUncertain
Đề chính thức ghi "(phủ định, người nhà, tiền sử)" — khớp đúng 3/5 trục.
`[]` = present/affirmed (KHÔNG có isPresent).

⚠️ BẪY LỚN NHẤT: cue phủ định nằm TRONG tên thực thể.
Đo trên input/: "không" xuất hiện 249 lần, nhưng rất nhiều lần là một phần của
preferred term ICD-10:
    "xuất huyết nội sọ KHÔNG DO CHẤN THƯƠNG, KHÔNG ĐẶC HIỆU"  (I62.9)  -> KHÔNG phủ định
    "tiểu tiện KHÔNG tự chủ"                                          -> KHÔNG phủ định
    "bệnh gút KHÔNG ĐẶC HIỆU"                                (M10.9)  -> KHÔNG phủ định
NegEx ngây thơ sẽ gắn isNegated hàng loạt => J=0 cho từng cái (vì gt là []).
Cách chặn: (1) bỏ qua cue nằm trong span thực thể; (2) blacklist các cụm cố định
là một phần thuật ngữ. Đúng thứ tự medspaCy làm: khoá span TRƯỚC, chạy ConText SAU.

⚠️ Chưa hiệu chỉnh trên dev set — ngưỡng/cue phải đo bằng src/evaluate.py trước khi tin.
"""
from __future__ import annotations

import re

# --- Cue theo trục, kèm số lần đo được trên 100 file input/
NEGATION = [  # ~150 lần
    "không có", "không ghi nhận", "không thấy", "không còn", "phủ nhận", "âm tính",
    "loại trừ", "chưa ghi nhận", "chưa có", "không bị", "không đau", "không sốt",
]
HISTORICAL = [  # ~460 lần — trục đáng đầu tư nhất
    "tiền sử", "trước đây", "trước khi nhập viện", "đã từng", "nhiều năm",
    "năm trước", "tháng trước", "ngày trước", "cách đây", "từ nhỏ",
    "mãn tính", "mạn tính", "trong quá khứ", "đã được chẩn đoán",
]
UNCERTAIN = [  # ~36 lần
    "nghi ngờ", "có thể", "khả năng", "theo dõi", "chưa loại trừ", "nghĩ nhiều đến",
    "có lẽ", "chẩn đoán phân biệt", "?",
]
FAMILY = [  # ~8 lần trong input/ — hiếm, đừng tốn nhiều công
    "gia đình", "mẹ", "bố", "cha", "anh trai", "chị gái", "em trai", "em gái",
    "con trai", "con gái", "người thân", "ông", "bà", "tiền sử gia đình",
    "chồng", "vợ", "anh em", "họ hàng",
]
HYPOTHETICAL = [
    "nếu", "trong trường hợp", "khi cần", "dặn dò", "hướng dẫn", "dị ứng",
]

# --- Cụm KHÔNG PHẢI phủ định dù chứa "không": chúng là một phần thuật ngữ ICD-10.
#     Đây là danh sách chặn tối thiểu; mở rộng khi có dev set.
NOT_NEGATION = [
    "không đặc hiệu",        # "unspecified" — đuôi ICD-10 phổ biến nhất
    "không xác định",        # "unspecified" / "not specified"
    "không do chấn thương",  # "nontraumatic"
    "không tự chủ",          # "incontinence"
    "không biến chứng",      # "without complication"
    "không rõ nguyên nhân",  # "of unknown cause"
    "không hồi phục",        # "non-rebreather" (NRB) — dịch sai của BTC
    "không ổn định",         # "unstable"
    "không dung nạp",        # "intolerance"
]

ATTR = {
    "isNegated": NEGATION,
    "isHistorical": HISTORICAL,
    "isUncertain": UNCERTAIN,
    "isFamily": FAMILY,
    "isHypothetical": HYPOTHETICAL,
}

# Ranh giới mệnh đề: cue không vượt qua các dấu này (giống ConText termination)
TERMINATOR = re.compile(r"[.;]|\bnhưng\b|\btuy nhiên\b|\bmặc dù\b")


def _cue_re(cue: str) -> re.Pattern:
    """Cue phải khớp theo RANH GIỚI TỪ.

    Bẫy tiếng Việt: khớp chuỗi con làm "kh(ông)" dính cue "ông" (người nhà), nên
    "Bệnh nhân không có sốt" bị gắn nhầm isFamily. Tương tự "(bà)n chân"/"bà",
    "(mẹ)"/"mẹo". Lookaround trên \\w (Unicode) chặn được vì ô/n/g đều là word char.
    """
    body = re.escape(cue)
    left = r"(?<!\w)" if cue[:1].isalnum() else ""
    right = r"(?!\w)" if cue[-1:].isalnum() else ""
    return re.compile(f"{left}{body}{right}")


_CUE_CACHE: dict[str, re.Pattern] = {}


def _cue_positions(text_lower: str, cues: list[str]) -> list[tuple[int, int]]:
    hits = []
    for c in cues:
        pat = _CUE_CACHE.setdefault(c, _cue_re(c))
        for m in pat.finditer(text_lower):
            hits.append((m.start(), m.end()))
    return hits


def _inside_entity(pos: int, ent_start: int, ent_end: int) -> bool:
    return ent_start <= pos < ent_end


def _in_not_negation(text_lower: str, pos: int) -> bool:
    """Cue phủ định này có thực ra là một phần cụm thuật ngữ không?"""
    for phrase in NOT_NEGATION:
        for m in re.finditer(re.escape(phrase), text_lower):
            if m.start() <= pos < m.end():
                return True
    return False


def assertions(sentence: str, ent_start: int, ent_end: int,
               section_historical: bool = False) -> list[str]:
    """Sinh cờ ConText cho 1 thực thể trong 1 câu.

    sentence            câu chứa thực thể
    ent_start/ent_end   offset của thực thể TRONG `sentence`
    section_historical  section cha có phải past-medical-history không
                        (medspaCy Sectionizer gán is_historical=True cho cả section)
    """
    low = sentence.lower()
    out: list[str] = []

    if section_historical:
        out.append("isHistorical")

    for attr, cues in ATTR.items():
        if attr in out:
            continue
        for cstart, cend in _cue_positions(low, cues):
            # (1) cue nằm TRONG thực thể -> nó là một phần tên, không phải ngữ cảnh
            if _inside_entity(cstart, ent_start, ent_end):
                continue
            # (2) cue phủ định thực ra là đuôi thuật ngữ ICD-10
            if attr == "isNegated" and _in_not_negation(low, cstart):
                continue
            # (3) cue phải đứng TRƯỚC thực thể và không vượt ranh giới mệnh đề
            if cend > ent_start:
                continue
            span = sentence[cend:ent_start]
            if TERMINATOR.search(span) or len(span) > 60:
                continue
            out.append(attr)
            break
    return out


def selftest() -> None:
    cases = [
        # (câu, thực thể, section_historical, kỳ vọng)
        ("Bệnh nhân không có sốt", "sốt", False, ["isNegated"]),
        ("Tiền sử tăng huyết áp", "tăng huyết áp", False, ["isHistorical"]),
        ("Nghi ngờ viêm phổi", "viêm phổi", False, ["isUncertain"]),
        ("Gia đình có tiền sử ung thư vú", "ung thư vú", False, ["isHistorical", "isFamily"]),
        # --- BẪY: "không" nằm TRONG tên bệnh -> phải trả []
        ("Lý do nhập viện: xuất huyết nội sọ không do chấn thương, không đặc hiệu",
         "xuất huyết nội sọ không do chấn thương, không đặc hiệu", False, []),
        ("- tiểu tiện không tự chủ", "tiểu tiện không tự chủ", False, []),
        ("- bệnh gút không đặc hiệu", "bệnh gút không đặc hiệu", False, []),
        # --- section prior
        ("metoprolol 25mg po bid", "metoprolol 25mg po bid", True, ["isHistorical"]),
    ]
    ok = 0
    print("=== ConText tiếng Việt — selftest ===")
    for sent, ent, hist, want in cases:
        s = sent.index(ent)
        got = assertions(sent, s, s + len(ent), hist)
        good = sorted(got) == sorted(want)
        ok += good
        print(f"  {'✅' if good else '❌'} {sent[:52]:54s}\n      -> {got}  (kỳ vọng {want})")
    print(f"\n>>> {ok}/{len(cases)}")


if __name__ == "__main__":
    selftest()
