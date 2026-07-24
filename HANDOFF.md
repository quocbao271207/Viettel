# HANDOFF — Viettel AI Race Bài 2 (trạng thái 24/07/2026)

> File này để một phiên chat MỚI nối tiếp ngay mà không cần lịch sử cũ. Đọc kèm memory
> (`viettel-*.md`) + `STRATEGY.md`. Cập nhật khi có tiến triển.

## 1. Đang ở đâu — điểm leaderboard (điểm hiển thị = raw×100, %)

Tiến trình (data MỚI 21/07): **rỗng 0.08 → thuốc 3.98 → +chẩn đoán 8.98 → +triệu chứng(rule) 15.47
→ NER Claude LLM 24.19 → +ICD CÓ CHẤM 27.26 → +re-rank ICD 30.2557** ✅ (bản tốt nhất, nộp 24/07 16:22).

- Top leaderboard **39.76**, top-15 ~**35**. Ta 30.26 (~76% top).
- Phân rã 30.26: **text 10.28 + assert 11.06 + candidates 8.92** (J_cand 14.80→22.29 nhờ re-rank).
  Công thức: `0.3(1−WER)+0.3·J_assert+0.4·J_cand`.
- Bản nộp tốt nhất: `out/submitted/06_claude_rerank_30.2557.zip`. Lịch sử điểm đầy đủ: `out/SCORES.md`.

## 2. Phát hiện CỨNG (đã trả giá bằng lượt nộp — đừng phân tích lại)

1. **ICD phải CÓ DẤU CHẤM** `D55.0` (không phải `D550`) → candidates gấp đôi (7.11→14.80). RxNorm giữ SỐ `7646`.
2. **Candidates KHÔNG còn free** trên data mới (rỗng J_cand≈0). Gần như MỌI concept gold đều có mã → gán mã là cược một chiều, headroom ~40đ.
3. **LLM extraction >> pipeline rule**: NER Claude (2119 concept, assertion ngữ cảnh THẬT) làm submission = 24-27đ; pipeline rule chỉ 15. **Assertion là mỏ vàng** (+4.7đ chỉ nhờ isHistorical/isNegated/… đúng).
4. **Không over-predict như lo**: Claude 6374 từ mà WER vẫn GIẢM → N_gold thật cao (~6000+), cứ trích đầy đủ nếu chính xác.
5. **Thuốc bị che `*****` = mồi nhử**, KHÔNG phải concept gold. Bỏ qua.
6. **SapBERT**: tốt để RETRIEVE ứng viên, nhưng top-1 SAI nhiều với cụm tiếng Việt ngắn ("sốt"→nôn, "suy tim"→nhịp nhanh). Phải LLM re-rank / tự đề xuất mã.
7. **Trần 9B chỉ áp Phase 2/3** (model self-host). Build gold + submission Phase 1 dùng LLM mạnh tuỳ ý.
8. Data mới: bài giáo dục/Q&A bác sĩ TRỘN mảnh note lâm sàng cũ; 20/100 file Unicode NFD (đã sửa `sections.read_raw` dùng offset raw).

## 3. Chiến lược 2 track

- **Track 1 — Phase 1 (leo NGAY):** submission = **NER bằng LLM** (Claude in-session free + Codex/Gemini) → gán mã (RxNorm + ICD re-rank, CÓ CHẤM). Đang ở 27.26, nhắm top-15 (~35).
- **Track 2 — Phase 2 (bắt buộc cho top-15):** dựng lại bằng pipeline **≤9B self-host** (Qwen3-8B) tune theo GOLD. GOLD = triangulate 3 LLM. Cần Colab GPU cho việc này.

## 4. Tài sản (scripts trong src/)

| File | Vai trò |
|---|---|
| `extract.py` / `extract_all.py` | pipeline rule NER (thuốc / +bệnh+triệu chứng) + RxNorm |
| `sections.py` | parser offset (ĐÃ sửa NFC: dùng raw cho 20 file NFD) |
| `gazetteer.py` + `data/gaz.json` | RxNorm 17.5k + ICD-10-CM 74.719 mã |
| `add_icd10.py` / `finalize_submission.py` | gán ICD bằng SapBERT (index `data/icd10_sapbert.pt` 230MB, đã dựng LOCAL trên MPS) |
| `context_vi.py` | assertion (ConText) — chưa dùng nhiều vì LLM làm tốt hơn |
| `evaluate.py` | chấm cục bộ (pred vs gold) |
| **Gold-building:** `gold_vote.py` | 1 LLM voter gọi API (OpenAI/DeepSeek/Anthropic/Gemini), cache resume |
| `gold_triangulate.py` | gộp voter ≥k đồng thuận + map mã. `build_gold.py` = orchestrator 1 lệnh |
| `merge_votes.py` | gộp phiếu chạy theo mảnh → dev/votes/<name>.json (parts cũ → archive/votes_parts) |
| `autolabel.py` / `review_csv.py` | bản dò-từ-điển / duyệt gold bằng CSV (ít dùng, LLM thay) |
| **Re-rank:** `rerank_prepare.py` → `rerank_apply.py` | SapBERT top-8 → LLM chọn mã → áp vào submission |

**Voter đã có:** `dev/votes/claude.json` = **2119 concept** (LLM in-session, 100/100 file, định vị 99.6%, assertion thật). Đây là nền của submission 24-27đ.

## 5. Cách tạo submission tốt nhất hiện tại (tái lập)

```bash
# 1. Gán mã cho voter Claude (curated + SapBERT), ra dev/gold_resolved.json
python3 src/gold_triangulate.py --k 1 --sapbert
# 2. (đang làm) re-rank mã ICD bằng LLM cho ĐÚNG hơn:
python3 src/rerank_prepare.py --topk 8          # -> dev/rerank_input.json
#    chia 5 batch -> dev/rerank_batches/, giao 5 agent LLM chọn mã -> dev/rerank_out/*.json
python3 src/rerank_apply.py                      # -> out/candidates/claude_rerank.zip (ICD CÓ CHẤM)
```
Nếu bỏ re-rank: đóng gói dev/gold_resolved.json thành zip nhớ **thêm dấu chấm ICD** (hàm `dot()` trong rerank_apply).

## 6. Trạng thái mới nhất (24/07 ~16:40)

- **`claude_rerank.zip` ĐÃ NỘP = 30.2557** (WER 65.73, J_assert 36.87, J_cand 22.29). Re-rank ăn +3đ.
- **Vụ "thuốc gán nhầm type" ĐÃ SẠCH** — kiểm claude.json + gold_resolved.json: 0 concept. Đừng làm lại.
  (Tool kiểm: `src/force_drugs.py --voter <tên> --dry` — dùng cho voter mới.)
- **2 voter MỚI đang chạy nền** (~16:30): `gold_vote.py --voter gpt` (gpt-4o) + `--voter gpt41` (gpt-4.1)
  → `dev/votes/{gpt,gpt41}.json`. Key OpenAI trong .env HOẠT ĐỘNG; **key Gemini HẾT credit trả trước**
  (429 mọi model) — cần nạp hoặc lấy key free AIza… từ aistudio.google.com/apikey rồi thay .env.
- **Nâng cấp script:** `gold_triangulate.py` thêm `--voters a,b` (lọc voter) + `--trust claude`
  (cụm có claude LUÔN giữ, span/assertion ưu tiên claude; cụm mới cần ≥k voter khác) + `--out`.
  `rerank_apply.py` thêm `--gold --out`. `rerank_prepare.py` thêm `--gold --out --skip-done`.
  `rerank_llm.py` MỚI: LLM re-rank ICD tự động qua OpenAI API (thay 5 agent tay).
- **Tái cấu trúc 24/07:** bản ĐÃ NỘP nằm ở `out/submitted/NN_tên_điểm.zip` (00→06); `out/candidates/`
  chỉ chứa bản CHƯA nộp. Đồ cũ (probe, olddata, nhãn tay, rerank_batches, votes/parts) → `archive/`.
  Bản đồ script active/legacy: `src/README.md`.

### Pipeline bản nộp KẾ TIẾP (khi 2 voter xong)
```bash
python3 src/gold_triangulate.py --k 2 --sapbert --trust claude --out dev/gold_merged.json
python3 src/rerank_prepare.py --gold dev/gold_merged.json --out dev/rerank_input_new.json --skip-done
python3 src/rerank_llm.py --input dev/rerank_input_new.json --name auto_gpt
python3 src/rerank_apply.py --gold dev/gold_merged.json --out merged3_rerank
# -> nộp out/candidates/merged3_rerank.zip
```

## 7. Việc tiếp theo (đòn bẩy còn lại)

1. **Candidates (lớn nhất, còn ~34đ):** re-rank ICD (đang làm) + kiểm mã RxNorm thuốc.
2. **Voter thứ 2-3 cho gold sạch (Track 2):** Codex (free, gói Plus) → `dev/votes/gpt.json` theo `dev/CODEX_TASK.md`; Gemini free (aistudio.google.com/apikey) → thêm vào `dev/voters.json`. Rồi `build_gold.py --k 2 --sapbert`.
3. **KHÔNG cần mua:** OpenAI API (Codex lo GPT), Anthropic (phiên chat lo Claude). Chỉ Gemini (free) hoặc DeepSeek (~$2) nếu muốn voter thêm.
4. **Phase 2:** distill gold → fine-tune/prompt Qwen3-8B trên Colab để pipeline ≤9B tái lập được.

## 8. Ràng buộc đề

Deadline Phase 1: **04/08/2026**. Top-15 phải nộp source + data + weights, BTC dựng lại trên private test bằng model self-host **≤9B**, cấm hard-code output. Timeout 600s (chỉ Phase 2/3). 5 lượt nộp/ngày.
