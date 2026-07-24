# Dựng gold bằng 3-4 LLM triangulate — CẮM KEY LÀ CHẠY

## Chạy (1 lệnh)
```bash
export OPENAI_API_KEY=sk-...        # cho gpt
export DEEPSEEK_API_KEY=sk-...      # cho deepseek
export ANTHROPIC_API_KEY=sk-...     # cho opus (hoặc bỏ, dùng file phiếu Opus có sẵn — xem dưới)

python3 src/build_gold.py --k 2 --sapbert --rule
#   --k 2      : giữ concept ≥2 model đồng thuận (tăng lên 3 nếu muốn precision cao hơn)
#   --sapbert  : gán ICD cho bệnh/triệu chứng NGOÀI từ điển curated (dùng index local)
#   --rule     : thêm 1 "voter" rule-based miễn phí (từ out/baseline_all.json)
```
Ra: **`dev/gold_resolved.json`**. Đo pipeline ngay:
```bash
python3 src/evaluate.py out/baseline_all.json dev/gold_resolved.json
```

## Cơ chế (đã test bằng phiếu giả: 119 phiếu → 45 concept, offset khớp 100%)
1. `src/gold_vote.py`  — mỗi model đọc 100 file → phiếu `dev/votes/<name>.json`. **Có cache**: chạy dở
   hết tiền/rớt mạng, chạy lại là **tiếp tục chỗ dở**, không gọi lại file đã xong.
2. `src/gold_triangulate.py` — gộp mọi phiếu: định vị span bằng ngữ cảnh trái (xử lý lần nhắc lặp) →
   gom cụm (cùng type + span chồng lấn) → **giữ nếu ≥k voter** → span/assertion lấy đa số.
3. Map mã **deterministic** (KHÔNG để LLM bịa): THUỐC→RxNorm (gazetteer) · CHẨN_ĐOÁN→curated 44 bệnh
   rồi SapBERT · TRIỆU_CHỨNG→curated 24 mã chương R rồi SapBERT.

## Cấu hình model: `dev/voters.json`
Sửa `model` / thêm bớt voter tuỳ ý. Đổi `gpt-4o`, `deepseek-chat`, `claude-opus-4-8` sang bản bạn có quyền.

## Nếu ĐÃ có gold Opus 4.8 sẵn
Chuyển nó về đúng format phiếu rồi đặt tại **`dev/votes/opus.json`** — `build_gold.py` sẽ tự dùng, KHỎI cần key Opus.
Format mỗi file (key = số file "1".."100"):
```json
{ "1": [ {"text": "viêm phổi", "type": "CHẨN_ĐOÁN", "assertion": "", "before": "bị chẩn đoán "}, ... ] }
```
- `text`: cụm NGUYÊN VĂN trong file. `type`: THUỐC/CHẨN_ĐOÁN/TRIỆU_CHỨNG.
- `assertion`: "" hoặc isNegated/isHistorical/isFamily/isUncertain/isHypothetical.
- `before`: ≤15 ký tự ngay trước cụm (để định vị đúng lần nhắc). Thiếu cũng được (sẽ tìm lần đầu).

## Lưu ý
- LLM build gold **KHÔNG bị trần 9B** (trần chỉ áp model self-host lúc NỘP). Dùng model mạnh nhất.
- Gold-LLM là **pseudo-gold** (xấp xỉ) — để lặp nhanh cục bộ; cải tiến lớn vẫn phải xác nhận trên leaderboard.
- `dev/votes/` đã .gitignore ngầm qua thư mục? Nếu không muốn push phiếu, thêm `dev/votes/` vào .gitignore.
