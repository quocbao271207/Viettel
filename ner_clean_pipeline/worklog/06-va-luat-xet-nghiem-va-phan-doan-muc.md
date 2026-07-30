# 06 — Vá nhánh xét nghiệm + phân đoạn mục (section)

Trạng thái: **xong**
Ngày: 28/07/2026
Tiếp nối: worklog/05 (oracle chấm điểm). Mọi số ở đây đo bằng
`python3 src/score.py --gt data/gt --pred submission`, cách ghép `overlap`, trên GT tay
6 file (95–100).

## Mục tiêu

worklog/05 đo ra 3 chỗ mất điểm, xử lý 2 chỗ dễ nhất trước khi làm model:

1. `TÊN_XÉT_NGHIỆM` / `KẾT_QUẢ_XÉT_NGHIỆM` recall **0%** dù pipeline *có* nhánh xét nghiệm.
2. `assertions` để rỗng 100% — bỏ không điểm `isHistorical`.

## Kết quả đo

| bản | WER | text | assert | cand | **final** |
|---|---|---|---|---|---|
| trước (submission_v1) | 82.33 | 17.67 | 15.37 | 20.45 | **18.09** |
| + `extract_labs` | 71.81 | 28.19 | 26.17 | 31.00 | **28.71** |
| + lọc "ho" theo mục | 71.68 | 28.32 | 26.24 | 31.19 | **28.85** |
| + `isHistorical` theo mục | 70.57 | 29.43 | **29.56** | 31.07 | **30.13** |

Recall / precision theo loại (đo bằng script tạm, ghép `overlap`):

| loại | GT | pred | hit | recall | prec |
|---|---|---|---|---|---|
| CHẨN_ĐOÁN | 50 | 8 | 8 | 16.0% | 100% |
| TRIỆU_CHỨNG | 47 | 15 | 15 | 31.9% | 100% |
| THUỐC | 14 | 7 | 7 | 50.0% | 100% |
| TÊN_XÉT_NGHIỆM | 13 | 11 | 11 | **84.6%** | 100% |
| KẾT_QUẢ_XÉT_NGHIỆM | 8 | 4 | 4 | **50.0%** | 100% |
| TỔNG | 132 | 45 | 45 | 34.1% | **100%** |

Xét nghiệm: 0% → 84.6% / 50.0%. Precision toàn cục 87% → **100%** (0 pred rác trên 6 file).

Lưu ý: `final` ở đây (30.13) KHÔNG so trực tiếp được với mốc BTC 16.29 — mốc BTC đo trên
100 file, đây là 6 file. Chỉ dùng để so *giữa các bản* trên cùng 6 file.

## Việc đã làm

### 1. `extract_labs()` trong `src/predict.py`

Nhánh cũ chỉ khớp `Tên: số đơnvị` (bắt buộc có dấu hai chấm). Corpus không viết như vậy.
Chia thành hai luật vì corpus có hai nhóm khác nhau hẳn về cấu trúc:

**Nhóm 1 — chỉ số định lượng**: tên rồi tới số, dấu `:` có thể có hoặc không.
`LAB_NAMES` mở rộng từ 29 → ~86 tên (thêm điện giải, khí máu, marker viêm, đông máu, và
**dấu hiệu sinh tồn**: Huyết áp, Mạch, Nhiệt độ, Nhịp thở, SpO2, tần số). Regex `LAB_VALUE`
nhận: `<>≤≥` đứng trước, thập phân dùng `.` hoặc `,`, khoảng `24.6 -32.5`, phân số
`110/70`, và ~30 đơn vị. Xuất tên là `TÊN_XÉT_NGHIỆM`, **chỉ giá trị + đơn vị** là
`KẾT_QUẢ_XÉT_NGHIỆM` (theo đúng định nghĩa đề: "bao gồm giá trị và đơn vị", ví dụ của đề
là "14,43" trần).

**Nhóm 2 — thủ thuật / chẩn đoán hình ảnh**: `PROCEDURES`, 36 cụm khớp trọn văn
(`chụp cắt lớp vi tính (ct)`, `điện tâm đồ`, `siêu âm ổ bụng`, `cấy nước tiểu`, `nội soi
dạ dày`, `sinh thiết`...). KHÔNG có con số theo sau nên phải khớp trọn cụm — mở rộng theo
số từ sẽ nuốt luôn phần kết quả (`chụp x-quang ngực cho thấy không có...`).

Đơn vị có chỗ chứa **hai dấu cách** (`105 chu  kì/phút`, `110/70  mmHg`) nên regex cho
phép `\s{0,2}` trước đơn vị.

Chốt bỏ: `đo` đứng một mình xuất hiện 145 lần trong corpus, phần lớn là động từ thường
("đo huyết áp", "cần đo lại"), không đưa vào `PROCEDURES`.

### 2. `src/sections.py` — phân đoạn theo mục

Corpus là bệnh án có cấu trúc mục rõ. Đo tần suất tiêu đề thật trên 100 file:
`Tiền sử bệnh hiện tại` ×33, `Đánh giá tại bệnh viện` ×33, `Tiền sử bệnh` ×29,
`Các bệnh lý mạn tính` ×16, `Các thủ thuật đã thực hiện` ×12...

Module gán 5 nhãn — `history`, `chronic` (tập con của history), `current`, `lab`,
`family` — phủ **65%** ký tự corpus. Tách riêng khỏi `predict.py` để model cũng dùng
được sau này. Có kèm lỗi chính tả thật của corpus (`Các thủ thuậ khác`).

Dùng cho hai việc:

**a. `isHistorical` theo phạm vi mục** — mọi CHẨN_ĐOÁN/THUỐC/TRIỆU_CHỨNG trong mục
`history` được gán `isHistorical`. Đo trên GT tay: tp=20 fp=4 fn=3 → **precision 83%,
recall 87%**. Toàn corpus xuất 234 `isHistorical` + 9 `isFamily`. Điểm assert 26.24 → 29.56.

FP/FN còn lại đều là ca biên: `tiêu chảy`/`da sạm`/`tàn nhang` nằm trong mục tiền sử
nhưng GT tay tôi coi là hiện tại; `suboxone` ngược lại. Không sửa vì cả hai cách đọc đều
biện hộ được, và 83/87 đã đủ để ăn điểm Jaccard.

Chưa làm `isNegated` bằng cách này: phủ định là chuyện **trong câu** ("không có tiếng
rales", "phủ nhận buồn nôn"), không phải theo mục. Để dành cho model hoặc luật cửa sổ.

**b. Lọc rác "ho"** — corpus có lỗi template: gạch đầu dòng trong mục `Các bệnh lý mạn
tính` bị dính chữ "ho" ở đầu → `- ho đái tháo đường`, `- ho Rung nhĩ`, `- ho Rối loạn
cảm xúc`. Trong mục đó mỗi dòng là một BỆNH nên "ho" trần là rác. Nhãn `chronic` khoanh
đúng **4/4** ca rác, không chạm ca "ho" thật nào (kiểm tay cả 17 ca).

### 3. Sửa 5 lỗi trong GT tay của tôi

Đây là điểm quan trọng nhất của phiên: khi nhánh xét nghiệm mới bắt được 4 thứ mà GT
tay tôi không có, tôi kiểm ngữ cảnh trước khi kết luận là "rác" — và **4/6 là GT tôi
sai, không phải luật sai**.

| file | sửa | lý do |
|---|---|---|
| 97 | + `Sinh thiết tuyến tiền liệt` (LAB) | thủ thuật lấy mẫu để xét nghiệm GPB. `Phẫu thuật cắt bỏ u` cùng mục thì KHÔNG (điều trị). Độ tin cậy vừa. |
| 99 | + `cấy nước tiểu` (LAB) | mục "Các thủ thuật đã thực hiện" |
| 99 | + `chụp x-quang ngực` lần 2 | "so với chụp x-quang ngực trước đó" vẫn là xét nghiệm đã làm |
| 99 | `Huyết áp` index 1 → 3 | đếm sai occurrence, index 1 rơi vào "hạ huyết áp" trong bệnh sử |
| 100 | + `tiền sản giật` lần 3 | nhất quán với lần 2 đã annotate |

GT: 128 → 132 khái niệm, 6 file, 0 lệch span.

### 4. Nối `textnorm` vào `predict.py` (việc treo từ worklog/04)

`extract_raw()` mới: khớp trên bản NFC rồi map `position` về file gốc bằng
`to_raw_span`. 20 file NFD trước đó chỉ ra 9.2 entity/file so với 13.5 của file NFC —
sau khi nối là **10.0**. Tổng entity 1267 → 1283. Kiểm 100 file: **0 lệch span**
(`raw[a:b] == text` cho cả 1283 entity). Oracle final 30.13 → **30.68**.

Mức tăng nhỏ hơn kỳ vọng vì phần thiếu ở file NFD phần lớn là CHẨN_ĐOÁN/TRIỆU_CHỨNG mà
từ điển vốn không có, không phải do lỗi encoding.

## Đo trần điểm (ablation) — con số quyết định thứ tự việc còn lại

Câu hỏi: nên đầu tư vào `assertions`/`candidates` hay vào recall? Đo bằng cách thay từng
phần của prediction bằng đúng GT, giữ nguyên các phần khác (script tạm, GT 6 file):

| kịch bản | text | assert | cand | **final** | Δ |
|---|---|---|---|---|---|
| hiện tại | 30.17 | 30.67 | 31.07 | **30.68** | — |
| + assertions HOÀN HẢO | 30.17 | 33.96 | 31.07 | **31.67** | +0.99 |
| + candidates HOÀN HẢO | 30.17 | 30.67 | 33.93 | **31.82** | +1.14 |
| + cả hai hoàn hảo | 30.17 | 33.96 | 33.93 | **32.81** | +2.13 |
| **recall 100%**, assert/cand để RỖNG | 100.00 | 82.13 | 56.79 | **77.35** | **+46.67** |
| recall 100% + cand hoàn hảo | 100.00 | 82.13 | 100.00 | **94.64** | +63.96 |
| hoàn hảo tuyệt đối | 100 | 100 | 100 | **100** | +69.32 |

**Recall đáng giá gấp 22 lần mọi thứ khác cộng lại.** Nếu bắt đúng đủ 100% khái niệm mà
để `assertions` và `candidates` RỖNG HẾT thì vẫn được **77.35** — cao hơn mốc dẫn đầu 49
điểm rất nhiều. Ngược lại, làm assertions và candidates hoàn hảo trên tập khái niệm đang
bắt được chỉ lên 32.81.

Lý do là cơ chế `J_X(i) = 1` khi cả GT và pred đều rỗng: 78% khái niệm GT có
`assertions` rỗng, 57% có `candidates` rỗng, nên chỉ cần *bắt được* khái niệm là đã ăn
điểm cả 3 metric dù để trống hai trường kia. Ngược lại bỏ sót một khái niệm là mất điểm
ở cả 3.

**Kết luận: dồn toàn bộ thời gian còn lại vào recall (model NER).** Tinh chỉnh assertions
và candidates là việc cuối, sau khi recall đã cao.

## Bài học

**Khi luật mới bắt được thứ GT không có, đọc ngữ cảnh trước khi gọi là false positive.**
Lần này 4/6 "FP" là GT tôi sai. Nếu tôi tin GT vô điều kiện thì đã đi thêm bộ lọc để
*chặn* 4 dự đoán đúng — tự hạ recall mà tưởng đang tăng precision. GT tay là nền móng,
nhưng nó do người viết nên cũng sai được; mọi bất đồng phải xử bằng cách đọc lại văn bản
gốc + định nghĩa của đề, không phải bằng cách tin bên nào.

## Việc còn lại

- [x] Vá nhánh xét nghiệm (recall 0% → 84.6% / 50.0%)
- [x] `isHistorical` theo mục (assert 26.24 → 29.56)
- [x] Nối `textnorm` vào `predict.py` (0 lệch span trên 1283 entity)
- [x] Đo trần điểm → chốt: recall là tất cả
- [ ] **Model NER** — việc quan trọng duy nhất còn lại. recall CHẨN_ĐOÁN 16% /
      TRIỆU_CHỨNG 32% là nút thắt, luật không chữa được (worklog/05 phát hiện 3)
- [ ] Mở rộng GT ra ~30 file (oracle 6 file còn nhiễu, và cần tập validation cho model)
- [ ] `isNegated` bằng luật cửa sổ trong câu — HOÃN, chỉ đáng ~1 điểm
- [ ] Tinh chỉnh candidates — HOÃN, chỉ đáng ~1.1 điểm
