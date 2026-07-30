# Clean NER Pipeline Branch

Folder này chứa pipeline NER sạch được tách riêng để không đè lên pipeline hiện có của repo.

Các mốc đã biết:

- `artifacts/submissions/ner34_from_colab/output.zip`: bản NER đầu tiên, điểm public `34.3271`.
- `artifacts/ensembles/v6_ner34_drop_mask_drugs.zip`: bản lọc `THUỐC` mask/rác, điểm public `35.6110`.
- `artifacts/submissions/clean_retrain/output_clean_retrain.zip`: bản train lại với dữ liệu đã lọc, cần nộp thử để xác nhận điểm.

Để chạy lại trên Colab, upload:

```text
ner_clean_pipeline/artifacts/viettel_colab_data.zip
```

Notebook tham khảo:

```text
ner_clean_pipeline/colab/viettel_train_ner_colab.ipynb
```
