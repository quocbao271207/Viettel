"""Gọi LLM cho batch breakthrough.

Yêu cầu `OPENAI_API_KEY`. Output là JSONL quyết định, dùng cho `breakthrough_apply.py`.

Ví dụ:

    python src/breakthrough_llm.py --task adjudicate \
      --input artifacts/breakthrough/adjudicate.jsonl \
      --out artifacts/breakthrough/adjudicate_decisions.jsonl

    python src/breakthrough_llm.py --task candidates \
      --input artifacts/breakthrough/candidates.jsonl \
      --out artifacts/breakthrough/candidate_decisions.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests


SYSTEM = {
    "adjudicate": """Bạn là bác sĩ annotator cho medical NER tiếng Việt.
Với mỗi item, quyết định span đó có nên giữ là một khái niệm y khoa độc lập hay bỏ.
Chỉ giữ nếu text là bệnh/chẩn đoán, triệu chứng, tên xét nghiệm, kết quả xét nghiệm, hoặc thuốc/điều trị cụ thể.
Bỏ nếu là sinh hiệu generic, số đo trơ, từ quá chung, nhóm thuốc quá chung, hoặc phrase không phải entity.
Trả JSON object {"items":[{"id":"...","keep":true/false,"assertions":["isNegated"|"isHistorical"|"isFamily", ...],"reason":"ngắn"}]}.""",
    "candidates": """Bạn là chuyên gia mã hoá ICD-10/RxNorm cho văn bản y khoa tiếng Việt.
Với mỗi item, chọn candidates tốt nhất từ options. Chọn tối đa 1 mã, ưu tiên để [] nếu không chắc.
CHẨN_ĐOÁN dùng ICD-10-CM; THUỐC dùng RxNorm/RxCUI. Không chọn mã chỉ vì gần chữ nếu ngữ nghĩa sai.
Trả JSON object {"items":[{"id":"...","candidates":["CODE"] hoặc [],"reason":"ngắn"}]}.""",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def call(model: str, key: str, task: str, batch: list[dict]) -> list[dict]:
    user = json.dumps({"items": batch}, ensure_ascii=False)
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        timeout=180,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM[task]}, {"role": "user", "content": user}],
        },
    )
    r.raise_for_status()
    obj = json.loads(r.json()["choices"][0]["message"]["content"])
    return obj.get("items", [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=("adjudicate", "candidates"), required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "gpt-4o"))
    ap.add_argument("--batch", type=int, default=12)
    args = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise SystemExit("Thiếu OPENAI_API_KEY")
    items = read_jsonl(Path(args.input))
    out_path = Path(args.out)
    done = {}
    if out_path.exists():
        for row in read_jsonl(out_path):
            done[row["id"]] = row
    todo = [x for x in items if x["id"] not in done]
    print(f"{args.task}: todo={len(todo)} done={len(done)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        for i in range(0, len(todo), args.batch):
            batch = todo[i : i + args.batch]
            for attempt in range(4):
                try:
                    res = call(args.model, key, args.task, batch)
                    break
                except Exception as exc:
                    if attempt == 3:
                        raise
                    print("retry", attempt + 1, str(exc)[:120])
                    time.sleep(2 + attempt * 3)
            by_id = {str(x.get("id")): x for x in res}
            for item in batch:
                row = by_id.get(item["id"], {"id": item["id"]})
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"{min(i + args.batch, len(todo))}/{len(todo)}")
    print("->", out_path)


if __name__ == "__main__":
    main()
