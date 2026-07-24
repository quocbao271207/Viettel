#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-rank mã ICD bằng LLM qua API (thay 5 agent thủ công) — cho các cụm trong rerank_input.

    python3 src/rerank_llm.py --input dev/rerank_input_new.json --name auto_gpt
-> dev/rerank_out/auto_gpt.json  {text: mã KHÔNG chấm}  (cache resume theo batch)

LLM thấy top-K ứng viên SapBERT (mã + mô tả EN) và được phép đề xuất mã ICD-10-CM khác
nếu ứng viên đều sai. Mã trả về được kiểm tra tồn tại trong gazetteer; mã lạ -> bỏ (giữ mã cũ).
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from gold_vote import load_env  # noqa: E402

SYSTEM = """Bạn là chuyên gia mã hoá ICD-10-CM cho văn bản y khoa tiếng Việt.
Với mỗi cụm (bệnh hoặc triệu chứng) kèm danh sách ứng viên [mã, mô tả tiếng Anh],
chọn MỘT mã ICD-10-CM đúng nhất. Nếu mọi ứng viên đều sai, tự đề xuất mã ICD-10-CM đúng.
Quy tắc:
- TRIỆU_CHỨNG thường thuộc chương R (trừ khi có mã chuyên biệt đúng hơn).
- CHẨN_ĐOÁN chọn mã bệnh cụ thể; ưu tiên mã "unspecified" nếu văn bản không nói rõ biến thể.
- Mã viết KHÔNG có dấu chấm (VD: J189, I509, R509).
Chỉ in JSON object {"cụm": "mã", ...}, không giải thích."""


def call(model: str, key: str, batch: list) -> dict:
    lines = []
    for it in batch:
        opts = ", ".join(f"[{c}] {d}" for c, d in it["options"])
        lines.append(f'- "{it["text"]}" ({it["type"]}): {opts}')
    user = "Chọn mã cho các cụm sau:\n" + "\n".join(lines) + '\n\nJSON:'
    r = requests.post("https://api.openai.com/v1/chat/completions", timeout=180,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "temperature": 0, "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]})
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="dev/rerank_input.json")
    ap.add_argument("--name", default="auto_gpt", help="tên file ra trong dev/rerank_out/")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--batch", type=int, default=25)
    args = ap.parse_args()

    load_env()
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise SystemExit("Thiếu OPENAI_API_KEY (.env)")
    items = json.loads((ROOT / args.input).read_text(encoding="utf-8"))
    valid = set(json.loads((ROOT / "data/gaz.json").read_text(encoding="utf-8")).get("icd_code2en", {}))
    out_path = ROOT / f"dev/rerank_out/{args.name}.json"
    done = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    todo = [it for it in items if it["text"] not in done]
    print(f"{len(todo)} cụm cần re-rank (đã có {len(done)})")

    bad = 0
    for i in range(0, len(todo), args.batch):
        batch = todo[i:i + args.batch]
        for attempt in range(4):
            try:
                res = call(args.model, key, batch)
                break
            except Exception as e:
                if attempt == 3:
                    print(f"batch {i} lỗi: {str(e)[:100]}"); res = {}
                else:
                    time.sleep(3 * (attempt + 1))
        for it in batch:
            code = str(res.get(it["text"], "")).replace(".", "").strip().upper()
            if code in valid:
                done[it["text"]] = code
            else:
                bad += 1
        out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {min(i + args.batch, len(todo))}/{len(todo)} (mã lạ bỏ: {bad})")
    print(f"-> {out_path.relative_to(ROOT)} ({len(done)} cụm)")


if __name__ == "__main__":
    main()
