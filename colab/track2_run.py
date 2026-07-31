#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRACK 2 — train + inference + ĐO THỜI GIAN, chạy trên Colab GPU.

    !git clone https://github.com/quocbao271207/Viettel.git && cd Viettel
    !pip -q install "transformers>=4.44" peft trl bitsandbytes accelerate datasets
    !python colab/track2_run.py --model Qwen/Qwen2.5-1.5B-Instruct --epochs 6

Sau khi chạy xong, tải `qwen_pred.jsonl` về máy rồi:

    python3 -m src.harness.track2 decode --pred qwen_pred.jsonl \
        --out out/candidates/track2_qwen.zip

## RÀNG BUỘC QUYẾT ĐỊNH: 600 giây cho TOÀN BỘ inference (Phase 2/3)

100 file / 600s = **6 giây/file**. Nhãn ~250 token/file ⇒ cần **~42 token/giây**.
Script này ĐO tốc độ thật và báo ĐẠT/KHÔNG ngay sau inference — đừng nộp nếu không đạt.

    Qwen2.5-1.5B trên T4   ~60-120 tok/s   -> ĐẠT thoải mái
    Qwen2.5-3B  trên T4    ~35-70  tok/s   -> sát ngưỡng
    Qwen2.5-7B  trên T4    ~15-25  tok/s   -> KHÔNG ĐẠT nếu không dùng vLLM

Chọn model nhỏ mà kịp giờ hơn là model to mà timeout: timeout = 0 điểm.
Trần trên của data là 99.73% (đo bằng `track2 verify`, không cần GPU) nên phần
quyết định điểm là model học lại nhãn tốt đến đâu, không phải kích thước model.

## Vì sao KHÔNG train mã (candidates)

Mã gán bằng bảng tra tĩnh lúc decode — không LLM, không API ⇒ hợp lệ với luật self-host ≤9B,
và verify cho thấy tra bảng khớp **100%**. Bắt model học thuộc ICD chỉ tốn token.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                          DataCollatorForSeq2Seq, Trainer, TrainingArguments)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dev/track2"


def build(tok, path: Path, max_len: int):
    rows = [json.loads(l) for l in path.read_text("utf-8").splitlines() if l.strip()]
    out = []
    for r in rows:
        msgs = r["messages"]
        prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
        full = prompt + msgs[-1]["content"] + tok.eos_token
        pi = tok(prompt, add_special_tokens=False)["input_ids"]
        fi = tok(full, add_special_tokens=False)["input_ids"][:max_len]
        # chỉ tính loss trên phần NHÃN, không tính trên đề bài
        labels = [-100] * min(len(pi), len(fi)) + fi[min(len(pi), len(fi)):]
        out.append({"input_ids": fi, "attention_mask": [1] * len(fi), "labels": labels})
    return Dataset.from_list(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct",
                    help="PHẢI ≤9B. 1.5B kịp timeout thoải mái; 7B cần vLLM.")
    ap.add_argument("--epochs", type=float, default=6)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max-len", type=int, default=3072)
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--out-dir", default="qwen_ner_lora")
    ap.add_argument("--pred", default="qwen_pred.jsonl")
    ap.add_argument("--skip-train", action="store_true")
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(args.model)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    if not args.skip_train:
        model = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch.bfloat16, device_map="auto")
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
        model = get_peft_model(model, LoraConfig(
            r=32, lora_alpha=64, lora_dropout=0.05, task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"]))
        model.print_trainable_parameters()

        Trainer(
            model=model,
            args=TrainingArguments(
                output_dir=args.out_dir, num_train_epochs=args.epochs,
                per_device_train_batch_size=1, gradient_accumulation_steps=8,
                learning_rate=args.lr, lr_scheduler_type="cosine", warmup_ratio=0.05,
                bf16=True, logging_steps=5, save_strategy="epoch", save_total_limit=1,
                report_to=[]),
            train_dataset=build(tok, DATA / "train.jsonl", args.max_len),
            eval_dataset=build(tok, DATA / "dev.jsonl", args.max_len),
            data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
        ).train()
        model.save_pretrained(args.out_dir)
        tok.save_pretrained(args.out_dir)
        print(f"\n✅ đã lưu adapter -> {args.out_dir}")
        del model
        torch.cuda.empty_cache()

    # ---------------------------------------------------------------- inference + ĐO GIỜ
    from peft import PeftModel
    base = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="auto")
    model = PeftModel.from_pretrained(base, args.out_dir).eval()

    sysmsg = json.loads((DATA / "dev.jsonl").read_text("utf-8").splitlines()[0]
                        )["messages"][0]["content"]
    preds, ntok, t0 = [], 0, time.time()
    for i in range(1, 101):
        raw = (ROOT / "input" / f"{i}.txt").read_text(encoding="utf-8")
        msgs = [{"role": "system", "content": sysmsg}, {"role": "user", "content": raw}]
        ids = tok.apply_chat_template(msgs, add_generation_prompt=True,
                                      return_tensors="pt").to(model.device)
        with torch.no_grad():
            gen = model.generate(ids, max_new_tokens=args.max_new, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        new = gen[0][ids.shape[1]:]
        ntok += len(new)
        preds.append({"file": i, "output": tok.decode(new, skip_special_tokens=True)})
        if i % 10 == 0:
            el = time.time() - t0
            print(f"  {i}/100 · {el:5.1f}s · {ntok/el:5.1f} tok/s · dự phóng {el/i*100:5.0f}s")

    el = time.time() - t0
    Path(args.pred).write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in preds), encoding="utf-8")

    print(f"\n{'='*62}")
    print(f"TỔNG   : {el:.1f} giây cho 100 file  ({el/100:.2f}s/file)")
    print(f"TỐC ĐỘ : {ntok/el:.1f} token/giây  ({ntok} token sinh ra)")
    print(f"NGƯỠNG : 600 giây")
    if el <= 600:
        print(f"✅ ĐẠT — còn dư {600-el:.0f}s ({600/el:.1f}× biên an toàn)")
    else:
        print(f"❌ KHÔNG ĐẠT — chậm {el/600:.1f}× so ngưỡng. ĐỪNG NỘP.")
        print("   Cách xử lý, theo thứ tự ưu tiên:")
        print("   1. model nhỏ hơn (Qwen2.5-1.5B) — trần data là 99.73% nên model to không cần thiết")
        print("   2. vLLM thay HF generate (nhanh 5-10×)")
        print("   3. giảm --max-new (hiện %d); nhãn thật chỉ ~250 token/file" % args.max_new)
    print(f"{'='*62}")
    print(f"-> {args.pred}. Tải về rồi chạy:")
    print(f"   python3 -m src.harness.track2 decode --pred {args.pred} "
          f"--out out/candidates/track2_qwen.zip")


if __name__ == "__main__":
    main()
