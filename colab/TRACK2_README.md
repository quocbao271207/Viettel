# TRACK 2 — model self-host ≤9B: dựng, chạy, kiểm soát

Phase 2/3 bắt buộc dựng lại kết quả bằng model **self-host ≤9B**, **không API**, **timeout 600 giây**.
Bắt buộc cho top-15. Điểm Phase 1 cao đến mấy mà thiếu Track 2 thì dừng ở đó.

FAQ BTC xác nhận: **dùng LLM tạo gold/synthetic để TRAIN là HỢP LỆ**; chỉ hệ thống NỘP BÀI
(inference) mới cấm API. Pipeline này hợp lệ.

## Trạng thái (30/07)

| | |
|---|---|
| Data train | `dev/track2/{train,dev}.jsonl` — sinh từ **`82x_cleanroom4_k2` = 38.6460** |
| Bảng tra mã | `dev/track2/code_map.json` (344 cụm) |
| **Trần trên** | **99.52% span+type · 100% mã** (đo bằng `verify`, KHÔNG cần GPU) |
| Output/file | ~688 ký tự ≈ **250 token** (định dạng gọn, giảm 4.2× so JSON) |
| Cần | **~42 token/giây** để kịp 600s |

## Ba lệnh

```bash
# 1. Sinh data từ gold tốt nhất  (chạy lại mỗi khi Phase 1 có bản tốt hơn)
python3 -m src.harness.track2 prep --gold out/candidates/82x_cleanroom4_k2.zip

# 2. Đo TRẦN TRÊN — không cần GPU. Chạy TRƯỚC khi tốn GPU.
python3 -m src.harness.track2 verify

# 3. Sau khi train + inference trên Colab, giải mã thành bài nộp
python3 -m src.harness.track2 decode --pred qwen_pred.jsonl --out out/candidates/track2_qwen.zip
```

## Chạy trên Colab

```python
!git clone https://github.com/quocbao271207/Viettel.git
%cd Viettel
!pip -q install "transformers>=4.44" peft trl bitsandbytes accelerate datasets
!python colab/track2_run.py --model Qwen/Qwen2.5-1.5B-Instruct --epochs 6
```
Xong thì tải `qwen_pred.jsonl` về máy và chạy lệnh `decode` ở trên.

## ⏱️ RÀNG BUỘC QUYẾT ĐỊNH: 600 giây — kiểm TRƯỚC khi nộp

100 file / 600s = **6 giây/file**, nhãn ~250 token/file ⇒ cần **~42 token/giây**.

| model | tốc độ trên T4 | kết luận |
|---|---|---|
| Qwen2.5-**1.5B** | ~60–120 tok/s | ✅ đạt thoải mái |
| Qwen2.5-3B | ~35–70 tok/s | ⚠️ sát ngưỡng |
| Qwen2.5-7B | ~15–25 tok/s | ❌ trượt, trừ khi dùng vLLM |

`track2_run.py` **tự đo và tự báo ĐẠT/KHÔNG** ngay sau inference. Đừng nộp nếu nó báo không đạt.

**Model nhỏ mà kịp giờ hơn model to mà timeout** — timeout là 0 điểm. Trần data đã 99.52%
nên phần quyết định là model học lại nhãn tốt đến đâu, không phải kích thước model.

## Định dạng nhãn — và vì sao không dùng JSON

```
D|Bệnh Kawasaki|1.
TH|sốt|nhân có
MN|paracetamol|dùng
```
- ký tự 1: `M` thuốc · `D` chẩn đoán · `T` triệu chứng · `X` tên xét nghiệm · `K` kết quả
- ký tự 2+: `N` phủ định · `H` tiền sử · `F` của người nhà (rỗng = khẳng định)
- trường 2: text nguyên văn · trường 3: 6 ký tự ngay trước span, để định vị

JSON đầy đủ nặng ~99 ký tự/concept ⇒ ~1060 token/file ⇒ cần 177 tok/s ⇒ **timeout chắc chắn**,
và không ai phát hiện cho tới lúc chấm. Định dạng này ~23 ký tự/concept.
`before` chỉ 6 ký tự vì đo được: 15 ký tự → 99.93% khôi phục · 6 → 99.73% · 0 → 97.37%.

**Mã KHÔNG do model sinh** — gán bằng bảng tra tĩnh lúc decode (không LLM, không API ⇒ hợp lệ),
verify cho thấy tra bảng khớp **100%**. Bắt model học thuộc ICD chỉ tốn token và kém chính xác hơn.

## Đã kiểm thử đầu-cuối (không cần GPU)

| tình huống giả lập | kết quả |
|---|---|
| model HOÀN HẢO (sinh đúng nhãn gold) | 2926 concept · cổng cứng ✅ |
| model KÉM (mất 20% dòng, cụt 10%, +3 dòng rác/file) | 2283 concept · cổng cứng ✅ |

Lần chạy thử đầu tiên **cổng cứng TỪ CHỐI ghi zip** vì model lộn xộn sinh span chồng lấn —
tức ngày chấm sẽ không có bài nộp nào. Đã sửa: gold thật có **0 cặp chồng lấn** nên mọi chồng lấn
là lỗi; `decode` lọc theo thứ tự tài liệu. Đánh đổi trần 99.73% → 99.52% để **luôn ra được bài nộp**.

## Bẫy đã trả giá

**Xuống dòng trong `before` phá định dạng theo dòng.** `before` như `' gì?\n\n'` bị cắt mất phần
sau xuống dòng ⇒ span không định vị được ⇒ trần rơi 99.7% → 96.7% **mà không có thông báo lỗi nào**.
Đã escape `\n`/`\r`/`\`. Sửa định dạng thì nhớ giữ escape.

## Việc còn lại

1. **Chạy Colab** (cần GPU của user) — việc duy nhất còn thiếu.
2. `decode` rồi nộp thử để biết Track 2 thật sự được bao nhiêu điểm.
3. Phase 1 có bản tốt hơn `82x` thì chạy lại `prep` với gold mới rồi train lại —
   gold là **trần trên** của model; gold kém 1 điểm thì model cũng kém chừng đó.

## Script cũ (`src/track2_*.py`) — đã thay thế
`track2_prep/codes/infer/verify.py` dùng định dạng JSON đầy đủ (sẽ timeout) và locator cũ.
Giữ lại để tham chiếu; dùng `src/harness/track2.py` thay thế.
