#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Track 2 — Inference bằng Qwen ≤9B đã fine-tune -> submission (self-host, KHÔNG API).
Qwen sinh concept (text,type,assertion) -> định vị offset -> gán mã (gazetteer + re-rank) -> zip.

    python3 src/track2_infer.py --adapter qwen_ner_lora --out qwen_submission

Đây là HỆ THỐNG NỘP BÀI hợp lệ (model self-host ≤9B). Gán mã bằng gazetteer/SapBERT (không LLM).
Chạy được trên máy có GPU (hoặc MPS chậm). Timeout đề 600s -> cần batch + vLLM nếu chậm.
"""
from __future__ import annotations
import argparse, json, re, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402
from track2_prep import SYSTEM  # noqa: E402


def parse_json(s: str) -> list:
    a, b = s.find("["), s.rfind("]")
    try:
        return json.loads(s[a:b + 1]) if a >= 0 and b > a else []
    except json.JSONDecodeError:
        return []


def locate(raw: str, concepts: list) -> list:
    """Gán offset cho concept Qwen sinh (khớp nguyên văn, tránh chồng lấn)."""
    out, used = [], []
    for c in concepts:
        txt, typ = (c.get("text") or "").strip(), c.get("type")
        if not txt or typ not in ("THUỐC", "CHẨN_ĐOÁN", "TRIỆU_CHỨNG"):
            continue
        start = 0
        while True:
            p = raw.find(txt, start)
            if p < 0:
                break
            if not any(p < ue and pe > p for pe, ue in used):
                out.append({"text": txt, "type": typ, "candidates": [],
                            "assertions": [c["assertion"]] if c.get("assertion") else [],
                            "position": [p, p + len(txt)]})
                used.append((p, p + len(txt)))
                break
            start = p + 1
    out.sort(key=lambda x: x["position"][0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True, help="thư mục LoRA adapter đã train")
    ap.add_argument("--base", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--out", default="qwen_submission")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    dev = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(args.base)
    model = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=torch.bfloat16).to(dev)
    model = PeftModel.from_pretrained(model, args.adapter).eval()

    out = ROOT / f"out/candidates/{args.out}/output"
    shutil.rmtree(out.parent, ignore_errors=True); out.mkdir(parents=True)
    for i in range(1, 101):
        raw = sections.read_raw(ROOT / "input" / f"{i}.txt")
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": raw}]
        ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(dev)
        with torch.inference_mode():
            gen = model.generate(ids, max_new_tokens=4096, do_sample=False)
        txt = tok.decode(gen[0][ids.shape[1]:], skip_special_tokens=True)
        ents = locate(raw, parse_json(txt))
        (out / f"{i}.json").write_text(json.dumps(ents, ensure_ascii=False, indent=1), encoding="utf-8")
        if i % 10 == 0:
            print(f"{i}/100 ...")
    shutil.make_archive(str(ROOT / f"out/candidates/{args.out}"), "zip", root_dir=out.parent, base_dir="output")
    print(f"-> out/candidates/{args.out}.zip (mã candidates còn RỖNG — chạy gán mã:")
    print(f"   python3 src/gold_triangulate.py --voters ... hoặc rerank_apply.py để thêm ICD/RxNorm)")


if __name__ == "__main__":
    main()
