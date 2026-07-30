"""Phân đoạn bệnh án thành các mục (section) theo dòng tiêu đề.

Dùng cho hai việc, nên tách riêng khỏi predict.py để model cũng dùng được:
  1. assertions: mọi khái niệm trong mục tiền sử -> isHistorical.
  2. phân loại: gạch đầu dòng trong mục "Các bệnh lý mạn tính" là CHẨN_ĐOÁN,
     không phải TRIỆU_CHỨNG (corpus có lỗi template "- ho đái tháo đường").

Tiêu đề đã đo tần suất thật trên 100 file input (xem worklog/06).
"""

from __future__ import annotations

import re
import unicodedata

# Mỗi nhóm: (nhãn mục, các mẫu tiêu đề). Khớp không phân biệt hoa thường, bỏ
# tiền tố "1. " và dấu ':' cuối dòng.
SECTION_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "history",
        (
            "tiền sử bệnh hiện tại",  # tên gây nhầm nhưng nội dung là tiền sử
            "tiền sử bệnh nội khoa",
            "tiền sử bệnh lý",
            "tiền sử bệnh",
            "tiền sử phẫu thuật / thủ thuật",
            "tiền sử phẫu thuật",
            "tiền sử dị ứng",
            "tiền sử gia đình",
            "các bệnh lý mạn tính",
            "các bệnh lý mãn tính",
            "thuốc trước khi nhập viện",
            "các sự kiện trước khi nhập viện",
            "sự kiện trước khi nhập viện",
            "tình trạng ngay trước khi nhập viện",
        ),
    ),
    (
        "chronic",  # tập con của history: mỗi gạch đầu dòng là một bệnh
        ("các bệnh lý mạn tính", "các bệnh lý mãn tính"),
    ),
    (
        "current",
        (
            "bệnh sử hiện tại",
            "triệu chứng hiện tại",
            "các triệu chứng hiện tại",
            "triệu chứng khi nhập viện",
            "đặc điểm triệu chứng",
            "thời điểm khởi phát triệu chứng",
            "lý do nhập viện",
            "diễn biến bệnh",
            "đánh giá tại bệnh viện",
            "dấu hiệu lâm sàng",
            "cận lâm sàng",
        ),
    ),
    (
        "lab",
        (
            "kết quả xét nghiệm",
            "kết quả chẩn đoán hình ảnh",
            "các phát hiện chẩn đoán khác",
            "các thủ thuật đã thực hiện",
            "các thủ thuậ khác",  # lỗi chính tả có thật trong corpus
            "các thủ thuật khác",
        ),
    ),
    (
        "family",
        ("tiền sử gia đình",),
    ),
]

_HEAD = re.compile(r"^\s*(?:\d+\s*\.\s*)?(.+?)\s*:?\s*$")


def _norm_head(line: str) -> str:
    return unicodedata.normalize("NFC", line).strip().lower()


def sections(text: str) -> list[tuple[int, int, set[str]]]:
    """Trả về [(start, end, nhãn)] phủ kín text, offset tính trên text truyền vào.

    Một mục có thể mang nhiều nhãn ("Các bệnh lý mạn tính" = history + chronic).
    Đoạn trước tiêu đề đầu tiên mang nhãn rỗng.
    """
    marks: list[tuple[int, set[str]]] = []
    pos = 0
    for line in text.split("\n"):
        stripped = _norm_head(line)
        m = _HEAD.match(stripped)
        head = m.group(1) if m else ""
        if head and len(head) <= 55:
            labels = {
                label
                for label, pats in SECTION_PATTERNS
                if any(head == p or head.startswith(p) for p in pats)
            }
            if labels:
                marks.append((pos, labels))
        pos += len(line) + 1

    out: list[tuple[int, int, set[str]]] = []
    if not marks or marks[0][0] > 0:
        out.append((0, marks[0][0] if marks else len(text), set()))
    for i, (start, labels) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out.append((start, end, labels))
    return out


def label_at(secs: list[tuple[int, int, set[str]]], pos: int) -> set[str]:
    """Nhãn mục chứa vị trí pos."""
    for start, end, labels in secs:
        if start <= pos < end:
            return labels
    return set()


def _demo() -> None:
    from collections import Counter
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    c: Counter[str] = Counter()
    cover = 0
    total = 0
    for i in range(1, 101):
        t = unicodedata.normalize("NFC", (root / "input" / f"{i}.txt").read_text(encoding="utf-8"))
        secs = sections(t)
        total += len(t)
        for start, end, labels in secs:
            if labels:
                cover += end - start
            for x in labels:
                c[x] += 1
    print(f"phủ {cover / total:.0%} ký tự corpus bằng mục có nhãn")
    for k, v in c.most_common():
        print(f"  {v:4d} đoạn  {k}")


if __name__ == "__main__":
    _demo()
