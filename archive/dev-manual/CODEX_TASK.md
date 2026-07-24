# Task cho Codex (hoặc bất kỳ LLM-agent nào) — làm 1 "voter" NER

Mở Codex trong repo này rồi giao đúng nhiệm vụ dưới đây. KHÔNG cần API trả tiền —
Codex chạy bằng gói ChatGPT Plus/Pro của bạn. Nó đọc file + ghi file y như Claude đã làm.

## Nhiệm vụ giao cho Codex (copy nguyên khối này)

> Bạn là chuyên gia gán nhãn NER y khoa tiếng Việt. Xử lý toàn bộ 100 file
> `input/1.txt` … `input/100.txt`. Với MỖI file, đọc nội dung rồi trích MỌI lần nhắc
> tới khái niệm y tế, gồm 3 loại: THUỐC, CHẨN_ĐOÁN, TRIỆU_CHỨNG.
>
> Quy tắc:
> 1. `text` = chuỗi NGUYÊN VĂN đúng như trong file (copy chính xác hoa/thường/dấu/space),
>    phải tìm lại được bằng string-search.
> 2. Trích MỖI LẦN NHẮC riêng — cùng một bệnh nhắc 5 lần = 5 mục.
> 3. `before` = tối đa 15 ký tự NGAY TRƯỚC cụm (nguyên văn) để định vị; đầu file thì "".
> 4. `assertion` chọn 1: "" (đang có — mặc định), "isNegated" (không/chưa), "isHistorical"
>    (tiền sử/thuốc trước nhập viện), "isFamily" (của người nhà), "isUncertain" (nghi ngờ),
>    "isHypothetical" (nếu/giả định). Suy từ ngữ cảnh.
> 5. Dùng ngữ cảnh: câu giáo dục "sốt là triệu chứng của X" vẫn trích "sốt". Gold chứa TOÀN BỘ.
> 6. BỎ tên người/bác sĩ/tổ chức dù trùng tên bệnh. BỎ tên thuốc bị che bằng `*****`.
>    BỎ chỉ số xét nghiệm/sinh hiệu thuần số (WBC, SpO2, mmHg…).
> 7. KHÔNG xuất mã ICD/RxNorm. KHÔNG tính offset ký tự.
>
> Ghi kết quả ra `dev/votes/gpt.json` (JSON hợp lệ UTF-8), cấu trúc:
> `{"1": [{"text":"...","type":"THUỐC|CHẨN_ĐOÁN|TRIỆU_CHỨNG","assertion":"...","before":"..."}], "2":[...], …, "100":[...]}`
> Đủ 100 key. Tự kiểm: mỗi `before`+`text` phải là chuỗi con của file tương ứng.
>
> Ví dụ đoạn "Thuốc trước nhập viện: metoprolol 25mg po bid. Bệnh nhân không sốt, tiền sử viêm dạ dày. Mẹ bị đái tháo đường.":
> `[{"text":"metoprolol 25mg po bid","type":"THUỐC","assertion":"isHistorical","before":"nhập viện: "},
>   {"text":"sốt","type":"TRIỆU_CHỨNG","assertion":"isNegated","before":"nhân không "},
>   {"text":"viêm dạ dày","type":"CHẨN_ĐOÁN","assertion":"isHistorical","before":"tiền sử "},
>   {"text":"đái tháo đường","type":"CHẨN_ĐOÁN","assertion":"isFamily","before":"Mẹ bị "}]`

## Sau khi Codex ghi xong `dev/votes/gpt.json`
```bash
# (tuỳ chọn) thêm DeepSeek tương tự -> dev/votes/deepseek.json
python3 src/gold_triangulate.py --k 2 --sapbert   # gộp claude + gpt (+ deepseek) -> dev/gold_resolved.json
```
`gold_triangulate` tự đọc MỌI file trong `dev/votes/` bất kể tên. Đã có `claude.json` sẵn.
