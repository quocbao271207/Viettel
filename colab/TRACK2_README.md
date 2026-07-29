# Track 2 — Model self-host ≤9B (BẮT BUỘC cho top-15)

BTC dựng lại trên private test bằng model self-host **≤9B, KHÔNG API**. FAQ xác nhận: **LLM tạo gold/synthetic
để TRAIN là HỢP LỆ**; chỉ hệ thống NỘP BÀI (inference) mới cấm API. → Pipeline này hợp lệ.

## Cập nhật 25/07: distill GOLD MỚI (bản 13 = 35.2306, 5 TYPE)
Gold Phase 1 đã lên **35.2306** (2511 concept, 5 type gồm xét nghiệm). Trần Track 2 = mức này.
Data/inference ĐÃ regenerate theo gold mới + spec §8a (5 type, assertions LIST 3 loại).

## Pipeline (4 bước)
1. **Chuẩn bị data + bảng mã** (máy, không GPU):
   ```bash
   python3 src/track2_prep.py     # -> dev/track2/{train,dev}.jsonl (2511 concept, 5 type, spec)
   python3 src/track2_codes.py    # -> dev/track2/code_map.json (text->ICD/RxNorm từ gold bản 13)
   ```
2. **Train** (Colab GPU T4/L4/A100): upload `train.jsonl`, `dev.jsonl`, `colab/track2_train_qwen.py` → chạy.
   - Model: `Qwen/Qwen2.5-7B-Instruct` (7.6B ≤ 9B ✓). QLoRA 4-bit vừa T4 16GB. ~6 epoch.
     (Có thể thử `Qwen3-8B` — verify param <9B trước; tắt thinking mode, xem STRATEGY §Model.)
   - Ra: `qwen_ner_lora/` (adapter) → tải về máy.
3. **Inference + gán mã** (máy/GPU): `python3 src/track2_infer.py --adapter qwen_ner_lora`
   - Qwen sinh {text,type,assertions,before} → `locate()` robust định vị offset → gán mã bằng
     `code_map.json` (bảng tra TĨNH, không LLM → hợp lệ ≤9B). Concept lạ để mã RỖNG (an toàn).
   - Ra: `out/candidates/qwen_submission.zip`.
4. **(tuỳ chọn) re-rank mã** cho concept ngoài bảng: `rerank_apply.py` + SapBERT.

## Đã VERIFY offline (không cần GPU) — pipeline inference đúng
Giả lập "Qwen sinh ra đúng nhãn gold" → `to_records`:
- **span match 2471/2511 = 98.4%** (40 miss = lần nhắc lặp, before trùng — chấp nhận được).
- **code match 1017/1017 = 100%** (bảng tra gán ICD/RxNorm chuẩn cho bệnh/thuốc trùng).
→ Nếu Qwen học lại được nhãn gold, submission self-host ≈ bản 13 (35.23). Thực tế Qwen sẽ thấp hơn (distill loss).

## Nâng chất lượng (còn làm)
- **Data ít (100 file / 2511 concept)**: augment (a) synthetic note lâm sàng (LLM, hợp lệ), (b) dataset NER
  công khai (ViMedNER, PhoNER_COVID19, i2b2/BC5CDR) map về 5 type — FAQ cho phép, tuân thủ license.
- **Timeout 600s** (Phase 2/3): dùng vLLM (`--default-chat-template-kwargs '{"enable_thinking":false}'`) hoặc Qwen2.5-3B.
- Gold càng sạch → Qwen học càng đúng. Ưu tiên tiếp tục nâng gold (Phase 1) song song.

## Ràng buộc
- Model ≤9B ✓ (Qwen2.5-7B). Nộp BTC: weights (adapter) + code (`src/track2_*.py`) + data (`dev/track2/*`) + README.
- Gán mã = bảng tra tĩnh + gazetteer/SapBERT (KHÔNG API) → hệ thống nộp bài hợp lệ.
