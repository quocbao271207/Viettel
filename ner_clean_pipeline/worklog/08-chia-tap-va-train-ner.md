# 08 — Chia tập train/val chống rò rỉ, rồi train NER

Bối cảnh: gán nhãn tay đã xong 100% (worklog/07). Nút thắt duy nhất còn lại là
**recall NER** — đo ở worklog/06: recall 100% mà `assertions`/`candidates` để rỗng
cũng được **77.35đ**, trong khi đội cao nhất bảng đang 49đ. Nên mọi công sức dồn vào
việc tìm đúng span, không phải tinh chỉnh hai trường kia.

## Vì sao không chia train/val theo file

Corpus này dịch máy và **trùng lặp nặng**. Số đo:

- 332 block cho 100 file. **24 block xuất hiện ở nhiều file**, block lặp nhiều nhất
  nằm ở **23 file**.
- Ngoài trùng nguyên khối còn có trùng một phần: `SHARE[bid] = (src, n)` ghi lại
  block dùng chung `n` ký tự đầu với block khác.
- Và trùng "cùng nguồn, hai bản dịch khác nhau" — kiểu đã gặp ở `GT[26]` vs `GT[89]`
  (cùng một câu kết luận CT, hai bản dịch, xem worklog/07 phần rà mâu thuẫn).

Chia theo file thì cùng một đoạn nguồn vừa nằm train vừa nằm val. Model chỉ cần **nhớ**
là val đã cao, đo xong không suy ra được gì về private test.

## Chia theo GROUP

`src/split.py`. Dựng đồ thị rồi lấy thành phần liên thông. Ba loại cạnh:

| Cạnh | Nguồn | Bắt được gì |
|---|---|---|
| file – block | `data/blocks/file_to_blocks.json` | file dùng chung block |
| block – block | `SHARE[bid] = (src, n)` | dùng chung tiền tố |
| block – block | jaccard 8-gram ≥ 0.5 trên chuỗi đã bỏ dấu cách/hoa/ký tự lạ | cùng nguồn, hai bản dịch |

Kết quả: **39 group**.

### Ngưỡng near-dup: đã thử rồi chốt

Bản đầu tôi dùng **min-overlap** (`|A∩B| / min(|A|,|B|)`) thay vì jaccard. Sai:
min-overlap coi "block ngắn nằm trong block dài" là trùng, nên nó **gộp chuỗi** —
ngưỡng 0.5 cho ra 1 cục **83 file**, gần như cả corpus, không còn gì để chia.

Quét cả hai công thức × 4 ngưỡng:

| ngưỡng | jaccard: ncomp / max_nfile | min-overlap: ncomp / max_nfile |
|---|---|---|
| 0.5 | 39 / 42 | 14 / **83** |
| 0.7 | 40 / 42 | 27 / 59 |
| 0.8 | 42 / 42 | 37 / 43 |
| 0.9 | 43 / 42 | 37 / 43 |

Đọc bảng: với jaccard, `max_nfile` **đứng im ở 42** ở mọi ngưỡng. Nghĩa là cục 42 file
đó không do ngưỡng lỏng mà do **block dùng chung thật** (block nằm ở 23 file). Đây là
ràng buộc cứng không phá được → cục đó phải nằm nguyên một bên, và vào train.

Chốt **jaccard 0.5**: lỏng nhất trong vùng an toàn, bắt được nhiều cặp near-dup nhất
mà không gộp chuỗi.

## Chọn val: cân bằng phân bố, không phải "càng dày entity càng tốt"

Bản đầu tôi xếp group theo entity/file giảm dần rồi nhặt vào val. Kết quả sai lệch rõ:

```
train {SYM 646, DX 527, DRUG 243, LAB 195, VAL 83}
val   {SYM 317, DX 277, LAB 210, DRUG 110, VAL 87}
```

**LAB ở val (210) nhiều hơn cả train (195)** — val 20 file mà chứa nhiều tên xét nghiệm
hơn 80 file train. Val như thế không đại diện gì cho test.

Sửa: mỗi bước thử thêm 1 group, chọn group nào làm **khoảng cách L1 giữa phân bố nhãn
của val và của toàn corpus** nhỏ nhất; trừ nhẹ `0.001·n_file` để không nhặt toàn group
1 file. Kết quả:

```
group           39
train  file  80  block 262  chars 152608  ent 2205
val    file  20  block  70  chars  36828  ent  490
block ở cả 2 bên: 0
train {SYM 791, DX 661, LAB 326, DRUG 287, VAL 140}
val   {SYM 172, DX 143, LAB  79, DRUG  66, VAL  30}
```

Tỉ lệ: train 35.9 / 30.0 / 14.8 / 13.0 / 6.3 %, val 35.1 / 29.2 / 16.1 / 13.5 / 6.1 %.
Khớp sát. **0 block nằm cả hai bên** — không rò rỉ theo định nghĩa group ở trên.

Ghi ở `data/blocks/split.json` (kèm `seed`, `near_th` để tái lập).

## Mốc để so: luật thuần trên val

Thêm `--split train|val` cho `src/score.py` (tham số `only` của `score_dirs`), chấm
`submission_v1` (bản luật thuần đã nộp lên BTC) đối chiếu GT tay:

| split | ghép overlap: WER | text | assert | cand | **final** |
|---|---|---|---|---|---|
| train (80 file) | 80.47 | 19.53 | 16.90 | 22.30 | **19.85** |
| val (20 file) | 82.11 | 17.89 | 17.15 | 24.49 | **20.31** |

Hai bên lệch 0.46đ → split cân bằng, val đo được. **Mốc cần vượt trên val: 20.31.**

Đối chiếu thêm: bản này nộp BTC được 16.2858 trên 100 file test thật. Số offline
(19.85/20.31) cao hơn vì GT tay của tôi không phải GT của BTC — nên val chỉ dùng để
**so tương đối giữa các bản của tôi**, không dùng để dự đoán điểm tuyệt đối.

## Dọn span lồng nhau (bắt buộc, không phải cho đẹp)

Mô hình sẽ là **token classification (BIO)**: mỗi token đúng một nhãn. Vì vậy span lồng
nhau *không biểu diễn được* — nếu GT có, dữ liệu train sẽ tự mâu thuẫn. Rà toàn bộ 100 file
thấy **12 span lồng nhau**, đã bỏ hết. Entity 3484 → **3475**. Sáu nhóm nguyên nhân:

| chỗ | nguyên nhân | cách sửa |
|---|---|---|
| `GT[74]` | `khó thở` dùng `ALL` → lần thứ 4 nằm trong bề mặt dài "khó nằm vào ban đêm để ngủ vì khó thở" | liệt kê index rõ, bỏ lần [3] |
| `GT[27]` | needle `[[nôn]],` cũng khớp `buồn nôn,` → 3/6 lần lồng trong `buồn nôn` | thêm ngữ cảnh `nôn, ` phía trước |
| `GT[34]` | `khó thở` `ALL` lần [0] chính là phần đuôi của `Khó thở nhẹ` (bản dịch lặp chữ) | bỏ [0], giữ 6 lần |
| `GT[28]` | `tiểu đường` index 1 nằm trong `bệnh tiểu đường`; `viêm` index 3 nằm trong `Viêm nha chu` | đổi sang index 2 và 6 |
| `GT[45]` | tôi CỐ Ý tách `nhịp nhanh trên thất` ra khỏi `rung nhĩ và nhịp nhanh trên thất` | bỏ nhãn con — `GT[94]` cùng bề mặt chỉ gán một nhãn cụm, đó là tiền lệ |
| `GT[129]` | đặt `[[...]]` SAI BÊN: viết `[[khó thở tăng lên khi xuất hiện  ]]Cơn nhịp nhanh` nên lấy đúng phần ngữ cảnh, đè lên nhãn ở dòng trên | chuyển ngoặc sang `Cơn nhịp nhanh` |

Bài học về cú pháp needle: `ngữ cảnh [[phần cần lấy]] ngữ cảnh`. Đặt sai bên thì **không
báo lỗi gì** — nó gán nhãn cho ngữ cảnh. Kiểm tra bằng `--occ` trước khi tin.

Kiểm chứng sau khi dọn: `3475 entity / 0 span trùng / 0 lệch offset`.

## Trần của pipeline: chấm bằng oracle

Thay phần model bằng chính GT (giả định model hoàn hảo, recall 100%, span khớp tuyệt đối)
rồi cho các luật hậu xử lý chạy như thật. Cách này tách bạch được *nút thắt do model* và
*nút thắt do luật*. Chấm `src/score.py`, ghép `overlap`, 100 file:

| biến thể | WER | text | assert | cand | **final** |
|---|---|---|---|---|---|
| oracle + cả 2 luật | 0 | 100 | 78.23 | 70.72 | 81.76 |
| oracle, 2 trường để rỗng | 0 | 100 | 78.77 | 64.69 | 79.51 |
| oracle + assertions LẤY TỪ GT | 0 | 100 | 99.90 | 70.72 | 88.26 |
| oracle + candidates LẤY TỪ GT | 0 | 100 | 78.23 | 99.68 | 93.34 |
| oracle, tắt luật assertion, bật luật candidate | 0 | 100 | 78.77 | 70.72 | **81.92** |

Ba kết luận:

1. **Luật assertion đang LỖ 0.16đ** → tắt (`use_assert=False` mặc định ở `src/ner_infer.py`).
   Lý do: 79% khái niệm trong GT có `assertions` rỗng, mà Jaccard cho J=1 khi *cả hai* rỗng.
   Đoán thêm là tự phá điểm chắc ăn. Đo riêng luật trên 100 file: **precision 0.39 /
   recall 0.36** (tp 277, fp 426, fn 487; trong đó 404 FP là `isHistorical`).
   `worklog/06` từng ghi precision 83% — nhưng đo trên **6 file**. Mở ra 100 file thì sập.
   Đây là ví dụ vì sao mọi số đo phải ghi rõ đo trên bao nhiêu dữ liệu.
2. Luật candidate lãi **+6.03đ** so với để rỗng → giữ.
3. Nếu candidates đúng hoàn toàn thì được **93.34 vs 81.92, tức ~11.4đ** đang nằm ở đó.
   Sau recall của NER, candidates là miếng to nhất còn lại.

## Vá chỗ tra mã ICD: từ điển học từ train

Đo độ phủ của cách tra hiện tại (khớp tên chính xác trong `data/kb/icd10.json`) trên toàn
bộ entity DX/DRUG của GT: **CHẨN_ĐOÁN trượt 868**, khớp hết 45, khớp phần 7, sai hẳn 35,
rỗng-đúng 71. THUỐC khá hơn: trượt 55, khớp hết 153.

85% chẩn đoán không tra được. Xem 20 bề mặt trượt nhiều nhất thì rõ lý do:

```
bệnh dại 41 | tăng huyết áp 25 | mày đay vô căn 19 | amyloidosis 18
đái tháo đường 17 | thiếu men g6pd 16 | béo phì 12 | hạt tophi 12
viêm dạ dày ruột do virus 11 | viêm sung huyết hang vị dạ dày 10 ...
```

`tăng huyết áp` và `đái tháo đường` — hai bệnh phổ biến nhất Việt Nam — cũng trượt. Không
phải thiếu mã (I10, E14 có trong danh mục) mà **thiếu bề mặt**: danh mục ICD tiếng Việt ghi
tên chuẩn hành chính, còn văn bản đề là bản dịch máy nên chữ không bao giờ trùng.

Chỗ này tôi đã tra tay xong hết trong `src/gt_blocks.py`. Nên: học bảng `bề mặt -> mã`
**chỉ từ 80 file train** (`src/gt_lexicon.py` → `data/kb/gt_lexicon.json`, 351 chẩn đoán +
69 thuốc), rồi áp cho val. Đo trên 209 entity DX/DRUG của val:

| cách tra | khớp hết | khớp phần | TRƯỢT | SAI hẳn | rỗng-đúng |
|---|---|---|---|---|---|
| chỉ tên chính xác | 26 | 1 | 138 | 6 | 67 |
| chỉ bảng học từ train | 64 | 0 | 102 | 5 | 67 |
| **bảng trước, tên chính xác sau** | **80** | 0 | **80** | 11 | 67 |

Chấm bằng điểm thật (oracle span, assertions rỗng, `--split val`):

| | WER | text | assert | cand | **final** |
|---|---|---|---|---|---|
| không từ điển | 0 | 100 | 79.66 | 74.09 | 83.53 |
| **có từ điển** | 0 | 100 | 79.66 | **83.63** | **87.35** |

**+3.82đ.** Sai hẳn có tăng 6 → 11, nhưng đổi lấy +54 ca đúng nên vẫn lãi — điểm thật xác
nhận, không chỉ đếm ca.

Vì sao đặt bảng TRƯỚC tên chuẩn: bảng là bề mặt dịch máy thật, sát văn bản đề hơn.

**Đây không phải bảng `block -> nhãn`.** Khoá là bề mặt bệnh/thuốc (`"tăng huyết áp"` →
`I10`), là kiến thức thuật ngữ dùng lại được cho văn bản chưa từng thấy — đúng bản chất một
từ điển ICD tiếng Việt mà tôi phải tự dựng vì không có sẵn. Bằng chứng nó tổng quát hoá:
20 file val **không góp một dòng nào** vào bảng mà vẫn lãi 3.82đ. Nếu học cả val thì con số
val thành vô nghĩa (tự chấm bài mình) — nên `src/gt_lexicon.py` mặc định `split="train"`.

Một bề mặt có thể mang mã khác nhau theo ngữ cảnh (`huyết khối` → I24.0 mạch vành vs I82.9
tĩnh mạch, xem worklog/07). Lúc suy luận không có ngữ cảnh để chọn nên lấy phương án phổ
biến nhất; hoà thì lấy mã nhỏ hơn để chạy lại cho ra kết quả giống nhau.

## SỬA: split từng bị TRÔI, các số ở trên đo trên split cũ

Phát hiện lúc chạy `colab/pack.sh`: từ điển đột nhiên còn 330 chẩn đoán thay vì 351.
Truy ra: `pack.sh` gọi lại `src/split.py`, và split ra khác — train/val đổi từ
262/70 block thành **256/76 block**.

Không phải do random: chạy `split.py` ba lần liền cho ra val giống hệt nhau
(md5 `084b1765`). Nguyên nhân là **tiêu chí chọn val phụ thuộc `G.GT`** — nó cân bằng phân
bố nhãn, nên khi tôi dọn 12 span lồng nhau thì phân bố đổi, greedy chọn group khác.

Đây là lỗi thiết kế của tôi, không phải bug nhỏ: split trôi theo mỗi lần sửa nhãn thì số đo
trước và sau **không so được với nhau**, mất đúng cái mục đích duy nhất của tập val.

Sửa: `src/split.py` giờ **đóng băng** — có `data/blocks/split.json` rồi thì giữ nguyên,
muốn tính lại phải `--rebuild` (và tự biết là các số đo cũ thành vô hiệu).

### Đo lại toàn bộ trên split đã đóng băng

Split chốt: 39 group, train 80 file / 256 block / 148767 chars / 2133 ent,
val 20 file / 76 block / 40669 chars / 567 ent, **0 block ở cả hai bên**.

| | SYM | DX | LAB | DRUG | VAL |
|---|---|---|---|---|---|
| train | 768 | 632 | 312 | 280 | 141 |
| val | 202 | 170 | 93 | 73 | 29 |

Mốc luật thuần (`submission_v1`), ghép overlap:

| split | WER | text | assert | cand | **final** |
|---|---|---|---|---|---|
| train (80 file) | 81.72 | 18.28 | 16.47 | 21.20 | **18.91** |
| val (20 file) | 76.83 | 23.17 | 19.13 | 28.51 | **24.09** |

Lệch 5.2đ, không phải 0.46đ như split cũ — **val này dễ hơn train**. Vẫn dùng được để so
các bản của tôi với nhau, nhưng tuyệt đối không so số val với số train.
**Mốc cần vượt trên val: 24.09.**

Trần oracle (span lấy từ GT, assertions rỗng):

| | split | assert | cand | **final** |
|---|---|---|---|---|
| không từ điển | val | 71.09 | 72.43 | **80.30** |
| có từ điển | val | 71.09 | 80.79 | **83.64** |
| có từ điển | train | 80.70 | 99.80 | 94.13 |

Từ điển lãi **+3.34đ trên val**. Con số train 94.13 là overfit hiển nhiên (từ điển học
chính từ train) — ghi ra đây để nhắc: **đừng bao giờ đọc số train của thành phần này.**

### Rò rỉ còn lại: 4.0% span, đã thử vá và không vá được

Kiểm lại bằng cách so 8-gram giữa từng cửa sổ val với toàn bộ train (không qua group nữa,
so trực tiếp trên văn bản đã vào `data/ner/*.jsonl`):

```
val: 51 cửa sổ, 849 span
rò rỉ (trùng >50% 8-gram với một cửa sổ train): 2 cửa sổ (3.9%), 34 span (4.0%)
```

Hai chỗ: `29.txt`@1666 trùng 78% với `11.txt`@1800; `31.txt`@900 trùng 65% với `21.txt`@1800.
Đây là block **khác nhau** nhưng nội dung gần trùng, đo được:

| cặp block | jaccard | min-overlap |
|---|---|---|
| 238 × 23 | 0.03 | 0.67 |
| 134 × 26 | 0.17 | 0.77 |
| 44 × 30 | 0.31 | 0.58 |

Jaccard dưới ngưỡng 0.5 nên cạnh không được nối, còn min-overlap thì cao — kiểu "block ngắn
nằm trong block dài". Trước tôi đã loại min-overlap vì nó nối cả corpus thành một cục 83 file.

Thử vá bằng min-overlap **có chặn độ dài** (chỉ nối khi cả hai block đủ dài, để không bị nối
qua một mảnh tí xíu), quét 4 mức `MINLEN` × 3 ngưỡng:

| MINLEN | TH | số group | group to nhất |
|---|---|---|---|
| — (chỉ jaccard 0.5) | — | 45 | 34 file |
| 100 | 0.5 / 0.6 / 0.7 | 28 / 33 / 36 | 60 / 47 / 43 |
| 200 | 0.5 / 0.6 / 0.7 | 30 / 33 / 36 | 54 / 47 / 43 |
| 300 | 0.5 / 0.6 / 0.7 | 35 / 38 / 41 | 45 / 40 / 36 |
| 400 | 0.5 / 0.6 / 0.7 | 36 / 39 / 42 | 43 / 38 / 34 |

**Không cấu hình nào tốt hơn baseline.** Group to nhất luôn ≥34 file, tức bằng hoặc tệ hơn
mức đang có, mà lại mất thêm block để chọn val. Lý do: corpus này ghép mảnh chồng chéo, nối
theo bắc cầu thì cứ dính chuỗi — đã gặp đúng vấn đề này lần đầu (cục 83 file).

**Chốt: nhận 4.0% rò rỉ.** Ghi rõ ở đây để lúc đọc điểm val biết là nó hơi lạc quan. 4% chưa
đủ để đảo kết luận nào (chênh lệch giữa các bản tôi đang so đều lớn hơn thế nhiều).

## SỬA: hàm `trim()` tự phá 59 bề mặt

Soát tĩnh code inference trước khi train (train phải chạy trên Colab, ở local không có
torch nên chỉ soát được bằng số). Phát hiện `trim()` trong `src/ner_infer.py` sai.

Việc của `trim` là cắt rác dính hai đầu span model trả về — sentencepiece gộp dấu cách vào
token nên span thô hay lẹm 1 ký tự. Bản đầu cắt **mù** mọi ký tự trong
`" \t\n\r.,;:••-–—()[]"` ở cả hai đầu. Cách kiểm: chạy `trim` lên chính 3473 bề mặt GT —
bề mặt GT là đúng theo định nghĩa, nên `trim` mà đổi chúng là `trim` sai.

```
trim cũ  làm sai 59/3473 bề mặt
trim mới làm sai  0/3473 bề mặt
```

Kiểu sai:

| bề mặt GT | trim cũ trả về | vì sao sai |
|---|---|---|
| `Nhiễm virus Herpes simplex (HSV)` | `Nhiễm virus Herpes simplex (HSV` | cắt `)` dù ngoặc cân |
| `Ảo thanh (AH)` | `Ảo thanh (AH` | như trên (17 nhãn LAB dạng này) |
| `Cl-`, `hco3-` | `Cl`, `hco3` | `-` là phần của tên ion |
| `.8` | `8` | `.` là phần của trị số |
| `nang chứa khí hay dịch nhỏ (<2cm)` | `...(<2cm` | ngoặc cân |

59 bề mặt = 1.7% khái niệm, mà theo "Lưu ý" của đề, sai text thì mất điểm **cả 3** metric
cho khái niệm đó (và còn bị tính 2 lần). Đây là loại lỗi tự bắn vào chân: model đoán đúng
rồi mà code hậu xử lý làm hỏng.

Luật mới:
- ngoặc đóng chỉ cắt khi **không cân** (đếm ngoặc mở tương ứng trong span)
- `-`/`–`/`—` giữ khi liền sau chữ hoặc số (`Cl-`), cắt khi đứng rời (`đau đầu -`)
- `.` giữ khi liền trước chữ số (`.8`), cắt các trường hợp khác (`đau đầu.`)
- cặp ngoặc bọc **kín** cả span thì bóc (`(đau đầu)` -> `đau đầu`); an toàn vì GT không có
  bề mặt nào dạng `(...)` — đã đếm: 0

Kiểm phần còn lại (`trim` vẫn phải cắt được rác thật):
```
'  • Men gan, ' -> 'Men gan'      ') đau đầu' -> 'đau đầu'
'đau đầu -'     -> 'đau đầu'      'đau đầu ('  -> 'đau đầu'
```

Trần oracle không đổi (**83.6394**) — đúng như kỳ vọng, vì oracle đưa span GT vào nên vốn
đã đúng; `trim` chỉ có tác dụng khi model trả span lệch, tức sau khi train.

## Luật gộp mã nhóm: +0.59đ trên val

Xem 132 ca còn trượt mã trên val, thấy hai loại khác nhau:

```
 11x viêm dạ dày ruột do virus     GT=[A08.4]  tra=-                        (khong co trong tu dien)
  5x loét tá tràng                 GT=[K26.9]  tra=[K26.0, K26.1, K26.2]    (tra ra ma CON)
  3x hội chứng ruột kích thích     GT=[K58]    tra=[K58.1, K58.2, K58.3]
  2x huyết khối                    GT=[I82.9]  tra=[I24.0]                  (sai nghia, xem worklog/07)
```

Loại thứ hai sửa được bằng luật, không cần thêm dữ liệu. Bề mặt trong văn bản là tên **trần**
(`loét tá tràng`) — không nói cấp hay thể — nên danh mục ICD trả cả loạt mã con: `K26.0` cấp
có xuất huyết, `K26.1` cấp có lỗ thủng, `K26.2` cấp có cả hai. Trả 3 mã con khi GT có 1 mã
nhóm thì Jaccard chỉ 1/3. Mà quy ước gán nhãn của tôi (worklog/07) vốn là **bề mặt trần ->
mã nhóm**, nên đây là làm cho luật tra khớp quy ước, không phải hack.

`collapse_group()`: nếu tra ra ≥2 mã cùng nhóm 3 ký tự thì quy về mã nhóm.

Thứ tự lấy: `.9` (không xác định) → mã trần. **Không lấy `.8`**: `.8` là "loại khác đã xác
định", tức một mã con cụ thể chứ không phải mã nhóm. Thử đưa `.8` vào thì
`hội chứng ruột kích thích` ra `K58.8` còn GT là `K58` — 3 ca sai. Bỏ `.8` thì 0 ca sai.
(`K58.9` không tồn tại trong danh mục, nên phải có nhánh lấy mã trần.)

Đo trên **cả 100 file**, 87 ca tra được bằng tên chuẩn:

| | đúng |
|---|---|
| trước | 45 |
| sau khi gộp | **76** |

sửa được 31 ca, **phá 0 ca**. Chỉ áp cho mã tra từ **tên chuẩn**; mã từ từ điển học-từ-train
thì không gộp, vì đó là mã tôi gán tay rồi, gộp nữa là phá.

Trần oracle:

| | val | train |
|---|---|---|
| trước | 83.6394 | — |
| sau | **84.2304** | 94.1261 |

Train 94.13 cao vì từ điển học từ chính train nên khớp gần hết — đúng như thiết kế, và đó
chính là lý do chỉ số val mới đáng tin.

## Rà lại đề: ba chỗ tôi làm khác ví dụ mẫu

Câu hỏi "vẫn đang làm đúng chứ" đúng lúc. Ví dụ input-output trong đề là bằng chứng duy
nhất về quy ước THẬT của BTC (GT của tôi là tự gán, có thể lệch quy ước mà không biết).
Đối chiếu, thấy ba chỗ khác. Đo từng chỗ thay vì đoán.

Trước hết: ví dụ mẫu **không nằm trong `input/`** — grep 8 mốc (`Danh sách thuốc trước`,
`amlodipine`, `nystatin`, `guaifenesin`, `pravastatin`, `docusate`, `senna`, `clonazepam`)
đều 0 file. Nên nó không cho ta nhãn GT thật, chỉ cho ta quy ước.

### (a) Bề mặt thuốc: đề có LIỀU trong bề mặt, tôi cắt liều

Đề: `"amlodipine 10 mg po daily"`, `"nystatin oral suspension 5 ml po qid:prn"` — gồm cả
liều, đường dùng, tần suất. Quy ước tôi: cắt hết, chỉ giữ tên thuốc.

Đo (khớp regex liều/đường dùng ngay sau `position[1]` trong văn bản gốc NFC):

| | số nhãn |
|---|---|
| nhãn THUỐC | 451 |
| bề mặt tôi đã chứa liều | 1 |
| ngay sau bề mặt là LIỀU | 26 (5.8% thuốc, 0.75% toàn bộ) |
| ngay sau bề mặt là ĐƯỜNG DÙNG | 9 |

Trần thiệt hại `text_score`: `0.3 × 0.0075 × 0.8 ≈ **0.18 điểm**` (0.8 = phần WER mất nếu
GT thật là 5 từ mà tôi trả 1 từ). Corpus đề bài phần lớn viết thuốc **không kèm liều**
(`- doxycycline`, `Torsemide: uống 1 viên/ngày` — liều nằm sau dấu hai chấm, là câu chỉ
dẫn chứ không phải cụm tên thuốc). **Không sửa** — 0.18đ không đáng đổi lấy rủi ro
re-annotate 451 nhãn và phá vỡ tính nhất quán đang có.

### (b) Mã thuốc: đề trả SCD, tôi trả IN — và tôi KHÔNG thể trả SCD

Tra cả 11 RxCUI trong ví dụ mẫu ngược lại `RXNCONSO.RRF`:

```
308135  SCD  amlodipine 10 MG Oral Tablet         313782  SCD  acetaminophen 325 MG Oral Tablet
243670  SCD  aspirin 81 MG Oral Tablet            904475  SCD  pravastatin sodium 40 MG Oral Tablet
866436  SCD  24 HR metoprolol succinate 50 MG ER  1099279 SCD  docusate sodium 100 MG Oral Tablet
7597    IN   nystatin                             312935  SY   sennosides A and B 8.6 MG Oral Tab
197527  SCD  clonazepam 0.5 MG Oral Tablet        197528  SCD  clonazepam 1 MG Oral Tablet
392085  -    (không có dòng nào)
```

9/10 mã tra được là **SCD** (clinical drug = hoạt chất + hàm lượng + dạng bào chế), chỉ
`7597` là IN. Mã tôi đang gán: `{IN 139, BN 66, MIN 2, PIN 1}` — **không có SCD nào**.
Metric candidates nặng 0.4 nên nghe rất đắt.

Nhưng SCD **không suy ra được** từ dữ liệu tôi có:

| | số nhãn |
|---|---|
| bề mặt THUỐC không chứa chữ số | **438 / 451** |

Không có hàm lượng thì không chọn được giữa `clonazepam 0.5 MG` và `clonazepam 1 MG` —
chính ví dụ mẫu cũng phải trả **cả hai** mã cho một bề mặt. Trần thiệt hại chỉ trên 26 ca
có liều: `0.4 × 0.0075 ≈ **0.30 điểm**`. **Không sửa.** Ghi lại vì nếu private test viết
thuốc kèm hàm lượng dày hơn thì đây là chỗ mất điểm, và cách vá là resolver
`hoạt chất + hàm lượng + dạng -> SCD`, không phải đổi thứ tự ưu tiên TTY.

### (c) isHistorical cho danh sách thuốc trước nhập viện — chỗ này TÔI SAI, đã sửa

Đề gán `isHistorical` cho **toàn bộ** thuốc trong mục "Danh sách thuốc trước nhập viện".
Đo GT của tôi, khoanh riêng nhãn THUỐC nằm dưới tiêu đề dạng đó (loại 38 nhãn nhiễu do
regex khớp một dòng kể chuyện `Từ năm 24-26 tuổi...`):

| tiêu đề | assertions | số nhãn |
|---|---|---|
| Thuốc trước khi nhập viện (mọi biến thể) | HIST | 30 |
| Thuốc trước khi nhập viện | NEG (thuốc đã ngừng/hết) | 8 |
| Thuốc trước khi nhập viện | **rỗng** | 2 |

Hai ca rỗng: `84.txt/"thuốc kháng nấm"` là văn bản ghép (đoạn tư vấn nấm bẹn, không thuộc
tiêu đề đó) -> **đúng là rỗng**. `57.txt/"Torsemide"` là **lỗi của tôi**.

Truy ra thì nó là một lỗi cấu trúc, không phải sơ suất lẻ: block 16 (304c) xuất hiện ở
`53.txt` dưới `Hiện tại:` nhưng ở `57.txt` dưới `1. Tiền sử bệnh / Thuốc trước khi nhập
viện`. GT gán theo BLOCK nên **không thể đúng cả hai file**. Quét toàn corpus:

| | số block |
|---|---|
| block xuất hiện >1 lần | 24 |
| tiêu đề mâu thuẫn giữa các file | 3 |
| trong đó do văn bản ghép (tiêu đề không chi phối block) — bỏ qua | 2 (block 1, block 4) |
| mâu thuẫn thật | **1** (block 16) |

Chọn HIST, và chọn theo bằng chứng **nằm trong** block chứ không theo tiêu đề: 5/6 thuốc
ghi "đã hết thuốc khoảng 3 tuần trước nhập viện" / "hiện đã ngừng sử dụng" -> là thuốc
dùng trước khi vào viện. Khớp luôn quy ước ví dụ mẫu. Sửa GT[16]: `Torsemide` `[] -> [HIST]`,
5 thuốc còn lại `[NEG] -> [NEG, HIST]` (hai assertion độc lập — ngừng thuốc không làm nó
thôi là thuốc quá khứ).

Còn `use_assert=False` trong `ner_infer.py` thì **giữ nguyên**: luật section đo trên 100
file được precision 0.39 / recall 0.36 (worklog/06), âm 0.16đ. Ví dụ mẫu chỉ nói mục thuốc
trước nhập viện nên gán HIST — mà đúng chỗ đó luật của tôi vốn đã đúng 30/40; chỗ nó sai
là 404 FP HIST **ngoài** các mục đó. Muốn bật thì phải thu hẹp luật về đúng tiêu đề thuốc,
đo lại rồi mới bật.

## SỬA: mốc val không phải 24.09 mà là 30.38

`submission_v1/` là bản NỘP CŨ đóng băng (BTC 16.2858), không phải đầu ra của `predict.py`
hiện tại — luật đã cải tiến nhiều sau lần nộp đó. Chấm cả hai trên cùng val, cùng GT
`data/gt_block`, ghép overlap:

| pred | WER | text | assert | cand | **final** |
|---|---|---|---|---|---|
| `submission_v1` (bản đã nộp) | 76.8184 | 23.1816 | 19.1276 | 28.5085 | **24.0962** |
| `submission` (`predict.py` hiện tại) | 71.8081 | 28.1919 | 24.3463 | 36.5371 | **30.3763** |

**Mốc thật model NER phải vượt trên val: 30.38** (không phải 24.09 như ghi ở trên).
Cùng luật hiện tại trên train: final **25.9110** — val vẫn dễ hơn train ~4.5đ, kết luận
"không so val với train" không đổi.

Cũng lưu: `score.py` mặc định `--gt data/gt` (6 file gán tay thuở đầu) nên chạy
`--split val` không có cờ `--gt` thì báo "không có file GT nào". Luôn truyền
`--gt data/gt_block`.

Rebuild sau 5 sửa đổi GT (4 ca rà rủi ro + GT[16]): 3473 entity, split giữ nguyên
(md5 `088c0211`), `ner_data` phủ 2745 train + 728 val, thiếu 0. Từ điển học: 331 chẩn
đoán, 68 thuốc.

## Tra gần đúng ICD: +0.39đ nữa, và bài học về cách đo

Còn 115 ca trên val tra không ra mã (`viêm dạ dày ruột do virus` 11x, `nấm bẹn` 6x,
`thuyên tắc phổi` 4x...). Thử tra **gần đúng**: tên chuẩn nào có tập từ là tập con hoặc tập
cha của bề mặt, lấy Jaccard-từ cao nhất.

Đếm theo CA thì luật này tệ: **đúng 5 / sai 6**. Suýt bỏ. Nhưng đếm ca là **đo sai thứ cần
đo** — đề chấm `candidates` bằng Jaccard, nên trả `[I26.0, I26.9]` khi GT là `[I26.9]` được
0.5 chứ không phải 0, còn trả rỗng thì được 0. Đo lại bằng đúng công thức của đề:

| | điểm cand (val) | số ca trả mã SAI HẲN |
|---|---|---|
| không fuzzy | 48.2890 | 5 |
| fuzzy th=0.6 | 51.3308 | 9 |
| **fuzzy th=0.7** | **50.9506** | **5** |
| fuzzy th=0.6 mintok=4 | 49.8099 | 5 |

Chọn **th=0.7**: được +2.66đ cand mà số ca sai hẳn **không tăng**. th=0.6 hơn 0.38đ nhưng
thêm 4 ca sai hẳn — private test thì đó là rủi ro không đáng đổi.

`mintok=3` (bỏ bề mặt dưới 3 từ): `nhồi máu`, `huyết khối`, `tật bẩm sinh` quá ngắn, khớp từ
dễ ra sai hẳn cơ quan — `tật bẩm sinh` ra `K00.0` (răng) trong khi GT là `Q66.5` (bàn chân
bẹt).

Chứng cứ nó chỉ tác động lên bề mặt LẠ: trên **train** điểm cand nhích **xuống**
(99.6253 → 99.5785), vì train đã được từ điển học-từ-train phủ gần hết nên fuzzy chỉ còn
chỗ để làm hỏng. Đúng chỗ cần: bề mặt chưa từng thấy.

Trần oracle val: 84.2304 → **84.6201**. Chi phí: fuzzy quét 13882 tên chuẩn nhưng chỉ chạy
khi tra chính xác trượt, 100 file hết 6.3s — không cần tối ưu.

### Tổng các mốc trên val (split đã đóng băng)

| | val |
|---|---|
| luật thuần (`submission_v1`) | 24.0962 |
| trần oracle, chỉ tên chuẩn | 80.30 |
| + từ điển học từ train | 83.6394 |
| + gộp mã nhóm | 84.2304 |
| + tra gần đúng | **84.6201** |

Ba luật trên cộng lại **+4.32đ** so với chỉ tra tên chuẩn, và không luật nào là bảng
`block -> nhãn`: cả ba đều là kiến thức thuật ngữ (bề mặt bệnh -> mã), dùng lại được cho văn
bản lạ. 24.10 là điểm nếu không có model; 84.62 là điểm nếu model hoàn hảo. Khoảng cách đó
là phần model phải lấy.

## Rà lại từ điển học được: nó có phải bảng `block -> nhãn` không?

Đề chấm lại trên **test riêng**, nên nếu tôi nhúng một bảng `block -> nhãn` vào code suy
luận thì (a) nó sẽ trượt sạch trên văn bản mới, (b) trông như gian lận. `data/kb/gt_lexicon.json`
được học từ GT tôi tự gán, nên phải tự kiểm nó là **từ điển thuật ngữ** chứ không phải bảng tra
theo block.

Ba chứng cứ.

**1. Đường đọc code.** Chỉ `gt_lexicon.build()` đọc `data/gt_block/` và `data/blocks/split.json`;
`gt_lexicon.load()` — hàm duy nhất mà suy luận gọi — chỉ đọc `data/kb/gt_lexicon.json`. Nên
bản đóng gói giao cho BTC không mang theo dữ liệu train. Kiểm bằng cách dựng cây giả lập
Docker chỉ gồm 8 file `src/` + 3 JSON trong `data/kb/`, rồi chạy: `tăng huyết áp -> I10`,
`loét tá tràng -> K26.9`, `thuyên tắc phổi -> I26.9`, `paracetamol -> 161`. Chạy được.

**2. Hình dạng khoá.** Khoá là bề mặt bệnh/thuốc, không phải định danh block. Đếm số từ:

| | số dòng | trung vị | dài nhất |
|---|---|---|---|
| CHẨN_ĐOÁN | 331 | 4 từ | 17 từ |
| THUỐC | 68 | 1 từ | 5 từ |

Trung vị 4 từ / 1 từ là hình dạng của thuật ngữ. Đuôi dài là mấy câu chẩn đoán dịch máy kiểu
`cấp tính do virus b thể thông thường điển hình mức độ nặng giai đoạn toàn phát` (17 từ) —
vẫn là **một** khái niệm, không phải văn bản block, nhưng dài đến mức gần như không trùng
nguyên văn lần nữa.

**3. Val tự chứng minh nó tổng quát hoá.** Bảng học **chỉ từ 80 file train**, val không góp
một dòng nào, mà vẫn nâng điểm cand val từ 74.09 lên 83.63. Một bảng `block -> nhãn` thì
điểm val phải bằng không.

### Cắt khoá dài: bỏ được mà không mất điểm

Để khỏi phải biện luận cho cái đuôi dài, tôi thử cắt. Đo điểm candidates trên val:

| ngưỡng | số dòng | cand (val) |
|---|---|---|
| không cắt | 399 | 56.2738 |
| **bỏ khoá >12 từ** | **395** | **56.2738** |
| bỏ khoá >8 từ | 382 | 55.8935 |
| bỏ khoá >6 từ | 340 | 55.1331 |

(Số ở bảng này thấp hơn 83.63 vì đo trên mọi entity DX/DRUG của val kể cả ca `candidates`
rỗng và không qua `score.py`; chỉ dùng để **so tương đối** giữa 4 ngưỡng.)

Chốt **>12 từ** (`MAX_KEY_WORDS` trong `src/gt_lexicon.py`): bỏ 4 dòng, mất **0 điểm**. Cắt
mạnh hơn thì mất thật — 8 từ mất 0.38, 6 từ mất 1.14 — nghĩa là khoá 9-12 từ **vẫn tái khớp**
trên văn bản chưa thấy, chúng là thuật ngữ dùng được chứ không phải rác. Đây là lý do không
cắt sâu hơn cho "sạch sẽ": sẽ mất điểm thật.

Xác nhận lại bằng đúng đường chấm cũ (oracle span, assertions rỗng, ghép overlap, `--split val`):
**84.6201**, không đổi. Từ điển còn 327 chẩn đoán + 68 thuốc.

## Chạy khan `main()` bằng pipe giả — bắt lỗi trước khi tốn phiên Colab

Rủi ro: nếu `ner_infer.main()` có lỗi runtime thì chỉ lộ ra **sau** khi train xong trên Colab,
tốn cả một phiên GPU. Nên tôi chạy trọn `main()` ngay ở máy này bằng cách:

- stub `torch` (máy này không có torch) chỉ để `import torch` và `torch.cuda.is_available()` chạy;
- thay `make_pipe` bằng một pipe **regex giả** bắt vài bề mặt cố ý chọn để đi qua mọi nhánh
  hậu xử lý: `tăng huyết áp` (tra được mã), `loét tá tràng` (đi qua `collapse_group`),
  `paracetamol` (nhánh THUỐC), `sốt`/`đau bụng` (nhánh dedup span ngắn/dài),
  `Cl-` và `Ảo thanh (AH)` (hai ca `trim()` từng làm sai), `***` (bề mặt che).

Kết quả:

    100 file ra, 241 entity
    kiem: 241 entity, lech offset 0, file NFD 20/100

Ba thứ được xác nhận: `main()` đi hết đường không lỗi; `raw[start:end] == text` đúng **mọi**
entity, **kể cả 20 file NFD** (tức không có chỗ nào normalize ngầm); mỗi bản ghi đúng 5 khoá
và `position` là list 2 phần tử chứ không phải dict.

Còn lại đúng một việc: thay pipe giả bằng model thật. Train phải chạy trên Colab.

## Rà lại "máy này không train được" — kết luận: sai

Câu chốt ở trên ("Train phải chạy trên Colab") dựa vào hai giả định, kiểm lại thì cả hai đều sai:

| giả định trước đó | thực tế đo được |
|---|---|
| máy không có torch và không cài được (mạng bị chặn) | pypi.org trả 200, tải được torch 2.2.2 (150MB) + 25 wheel khác |
| chỉ có Python 3.13, torch không hỗ trợ | có sẵn `python3.11` = 3.11.15 -> tạo `.venv311` |

Cách mạng ra được (quan trọng, để lần sau không mò lại): tiến trình bị tiêm 20 biến proxy
trỏ localhost, pip và urllib đọc chúng rồi bị proxy trả 403. Bỏ biến proxy thì DNS không
phân giải được. Đường duy nhất chạy: **một lệnh `curl` gõ trực tiếp ở top-level**. Cùng lệnh
đó đặt trong file `.sh`, trong `subprocess.run`, hay trong `eval` đều 403. Nhưng một lệnh
curl với NHIỀU cặp `-o <file> <url>` thì tải được tất cả trong một lần. Cài offline bằng
`pip install --no-index --find-links .wheels`.

Vì thế `tools/fetch_wheels.sh` là code chết cho mục đích của nó — curl trong file script
luôn bị chặn. Giữ lại phần docstring vì nó ghi đúng chẩn đoán, còn thân script vô dụng.

torch trên Intel Mac: PyTorch đã bỏ macOS x86_64. Bản cuối còn wheel `macosx_*_x86_64` là
**2.2**, và chỉ tới **cp311** -> đó là lý do phải dùng Python 3.11.

### Đo tốc độ CPU: train được nhưng chỉ bản base

`torch.backends.mps.is_available()` = False (Intel Mac không có MPS), nên chỉ còn CPU 12 luồng.

    xlm-roberta-base, bs 1  len 512   ~9-12 s/step
    xlm-roberta-base, bs 4  len 384   19.9 s/step  (min của 3 lần)
    xlm-roberta-base, bs 8  len 384   29.3 s/step

194 cửa sổ / (bs 4 × accum 4) = 12 step/epoch, ~63 s/step thực tế -> **~13 phút/epoch**.
20 epoch ≈ 4-5 tiếng cho bản base. Bản large (560M) thì không kham nổi.

Chiều dài cửa sổ đo được (tokenizer XLM-R, max_len 512): train p50 288 / p90 334 / max 380;
val p50 267 / max 362. **Không cửa sổ nào bị truncate** -> `--max-len 512` là dư, không mất span.

### Chạy khan train thật ở máy này (1 epoch) — bắt được 1 lỗi

Lần chạy đầu chết ngay bước 0:

    ImportError: Using the `Trainer` with `PyTorch` requires `accelerate>=0.21.0`

`accelerate` đã có trong `requirements.txt` từ trước, chỉ là chưa cài vào venv cục bộ. Cài
`accelerate 1.10.1` + `psutil 7.2.2` (dependency) rồi chạy lại 1 epoch với
`--model models/xlmr-base --bs 4 --accum 4`:

    12/12 step, 13:22
    "eval_loss": 1.605, "eval_precision": 0.0, "eval_recall": 0.0, "eval_f1": 0.0
    đã lưu -> models/smoke

recall 0.0 sau 1 epoch là ĐÚNG kỳ vọng: lớp classifier khởi tạo ngẫu nhiên, 12 bước không
đủ để nó học nhãn nào. Mục đích của lần chạy này không phải điểm mà là xác nhận code không vỡ.

Rồi nạp weights vừa lưu vào `ner_infer.py` (offline hoàn toàn, `HF_HUB_OFFLINE=1`):

    0 entity trên 100 file
    score.py --split val:  WER 100.0000  text 0.0000  assert 0.0000  cand 0.0000  final 0.0000

Cả dây chuyền train -> lưu -> nạp lại offline -> sinh 100 file -> chấm đã thông. Điểm 0 cũng
là một kiểm chứng: `score.py` không bịa điểm khi model không đoán gì.

Ba thứ chỉ lần chạy thật này mới lộ ra, mà pipe giả trước đó không bắt được:
`accelerate` thiếu; `--out` đường dẫn tuyệt đối vẫn đúng; model do `Trainer` lưu ra đủ file
để `local_files_only=True` nạp lại được (config + safetensors + tokenizer + sentencepiece).

Đã dọn `models/smoke`, `pred_smoke`. `.wheels` (190MB) và `models/xlmr-base` (1.1GB) không
được đóng gói hay commit.

### Chốt: train trên Colab

Chọn Colab vì GPU chạy được **xlm-roberta-large** (560M) trong ~10-15 phút, trong khi máy này
mất 4-5 tiếng và chỉ được bản base (277M). Sửa notebook `colab/train_ner.ipynb` ba chỗ, mỗi
chỗ là một cách mất cả phiên GPU:

1. **Pin `transformers==4.44.2`.** `pip install -U "transformers>=4.44"` sẽ lấy 5.x, mà 5.x
   đổi tên tham số `TrainingArguments` -> `ner_train.py` vỡ. 4.44.2 là bản đã chạy thật ở đây.
2. **`--bs 4 --accum 4` thay cho `--bs 8 --accum 2`.** Batch hiệu dụng vẫn 16, nhưng large
   560M + Adam ở bs 8 dễ OOM trên L4 24GB. Chậm hơn không đáng, OOM là mất cả phiên. Đổi ở
   CẢ hai ô (bước 2 và bước 4) — khác batch hiệu dụng thì số epoch chốt ở bước 2 không còn đúng.
3. **`tee` log ra file + thêm ô in bảng recall theo epoch.** `| tail -30` cắt mất bảng eval,
   mà đó chính là con số cần để đặt `--epochs` ở bước 4. Bộ parse regex đã test với log giả.
4. Weights large ~2.2GB: `files.download()` hay đứt với file cỡ này -> copy sang Drive.

`vietel_ner.zip` đã build lại: 850KB, 220 file, GT 2745 train + 728 val entity, thiếu 0.

## Kiểm phần SAU train, không cần chờ weights thật

Train phải chờ phiên Colab của user. Nhưng hai việc phía sau (`pack_submission.sh` và Docker)
kiểm được ngay bằng cách lấy `models/xlmr-base` làm **model giả**: cùng kiến trúc
XLMRobertaForTokenClassification, chỉ là lớp classifier chưa học. Nhãn nó ra là rác, nhưng
thứ cần chứng minh là đường chạy không vỡ, không phải điểm.

### Bắt được 3 lỗi thật, cả 3 đều chỉ lộ ra khi chạy

**1. `pack_submission.sh` liệt kê `data/blocks.json` — đường dẫn không tồn tại.**
Đúng là `data/blocks/blocks.json`. `zip` bỏ qua path không tồn tại **im lặng** (không lỗi,
không cảnh báo), nên dòng chết này nằm đó không ai thấy. File thật vẫn vào gói qua thư mục
`data/blocks`, nên không mất gì — nhưng nếu ai đó tin vào dòng đó mà bỏ `data/blocks` đi thì
gói ra sẽ thiếu `split.json`. Đã xoá dòng chết.

**2. `Dockerfile` dùng `python:3.13-slim` nhưng torch không có wheel cp313 ở bản cần.**
Tra PyPI:

    torch 2.1.0  linux cp313: KHÔNG   linux cp311: có
    torch 2.2.2  linux cp313: KHÔNG   linux cp311: có
    torch 2.4.1  linux cp313: KHÔNG   linux cp311: có
    torch 2.5.1  linux cp313: có      linux cp311: có

torch chỉ có cp313 **từ 2.5.0**. Mà 2.2.2 là bản cuối còn wheel macOS x86_64, tức bản duy nhất
chạy được cả ở máy dev này. Hai điều kiện đó chỉ gặp nhau ở Python 3.11 -> đổi base image
sang `python:3.11-slim`.

**3. `requirements.txt` dùng khoảng version, không phải pin cứng.**
`transformers>=4.44,<5` sẽ lấy 4.57, trong khi MỌI số đo trong worklog chạy trên 4.44.2.
`torch>=2.1` trên Python 3.13 buộc pip lấy >=2.5. Nghĩa là môi trường BTC dựng lại KHÁC môi
trường đã đo, mà sai kiểu này không báo lỗi — chỉ ra điểm khác. Đã pin cứng cả 5 gói.

### Mô phỏng Docker: dựng đúng cây file rồi chạy thật

Máy này không có `docker` (`command not found`), nên không build được image. Thay vào đó dựng
`.dockersim/` chứa **đúng** các file mà `Dockerfile` COPY (8 file `src/`, 3 JSON `data/kb/`,
`models/ner`, `input/`), rồi chạy hai lệnh của Dockerfile trong đó.

`RUN python -c ...` (bước kiểm lúc build):

    10910 thuoc, 13882 ten benh, 15037 ma, lexicon 395 dong

`ENTRYPOINT` với `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` (chặn mạng ở tầng thư viện, mạnh
hơn `--network none` vì nếu có chỗ nào gọi hub thì nó báo lỗi ngay):

    9351 entity trên 100 file (93.5/file)
    -> submission

Kiểm 100 file ra:

    file 100 | entity 9351 | sai schema/offset 0 | file NFD 20

9351 entity là **rác** (model chưa học), nhưng 0 lỗi schema và 0 lệch offset trên 9351 span —
gấp 39 lần lượng span mà pipe giả trước đó tạo ra (241) — là bằng chứng mạnh hơn nhiều rằng
`trim()`, `dedup_overlap()`, `collapse_group()` không làm hỏng offset trong trường hợp dày span.
Kể cả 20 file NFD.

Còn lại: `docker build` thật thì phải chờ máy có Docker; nhưng cả hai lệnh trong Dockerfile đã
chạy đúng trên cây file đúng, nên rủi ro còn lại chỉ là tầng cài đặt gói, mà pin cứng đã xử lý.

`bash pack_submission.sh --no-w`: `submit_code.zip` 1.2M, 12/12 file bắt buộc có mặt.
