#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1 LLM "bỏ phiếu" NER trên 100 file -> dev/votes/<voter>.json (có cache, resume được).

    export OPENAI_API_KEY=sk-...      DEEPSEEK_API_KEY=sk-...   [ANTHROPIC_API_KEY=sk-...]
    python3 src/gold_vote.py --voter gpt        # 1 voter
    python3 src/build_gold.py                    # chạy tất cả voter + triangulate (khuyên dùng)

Cấu hình voter ở dev/voters.json. LLM CHỈ trả span+type+assertion+ngữ-cảnh-trái (KHÔNG mã,
KHÔNG offset — hai thứ LLM hay sai). Offset tính sau bằng ngữ cảnh; mã map bằng gazetteer/SapBERT.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
VOTES = ROOT / "dev/votes"


def load_env():
    """Nạp key từ .env vào os.environ (nếu chưa có). Không cần cài python-dotenv."""
    envp = ROOT / ".env"
    if not envp.exists():
        return
    for line in envp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and k not in os.environ:
            os.environ[k] = v

SYSTEM = """Bạn là chuyên gia gán nhãn NER y khoa tiếng Việt cho một cuộc thi.
Trích MỌI lần nhắc tới khái niệm y tế trong văn bản, gồm 3 loại:
- THUỐC: tên thuốc/hoạt chất (kèm liều/đường dùng nếu có, VD "amlodipine 10 mg po daily").
- CHẨN_ĐOÁN: tên bệnh/chẩn đoán (VD "viêm phổi", "Bệnh Kawasaki", "thiếu men G6PD").
- TRIỆU_CHỨNG: triệu chứng/dấu hiệu (VD "sốt", "khó thở", "vàng da").

QUY TẮC:
1. text phải là chuỗi NGUYÊN VĂN xuất hiện trong đoạn (copy đúng, kể cả hoa/thường/dấu).
2. Trích MỖI LẦN NHẮC riêng — cùng một bệnh nhắc 3 lần = 3 mục.
3. Với mỗi mục cho thêm "before" = tối đa 15 ký tự NGAY TRƯỚC span (nguyên văn) để định vị.
4. assertion chọn 1: "" (đang có/khẳng định — MẶC ĐỊNH), "isNegated" (phủ định: không/chưa),
   "isHistorical" (tiền sử/quá khứ/thuốc trước nhập viện), "isFamily" (của người nhà),
   "isUncertain" (nghi ngờ/có thể), "isHypothetical" (giả định/điều kiện: nếu/khi nào).
5. KHÔNG xuất mã ICD/RxNorm. KHÔNG đếm vị trí ký tự. KHÔNG bịa.
6. Bỏ tên người, tên bác sĩ, tên tổ chức (dù trùng tên bệnh).

Chỉ in JSON array, không giải thích. Mỗi phần tử:
{"text": "...", "type": "THUỐC|CHẨN_ĐOÁN|TRIỆU_CHỨNG", "assertion": "...", "before": "..."}"""

FEWSHOT_IN = 'Thuốc trước nhập viện: metoprolol 25mg po bid. Bệnh nhân không sốt, khai có tiền sử viêm dạ dày. Mẹ bị đái tháo đường.'
FEWSHOT_OUT = json.dumps([
    {"text": "metoprolol 25mg po bid", "type": "THUỐC", "assertion": "isHistorical", "before": "nhập viện: "},
    {"text": "sốt", "type": "TRIỆU_CHỨNG", "assertion": "isNegated", "before": "nhân không "},
    {"text": "viêm dạ dày", "type": "CHẨN_ĐOÁN", "assertion": "isHistorical", "before": "tiền sử "},
    {"text": "đái tháo đường", "type": "CHẨN_ĐOÁN", "assertion": "isFamily", "before": "Mẹ bị "},
], ensure_ascii=False)


def call_llm(cfg: dict, key: str, text: str) -> str:
    """Gọi 1 lần, trả nội dung text. Hỗ trợ OpenAI-compatible (gpt/deepseek) + Anthropic (opus)."""
    user = f"Ví dụ:\nĐOẠN: {FEWSHOT_IN}\nKQ: {FEWSHOT_OUT}\n\nĐOẠN:\n{text}\nKQ:"
    if cfg["provider"] == "anthropic":
        r = requests.post(f'{cfg["base_url"]}/messages', timeout=120,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": cfg["model"], "max_tokens": 4096, "system": SYSTEM,
                  "messages": [{"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    # OpenAI-compatible (OpenAI, DeepSeek)
    body = {"model": cfg["model"],
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]}
    if not cfg.get("no_temp"):        # model GPT-5 series chỉ nhận temperature mặc định
        body["temperature"] = 0
    timeout = cfg.get("timeout", 120)  # model reasoning mạnh cần lâu hơn
    r = requests.post(f'{cfg["base_url"]}/chat/completions', timeout=timeout,
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"}, json=body)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse_json(s: str) -> list:
    """Bóc JSON array khỏi câu trả lời (gỡ ```json fence, tìm [ ... ])."""
    s = s.strip()
    if "```" in s:
        s = s.split("```")[1].removeprefix("json").strip() if s.count("```") >= 2 else s
    a, b = s.find("["), s.rfind("]")
    if a < 0 or b < 0:
        return []
    try:
        out = json.loads(s[a:b + 1])
        return out if isinstance(out, list) else []
    except json.JSONDecodeError:
        return []


def run_voter(name: str, cfg: dict):
    load_env()
    key = os.environ.get(cfg.get("key_env", ""), "")
    if not key:
        print(f"[{name}] THIẾU env {cfg.get('key_env')} — bỏ qua. (export {cfg.get('key_env')}=...)")
        return
    VOTES.mkdir(parents=True, exist_ok=True)
    out_path = VOTES / f"{name}.json"
    done = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    sys.path.insert(0, str(ROOT / "src"))
    import sections
    for i in range(1, 101):
        if str(i) in done:
            continue
        raw = sections.read_raw(ROOT / "input" / f"{i}.txt")
        for attempt in range(4):
            try:
                done[str(i)] = parse_json(call_llm(cfg, key, raw))
                break
            except Exception as e:
                if attempt == 3:
                    print(f"[{name}] file {i} lỗi sau 4 lần: {str(e)[:80]}")
                    done[str(i)] = []
                else:
                    time.sleep(2 * (attempt + 1))
        if i % 10 == 0:
            out_path.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"[{name}] {i}/100 ...")
    out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(v) for v in done.values())
    print(f"[{name}] xong -> {out_path}  ({n} concept thô)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voter", required=True, help="tên voter trong dev/voters.json")
    args = ap.parse_args()
    voters = json.loads((ROOT / "dev/voters.json").read_text(encoding="utf-8"))
    cfg = next((v for v in voters if v["name"] == args.voter), None)
    if not cfg:
        raise SystemExit(f"Không thấy voter {args.voter!r} trong dev/voters.json")
    run_voter(args.voter, cfg)


if __name__ == "__main__":
    main()
