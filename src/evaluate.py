#!/usr/bin/env python3
"""Cài đặt lại metric của BTC để đo CỤC BỘ trên dev set (khỏi đốt lượt nộp).

    python3 src/evaluate.py out/baseline.json dev/gold.json

⚠️ ĐÂY LÀ BẢN TÁI DỰNG, KHÔNG PHẢI CODE GỐC CỦA BTC. Đề chỉ mô tả metric bằng lời,
không nói rõ 2 điều quyết định:
  (a) concept dự đoán ghép với concept GT theo tiêu chí nào?
  (b) text_score tính WER trên chuỗi nối hay theo từng concept?
Vì vậy các giả thiết đó để thành THAM SỐ. Dùng probe P2/P4/P6 (src/probes.py) để
chốt, rồi khoá lại đúng cấu hình.

Bằng chứng cho mô hình hiện tại: đề ghi "đoán đúng text nhưng sai loại -> tính 2 lần,
mỗi lần 0đ với cả 3 metric" => concept không ghép được thì bị 0, và khoá ghép có
chứa `type`. Đặt Jc = Jaccard(tập concept pred, tập concept gt) thì:
    final ≈ 0.3·T + 0.3·(Jc · acc_assertion) + 0.4·(Jc · acc_candidate)
Thay Jc=0.60 -> 55.2 điểm, khớp gần đúng top leaderboard thật (54.66).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ------------------------------------------------------------------ WER


def wer(ref: list[str], hyp: list[str]) -> float:
    """(S+D+I)/N — Levenshtein trên mức TỪ. KHÔNG chặn trên: hyp dài hơn ref thì
    WER > 1 => (1-WER) âm. Đây chính là lý do phải ưu tiên precision."""
    n, m = len(ref), len(hyp)
    if n == 0:
        return 0.0 if m == 0 else float("inf")
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cur[j] = min(
                prev[j] + 1,                              # deletion
                cur[j - 1] + 1,                           # insertion
                prev[j - 1] + (ref[i - 1] != hyp[j - 1]),  # substitution
            )
        prev = cur
    return prev[m] / n


def jaccard(gt: list | None, pred: list | None) -> float:
    """Theo đúng đề: gt rỗng & pred rỗng -> 1 ; gt rỗng & pred khác rỗng -> 0."""
    g, p = set(gt or []), set(pred or [])
    if not g and not p:
        return 1.0
    if not g:
        return 0.0
    if not p:
        return 0.0
    return len(g & p) / len(g | p)


# ------------------------------------------------------------ ghép concept


def key_of(e: dict, mode: str) -> tuple:
    t = e["text"].strip().lower()
    if mode == "text_type":
        return (t, e["type"])
    if mode == "pos_type":
        return (tuple(e["position"]), e["type"])
    if mode == "text_pos_type":
        return (t, tuple(e["position"]), e["type"])
    raise ValueError(mode)


def align(gold: list[dict], pred: list[dict], mode: str):
    """Trả (các cặp ghép được, số GT bị bỏ sót, số dự đoán thừa).

    Dùng multiset: cùng (text,type) xuất hiện 2 lần trong GT thì phải dự đoán 2 lần.
    Cần thiết vì cùng một thực thể lặp ở nhiều section (VD 15.txt: "xuất huyết nội
    sọ..." xuất hiện ở cả "Lý do nhập viện" và "Các phát hiện chẩn đoán khác").
    """
    pool: dict[tuple, list[dict]] = {}
    for e in pred:
        pool.setdefault(key_of(e, mode), []).append(e)
    pairs, missed = [], 0
    for g in gold:
        k = key_of(g, mode)
        if pool.get(k):
            pairs.append((g, pool[k].pop(0)))
        else:
            missed += 1
    spurious = sum(len(v) for v in pool.values())
    return pairs, missed, spurious


# --------------------------------------------------------------- các score


def sample_scores(gold: list[dict], pred: list[dict], mode: str, text_mode: str):
    pairs, missed, spurious = align(gold, pred, mode)

    # --- text
    if text_mode == "concat":
        ref = " ".join(e["text"] for e in sorted(gold, key=lambda x: x["position"][0])).split()
        hyp = " ".join(e["text"] for e in sorted(pred, key=lambda x: x["position"][0])).split()
        t = 1.0 - wer(ref, hyp)
    else:  # 'per_concept': concept không ghép được -> 0
        n = len(pairs) + missed + spurious
        t = (sum(1.0 - wer(g["text"].split(), p["text"].split()) for g, p in pairs) / n) if n else 1.0

    # --- assertions / candidates: trung bình theo concept; không ghép được -> 0
    n_items = len(pairs) + missed + spurious
    if n_items == 0:
        return t, 1.0, 1.0, 0
    a = sum(jaccard(g.get("assertions"), p.get("assertions")) for g, p in pairs) / n_items
    c = sum(jaccard(g.get("candidates"), p.get("candidates")) for g, p in pairs) / n_items
    weight = sum(len(g.get("candidates") or []) + 1 for g in gold)
    return t, a, c, weight


def evaluate(gold_all: dict, pred_all: dict, mode="text_type", text_mode="concat") -> dict:
    ts, as_, cs, ws = [], [], [], []
    for k, gold in gold_all.items():
        t, a, c, w = sample_scores(gold, pred_all.get(k, []), mode, text_mode)
        ts.append(t); as_.append(a); cs.append(c); ws.append(w)
    n = len(gold_all)
    text_score = sum(ts) / n
    assertions_score = sum(as_) / n
    candidates_score = (sum(c * w for c, w in zip(cs, ws)) / sum(ws)) if sum(ws) else 0.0
    final = 0.3 * text_score + 0.3 * assertions_score + 0.4 * candidates_score
    return {
        "text_score": text_score,
        "assertions_score": assertions_score,
        "candidates_score": candidates_score,
        "final_score": final,
        "final_x100": final * 100,
    }


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("dùng: python3 src/evaluate.py <pred.json> <gold.json>")
    pred = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    gold = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    pred = {k: v for k, v in pred.items() if k in gold}  # chỉ chấm phần có nhãn

    print(f"Dev set: {len(gold)} file | {sum(len(v) for v in gold.values())} concept GT")
    print(f"{'ghép theo':16s} {'text':10s} {'text':>7s} {'assert':>7s} {'cand':>7s} {'FINAL':>8s}")
    for mode in ("text_type", "pos_type", "text_pos_type"):
        for tm in ("concat", "per_concept"):
            r = evaluate(gold, pred, mode, tm)
            print(f"{mode:16s} {tm:10s} {r['text_score']:7.4f} {r['assertions_score']:7.4f} "
                  f"{r['candidates_score']:7.4f} {r['final_x100']:8.2f}")
    print("\nCác dòng trên là các GIẢ THIẾT khác nhau về cơ chế chấm. Dùng probe để chốt cái đúng.")


if __name__ == "__main__":
    main()
