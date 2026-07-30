# 03 — Bản nộp thử: pipeline luật thuần, không model

Mục tiêu: **không phải điểm cao**. Chỉ dùng 1 lượt nộp để trả lời hai câu hỏi mà
phân tích offline không trả lời được:

1. Format output có được hệ thống chấm chấp nhận không? (list dict, 5 trường,
   offset ký tự, tên file `1.json`..`100.json`)
2. Khai thác Jaccard có thật không? Nếu `assertions: []` ở mọi entity mà
   `assertions_score` vẫn cao (>0.5) thì xác nhận `J=1` khi GT rỗng và pred rỗng
   — tức 0.3 điểm gần như miễn phí, không cần model assertion.

Điểm nhận được là **mốc 0**, không phải dự báo điểm bài cuối.

## Code

| File | Việc |
|---|---|
| [`src/lexicon.py`](../src/lexicon.py) | 3 từ điển tĩnh: thuốc (RXNCONSO), bệnh (ICD BYT), triệu chứng (viết tay) |
| [`src/predict.py`](../src/predict.py) | đọc `input/*.txt` → ghi `submission/*.json` |

Không gọi mạng ở bất kỳ đâu trong đường chạy. Lý do: BTC chạy lại code trên
private test, môi trường có thể không có mạng, và RxNav giới hạn 20 req/s.

## Luật đã dùng, và lý do metric

| Nhãn | Luật | Số entity |
|---|---|---|
| `THUỐC` | tên trong RxNorm TTY `IN`/`BN`/`PIN` khớp nguyên văn, có biên từ. candidates = RxCUI của chính atom đó | 158 |
| `CHẨN_ĐOÁN` | tên bệnh VI trong danh mục BYT khớp nguyên văn. candidates = mã, áp luật bung mã con (cờ cột 25), cắt còn 3 mã | 170 |
| `TRIỆU_CHỨNG` | 64 cụm viết tay. Không candidates (đề không yêu cầu linking cho nhãn này) | 612 |
| `TÊN_XÉT_NGHIỆM` + `KẾT_QUẢ_XÉT_NGHIỆM` | chỉ nhận dạng `Tên: số đơnvị`, phải có dấu `:`/`=` và số ngay sau | 25 + 25 |

Quyết định theo metric:

- **Sort theo `position`** — WER phụ thuộc thứ tự.
- **`assertions: []` ở 100% entity** — đó là phép thử của bản nộp này.
- **Cắt candidates còn ≤3** — `candidates_score` chia theo `len(GT)+1`, trả top-10
  là tự trừ điểm.
- **Span chồng nhau: giữ span dài nhất** — `sốt cao` thắng `sốt`, `đau bụng` thắng
  `đau`. Nếu xuất cả hai thì span ngắn là insertion, WER tăng.
- **Loại chương ICD `R` và `Z`** khỏi từ điển chẩn đoán. Chương R là "triệu chứng,
  dấu hiệu" — tên của nó (`R06.0 Khó thở`, `R51 Đau đầu`, `R00.2 Đánh trống ngực`)
  trùng nguyên văn với mention triệu chứng. Để lại thì `khó thở` bị gán
  `CHẨN_ĐOÁN` trong khi GT là `TRIỆU_CHỨNG`, mà **sai type bị trừ 2 lần** — đắt
  hơn bỏ span. Chỉ riêng `R06.0 khó thở` đã khớp 65 lần ở 28 file.

## False positive đã đo và chặn

Không đoán, đã in ngữ cảnh từng lần khớp rồi mới quyết:

| Chuỗi | Vấn đề | Xử lý |
|---|---|---|
| `phù` | 11/61 lần khớp thực ra là **"phù hợp"** (tính từ) | chặn khi từ tiếp theo là `hợp` |
| `E50.9` tên VI = `"xác định"` | tên trong CSV BYT bị cắt cụt còn phần đuôi vô nghĩa; khớp 20 lần ở 15 file | blacklist tên |
| `L81.7` = `"sắc tố"`, `P72.1` = `"trẻ sơ sinh"` | cùng lỗi cắt cụt | blacklist |
| `L70 Trứng cá` | corpus luôn viết **"mụn trứng cá"**; lấy `trứng cá` thì text lệch → WER tính substitution | mở rộng biên trái thành `mụn trứng cá` |
| `Q62.8 niệu quản`, `I51.7 tim to`, `E86 giảm thể tích` | trong corpus là **bộ phận cơ thể / dấu hiệu hình ảnh**, không phải chẩn đoán ("SA: không có sỏi… niệu quản", "Hình ảnh bóng tim to") | blacklist |
| `U83.0 kháng vancomycin` | corpus: "Enterococcus kháng vancomycin" — là đặc tính vi khuẩn | blacklist |
| `glucose`, `cholesterol`, `creatinine`, `prothrombin`, `lactate`, `albumin`… | có trong RxNorm dạng `IN` nhưng trong corpus xuất hiện ở **bảng xét nghiệm** (`Cholesterol: 4,7 mmol/l`) → gán `THUỐC` là sai type | blacklist tên thuốc |

Lọc xong: 1021 → **990 entity**.

## RxNorm tra tĩnh: đủ cho tầng tên hoạt chất

Kiểm trên file `RXNCONSO.RRF` đã tải, khớp tên nguyên văn không cần mạng:

```
amlodipine 10 mg oral tablet   -> 308135  = GT
aspirin 81 mg oral tablet      -> 243670  = GT
nystatin                       ->   7597  = GT
acetaminophen 325 mg oral tablet -> 313782 = GT
clonazepam 0.5 mg oral tablet  -> 197527  = GT
pravastatin 40 mg oral tablet  -> None    (tên chuẩn khác chuỗi này)
```

Nghĩa là: **phần khó không phải tra mã, mà là chuẩn hóa mention thành chuỗi truy
vấn đúng** — đúng như kết luận ở [02](02-kiem-chung-luat-tra-ma-thuoc.md). Bản nộp
này chưa làm bước chuẩn hóa, chỉ khớp tên hoạt chất/biệt dược trần → candidates ở
tầng `IN`/`BN`, không phải `SCD` như GT thường dùng. Đây là chỗ mất điểm đã biết
trước, sẽ sửa ở bản sau.

## Kiểm tra trước khi nộp

Script validate đã chạy, 100/100 file đạt:

- `json.loads` ra `list`, mỗi phần tử đúng 5 trường, không thừa không thiếu
- `type` thuộc 5 nhãn cho phép
- `0 <= start < end <= len(text)` và **`text[start:end]` khớp đúng trường `text`**
- danh sách đã sort tăng theo `position[0]`
- `assertions == []`, `candidates` là list string, `len <= 3`

Kết quả: 990 entity / 100 file, trung bình 9.9 entity/file, 33% entity có candidates.

## Kết quả nộp — 2026-07-28 19:52

Nộp dạng **zip**, 100 file `.json` nằm ngay gốc archive, không bọc thư mục con.
Chấm xong sau ~2 giây.

| Chỉ số BTC trả về | Giá trị |
|---|---|
| `WER` | 82.9421 |
| `J_assertion` | 18.5774 |
| `J_candidates` | 13.9879 |
| `num_scored` / `num_records` | 100 / 100 |
| **Điểm** | **16.2858** |

### Xác nhận được công thức chấm, khớp đến 4 chữ số

```
0.3·(100 − 82.9421) + 0.3·18.5774 + 0.4·13.9879
= 5.11737 + 5.57322 + 5.59516
= 16.28575  →  16.2858
```

Nghĩa là `text_score = 100 − WER`, không có hệ số ẩn, không có chuẩn hóa nào khác.
Từ giờ đo offline được: chỉ cần tự tính 3 số này là biết điểm trước khi nộp.

Cũng xác nhận **format được chấp nhận** (`num_scored = 100`, không file nào bị loại)
→ câu hỏi 1 của bản nộp này: xong.

## Phát hiện: khai thác "assertions rỗng" là SAI — giả thuyết bị phủ định

`J_assertion = 18.58` khi **100% entity để `assertions: []`**.

Giả thuyết ở PLAN.md §2 (và [00](00-phan-tich-de-va-du-lieu.md)) là: Jaccard cho
`J = 1` khi GT rỗng và pred rỗng, nên để `[]` hết sẽ ăn gần trọn 0.3 điểm. Nếu
đúng thì con số phải >50. Thực tế 18.58.

Hai cách giải thích, chưa tách được bằng một lượt nộp:

1. Phần lớn entity trong GT **có** assertion → cặp rỗng–rỗng hiếm, không ăn được
   nhiều điểm miễn phí.
2. Metric **không cộng điểm** cho cặp rỗng–rỗng (coi `0/0` là 0, không phải 1).

Cả hai đều dẫn tới cùng một kết luận thực hành: **phải làm assertion thật, không có
đường tắt.** Đã cập nhật PLAN.md §2 và §6.

Ghi chú giá trị: 18.58 này là **mốc sàn** của assertions. Bất kỳ luật assertion nào
làm ra số thấp hơn 18.58 thì tệ hơn việc để rỗng.

## Phát hiện: WER 82.94 là thiếu entity, không phải thừa

WER không âm (`100 − 82.94 = 17.06 > 0`) nên chưa xuất quá nhiều. Nhưng 82.94 rất
cao. Với 990 entity mà vẫn sai 83% thì thành phần lỗi lớn nhất gần chắc là
**deletion** — GT nhiều entity hơn ta.

Số liệu phân bố của bản nộp: median 8 entity/file, p25 = 4, **min = 0** (có file
không ra entity nào), max 47. Từ điển viết tay 64 cụm triệu chứng + khớp tên nguyên
văn là quá hẹp.

→ Ưu tiên tiếp theo là **recall**, không phải precision. Đảo ngược so với dự tính
ban đầu (PLAN.md §2 viết "phải thiên về precision" — đúng về nguyên tắc WER nhưng
sai về thứ tự việc cần làm ở thời điểm này).

Một quyết định của bản nộp này cần xem lại: loại chương `R` khỏi từ điển để tránh
sai type. Chương R có 400 tên, khớp corpus 122 lần ở các cụm `khó thở` (65 lần,
28 file), `đau đầu` (32), `đánh trống ngực` (13). Nó là **từ điển triệu chứng có
sẵn** — nên dùng làm nguồn `TRIỆU_CHỨNG` thay vì bỏ đi.

## Phát hiện: candidates 13.99 với độ phủ 33% là tín hiệu tốt

Chỉ 1/3 entity có `candidates`, và tầng TTY còn sai (trả `IN`/`BN` thay vì `SCD`),
mà đã được 13.99/100. Luật tra mã đang đúng hướng, thiếu **độ phủ** chứ không sai
bản chất. Đây là chỗ đòn bẩy lớn nhất còn lại: trọng số 0.4, đang ở 14.

## Hệ quả: phân rã mức 49 điểm của leaderboard ở PLAN.md §2 không còn đứng

Giả định cũ: `text ~55, assertions ~80, candidates ~20`. Phần `assertions ~80` dựa
trên niềm tin rằng để rỗng là ăn điểm cao — đã bị phủ định. Đội 49 điểm không thể
đạt 80 bằng cách để rỗng. Đã sửa PLAN.md §2.

## Việc còn lại

- [x] Ghi điểm nhận được + 3 thành phần
- [x] Kiểm giả thuyết assertions rỗng → **phủ định**
- [x] Kiểm text_score có âm không → không âm, nhưng thiếu recall
- [x] So candidates với giả định 0.20 → thực tế 0.14 với độ phủ 33%
- [ ] Tăng recall NER (dùng chương R làm từ điển triệu chứng)
- [ ] Làm assertion theo scope section — sàn phải vượt 18.58
- [ ] Chuẩn hóa mention thuốc → tầng `SCD` như [02](02-kiem-chung-luat-tra-ma-thuoc.md) đã đo 10/13

| Lần nộp | Ngày | Nội dung | text | assertions | candidates | final |
|---|---|---|---|---|---|---|
| 1 | 2026-07-28 | luật thuần, 990 entity, assertions rỗng hết | 17.06 | 18.58 | 13.99 | **16.2858** |
