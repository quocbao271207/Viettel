#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPEC ĐÓNG BĂNG — nguồn sự thật duy nhất cho mọi lần sinh data.

Đọc kèm `dev/SPEC_V2.md` (bản văn xuôi + bằng chứng từng luật).
MỌI luật ở đây đều gắn với một lượt nộp đã trả giá. Đừng nới lỏng nếu không có
số liệu leaderboard mới bác bỏ.
"""
from __future__ import annotations

import re
import unicodedata

# ------------------------------------------------------------------ hằng số spec

TYPES = ("THUỐC", "CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM")
ASSERTIONS = ("isNegated", "isHistorical", "isFamily")
CODED_TYPES = ("CHẨN_ĐOÁN", "THUỐC")   # chỉ 2 type này được chấm J_cand

CONTEXT_LEN = 15                        # độ dài before/after LLM phải trả

# Ngưỡng hoà vốn h* = J/(1+J) — xem SPEC_V2 §6.
J_ASSERT = 0.483759
J_CAND = 0.236121
BREAKEVEN_ASSERT = J_ASSERT / (1 + J_ASSERT)   # 0.326
BREAKEVEN_CAND = J_CAND / (1 + J_CAND)         # 0.191

# ------------------------------------------------------------------ danh sách cấm
# §2a — bản 16 = −0.61 điểm, WER TĂNG. Từ PHÂN LOẠI, không phải tên xét nghiệm.
BANNED_EXACT = {
    "xét nghiệm", "các xét nghiệm", "chẩn đoán hình ảnh", "cận lâm sàng",
    "thăm khám", "kiểm tra", "xét nghiệm máu", "chụp chiếu",
    # dấu hiệu sinh tồn đo tại giường
    "huyết áp", "ha", "mạch", "nhiệt độ", "nhịp thở", "nhịp tim",
    "spo2", "cân nặng", "chiều cao", "bmi",
}
# giá trị đi kèm sinh tồn: "130/76 mmHg", "93 l/p", "36.3 độ C", "70 kg"
# CỐ Ý không chặn "%": phân suất tống máu (EF 55%) và nhiều kết quả cận lâm sàng dùng %,
# đó là KẾT_QUẢ_XÉT_NGHIỆM hợp lệ chứ không phải sinh tồn.
BANNED_VALUE_RE = re.compile(
    r"^\s*\d{1,3}([.,]\d+)?\s*(/\s*\d{1,3})?\s*"
    r"(mmhg|l/p|lần/phút|lan/phut|độ\s*c|do\s*c|kg|cm)\s*$",
    re.IGNORECASE,
)
# §2b — bản 15 = −0.075. Cụm 1 âm tiết đứng trơ (chỉ chặn concept MỚI, không đụng bản 14).
ONE_SYLLABLE = {"đau", "yếu", "phù", "ho", "sốt", "nôn", "mệt", "sưng", "ngứa", "rát", "tê"}

# §2c — mồi nhử theo đề
MASKED_RE = re.compile(r"\*{3,}")


def malformed_boundary(text: str) -> str | None:
    """Ranh giới span hỏng — khác với dấu câu HỢP LỆ nằm trong tên.

    Hợp lệ và PHẢI giữ: `chụp cắt lớp vi tính (CT)` · `Cl-` · `HCO3-` · `(+)` · `(-)`.
    Hỏng: thừa khoảng trắng, cụt giữa chừng (ngoặc lệch), dính dấu câu kết câu.
    """
    if text != text.strip():
        return "thừa khoảng trắng ở biên"
    if text[:1] in ".,;:" or text[-1:] in ".,;:":
        return "dính dấu câu kết câu ở biên"
    if text.count("(") != text.count(")") or text.count("[") != text.count("]"):
        return "ngoặc lệch — span bị cắt cụt"
    return None


def is_banned(text: str, type_: str) -> str | None:
    """Cấm CỨNG — đúng cho cả trích mới lẫn đãi bỏ data cũ. Trả lý do, hoặc None."""
    t = unicodedata.normalize("NFC", text)
    low = t.strip().lower()
    if not t.strip():
        return "rỗng"
    if MASKED_RE.search(t):
        return "tên bị che ***** (mồi nhử, §2c)"
    if low in BANNED_EXACT:
        return "từ phân loại / dấu hiệu sinh tồn (§2a, bản 16 −0.61)"
    if BANNED_VALUE_RE.match(t):
        return "giá trị sinh tồn (§2a, bản 16 −0.61)"
    return malformed_boundary(t)


def is_weak(text: str, type_: str) -> str | None:
    """Cấm MỀM — chặn khi trích MỚI (bản 15 chứng minh thêm vào là lỗ), nhưng đãi bỏ khỏi
    data cũ là một CANH BẠC RIÊNG: các cụm này đã nằm trong bản 11-14 và những bản đó ăn điểm.
    Vì vậy nó là luật đãi bỏ tách riêng (`--rule onesyl`), không nằm trong `--rule spec`.
    """
    if unicodedata.normalize("NFC", text).strip().lower() in ONE_SYLLABLE:
        return "cụm 1 âm tiết đứng trơ (§2b, bản 15 −0.075)"
    return None


# ------------------------------------------------------------------ mã

def dot(code: str) -> str:
    """ICD-10-CM phải CÓ DẤU CHẤM khi nộp: D550 -> D55.0. J_cand gấp đôi (7.11 -> 14.80).

    RxNorm là số thuần -> trả nguyên. Mã đã có chấm -> trả nguyên.
    """
    c = (code or "").strip().upper()
    if not c or c.isdigit() or "." in c:
        return c
    return c[:3] + "." + c[3:] if len(c) > 3 else c


def undot(code: str) -> str:
    """Ngược lại — để tra `gaz.json` (lưu mã KHÔNG chấm)."""
    return (code or "").strip().upper().replace(".", "")


# ------------------------------------------------------------------ prompt cho LLM
# Đây là prompt DUY NHẤT được dùng để sinh data. Sửa ở đây, không sửa rải rác.

SYSTEM = f"""Bạn là chuyên gia gán nhãn NER y khoa tiếng Việt cho một cuộc thi.
Nhiệm vụ: trích MỌI lần nhắc tới khái niệm y tế trong đoạn văn được giao.

NĂM LOẠI (đóng — không có loại thứ 6):
- THUỐC: tên thuốc/hoạt chất, kèm liều+đường dùng nếu liền mạch ("metoprolol 25mg po bid").
- CHẨN_ĐOÁN: tên bệnh/chẩn đoán ("viêm phổi", "thiếu men G6PD").
- TRIỆU_CHỨNG: triệu chứng/dấu hiệu ("khó thở", "vàng da").
- TÊN_XÉT_NGHIỆM: tên một xét nghiệm CẬN LÂM SÀNG CỤ THỂ ("WBC", "creatinin",
  "Troponin T", "chụp x-quang ngực", "nội soi").
- KẾT_QUẢ_XÉT_NGHIỆM: giá trị + đơn vị ("14,43", "316 mg/dl", "âm tính").

TUYỆT ĐỐI KHÔNG TRÍCH (đã kiểm chứng là gold KHÔNG có, trích vào là MẤT ĐIỂM):
1. Từ PHÂN LOẠI thay vì tên một xét nghiệm: "xét nghiệm", "chẩn đoán hình ảnh",
   "cận lâm sàng", "thăm khám", "kiểm tra".
2. DẤU HIỆU SINH TỒN đo tại giường và giá trị của chúng: "Huyết áp", "HA", "Mạch",
   "Nhiệt độ", "Nhịp thở", "SpO2", "cân nặng", "130/76 mmHg", "93 l/p", "36.3 độ C".
   (TÊN_XÉT_NGHIỆM chỉ gồm xét nghiệm cận lâm sàng, KHÔNG gồm chỉ số đo tại giường.)
3. Cụm 1 âm tiết đứng trơ không bổ ngữ: "đau", "yếu", "phù", "ho" đơn lẻ.
4. Tên người / bác sĩ / tổ chức, kể cả khi trùng tên bệnh.
5. Tên thuốc bị che bằng dấu sao ("*****") — đó là mồi nhử, KHÔNG phải khái niệm.
6. Mốc thời gian, mức độ, vị trí giải phẫu đứng riêng ("3 ngày nay", "dữ dội", "hạ sườn phải").

QUY TẮC:
1. "text" là chuỗi NGUYÊN VĂN copy từ đoạn — đúng từng ký tự hoa/thường/dấu.
   KHÔNG sửa chính tả, KHÔNG chuẩn hoá, KHÔNG cắt bớt.
2. Trích MỖI LẦN NHẮC riêng — cùng một bệnh nhắc 3 lần = 3 mục riêng biệt.
3. "before" = ĐÚNG {CONTEXT_LEN} ký tự ngay TRƯỚC span (nguyên văn, kể cả khoảng trắng
   và xuống dòng). "after" = ĐÚNG {CONTEXT_LEN} ký tự ngay SAU span. Ít hơn nếu chạm biên file.
   Hai trường này dùng để ĐỊNH VỊ — sai là mục bị loại bỏ.
4. "assertions" = LIST 0 đến 3 nhãn, CHỈ được dùng: isNegated, isHistorical, isFamily.
   Đang có / khẳng định -> [] (rỗng, đây là mặc định của phần lớn concept).
   Nhiều nhãn cùng lúc được: "bố có tiền sử hen" -> ["isFamily","isHistorical"].
   KHÔNG có isUncertain, KHÔNG có isHypothetical.
   Trong bài GIÁO DỤC y khoa ("bệnh X là gì", "triệu chứng của X"), concept nhắc chung
   về bệnh KHÔNG phải isHistorical và KHÔNG phải isNegated -> [].
5. KHÔNG xuất mã ICD/RxNorm. KHÔNG đếm vị trí ký tự. KHÔNG bịa thêm gì ngoài văn bản.

Chỉ in JSON array, không giải thích, không markdown fence. Mỗi phần tử đúng 5 khoá:
{{"text": "...", "type": "...", "assertions": [...], "before": "...", "after": "..."}}"""

FEWSHOT_IN = (
    "metoprolol 25mg po bid (thuốc trước nhập viện). Bệnh nhân không sốt cao. "
    "Tiền sử viêm dạ dày. Mẹ bị đái tháo đường. WBC: 14,43; glucose 316 mg/dl. "
    "Huyết áp 130/76 mmHg."
)
FEWSHOT_OUT = """[
 {"text":"metoprolol 25mg po bid","type":"THUỐC","assertions":["isHistorical"],"before":"","after":" (thuốc trước "},
 {"text":"sốt cao","type":"TRIỆU_CHỨNG","assertions":["isNegated"],"before":"nh nhân không ","after":". Tiền sử viêm"},
 {"text":"viêm dạ dày","type":"CHẨN_ĐOÁN","assertions":["isHistorical"],"before":"o. Tiền sử ","after":". Mẹ bị đái th"},
 {"text":"đái tháo đường","type":"CHẨN_ĐOÁN","assertions":["isFamily"],"before":"dày. Mẹ bị ","after":". WBC: 14,43; "},
 {"text":"WBC","type":"TÊN_XÉT_NGHIỆM","assertions":[],"before":"tháo đường. ","after":": 14,43; gluco"},
 {"text":"14,43","type":"KẾT_QUẢ_XÉT_NGHIỆM","assertions":[],"before":"đường. WBC: ","after":"; glucose 316 "},
 {"text":"glucose","type":"TÊN_XÉT_NGHIỆM","assertions":[],"before":"WBC: 14,43; ","after":" 316 mg/dl. Hu"},
 {"text":"316 mg/dl","type":"KẾT_QUẢ_XÉT_NGHIỆM","assertions":[],"before":"14,43; glucose ","after":". Huyết áp 130"}
]"""
# Lưu ý few-shot: "Huyết áp 130/76 mmHg" CỐ Ý không xuất hiện trong output — dạy model bỏ sinh tồn.
