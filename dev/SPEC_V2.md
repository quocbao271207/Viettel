# SPEC V2 — LUẬT GÁN NHÃN ĐÓNG BĂNG (29/07/2026)

> Đây là **nguồn sự thật DUY NHẤT** cho mọi lần sinh data. Muốn đổi hành vi pipeline thì
> sửa file này rồi chạy lại — **KHÔNG sửa tay JSON đầu ra**. Mọi luật dưới đây đều gắn với
> bằng chứng từ một lượt nộp đã trả giá (xem `out/SCORES.md`).

## 0. Hợp đồng đầu ra của LLM

LLM **CHỈ** trả JSON array. Mỗi phần tử đúng 5 khoá, không thừa không thiếu:

```json
{"text": "...", "type": "...", "assertions": [], "before": "...", "after": "..."}
```

- `text` — **nguyên văn** copy từ đoạn, đúng từng ký tự hoa/thường/dấu. Không sửa chính tả, không chuẩn hoá.
- `before` — **đúng 15 ký tự ngay TRƯỚC** span (ít hơn nếu ở đầu file). Nguyên văn, kể cả khoảng trắng/xuống dòng.
- `after` — **đúng 15 ký tự ngay SAU** span. Nguyên văn.
- LLM **KHÔNG** xuất mã, **KHÔNG** đếm offset. Hai thứ đó harness tự tính (LLM sai kinh niên ở đây).

`before`+`after` là **cơ chế định vị**, không phải trang trí. Thiếu chúng thì concept bị loại
(xem §4). Đây là chỗ khác biệt lớn nhất so với pipeline cũ: bản cũ chỉ có `before` nên phải
"cứu" bằng dò fuzzy toàn cục → đó chính là nguồn của 45 ca gán nhầm số file ở bản 12.

## 1. Năm loại (đóng, không có loại thứ 6)

| type | là gì | ví dụ ĐÃ ĂN ĐIỂM |
|---|---|---|
| `THUỐC` | tên thuốc / hoạt chất (kèm liều, đường dùng nếu liền mạch) | `metoprolol 25mg po bid`, `Gleevec` |
| `CHẨN_ĐOÁN` | tên bệnh / chẩn đoán | `viêm phổi`, `thiếu men G6PD`, `mày đay vô căn` |
| `TRIỆU_CHỨNG` | triệu chứng / dấu hiệu bệnh nhân có | `khó thở`, `vàng da`, `đau bụng` |
| `TÊN_XÉT_NGHIỆM` | tên một xét nghiệm **cận lâm sàng CỤ THỂ** | `WBC`, `creatinin`, `Troponin T`, `chụp x-quang ngực`, `nội soi` |
| `KẾT_QUẢ_XÉT_NGHIỆM` | giá trị + đơn vị của xét nghiệm | `14,43`, `316 mg/dl`, `âm tính` |

## 2. DANH SÁCH CẤM — đã trả giá bằng 3 lượt nộp, KHÔNG được trích lại

### 2a. Cấm cứng (bản 16 = −0.61 điểm, WER **TĂNG** lần đầu tiên)
- **Từ PHÂN LOẠI, không phải tên một xét nghiệm:** `xét nghiệm`, `chẩn đoán hình ảnh`,
  `cận lâm sàng`, `thăm khám`, `kiểm tra`. Gold không đánh nhãn chúng.
- **Dấu hiệu SINH TỒN đo tại giường + giá trị của chúng:** `Huyết áp`, `HA`, `Mạch`,
  `Nhiệt độ`, `Nhịp thở`, `SpO2`, `SPO2`, `cân nặng`, `130/76 mmHg`, `93 l/p`, `36.3 độ C`.
  Giả thuyết "sinh tồn cũng là xét nghiệm" đã **SAI**: `TÊN_XÉT_NGHIỆM` của gold là xét nghiệm
  **cận lâm sàng**, không gồm chỉ số đo tại giường.

### 2b. Cấm cứng (bản 15 = −0.075 điểm — dưới ngưỡng hoà vốn)
- **Cụm 1 âm tiết đứng trơ:** `đau`, `yếu`, `phù`, `ho`, `sốt` khi **không** có bổ ngữ.
  (Ngoại lệ: đã có sẵn trong bản 14 thì giữ — chúng đã được gold xác nhận.)
- **Biến thể hoa/thường của cùng một span đã trích** — không nhân bản kiểu đó.

### 2c. Cấm theo đề
- Tên người, tên bác sĩ, tên tổ chức (kể cả khi trùng tên bệnh).
- **Tên thuốc bị che `*****`** — là mồi nhử, không phải concept gold.
- Mốc thời gian, mức độ, vị trí giải phẫu đứng riêng (`3 ngày nay`, `dữ dội`, `hạ sườn phải`).

## 3. Assertions — LIST 0..3 nhãn, chỉ 3 giá trị hợp lệ

`isNegated` · `isHistorical` · `isFamily`

- Đang có / khẳng định → `[]` (rỗng). Đây là **mặc định**, chiếm ~77% concept.
- Multi-label hợp lệ: `"bố có tiền sử hen"` → `["isFamily","isHistorical"]`.
- **KHÔNG có** `isUncertain` / `isHypothetical`. Bỏ 2 nhãn này ăn **+1.6 J_assert = +0.48 điểm** (bản 11).
- Trong bài giáo dục y khoa ("bệnh X là gì", "triệu chứng của X"): concept nhắc chung chung
  về bệnh **KHÔNG** phải `isHistorical` và **KHÔNG** phải `isNegated` → `[]`.

## 4. Định vị (harness làm, không phải LLM)

1. Tìm **mọi** lần `text` xuất hiện nguyên văn trong raw của đúng file đó.
2. 0 lần → **LOẠI** (LLM bịa hoặc sửa chữ).
3. 1 lần → nhận.
4. >1 lần → lọc bằng `before` (khớp đuôi) và `after` (khớp đầu). Còn đúng 1 → nhận;
   còn 0 hoặc ≥2 → **LOẠI**.
5. **KHÔNG dò sang file khác. KHÔNG khớp fuzzy hoa/thường. KHÔNG nới ranh giới.**
   Ca không định vị được là ca LLM không chắc — vứt rẻ hơn đoán.

Chỉ nới đúng một điều, và nó vẫn là khớp CHÍNH XÁC: 20/100 file ở dạng Unicode phân rã (NFD).
Cho phép so khớp sau khi chuẩn hoá NFC **hai phía**, với điều kiện `NFC(raw[s:e]) == NFC(text)`.
Offset trả về luôn tính trên raw gốc. Ca này được ghi log riêng (`match_mode="nfc"`).

## 5. Candidates (mã) — harness gán, LLM không đụng vào

- **CHỈ** `CHẨN_ĐOÁN` (ICD-10-CM 2026) và `THUỐC` (RxNorm 2026). Ba type còn lại: **luôn `[]`**.
- ICD phải **CÓ DẤU CHẤM**: `D55.0` chứ không phải `D550` → gấp đôi J_cand (7.11 → 14.80).
- RxNorm giữ **số** nguyên: `7646`.
- Mã phải **tồn tại** trong `data/gaz.json`. Mã không tra được → để `[]`.
- **Không rõ thì ĐỂ RỖNG.** Điền mã thuốc đoán mò làm J_cand **GIẢM 0.49** (bản curated 24/07):
  gold cố ý để rỗng cho paracetamol/insulin/Vastarel.

## 6. Luật vàng về SỐ LƯỢNG (rút từ 4 lượt nộp sau bản 14)

> **J là Jaccard trên HỢP (gold ∪ pred) — concept thừa làm PHÌNH MẪU SỐ.**

Ngưỡng hoà vốn `h* = J/(1+J)`:

| trục | J hiện tại | h* | nghĩa |
|---|---|---|---|
| `J_assert` | 48.38% | **32.6%** | THÊM nhóm concept chỉ lời nếu >32.6% khớp gold. **BỎ** nhóm nào lời nếu <32.6% khớp gold. |
| `J_cand` | 23.61% | **19.1%** | như trên, chỉ áp cho `CHẨN_ĐOÁN`+`THUỐC`. |

Lịch sử biên lợi ích mỗi concept THÊM:

| bản | cách thêm | concept | điểm/concept |
|---|---|---|---|
| 14 | nhân bản text **đã được gold xác nhận** sang lần nhắc khác | +313 | **+0.00403** |
| 15 | cụm 1 âm tiết + biến thể hoa/thường | +147 | −0.00051 |
| 16 | trích lại + sinh tồn + từ chung chung | +251 | −0.00244 |
| 17 | trích lại (chỉ concept "cụ thể") | +113 | **−0.00499** |

**Chỉ MỘT cách thêm từng thắng.** Mọi concept do LLM tự nghĩ thêm đều lỗ.

## 7. Chặn trên kích thước gold (giải ngược từ bản 14 vs 17)

Với `J_assert` và `h* = J/(1+J)`, số concept khớp gold ở bản N ≈ `h*_N × (G + P_N)`.
Ép hiệu số ≥ 0 giữa bản 14 (P=2824, J=48.3759) và bản 17 (P=2937, J=47.2163):

**G ≤ ~4000.** Kéo theo precision bản 14 chỉ **61–79%** ⇒ đang mang **600–1100 concept rác**.

⇒ Đòn bẩy chưa từng thử: **BỎ BỚT**, không phải thêm.

## 7b. TRUNG BÌNH THEO FILE — khuếch đại lỗi ở file THƯA

Theo bản tái dựng metric (`src/evaluate.py`, **không phải code gốc BTC** — đây là suy luận):

```python
text_score       = sum(ts) / n_file      # trung bình theo FILE, không trọng số
assertions_score = sum(as_) / n_file     # trung bình theo FILE, không trọng số
candidates_score = sum(c*w)/sum(w)       # CÓ trọng số theo số mã của gold
```

⇒ Một file chỉ có vài concept gold có **ảnh hưởng ngang** một file có 60 concept.
Thêm/bớt một concept ở file thưa dịch chuyển `a_f` của file đó rất mạnh, và `a_f` đó
chiếm trọn 1/100 tổng điểm.

**Điều này giải thích bản 16/17 lỗ nặng hơn dự đoán:** cả hai đều trích lại đúng
**"30 file mật độ thấp nhất"** — tức đổ concept mới vào chính những file mà mỗi sai sót
bị khuếch đại nhất. Cùng số concept sai, đặt ở file dày thì hại ít hơn nhiều.

**Hệ quả dùng được:**
- Đãi bỏ rác ở file THƯA có lời cao nhất.
- Thêm concept vào file THƯA là rủi ro nhất — cần bằng chứng mạnh hơn hẳn.
- Đừng đánh giá một bản chỉ bằng tổng số concept; xem phân bố theo file.

## 8. Ràng buộc đề

- `final = 0.3·(1−WER) + 0.3·J_assert + 0.4·J_cand`
- WER tính trên chuỗi **nối** các text sắp theo `position`, mức TỪ, **không chặn trên**.
- 5 lượt nộp/ngày. Deadline Phase 1: **04/08/2026**.
- Phase 2/3 phải self-host **≤9B** — nhưng data/gold sinh bằng LLM mạnh là **HỢP LỆ** (FAQ BTC).
