#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Track 2 — LoRA fine-tune Qwen ≤9B cho generative NER y khoa. CHẠY TRÊN COLAB GPU (T4/A100).

Cài:  pip install -U transformers peft trl datasets accelerate bitsandbytes
Data: upload dev/track2/train.jsonl + dev.jsonl lên Colab (hoặc mount Drive).

Model: Qwen/Qwen2.5-7B-Instruct (7.6B ≤ 9B ✓). QLoRA 4-bit để vừa T4 16GB.
Sau train: lưu adapter -> tải về, dùng src/track2_infer.py để sinh submission.
"""
import json, torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig

MODEL = "Qwen/Qwen2.5-7B-Instruct"   # ≤9B; đổi Qwen2.5-3B nếu GPU nhỏ

tok = AutoTokenizer.from_pretrained(MODEL)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb, device_map="auto")
model = get_peft_model(model, LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
model.print_trainable_parameters()

ds = load_dataset("json", data_files={"train": "train.jsonl", "dev": "dev.jsonl"})


def fmt(ex):
    return {"text": tok.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=False)}


ds = ds.map(fmt)

trainer = SFTTrainer(
    model=model, tokenizer=tok,
    train_dataset=ds["train"], eval_dataset=ds["dev"],
    args=SFTConfig(
        output_dir="qwen_ner_lora", max_seq_length=8192,  # file dài nhất ~6k token (không cắt nhãn)
        per_device_train_batch_size=1, gradient_accumulation_steps=8,  # T4 OOM -> giảm max_seq_length hoặc dùng L4/A100
        num_train_epochs=6, learning_rate=2e-4, warmup_ratio=0.05,
        logging_steps=5, eval_strategy="epoch", save_strategy="epoch",
        bf16=True, gradient_checkpointing=True, report_to="none"),
)
trainer.train()
trainer.save_model("qwen_ner_lora")   # tải thư mục này về -> track2_infer.py
print("XONG. Tải qwen_ner_lora/ về máy, chạy: python3 src/track2_infer.py --adapter qwen_ner_lora")
