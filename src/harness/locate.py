#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ĐỊNH VỊ TẤT ĐỊNH — biến (text, before, after) do LLM trả thành offset chính xác.

Nguyên tắc (SPEC_V2 §4): **thà LOẠI còn hơn ĐOÁN.**
Pipeline cũ chỉ có `before` nên phải dò fuzzy toàn cục để "cứu" → chính là nguồn của
45 ca gán nhầm số file ở bản 12. Ở đây: không dò sang file khác, không khớp hoa/thường,
không nới ranh giới. Ca mơ hồ bị vứt và ghi lý do.

Nới lỏng DUY NHẤT, và nó vẫn là khớp CHÍNH XÁC: 20/100 file ở dạng Unicode phân rã (NFD),
cho phép so khớp sau khi chuẩn hoá NFC hai phía. Offset luôn trả trên raw gốc.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass
class Hit:
    start: int
    end: int
    mode: str          # "exact" | "nfc"


@dataclass
class Result:
    ok: bool
    start: int = -1
    end: int = -1
    mode: str = ""
    reason: str = ""   # lý do loại, khi ok=False
    n_raw: int = 0     # số lần text xuất hiện trước khi lọc ngữ cảnh


def _find_all_exact(raw: str, text: str) -> list[Hit]:
    out, i = [], raw.find(text)
    while i >= 0:
        out.append(Hit(i, i + len(text), "exact"))
        i = raw.find(text, i + 1)
    return out


def _find_all_nfc(raw: str, text: str) -> list[Hit]:
    """Khớp trên NFC nhưng trả offset trên RAW.

    Chỉ chạy khi khớp nguyên văn thất bại. Dò từng vị trí bắt đầu và so NFC hai phía —
    O(n·m) nhưng file chỉ ~2000 ký tự nên không đáng kể, đổi lại là đúng tuyệt đối.
    """
    tgt = unicodedata.normalize("NFC", text)
    if not tgt:
        return []
    out: list[Hit] = []
    n = len(raw)
    # độ dài raw của cùng một chuỗi NFC có thể dài hơn (mỗi dấu tổ hợp = 1 ký tự thừa)
    lo, hi = len(tgt), len(tgt) * 2 + 4
    for s in range(n):
        for ln in range(lo, min(hi, n - s) + 1):
            if unicodedata.normalize("NFC", raw[s:s + ln]) == tgt:
                out.append(Hit(s, s + ln, "nfc"))
                break          # lấy khớp NGẮN NHẤT tại mỗi vị trí bắt đầu
    return out


def _ctx_ok(raw: str, hit: Hit, before: str, after: str) -> bool:
    """before phải là ĐUÔI của phần trước span; after phải là ĐẦU của phần sau span."""
    if before:
        b = raw[max(0, hit.start - len(before)):hit.start]
        if unicodedata.normalize("NFC", b) != unicodedata.normalize("NFC", before):
            return False
    if after:
        a = raw[hit.end:hit.end + len(after)]
        if unicodedata.normalize("NFC", a) != unicodedata.normalize("NFC", after):
            return False
    return True


def locate(raw: str, text: str, before: str = "", after: str = "") -> Result:
    """Trả Result(ok=True) chỉ khi định vị được DUY NHẤT một span."""
    if not text:
        return Result(False, reason="text rỗng")

    hits = _find_all_exact(raw, text)
    if not hits:
        hits = _find_all_nfc(raw, text)
    if not hits:
        return Result(False, reason="text không xuất hiện nguyên văn trong file")

    n_raw = len(hits)
    if n_raw == 1:
        h = hits[0]
        return Result(True, h.start, h.end, h.mode, n_raw=n_raw)

    # >1 lần: bắt buộc dùng ngữ cảnh
    keep = [h for h in hits if _ctx_ok(raw, h, before, after)]
    if len(keep) == 1:
        h = keep[0]
        return Result(True, h.start, h.end, h.mode, n_raw=n_raw)
    if not keep:
        # thử nới: chỉ before, rồi chỉ after (LLM hay đếm lệch 1-2 ký tự ở một bên)
        for b, a in ((before, ""), ("", after)):
            if not (b or a):
                continue
            k = [h for h in hits if _ctx_ok(raw, h, b, a)]
            if len(k) == 1:
                return Result(True, k[0].start, k[0].end, k[0].mode, n_raw=n_raw)
        return Result(False, reason=f"ngữ cảnh không khớp lần xuất hiện nào (có {n_raw} lần)",
                      n_raw=n_raw)
    return Result(False, reason=f"ngữ cảnh còn mơ hồ ({len(keep)}/{n_raw} lần khớp)", n_raw=n_raw)


def locate_group(raw: str, text: str, before: str, after: str,
                 n_requested: int) -> tuple[list[tuple[int, int, str]], str]:
    """Định vị một NHÓM: voter báo cùng (text, before, after) đúng `n_requested` lần.

    Cần thiết vì văn bản có đoạn lặp y hệt — khi đó 15 ký tự ngữ cảnh hai bên KHÔNG
    phân biệt được các lần xuất hiện, và đó không phải lỗi của voter. Ví dụ file 10 có
    "ngoại tâm thu nhĩ" xuất hiện 2 lần trong 2 câu giống hệt nhau.

    Luật: sau khi lọc ngữ cảnh còn H vị trí *không phân biệt được*, gán theo THỨ TỰ
    TÀI LIỆU, tối đa `n_requested` vị trí. Đây vẫn là tất định (cùng input -> cùng output),
    và không bịa ra text: mọi vị trí trả về đều khớp nguyên văn trong đúng file đó.
    """
    hits = _find_all_exact(raw, text) or _find_all_nfc(raw, text)
    if not hits:
        return [], "text không xuất hiện nguyên văn trong file"
    keep = [h for h in hits if _ctx_ok(raw, h, before, after)] if len(hits) > 1 else hits
    if not keep:
        # Tầng dung sai — VẪN là khớp nguyên văn, chỉ thu ngắn cửa sổ. LLM hay đếm lệch
        # vài ký tự ở một đầu; phần SÁT span thì gần như luôn đúng.
        for b, a in ((before, ""), ("", after), (before[-6:], after[:6]), (before[-4:], "")):
            if not (b or a):
                continue
            keep = [h for h in hits if _ctx_ok(raw, h, b, a)]
            if keep:
                break
    if not keep:
        return [], f"ngữ cảnh không khớp lần xuất hiện nào (có {len(hits)} lần)"
    keep.sort(key=lambda h: h.start)
    mode = "exact" if len(keep) == 1 else "ordinal"
    return [(h.start, h.end, h.mode) for h in keep[:n_requested]], mode


def locate_all_occurrences(raw: str, text: str) -> list[tuple[int, int]]:
    """Mọi lần xuất hiện nguyên văn — dùng cho cơ chế NHÂN BẢN (cách thêm DUY NHẤT từng thắng).

    Bản 14 (+1.26 điểm) đến từ đây: lấy text ĐÃ được gold xác nhận, tìm mọi lần nhắc khác.
    """
    hits = _find_all_exact(raw, text) or _find_all_nfc(raw, text)
    return [(h.start, h.end) for h in hits]
