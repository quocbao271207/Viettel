# Xây knowledge base ICD-10 + RxNorm

- **Trạng thái**: đang làm
- **Bắt đầu**: 2026-07-28 · **Cập nhật**: 2026-07-28
- **Liên quan**: [PLAN.md](../PLAN.md) §3.2, §4 · [00-phan-tich-de-va-du-lieu.md](00-phan-tich-de-va-du-lieu.md)

## Mục tiêu

Dựng KB cho tầng linking — thành phần chiếm **0.4 điểm** và là chỗ nghi mọi đội đang thất bại. Yêu cầu: không cần UMLS license (user đã chốt không chờ duyệt), và inference phải chạy được **offline** vì BTC dựng lại code chấm private test.

## Đã làm

### Xác minh đường lấy RxNorm không cần license

Đọc tài liệu NLM qua WebFetch:

- **RxNav public API** — không cần license. `getAllConceptsByTTY` lấy concept theo TTY. `getRxcuiHistoryStatus` có scope **"Current and Historical"** → lấy được concept obsolete/remapped, đúng thứ GT cần. Giới hạn **20 req/s**, NLM khuyến nghị cache 12–24h. Có `getApproximateMatch` để mô phỏng hành vi annotator.
- **Prescribable subset** — public domain, không login, có RXNCONSO/RXNSAT/RXNREL. Nhưng **đã lọc bỏ suppressed + obsolete** → thiếu đúng mã GT cần. Chỉ dùng làm xương sống.
- **WHO ICD API** — ICD-10 chỉ có English + French, **không có tiếng Việt**. Loại, chỉ dùng bổ trợ tên Latin.

Kết luận: không có gì phải chờ. Bảng nguồn đầy đủ ở PLAN.md §4.

### Kiểm tra mạng trong sandbox

`curl -I` (HEAD) bị chặn → trả `HTTP 000`. Nhưng `curl -r 0-1000` (range GET) trả `206` bình thường. Bài học: **đo dung lượng bằng range request, không dùng `-I`**.

`$TMPDIR` bị reset giữa các lần gọi bash → không dùng làm nơi lưu file trung gian. Tải thẳng vào `data/raw/`.

### Tải + parse ICD-10 BYT

Nguồn: `tamton23/primekg-vn-icd10-omop` → `icd10_danh_muc.csv` (9.9 MB, 15.850 dòng CSV). File là Phụ lục Thông tư BYT xuất ra CSV, **29 cột**, có cả tên tiếng Việt và tên WHO English.

Cột dùng được:

| Cột | Nội dung |
|---|---|
| 14 | Mã nhóm bệnh 3 ký tự |
| 16 | Tên nhóm bệnh 3 ký tự (VI) |
| 17 | **Mã ICD đầy đủ** |
| 19 | Disease name WHO 2019 (EN) |
| 21 | **Tên bệnh (VI)** |
| 23 | Cờ: mã không được dùng làm bệnh chính |
| 25 | Cờ: **mã không được dùng vì có mã 4-5 ký tự cụ thể hơn** |

Parse ra `data/raw/icd10_kb.json`.

## Kết quả đo được

```
ICD-10 BYT: 15.037 mã hợp lệ (regex ^[A-Z]\d{2}(\.\d+)?$)
            15.037 mã độc nhất
            15.020 mã có tên tiếng Việt (99.9%)
```

Kiểm tra trên đúng ví dụ của đề:

```
K21    Bệnh trào ngược dạ dày - thực quản                          [cột25 = có mã cụ thể hơn]
K21.0  Bệnh trào ngược dạ dày - thực quản kèm viêm thực quản
K21.9  Bệnh trào ngược dạ dày - thực quản không kèm viêm thực quản
```

Đề: mention "bệnh trào ngược dạ dày - thực quản" → GT = `K21.0, K21.9`.

## Phát hiện

### Luật sinh candidate ICD của annotator — tái tạo được cơ học

Tên tiếng Việt của `K21` **khớp chính xác từng chữ** với mention, nhưng GT **không chứa `K21`** — chỉ có hai mã con. Cột 25 đánh dấu `K21` là "mã không được sử dụng vì có mã 4 hoặc 5 ký tự cụ thể hơn".

→ Luật suy ra: **match tên → nếu mã trúng bị cờ cột 25 thì bung ra toàn bộ mã con của nó, loại bỏ mã cha.**

Đây là luật cơ học, không cần model, và ăn thẳng vào `candidates_score` (0.4 điểm) cho nhánh `CHẨN_ĐOÁN`. Cần kiểm chứng trên nhiều mention hơn khi có data annotate ở GĐ1.

Cờ cột 23 ("không được dùng làm bệnh chính") có thể là luật lọc thứ hai — chưa kiểm chứng.

### Chưa rõ mức chi tiết GT dừng ở đâu

`K21.0` và `K21.9` là mã 4 ký tự. Chưa biết với nhóm có mã 5 ký tự thì GT bung tới cấp nào. Phải đo khi có data.

### Luật bung VÔ ĐIỀU KIỆN là sai — phải có điều kiện số con

Phát hiện lúc annotate 6 file đầu (2026-07-28, xem [04](04-oracle-va-annotate-gt.md)).
`K21` chỉ có **2 mã con** nên bung cả hai vẫn được Jaccard cao. Nhưng đo trên toàn KB:

```
1.556 mã có cờ cột 25 + có con
số con:  min 1 | p25 4 | median 7 | p75 9 | p90 10 | max 110
phân bố: 1-3 con 236 mã | 4-6 con 533 | 7-10 con 724 | >10 con 63
```

Ví dụ tệ nhất gặp thật trong corpus: mention "bệnh gút" → khớp `M10 Gút [thống phong]`
→ bung ra **66 mã con**. Nếu GT là 1-2 mã thì Jaccard ≈ 1/66 ≈ 0.015, tức gần như 0
điểm cho entity đó — **tệ hơn cả trả về mã cha sai**.

`K21` với 2 con là trường hợp thuận lợi nhất trong KB (p25 đã là 4 con). Suy luật từ
một ví dụ duy nhất, mà lại là ví dụ nằm ở đuôi phân bố, là lỗi phương pháp của tôi.

→ Luật phải sửa thành: **bung mã con chỉ khi số con nhỏ** (ngưỡng phải đo, phỏng đoán
ban đầu ≤3); nhiều con thì cần chọn mã cụ thể thay vì bung hết. Ngưỡng chốt sau khi
có GT đủ nhiều.

## Việc còn lại

- [x] Phát hiện luật bung vô điều kiện sai với mã nhiều con (M10 → 66 mã)
- [ ] Đo ngưỡng số con để quyết định bung / không bung (cần GT ≥ 30 mention CHẨN_ĐOÁN)
- [ ] Kiểm chứng luật bung mã con trên nhiều mention `CHẨN_ĐOÁN` hơn (chờ GĐ1 annotate).
- [ ] Kiểm tra license của `icd10_danh_muc.csv` trước khi đưa vào bundle.
- [ ] Tải RxNorm prescribable subset (~50 MB) làm xương sống index.
- [ ] Bổ sung concept historical qua `getRxcuiHistoryStatus` — chỉ gọi cho mention thuốc thật cần, không quét toàn bộ. Số lần gọi phụ thuộc GĐ1 (dedupe block) cho biết có bao nhiêu mention thuốc độc nhất.
- [ ] Xây bảng biệt dược Việt → hoạt chất (Medrol, Omez, Zestril, Fortex, Philpovin, Nitramyl…) — nhóm này không có trong RxNorm.
- [ ] Đóng băng KB thành file tĩnh cho bundle offline. Inference **không được** gọi RxNav.
- [ ] Ghi attribution NLM vào README bundle: "uses publicly available data from the U.S. National Library of Medicine (NLM)", NLM không endorse sản phẩm.
