# Clean NER Pipeline Branch

Folder này chứa pipeline NER sạch được tách riêng để không đè lên pipeline hiện có của repo.

Các mốc đã biết:

- `artifacts/submissions/ner34_from_colab/output.zip`: bản NER đầu tiên, điểm public `34.3271`.
- `artifacts/ensembles/v6_ner34_drop_mask_drugs.zip`: bản lọc `THUỐC` mask/rác, điểm public `35.6110`.
- `artifacts/submissions/clean_retrain/output_clean_retrain.zip`: bản train lại với dữ liệu đã lọc, cần nộp thử để xác nhận điểm.
- `artifacts/ensembles/v12_v6_strict_assert.zip`: probe khuyên nộp tiếp theo, lấy bản public-best `35.6110` và chỉ thêm strict assertions.
- `artifacts/ensembles/v13_v6_strict_assert_repeats.zip`: probe rủi ro hơn, thêm strict assertions và exact-repeat đã siết.

Để chạy lại trên Colab, upload:

```text
ner_clean_pipeline/artifacts/viettel_colab_data.zip
```

Notebook tham khảo:

```text
ner_clean_pipeline/colab/viettel_train_ner_colab.ipynb
```

Postprocess probe:

```bash
python3 src/enhance_submission.py --pred artifacts/ensembles/v6_ner34_drop_mask_drugs.zip \
  --out artifacts/ensembles/v12_v6_strict_assert.zip --strict-assertions
```
