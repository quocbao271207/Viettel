# Chạy trên Colab

## File cần dùng

- Notebook: `colab/viettel_train_ner_colab.ipynb`
- Gói upload lên Colab: `artifacts/viettel_colab_data.zip`

Gói upload đã chứa đủ:

- `input/`: 100 file đề bài
- `data/gt_block/`: 100 file nhãn tay, 3.473 entity
- `data/ner/`: train/val jsonl đã dựng sẵn
- `data/kb/`: ICD/RxNorm/lexicon rút gọn
- `src/`: code train, infer, score

Không cần upload `_archive/`, `.venv`, `.wheels`, `models` cache cũ.

## Tạo lại gói upload

```bash
bash colab/pack.sh
```

Output sẽ nằm ở:

```text
artifacts/viettel_colab_data.zip
```

## Quy trình trong Colab

1. Mở `colab/viettel_train_ner_colab.ipynb`.
2. Chọn runtime GPU, ưu tiên L4 hoặc A100.
3. Chạy các cell theo thứ tự.
4. Ở cell upload, chọn `artifacts/viettel_colab_data.zip`.
5. Train thử train/val để chọn epoch.
6. Train final với `--all`.
7. Tải `output.zip` để nộp và `ner_weights.zip` để giữ weights.

Nếu `xlm-roberta-large` bị thiếu VRAM, đổi `MODEL_NAME` trong notebook sang `xlm-roberta-base`.
