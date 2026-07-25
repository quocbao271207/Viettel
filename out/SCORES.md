# Lịch sử nộp (data mới 21/07) — điểm hiển thị là %, top hiện 39.76

| Ngày | Bản | Nội dung | Điểm | WER | J_assert | J_cand |
|------|-----|----------|------|-----|----------|--------|
| 23/07 14:18 | `submitted/00_empty_0.0773.zip` | rỗng `[]` | **0.0773** | 100 | 0 | 0.19 |
| 23/07 20:42 | `submitted/01_drugs_3.9814.zip` | thuốc + RxNorm | **3.9814** | 96.19 | 2.54 | 5.19 |
| 23/07 21:46 | `submitted/02_drugs+dx_8.9788.zip` | + chẩn đoán (curated ICD) | **8.9788** | 89.31 | 9.86 | 7.04 |
| 23/07 | `submitted/03_sym_rule_15.4700.zip` | + triệu chứng (rule) | **15.47** | — | — | — |
| 23/07 | `submitted/04_claude_full_24.1900.zip` | NER Claude LLM, ICD KHÔNG chấm | **24.19** | 65.73 | 36.87 | ~7 |
| 24/07 | `submitted/05_claude_dotted_27.2600.zip` | như trên, ICD CÓ CHẤM | **27.26** | 65.73 | 36.87 | 14.80 |
| 24/07 16:22 | `submitted/06_claude_rerank_30.2557.zip` | + re-rank ICD bằng 5 agent LLM | **30.2557** | 65.7299 | 36.8652 | **22.2878** |
| 24/07 16:54 | `submitted/07_merged3_29.7798.zip` | gộp 3 voter (+210 concept) | **29.7798** ↓ | 66.0407 | 35.8719 | 22.0761 |

**BÀI HỌC bản 07 (GIẢM):** thêm 210 concept từ gpt+gpt41 → over-predict, tệ CẢ 3 trục (WER↑, assert↓,
cand↓). Kết luận: **30.26 (claude thuần) là trần cho hướng "thêm concept". Đòn bẩy là CHẤT LƯỢNG, không
phải SỐ LƯỢNG.** Vote assertion theo gpt cũng có hại (gpt xoá nuance isFamily/isHypothetical claude bắt đúng).

Phân rã 30.26 = text 10.28 + assert 11.06 + cand 8.92. Re-rank ICD ăn +3.0đ toàn bộ ở trục
candidates (14.80→22.29). Text/assert giữ nguyên vì NER không đổi ⇒ đòn bẩy kế: ĐỘ PHỦ NER
(claude 2119 concept / gold ~6000+) — đang chạy voter gpt (gpt-4o) + gpt41 (gpt-4.1) để gộp 3 bộ.

Phân rã 8.98 = text 3.21 + assert 2.96 + cand 2.82. Thêm 269 concept bệnh (chưa mã) ăn điểm
CẢ 3 trục ⇒ **NER chính xác là chìa khoá**. Ngân sách từ gold ≈ 4171; mới trích ~918 (22%).

| 24/07 20:49 | `curated.zip` (filled+assertion) | +37 mã thuốc +126 assertion | **30.2627** | 65.7299 | **37.5484** | 21.793 |

**BÀI HỌC bản curated:** tách bạch 2 hiệu ứng so 30.2557:
- **Assertion ĐÚNG**: J_assert 36.87→**37.55 (+0.68)** — xác nhận "bệnh nền→isHistorical" đúng. GIỮ.
- **Điền mã thuốc SAI**: J_cand 22.29→21.79 (**−0.49**) — gold để RỖNG cho paracetamol/insulin/Vastarel...
  ta điền mã → J rớt 1→0. BỎ 37 mã thuốc.
- Hai hiệu ứng triệt tiêu (+0.007). ⇒ Bản `rerank_assert` = 30.2557 + assertion, BỎ mã thuốc → kỳ vọng ~30.46.

| 24/07 21:26 | `submitted/08_rerank_assert_30.4607.zip` | nền 30.2557 + 128 assertion duyệt tay | **30.4607** ✅ | 65.7299 | **37.5484** | 22.2878 |

**BẢN TỐT NHẤT = 30.4607.** Duyệt assertion 100 file (Fable 5) → +0.205 điểm thực. WER & J_cand bất biến.
Phân rã: text 10.28 + assert **11.26** + cand 8.92. Đòn bẩy còn: **WER (giảm D, cần +recall ~3x)** > candidates.

## Ứng viên CHỜ NỘP (ưu tiên)
- **`candidates/claude_plus_sol10.zip`** — VERIFY WER: +196 concept sol ở 10 file. Nếu WER < 65.73 ⇒ mật độ
  cao đúng hướng, đáng trích dày 100 file (gold ~5800 concept, ta mới 2006). Nếu WER tăng ⇒ dừng hướng này.
- `dedupe.zip` — test full vs dedupe (góc nhìn ngược: dedupe thấp hơn ⇒ gold trích dày).

## Ứng viên CHỜ NỘP
- `candidates/dedupe.zip` — **THÍ NGHIỆM full vs dedupe** (chưa từng test). Nền 30.26 nhưng mỗi (text,type)
  chỉ giữ 1 lần/file → 1526 concept (bỏ 480 bản lặp = 24%). Mã giống hệt full ⇒ so sánh sạch.
  - dedupe > 30.26 → gold TÍNH 1 LẦN (nhất là bài giáo dục lặp từ khoá) → build gold theo hướng dedupe.
  - dedupe < 30.26 → gold trích FULL (đúng spec) → giữ nguyên, đừng dedupe.
  Bối cảnh: WER=66 bất thường cao; nghi do trích full bài giáo dục (file 1 lặp "thiếu men G6PD" 16 lần).
- `candidates/claude_filled.zip` — nền bản 30.26, **điền RxNorm cho 37 concept THUỐC đang rỗng mã**
  (paracetamol→161, Omez→omeprazole, Vastarel→trimetazidine, cotrimoxazol, Furosemid, các antacid...).
  KHÔNG đụng text/type/assertion/position (diff kiểm = 0) ⇒ **WER giữ 65.73, J_assert giữ 36.87, chỉ J_cand
  có thể tăng — cược 1 chiều.** Bệnh/triệu chứng đã đủ mã 100%; chỉ thuốc còn rỗng 76→39.
  Tạo lại: `python3 src/fill_drug_codes.py --in out/submitted/06_claude_rerank_30.2557.zip --out claude_filled`

## Quy ước thư mục
- `submitted/NN_tên_điểm.zip` = bản ĐÃ NỘP, đánh số theo thứ tự nộp, đuôi = điểm nhận được.
- `candidates/` = bản CHƯA NỘP đang chờ (hiện trống — bản kế: `merged3_rerank.zip` từ gộp 3 voter).
- Đồ data-cũ (trước 21/07) + probe + nhãn tay: đã dời sang `archive/` ở gốc repo.

## Tạo lại bản nộp
Pipeline hiện tại: xem `HANDOFF.md` §"Pipeline bản nộp KẾ TIẾP" + `src/README.md`.
(Pipeline rule cũ: `extract.py` / `extract_all.py` / `finalize_submission.py` — legacy.)

## Ghi chú
- `baseline_all.json` = output NER pipeline rule (tham chiếu; nguồn chính giờ là `dev/votes/`).
- Index SapBERT: `data/icd10_sapbert.pt` (220MB, KHÔNG push git — tái tạo bằng `src/test_sapbert.py`).

## CHỐT: 30.4607 (bản 08) là TỐI ƯU Phase 1
| 25/07 12:54 | `submitted/09_assert_sol_fable_30.3801.zip` | +216 concept (sol+fable dày) | **30.3801** ↓ | 65.6531 | 37.3509 | 22.1769 |

**BÀI HỌC CUỐI — recall là BẪY:** thêm concept sol+fable giảm WER (65.73→65.65) NHƯNG J_assert
(37.55→37.35) và J_cand (22.29→22.18) giảm nhiều hơn → điểm GIẢM 30.46→30.38.
Công thức: WER chỉ 0.3, J_assert+J_cand = 0.7. Concept thừa (rỗng mã, assertion thô) hại > lợi.
⇒ KHÔNG thêm concept nữa. **Bản 08 (30.4607) là trần Phase 1.** Đòn bẩy còn lại: CHẤT LƯỢNG mã
(J_cand) + Track 2 (Qwen ≤9B, bắt buộc top-15).

## ĐỘT PHÁ CANDIDATES: 30.6591 (bản 10)
| 25/07 13:11 | `submitted/10_cand_fix_30.6591.zip` | sửa 3 cụm mã ICD sai | **30.6591** ✅ | 65.7299 | 37.5484 | **22.7839** |
Chỉ sửa 9 mã (thuyên tắc phổi Q35.9→I26.99, nấm bẹn B35.3→B35.6, G6PD D55.0) → J_cand +0.50 = +0.20 điểm!
⇒ **CANDIDATES là đòn bẩy LỚN.** Sửa mã ICD SAI cho cụm phổ biến ăn nhiều điểm. Audit sâu top cụm.
