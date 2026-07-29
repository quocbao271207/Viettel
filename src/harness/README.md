# HARNESS — sinh data một chiều, không chắp vá

Vấn đề của pipeline cũ: mỗi bản nộp là "nền bản N + vá thêm X". Sau 4 lớp vá (bản 14→17)
không ai còn tách được lớp nào ăn điểm, lớp nào lỗ, và một luật sửa ở `build_repeat.py`
không tự lan sang `build_reextract.py`. Harness này đổi hẳn cách làm:

```
input/*.txt  ──►  SPEC (đóng băng)  ──►  voter độc lập  ──►  ĐỊNH VỊ  ──►  LỌC CẤM
                                                                              │
   zip nộp  ◄──  CỔNG CỨNG  ◄──  GÁN MÃ  ◄──  GỘP PHIẾU (ngưỡng k)  ◄────────┘
```

**Muốn đổi hành vi thì sửa SPEC rồi chạy lại — không sửa tay JSON đầu ra.**

## File

| file | vai trò |
|---|---|
| `../../dev/SPEC_V2.md` | spec văn xuôi + bằng chứng từng luật. Đọc trước tiên. |
| `../../dev/VOTER_TASK.md` | hướng dẫn giao cho voter. Mọi voter dùng CHUNG file này. |
| `spec.py` | hằng số spec, danh sách cấm, `dot()`, prompt LLM. Nguồn sự thật của code. |
| `locate.py` | (text, before, after) → offset. Tất định. Thà loại còn hơn đoán. |
| `validate.py` | cổng cứng: schema, `raw[s:e]==text`, mã tồn tại, ICD có chấm, chồng lấn. |
| `build.py` | phiếu thô → bản nộp. Ngưỡng `k` là núm vặn. |
| `merge_parts.py` | gộp mảnh voter, báo mảnh thiếu. |
| `prune.py` | **Track A** — đãi bỏ concept rác khỏi bản nền. |
| `diff.py` | so 2 bản nộp; cảnh báo khi đổi nhiều trục cùng lúc. |
| `selftest.py` | harness tự chứng minh trên bản 14. **Chạy trước mọi thứ khác.** |

## Quy trình

```bash
# 0. Harness có làm mất concept không? Phải đạt ~100% trước khi tiêu 1 lượt gọi model nào.
python3 -m src.harness.selftest

# 1. Voter chạy (subagent) -> dev/votes_v2/parts/<voter>_<lo>-<hi>.json, rồi gộp:
python3 -m src.harness.merge_parts

# 2. Xem voter định vị được bao nhiêu, mất ở đâu:
python3 -m src.harness.build --report

# 3. TRACK B — dựng bản clean-room ở nhiều ngưỡng đồng thuận:
python3 -m src.harness.build --k 2 --out out/candidates/v2_k2.zip

# 4. TRACK A — đãi bỏ concept không voter độc lập nào xác nhận:
python3 -m src.harness.prune --rule uncorroborated --min-votes 1 --dry
python3 -m src.harness.prune --rule uncorroborated --min-votes 1 --out out/candidates/18_prune.zip

# 5. Trước khi nộp: bản này khác bản nền chỗ nào?
python3 -m src.harness.diff out/submitted/14_repeat_36.4914.zip out/candidates/18_prune.zip
```

## Vì sao ngưỡng `k` là núm vặn chứ không phải giả định

Một lần chạy voter sinh được cả `k>=1` (phủ rộng, chính xác thấp), `k>=2`, `k>=3`
(phủ hẹp, chính xác cao) mà **không phải gọi model lại**. Ta không biết điểm cân bằng
chính xác/độ phủ nằm ở đâu — nhưng leaderboard biết. Nộp 2-3 mức, đọc điểm, chốt.

Đây là điểm khác biệt với 4 lượt nộp trước: chúng đều đoán trước một mức rồi nộp một lần.

## Bất biến harness bảo đảm

1. `raw[start:end] == text` — đúng từng ký tự, kiểm trên cả 20 file Unicode phân rã.
2. Không concept nào định vị sang **nhầm file** (bản 12 từng dính 45 ca; giờ không thể
   xảy ra vì locator không bao giờ dò ra ngoài file đang xét).
3. Assertion chỉ thuộc `{isNegated, isHistorical, isFamily}`.
4. `candidates` chỉ có ở `CHẨN_ĐOÁN` + `THUỐC`; ICD luôn **có dấu chấm**; mọi mã đều
   tồn tại trong `data/gaz.json`.
5. Bản nộp không qua `validate.validate()` thì **không có zip nào được ghi ra**.
