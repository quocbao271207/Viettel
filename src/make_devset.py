#!/usr/bin/env python3
"""Sinh bộ khung để đội y gán nhãn dev set — điền vào là xong, không phải gõ lại.

    python3 src/make_devset.py            # -> dev/to_annotate.json (30 file)
    python3 src/make_devset.py --check    # kiểm tra dev/gold.json đã gán có hợp lệ không

Vì sao cần dev set: mọi cải tiến hiện phải đo bằng lượt nộp (5/ngày). Có 30 file gán
nhãn là đo được cục bộ bằng src/evaluate.py, lặp bao nhiêu lần cũng được.

Chọn 30/100 file theo PHÂN TẦNG ĐỘ DÀI để dev set đại diện cho cả tập, không lệch về
file ngắn (file dài có mật độ khái niệm khác hẳn).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sections  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / "dev"
N_DEV = 30

TYPES = ["TRIỆU_CHỨNG", "CHẨN_ĐOÁN", "THUỐC", "KHÔNG_PHẢI_KHÁI_NIỆM"]


def pick_files() -> list[int]:
    """Phân tầng theo độ dài: lấy đều từ ngắn -> dài."""
    sizes = sorted(((len(sections.read_raw(ROOT / "input" / f"{i}.txt")), i) for i in range(1, 101)))
    step = len(sizes) / N_DEV
    return sorted(sizes[int(k * step)][1] for k in range(N_DEV))


def build() -> None:
    DEV.mkdir(exist_ok=True)
    files = pick_files()
    out = {}
    n_lines = 0
    for i in files:
        raw = sections.read_raw(ROOT / "input" / f"{i}.txt")
        items = []
        for ln in sections.parse(raw):
            items.append({
                "line": ln.text,                 # dòng gốc, để đối chiếu
                "section": ln.section,
                "sub": ln.sub,
                "auto_skip": ln.skip,            # ta ĐANG bỏ qua dòng này — đúng hay sai?
                "concepts": [                    # <<< ĐIỀN VÀO ĐÂY
                    {"text": "", "type": "", "candidates": [], "assertions": []}
                ],
            })
            n_lines += 1
        out[str(i)] = items
    (DEV / "to_annotate.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> dev/to_annotate.json : {len(files)} file, {n_lines} dòng cần duyệt")
    print(f"   file: {files}")
    print(f"\n   Mỗi dòng điền `concepts`:")
    print(f"     • Dòng không chứa khái niệm nào  -> concepts: []")
    print(f"     • Dòng chứa 1 khái niệm          -> 1 phần tử, `text` là ĐÚNG cụm khái niệm")
    print(f"                                          (cắt bỏ phần thừa, KHÔNG copy cả dòng)")
    print(f"     • Dòng chứa nhiều khái niệm      -> nhiều phần tử")
    print(f"   `type` chọn 1 trong: {', '.join(TYPES[:3])}")
    print(f"   `assertions`: để [] nếu bình thường; nếu phủ định/tiền sử/người nhà thì ghi")
    print(f"                 mô tả TIẾNG VIỆT (vd 'phủ định') — ta chưa biết tên nhãn của BTC")


def check() -> None:
    """Chuyển dev/gold.json về format của evaluate.py và kiểm tính hợp lệ."""
    src = DEV / "gold.json"
    if not src.exists():
        raise SystemExit("Chưa có dev/gold.json. Gán nhãn dev/to_annotate.json rồi lưu thành gold.json.")
    data = json.loads(src.read_text(encoding="utf-8"))
    gold, errs, n = {}, [], 0
    for fid, items in data.items():
        raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
        ents = []
        for it in items:
            for c in it.get("concepts", []):
                if not c.get("text"):
                    continue
                n += 1
                if c["type"] not in TYPES[:3]:
                    errs.append(f"file {fid}: type không hợp lệ {c['type']!r} — {c['text'][:30]}")
                    continue
                # tìm offset: text phải xuất hiện nguyên văn trong file
                pos = raw.find(c["text"])
                if pos < 0:
                    errs.append(f"file {fid}: KHÔNG tìm thấy trong file gốc: {c['text'][:40]!r}"
                                f" (sửa lỗi gõ / đừng đổi dấu câu)")
                    continue
                ents.append({"text": c["text"], "type": c["type"],
                             "candidates": c.get("candidates", []),
                             "assertions": c.get("assertions", []),
                             "position": [pos, pos + len(c["text"])]})
        gold[fid] = sorted(ents, key=lambda e: e["position"][0])

    print(f"{len(gold)} file | {n} khái niệm đã gán | {len(errs)} lỗi")
    for e in errs[:12]:
        print("  ❌", e)
    if not errs:
        (DEV / "gold_resolved.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")
        print("-> dev/gold_resolved.json  (dùng: python3 src/evaluate.py out/baseline.json dev/gold_resolved.json)")
        w = sum(len(e["text"].split()) for v in gold.values() for e in v)
        print(f"\n   Đối chiếu với mốc đo từ leaderboard (toàn tập: 1711 concept / 4871 từ):")
        print(f"     dev set {len(gold)} file -> {n} concept, {w} từ  ({w/max(n,1):.2f} từ/concept)")
        print(f"     kỳ vọng ~2.85 từ/concept và ~{1711*len(gold)/100:.0f} concept nếu dev đại diện")


if __name__ == "__main__":
    check() if "--check" in sys.argv else build()
