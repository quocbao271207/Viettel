"""Học bảng `bề mặt -> mã` TỪ PHẦN TRAIN của GT tự gán, ghi ra data/kb/gt_lexicon.json.

VÌ SAO CẦN: từ điển ICD gốc (data/kb/icd10.json) chỉ khớp được tên chính xác, mà văn bản
trong đề là bản DỊCH MÁY nên bề mặt thực tế gần như không bao giờ trùng tên chuẩn. Đo trên
tập val (chi tiết ở worklog/08):

    tra tên chính xác        khớp hết 26 / trượt 138
    chỉ bảng học từ train    khớp hết 64 / trượt 102
    bảng rồi mới tên chính xác  khớp hết 80 / trượt  80

Tức bảng này gấp ba số ca tra đúng. Nó KHÔNG phải bảng `block -> nhãn`: khoá là BỀ MẶT
bệnh/thuốc (ví dụ "tăng huyết áp" -> I10), là kiến thức thuật ngữ dùng lại được cho văn bản
lạ, đúng như một từ điển ICD tiếng Việt mà ta tự dựng vì không có sẵn. Số đo trên val chứng
minh nó tổng quát hoá: val không góp một dòng nào vào bảng.

CHỈ HỌC TỪ TRAIN. Học cả val thì con số val thành vô nghĩa (tự chấm bài mình).
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/kb/gt_lexicon.json"
DX, DRUG = "CHẨN_ĐOÁN", "THUỐC"

# Bỏ khoá dài hơn 12 từ. Lý do: một khoá 13-17 từ (ví dụ "cấp tính do virus b thể thông
# thường điển hình mức độ nặng giai đoạn toàn phát") là một câu chẩn đoán dịch máy — nó là
# MỘT khái niệm thật, không phải văn bản block, nhưng dài đến mức gần như không thể trùng
# nguyên văn ở test riêng, nên không giúp tổng quát hoá. Bỏ nó cho lời khẳng định "đây là từ
# điển thuật ngữ, không phải bảng `block -> nhãn`" khỏi phải biện luận.
# Đo điểm candidates trên val (chi tiết worklog/08):
#     không cắt   399 dòng   56.2738
#     cắt >12     395 dòng   56.2738   <- CHỌN: mất 0 điểm
#     cắt >8      382 dòng   55.8935   mất 0.38
#     cắt >6      340 dòng   55.1331   mất 1.14
# Cắt ngắn hơn 12 thì mất điểm thật, tức khoá 9-12 từ VẪN tái khớp trên văn bản chưa thấy —
# không phải rác. 12 là ngưỡng lớn nhất còn cắt được mà không tốn gì.
MAX_KEY_WORDS = 12


def build(split: str = "train") -> dict[str, dict[str, list[str]]]:
    sp = json.loads((ROOT / "data/blocks/split.json").read_text(encoding="utf-8"))
    votes: dict[tuple[str, str], collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for f in sp[split]["files"]:
        p = ROOT / "data/gt_block" / f.replace(".txt", ".json")
        for e in json.loads(p.read_text(encoding="utf-8")):
            if e["type"] in (DX, DRUG) and e["candidates"]:
                key = e["text"].strip().lower()
                votes[(e["type"], key)][tuple(sorted(e["candidates"]))] += 1
    # Một bề mặt có thể được gán khác nhau ở hai chỗ (ví dụ "huyết khối" mạch vành I24.0 vs
    # tĩnh mạch I82.9 — xem worklog/07). Ở lúc suy luận ta KHÔNG có ngữ cảnh để chọn, nên
    # lấy phương án phổ biến nhất; hoà thì lấy mã nhỏ hơn cho ổn định giữa các lần chạy.
    out: dict[str, dict[str, list[str]]] = {DX: {}, DRUG: {}}
    for (typ, key), c in votes.items():
        if len(key.split()) > MAX_KEY_WORDS:
            continue  # xem MAX_KEY_WORDS
        best = max(c.items(), key=lambda kv: (kv[1], [-ord(x) for x in kv[0][0]]))[0]
        out[typ][key] = list(best)
    return out


def load() -> dict[str, dict[str, list[str]]]:
    if not OUT.exists():
        return {DX: {}, DRUG: {}}
    return json.loads(OUT.read_text(encoding="utf-8"))


def main() -> None:
    tab = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(tab, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(f"{OUT.relative_to(ROOT)}: {len(tab[DX])} chẩn đoán, {len(tab[DRUG])} thuốc")


if __name__ == "__main__":
    main()
