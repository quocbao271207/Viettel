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

## Lượt nộp: HẾT (24/07). Lần cuối = `submitted/07_merged3_29.7798.zip`. Reset mai.
Thứ tự nộp KHUYẾN NGHỊ mai (5 lượt): (1) `curated.zip` (filled + assertion duyệt tay — bản tốt nhất),
(2) `dedupe.zip` (test full vs dedupe, biến số 24%), (3) tuỳ kết quả.

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
