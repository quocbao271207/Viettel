# SỔ NỘP BÀI — Viettel AI Race 2026, Bài 2

> **Luật của sổ này: ghi NGAY sau mỗi lượt nhận điểm, không để dồn.**
> Cả chiến lược dự án được lái bằng **chênh lệch giữa các lượt nộp**, không phải điểm tuyệt đối.
> Mất một dòng là mất một quan sát không mua lại được.
>
> Công cụ ghi tự động (tính Δ theo trục, lợi ích biên, kiểm số học, tự kết luận):
> ```
> python3 -m src.harness.log_submission --ban <tên> --nen <tên nền> \
>     --diem 38.6 --wer 55.9 --assert 50.1 --cand 25.9 --gio 13:23 \
>     --nhan-xet "vì sao ăn/lỗ"
> ```
> Bảng điền tay: `out/RESULTS.csv` · Đọc & diễn giải: `python3 -m src.harness.score_report`

`final = 0.3·(1−WER) + 0.3·J_assert + 0.4·J_cand` — mọi chỉ số trên trang nộp là **phần trăm**.

---

## 📊 TOÀN BỘ LƯỢT NỘP

### Giai đoạn 1 (23–29/07) — dựng nền, xem `SCORES.md` để biết chi tiết

| ngày | bản | điểm | WER | J_assert | J_cand | ghi nhận |
|---|---|---|---|---|---|---|
| 23/07 | `00_empty` | 0.0773 | 100 | 0 | 0.19 | candidates KHÔNG còn free trên data mới |
| 23/07 | `01_drugs` | 3.9814 | 96.19 | 2.54 | 5.19 | validate toàn bộ cơ chế: NER+RxNorm+offset đều khớp |
| 23/07 | `02_drugs+dx` | 8.9788 | 89.31 | 9.86 | 7.04 | NER chính xác là chìa khoá |
| 23/07 | `03_sym_rule` | 15.4700 | — | — | — | pipeline rule |
| 23/07 | `04_claude_full` | 24.1900 | 65.73 | 36.87 | ~7 | LLM extraction >> pipeline rule |
| 24/07 | `05_claude_dotted` | 27.2600 | 65.73 | 36.87 | 14.80 | **ICD PHẢI CÓ DẤU CHẤM** — gấp đôi J_cand |
| 24/07 | `06_claude_rerank` | 30.2557 | 65.73 | 36.87 | 22.29 | re-rank mã ăn +3đ, rồi trần |
| 24/07 | `07_merged3` | 29.7798 | 66.04 | 35.87 | 22.08 | ❌ gộp 3 voter thô → over-predict |
| 24/07 | `08_rerank_assert` | 30.4607 | 65.73 | 37.55 | 22.29 | assertion duyệt tay +0.205 |
| 25/07 | `09_assert_sol_fable` | 30.3801 | 65.65 | 37.35 | 22.18 | ❌ +216 concept từ 1 model |
| 25/07 | `10_cand_fix` | 30.6591 | 65.73 | 37.55 | 22.78 | sửa 9 mã ICD sai ăn +0.20 |
| 25/07 | `11_spec_both` | 31.1438 | 65.73 | 39.16 | 22.78 | bỏ isUncertain/isHypothetical: +0.48 |
| 25/07 | `12_gold_lab` | 35.1719 | 59.76 | 46.62 | 22.78 | **+4.03** — thêm 2 type xét nghiệm |
| 25/07 | `13_gold_lab_fixes` | 35.2306 | — | — | — | sửa lab gán nhầm file |
| 29/07 | `14_repeat` | **36.4914** | 58.2207 | 48.3759 | 23.6121 | +313 lần nhắc lặp — **nền của cả ngày 30/07** |
| 29/07 | `15_repeat2` | 36.4164 | — | — | — | ❌ cụm 1 âm tiết + biến thể hoa/thường |
| 29/07 | `16_reextract` | 35.8785 | 58.7368 | 47.0371 | 23.4710 | ❌❌ sinh tồn + từ chung chung, **WER TĂNG** |
| 29/07 | `17_reextract_clean` | 35.9273 | 58.7534 | 47.2163 | 23.4710 | ❌ trích lại concept "cụ thể" |

### Giai đoạn 2 (30/07) — harness V2, 17 lượt nộp

| # | giờ | bản | điểm | WER | J_assert | J_cand | kết luận |
|---|---|---|---|---|---|---|---|
| 1 | 10:25 | `21_assert_consensus` | 36.2479 | 58.2207 | 47.5642 | 23.6121 | ❌ −0.24 · **KIỂM CHỨNG METRIC** |
| 2 | 10:40 | `23_span_fix` | 36.7829 | 57.3953 | 48.3247 | 23.7601 | ✅ +0.29 · phá trần bản 14 |
| 3 | 10:44 | `36_span_fix_k1` | 36.9103 | 57.0053 | 48.2650 | 23.8309 | ✅ +0.13 · liều mạnh vẫn tốt |
| 4 | 11:04 | `42_tighten` | 36.8179 | 57.1576 | 48.1095 | 23.8309 | ❌ −0.09 · agent kém hơn voter |
| 5 | 11:05 | `38_spank1_prune` | 37.0865 | 56.9945 | 48.5007 | 24.0865 | ✅ +0.18 · **đãi bỏ ăn điểm** |
| 6 | 11:06 | `48_harmonize_safe` | 36.6490 | 57.7208 | 48.1095 | 23.8309 | ❌ −0.26 · đồng bộ về NGẮN là sai hướng |
| 7 | 11:12 | `52_harmonize_longer` | 37.0212 | 56.6355 | 48.2650 | 23.8309 | ✅ +0.11 · đảo hướng đúng, J phẳng |
| 8 | 11:16 | `57_best_plus_longer` | 37.1974 | 56.6247 | 48.5007 | 24.0865 | ✅ **cộng dồn khớp tới từng chữ số** |
| 9 | 11:19 | `58_stack_prunek2` | 37.3091 | 56.4993 | 48.7643 | 24.0741 | ✅ +0.11 |
| 10 | 11:20 | `60_longer_win25` | 37.2010 | 56.6512 | 48.5391 | 24.0865 | ✅ cửa sổ 25 nhỉnh hơn 45 |
| 11 | 11:39 | `63_prune_L3` | 37.3972 | 56.5178 | 48.5986 | 24.4324 | ✅ bỏ 65 |
| 12 | 11:39 | `64_prune_L4` | 37.2692 | 56.8033 | 48.5167 | 24.3881 | ❌ bỏ 145 = quá liều |
| 13 | 11:42 | `65_prune_onesyl` | 36.5947 | 58.0282 | 47.4930 | 24.3881 | ❌❌ −0.71 · cụm 1 âm tiết CÓ trong gold |
| 14 | 11:51 | `72_kcode_2` | 34.2754 | 56.8033 | 48.5167 | 16.9035 | ❌❌ −3.12 · **gold có ĐÚNG 1 mã** |
| 15 | 11:56 | `76_best_aug_k2` | 38.2704 | 55.3011 | 49.8222 | 24.7851 | ✅ **+0.87 · cả ba trục** |
| 16 | 13:22 | `80_aug4_k2` | 38.1800 | 55.4950 | 49.7281 | 24.7751 | ❌ −0.09 · cặp voter mới yếu hơn |
| 17 | 13:23 | `82x_cleanroom4_k2` | **38.6460** | 55.9124 | 50.1717 | **25.9205** | 🏆 **TỐT NHẤT** · clean-room thuần |

**Tiến trình 30/07: 36.4914 → 38.6460 (+2.1546 sau 17 lượt).**

---

## 🧠 ĐÁNH GIÁ — những gì 17 lượt nộp này dạy được

### 1. Mô hình metric ĐÚNG (bản 21, một lượt nộp mua được sự chắc chắn)
Bản 21 chỉ đổi `assertions` ⇒ WER và J_cand **phải** bất biến. Chúng bất biến tới từng chữ số.
Xác nhận công thức, khoá ghép concept, và mọi suy luận dựng trên đó:
- **gold ≤ ~4000–4600 concept** (không phải 5400 như ước tính cũ)
- **ngưỡng hoà vốn khi BỎ concept: `h* = J/(1+J)` = 32.6%**

*Mẹo dùng lại được:* bản chỉ đổi `candidates` cũng có WER/J_assert bất biến — dùng bất biến này
để **truy ngược nền thật** của một lượt nộp khi nghi gán nhầm kết quả (đã dùng để phát hiện
ảnh của bản 63/64 bị gán ngược).

### 2. NGUỒN BẰNG CHỨNG quyết định, không phải hướng đi
Đây là bài học lớn nhất. Cùng một việc "sửa ranh giới span", kết quả trái ngược tuỳ nguồn:

| nguồn bằng chứng | kết quả đo được |
|---|---|
| **đồng thuận 2 voter độc lập** | **+0.42** (ranh giới) · **+0.87** (thêm concept) |
| oracle nội bộ (đoạn văn trùng), đúng hướng | +0.11 |
| một agent soi kỹ, có tham chiếu nhãn cũ | **−0.09** |

`HANDOFF.md` từng chốt *"mọi concept do LLM tự nghĩ thêm đều lỗ, dù duyệt kỹ đến đâu"* —
**sai về nguyên nhân**. Ba lần lỗ (bản 15/16/17) đều là phán đoán đơn lẻ; hai lần lời
(bản 14, 76) đều có bằng chứng độc lập bảo chứng.

### 3. Oracle nội bộ chỉ ra CHỖ sai, KHÔNG chỉ ra HƯỚNG sửa
Bộ data có file dùng lại nguyên xi đoạn của nhau (file 6 vs 11 giống 78.5%). Gold phải gán nhãn
nhất quán ⇒ mọi bất đồng là lỗi của ta. Nhưng **chọn bản nào** thì phải ĐO:
đồng bộ về NGẮN → −0.26; đảo lại về DÀI → +0.11. Đừng suy từ thí nghiệm khác sang.

### 4. Cải tiến TRỰC GIAO thì CỘNG DỒN, và dự đoán được
Bản 38 ăn điểm hoàn toàn qua **J** (WER phẳng); bản 52 ăn hoàn toàn qua **WER** (J phẳng).
Dự phóng `36.9103 + 0.1762 + 0.1109 = 37.1974` · thực tế **37.1974**.
⇒ Mỗi cải tiến chỉ cần đo RIÊNG một lần rồi cộng, không phải nộp thử từng tổ hợp.
Điều kiện: hai thay đổi không đụng cùng concept — kiểm trước bằng `src/harness/diff.py`.

### 5. Đãi bỏ ăn điểm, nhưng có ngưỡng và phụ thuộc TYPE
- Bỏ 49 → +0.176 · bỏ thêm 24 → +0.112 · bỏ 145 → **−0.04** (quá liều, ngưỡng ~65).
- Quy luật: đãi bỏ **luôn** làm J_cand tăng, **luôn** làm WER + J_assert giảm.
  Bỏ `CHẨN_ĐOÁN`/`THUỐC` thì lời; bỏ `TRIỆU_CHỨNG`/xét nghiệm thì lỗ (chúng CÓ trong gold).
- **Cụm 1 âm tiết (`sốt`/`nôn`/`ho`) CÓ THẬT trong gold** — bỏ 83 cụm làm WER vọt lên 58.03,
  lỗ 0.71. Bài học bản 15 đúng cho việc THÊM chúng, sai cho việc BỎ cụm đã có.

### 6. `candidates` của gold là MỘT mã, không phải danh sách
J_cand bám 22–24 suốt 10 lượt nộp qua đủ mọi can thiệp — nghi là hiện vật cấu trúc
(nếu gold liệt k mã mà ta đưa 1 mã đúng thì Jaccard = 1/k; k=4 cho 0.25, ta ở 0.244).
Bản 72 thêm 1 mã anh em cho 727 chẩn đoán → J_cand **tụt 30.7%**. Giả thuyết bị bác bỏ dứt khoát.
⇒ Trần J_cand là THẬT. Nó chỉ dịch khi **span chẩn đoán khớp gold nhiều hơn** — và đúng vậy:
clean-room 4 voter đẩy J_cand lên **25.92**, phá mốc sau 10 lượt.

### 7. Thêm voter giúp bằng cách DỰNG LẠI, không phải nới ngưỡng
- Vá 64 concept từ cặp voter mới vào nền cũ → **−0.09** (cặp không chứa a/b là tín hiệu yếu hơn).
- Dựng lại clean-room từ cả 4 phiếu → **+0.38**, J_cand +1.14.

### 8. Trung bình theo FILE khuếch đại lỗi ở file THƯA
`text_score` và `assertions_score` là trung bình **không trọng số theo file** ⇒ file 3 concept
ảnh hưởng ngang file 60 concept. Bản 16 và 17 đều trích lại đúng "30 file mật độ thấp nhất" —
đổ concept mới vào chính nơi mỗi sai sót bị khuếch đại mạnh nhất.

---

## 🔧 HAI LỖI BỊ BẮT BỞI KIỂM THỬ ĐẦU-CUỐI (không đọc code nào thấy)

1. **Luật đãi bỏ coi "file voter CHƯA CHẠY" = "không ai xác nhận"** → suýt xoá `thiếu men G6PD`
   17 lần ở file 1. Sửa: cổng `covered`, chỉ đãi bỏ ở file mà MỌI voter đều có phiếu.
2. **Đối chiếu cụm bề mặt CHÍNH XÁC quá khắt khe**: voter trích `bệnh gút`, nền có `gút`
   → bị tính là không ai xác nhận. Suýt xoá `xơ gan`/`vảy nến`/`amoxicillin`.
   Sửa: đối chiếu thêm bằng CHỒNG LẤN VỊ TRÍ. Số bỏ từ 256 xuống 49.

Cả hai chỉ lộ ra khi **chạy đầu-cuối rồi SOI TAY danh sách bị đụng**. Đọc code không thấy.

Và một lỗi quy trình: **gán nhầm ảnh kết quả cho bản 63/64**, phải truy ngược bằng bất biến
WER mới phát hiện. Đó là lý do sổ này tồn tại — ghi ngay lúc nộp thì không xảy ra.

---

## 📌 TRẠNG THÁI

- **Tốt nhất: `82x_cleanroom4_k2` = 38.6460** (clean-room 4 voter, k≥2, 2932 concept)
- Top leaderboard **50** · top-15 ~35 · deadline Phase 1 **04/08/2026**
- 4 voter clean-room đủ 100/100 file: `dev/votes_v2/{a,b,c,d}.json`
- ⚠️ **Track 2 (Qwen ≤9B) CHƯA CHẠY** — bắt buộc để vào top-15, cần GPU Colab.
  `dev/track2/` hiện sinh từ bản 14, thua bản tốt nhất 2.15 điểm ⇒ nên sinh lại từ `82x`.
- ⛔ API ngoài đã chết: `OPENAI_API_KEY` 401 · `GEMINI_API_KEY` 429 hết credit.
