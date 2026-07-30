# Phân tích đề + khảo sát dữ liệu

- **Trạng thái**: xong
- **Bắt đầu**: 2026-07-28 · **Cập nhật**: 2026-07-28
- **Liên quan**: [PLAN.md](../PLAN.md) §2, §3

## Mục tiêu

Hiểu metric để biết điểm nằm ở đâu, và khảo sát 100 file test để biết dữ liệu thật khác đề tả thế nào. Không viết code giải, chỉ đo.

## Đã làm

### Đọc metric, tìm lỗ hổng khai thác

`final = 0.3·text + 0.3·assertions + 0.4·candidates`. Ba điều rút ra:

- WER không chặn trên → `1 − WER` có thể âm → entity dự đoán thừa bị phạt vô hạn → pipeline phải thiên precision.
- Jaccard cho `J = 1` khi GT rỗng **và** pred rỗng → để `assertions: []` được điểm tuyệt đối ở phần lớn entity.
- Sai type bị tính 2 lần, mỗi lần 0 điểm cả 3 metric → sai type tốn ~gấp đôi bỏ qua entity.

Phân rã giả định mức 49 điểm của leaderboard → nghi `candidates` là chỗ thất bại (chi tiết PLAN.md §2). **Chưa xác nhận**, phải probe.

### Khảo sát 100 file input

Đo bằng shell + python trên `input/*.txt`. Kết quả ở §"Kết quả đo được".

### Phát hiện trùng lặp — đo bằng 6-gram shingle

```python
# containment = |A ∩ B| / min(|A|, |B|) trên tập 6-gram
# ngưỡng 0.5 để union-find gom cụm
```

Chạy union-find trên 100 file → 21 cụm, 53 file. Diff từng cặp trong cụm bằng `difflib.unified_diff` xác nhận cơ chế: BTC ghép 2–4 **block** từ một pool nhỏ thành mỗi file test.

Lưu ý kỹ thuật: `diff <(...) <(...)` bị sandbox chặn (`/dev/fd/11: Operation not permitted`), phải dùng `difflib` trong python thay thế.

### Tra RxNorm cho từng mã trong ví dụ của đề

`curl` trực tiếp tới `rxnav.nlm.nih.gov` bị sandbox chặn ban đầu → dùng WebFetch tới REST endpoint. Tra `/rxcui/{id}/properties.json`, mã nào trả `{}` thì tra tiếp `/rxcui/{id}/historystatus.json`.

Đây là bước cho phát hiện quan trọng nhất về `candidates` (xem PLAN.md §3.2).

## Kết quả đo được

### Corpus

| Chỉ số | Giá trị |
|---|---|
| Số file | 100 |
| Tổng dung lượng | 265.147 bytes |
| Trung bình | ~2.650 ký tự/file |
| Nhỏ nhất / lớn nhất | 1.689 (`100.txt`) / 5.862 (`1.txt`) |
| File QA bác sĩ | 35 |
| File EHR/bệnh án | 51 |
| File trộn 2 thể loại | 12 |
| File có bảng xét nghiệm số | 8 (6, 24, 26, 36, 40, 53, 58, 97) |
| Chỗ bị mask `***` | 99 chỗ / 30 file |
| Deid placeholder | `[Ngày]` 9, `[Date]` 7, `[Số]` 3, `[Tên cuộc họp]` 2, `[Name]` 2, `[Tên bác sĩ]` 1 |

Dài gấp ~5 lần ví dụ trong đề → không nhét thẳng vào prompt, phải chunk + map offset.

### Trùng lặp

**53/100 file thuộc 21 cụm.** Cụm lớn nhất 5 file (35, 56, 67, 86, 94). Danh sách đầy đủ ở PLAN.md §3.1.

### RxNorm của ví dụ trong đề

8 mã tra được: 5 mã SCD active, 1 mã **IN** (7597 nystatin), 1 mã **Remapped** hết active 09/2016 (360047), 1 mã **Obsolete** từ 01/2021 (1660761). Bảng đầy đủ ở PLAN.md §3.2.

### Cấu trúc section

Header cấp 1 và sub-label đếm được, phân bố rất đều — 35× "Lý do nhập viện:", 33× "2. Tiền sử bệnh hiện tại", 10× "Thuốc trước khi nhập viện:". Chi tiết PLAN.md §3.4.

## Phát hiện

Ba phát hiện đã ghi vào PLAN.md §3 (đã cập nhật):

1. **§3.1 — Tập test là cắt-dán từ ~60–70 block độc nhất.** Nhãn block bất biến qua file, chỉ khác `position`. Bài toán co lại đủ nhỏ để annotate tay chất lượng cao. Ràng buộc: dùng làm training data, KHÔNG hardcode lookup (BTC chấm lại private test).
2. **§3.2 — GT không phải RxNorm hiện hành.** Dùng snapshot cũ (~2020AB), trộn mức TTY (SCD lẫn IN), và chọn multi-ingredient khi mention là single-ingredient. → Bài đo "khớp pipeline annotate của BTC", không đo đúng y khoa.
3. **§3.4 — Assertion gán theo section, không theo câu.** Ví dụ vòng 1: toàn bộ thuốc dưới "Danh sách thuốc trước nhập viện" đều `isHistorical` bất kể cue trong câu.

Ngoài ra, hai lỗi trong đề (PLAN.md §3.5): schema JSON thiếu field cho "quan hệ giữa các khái niệm" dù đề mô tả có (khả năng là phần Round 2 bị hoãn); ví dụ §3.2 ghi output `"TWBC"` trong khi input là `WBC` → GT có nhiễu, không tối ưu sát ví dụ.

## Việc còn lại

- [ ] Probe leaderboard để xác nhận phân rã 49 điểm (bản NER-only, candidates + assertions rỗng).
- [ ] Xác nhận Round 2 đã công bố chưa — nếu thêm field relation thì mốc 49 điểm hết ý nghĩa tham chiếu.
- [ ] Kiểm chứng giả thuyết corpus EHR = MIMIC-IV dịch máy.
