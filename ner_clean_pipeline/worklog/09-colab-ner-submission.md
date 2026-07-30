# 09 — Bản nộp NER train Colab từ GT tay

- **Trạng thái**: đang làm
- **Bắt đầu / Cập nhật**: 2026-07-30
- **Liên quan**: `worklog/07`, `worklog/08`, `colab/viettel_train_ner_colab.ipynb`

## Mục tiêu

Dùng 3.473 nhãn tay trong `data/gt_block` để train XLM-R token classification, thay cho bản luật thuần 16.2858.

## Đã làm

- Đóng gói `artifacts/viettel_colab_data.zip`.
- Train `xlm-roberta-large` trên Colab.
- Dev split tốt nhất ở epoch ~20: precision 0.7477, recall 0.7741, F1 0.7607.
- Chấm offline val bằng `src/score.py`: final 65.4142 trên GT tay.
- Train final `--all` 20 epoch, infer ra 100 file và nộp `output.zip`.

## Kết quả nộp — 2026-07-30 09:02

| Chỉ số BTC trả về | Giá trị |
|---|---:|
| `WER` | 62.4139 |
| `J_assertion` | 41.0813 |
| `J_candidates` | 26.8173 |
| `num_scored` / `num_records` | 100 / 100 |
| **Điểm** | **34.3271** |

Phân rã điểm:

```text
text_score = 100 - 62.4139 = 37.5861  -> 11.2758 điểm
assertions = 41.0813                  -> 12.3244 điểm
candidates = 26.8173                  -> 10.7269 điểm
tổng                                     34.3271
```

## So với bản 36.4914 của repo đồng đội

| Trục | NER Colab | Bản 36.4914 | Chênh đóng góp |
|---|---:|---:|---:|
| text | 37.5861 | 41.7793 | -1.2580 |
| assertion | 41.0813 | 48.3759 | -2.1884 |
| candidate | 26.8173 | 23.6121 | +1.2821 |
| **final** | **34.3271** | **36.4914** | **-2.1643** |

## Phát hiện

- Candidate của pipeline NER tốt hơn bản 36 (+1.28 điểm đóng góp), nghĩa là từ điển GT/RxNorm/ICD trong repo này có ích thật.
- Khoảng cách chính nằm ở `J_assertion` và `text/WER`, không phải candidates.
- Output NER có thể đang thêm span sai hoặc sai ranh giới/type so với GT BTC; cần so/chưng cất từ bản 36 để tăng precision text và assertion.

## Việc tiếp theo

- [ ] Lấy output NER mới từ Colab về local để phân tích entity/type/count.
- [ ] So với bản 36.4914: tìm các span bản 36 có mà NER thiếu, và các span NER có nhưng bản 36 không có.
- [ ] Thử ensemble an toàn: giữ span giao/union có lọc theo type, dùng candidates của NER khi cùng `(text,type)`.
- [ ] Ưu tiên vá assertion bằng luật/spec 3 loại `isNegated`, `isFamily`, `isHistorical`.

## 2026-07-30 — Ensemble/probe đã tạo

Output Colab đã tải về local: `artifacts/submissions/ner34_from_colab/output.zip`.

So với bản 36.4914:

- Bản NER có candidates tốt hơn trên leaderboard, nhưng span/assertion kém hơn.
- Delta NER vs teammate36: `artifacts/diagnostics/teammate36_vs_ner34_delta.csv`.
- NER có 103 `THUỐC` dạng mask/rác rõ (`*****`, span 1 ký tự). Handoff đồng đội nói masked drugs là mồi nhử, không nên trích.

Các bản nộp probe:

| Ưu tiên | File | Ý nghĩa |
|---:|---|---|
| 1 | `artifacts/ensembles/v1_teammate14_ner_candidates.zip` | Giữ span/assertion của bản 36.4914, thay candidates bằng NER khi có. Ít rủi ro nhất. |
| 2 | `artifacts/ensembles/v2_teammate14_plus_ner_lab.zip` | Như v1, thêm lab từ NER. Đo liệu lab NER có đúng gold BTC không. |
| 3 | `artifacts/ensembles/v5_intersection_teammate_spans.zip` | Probe precision: chỉ giữ span teammate được NER xác nhận. |
| 4 | `artifacts/ensembles/v6_ner34_drop_mask_drugs.zip` | Bản NER 34 bỏ thuốc mask/rác. |
| 5 | `artifacts/ensembles/v7_ner34_drop_mask_drugs_vital_labs.zip` | Bản NER 34 bỏ thêm vitals/generic labs. Rủi ro hơn v6. |

Script tái tạo:

```bash
python3 src/build_ensemble.py
python3 src/filter_submission.py --pred artifacts/submissions/ner34_from_colab/output.zip \
  --out artifacts/ensembles/v6_ner34_drop_mask_drugs.zip --drop-mask-drugs
```

## 2026-07-30 12:08 — Probe sạch v6 thành công

Nộp `artifacts/ensembles/v6_ner34_drop_mask_drugs.zip`: bản NER 34.3271 nhưng bỏ 103 `THUỐC` mask/rác (`*****`, span 1 ký tự).

| Chỉ số BTC trả về | NER 34 | v6 | Chênh |
|---|---:|---:|---:|
| `WER` | 62.4139 | **61.3309** | +1.0830 text |
| `J_assertion` | 41.0813 | **42.5358** | +1.4545 |
| `J_candidates` | 26.8173 | **28.1237** | +1.3064 |
| **Điểm** | **34.3271** | **35.6110** | **+1.2839** |

Phân rã phần tăng:

```text
text      +0.3249
assertion +0.4364
candidate +0.5226
tổng      +1.2839
```

Kết luận: filter thuốc mask/rác là rule sạch, tổng quát và phải giữ trong inference cuối. Rule đã được đưa vào `src/ner_infer.py`; `src/ner_data.py` cũng đã lọc mask khỏi data train để train lại model sạch hơn.

## 2026-07-30 — Đọc repo đồng đội, thêm postprocess rule

Remote GitHub `quocbao271207/Viettel` hiện chỉ có `main` và branch sạch mình đẩy; `main` vẫn dừng ở chuỗi
submission public tốt nhất `out/submitted/14_repeat_36.4914.zip`. Chưa thấy artifact/code bản 38 trên remote.

Bài học chuyển được từ repo đồng đội:

- `exact repeat` chỉ thắng khi nhân bản text đã được xác nhận, đủ cụ thể, không phải cụm ngắn/generic.
- Các nhóm `xét nghiệm`, `chẩn đoán hình ảnh`, sinh hiệu (`HA`, `Mạch`, `Nhiệt độ`, `SpO2`) từng làm giảm điểm.
- Assertion rỗng là baseline an toàn, nhưng strict assertion theo header rõ đáng thử vì bản 14 có ~650 assertion,
  còn NER của mình đang để rỗng toàn bộ.

Đã thêm `src/enhance_submission.py` để tạo probe tách biệt:

- `v8_clean_retrain_strict_assert.zip`: clean retrain + strict assertions.
- `v9_clean_retrain_repeats.zip`: clean retrain + repeat đã siết.
- `v10_clean_retrain_assert_repeats.zip`: clean retrain + strict assertions + repeat.
- `v12_v6_strict_assert.zip`: bản public-best v6 + strict assertions; nên nộp probe trước nếu còn lượt.
- `v13_v6_strict_assert_repeats.zip`: v6 + strict assertions + repeat coded/generic-guard; rủi ro hơn v12.
