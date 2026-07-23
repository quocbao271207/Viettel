# Viettel AI Race 2026 — Bài 2 — Code

Chiến lược đầy đủ: **[STRATEGY.md](STRATEGY.md)**. File này chỉ mô tả code.

⚠️ **Deadline là 04/08 (không phải 30/07). Đề được NÂNG CẤP ngày 21/07** — xem STRATEGY.md §1.1.

## Chạy

```bash
python3 src/gazetteer.py      # dựng gazetteer RxNorm + ICD-10 (tự selftest)
python3 src/sections.py       # bóc cấu trúc văn bản (tự kiểm 100% offset)
python3 src/extract.py        # -> out/baseline.json + out/submission.zip
python3 src/probes.py --list  # xem các phép dò cơ chế chấm
python3 src/probes.py P1      # -> probes/P1.zip  (NỘP CÁI NÀY TRƯỚC)
python3 src/evaluate.py out/baseline.json dev/gold.json   # cần dev set tự gán nhãn
```

Toàn bộ chạy cục bộ trong ~1 giây, không cần GPU, không gọi API.

## Các file

| File | Việc | Trạng thái |
|---|---|---|
| `src/sections.py` | Bóc section/sub-header/bullet + offset tuyệt đối | ✅ 2.217/2.217 offset khớp |
| `src/gazetteer.py` | RxNorm (SCD/IN/brand) + ICD-10-CM offline | ✅ selftest 8/8 SCD + IN fallback |
| `src/extract.py` | Pipeline trích xuất THUỐC + RxNorm | ✅ 153 thuốc, 100% có mã |
| `src/evaluate.py` | Cài lại metric để đo cục bộ | ⚠️ tái dựng — xem cảnh báo bên dưới |
| `src/probes.py` | Sinh 11 phép dò cơ chế chấm | ✅ P1 sẵn sàng nộp |
| `src/test_sapbert.py` | Thử khớp chéo ngôn ngữ VI→ICD-10 | 🔬 thí nghiệm |
| `colab/build_icd10_vi.py` | Dựng gazetteer ICD-10 tiếng Việt (cần GPU) | 📋 chưa chạy |

## Dữ liệu (`data/`, không commit)

| Nguồn | Số lượng | Lấy từ |
|---|---|---|
| ICD-10-CM 2026 | **74.719** mã | CMS, free, không cần đăng ký |
| RxNorm SCD | 17.552 | RxNav `/REST/allconcepts?tty=SCD` |
| RxNorm IN | 14.648 | RxNav |
| RxNorm SBD | 9.696 | RxNav — suy ra brand→hoạt chất từ `[Brand]` trong tên |

Tất cả tải bằng API/HTTP công khai, không cần license. Chạy lại: `python3 src/gazetteer.py`.

## Ba điều dễ làm hỏng bài

**1. `position` là chỉ số ký tự NFC trên file đọc THÔ.** Đã truy ngược từ ví dụ đề
(delta tăng đúng +2 mỗi mục danh sách → input thật là list xuống dòng thụt lề 2 space).
`raw[start:end] == text`, `end` exclusive. **Không** strip, **không** chuẩn hoá lại.

**2. Trích thừa cho điểm ÂM.** `text_score = mean(1-WER)`, `WER=(S+D+I)/N` không chặn trên.
Đo bằng `src/evaluate.py`: over-predict 4× → **−42.50**; 8× → **−171.25**. Precision > Recall.

**3. Sai type bị phạt kép** (đề nói rõ: tính 2 lần, mỗi lần 0đ cả 3 metric).

## ⚠️ Cảnh báo về `src/evaluate.py`

Đây là **bản tái dựng theo mô tả bằng lời của đề**, không phải code gốc BTC. Hai điều
đề không nói rõ và đã để thành tham số:
- concept dự đoán ghép với GT theo `text_type` / `pos_type` / `text_pos_type`?
- `text_score` tính WER trên chuỗi nối (`concat`) hay theo từng concept (`per_concept`)?

Bằng chứng cho thấy `concat` toàn cục **SAI**: ở chế độ đó, "đúng text sai type" vẫn cho
`text=1.000`, trái với đề. Dùng probe P3/P6 để chốt rồi khoá cấu hình lại.

## Kết quả thí nghiệm (đã chạy thật)

**Đã chứng minh — span CHẨN_ĐOÁN là thuật ngữ ICD-10-CM dịch máy:** đối chiếu tay
**12/12 khớp nguyên văn** với mô tả CMS chính thức (`bệnh thận mạn, không đặc hiệu`
= "Chronic kidney disease, unspecified" = N18.9). Đuôi ", không đặc hiệu" là dấu vân tay.

**RxNorm: tái tạo 8/9 gold của ví dụ đề, end-to-end** (`resolve_rxnorm`):

| Text | Ra | Gold | |
|---|---|---|---|
| `metoprolol succinate xl 50 mg po daily` | 866436 | 866436 | ✅ nhờ fallback ER |
| `amlodipine 10 mg po daily` | 308135 | 308135 | ✅ |
| `aspirin 81 mg po daily` | 243670 | 243670 | ✅ |
| `pravastatin 40 mg po daily` | 904475 | 904475 | ✅ nhờ fallback muối |
| `docusate sodium 100 mg po bid` | 1099279 | 1099279 | ✅ |
| `clonazepam 0.5 mg po qam:prn` | 197527 | 197527 | ✅ |
| `acetaminophen 325-650 mg po q6h:prn` | 313782 | 313782 | ✅ |
| `nystatin oral suspension 5 ml po qid:prn` | 7597 | 7597 | ✅ fallback IN |
| `senna 8.6 mg po bid:prn` | — | 312935 | ❌ RxNorm gọi là `sennosides, USP` |

**Cầu nối VI→ICD-10 CHƯA giải xong** — việc còn lại lớn nhất. Đã đo:

| Cách | Kết quả | Kết luận |
|---|---|---|
| `Helsinki-NLP/opus-mt-en-vi` dịch EN→VI | fuzzy **42/100**, 0/10 đạt ngưỡng; sinh rác lặp vô hạn | ❌ vô dụng với thuật ngữ y khoa |
| `VietAI/envit5-translation` | vỡ với `transformers 5.7` (tokenizer T5 cũ) | ❌ cần transformers<5 |
| `paraphrase-multilingual-MiniLM-L12-v2` | top-1 **1/10**, top-5 3/10 | ❌ không đủ chuyên y sinh |
| **`SapBERT-UMLS-2020AB-all-lang-from-XLMR`** | **top-1 6/12, top-5 9/12** (`src/test_sapbert.py`) | 🔶 tốt để SINH ỨNG VIÊN, chưa đủ để quyết định |

SapBERT sai theo kiểu **cận nghĩa**, không phải sai bậy: `bệnh gút không đặc hiệu` → "Idiopathic
gout, unspecified site" (M1000) thay vì "Gout, unspecified" (M109). Đó là tín hiệu tốt.

**Hướng đi tiếp (theo thứ tự ưu tiên):**
1. **Thu hẹp không gian ứng viên.** 74.719 mã gồm phần lớn là mã chấn thương S/T có
   laterality/encounter — không bao giờ xuất hiện. Lọc còn ~10K mã hợp lý sẽ nâng top-1 mạnh.
2. **SapBERT top-5 + LLM rerank.** top-5 đã là 9/12; để LLM ≤9B chọn 1 trong 5 là bài dễ.
3. **LLM dịch VI→EN + khớp CHÍNH XÁC** với 74.719 mô tả. Chỉ ~2.500 cụm cần dịch
   (rẻ hơn dịch cả 74.719 mã), và khớp phía tiếng Anh là exact nên không cần fuzzy.

⚠️ **Đừng dự đoán top-3 để "ăn may" Jaccard.** `candidates` chấm bằng Jaccard: nếu gold có
1 mã và ta trả 3 mã thì J = 1/3. Với top-1=50%, E[J]=0.50; trả top-3 thì E[J]≈0.67/3≈0.22.
**Trả top-1 luôn tốt hơn.**

## Việc tiếp theo

1. **Nộp `probes/P1.zip` ngay** — 1 lượt, trả lời câu đắt nhất (concept miss bị 0 hay được J=1).
2. **Gán nhãn dev set 30 file** vào `dev/gold.json` (cùng format `out/baseline.json`).
3. **Giải nốt cầu nối VI→ICD-10** (xem bảng trên).
4. **21/07: đọc đề mới ngay** — sẽ có thêm type XÉT_NGHIỆM / THÔNG_TIN_BỆNH_NHÂN + relations.
