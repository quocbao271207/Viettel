# Nhật ký làm việc

Mỗi file là nhật ký của **một giai đoạn** hoặc **một scope** công việc. Không gộp nhiều scope vào một file, không tách một scope ra nhiều file.

## Quy ước đặt tên

```
<số thứ tự 2 chữ số>-<scope-slug>.md
```

Số thứ tự theo trình tự bắt đầu, không theo trình tự kết thúc. Scope phát sinh giữa đường vẫn lấy số tiếp theo.

## Cấu trúc mỗi file

```markdown
# <Tên scope>

- **Trạng thái**: đang làm | xong | tạm dừng | bỏ
- **Bắt đầu** / **Cập nhật**: YYYY-MM-DD
- **Liên quan**: PLAN.md §x, các worklog khác

## Mục tiêu
Ăn điểm ở đâu, hoặc mở đường cho việc gì.

## Đã làm
Theo thứ tự thời gian. Ghi cả việc thất bại và lý do.

## Kết quả đo được
Số liệu thật. Không ghi cảm nhận.

## Phát hiện
Điều học được mà PLAN.md chưa có. Nếu quan trọng → cập nhật PLAN.md và ghi rõ đã cập nhật.

## Việc còn lại
Checklist.
```

## Nguyên tắc

- Ghi **trong lúc làm**, không ghi hồi tố cuối ngày.
- Ghi cả đường cụt: cái gì không chạy, tại sao. Tránh thử lại vòng hai.
- Số liệu đo được luôn kèm cách đo, để lần sau lặp lại được.
- Phát hiện ảnh hưởng chiến lược → cập nhật `PLAN.md` ngay, worklog chỉ trỏ tới.
- Mỗi lần nộp leaderboard: ghi số hiệu bản nộp, thay đổi so với bản trước, điểm nhận được. Đây là dữ liệu đắt nhất của cuộc thi.

## Danh mục

| # | Scope | Trạng thái |
|---|---|---|
| [00](00-phan-tich-de-va-du-lieu.md) | Phân tích đề + khảo sát dữ liệu | xong |
| [01](01-xay-kb-icd10-rxnorm.md) | Xây knowledge base ICD-10 + RxNorm | đang làm |
| [02](02-kiem-chung-luat-tra-ma-thuoc.md) | Kiểm chứng luật tra mã thuốc RxNorm | đang làm |
| [03](03-ban-nop-thu-luat-thuan.md) | Bản nộp thử: pipeline luật thuần, không model | xong — 16.2858 |
| [04](04-unicode-nfd-va-annotate-gt.md) | Unicode NFD + annotate GT để chốt oracle | đang làm |
| [05](05-oracle-cham-diem-offline.md) | Oracle chấm điểm offline (đúng công thức đề) | xong |
| [06](06-va-luat-xet-nghiem-va-phan-doan-muc.md) | Vá nhánh xét nghiệm + phân đoạn mục | xong — oracle 18.09 → 30.68 |
| [07](07-gan-nhan-tay-cap-block.md) | Gán nhãn tay cấp block (phương án A) | đang làm |
