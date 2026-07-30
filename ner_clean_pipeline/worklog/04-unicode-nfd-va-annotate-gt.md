# Unicode NFD + annotate GT để chốt oracle

- **Trạng thái**: đang làm
- **Bắt đầu**: 2026-07-28 · **Cập nhật**: 2026-07-28
- **Liên quan**: [PLAN.md](../PLAN.md) §7, [worklog/03](03-ban-nop-thu-luat-thuan.md)

## Mục tiêu

Có GT thật cho vài file để chốt biến thể ghép entity trong [`src/score.py`](../src/score.py).
Không có GT thì mỗi thay đổi phải tiêu 1 lượt nộp/ngày mới biết tốt hay xấu.

## Phát hiện ngoài dự kiến: 20/100 file input ở dạng Unicode NFD

Đi tìm offset để annotate thì phát hiện dò chuỗi bị trượt. Nguyên nhân: **dấu
tiếng Việt lưu tách rời khỏi chữ**.

`ỏ` có hai cách lưu trong Unicode:
- **NFC** (dựng sẵn): 1 ký tự `U+1ECF`
- **NFD** (tách rời): 2 ký tự `o` + `U+0309`

20 file dùng NFD: `13 14 16 17 19 20 28 34 35 42 52 54 56 67 72 81 86 94 97 100`.
Tệ hơn: **có file trộn cả hai dạng trong cùng một file** — `100.txt` khớp
"tiền sản giật" ở 3 vị trí nhưng trượt chỗ thứ nhất.

### Hệ quả 1 — trượt entity thật

Đo bằng chính matcher của pipeline (`find_all`, có ràng buộc biên từ), gộp thành
một regex hợp nhất cho nhanh:

```
20 file NFD: triệu chứng 111 -> 122 (+11) | thuốc 28 -> 28 (+0)
```

Thuốc không đổi vì tên thuốc là ASCII, không có dấu. Chỉ nhãn tiếng Việt bị ảnh
hưởng.

### Hệ quả 2 — NFD còn sinh entity RÁC

Đây là chiều tôi không nghĩ tới lúc đầu. Trên file NFD, dò chuỗi `"ho"` khớp vào
giữa `"khỏe"`: các ký tự là `k`,`h`,`o`,`U+0309`, nên `ho` khớp trước khi dấu tới.
Ở `81.txt`, 4/10 lần khớp `ho` là rác:

```
pos   199 FP-dấu ' máu tên y học là throm'
pos   436 FP-dấu ' đến sức khỏe và cuộc'
pos   568 FP-dấu ' đến sức khỏe của mẹ v'
pos   684 FP-dấu '̀ và sức khỏe không ạ.'
```

Guard `(?<!WORD)needle(?!WORD)` **không** chặn được, vì `WORD = [\wÀ-ỹ]` không
chứa dấu tổ hợp trần (`U+0309` nằm ngoài khoảng `À-ỹ`).

Vì vậy tổng số lần khớp có thể **giảm** sau khi chuẩn hoá trong khi recall thật
lại **tăng** — hai chiều bù nhau. Lúc đầu tôi đo bằng `str.count()` không có biên
từ, ra "NFC giảm 11 lần khớp", và đã suýt kết luận sai rằng chuẩn hoá là có hại.
Số đúng phải đo bằng matcher thật của pipeline.

### Hệ quả 3 — chuẩn hoá làm lệch offset

BTC chấm `position` trên **file gốc**. Chuẩn hoá đổi độ dài chuỗi:

```
81.txt  1516 -> 1441   14.txt  2672 -> 2538   28.txt  2329 -> 2186
100.txt 1293 -> 1233   19.txt  2639 -> 2496   52.txt  1825 -> 1743
```

Nên không được chuẩn hoá rồi xuất offset của chuỗi đã chuẩn hoá — mọi span trong
20 file đó sẽ sai. Phải **match trên chuỗi NFC rồi map offset về gốc**.

### Cách xử lý: `src/textnorm.py`

`normalize(raw) -> (norm, imap)` với `imap[i]` = offset trong `raw` của ký tự
chuẩn hoá thứ `i`. Chuẩn hoá theo từng cụm (ký tự nền + các dấu theo sau) nên
map luôn nhất quán. `to_raw_span()` đổi span trên `norm` về span trên `raw`.

Kiểm chứng bằng `check()`: với mọi cửa sổ 5 ký tự lấy mẫu mỗi 7 bước, span map
về gốc phải có cùng dạng NFC. **Chạy sạch trên cả 100 file.**

```
python3 src/textnorm.py   # round-trip ok trên 100 file
```

## Việc còn lại

- [x] Phát hiện + đo NFD, viết `src/textnorm.py`, round-trip 100/100 file
- [ ] Nối `textnorm` vào `predict.py` (match trên NFC, xuất offset gốc)
- [x] Annotate GT 6 file 95–100 vào `data/gt/` — 125 khái niệm, xem worklog/05
- [x] Chạy `src/score.py` chốt biến thể ghép entity — chốt `overlap`, xem worklog/05
