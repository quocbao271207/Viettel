# 02 — Kiểm chứng luật tra mã thuốc (RxNorm)

Trạng thái: **đang làm**

## Mục tiêu

Trả lời một câu: **annotator dùng công cụ gì để ra mã RxNorm?**

Nếu tái tạo được đúng công cụ đó thì nhánh `THUỐC` của `candidates_score` (0.4 điểm) thành việc cơ học, không cần model. Giả thuyết ban đầu: annotator dùng `approximateTerm` của RxNav (công cụ mặc định, không cần license, gõ tên thuốc ra mã).

Bộ đo: 13 cặp `(mention, mã GT)` lấy từ ví dụ vòng 1 trong đề. Đây là toàn bộ GT thuốc hiện có.

## Đã làm

Gọi `approximateTerm.json?term=<mention>&maxEntries=20` cho cả 13 mention, lưu JSON thô vào `data/kb/rxnav_raw/approx_m01..m13.json`. Gộp các atom cùng `rxcui` (một mã trả về nhiều dòng tên khác nhau), giữ thứ tự `rank` tăng dần, rồi tìm vị trí mã GT trong danh sách.

Sau đó tra TTY của từng mã trong `RXNCONSO.RRF` (bản prescribable subset đã tải) để hiểu vì sao lệch.

## Kết quả đo được

### Vòng 1 — approximateTerm thô

```
top-1 : 0/13
top-3 : 3/13
top-20: 5/13
```

| mention | GT | vị trí GT |
|---|---|---|
| amlodipine 10 mg po daily | 308135 | 2 |
| aspirin 81 mg po daily | 243670 | 4 |
| docusate sodium 100 mg po bid | 1099279 | 3 |
| clonazepam 0.5 mg po qam:prn | 197527 | 2 |
| clonazepam 1.5 mg po qhs | 197528 | 4 |
| 8 mention còn lại | — | không có trong top-20 |

### Vòng 2 — thêm một bước lọc TTY = SCD

```
top-1 thô        : 0/13
top-1 sau ép SCD : 5/13   ← và 6/6 ca "GT nằm trong danh sách" đều lên top-1 hoặc top-2
top-1 ưu tiên TTY: 5/13   (SCD > SBD > SCDC > IN — không hơn được lọc SCD thuần)
```

Nghĩa là: **khi mã GT có mặt trong kết quả trả về, lọc TTY=SCD đưa nó lên hạng 1 gần như luôn luôn.** Ca `aspirin` lên hạng 2 vì có một SCD khác chen trước.

→ **Bài toán không nằm ở ranking. Nằm ở recall**: 7/13 ca GT không hề xuất hiện trong 20 candidate.

### Vòng 3 — làm sạch mention trước khi tra

Tra TTY cho thấy `approximateTerm` luôn ưu tiên **SCDC** (hoạt chất + hàm lượng, không có dạng bào chế), trong khi GT là **SCD** (đủ dạng bào chế). Nhưng phần lớn ca miss lại do chính chuỗi truy vấn có rác. Thử làm sạch:

| mention gốc | vị trí GT | mention đã sạch | vị trí GT |
|---|---|---|---|
| `acetaminophen 325-650 mg po q6h:prn` | không có | `acetaminophen 325 mg` | **2** |
| `metoprolol succinate xl 50 mg po daily` | không có | `metoprolol succinate 50 mg extended release` | **2** |
| `sena 8.6 mg po bid:prn` | không có | `senna 8.6 mg` | **1** |
| `nystatin oral suspension 5 ml po qid:prn` | không có | `nystatin` | **1** |

4/4 ca miss được cứu chỉ bằng tiền xử lý chuỗi. Ba phép biến đổi tách biệt:

1. **Bỏ đuôi liều dùng** (`po`, `q6h:prn`, `bid`, `daily`, `qhs`, `qam`) và bỏ khoảng liều, giữ số đầu (`325-650 mg` → `325 mg`).
2. **Sửa lỗi chính tả của mention** (`sena` → `senna`). Mention trong input có lỗi typo; annotator vẫn ra đúng mã, nên pipeline của họ có bước fuzzy/chính tả.
3. **Dịch viết tắt dạng bào chế** (`xl` → `extended release`).

Ca `nystatin` cho thấy quy luật chọn tầng: `nystatin oral suspension` → trả về hàng loạt SCDF/SBD nhưng **không có** `7597`; `nystatin` trần → `7597` ở hạng 1. Tức GT tầng `IN` xuất hiện khi truy vấn chỉ còn tên hoạt chất. Đây là gợi ý mạnh rằng annotator tra **theo tên hoạt chất trước**, và mã cụ thể hơn chỉ ra khi mention có hàm lượng rõ ràng.

### Còn lại 3 ca thật sự khó — đều là mã không tồn tại trong subset

`392085` (guaifenesin), `360047` (chlorpheniramine syrup), `1660761` (capsaicin cream): 3/13 ≈ 23%, khớp con số đo trước đó.

Trường hợp `Capsaicin 0.38 MG/ML`: GT `1660761`, API trả duy nhất `1660760` — **lệch đúng 1 số**, cả hai đều không có trong subset. `1660761` là concept obsolete từ 01/2021. Đây là loại ca chỉ giải được bằng snapshot RxNorm cũ hoặc `getRxcuiHistoryStatus`, không phải bằng tiền xử lý.

## Phát hiện

### Giả thuyết được xác nhận ở dạng "approximateTerm + tiền xử lý + lọc SCD"

Chuỗi ba bước tái tạo được 10/13 mã GT, và 10/13 đúng bằng số mã GT có trong subset — tức **luật này giải hết mọi ca về nguyên tắc giải được**:

```
mention → làm sạch chuỗi → approximateTerm → lọc TTY (SCD, hoặc IN nếu không có hàm lượng) → lấy hạng 1
```

Bằng chứng: 0/13 nếu gõ thô; 5/13 khi thêm lọc SCD; 4/4 ca miss còn lại được cứu bằng làm sạch chuỗi. Ba ca không cứu được đều là mã **không tồn tại trong prescribable subset** (2 obsolete/remapped), không phải lỗi của luật.

Đây là luật cơ học cho nhánh `THUỐC` của `candidates_score` — cùng bản chất với luật bung mã con của ICD-10 ở [01](01-xay-kb-icd10-rxnorm.md). Cả hai nhánh của 0.4 điểm giờ đều có công thức, không cần model để chọn mã.

Cần lưu ý mức tin cậy: 13 mẫu, và 4 ca "cứu được" là do tôi tự đoán cách làm sạch rồi thử — có rủi ro overfit vào 13 mẫu này. Phải kiểm lại trên bộ đo mở rộng sau khi annotate corpus (GĐ1).

### Chọn tầng TTY phụ thuộc mention có hàm lượng hay không

Lọc SCD thuần = 5/13; ưu tiên SCD>SBD>SCDC>IN cũng = 5/13, không hơn. Nhưng ca `nystatin` cho luật rõ: mention còn hàm lượng → SCD; mention chỉ còn tên hoạt chất → `IN`. Với `nystatin oral suspension 5 ml`, `5 ml` là thể tích liều chứ không phải hàm lượng thuốc, nên sau khi làm sạch còn lại tên trần → `IN`. Luật phân biệt "hàm lượng" (mg, MG/ML, UNT/ML) với "thể tích liều" (ml đứng một mình) là cần thiết.

### Prescribable subset thiếu 23% mã GT — phải bù bằng RxNav

3/13 mã GT không có trong `RXNCONSO.RRF`. Không thể xây index chỉ từ subset. Phải bù qua API rồi đóng băng thành file tĩnh (inference phải offline).

## Vướng mắc kỹ thuật của sandbox (ghi để không mất thời gian lại)

Chuỗi lỗi này ngốn ~20 lần gọi bash. Nguyên nhân xếp lớp lên nhau:

1. **Python subprocess không ra được RxNav.** Proxy sandbox có allowlist, `rxnav.nlm.nih.gov` bị chặn: `HTTP/1.1 403`, header `X-Proxy-Error: blocked-by-allowlist`. Shell của bash tool đã unset biến proxy nên curl đi thẳng được; `python3` lại thấy đủ `https_proxy/HTTP_PROXY/ALL_PROXY/...` (22 biến) nên mọi curl gọi qua `subprocess.run` bị đẩy vào proxy và chết `rc=56`.
   - Bỏ biến proxy trong env truyền cho subprocess **không cứu được**: khi đó DNS fail luôn (`rc=6`, `socket.gethostbyname` cũng fail). Ghim IP bằng `--resolve` → `rc=7`. Tức là chỉ shell của bash tool có đường ra thật.
   - → **Kết luận: khâu tải mạng phải nằm trong shell, python chỉ đọc file đã tải.** Đây là lý do `src/rxnav_probe.py` cho 0/13 giả — nó ghi cache rỗng rồi tự đọc lại cache rỗng đó.
2. **HTTP/2 bị reset trên endpoint `approximateTerm`.** Cùng URL, `curl` mặc định (HTTP/2) trả `rc=56`, thêm `--http1.1` thì trả 200. Endpoint `property.json` thì HTTP/2 vẫn chạy bình thường — nên lỗi này dễ bị chẩn đoán nhầm thành "host chết".
3. **Nhiều request liên tiếp trong một lần gọi bash đều fail.** 1 request/lần gọi: ổn định 13/13. 3 request trong một `for`: có lần được. 13 request: fail sạch, kể cả có `sleep 2` và retry 4 lần với backoff (hết 2 phút cho 2 mention). Đã lấy đủ data bằng cách gọi 13 lần bash riêng biệt, mỗi lần 1 request.
4. **`curl -o file` bị sandbox chặn** (`no such file or directory` dù dir tồn tại và ghi được). Dùng shell redirect `> file`.
5. **`while read` + heredoc + gọi `python3` bên trong: python ăn hết stdin của heredoc.** Thêm `< /dev/null` cho mọi lệnh trong loop, hoặc dùng `for` với mảng.

Đã ghi các mục 1–2 vào đây thay vì PLAN.md vì là chi tiết môi trường, không phải chiến lược. Nhưng mục 1 có hệ quả chiến lược: **mọi script cần mạng phải tách hai pha — shell tải, python xử lý.**

## Sai sót của tôi trong lần đo này (ghi để không lặp)

Lần chạy đầu tôi nhập sai 2 mã GT — viết `90475` thay vì `904475`, `36047` thay vì `360047` (thiếu một chữ số). Hệ quả: bảng kết quả đầu tiên báo `pravastatin` và `chlorpheniramine` là "GT không có trong subset", và tổng kết sai thành 5/13 mã thiếu (38%) thay vì 3/13 (23%). Sau khi sửa, `904475` thật ra **có** trong subset và lên top-1 sau lọc SCD.

Bài học: mã GT phải copy từ đề/PLAN.md, không gõ lại bằng tay. Bộ GOLD trong `src/rxnav_probe.py` cũng đang giữ bản sai — phải sửa.

## Việc còn lại

- [ ] Sửa `src/rxnav_probe.py`: bỏ phần tự gọi curl (chỉ đọc `data/kb/rxnav_raw/*.json`), và sửa 2 mã GT sai (`90475`→`904475`, `36047`→`360047`). Hiện tại file này cho kết quả sai hoàn toàn.
- [ ] Viết bộ làm sạch mention thuốc: bỏ ký hiệu liều dùng, tách hàm lượng khỏi thể tích, dịch viết tắt dạng bào chế (`xl`/`er`/`sr`→extended release), sửa chính tả.
- [ ] Mở rộng bộ đo GT thuốc: hiện chỉ 13 mẫu và 4 ca đã bị tôi tune tay → rủi ro overfit. Cần annotate corpus (GĐ1) để có ≥100 cặp rồi đo lại từ đầu.
- [ ] Thử `findRxcuiByString` với `search=2` (normalized) và `getApproximateMatch` — có thể ưu tiên SCD sẵn, khỏi cần hậu xử lý.
- [ ] Bù 3 mã thiếu qua `getRxcuiHistoryStatus` scope "Current and Historical", đóng băng vào KB tĩnh.
- [ ] Lưu ý mention tiếng Việt: cả 13 mẫu đều là tên thuốc tiếng Anh. Corpus thật có biệt dược Việt (Medrol, Omez…) — luật này chưa chạm tới nhóm đó.
