#!/usr/bin/env bash
# Đóng gói bản nộp cho BTC (top 15 phải nộp code + data + weights + README để dựng lại).
#
#   bash pack_submission.sh            # gói đầy đủ, có weights
#   bash pack_submission.sh --no-w     # bỏ weights (để xem gói code nặng bao nhiêu)
#
# Ra 2 file:
#   submit_code.zip     code + data + README + Dockerfile  (nhẹ, đọc được)
#   submit_full.zip     thêm models/ner (weights ~2.2GB với xlm-roberta-large)
#
# Vì sao tách: nhiều nơi nộp giới hạn dung lượng, và người review đọc code thì không cần
# tải 2GB weights.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d models/ner ] && [ "${1:-}" != "--no-w" ]; then
  echo "THIẾU models/ner — chưa train, hoặc chưa giải nén weights từ Colab về." >&2
  echo "Chạy 'bash pack_submission.sh --no-w' nếu chỉ muốn gói code." >&2
  exit 1
fi

# Build lại dữ liệu dẫn xuất trước khi gói. gt_blocks.py là thứ sửa liên tục; quên bước này
# thì gói ra bản nhãn cũ mà không có gì báo.
python3 src/make_gt.py    >/dev/null
python3 src/split.py      >/dev/null
python3 src/gt_lexicon.py

# Sinh kết quả để nộp lên leaderboard, nếu đã có weights.
if [ -d models/ner ]; then
  python3 src/ner_infer.py --model models/ner --input input --out submission | tail -8
  rm -f submission.zip
  ( cd submission && zip -q -r ../submission.zip . )
  echo "submission.zip: $(ls -lh submission.zip | awk '{print $5}')  <- file nộp lên leaderboard"
fi

CODE=(
  README.md requirements.txt Dockerfile pack_submission.sh PLAN.md
  # data/blocks đã chứa blocks.json + file_to_blocks.json + split.json; không có
  # data/blocks.json ở gốc (đường dẫn đó từng ghi sai, zip bỏ qua im lặng nên không ai thấy).
  src data/kb data/gt_block data/ner data/blocks input worklog colab
)

rm -f submit_code.zip submit_full.zip
zip -q -r submit_code.zip "${CODE[@]}" \
  -x '*__pycache__*' '*.DS_Store' 'data/kb/rxnav_raw/*'
echo "submit_code.zip: $(ls -lh submit_code.zip | awk '{print $5}')"

if [ -d models/ner ]; then
  cp submit_code.zip submit_full.zip
  zip -q -r submit_full.zip models/ner -x '*__pycache__*'
  echo "submit_full.zip: $(ls -lh submit_full.zip | awk '{print $5}')"
fi

# Kiểm gói: file nào BTC bắt buộc phải có mới chạy được inference.
echo
echo "kiểm gói code có đủ thứ để chạy inference:"
for f in README.md requirements.txt Dockerfile src/ner_infer.py src/lexicon.py \
         src/gt_lexicon.py src/predict.py src/sections.py src/textnorm.py \
         data/kb/icd10.json data/kb/rxnorm_drugs.json data/kb/gt_lexicon.json; do
  if unzip -l submit_code.zip "$f" >/dev/null 2>&1; then echo "  ok   $f"; else echo "  THIẾU $f"; fi
done
