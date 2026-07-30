"""Oracle chấm điểm offline — dựng đúng theo công thức đề, không còn đoán.

CÔNG THỨC (nguyên văn đề, phần "Metric đánh giá"):

    final = 0.3·text_score + 0.3·assertions_score + 0.4·candidates_score

    text_score       = Σ_i (1 − WER(i)) / len(test)
    assertions_score = Σ_i J_assertions(i) / len(test)
    candidates_score = Σ_i J_candidates(i)·w(i) / Σ_i w(i),  w(i) = Σ_k (len(gt(k)) + 1)

    i = 1 sample (1 file). k = 1 khái niệm trong sample i.
    J_X(i) = 1 nếu gt_X và pred_X đều rỗng
           = 0 nếu gt_X rỗng mà pred_X khác rỗng
           = |gt ∩ pred| / |gt ∪ pred| các trường hợp còn lại

Chú ý ba điều công thức này nói mà bản trước của file này làm sai:

1. `text_score` và `assertions_score` là trung bình **theo file** — mỗi file 1 phiếu
   bằng nhau, file ít entity cũng nặng như file nhiều entity.
2. `candidates_score` là trung bình **có trọng số**: w(i) = tổng (số candidate GT của
   mỗi khái niệm + 1). File nhiều khái niệm / nhiều candidate thì nặng hơn.
   Số +1 để khái niệm không có candidate vẫn có trọng số.
3. J tính **theo từng khái niệm k rồi trung bình trong file**, không phải gộp phẳng cả
   file. Bằng chứng: bản nộp #1 để assertions rỗng 100%; nếu gộp phẳng thì J mỗi file
   chỉ nhận 0 hoặc 1 → trung bình 100 file phải là số nguyên. BTC trả 18.5774.

CÁCH GHÉP KHÁI NIỆM — đề chốt trong phần "Lưu ý":

    "đoán đúng phần text của khái niệm nhưng sai loại (VD: đoán CHẨN_ĐOÁN nhưng
     ground truth là TRIỆU_CHỨNG), khái niệm sẽ bị tính 2 lần (do tạo ra 1 khái niệm
     mới so với ground truth) và mỗi lần đều được tính 0 điểm với cả 3 loại metric."

Suy ra:
  - `type` nằm trong khoá ghép. Sai type = không ghép được = 2 khái niệm lẻ.
  - Khái niệm lẻ (chỉ GT hoặc chỉ pred) tính 0 cho **cả 3** metric, kể cả WER. Nên
    mẫu số của J là |hợp khái niệm|, và WER cũng tính theo khái niệm rồi lấy trung
    bình (không thể "cho 0 điểm 1 khái niệm" nếu WER chạy trên chuỗi nối).
  - Đề nói "đoán đúng phần **text**" → khoá ghép dựa trên text, không phải position.

Còn 1 ẩn số duy nhất: trong cùng type, ghép theo text khớp tuyệt đối hay theo span
chồng lấn (rồi WER đo phần lệch chữ). Hai biến thể đó vẫn để cạnh nhau ở dưới.

HỆ QUẢ QUAN TRỌNG NHẤT cho hướng làm bài: J_assertions cho 1 điểm khi GT rỗng và
pred rỗng. ~78% khái niệm trong GT tay có assertions rỗng. Nên điểm assertions gần
như bị quyết định bởi **recall của NER**, không phải bởi logic assertion. Cùng lý do
với candidates. Recall NER kéo cả 3 metric — xem worklog/05.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent

# Số BTC trả về cho bản nộp #1 (submission_v1) — mốc hiệu chuẩn duy nhất đang có.
CAL = {"wer": 82.9421, "assertions": 18.5774, "candidates": 13.9879, "final": 16.2858}

Entity = dict[str, Any]
Record = list[Entity]


# ------------------------------------------------------------------ tiện ích

def tokenize(s: str) -> list[str]:
    """Tách từ để tính WER. Tiếng Việt tách theo khoảng trắng; số thập phân có dấu
    phẩy (14,43) giữ nguyên làm 1 token."""
    return re.findall(r"\w+(?:[.,]\w+)*", s.lower())


def edit_distance(a: list[str], b: list[str]) -> int:
    """Levenshtein mức từ. a = tham chiếu (GT), b = giả thuyết (pred)."""
    if not a:
        return len(b)
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def wer_pair(gt_text: str, pred_text: str) -> float:
    """WER của 1 khái niệm đã ghép được."""
    g, p = tokenize(gt_text), tokenize(pred_text)
    if not g:
        return 0.0 if not p else 1.0
    return min(1.0, edit_distance(g, p) / len(g))


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    return len(a & b) / len(u) if u else 1.0


def field_set(e: Entity, field: str) -> set[str]:
    v = e.get(field) or []
    if isinstance(v, dict):  # phòng trường hợp assertions là dict
        return {k for k, val in v.items() if val}
    return {str(x) for x in v}


def span(e: Entity) -> tuple[int, int]:
    p = e.get("position") or [0, 0]
    if isinstance(p, list) and len(p) >= 2:
        return int(p[0]), int(p[1])
    return 0, 0


# ------------------------------------------------------- ghép khái niệm k
# Trả về (pairs, n_gt_only, n_pred_only). pairs = [(entity_gt, entity_pred)].
# Mọi biến thể đều bắt buộc trùng `type` — đề đã chốt điều này.

Pairing = Callable[[Record, Record], tuple[list[tuple[Entity, Entity]], int, int]]


def pair_by_text(gt: Record, pred: Record) -> tuple[list, int, int]:
    """Ghép theo khoá (type, text đã hạ chữ thường). Trùng khoá thì gộp làm 1 khái
    niệm — đề nói "khái niệm", không nói "lần xuất hiện"."""
    def key(e):
        return (e.get("type"), (e.get("text") or "").strip().lower())

    G, P = {}, {}
    for e in gt:
        G.setdefault(key(e), e)
    for e in pred:
        P.setdefault(key(e), e)
    pairs = [(G[k], P[k]) for k in G if k in P]
    return pairs, len(set(G) - set(P)), len(set(P) - set(G))


def pair_by_span(gt: Record, pred: Record) -> tuple[list, int, int]:
    """Ghép theo khoá (type, position) khớp tuyệt đối."""
    def key(e):
        return (e.get("type"), span(e))

    G = {key(e): e for e in gt}
    P = {key(e): e for e in pred}
    pairs = [(G[k], P[k]) for k in G if k in P]
    return pairs, len(set(G) - set(P)), len(set(P) - set(G))


def pair_by_overlap(gt: Record, pred: Record) -> tuple[list, int, int]:
    """Ghép 1-1 theo số ký tự chồng lấn, tham lam từ cặp chồng nhiều nhất, cùng type.
    Khi span lệch chút, cặp vẫn ghép được và WER đo phần chữ lệch."""
    cands = []
    for i, g in enumerate(gt):
        ga, gb = span(g)
        for j, p in enumerate(pred):
            if g.get("type") != p.get("type"):
                continue
            pa, pb = span(p)
            ov = min(gb, pb) - max(ga, pa)
            if ov > 0:
                cands.append((-ov, i, j))
    cands.sort()
    ug: set[int] = set()
    up: set[int] = set()
    pairs = []
    for _, i, j in cands:
        if i in ug or j in up:
            continue
        ug.add(i)
        up.add(j)
        pairs.append((gt[i], pred[j]))
    return pairs, len(gt) - len(ug), len(pred) - len(up)


PAIRINGS: dict[str, Pairing] = {
    "text": pair_by_text,
    "span": pair_by_span,
    "overlap": pair_by_overlap,
}


# ------------------------------------------------------------- chấm 1 file

def score_record(gt: Record, pred: Record, pairing: Pairing) -> tuple[float, float, float, float]:
    """Trả về (WER(i), J_assertions(i), J_candidates(i), w(i)) cho 1 file."""
    pairs, n_gt_only, n_pred_only = pairing(gt, pred)
    n = len(pairs) + n_gt_only + n_pred_only  # |hợp khái niệm|

    # w(i) = Σ_k (len(gt candidates của k) + 1), lấy trên khái niệm GT
    w = sum(len(field_set(e, "candidates")) + 1 for e in gt)

    if n == 0:
        return 0.0, 1.0, 1.0, float(w)

    wer = sum(wer_pair(g.get("text", ""), p.get("text", "")) for g, p in pairs)
    wer += n_gt_only + n_pred_only  # khái niệm lẻ: WER = 1
    ja = sum(jaccard(field_set(g, "assertions"), field_set(p, "assertions")) for g, p in pairs)
    jc = sum(jaccard(field_set(g, "candidates"), field_set(p, "candidates")) for g, p in pairs)
    return wer / n, ja / n, jc / n, float(w)


def score_dirs(
    gt_dir: Path,
    pred_dir: Path,
    pairing: Pairing,
    only: set[str] | None = None,
) -> dict[str, float]:
    """`only` = tập tên file ('7.json') muốn chấm; None = chấm mọi file có GT.
    Dùng để chấm riêng tập val (xem src/split.py)."""
    G = {f.name: json.loads(f.read_text(encoding="utf-8")) for f in sorted(gt_dir.glob("*.json"))}
    P = {f.name: json.loads(f.read_text(encoding="utf-8")) for f in sorted(pred_dir.glob("*.json"))}
    names = sorted(G) if only is None else sorted(n for n in G if n in only)  # chỉ file có GT
    if not names:
        raise SystemExit(f"không có file GT nào trong {gt_dir}")

    wers, jas, jcs, ws = [], [], [], []
    for name in names:
        wer, ja, jc, w = score_record(G[name], P.get(name, []), pairing)
        wers.append(wer)
        jas.append(ja)
        jcs.append(jc)
        ws.append(w)

    n = len(names)
    text_score = 100 * sum(1 - x for x in wers) / n
    assertions_score = 100 * sum(jas) / n
    tw = sum(ws)
    candidates_score = 100 * sum(j * w for j, w in zip(jcs, ws)) / tw if tw else 100.0
    return {
        "n_files": n,
        "wer": 100 - text_score,
        "text_score": text_score,
        "assertions": assertions_score,
        "candidates": candidates_score,
        "final": 0.3 * text_score + 0.3 * assertions_score + 0.4 * candidates_score,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default="data/gt")
    ap.add_argument("--pred", default="submission")
    ap.add_argument("--pairing", default=None, choices=sorted(PAIRINGS), help="mặc định: in cả 3")
    ap.add_argument("--per-file", action="store_true")
    ap.add_argument("--split", default=None, choices=("train", "val"),
                    help="chỉ chấm phần này của data/blocks/split.json")
    args = ap.parse_args()

    gt_dir, pred_dir = ROOT / args.gt, ROOT / args.pred
    keys = [args.pairing] if args.pairing else sorted(PAIRINGS)

    only = None
    if args.split:
        sp = json.loads((ROOT / "data/blocks/split.json").read_text(encoding="utf-8"))
        only = {f.replace(".txt", ".json") for f in sp[args.split]["files"]}

    print(f"GT: {args.gt}   pred: {args.pred}"
          + (f"   split: {args.split} ({len(only)} file)" if only else "") + "\n")
    print(f"  {'ghép':9s} {'WER':>8s} {'text':>8s} {'assert':>8s} {'cand':>8s} {'final':>8s}")
    for k in keys:
        r = score_dirs(gt_dir, pred_dir, PAIRINGS[k], only)
        print(f"  {k:9s} {r['wer']:8.4f} {r['text_score']:8.4f} "
              f"{r['assertions']:8.4f} {r['candidates']:8.4f} {r['final']:8.4f}")
    print(f"\n  chấm trên {r['n_files']} file")
    print(f"  mốc BTC (bản nộp #1, 100 file): WER {CAL['wer']} | assert {CAL['assertions']} "
          f"| cand {CAL['candidates']} | final {CAL['final']}")

    if args.per_file:
        pairing = PAIRINGS[keys[0]]
        print(f"\n  theo từng file (ghép {keys[0]}):")
        for f in sorted(gt_dir.glob("*.json")):
            g = json.loads(f.read_text(encoding="utf-8"))
            pf = pred_dir / f.name
            p = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else []
            wer, ja, jc, w = score_record(g, p, pairing)
            print(f"    {f.stem:>4s}  GT {len(g):3d}  pred {len(p):3d}  "
                  f"WER {100*wer:6.2f}  assert {100*ja:6.2f}  cand {100*jc:6.2f}  w {w:4.0f}")


if __name__ == "__main__":
    main()
