#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Track 2 — Inference bằng Qwen ≤9B đã fine-tune -> submission (self-host, KHÔNG API).
Qwen sinh {text,type,assertions,before} -> định vị offset (locate robust) -> gán mã (bảng tra) -> zip.

    python3 src/track2_infer.py --adapter qwen_ner_lora --out qwen_submission

Hệ thống nộp bài HỢP LỆ (model self-host ≤9B; gán mã bằng bảng tra tĩnh, không LLM/API).
Chạy trên GPU (Colab/T4) hoặc MPS. Timeout đề 600s -> nên dùng vLLM nếu chậm.
"""
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402
from track2_prep import SYSTEM  # noqa: E402
from build_gold_lab import locate as locate_span, ALLOWED_ASSERT  # noqa: E402

LAB = {"TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM"}
ALL_TYPES = {"THUỐC", "CHẨN_ĐOÁN", "TRIỆU_CHỨNG"} | LAB


def parse_json(s: str) -> list:
    a, b = s.find("["), s.rfind("]")
    try:
        return json.loads(s[a:b + 1]) if a >= 0 and b > a else []
    except json.JSONDecodeError:
        return []


def to_records(raw: str, concepts: list, code_map: dict) -> list:
    """Định vị + gán mã cho concept Qwen sinh. Dùng locate() robust (before+text, fuzzy)."""
    out, used = [], []
    for c in concepts:
        typ = (c.get("type") or "").strip()
        txt = (c.get("text") or "").strip()
        if typ not in ALL_TYPES or not txt:
            continue
        pos = locate_span(raw, txt, c.get("before", ""), used)
        if pos is None:
            continue
        s, e = pos
        used.append((s, e))
        asserts = [x for x in (c.get("assertions") or []) if x in ALLOWED_ASSERT]
        cands = code_map.get(typ, {}).get(raw[s:e].strip().lower(), []) if typ in ("CHẨN_ĐOÁN", "THUỐC") else []
        out.append({"text": raw[s:e], "type": typ, "candidates": cands,
                    "assertions": asserts, "position": [s, e]})
    out.sort(key=lambda x: (x["position"][0], x["position"][1]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True, help="thư mục LoRA adapter đã train")
    ap.add_argument("--base", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--codes", default="dev/track2/code_map.json")
    ap.add_argument("--out", default="qwen_submission")
    args = ap.parse_args()

    code_map = json.loads((ROOT / args.codes).read_text(encoding="utf-8")) if (ROOT / args.codes).exists() else {}

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
            # sampling theo card Qwen (greedy dễ lặp vô hạn — STRATEGY §Model)
            gen = model.generate(ids, max_new_tokens=4096, do_sample=True,
                                 temperature=0.7, top_p=0.8, top_k=20)
        txt = tok.decode(gen[0][ids.shape[1]:], skip_special_tokens=True)
        ents = to_records(raw, parse_json(txt), code_map)
        (out / f"{i}.json").write_text(json.dumps(ents, ensure_ascii=False, indent=1), encoding="utf-8")
        if i % 10 == 0:
            print(f"{i}/100 ...")
    shutil.make_archive(str(ROOT / f"out/candidates/{args.out}"), "zip", root_dir=out.parent, base_dir="output")
    print(f"-> out/candidates/{args.out}.zip (đã gán mã qua bảng tra; concept lạ để rỗng — an toàn)")


if __name__ == "__main__":
    main()
