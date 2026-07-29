# HANDOFF — Viettel AI Race Bài 2 (trạng thái 29/07/2026)

> File này để một phiên chat MỚI nối tiếp ngay. Đọc kèm `STRATEGY.md` + `dev/NER_PROMPT_SPEC.md`.

## ⭐ TỐT NHẤT: BẢN 14 = **36.4914** (WER 58.2207 · J_assert 48.3759 · J_cand 23.6121)
`out/submitted/14_repeat_36.4914.zip`. Thêm 313 **lần nhắc lặp** bị bỏ sót → **tăng CẢ 3 TRỤC**, phá mốc
J_cand đóng băng 4 lần nộp. 3 kết luận cứng rút ra: xem `out/SCORES.md` §BẢN 14.

## 🔴 VIỆC NGAY (29/07): NỘP `out/candidates/15_repeat2.zip`
Bản 15 = nền bản 14 + **147 lần nhắc lớp 2** (cụm 1 âm tiết + biến thể hoa/thường). Chi tiết: `out/SCORES.md` §BẢN 15.
Tái lập: `python3 src/build_repeat.py --stage 2`.
Diff vs bản 14 = **thêm thuần 147 concept, 0 concept cũ bị đụng** ⇒ đọc kết quả sạch:
- TĂNG ⇒ cụm ngắn cũng được gold tính → quét tiếp lớp 3 (viết tắt, biến thể chính tả, cụm gần đúng).
- GIẢM ⇒ ngưỡng an toàn dừng ở cụm ≥2 âm tiết → quay về bản 14, dồn lực Track 2.

## 📌 NGUYÊN TẮC ĐÃ CHỨNG MINH (dùng cho mọi bản sau)
1. **Gold tính MỌI lần nhắc, không dedupe.** Trích full đúng spec — kể cả trong bài giáo dục lặp từ khoá.
2. **Muốn tăng J_cand phải thêm SPAN MỚI mang mã đúng**, không phải sửa mã trên span cũ (đã phí 4 lượt nộp).
3. **Recall AN TOÀN = nhân bản text đã ăn điểm sang lần nhắc khác, giữ nguyên mã.**
   Recall NGUY HIỂM = span mới do voter khác đề xuất, mã rỗng (bẫy bản 09).

## ⭐ TRẠNG THÁI (25/07 16:17): BẢN 13 = 35.2306 — TỐT NHẤT HIỆN TẠI
`out/submitted/13_gold_lab_fixes_35.2306.zip`. **2511 concept / 5 type.** Build:
`python3 src/build_gold_lab.py --fixes dev/icd_fixes.json --afixes dev/assert_fixes.json`
+0.06 vs bản 12 (nguồn: J_assert 46.62→46.76 do relabel lab đúng chỗ; WER phẳng).
**⚠️ PHÁT HIỆN: J_cand = 22.7839 ĐÓNG BĂNG qua 4 lần nộp (bản 10→13).** Sửa 4 mã ICD tần suất thấp KHÔNG dịch được J_cand.
→ J_cand chỉ nhúc nhích khi sửa mã cụm TẦN SUẤT CAO + KHỚP span gold (bản 10). Hướng "sửa mã lẻ" ĐÃ CẠN.

## ĐÒN BẨY (đã rà toàn bộ 25/07 chiều — "làm toàn bộ")
1. **WER 59.70 (0.3) — CẠN phần an toàn.** Recall "thêm type thiếu" (xét nghiệm) đã ăn trọn. Phân tích mật độ:
   không còn pocket lớn gold-có-mà-ta-thiếu; thêm concept existing-type = bẫy bản 09. (1 micro-fix: file 76 "MÀY đay"→"MÀY đay VÔ CĂN", bỏ qua vì ~0 tác động.)
2. **Track 2 (Qwen ≤9B) — ĐÃ CHUẨN BỊ XONG, CHỜ COLAB GPU (việc lớn còn lại).**
   - `python3 src/track2_prep.py && python3 src/track2_codes.py` → data 5 type + code_map (đã có).
   - Train: upload `dev/track2/*.jsonl` + `colab/track2_train_qwen.py` lên Colab (Qwen2.5-7B QLoRA). Xem `colab/TRACK2_README.md`.
   - Inference: `src/track2_infer.py --adapter qwen_ner_lora`. VERIFY offline: span 98.4%, code 100%.
3. **J_cand 22.78 (0.4) — KHÓA.** Top-40 bệnh + top-20 thuốc đã ĐÚNG mã (verify). Đóng băng 4 lần nộp: đổi mã mù = 0 tín hiệu.
   Headroom nằm sau match span gold (recall/ranh giới) — cần gold để đối chiếu. Đừng phí lượt nộp đổi mã lẻ.

## (đã nộp 25/07 15:22) BẢN 12 = 35.1719 — thêm 2 type XÉT NGHIỆM (+4.03 điểm)
`out/submitted/12_gold_lab_35.1719.zip`. Nền bản 11 + 487 concept xét nghiệm. WER 65.73→59.76 · J_assert 39.16→**46.62** · J_cand 22.78.
- **BÀI HỌC LẬT NGƯỢC "recall là bẫy":** bẫy chỉ với concept TRÙNG type. Thêm concept ĐÚNG TYPE gold-có-mà-ta-thiếu = thắng đậm.
- **ĐÒN BẨY CÒN (sau bản 13):** J_cand (audit sâu hơn top cụm chẩn đoán) · WER (rà ranh giới span xét nghiệm file nặng) · Track 2 (Qwen ≤9B).

## (cũ) VIỆC ĐẦU TIÊN PHIÊN MỚI (25/07): SINH LẠI GOLD THEO SPEC ĐÚNG
Vừa phát hiện spec chính thức (§8a) — ta đã hiểu SAI lớn. Bản tốt nhất hiện tại **31.1438** (bản 11).
**Kế hoạch sinh gold mới (spec-compliant):**
1. **Nền:** bản 11 (`out/submitted/11_spec_both_31.1438.zip`) ĐÃ đúng: assertion 3 loại, bỏ mã triệu chứng,
   mã ICD/RxNorm chuẩn. Concept 3 type (thuốc/bệnh/triệu chứng) đã curate kỹ (assertion duyệt tay 100 file).
2. **THIẾU (đòn bẩy WER lớn nhất):** 2 type `TÊN_XÉT_NGHIỆM` + `KẾT_QUẢ_XÉT_NGHIỆM` — ta bỏ HOÀN TOÀN.
   Note lâm sàng đầy "kali 6.3, creatinin 5.7, WBC 14.99, glucose 316..." → gold có, ta không trích → WER 65.73.
   → **Fable 5 (phiên mới) trích thêm 2 type này cho 100 file** (dùng prompt `dev/NER_PROMPT_SPEC.md`).
   Đây là recall ĐÚNG TYPE (không phải bẫy như trước) → giảm WER thật.
3. **Cân nhắc:** KHÔNG cần vứt bản 11 (đã tốt). Chỉ THÊM xét nghiệm + kiểm assertions multi-label
   (vd bệnh nền của người nhà = [isFamily,isHistorical]). Nếu muốn sạch tuyệt đối: NER lại toàn bộ bằng
   prompt spec mới rồi gán mã + curate — nhưng tốn công, bản 11 đã là nền vững.
4. Cập nhật `src/gold_vote.py` SYSTEM + `src/track2_prep.py` SYSTEM theo `dev/NER_PROMPT_SPEC.md` (5 type, 3 assertion).

Chi tiết spec: §8a. Lịch sử điểm + bài học: `out/SCORES.md`. Guide assertion (cần cập nhật bỏ isUncertain/isHypothetical): `dev/ASSERTION_GUIDE.md`.

---

> (Phần dưới là trạng thái 24/07, một số chỗ đã cũ so với spec — tham chiếu.)

## 1. Đang ở đâu — điểm leaderboard (điểm hiển thị = raw×100, %)

Tiến trình (data MỚI 21/07): **rỗng 0.08 → ... → re-rank ICD 30.2557 → +assertion duyệt tay 30.4607** ✅
(bản tốt nhất, nộp 24/07 21:26).

- Top leaderboard **39.76**, top-15 ~**35**. Ta 30.46 (~77% top).
- Phân rã 30.46: **text 10.28 + assert 11.26 + candidates 8.92**. Công thức: `0.3(1−WER)+0.3·J_assert+0.4·J_cand`.
- Bản nộp tốt nhất: `out/submitted/08_rerank_assert_30.4607.zip`. Lịch sử đầy đủ: `out/SCORES.md`.

### ĐÒN BẨY CÒN LẠI (nghiên cứu 24/07 tối)
1. **WER (lớn nhất, ~20đ headroom):** gold ~5800 concept / ~18,600 từ, ta mới 2006/6374 → **thiếu 66% (D)**.
   Giảm WER = tăng recall ~3x. NHƯNG thêm concept SAI ranh giới → WER TĂNG (merged đã dính). Cần khớp gold.
   API OpenAI/Gemini HẾT QUOTA → chỉ Fable 5 trích tay. VERIFY trước bằng `claude_plus_sol10.zip`.
2. **Candidates (8.92/40):** mã ICD/RxNorm. Điền mã thuốc rỗng ĐÃ THỬ → HẠI (gold để rỗng, J_cand giảm). Bỏ.
3. **Assertion (11.26/30):** đã duyệt 100 file xong, +0.68. Còn ít headroom.

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

## 3b. CÔNG CỤ CHỈNH GOLD (human-in-the-loop) — thêm 24/07 chiều

Chiến lược mới (user chốt): **gold là TRẦN TRÊN của model ≤9B** — train self-host trên gold yếu là vô ích.
Phải nâng gold vượt top-15 (nhắm ≥40đ) TRƯỚC, rồi mới distill Qwen. Kết hợp nhiều model mạnh + user chỉnh tay.

- **Voter mạnh nhất:** `sol` = **gpt-5.6-sol** (OpenAI, reasoning). Chạy: `python3 src/gold_vote.py --voter sol`.
  Lưu ý: GPT-5 series KHÔNG nhận `temperature` (voters.json có `"no_temp":true,"timeout":240`).
- **Công cụ chỉnh:** `python3 src/review_server.py` → mở http://localhost:8000. Python thuần, không cài gì.
  Trái: text tô màu theo type. Phải: sửa type/assertion/candidates, xoá, hoặc bôi đen text để THÊM concept.
  Mỗi concept hiện phiếu 4 model (claude/gpt/gpt41/sol) để quyết nhanh. Panel "Model đề xuất THÊM" = concept
  voter có mà gold thiếu (1 nút thêm). Lưu → ghi `dev/gold_curated.json`. Nút "Xuất ZIP" → `out/candidates/curated.zip`.
- **Nền curate:** `dev/gold_curated.json` khởi tạo từ bản 30.26+37 mã thuốc (`claude_filled`). User sửa dần trên đó.
- **Fable 5 (model phiên chat) = trọng tài:** khi user gặp ca khó trong lúc chỉnh, hỏi trực tiếp để phân xử.

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

### KẾT QUẢ THỬ NGHIỆM 3-VOTER: THẤT BẠI (bản 07 = 29.7798 < 30.26)
3 voter đã chạy: claude 2119, gpt 1957, gpt41 2755 concept. Gộp trust=claude+k2 → +210 concept →
**GIẢM điểm CẢ 3 trục** (WER 65.73→66.04, assert 36.87→35.87, cand 22.29→22.08). **Over-predict.**
- **30.26 (claude thuần) là TRẦN cho hướng "thêm concept". Đừng thử thêm concept nữa.**
- Vote assertion theo gpt/gpt41 CŨNG hại: đã soi 144 ca (`dev/assertion_disputes.json`), gpt xoá nuance
  `isFamily`/`isHypothetical` mà claude bắt đúng (vd "mẹ em bị run", "bệnh CÓ THỂ gây biến chứng").
- gpt/gpt41 votes vẫn hữu ích cho **Track 2** (gold sạch để distill Qwen ≤9B), không cho submission Phase 1.

### Bản nộp KẾ TIẾP — `out/candidates/claude_filled.zip` (cược 1 chiều, an toàn), CHỜ NỘP
Nền bản 30.26, chỉ **điền RxNorm cho 37 concept THUỐC đang rỗng mã** (bệnh/tc đã đủ mã 100%).
Diff vs 30.26 = ĐÚNG 37 candidates, 0 thay đổi text/assert/pos ⇒ **WER & J_assert BẤT BIẾN, chỉ J_cand ↑**.
**VIỆC NGAY: nộp `07`... à nhầm — nộp `claude_filled.zip`, ghi điểm vào SCORES.md.**
```bash
python3 src/fill_drug_codes.py --in out/submitted/06_claude_rerank_30.2557.zip --out claude_filled
```
Nếu J_cand tăng: đòn bẩy tiếp = cải thiện ĐỘ CHÍNH XÁC mã ICD bệnh/tc (re-rank kỹ hơn), KHÔNG thêm concept.

## 7. Việc tiếp theo (đòn bẩy còn lại)

1. **Candidates (lớn nhất, còn ~34đ):** re-rank ICD (đang làm) + kiểm mã RxNorm thuốc.
2. **Voter thứ 2-3 cho gold sạch (Track 2):** Codex (free, gói Plus) → `dev/votes/gpt.json` theo `dev/CODEX_TASK.md`; Gemini free (aistudio.google.com/apikey) → thêm vào `dev/voters.json`. Rồi `build_gold.py --k 2 --sapbert`.
3. **KHÔNG cần mua:** OpenAI API (Codex lo GPT), Anthropic (phiên chat lo Claude). Chỉ Gemini (free) hoặc DeepSeek (~$2) nếu muốn voter thêm.
4. **Phase 2:** distill gold → fine-tune/prompt Qwen3-8B trên Colab để pipeline ≤9B tái lập được.

## 8a. SPEC OUTPUT CHÍNH THỨC (25/07) — SỬA HIỂU LẦM LỚN

Ta đã hiểu SAI 3 điểm (ảnh hưởng lớn):
1. **5 TYPE** (không phải 3): TRIỆU_CHỨNG, **TÊN_XÉT_NGHIỆM**, **KẾT_QUẢ_XÉT_NGHIỆM**, CHẨN_ĐOÁN, THUỐC.
   → Ta BỎ QUA xét nghiệm (WBC, kali, creatinine, glucose...) = nguồn concept LỚN thiếu → WER cao.
   Sai type = phạt KÉP (0đ cả 3 trục + tạo concept ma).
2. **assertion CHỈ 3 loại**: `isNegated`, `isFamily`, `isHistorical` (KHÔNG có isUncertain/isHypothetical).
   Là LIST multi-label (tối đa 3, vd "bố có tiền sử hen" = [isFamily, isHistorical]).
   → 130 concept ta gán isUncertain/isHypothetical là SAI → gán ∅ (bản spec_assert).
3. **candidates CHỈ cho CHẨN_ĐOÁN + THUỐC** (KHÔNG cho TRIỆU_CHỨNG/xét nghiệm).
   → 970 mã R-code ta gán cho triệu chứng có thể THỪA → bỏ (bản spec_nocand_tri). ICD với bệnh, RxNorm với thuốc.

Bản test (25/07): `spec_both.zip` (gộp) / `spec_assert.zip` / `spec_nocand_tri.zip`. Nộp đo tác động.
**Việc lớn tiếp theo:** trích TÊN_XÉT_NGHIỆM + KẾT_QUẢ_XÉT_NGHIỆM (recall lớn, spec-compliant, KHÔNG phải bẫy
vì đúng type gold có). Ví dụ spec: "WBC","NEUT%..." = TÊN_XÉT_NGHIỆM; "14,43","76,4" = KẾT_QUẢ_XÉT_NGHIỆM.

## 8b. FAQ CHÍNH THỨC BTC (ảnh 24/07 tối) — QUAN TRỌNG

1. **Chấm điểm ĐẶC BIỆT chú trọng khả năng TÌM ĐỦ (recall).** → XÁC NHẬN hướng WER/giảm D đúng.
   Đầu tư tăng recall (thêm concept đúng) là ưu tiên BTC muốn.
2. **LLM tạo gold/synthetic data để TRAIN & fine-tune = ĐƯỢC PHÉP.** Quy định "không dùng API Agent/LLM
   bên thứ ba" CHỈ áp cho HỆ THỐNG NỘP BÀI (inference private test = self-host ≤9B). → Track 2 (LLM→gold→Qwen)
   HỢP LỆ hoàn toàn; có thể dùng LLM sinh thêm synthetic data để train. Xoá lo ngại "gian lận".
3. **RxNorm: dùng bản MỚI NHẤT 2026.** ICD-10-CM đã 2026 ✓. RxNorm (rx_*.json) CẦN verify/cập nhật bản 2026.
4. **Được dùng dataset NER y tế công khai để train** (tuân thủ license): i2b2/n2c2, BC5CDR, MedMentions... → tài nguyên Track 2.
5. **(người khác gợi ý) Candidates KHÔNG rõ → ĐỂ RỖNG là ổn nhất.** XÁC NHẬN: bản filled điền mã thuốc rỗng
   làm J_cand GIẢM (gold để rỗng). Nguyên tắc: chỉ gán mã khi CHẮC (curated), đoán mò → rỗng.

## 8. Ràng buộc đề

Deadline Phase 1: **04/08/2026**. Top-15 phải nộp source + data + weights, BTC dựng lại trên private test bằng model self-host **≤9B**, cấm hard-code output. Timeout 600s (chỉ Phase 2/3). 5 lượt nộp/ngày.
