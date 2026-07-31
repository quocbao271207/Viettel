"""Dựng dataset token-classification (BIO) từ GT tay + split chống rò rỉ.

Đầu ra: data/ner/{train,val}.jsonl. Mỗi dòng 1 cửa sổ:

    {"file": "7.txt", "off": 0, "text": "...", "spans": [[s, e, "TRIỆU_CHỨNG"], ...]}

`s`/`e` là offset TƯƠNG ĐỐI trong `text`. Chưa tokenize ở đây — tokenizer chạy lúc
train (cần transformers, máy này không có). Việc của file này là cắt cửa sổ + gắn span,
để bước train chỉ còn việc gọi tokenizer với `return_offsets_mapping=True`.

Hai điều bắt buộc phải đúng, nếu sai thì mọi thứ sau đó vô nghĩa:

1. **KHÔNG normalize Unicode.** Offset trong data/gt_block ghi theo văn bản GỐC THÔ.
   20/100 file là NFD; NFC ghép combining sequence lại làm chuỗi NGẮN ĐI -> mọi offset
   sau lần ghép đầu tiên lệch hết (đã mắc bẫy này một lần, xem worklog/07).
2. **Cắt cửa sổ không được xé span.** Cắt theo ranh giới dòng, và nếu một span vắt qua
   ranh giới thì đẩy ranh giới ra sau span đó.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data/ner"

# Cửa sổ tính theo KÝ TỰ, không theo token. Ước lượng: XLM-R ~2.5 ký tự/token với
# tiếng Việt có dấu, nên 1200 ký tự ~ 480 token, còn dư chỗ trong giới hạn 512.
WIN = 1200
STRIDE = 900  # chồng 300 ký tự để entity gần ranh giới vẫn xuất hiện nguyên ở 1 cửa sổ


def is_noise_training_span(text: str, typ: str) -> bool:
    """Không đưa nhiễu chắc chắn vào train.

    `data/gt_block` vẫn giữ nguyên nhãn tay để audit, nhưng các thuốc bị mask
    (`*****`) không có bề mặt y học để model học và đã làm NER sinh rất nhiều FP
    trên leaderboard. Loại cả span thuốc 1-2 ký tự do lỗi tokenizer/annotation.
    """
    surface = text.strip()
    if typ != "THUỐC":
        return False
    if "*" in surface:
        return True
    if len(surface) <= 2:
        return True
    if not re.search(r"[A-Za-zÀ-ỹ]", surface):
        return True
    return False


def load_file(
    fname: str, input_dir: Path, gt_dir: Path
) -> tuple[str, list[tuple[int, int, str, list[str], list[str]]]]:
    raw = (input_dir / fname).read_text(encoding="utf-8")  # KHÔNG normalize
    ents = json.loads((gt_dir / fname.replace(".txt", ".json")).read_text(encoding="utf-8"))
    out = []
    for e in ents:
        s, t = e["position"]
        if raw[s:t] != e["text"]:
            raise SystemExit(f"{fname}: offset lệch tại {e['position']} {e['text']!r}")
        if is_noise_training_span(e["text"], e["type"]):
            continue
        out.append((s, t, e["type"], e["assertions"], e["candidates"]))
    out.sort()
    for (s1, t1, *_), (s2, *_) in zip(out, out[1:]):
        if s2 < t1:
            raise SystemExit(f"{fname}: span lồng nhau {s1}-{t1} và {s2}-...")
    return raw, out


def cut_windows(raw: str, spans: list) -> list[tuple[int, int]]:
    """Ranh giới cửa sổ: ưu tiên xuống dòng, và không bao giờ xé một span."""
    bounds: list[tuple[int, int]] = []
    pos = 0
    n = len(raw)
    while pos < n:
        end = min(pos + WIN, n)
        if end < n:
            nl = raw.rfind("\n", pos + WIN // 2, end)
            if nl > pos:
                end = nl + 1
        # đẩy ranh giới ra sau span nào bị xé
        for s, t, *_ in spans:
            if s < end < t:
                end = t
        bounds.append((pos, end))
        if end >= n:
            break
        # Điểm bắt đầu cửa sổ sau KHÔNG ĐƯỢC vượt quá `end`. Thiếu ràng buộc này thì
        # khi `end` bị lùi về ranh giới dòng (nhỏ hơn pos+WIN) mà pos+STRIDE lại lớn
        # hơn `end`, ta để hở một khoảng không cửa sổ nào phủ -> mất entity. Đã mắc:
        # lần đầu mất 13 entity, ví dụ 35.txt hở khoảng 743..900.
        nxt = min(pos + STRIDE, end)
        # ranh giới bắt đầu cửa sổ sau cũng không được nằm giữa span
        for s, t, *_ in spans:
            if s < nxt < t:
                nxt = s
        pos = max(nxt, pos + 1)
    return bounds


def build(files: list[str], input_dir: Path, gt_dir: Path) -> list[dict]:
    rows = []
    for fname in files:
        raw, spans = load_file(fname, input_dir, gt_dir)
        for a, b in cut_windows(raw, spans):
            inside = [
                [s - a, t - a, typ, asrt, cand]
                for s, t, typ, asrt, cand in spans
                if s >= a and t <= b
            ]
            rows.append({"file": fname, "off": a, "text": raw[a:b], "spans": inside})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default=str(ROOT / "data/gt_block"))
    ap.add_argument("--input", default=str(ROOT / "input"))
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    gt_dir = Path(args.gt)
    input_dir = Path(args.input)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sp = json.loads((ROOT / "data/blocks/split.json").read_text(encoding="utf-8"))
    total_ent = collections.Counter()
    for part in ("train", "val"):
        rows = build(sp[part]["files"], input_dir, gt_dir)
        p = out / f"{part}.jsonl"
        with p.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        nent = sum(len(r["spans"]) for r in rows)
        c = collections.Counter(s[2] for r in rows for s in r["spans"])
        total_ent[part] = nent
        print(f"{part:5s} {len(sp[part]['files']):3d} file  {len(rows):4d} cửa sổ  "
              f"{nent:4d} span  (ký tự {sum(len(r['text']) for r in rows)})")
        for k, v in c.most_common():
            print(f"        {v:5d}  {k}")

    # kiểm mất mát: mọi entity GT phải xuất hiện ở >=1 cửa sổ
    for part in ("train", "val"):
        want = 0
        for f in sp[part]["files"]:
            _, spans = load_file(f, input_dir, gt_dir)
            want += len(spans)
        rows = [json.loads(l) for l in (out / f"{part}.jsonl").read_text("utf-8").splitlines()]
        got = {(r["file"], r["off"] + s[0], r["off"] + s[1]) for r in rows for s in r["spans"]}
        print(f"{part}: GT sau lọc {want} entity, cửa sổ phủ {len(got)} entity duy nhất, "
              f"thiếu {want - len(got)}")


if __name__ == "__main__":
    main()
