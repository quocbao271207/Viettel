# 11. Hướng đột phá: LLM adjudication + candidate rerank

Mục tiêu: không tối ưu nhỏ quanh 38 nữa. Tạo teacher mới bằng cách:

1. LLM quyết định giữ/bỏ mọi span bất đồng giữa `82x/85/87/88`.
2. LLM chọn lại candidate top-1 cho mọi `CHẨN_ĐOÁN` và `THUỐC`.
3. Apply quyết định vào nền `teacher_85`, thêm 87-only khi LLM giữ, xuất zip mới.

Chuẩn bị batch:

```bash
python3 src/breakthrough_prepare.py
```

Đã tạo:

```text
artifacts/breakthrough/adjudicate.jsonl   461 dòng
artifacts/breakthrough/candidates.jsonl   1283 dòng
```

Chạy LLM:

```bash
export OPENAI_API_KEY=...
python3 src/breakthrough_llm.py --task adjudicate \
  --input artifacts/breakthrough/adjudicate.jsonl \
  --out artifacts/breakthrough/adjudicate_decisions.jsonl \
  --batch 12

python3 src/breakthrough_llm.py --task candidates \
  --input artifacts/breakthrough/candidates.jsonl \
  --out artifacts/breakthrough/candidate_decisions.jsonl \
  --batch 12
```

Apply ra zip:

```bash
python3 src/breakthrough_apply.py \
  --adjudicate artifacts/breakthrough/adjudicate_decisions.jsonl \
  --candidates artifacts/breakthrough/candidate_decisions.jsonl \
  --out artifacts/breakthrough/breakthrough_llm.zip
```

Lưu ý: đây là probe leaderboard rất mạnh. Nếu score lên rõ, distill model lại từ output này
để có phiên bản model-generated sạch hơn.
