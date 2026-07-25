# Track 2 — Model self-host ≤9B (BẮT BUỘC cho top-15)

BTC dựng lại trên private test bằng model self-host **≤9B, KHÔNG API**. FAQ xác nhận: **LLM tạo gold/synthetic
để TRAIN là HỢP LỆ**; chỉ hệ thống NỘP BÀI (inference) mới cấm API. → Pipeline này hợp lệ.

## Pipeline
1. **Chuẩn bị data** (máy): `python3 src/track2_prep.py` → `dev/track2/{train,dev}.jsonl` (gold curate 100 file).
2. **Train** (Colab GPU T4/A100): upload 2 file jsonl + `colab/track2_train_qwen.py` → chạy.
   - Model: `Qwen/Qwen2.5-7B-Instruct` (7.6B ≤ 9B). QLoRA 4-bit vừa T4 16GB. ~6 epoch.
   - Ra: `qwen_ner_lora/` (adapter) → tải về máy.
3. **Inference** (máy/GPU): `python3 src/track2_infer.py --adapter qwen_ner_lora` → concept.
4. **Gán mã**: dùng gazetteer/SapBERT (`rerank_apply.py`) thêm ICD/RxNorm → submission cuối.

## Cần làm thêm (nâng chất lượng)
- **Data ít (100 file)**: augment bằng (a) LLM sinh synthetic note lâm sàng khi có API, (b) dataset NER
  y tế công khai (ViMedNER, PhoNER_COVID19) map nhãn về 3 type — FAQ cho phép, tuân thủ license.
- **Timeout 600s**: nếu Qwen sinh chậm, dùng vLLM hoặc giảm Qwen2.5-3B.
- **Distill từ gold tốt hơn**: gold càng sạch (đã curate assertion) → Qwen học càng đúng.

## Ràng buộc
- Model ≤9B ✓ (Qwen2.5-7B). Weights + code + data + README nộp cho BTC.
- Gold hiện tại (Phase 1) đạt 30.46 = TRẦN của gold; Qwen distill sẽ ≤ mức đó (thường thấp hơn 3-8đ).
  → Muốn top-15 (~35) qua Track 2, gold phải tốt hơn HOẶC Qwen + gazetteer bù mã tốt.
