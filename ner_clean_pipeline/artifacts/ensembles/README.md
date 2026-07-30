# Ensemble submissions

Ưu tiên nộp theo thứ tự này:

1. `v1_teammate14_ner_candidates.zip`  
   Giữ span/assertion của bản 36.4914, thay candidates bằng NER/linker của mình khi có. Đây là bản ít rủi ro nhất.

2. `v2_teammate14_plus_ner_lab.zip`  
   Như v1, thêm các span xét nghiệm từ NER nếu không chồng lên bản 36. Có thể tăng WER/Assertion nếu lab đúng, nhưng rủi ro overpredict cao hơn v1.

3. `v5_intersection_teammate_spans.zip`  
   Chỉ giữ span teammate được NER xác nhận. Đây là probe precision, không kỳ vọng top nhưng giúp hiểu BTC phạt overpredict ra sao.

4. `v6_ner34_drop_mask_drugs.zip`  
   Bản NER 34.3271 nhưng bỏ 103 thuốc mask/rác (`*****`, span 1 ký tự). Theo handoff đồng đội, masked drugs là mồi nhử; local score giảm vì GT tay của mình có gán mask, nên đây là probe riêng nếu còn lượt.

5. `v7_ner34_drop_mask_drugs_vital_labs.zip`  
   Như v6, bỏ thêm 66 lab/vital/generic (`HA`, `Mạch`, `SPO2`, `xét nghiệm...`). Rủi ro cao hơn v6; chỉ nộp nếu cần đo giả thuyết vitals không thuộc gold.

Không nộp `v3_teammate14_plus_ner_all.zip` nếu chưa có lượt dư: union tất cả NER vào bản 36, local rất cao nhưng BTC có rủi ro phạt thừa span.
