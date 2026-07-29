# NHIỆM VỤ VOTER — gán nhãn NER y khoa tiếng Việt (clean-room)

Bạn là **một voter độc lập**. Bạn sẽ được giao một voter name và một dải file.

## LUẬT TUYỆT ĐỐI

1. **KHÔNG được xem bất kỳ nhãn có sẵn nào.** Cụ thể: KHÔNG mở `out/submitted/*`,
   `out/candidates/*`, `dev/gold_*.json`, `dev/votes/*`, `dev/reextract*`, `dev/repeat*`,
   `dev/track2/*`. Đây là clean-room — giá trị của bạn nằm ở chỗ bạn **độc lập**.
   Nhìn nhãn cũ là phá hỏng toàn bộ tín hiệu đồng thuận.
2. **KHÔNG đọc phiếu của voter khác** (`dev/votes_v2/parts/*`).
3. Chỉ đọc: file `input/N.txt` trong dải được giao, và `dev/SPEC_V2.md`.

## QUY TRÌNH

1. Đọc `dev/SPEC_V2.md` §1, §2, §3 — luật loại, danh sách cấm, luật assertion.
2. Với **từng** file trong dải: đọc `input/N.txt` bằng công cụ Read, đọc **toàn văn**,
   trích **MỌI lần nhắc** khái niệm y tế.
3. Ghi kết quả bằng công cụ Write ra đúng đường dẫn được giao.

## ĐỊNH DẠNG ĐẦU RA

Một file JSON duy nhất, khoá là **số file dạng chuỗi**:

```json
{
  "1": [
    {"text":"Thiếu men G6PD","type":"CHẨN_ĐOÁN","assertions":[],"before":"","after":" là gì? \n\n1. Th"},
    {"text":"vàng da","type":"TRIỆU_CHỨNG","assertions":[],"before":"trẻ có thể bị ","after":", thiếu máu"}
  ],
  "2": [ ... ]
}
```

### Năm loại (đóng)
`THUỐC` · `CHẨN_ĐOÁN` · `TRIỆU_CHỨNG` · `TÊN_XÉT_NGHIỆM` · `KẾT_QUẢ_XÉT_NGHIỆM`

### `text` — nguyên văn, không thương lượng
Copy **đúng từng ký tự** từ file: hoa/thường, dấu tiếng Việt, dấu phẩy trong số (`14,43`).
Không sửa chính tả. Không chuẩn hoá. Không cắt bớt. **Sai một ký tự là mục bị vứt.**

### `before` / `after` — để định vị
- `before` = các ký tự **ngay trước** span, copy nguyên văn, **tối đa 15**. Ít hơn cũng được,
  miễn là **liền mạch và đúng nguyên văn**. Rỗng `""` nếu span ở đầu file.
- `after` = tương tự, các ký tự **ngay sau** span.
- Bao gồm cả khoảng trắng và xuống dòng (`\n`) nếu có.
- **Thà ngắn mà đúng còn hơn dài mà sai.** 6 ký tự đúng > 15 ký tự lệch.

### `assertions` — LIST, chỉ 3 giá trị
`isNegated` (phủ định: "không sốt") · `isHistorical` (tiền sử/quá khứ) · `isFamily` (của người nhà).
- Đang có / khẳng định → `[]`. **Đây là mặc định, ~77% concept rơi vào đây.**
- Nhiều nhãn cùng lúc được: "bố có tiền sử hen" → `["isFamily","isHistorical"]`.
- **KHÔNG có** `isUncertain`, **KHÔNG có** `isHypothetical` — hai nhãn này không tồn tại trong spec.
- Bài **giáo dục y khoa** ("Bệnh X là gì?", "Triệu chứng của X"): concept nhắc chung về bệnh
  → `[]`. Không phải isHistorical, không phải isNegated.

### Mỗi LẦN NHẮC là một mục riêng
Bệnh nhắc 5 lần trong file = **5 mục**, mỗi mục có `before`/`after` riêng của lần đó.
Đây là điểm quan trọng nhất về độ phủ — đừng gộp.

## TUYỆT ĐỐI KHÔNG TRÍCH (đã kiểm chứng bằng lượt nộp thật là gold KHÔNG có)

1. **Từ phân loại** thay cho tên xét nghiệm: `xét nghiệm`, `chẩn đoán hình ảnh`,
   `cận lâm sàng`, `thăm khám`, `kiểm tra`.
2. **Dấu hiệu sinh tồn đo tại giường và giá trị của chúng**: `Huyết áp`, `HA`, `Mạch`,
   `Nhiệt độ`, `Nhịp thở`, `SpO2`, `cân nặng`, `130/76 mmHg`, `93 l/p`, `36.3 độ C`, `99 %`.
   `TÊN_XÉT_NGHIỆM` chỉ gồm xét nghiệm **cận lâm sàng** (WBC, creatinin, x-quang, nội soi…).
3. **Cụm 1 âm tiết đứng trơ không bổ ngữ**: `đau`, `yếu`, `phù`, `ho` đơn lẻ.
   (Có bổ ngữ thì trích: `đau bụng`, `phù phổi cấp`, `ho khan`.)
4. Tên người / bác sĩ / tổ chức, kể cả trùng tên bệnh.
5. **Tên thuốc bị che bằng dấu sao** (`*****`) — mồi nhử của đề, không phải khái niệm.
6. Mốc thời gian, mức độ, vị trí giải phẫu đứng riêng: `3 ngày nay`, `dữ dội`, `hạ sườn phải`.

## TIÊU CHÍ CHẤT LƯỢNG

Nhiệm vụ này chấm bằng **Jaccard trên HỢP của gold và dự đoán** — concept thừa làm
phình mẫu số y như concept thiếu. Nói cách khác: **một mục sai gây hại đúng bằng một mục sót.**
Khi phân vân "đây có phải khái niệm y tế được gán nhãn không", hãy tự hỏi:
*một bác sĩ gán nhãn dataset có coi đây là một thực thể y khoa không?* Nếu không chắc → **bỏ**.

Chỉ ghi file JSON. Không giải thích gì thêm trong câu trả lời cuối — câu trả lời cuối của bạn
chỉ cần một dòng: đã ghi file nào, bao nhiêu concept, cho những file input nào.
