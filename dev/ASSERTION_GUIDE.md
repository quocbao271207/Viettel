# Quy ước ASSERTION khi duyệt gold (đã chốt với user)

Chỉ gán assertion đặc biệt khi có tín hiệu RÕ về CHÍNH bệnh nhân, theo NGỮ CẢNH (không quy tắc cứng).

| Ngữ cảnh | Assertion | Ví dụ |
|---|---|---|
| Bệnh nhân đang có / triệu chứng đợt này / văn giáo dục-định nghĩa chung | `∅` | "Triệu chứng hiện tại: đau bụng"; "Bệnh Kawasaki là..." |
| Bệnh nền trong mục "Tiền sử / Các bệnh lý mạn tính" | `isHistorical` | ĐTĐ, THA, suy thận mạn, CML; amyloidosis "đã lâu" |
| Thuốc/tổn thương/lần khám trong QUÁ KHỨ ("trước đó", "1 tháng trước", "đã ngừng") | `isHistorical` | "CT trước đó ghi nhận..."; "NSAID (đã ngừng)" |
| Phủ nhận về bệnh nhân | `isNegated` | "phủ nhận buồn nôn"; "không sốt"; "âm tính DVT" |
| Nghi ngờ bệnh nhân CÓ / **nguy cơ X cao** | `isUncertain` | "nghi ngờ co giật"; "rất có thể PCOS"; **"nguy cơ tiền sản giật cao"** |
| Của người nhà (mẹ/bố/ông/bà/vợ/chồng) | `isFamily` | "mẹ em bị run tay" |
| Điều kiện/giả định/mục đích/tác dụng phụ giả định | `isHypothetical` | "nếu sốt cao..."; "để phòng ngừa tiền sản giật"; "thuốc có thể gây chảy máu" |

## Chốt cụ thể (user quyết)
- **"nguy cơ X cao"** → `isUncertain` (KHÔNG phải isHypothetical). isHypothetical chỉ cho "để phòng ngừa / có thể gây".
- **Văn khuyến cáo/giáo dục chung** (không gắn bệnh nhân cụ thể) → `∅`.
- **amyloidosis** khi bệnh nhân có "đã lâu": mọi cụm (kể cả câu định nghĩa) → `isHistorical` (file 73, 32).
- Đoạn Q&A CHÈN về người khác (bé/bạn/chồng) hoặc định nghĩa bệnh → `∅`, KHÔNG isFamily.

## Đã duyệt (file)
5 6 10 11 12 14 32 54 63 68 70 73 82 84 85 89 91 92 97 98 99 100
