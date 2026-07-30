# Oracle chấm điểm offline (dựng đúng công thức đề)

- **Trạng thái**: xong
- **Bắt đầu** / **Cập nhật**: 2026-07-28
- **Liên quan**: worklog/03 (bản nộp #1 = mốc hiệu chuẩn), worklog/04 (NFD, cần cho offset GT), PLAN.md

## Mục tiêu

Đo được điểm **không cần nộp**. Mỗi ngày chỉ có 5 lượt nộp; nếu phải nộp mới biết mình
tăng hay giảm thì 7 ngày còn lại chỉ đo được 35 lần. Có oracle thì đo bao nhiêu lần
cũng được, và quan trọng hơn: biết **mất điểm ở đâu**.

## Đã làm

### 1. Viết GT tay cho 6 file (95–100), 125 khái niệm

`src/make_gt.py`. Annotation viết dạng `(cụm chữ, lần xuất hiện thứ n, loại,
assertions, candidates)` chứ **không viết offset trực tiếp**. Lý do: offset gõ tay sai
một chữ số là sai âm thầm, còn cụm chữ sai thì script chết ngay với thông báo rõ. Phiên
trước tôi đã từng gõ nhầm một chữ số mã ICD và làm hỏng cả bảng kết quả.

Offset được resolve bằng cách dò trên chuỗi **NFC** rồi map ngược về offset file gốc qua
`src/textnorm.py` (worklog/04) — vì 97.txt và 100.txt là file NFD, dò trực tiếp trên
chuỗi gốc thì `cục máu đông` và `đi tiêu ra máu` không tìm thấy.

Ba lớp kiểm tra tự động, đều pass:
- span trên file gốc, đưa qua NFC, phải bằng đúng cụm đã annotate;
- không có hai khái niệm trùng span;
- `raw[position[0]:position[1]] == text` trên cả 125 khái niệm (0 mismatch).

Bẫy gặp phải: tên thuốc bị mask bằng dấu sao. `*******` (7 sao) là substring của
`************` (12 sao), nên `str.find` khớp vào **giữa** run 12 sao → sinh 3 span
chồng nhau ở cùng offset 202. Sửa: với cụm toàn dấu sao thì match nguyên run `\*+` và
so độ dài run, không dùng find.

Quy ước annotation đã theo (rút từ ví dụ của đề):
- `assertions` chỉ cho CHẨN_ĐOÁN / THUỐC / TRIỆU_CHỨNG.
- Mọi thứ nằm trong mục "Tiền sử bệnh" → `isHistorical`, gán **theo phạm vi mục**, không
  theo dấu hiệu trong câu.
- Trong ví dụ của đề, triệu chứng là *chỉ định* của thuốc ("điều trị lo âu") vẫn để
  `assertions: []` dù thuốc là isHistorical. Nên chỉ gán khi bản thân triệu chứng là
  tiền sử / bị phủ định.
- Tên thuốc bị mask: vẫn xuất THUỐC (span hợp lệ, số dấu sao khớp số ký tự gốc), nhưng
  `candidates` rỗng vì không suy ra được RxCUI.

### 2. Tìm lại công thức chấm đầy đủ trong đề

Trước đó tôi đang dùng công thức rút gọn `final = 0.3·(100−WER) + 0.3·J_a + 0.4·J_c`,
suy ra từ 4 con số BTC trả về. Nó khớp tới 4 chữ số thập phân nên tôi tưởng đã đủ. Đọc
lại đề (grep transcript JSONL) thì đề ghi chi tiết hơn, và phần chi tiết đó đổi cách
tính:

```
text_score       = Σ_i (1 − WER(i)) / len(test)
assertions_score = Σ_i J_assertions(i) / len(test)
candidates_score = Σ_i J_candidates(i)·w(i) / Σ_i w(i),   w(i) = Σ_k (len(gt(k)) + 1)
```

`i` = 1 file, `k` = 1 khái niệm trong file. Ba điều bản trước của `src/score.py` làm sai:

1. `text_score`, `assertions_score` là trung bình **theo file** — mỗi file một phiếu
   bằng nhau. File 7 khái niệm nặng bằng file 34 khái niệm.
2. `candidates_score` là trung bình **có trọng số**: `w(i) = Σ_k (số candidate GT của
   khái niệm k + 1)`. File nhiều khái niệm/nhiều candidate thì nặng hơn. Số `+1` để
   khái niệm không có candidate vẫn có trọng số.
3. J tính **theo từng khái niệm rồi trung bình trong file**, không gộp phẳng cả file.

Điểm 3 có bằng chứng độc lập: bản nộp #1 để assertions rỗng 100%. Nếu gộp phẳng thì
J mỗi file chỉ nhận 0 hoặc 1, nên trung bình 100 file phải là số nguyên chia 100
(19.0000...). BTC trả **18.5774** → loại gộp phẳng. Biến thể `flat` đã xoá khỏi scorer.

### 3. Chốt cách ghép khái niệm bằng chính "Lưu ý" của đề

Ẩn số lớn nhất từ đầu giải là: BTC ghép khái niệm dự đoán với khái niệm GT thế nào
trước khi tính Jaccard? Đề trả lời trong phần Lưu ý:

> "đoán đúng phần text của khái niệm nhưng sai loại (VD: đoán `CHẨN_ĐOÁN` nhưng ground
> truth là `TRIỆU_CHỨNG`), khái niệm sẽ bị tính **2 lần** (do tạo ra 1 khái niệm mới so
> với ground truth) và mỗi lần đều được tính **0 điểm với cả 3 loại metric**."

Suy ra bốn điều, không phải đoán nữa:
- `type` nằm trong khoá ghép. Sai type = không ghép được.
- Khái niệm lẻ (chỉ có ở GT, hoặc chỉ có ở pred) tính 0 cho **cả 3** metric — kể cả WER.
  Nên mẫu số của J là |hợp khái niệm|, và **WER cũng phải tính theo từng khái niệm rồi
  trung bình**; không thể "cho 0 điểm 1 khái niệm" nếu WER chạy trên chuỗi nối cả file.
  Bản trước của scorer tính WER trên chuỗi nối → sai.
- Đề nói "đoán đúng phần **text**" → ghép dựa trên nội dung chữ, không đòi khớp
  `position` tuyệt đối.
- Sai type bị phạt gấp đôi: mất 1 khái niệm GT **và** thêm 1 khái niệm rác. Đoán nhầm
  CHẨN_ĐOÁN ↔ TRIỆU_CHỨNG đắt gấp 2 lần so với bỏ qua.

Còn 1 ẩn số nhỏ: trong cùng type, ghép theo text khớp tuyệt đối hay theo span chồng lấn.
Giữ 3 biến thể `text` / `span` / `overlap` trong scorer để so.

## Kết quả đo được

Cách đo: `python3 src/score.py --gt data/gt --pred submission_v1 --per-file`, GT 6 file
tay, pred là **đúng thư mục đã nộp** (submission_v1, điểm BTC 16.2858).

| cách ghép | WER | text | assert | cand | **final** |
|---|---|---|---|---|---|
| **overlap** | **81.91** | 18.09 | 15.91 | 20.92 | **18.57** |
| span | 85.27 | 14.73 | 11.29 | 14.51 | 13.61 |
| text | 85.52 | 14.48 | 12.02 | 12.88 | 13.10 |
| *mốc BTC (100 file)* | *82.94* | *17.06* | *18.58* | *13.99* | *16.29* |

`overlap` gần mốc nhất và là biến thể duy nhất nhất quán với Lưu ý của đề (span lệch
vài ký tự vẫn phải ghép được, phần chữ lệch thì WER đo). Hai biến thể kia lệch 3–5 điểm
final. Chốt dùng `overlap`. Lưu ý mẫu chỉ 6 file nên vẫn còn nhiễu; không kỳ vọng khớp
số tuyệt đối, chỉ dùng để xếp hạng thay đổi.

Recall/precision theo loại (ghép overlap, 6 file):

| loại | GT | pred | khớp | recall | precision |
|---|---|---|---|---|---|
| CHẨN_ĐOÁN | 49 | 8 | 7 | **14.3%** | 87.5% |
| TRIỆU_CHỨNG | 47 | 16 | 15 | **31.9%** | 93.8% |
| THUỐC | 14 | 7 | 7 | 50.0% | 100.0% |
| TÊN_XÉT_NGHIỆM | 9 | 0 | 0 | **0.0%** | – |
| KẾT_QUẢ_XÉT_NGHIỆM | 6 | 0 | 0 | **0.0%** | – |
| **tổng** | **125** | **31** | **29** | **23.2%** | **93.5%** |

Mật độ khái niệm: 125 khái niệm / 6 file ≈ 21/file. Pipeline hiện xuất 990 khái niệm
trên 100 file ≈ 9.9/file. Ngoại suy: tập test có **~2100 khái niệm**, ta đang bắt ~23%.

## Phát hiện

**1. Recall NER quyết định cả 3 metric, không chỉ WER.** Đây là phát hiện đổi hướng
làm bài. `J_X(i) = 1` khi cả GT và pred đều rỗng — và trong GT tay, 78% khái niệm có
`assertions` rỗng, 57% có `candidates` rỗng (đo: đếm trên 125 khái niệm trong `data/gt`). Nghĩa là mỗi khái niệm bắt thêm được, kể cả
khi để `assertions: []` và `candidates: []`, vẫn **được điểm** ở cả assertion lẫn
candidate nếu GT của nó cũng rỗng. Ngược lại mỗi khái niệm bỏ sót ăn 0 điểm ở cả 3
metric. Không cần logic assertion tinh vi để nhích assertions_score; cần bắt đủ khái
niệm trước. Điều này giải thích luôn vì sao bản nộp #1 để assertions rỗng 100% mà vẫn
được 18.58: đó không phải điểm thưởng, đó là phần khái niệm nó bắt đúng và GT cũng rỗng.

**2. TÊN_XÉT_NGHIỆM / KẾT_QUẢ_XÉT_NGHIỆM đang recall 0%** dù pipeline *có* nhánh xử lý
xét nghiệm. Nhánh đó chỉ khớp mẫu `Tên: số đơnvị` (dấu hai chấm), còn corpus viết
"Ure máu 91 mg/dl", "SpO2 99%", "huyết áp tâm thu là 90", "105 chu  kì/phút" (chú ý hai
dấu cách). 15/125 = 12% khái niệm, đang mất trắng. Đây là món dễ nhất còn lại.

**3. Không tồn tại "bảng tra" nào cứu được.** Recall thấp không phải vì thiếu vài từ
trong từ điển. 42 CHẨN_ĐOÁN bỏ sót gồm những cụm như "biến dạng xương khớp", "Đã tử
vong", "không có hình ảnh tổn thương viêm cấp tính", "gout cấp", "Cơn tim nhanh nhĩ" —
không cụm nào có trong danh mục ICD BYT theo dạng khớp chính xác. Phải là model NER,
đúng như PLAN.md dự kiến. Từ điển chỉ để bootstrap dữ liệu huấn luyện.

**4. Sai type đắt gấp đôi bỏ sót.** Hệ quả trực tiếp của Lưu ý. Precision hiện đang
93.5% nên chưa phải vấn đề, nhưng khi thêm model cần nhớ: thà bỏ trống hơn đoán sai
loại. Ranh giới nguy hiểm nhất là CHẨN_ĐOÁN ↔ TRIỆU_CHỨNG ("hạt tophi", "hoại tử",
"hạ huyết áp" — tôi tự annotate cũng phải cân nhắc).

**5. Sai sót của chính tôi cần ghi lại**: tôi đã tin công thức rút gọn vì nó khớp 4 chữ
số thập phân với 4 số BTC trả về. Nhưng khớp trên **1 điểm dữ liệu** không chứng minh
công thức đúng — trung bình theo file và trung bình có trọng số cho ra cùng một con số
khi tất cả `w(i)` xấp xỉ nhau. Bài học: khi đề có văn bản gốc, đọc văn bản gốc, đừng
suy ngược từ điểm số.

## Việc còn lại

- [x] Viết GT 6 file vào `data/gt/`, 125 khái niệm, 3 lớp kiểm tra pass
- [x] Dựng lại `src/score.py` đúng công thức đề (theo file / có trọng số / theo khái niệm)
- [x] Chốt cách ghép = `overlap` (cùng type, chồng lấn ký tự, tham lam)
- [x] Đo recall theo loại → biết mất điểm ở đâu
- [ ] Vá nhánh xét nghiệm: bắt được `Ure máu 91 mg/dl`, `SpO2 99%`, `110/70  mmHg` (recall 0% → mục tiêu >50%)
- [ ] Nối `textnorm` vào `predict.py` (đang là việc treo từ worklog/04)
- [ ] Mở rộng GT ra ~30 file để oracle bớt nhiễu và có tập validation cho model
- [ ] Bắt đầu model NER (PLAN.md): recall là nút thắt, không phải luật
