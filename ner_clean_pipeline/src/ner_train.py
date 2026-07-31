"""Train NER token-classification (BIO) cho 5 loại khái niệm.

Chạy được ở hai nơi:
  - Colab (L4/A100) để train thật
  - máy BTC khi dựng lại: chỉ cần inference, xem src/ner_infer.py

    python src/ner_train.py --model xlm-roberta-large --epochs 20 --bs 4 --lr 2e-5

Vì sao XLM-R chứ không PhoBERT: 22.7% bề mặt khái niệm là THUẦN ASCII (tên thuốc
tiếng Anh trong RxNorm: "Augmentin", "amoxicillin", "Thrombophilia"). PhoBERT tokenizer
chuyên tiếng Việt và cần word-segmentation trước, mà segmentation làm lệch offset —
trong khi đề chấm theo `position`. XLM-R là sentencepiece đa ngữ, có
`return_offsets_mapping=True` nên map ngược về offset gốc chính xác.

Điểm dễ sai nhất và cách xử lý:

1. **Offset gốc là văn bản THÔ, không normalize.** 20/100 file là NFD. Không gọi
   unicodedata.normalize ở bất kỳ đâu trong pipeline.
2. **is_split_into_words=False + offsets_mapping.** Không tự tách từ.
3. Token đầu của span -> `B-X`, token sau -> `I-X`, token special/không thuộc span
   -> `O`. Token bị nhãn -100 chỉ là special token, phần còn lại đều tính loss.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TYPES = (
    "TRIỆU_CHỨNG",
    "CHẨN_ĐOÁN",
    "TÊN_XÉT_NGHIỆM",
    "KẾT_QUẢ_XÉT_NGHIỆM",
    "THUỐC",
)
LABELS = ["O"] + [f"{p}-{t}" for t in TYPES for p in ("B", "I")]
L2I = {x: i for i, x in enumerate(LABELS)}


def set_seed(s: int) -> None:
    import numpy as np
    import torch

    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)
    torch.cuda.manual_seed_all(s)


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def encode(rows: list[dict], tok, max_len: int):
    """rows -> dict các list, mỗi phần tử 1 cửa sổ đã tokenize + gắn nhãn BIO."""
    out = {"input_ids": [], "attention_mask": [], "labels": []}
    n_lost = 0
    for r in rows:
        enc = tok(
            r["text"],
            truncation=True,
            max_length=max_len,
            return_offsets_mapping=True,
        )
        offs = enc["offset_mapping"]
        lab = [L2I["O"]] * len(offs)
        for i, (a, b) in enumerate(offs):
            if a == b:  # special token
                lab[i] = -100
        for s, e, typ, *_ in r["spans"]:
            first = True
            hit = False
            for i, (a, b) in enumerate(offs):
                if a == b:
                    continue
                if a >= e or b <= s:  # không giao
                    continue
                lab[i] = L2I[("B-" if first else "I-") + typ]
                first = False
                hit = True
            if not hit:
                n_lost += 1
        out["input_ids"].append(enc["input_ids"])
        out["attention_mask"].append(enc["attention_mask"])
        out["labels"].append(lab)
    if n_lost:
        print(f"  CẢNH BÁO: {n_lost} span không map được vào token nào (bị truncate?)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="xlm-roberta-large")
    ap.add_argument("--data", default=str(ROOT / "data/ner"))
    ap.add_argument("--out", default=str(ROOT / "models/ner"))
    ap.add_argument("--epochs", type=float, default=20)
    ap.add_argument("--bs", type=int, default=4)
    ap.add_argument("--accum", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=512)
    ap.add_argument("--seed", type=int, default=20260728)
    # fp16 với XLM-R large rất dễ ra NaN loss (lớp LayerNorm tràn số). L4 và A100 đều có
    # bf16 nên mặc định dùng bf16; để --fp16 lại cho GPU cũ (T4) không hỗ trợ bf16.
    ap.add_argument("--fp16", action="store_true")
    ap.add_argument("--bf16", action="store_true")
    # Chốt siêu tham số trên val TRƯỚC, rồi bật --all để train lại trên cả 100 file cho
    # bản nộp cuối. Dữ liệu chỉ có 3475 entity, bỏ 20% đi là bỏ thật.
    ap.add_argument("--all", action="store_true", help="train trên train+val")
    args = ap.parse_args()

    import numpy as np
    import torch
    from torch.utils.data import Dataset
    from transformers import (
        AutoModelForTokenClassification,
        AutoTokenizer,
        DataCollatorForTokenClassification,
        Trainer,
        TrainingArguments,
    )

    set_seed(args.seed)
    data_dir = Path(args.data)
    tok = AutoTokenizer.from_pretrained(args.model)

    tr_rows = read_jsonl(data_dir / "train.jsonl")
    va_rows = read_jsonl(data_dir / "val.jsonl")
    if args.all:
        tr_rows = tr_rows + va_rows  # val vẫn dùng làm eval, nhưng nó đã nằm trong train
        print("--all: train trên cả 100 file, số eval CHỈ còn để xem loss, KHÔNG tin được")
    print(f"train {len(tr_rows)} cửa sổ, val {len(va_rows)} cửa sổ")
    tr, va = encode(tr_rows, tok, args.max_len), encode(va_rows, tok, args.max_len)

    class DS(Dataset):
        def __init__(self, d):
            self.d = d

        def __len__(self):
            return len(self.d["input_ids"])

        def __getitem__(self, i):
            return {k: self.d[k][i] for k in self.d}

    model = AutoModelForTokenClassification.from_pretrained(
        args.model,
        num_labels=len(LABELS),
        id2label={i: x for x, i in L2I.items()},
        label2id=L2I,
    )

    def metrics(p):
        """Đo theo SPAN, không theo token — vì đề chấm theo khái niệm.
        Đây chỉ là đèn báo trong lúc train; điểm thật đo bằng src/score.py."""
        logits, labels = p
        pred = np.argmax(logits, axis=-1)
        tp = fp = fn = 0
        for pr, lb in zip(pred, labels):
            ps = _spans([LABELS[i] for i, m in zip(pr, lb) if m != -100])
            gs = _spans([LABELS[i] for i in lb if i != -100])
            tp += len(ps & gs)
            fp += len(ps - gs)
            fn += len(gs - ps)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {"precision": prec, "recall": rec, "f1": f1}

    targs = TrainingArguments(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.bs,
        per_device_eval_batch_size=args.bs * 2,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        weight_decay=0.01,
        logging_steps=20,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        # Với --all thì val đã nằm trong train, chọn checkpoint theo nó là tự lừa mình
        # -> lấy checkpoint cuối, dùng đúng số epoch đã chốt được ở vòng có val sạch.
        load_best_model_at_end=not args.all,
        # RECALL, không phải F1. Đo ở worklog/06: recall 100% với assertions/candidates
        # rỗng đã là 77.35đ, còn precision chỉ ảnh hưởng gián tiếp -> chọn checkpoint
        # theo recall.
        metric_for_best_model="recall",
        greater_is_better=True,
        fp16=args.fp16,
        bf16=args.bf16,
        report_to=[],
        seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=DS(tr),
        eval_dataset=DS(va),
        data_collator=DataCollatorForTokenClassification(tok),
        compute_metrics=metrics,
    )
    trainer.train()
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    print(json.dumps(trainer.evaluate(), indent=1))
    print("đã lưu ->", args.out)


def _spans(tags: list[str]) -> set[tuple[int, int, str]]:
    out, cur = set(), None
    for i, t in enumerate(tags):
        if t.startswith("B-"):
            if cur:
                out.add((cur[0], i, cur[1]))
            cur = (i, t[2:])
        elif t.startswith("I-"):
            if cur is None or cur[1] != t[2:]:
                cur = (i, t[2:])  # I- mở đầu: vẫn nhận, thiên về recall
        else:
            if cur:
                out.add((cur[0], i, cur[1]))
            cur = None
    if cur:
        out.add((cur[0], len(tags), cur[1]))
    return out


if __name__ == "__main__":
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    main()
