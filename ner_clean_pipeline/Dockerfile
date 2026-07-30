# Sinh kết quả cho Đề 2, chạy được KHI NGẮT MẠNG HOÀN TOÀN.
#
# Build (cần mạng, chỉ để cài thư viện):
#   docker build -t vietel-de2 .
#
# Chạy (KHÔNG cần mạng):
#   docker run --rm --network none \
#     -v "$PWD/input:/app/input:ro" -v "$PWD/submission:/app/submission" vietel-de2
#
# Có GPU thì thêm `--gpus all`; không có thì tự chạy CPU.
#
# Vì sao `--network none` chạy được: weights nằm trong image ở /app/models/ner và load bằng
# `local_files_only=True`; từ điển ICD-10/RxNorm là 3 file JSON trong /app/data/kb. Không có
# lệnh gọi API nào trong đường inference.

# 3.11 chứ không 3.13: torch được ghim ở 2.2.2 (xem requirements.txt) và bản đó KHÔNG có
# wheel cp313 — torch chỉ có cp313 từ 2.5.0. Dùng 3.13-slim thì `pip install` chết ở bước
# resolve, hoặc tệ hơn là kéo một bản torch khác bản đã đo.
FROM python:3.11-slim

# Không cần compiler: các wheel torch/transformers đều là bản dựng sẵn.
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false \
    # Chặn cả ở tầng thư viện, không chỉ dựa vào --network none. Nếu có chỗ nào vô tình
    # gọi hub thì nó báo lỗi ngay lúc chạy chứ không âm thầm tải về.
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Chỉ copy thứ inference cần. Không mang data/raw (29MB RxNorm gốc + 9.5MB CSV ICD) vì
# data/kb đã là bản rút gọn; không mang data/gt_block, data/ner, data/blocks vì đó là dữ
# liệu huấn luyện.
COPY src/ner_infer.py src/ner_train.py src/predict.py src/lexicon.py src/gt_lexicon.py \
     src/sections.py src/textnorm.py src/score.py ./src/
COPY data/kb/icd10.json data/kb/rxnorm_drugs.json data/kb/gt_lexicon.json ./data/kb/
COPY models/ner ./models/ner

# Kiểm ngay lúc build: thiếu file từ điển thì vỡ ở đây, không phải lúc chấm.
RUN python -c "import sys; sys.path.insert(0,'src'); \
import gt_lexicon; from lexicon import load_drugs, load_icd; \
n,_,e=load_icd(); \
print(f'{len(load_drugs())} thuoc, {len(n)} ten benh, {len(e)} ma, lexicon {sum(len(v) for v in gt_lexicon.load().values())} dong')"

ENTRYPOINT ["python", "src/ner_infer.py", "--model", "models/ner", \
            "--input", "input", "--out", "submission"]
