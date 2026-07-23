# Cuộc thi Viettel AI Race - Vòng 1: Sơ loại

**Thời gian:** 02/07/2026 - 30/07/2026  
**Trạng thái:** Đang mở

---

## 1. Thể thức và Quy định Nộp bài

*   **Định dạng nộp bài:** Các thí sinh nộp kết quả dự đoán dưới dạng file JSON theo format do Ban Tổ chức (BTC) quy định.
*   **Cấu trúc file nộp:** File nộp bao gồm một file `output.zip`, sau khi giải nén có cấu trúc như sau:
    ```text
    output/
        ├── 1.json     # Nhãn của bản ghi 1
        ├── 2.json     # Nhãn của bản ghi 2
        ├── …
        └── 100.json
    ```

**Quy định chống gian lận (Dành cho Top ~15 đội):**
Trước khi vòng 1 kết thúc, BTC yêu cầu top ~15 đội gửi trước source code riêng để thực hiện dựng lại và đánh giá trên dữ liệu private test (nhằm tránh tình trạng gian lận nộp file hard code output).

**Source code bắt buộc bao gồm:**
*   Tất cả các file code của nhóm (data processing, training, inference, …)
*   Data nhóm sử dụng
*   Model weights
*   1 file `readme` hướng dẫn cài đặt chi tiết

*Lưu ý: Nếu BTC không thể cài đặt được code của nhóm thi, nhóm sẽ được liên lạc riêng để hỗ trợ trong 1 khoảng thời gian nhất định. Nếu nhóm không thể cung cấp hỗ trợ kịp thời sẽ bị loại khỏi cuộc thi.*

---

## 2. Thông tin Hạ tầng & Giới hạn Tài nguyên

*   **Tài nguyên:** Thí sinh tự chuẩn bị tài nguyên tính toán.
*   **Giới hạn Model / API:** Với những giải pháp LLM/agent, chỉ cho phép thí sinh self-host model mà **không được sử dụng API ngoài**. Model self-host có độ lớn **tối đa là 9B params**.
*   **Hạ tầng chấm của BTC:** Chấm bằng GPU.
*   **Giới hạn nộp bài:** Tối đa 5 lần/ngày.
*   **Thời gian chờ (Timeout):** 600 giây.

---

## 3. Định dạng Dữ liệu (Input / Output)

### Ví dụ Input
```text
'Danh sách thuốc trước nhập viện chính xác và đầy đủ. 1. amlodipine 10 mg po daily 2. aspirin 81 mg po daily 3. metoprolol succinate xl 50 mg po daily 4. guaifenesin ml po q6h:prn điều trị ho 5. nystatin oral suspension 5 ml po qid:prn điều trị đau nhức 6. acetaminophen 325-650 mg po q6h:prn điều trị sốt đau 7. pravastatin 40 mg po daily 8. docusate sodium 100 mg po bid điều trị táo bón 9. senna 8.6 mg po bid:prn điều trị táo bón 10. clonazepam 0.5 mg po qam:prn điều trị lo âu 11. clonazepam 1.5 mg po qhs điều trị lo âu mất ngủ'
```

### Ví dụ Output
*Output trả về là một mảng các đối tượng JSON, trích xuất các thực thể kèm các thông tin liên quan.*

```json
[
  {
    "text": "amlodipine 10 mg po daily",
    "type": "THUỐC",
    "candidates": ["308135"],
    "assertions": ["isHistorical"],
    "position": [58, 83]
  },
  {
    "text": "aspirin 81 mg po daily",
    "type": "THUỐC",
    "candidates": ["243670"],
    "assertions": ["isHistorical"],
    "position": [89, 111]
  },
  {
    "text": "metoprolol succinate xl 50 mg po daily",
    "type": "THUỐC",
    "candidates": ["866436"],
    "assertions": ["isHistorical"],
    "position": [117, 155]
  },
  {
    "text": "guaifenesin ml po q6h:prn",
    "type": "THUỐC",
    "candidates": ["392085"],
    "assertions": ["isHistorical"],
    "position": [161, 186]
  },
  {
    "text": "ho",
    "type": "TRIỆU_CHỨNG",
    "assertions": [],
    "position": [196, 198]
  },
  {
    "text": "nystatin oral suspension 5 ml po qid:prn",
    "type": "THUỐC",
    "candidates": ["7597"],
    "assertions": ["isHistorical"],
    "position": [204, 244]
  },
  {
    "text": "đau nhức",
    "type": "TRIỆU_CHỨNG",
    "assertions": [],
    "position": [254, 262]
  },
  {
    "text": "acetaminophen 325-650 mg po q6h:prn",
    "type": "THUỐC",
    "candidates": ["313782"],
    "assertions": ["isHistorical"],
    "position": [268, 303]
  },
  {
    "text": "sốt đau",
    "type": "TRIỆU_CHỨNG",
    "assertions": [],
    "position": [313, 320]
  },
  {
    "text": "pravastatin 40 mg po daily",
    "type": "THUỐC",
    "candidates": ["904475"],
    "assertions": ["isHistorical"],
    "position": [326, 352]
  },
  {
    "text": "docusate sodium 100 mg po bid",
    "type": "THUỐC",
    "candidates": ["1099279"],
    "assertions": ["isHistorical"],
    "position": [358, 387]
  },
  {
    "text": "táo bón",
    "type": "TRIỆU_CHỨNG",
    "assertions": [],
    "position": [397, 404]
  },
  {
    "text": "senna 8.6 mg po bid:prn",
    "type": "THUỐC",
    "candidates": ["312935"],
    "assertions": ["isHistorical"],
    "position": [410, 433]
  },
  {
    "text": "táo bón",
    "type": "TRIỆU_CHỨNG",
    "assertions": [],
    "position": [443, 450]
  },
  {
    "text": "clonazepam 0.5 mg po qam:prn",
    "type": "THUỐC",
    "candidates": ["197527"],
    "assertions": ["isHistorical"],
    "position": [457, 485]
  },
  {
    "text": "lo âu",
    "type": "TRIỆU_CHỨNG",
    "assertions": [],
    "position": [495, 500]
  },
  {
    "text": "clonazepam 1.5 mg po qhs",
    "type": "THUỐC",
    "candidates": ["197528"],
    "assertions": ["isHistorical"],
    "position": [507, 531]
  },
  {
    "text": "lo âu",
    "type": "TRIỆU_CHỨNG",
    "assertions": [],
    "position": [541, 546]
  },
  {
    "text": "mất ngủ",
    "type": "TRIỆU_CHỨNG",
    "assertions": [],
    "position": [547, 554]
  }
]
```

---

## 4. Metric Đánh giá

Kết quả của thí sinh sẽ được tính trên tập test theo các metric sau:

1.  **Xác định tên khái niệm:** Sử dụng metric **Word Error Rate (WER)** trên trường `text`.
2.  **Xác định các assertions giữa khái niệm:** Sử dụng metric **Độ tương đồng Jaccard (Jaccard similarity)** với các bệnh, thuốc và triệu chứng tương ứng, lấy trung bình tất cả các giá trị này thành 1 điểm $J(assertion)$.
3.  **Xác định candidates trong khái niệm:** Sử dụng metric giống với xác định assertion.

### Công thức tính điểm tổng hợp (`final_score`)

$$ final\_score = 0.3 \cdot text\_score + 0.3 \cdot assertions\_score + 0.4 \cdot candidates\_score $$

**Chi tiết cách tính các thành phần:**
Với mỗi $i$ là 1 sample trong tập test, mỗi $k$ là 1 candidate trong sample $i$:
*   $WER(i)$ là WER của trường text trong sample $i$.
*   $ground\_truth(k)$, $prediction(k)$ lần lượt là tập ground truth, prediction của candidate $k$ trong sample $i$.
*   $J_X(i)$ là độ tương đồng Jaccard của sample $i$ xét trên trường $X$ tương ứng của output.

**Tính từng Score:**

*   **`text_score`**: 
    $$ text\_score = \frac{\sum_{i \in test} (1 - WER(i))}{len(test)} $$

*   **`assertions_score`**: 
    $$ assertions\_score = \frac{\sum_{i \in test} J_{assertions}(i)}{len(test)} $$

*   **`candidates_score`**: 
    $$ candidates\_score = \frac{\sum_{i \in test} J_{candidates}(i) \cdot \left( \sum_{k \in i} (len(ground\_truth(k)) + 1) \right)}{\sum_{i \in test} \sum_{k \in i} (len(ground\_truth(k)) + 1)} $$

**Chi tiết công thức Jaccard Similarity $J_X(i)$:**

*   Nếu $len(ground\_truth_X(i)) = 0$ và $len(prediction_X(i)) = 0$ thì $J_X(i) = 1$
*   Nếu $len(ground\_truth_X(i)) = 0$ và $len(prediction_X(i)) \neq 0$ thì $J_X(i) = 0$
*   Trong các trường hợp còn lại: 
    $$ J_X(i) = \frac{|ground\_truth_X(i) \cap prediction_X(i)|}{|ground\_truth_X(i) \cup prediction_X(i)|} $$

**Lưu ý cực kỳ quan trọng về việc xác định sai loại khái niệm:**
Trong trường hợp đoán đúng phần text của khái niệm nhưng sai loại (VD: đoán `CHẨN_ĐOÁN` nhưng ground truth là `TRIỆU_CHỨNG`), khái niệm đó sẽ bị tính **2 lần** (do tạo ra 1 khái niệm mới so với ground truth) và **mỗi lần đều được tính 0 điểm** với cả 3 loại metric.

---

## 5. Bảng xếp hạng (Top 10) - Tham khảo lúc mở cuộc thi

| Hạng | Đội | Điểm |
| :---: | :--- | :--- |
| 1 | 7 Cỏ X 10 Gió | 54.66380 |
| 2 | Balerion | 53.10330 |
| 3 | VTP-Sudo | 53.03970 |
| 4 | Tester - AI | 53.03970 |
| 5 | BoyPho_28 | 53.03470 |
| 6 | VSF-1 | 52.93400 |
| 7 | Milo | 52.90820 |
| 8 | M_10_top1 | 52.45590 |
| 9 | VCX_AI | 51.59160 |
| 10 | Bún bò Ngô Thúy | 51.24320 |
