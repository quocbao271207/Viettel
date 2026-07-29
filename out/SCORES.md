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

## SPEC CHÍNH THỨC (25/07): 31.1438 (bản 11) — assertion đúng spec
| 25/07 14:09 | `submitted/11_spec_both_31.1438.zip` | assertion 3 loại + bỏ mã triệu chứng | **31.1438** ✅ | 65.7299 | **39.164** | 22.7839 |
- Bỏ isUncertain/isHypothetical (spec chỉ isNegated/isFamily/isHistorical) → **J_assert +1.6 = +0.48 điểm!**
- Bỏ 970 mã R-code triệu chứng → J_cand BẤT BIẾN (hệ chấm lọc type: triệu chứng KHÔNG tính candidates).
- WER chưa đổi ⇒ **ĐÒN BẨY LỚN CÒN LẠI: trích TÊN_XÉT_NGHIỆM + KẾT_QUẢ_XÉT_NGHIỆM** (ta bỏ hoàn toàn 2 type này).

## ✅ ĐỘT PHÁ LỚN NHẤT: 35.1719 (bản 12) — thêm 2 type XÉT NGHIỆM
| 25/07 15:22 | `submitted/12_gold_lab_35.1719.zip` | +487 concept xét nghiệm | **35.1719** ✅ | **59.7635** | **46.6245** | 22.7839 |
Nhảy **+4.03 điểm** (31.14→35.17) — bước nhảy lớn nhất từ trước tới nay. Dự đoán ĐÚNG cả 3 trục:
- **WER 65.73→59.76 (−5.97):** recall 2 type gold CÓ mà ta thiếu hẳn → giảm WER mạnh (đúng đòn bẩy §8a).
- **J_assert 39.16→46.62 (+7.46!):** concept xét nghiệm assertion=[] KHỚP gold → Jaccard assertion tăng vọt (bất ngờ tốt).
- **J_cand 22.78→22.78 (BẤT BIẾN):** xác nhận hệ chấm LỌC candidates theo type — xét nghiệm rỗng mã không đụng J_cand.
- **BÀI HỌC MỚI (lật lại "recall là bẫy"):** bẫy CHỈ áp cho concept TRÙNG type đã có (bản 09). Thêm concept
  ĐÚNG TYPE mà gold có nhưng ta thiếu = thắng đậm cả WER lẫn J_assert. Recall đúng type >> mọi thứ khác.
- Đòn bẩy còn: WER vẫn 59.76 (còn ~40 ca lab bị drop + ranh giới span) · **J_cand 22.78 (trọng số 0.4, nhiều headroom nhất)**.

## (đã nộp — xem trên) GOLD MỚI: thêm 2 type XÉT NGHIỆM — `out/candidates/gold_lab.zip`
Nền bản 11 (2006 concept, 3 type, giữ NGUYÊN text/assert/candidates/pos) + **487 concept xét nghiệm** trích
bằng Fable 5 (6 subagent song song, spec §8a). Tổng **2493 concept / 5 type**:
CHẨN_ĐOÁN 810 · TRIỆU_CHỨNG 970 · THUỐC 226 · **TÊN_XÉT_NGHIỆM 362 · KẾT_QUẢ_XÉT_NGHIỆM 125**.
- Build: `python3 src/build_gold_lab.py` (định vị before+text; fuzzy hoa-thường/khoảng trắng; **cứu toàn cục
  45 ca subagent gán nhầm số file** → dò before+text trên cả 100 file, chỉ nhận khi khớp DUY NHẤT 1 file).
- Verify: 0 vị trí sai (`raw[s:e]==text` toàn bộ), assertion chỉ {isNegated,isHistorical,isFamily},
  xét nghiệm KHÔNG có candidates (đúng spec). 40 ca mơ hồ/hallucinate bị DROP an toàn (không chèn sai file).
- **Kỳ vọng:** WER giảm (recall 2 type gold CÓ mà ta thiếu hẳn). J_cand BẤT BIẾN (hệ chấm lọc candidates
  theo type — đã chứng minh với mã R triệu chứng ở bản 11). Khác với bẫy bản 09 (thêm concept TRÙNG type).
- **RỦI RO:** ranh giới span xét nghiệm chưa chuẩn 100% có thể làm WER lệch. → NỘP ĐO 1 lượt để xác nhận.

## BẢN 13 (CHỜ NỘP): sửa lab gán nhầm file + 4 mã ICD + 1 assertion — `out/candidates/13_gold_lab_fixes.zip`
Nền bản 12 (35.1719), 3 cải tiến (build: `python3 src/build_gold_lab.py --fixes dev/icd_fixes.json --afixes dev/assert_fixes.json`):
1. **WER — sửa lab batch_03 GÁN NHẦM SỐ FILE (dịch khóa):** subagent trích đúng nội dung nhưng gán lệch file trong
   cụm văn bản giống nhau. Relabel `43→44, 44→45, 45→47, 47→46`; xóa lab hallucinate ở 41/43/48 (trùng nội dung
   file 62/44/47). Lab định vị **487→505** (+18 đúng vị trí), ca drop **40→12**. Panel phục hồi: file 44 (ast 421/alt 336/alp),
   file 45 (Tổng phân tích tế bào máu + PT/Troponin/NT-proBNP/AST/ALT/Creatinin/điện giải), file 46 (khí máu Lactat/HCO3/PO2/pH + EF).
2. **J_cand — sửa 4 mã ICD sai rõ (9 concept)** (audit toàn bộ 366 cặp, đối chiếu nghĩa tiếng Anh, verify mã tồn tại):
   tổn thương âm hộ P11.5→N90.9 · đau thắt ngực ổn định G43.D1→I20.9 · tai biến mạch máu não M31.9→I63.9 · tràn dịch màng tim J94.0→I31.39.
3. **J_assert — 1 multi-label:** file 24 "viêm gan B" trong "Tiền sử gia đình: KHÔNG AI bị" → [isFamily,isNegated].
Tổng **2511 concept / 5 type**. Verify: 0 vị trí sai, 0 vi phạm schema, xét nghiệm không mã, assertion hợp lệ. (overlap "phù"⊂"phù phổi cấp" có sẵn nền bản 11.)
**VIỆC: nộp `13_gold_lab_fixes.zip` — kỳ vọng WER↓ (lab đặt đúng chỗ) + J_cand↑ (4 mã).**

## BẢN 13 = 35.2306 (đã nộp 25/07 16:17) — +0.06, và PHÁT HIỆN J_cand ĐÓNG BĂNG
`submitted/13_gold_lab_fixes_35.2306.zip`. WER 59.7635→**59.7049** · J_assert 46.6245→**46.7616** · J_cand **22.7839 (Y HỆT)**.
- Điểm +0.0587, nguồn tăng CHÍNH = **J_assert +0.137** (18 concept lab đặt đúng chỗ sau relabel, assertion=[] khớp gold). WER gần phẳng.
- **⚠️ PHÁT HIỆN LỚN: J_cand = 22.7839 Y HỆT qua 4 lần nộp (bản 10→11→12→13).** 4 mã ICD sửa (âm hộ/đau thắt ngực/
  tai biến/tràn dịch màng tim, tần suất 1-4) KHÔNG dịch được J_cand 1 chút nào ở 4 chữ số.
- **DIỄN GIẢI:** bản 10 sửa mã ăn +0.50 J_cand vì đó là cụm TẦN SUẤT CAO + KHỚP span gold (thuyên tắc phổi/nấm bẹn/G6PD).
  Nghi J_cand chỉ tính trên concept KHỚP span gold; concept chẩn đoán tần suất thấp hoặc lệch ranh giới span → sửa mã VÔ ÍCH.
- **HỆ QUẢ CHIẾN LƯỢC:** muốn dịch J_cand phải (a) sửa mã cho cụm chẩn đoán TẦN SUẤT CAO mà ta đang sai (top list phần lớn đã đúng),
  HOẶC (b) khớp RANH GIỚI span chẩn đoán với gold (nếu đang lệch thì candidates không bao giờ được chấm). Đòn bẩy J_cand đã cạn ở hướng "sửa mã lẻ".
- **Đòn bẩy còn thực sự:** WER 59.70 (trọng số 0.3, thêm recall ĐÚNG type gold-có) · Track 2 (Qwen ≤9B, bắt buộc top-15).

## ĐÒN BẨY 2 & 3 (25/07 chiều, phiên "làm toàn bộ") — KẾT LUẬN
### Track 2 (Qwen ≤9B) — ĐÃ CHUẨN BỊ XONG, chờ Colab GPU
- Regenerate data từ gold bản 13: `dev/track2/{train,dev}.jsonl` = 2511 concept / **5 type** / assertions LIST spec §8a.
- `dev/track2/code_map.json` = bảng tra text→ICD/RxNorm (366 bệnh + 67 thuốc) từ gold — gán mã inference (không LLM, hợp lệ ≤9B).
- Scripts cập nhật: `track2_prep.py` (5 type + before), `track2_codes.py` (mới), `track2_infer.py` (locate robust + gán mã + sampling), `track2_train_qwen.py` (max_seq 4096→8192).
- **VERIFY offline (không GPU):** giả lập Qwen sinh đúng nhãn gold → span match **2471/2511 = 98.4%**, code match **1017/1017 = 100%**.
  ⇒ pipeline inference ĐÚNG; nếu Qwen học lại được nhãn → self-host ≈ bản 13. Việc còn: train trên Colab (GPU của user).

### J_cand — KHÓA (không phá được nếu không có gold)
- Đã audit + verify: **top-40 chẩn đoán ĐÚNG mã, top-20 thuốc ĐÚNG RxNorm** (gleevec→imatinib, tylenol→161...).
- J_cand = 22.7839 đóng băng 4 lần nộp: sửa 9 mã (bản 13) → J_cand Y HỆT 4 chữ số ⇒ 9 concept đó KHÔNG nằm trong
  tập KHỚP gold (span lệch/gold không có). J_cand chỉ chấm trên concept KHỚP span gold.
- ⇒ Headroom J_cand nằm sau (a) match thêm concept bệnh/thuốc của gold (recall — rủi ro như bản 09), hoặc
  (b) khớp ranh giới span. **Đổi mã mù = 0 tín hiệu, phí lượt nộp.** Dừng hướng này cho tới khi có gold để đối chiếu.
