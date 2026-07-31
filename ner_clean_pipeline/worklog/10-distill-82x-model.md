# 10. Distill model từ bản public 82x

Mục tiêu: dùng bản `82x_cleanroom4_k2.zip` (public 38.6460) như pseudo-label để train
NER, thay vì nộp nguyên output đó. Đây là hướng “model học lại quyết định span/type tốt”
rồi hậu xử lý candidates bằng lexicon bề mặt.

## Dữ liệu

- Teacher zip: `artifacts/teammate_latest_candidates/82x_cleanroom4_k2.zip`
- Extract ra: `data/teacher_82x/*.json`
- Dataset train: `data/ner_teacher_82x/{train,val}.jsonl`
- Lexicon teacher: `data/kb/gt_lexicon_teacher_82x.json`

Thống kê teacher:

```text
2932 entity trên 100 file
1063 TRIỆU_CHỨNG
 907 CHẨN_ĐOÁN
 439 TÊN_XÉT_NGHIỆM
 314 THUỐC
 209 KẾT_QUẢ_XÉT_NGHIỆM
 947 có candidates
 461 có assertions
```

`src/teacher_from_zip.py` kiểm tra offset với `input/*.txt` trước khi ghi nhãn.

## Cách chạy Colab

Local:

```bash
bash colab/pack.sh
```

Upload `artifacts/viettel_colab_data.zip`, mở/chạy:

```text
colab/viettel_distill_82x_colab.ipynb
```

Cell cuối tải về:

```text
/content/output_teacher_model_82x.zip
```

Đây là output do model `models/ner_teacher_82x` sinh ra, không phải copy nguyên teacher.
