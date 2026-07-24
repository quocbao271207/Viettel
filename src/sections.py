#!/usr/bin/env python3
"""Bóc cấu trúc văn bản: section cấp 1, sub-header, và các dòng mang thực thể.

Văn bản có cấu trúc rất đều (đo trên 100 file input/):
  746 dòng "Tiền sử bệnh hiện tại" | 504 "Bệnh sử hiện tại" | 388 "Đánh giá tại bệnh viện"
  1650 dòng bullet "- ..."          | 320 dòng "Nhãn: giá trị"

Section là feature MẠNH cho assertion: medspaCy Sectionizer gán is_historical=True cho
cả section past_medical_history — đó là lý do danh sách thuốc tiền sử đều ["isHistorical"].

MỌI offset ở đây là chỉ số ký tự trên chuỗi raw đọc thô (NFC), khớp quy ước `position`
của BTC: raw[start:end] == text, end exclusive.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# Section cấp 1: "1.  Tiền sử bệnh", "2. Bệnh sử hiện tại"
SEC_RE = re.compile(r"^\s*(\d)\.\s+(.{3,60}?)\s*$")
# Sub-header có giá trị: "Lý do nhập viện: xuất huyết ..."
SUB_RE = re.compile(r"^\s*([^:\-–•*][^:]{2,55}):\s*(.*)$")
# Bullet: "- metoprolol 25mg po bid"
BUL_RE = re.compile(r"^\s*[-–•*]\s*(.*)$")

# --- Phân loại section cấp 1 -> ngữ cảnh thời gian
HISTORY_SEC = ("tiền sử bệnh", "tiền sử bệnh nội khoa", "tiền sử bệnh lý", "tiền sử bệnh nội")
PRESENT_SEC = ("tiền sử bệnh hiện tại", "bệnh sử hiện tại", "bệnh sử", "lịch sử bệnh hiện tại",
               "tiền sử bệnh bệnh hiện tại")
HOSPITAL_SEC = ("đánh giá tại bệnh viện", "khám tại bệnh viện")

# --- Sub-header -> gợi ý loại thực thể / assertion
SUB_HISTORICAL = ("thuốc trước khi nhập viện", "thuốc trước khi nhập viện lần này",
                  "bệnh lý mãn tính", "các bệnh lý mãn tính", "các bệnh mãn tính",
                  "bệnh mãn tính", "bệnh mạn tính", "tiền sử phẫu thuật / thủ thuật",
                  "các yếu tố nguy cơ liên quan", "các đợt tương tự trước đây",
                  "các sự kiện trước khi nhập viện", "sự kiện trước khi nhập viện",
                  "trước khi nhập viện", "các diễn biến  trước khi nhập viện")
# Sub-header KHÔNG mang khái niệm được gán nhãn (thủ thuật/xét nghiệm/hình ảnh).
# Metric chỉ nhắc "bệnh, thuốc và triệu chứng" => trích ở đây là mất điểm kép
# (WER insertion + concept thừa). Sẽ kiểm chứng lại bằng probe.
SUB_SKIP = ("tiền sử phẫu thuật / thủ thuật", "lịch sử phẫu thuật / thủ thuật",
            "các thủ thuật đã thực hiện", "các thủ thuật thực hiện", "thủ thuật thực hiện",
            "các thủ thuật", "kết quả chẩn đoán hình ảnh", "kết quả chụp ảnh",
            "kết quả chụp ảnh / tạo ảnh", "kết quả xét nghiệm", "kết quả phòng thí nghiệm",
            "cận lâm sàng", "siêu âm tim", "nhiệt độ",
            # Các mục chứa THUỘC TÍNH của triệu chứng, không phải bản thân khái niệm.
            # Metric chỉ nhắc "bệnh, thuốc và triệu chứng" nên mốc thời gian / mức độ /
            # vị trí giải phẫu nhiều khả năng không được gán nhãn. 468 dòng chỉ riêng
            # "thời điểm khởi phát" — trích nhầm là Insertion thẳng vào WER.
            "thời điểm khởi phát triệu chứng", "thời điểm khởi phát",
            "mức độ nghiêm trọng", "vị trí", "tần suất", "hoàn cảnh khởi phát",
            "các yếu tố làm nặng", "yếu tố làm nặng", "các yếu tố làm giảm")


# Sub-header đứng riêng dòng, không có dấu hai chấm. Khớp bằng tiền tố nên bắt được
# cả biến thể do dịch máy ("Các sự kiện trước khi nhập viện" / "Sự kiện trước khi...").
BARE_SUB_PREFIXES = (
    "thuốc trước khi nhập viện", "triệu chứng hiện tại", "các triệu chứng hiện tại",
    "bệnh lý mãn tính", "các bệnh lý mãn tính", "các bệnh mãn tính", "bệnh mãn tính",
    "bệnh mạn tính", "các bệnh mạn tính", "các yếu tố nguy cơ", "yếu tố nguy cơ",
    "tiền sử phẫu thuật", "lịch sử phẫu thuật", "các thủ thuật", "thủ thuật",
    "các phát hiện chẩn đoán", "các kết quả chẩn đoán", "kết quả chẩn đoán hình ảnh",
    "kết quả xét nghiệm", "kết quả khám", "kết quả phòng thí nghiệm", "cận lâm sàng",
    "các sự kiện trước khi nhập viện", "sự kiện trước khi nhập viện",
    "các diễn biến", "diễn biến", "các đợt tương tự", "đặc điểm triệu chứng",
    "lý do nhập viện", "thời điểm khởi phát", "tình trạng ngay trước khi nhập viện",
    "mức độ nghiêm trọng", "vị trí", "tần suất", "hoàn cảnh khởi phát", "các yếu tố làm",
    "dấu hiệu lâm sàng", "điều trị", "chẩn đoán", "tiền sử",
)


def is_bare_subheader(text: str) -> bool:
    t = text.strip().lower()
    if len(t) > 60 or any(ch.isdigit() for ch in t):
        return False
    return any(t.startswith(p) for p in BARE_SUB_PREFIXES)


@dataclass
class Line:
    start: int          # offset ký tự của phần NỘI DUNG (đã bỏ bullet/nhãn)
    end: int
    text: str           # raw[start:end]
    section: str        # section cấp 1, lowercase
    sub: str            # sub-header gần nhất, lowercase ("" nếu không có)
    kind: str           # 'bullet' | 'value' | 'plain'

    @property
    def is_historical_ctx(self) -> bool:
        return self.section in HISTORY_SEC or self.sub in SUB_HISTORICAL

    @property
    def skip(self) -> bool:
        return self.sub in SUB_SKIP


def read_raw(path: str | Path) -> str:
    """Đọc đúng như BTC giao: position là chỉ số codepoint trên chuỗi RAW này.

    Data vòng 1-turn2 (21/07) có ~20/100 file ở dạng Unicode PHÂN RÃ (decomposed):
    NFC gộp base+dấu tổ hợp làm ĐỔI độ dài -> nếu normalize thì offset lệch so với gold
    (gold đánh trên file raw như được giao). Vì vậy KHÔNG normalize toàn văn: giữ raw để
    offset khớp gold. Chỉ normalize an toàn khi độ dài không đổi (80 file NFC thuần -> raw≡NFC).
    Tên thuốc là ASCII nên matching không bị ảnh hưởng; matching tiếng Việt ở 20 file phân rã
    xử lý riêng ở tầng trên nếu cần (TODO), không đụng tới offset.
    """
    raw = Path(path).read_text(encoding="utf-8")
    nfc = unicodedata.normalize("NFC", raw)
    return nfc if len(nfc) == len(raw) else raw


def _add(out: list[Line], line_start: int, body: str, off_in_body: int, content: str,
         section: str, sub: str, kind: str) -> None:
    """Thêm 1 dòng nội dung, cắt khoảng trắng đuôi và giữ offset tuyệt đối chính xác."""
    trimmed = content.rstrip()
    if not trimmed:
        return
    start = line_start + off_in_body
    out.append(Line(start, start + len(trimmed), trimmed, section, sub, kind))


def parse(raw: str) -> list[Line]:
    """Trả về các dòng mang nội dung, kèm offset tuyệt đối trên `raw`."""
    out: list[Line] = []
    section = sub = ""
    pos = 0
    for line in raw.splitlines(keepends=True):
        line_start = pos
        pos += len(line)
        body = line.rstrip("\n")
        if not body.strip():
            continue

        m = SEC_RE.match(body)
        if m:
            section, sub = m.group(2).strip().lower(), ""
            continue

        m = BUL_RE.match(body)
        if m:
            _add(out, line_start, body, m.start(1), m.group(1), section, sub, "bullet")
            continue

        m = SUB_RE.match(body)
        if m:
            sub = m.group(1).strip().lower()
            _add(out, line_start, body, m.start(2), m.group(2), section, sub, "value")
            continue

        m = re.match(r"^\s*(\S.*?)\s*$", body)
        if m:
            # Sub-header có thể đứng riêng một dòng, KHÔNG có dấu hai chấm.
            # VD 1.txt: "    Thuốc trước khi nhập viện" rồi mới tới các bullet.
            if is_bare_subheader(m.group(1)):
                sub = m.group(1).strip().lower()
                continue
            _add(out, line_start, body, m.start(1), m.group(1), section, sub, "plain")
    return out


def selftest() -> None:
    root = Path(__file__).resolve().parent.parent
    ok = tot = 0
    for f in sorted((root / "input").glob("*.txt")):
        raw = read_raw(f)
        for ln in parse(raw):
            tot += 1
            ok += raw[ln.start : ln.end] == ln.text
    print(f"Offset khớp raw[start:end] == text : {ok}/{tot}  ({ok/tot:.2%})")
    assert ok == tot, "CÓ OFFSET SAI -> phải sửa trước khi chạy tiếp"

    raw = read_raw(root / "input" / "1.txt")
    lines = parse(raw)
    print(f"\nVí dụ 1.txt — {len(lines)} dòng nội dung:")
    for ln in lines[:8]:
        flag = "HIST" if ln.is_historical_ctx else "    "
        skip = "SKIP" if ln.skip else "    "
        print(f"  [{ln.start:4d},{ln.end:4d}] {flag} {skip} {ln.kind:6s} | {ln.text[:52]}")


if __name__ == "__main__":
    selftest()
