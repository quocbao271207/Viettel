# Viettel AI Race 2026 — Đề 2: Chuẩn hóa khái niệm y tế + Ontological Reasoning

Kế hoạch giải đề. Cập nhật lần cuối: 2026-07-28.

## 1. Tóm tắt bài toán

Input: 100 file `.txt` văn bản y khoa tiếng Việt tự do (`input/1.txt` … `input/100.txt`).
Output: 100 file `.json`, mỗi file là list dict với các trường `text`, `position`, `type`, `assertions`, `candidates`.

Ba task lồng nhau:

1. **NER span-level** — 5 nhãn: `TRIỆU_CHỨNG`, `TÊN_XÉT_NGHIỆM`, `KẾT_QUẢ_XÉT_NGHIỆM`, `CHẨN_ĐOÁN`, `THUỐC`, kèm offset ký tự `[start, end]`.
2. **Assertion classification** — `isNegated` / `isFamily` / `isHistorical`, chỉ áp cho `CHẨN_ĐOÁN`, `THUỐC`, `TRIỆU_CHỨNG`.
3. **Entity linking** — `CHẨN_ĐOÁN` → ICD-10, `THUỐC` → RxNorm. Trả về **list** mã (multi-label).

Ràng buộc: self-host model, **tối đa 9B params**, không dùng API ngoài **trong lời giải**. Đề khuyến khích dùng giải pháp ngoài để **tạo thêm data**.

Deadline Round 1: **04/08/2026**. Nộp **5 lần/ngày**, lấy kết quả **lần cuối trong ngày**.

## 2. Metric — nơi quyết định điểm

```
final_score = 0.3·text_score + 0.3·assertions_score + 0.4·candidates_score
```

| Thành phần | Metric | Tính chất cần khai thác |
|---|---|---|
| `text_score` | `mean(1 − WER)` trên trường text | WER **không chặn trên** → có thể âm. Entity thừa = insertion, thiếu = deletion. Phải **thiên về precision**. Phụ thuộc thứ tự → luôn sort output theo `position`. |
| `assertions_score` | Jaccard, trung bình theo sample | Giả thuyết "`J=1` khi GT rỗng và pred rỗng → để `[]` là ăn điểm free" **đã bị bản nộp #1 phủ định**: để rỗng 100% chỉ được **18.58**. Phải làm assertion thật. 18.58 là **mốc sàn**. |
| `candidates_score` | Jaccard có trọng số `len(GT)+1` | Thêm mã đúng thì tăng, mã sai thì giảm → tối ưu khi `len(pred) ≈ len(GT)` (thường 1–3), **không** trả top-10. Sample nhiều mã đóng góp nhiều hơn. |

**Bẫy sai type**: đoán đúng text nhưng sai nhãn bị tính **2 lần**, mỗi lần 0 điểm cho cả 3 metric. Sai type tốn ~gấp đôi so với bỏ qua entity. Với span lưỡng lự `TRIỆU_CHỨNG` vs `CHẨN_ĐOÁN`, bỏ đi có khi lời hơn.

**Công thức chấm — đã xác nhận bằng số thật, không còn là giả định.** BTC trả về
`WER`, `J_assertion`, `J_candidates` trên thang 100. Bản nộp #1 (xem
[worklog/03](worklog/03-ban-nop-thu-luat-thuan.md)):

```
0.3·(100 − 82.9421) + 0.3·18.5774 + 0.4·13.9879 = 16.28575   →  BTC báo 16.2858
```

→ `text_score = 100 − WER`, không hệ số ẩn. **Tự tính được điểm offline** trước khi
nộp, chỉ cần có GT. Đây là lý do phải làm oracle offline ở GĐ1 (xem §7).

**Phân rã mức 49 điểm của leaderboard — bản cũ đã bị phủ định.** Giả định trước đó
là `text ~55 / assertions ~80 / candidates ~20`, trong đó `assertions ~80` dựa vào
niềm tin để rỗng là ăn điểm cao. Bản nộp #1 cho thấy để rỗng chỉ được 18.58, nên
đội 49 điểm **không** đạt 80 theo cách đó. Phân rã thật chưa biết; cần probe §6.

Điều vẫn đứng: `candidates` trọng số 0.4 là chỗ đòn bẩy lớn nhất. Bản nộp #1 đạt
13.99 với độ phủ chỉ 33% entity và tầng TTY còn sai → còn rất nhiều đất.

## 3. Phát hiện từ phân tích dữ liệu

### 3.1 Tập test được sinh bằng cắt-dán từ pool block nhỏ — PHÁT HIỆN QUAN TRỌNG NHẤT

**53/100 file thuộc 21 cụm trùng lặp** (đo bằng 6-gram shingle containment > 0.5):

```
5 file: 35, 56, 67, 86, 94
4 file: 14, 19, 28, 52
4 file: 30, 44, 76, 83
3 file: 13,16,20 | 21,32,79 | 23,45,50 | 41,59,60
2 file: 6,11 | 7,9 | 12,15 | 37,48 | 39,47 | 42,62 | 43,63 |
        49,65 | 51,70 | 55,93 | 72,98 | 73,74 | 75,84 | 80,95
```

Cơ chế: BTC có một pool **đoạn văn (block)** — mỗi block là một mục bệnh án hoặc một đoạn tư vấn — rồi ghép ngẫu nhiên 2–4 block thành mỗi file test. File cùng cụm dùng chung phần lớn block, chỉ khác block được thêm/bớt.

Bằng chứng: đoạn "Viêm hang vị sung huyết là tình trạng niêm mạc vùng hang vị dạ dày viêm…" xuất hiện nguyên văn trong cả 5 file của cụm lớn nhất. Đoạn "tổn thương vùng âm hộ và mông bên phải / Tổn thương cực kỳ đau đớn / …" xuất hiện trong 7, 9, 12, 15.

**Hệ quả: nhãn của một block là bất biến qua các file, trừ `position`.**

Đã đo thật bằng [`src/blocks.py`](src/blocks.py): **381 block instance → 332 block độc nhất**, 24 block bị lặp, tiết kiệm chỉ **7%** ký tự. Kiểm chứng bất biến offset: `text[start:end]` khớp nguyên văn ở **0/381 lỗi**.

Con số "60–70 block độc nhất" tôi ước lượng trước đó là **sai**. Nguyên nhân: containment với `min(|A|,|B|)` ở mẫu số bị thổi phồng bởi các dòng tiêu đề section lặp lại ("Câu trả lời của bác sĩ" ×33, "2. Tiền sử bệnh hiện tại" ×33, "Đặc điểm triệu chứng" ×22). Đúng là 34.7% ký tự trùng ở mức dòng, nhưng phần trùng nằm ở **tiêu đề cấu trúc, không phải nội dung y tế**. Đo lại ở nhiều mức: 2 dòng liền 24%, 5 dòng 16%, 8 dòng 12%, cả block 7%.

Con số 53/100 file thuộc 21 cụm ở trên vẫn đúng; chỉ phần suy ra "corpus co lại còn 60–70 block" là sai. Quy mô thật để annotate là **332 block**, vẫn khả thi nhưng gấp 5 lần dự tính.

Lưu ý tính hợp lệ: dùng bộ block đã annotate làm **training data**, KHÔNG nhét lookup table `block → label` vào code inference. BTC chấm lại trên private test từ source code; nếu private test dùng pool block khác thì lookup table sập và trông giống gian lận.

### 3.2 GT không phải RxNorm hiện hành

Tra từng mã trong ví dụ của đề qua RxNav:

| RxCUI | Tên | TTY | Trạng thái |
|---|---|---|---|
| 308135 | amlodipine 10 MG Oral Tablet | SCD | active |
| 392085 | guaifenesin 800 MG Oral Tablet | SCD | active |
| 313782 | acetaminophen 325 MG Oral Tablet | SCD | active |
| 197527 | clonazepam 0.5 MG Oral Tablet | SCD | active |
| 866436 | 24 HR metoprolol succinate 50 MG ER Oral Tablet | SCD | active |
| **7597** | **nystatin** | **IN** | active |
| **360047** | chlorpheniramine 0.4 MG/ML / dextromethorphan / guaifenesin / pseudoephedrine Oral Solution | SCD | **Remapped, hết active 09/2016** |
| **1660761** | capsaicin 0.38 MG/ML / menthol / methyl salicylate Topical Cream | SCD | **Obsolete từ 01/2021** |

Ba kết luận:

- **GT trộn mức TTY.** `nystatin oral suspension 5 ml po qid:prn` → `7597` (Ingredient), không phải SCD. Đã đo được lý do: truy vấn `nystatin oral suspension` **không** trả `7597`, nhưng `nystatin` trần trả nó ở hạng 1. Tức tầng TTY do **chuỗi truy vấn sau khi làm sạch** quyết định, không phải do fallback: còn hàm lượng → SCD, chỉ còn tên hoạt chất → IN.
- **GT dùng RxNorm bản cũ.** Nếu index bằng `RxNorm_full_07062026.zip` thì 360047 và 1660761 **không tồn tại** → không bao giờ đoán ra. Phải có concept historical.
- **GT chọn multi-ingredient khi mention là single-ingredient.** `Chlorpheniramine 0.4 MG/ML` → GT `360047` (syrup 4 thành phần), trong khi match đúng nghĩa là `996986` (SCDC).

→ **Bài này không đo map đúng y khoa, nó đo khớp với một pipeline annotate cụ thể.** Reverse-engineer công cụ đó có giá trị hơn xây linker chính xác.

**Đã reverse-engineer xong nhánh THUỐC** — công thức 3 bước tái tạo 10/13 mã GT, xem [worklog/02](worklog/02-kiem-chung-luat-tra-ma-thuoc.md) và §5. Công cụ nền của annotator gần như chắc chắn là RxNav approximate match trên snapshot cũ.

### 3.3 Đặc tính corpus

- **~2.650 ký tự/file** (min 1.689 — `100.txt`, max 5.862 — `1.txt`), dài gấp ~5 lần ví dụ trong đề. Không nhét thẳng vào prompt được → phải chunk và map offset về gốc.
- Thể loại: **35 file QA bác sĩ** (Vinmec-style), **51 file EHR/bệnh án** (dịch máy từ tiếng Anh, khả năng cao MIMIC-IV), phần còn lại là bài giải thích bệnh phổ thông ("THIẾU MEN G6PD là gì?").
- **12 file trộn 2 thể loại** — `5.txt` là bệnh án ung thư đường mật bị chèn nguyên đoạn tư vấn vô sinh vào giữa.
- Noise: dính chữ ("tế bào bất thườngtế bào bất thường", "ăng huyết áp" thiếu chữ T), đoạn trùng lặp nguyên khối trong cùng file.
- **99 chỗ tên thuốc bị mask `***`** ở 30 file, độ dài dấu sao khớp số ký tự tên gốc. Cần quyết định: bỏ hẳn hay coi là `THUỐC` không candidate. Có chỗ mask lệch nghĩa ("Vitamin K dùng trong điều trị nhiễm khuẩn tiết niệu" — thực ra nitrofurantoin bị mask sai).
- Deid placeholder: `[Ngày]` (9), `[Date]` (7), `[Số]` (3), `[Tên cuộc họp]` (2), `[Name]` (2), `[Tên bác sĩ]` (1). Không có `___` kiểu MIMIC-IV gốc.
- **Thuốc trộn 3 hệ tên**: generic EN (`omeprazole`, `allopurinol`, `metoprolol 25mg`), biệt dược Mỹ (`gleevec`, `tylenol`, `bactrim`, `suboxone`, `eliquis`), biệt dược Việt (`Medrol 16mg`, `Omez 20mg`, `Zestril 10mg`, `Fortex 25mg`, `Philpovin 5g`, `Nitramyl 2,5 mg`). Nhóm thứ ba **không có trong RxNorm** → cần bảng biệt dược Việt → hoạt chất (Danh mục thuốc BYT / Drugbank VN) làm tầng trung gian.
- **Chỉ 8 file có bảng xét nghiệm số** (24, 26, 36, 40, 53, 58, 6, 97). Hai nhãn `TÊN_XÉT_NGHIỆM`/`KẾT_QUẢ_XÉT_NGHIỆM` đóng góp ít → không đầu tư nhiều.
- Số thập phân dùng **cả dấu phẩy và dấu chấm** (`14,43` vs `14.99`).

### 3.4 Cấu trúc section rất đều — chìa khóa cho assertions

Header cấp 1 (đếm được):

```
33× "2.  Tiền sử bệnh hiện tại"      25× "3.  Đánh giá tại bệnh viện"
21× "1.  Tiền sử bệnh"               11× "2. Bệnh sử hiện tại"
 9× "1.  Tiền sử bệnh nội khoa"       4× "1.  Tiền sử bệnh lý"
```

Sub-label:

```
35× "Lý do nhập viện:"               19× "Thời điểm khởi phát triệu chứng:"
10× "Thuốc trước khi nhập viện:"      8× "Kết quả chẩn đoán hình ảnh:"
 7× "Tiền sử phẫu thuật / thủ thuật:" 5× "Triệu chứng hiện tại:"
 3× "Bệnh lý mãn tính:"               2× "Tiền sử gia đình:"
 2× "Tiền sử bản thân:"               2× "Tiền sử dịch tễ:"  2× "Dị ứng:"
```

Ví dụ vòng 1 chứng minh assertion gán theo **section**, không theo câu: toàn bộ thuốc dưới header "Danh sách thuốc trước nhập viện" đều `isHistorical` bất kể câu chứa cue gì. → **Parse cây section rồi gán assertion theo scope là ăn phần lớn điểm mà không cần model.**

### 3.5 Hai lỗi/mơ hồ trong đề

- Phần Tổng quan và §3.2 đều nói output phải có "mối liên hệ **giữa các khái niệm**" (quan hệ thuốc–bệnh, triệu chứng–chẩn đoán), nhưng schema JSON **không có field nào** cho quan hệ đó — `assertions` chỉ là thuộc tính của entity đơn lẻ. Rất có thể đây là phần **nâng cấp Round 2** đang bị hoãn. → Kiến trúc phải tách sạch giai đoạn extract entity và giai đoạn relation ngay từ đầu.
- Ví dụ §3.2: input ghi `WBC` nhưng output ghi `"TWBC"` — text không tồn tại trong input, position không thể hợp lệ. Xác nhận GT có nhiễu → **không tối ưu quá sát vào ví dụ trong đề**.

## 4. Nguồn dữ liệu — không cần UMLS license

Đã kiểm chứng, không có gì phải chờ duyệt:

| Nguồn | License | Dùng cho |
|---|---|---|
| **RxNav public API** | Không cần | `getAllConceptsByTTY` lấy toàn bộ concept theo TTY (SCD/SBD/IN/PIN/BN/SCDC). `getRxcuiHistoryStatus` scope **"Current and Historical"** → lấy được concept obsolete/remapped (đúng thứ prescribable subset lọc mất). Giới hạn **20 req/s**, NLM khuyến nghị cache 12–24h. `getApproximateMatch` để mô phỏng hành vi annotator. |
| **RxNorm prescribable subset** | Public domain, không login | RXNCONSO / RXNSAT / RXNREL. Xương sống index. Nhược điểm: đã lọc bỏ suppressed + obsolete. |
| **RxNav-in-a-Box** | Cần kiểm tra | Docker local, cùng REST API, cho khối lượng lớn. |
| **`tamton23/primekg-vn-icd10-omop`** | Kiểm tra license trước khi dùng | `icd10_danh_muc.csv` — danh mục ICD-10 BYT, **15.844 mã** tiếng Việt. |
| WHO ICD API | Cần register key | ICD-10 chỉ có **English + French**, KHÔNG có tiếng Việt → chỉ dùng bổ trợ tên Latin. |

Attribution: app dùng data NLM phải ghi chú "uses publicly available data from the U.S. National Library of Medicine (NLM)" và NLM không endorse sản phẩm.

## 5. Kiến trúc

Model nằm dưới ngưỡng 9B:

- **SapBERT-UMLS-2020AB-all-lang-from-XLMR-large** (~0.55B) — cross-lingual VI→EN entity linking, self-alignment pretraining trên UMLS 2020AB. Dùng `[CLS]` làm representation. Trùng đúng era của GT (2020AB).
- **XLM-R large / PhoBERT-large / ViHealthBERT** — token classification cho NER (offset chính xác).
- **Qwen3-8B + LoRA** — phân xử type khi encoder lưỡng lự, xử lý span dài/mơ hồ.

Nguyên tắc: **không dùng LM sinh trực tiếp span** — offset sẽ lệch. Encoder lo offset, LM lo ngữ nghĩa.

### Tầng linking — luật cơ học trước, model chỉ để bù recall

Hai nhánh của `candidates_score` đều đã tìm ra công thức tái tạo GT. Đây là thay đổi lớn so với thiết kế ban đầu: **model không quyết định mã, luật quyết định.**

**Nhánh `CHẨN_ĐOÁN` → ICD-10** (chi tiết ở [worklog/01](worklog/01-xay-kb-icd10-rxnorm.md)):

```
match tên tiếng Việt → nếu mã trúng bị cờ cột 25 ("có mã 4-5 ký tự cụ thể hơn")
                       thì bung toàn bộ mã con, loại mã cha
```

Kiểm chứng: `"bệnh trào ngược dạ dày - thực quản"` → `K21.0 + K21.9`, khớp GT của đề chính xác.

**Nhánh `THUỐC` → RxNorm** (chi tiết ở [worklog/02](worklog/02-kiem-chung-luat-tra-ma-thuoc.md)):

```
mention → làm sạch chuỗi → approximateTerm → lọc TTY → hạng 1
           (bỏ liều dùng,                     (SCD nếu còn hàm lượng,
            sửa chính tả,                      IN nếu chỉ còn tên hoạt chất)
            dịch xl/er→extended release)
```

Đo trên 13 cặp GT của đề: gõ thô 0/13 top-1 → thêm lọc SCD 5/13 → thêm làm sạch chuỗi **10/13**. Đúng bằng số mã GT có mặt trong prescribable subset, tức luật giải hết mọi ca giải được. 3 ca còn lại là mã obsolete/remapped, cần bù bằng `getRxcuiHistoryStatus`.

Cảnh báo overfit: 13 mẫu, 4 ca do tôi tune tay. Phải đo lại trên ≥100 cặp sau khi annotate corpus.

**Vai trò còn lại của model** — bù recall, không chọn mã:
1. Chuẩn hóa mention: dịch biệt dược Việt → hoạt chất (Medrol, Omez… không có trong RxNorm, luật trên không chạm tới).
2. Retrieval khi luật trượt: SapBERT-XLMR (dense) + BM25 trên chuỗi normalized. Bắt buộc cho ICD vì match tên chính xác chỉ đạt **1/20** trên mention corpus thật.
3. Luật quyết định **số lượng** mã trả về — `candidates_score` chia theo `len(GT)+1` nên đoán đúng số lượng đáng giá bằng đoán đúng mã. Học phân bố `len(GT)` từ data đã annotate.

### Tầng assertions

Luật section-scope là chủ lực, classifier chỉ xử lý ca khó. **Mặc định `[]`.**

## 6. Probe leaderboard — 5 lần nộp/ngày, lấy lần cuối

Nộp dạng **zip**, 100 file `.json` ở gốc archive, không bọc thư mục con. Đã xác nhận
được chấp nhận (`num_scored = 100`).

Vì §2 đã xác nhận công thức chấm, giá trị của việc probe **giảm mạnh**: có GT là tự
tính điểm offline được. Ưu tiên chuyển sang xây oracle offline (GĐ1), probe chỉ dùng
để kiểm chỗ offline không đo được (nhiễu GT, cách metric tokenize WER).

| # | Ngày | Bản nộp | Kết quả |
|---|---|---|---|
| 1 | 28/07 | luật thuần, 990 entity, `assertions` rỗng hết | **16.2858** — text 17.06 / assert 18.58 / cand 13.99 |

Probe còn đáng làm: nộp bản **chỉ có `THUỐC`** kèm candidates, bỏ hết `CHẨN_ĐOÁN`;
rồi bản ngược lại. Tách được RxNorm-score khỏi ICD-score — hai bên xử lý khác nhau
và cần biết bên nào đang lỗ.

Probe phụ (ngày sau, rất đáng giá): nộp bản **chỉ có `THUỐC`** với candidates, bỏ hết `CHẨN_ĐOÁN`; rồi bản ngược lại. Tách được RxNorm-score khỏi ICD-score — hai bên cần cách xử lý khác nhau và cần biết bên nào đang lỗ.

## 7. Lộ trình

| GĐ | Ngày | Nội dung |
|---|---|---|
| **0** | 1 | Dựng project, script tách + dedupe block, tải KB. Nộp probe #1 lấy baseline thật. |
| **1** | 1–3 | Gom 100 file → ~60–70 block độc nhất. Annotate cấp block chất lượng cao nhất. Chiếu ngược ra 100 file với `position` đúng. Đây là train set + oracle đo offline. |
| **2** | 3–7 | **Linking (0.4 điểm)**. Index BM25 + SapBERT. Bắt chước annotator: SCD trước → fallback IN; giữ concept historical. Học phân bố `len(GT)`. |
| **3** | 5–10 | **NER**. Encoder token-classification, train trên data distill. Ngưỡng thiên precision. |
| **4** | 8–10 | **Assertions**. Parse cây section + cue word. Mặc định `[]`. |
| **5** | 10+ | Đóng gói: Docker offline, README, weights. Bắt buộc — top ~15 phải gửi code để BTC chấm private test. |

Ưu tiên sau bản nộp #1 — **thứ tự đã đổi so với dự tính ban đầu**:

1. **Oracle offline + data annotate (GĐ1)**. Chặn tất cả việc khác. Vì §2 đã biết
   công thức chấm, có GT là tự tính điểm được → không còn phải tiêu lượt nộp để đo.
2. **Recall NER**. WER 82.94 với 990 entity, median 8/file, có file 0 entity → lỗi
   chính là **deletion**, không phải insertion. Nguyên tắc "thiên precision" của WER
   vẫn đúng, nhưng ở mức recall hiện tại thì thêm entity vẫn lời.
3. **Linking (0.4 điểm)**. Vẫn là chỗ đòn bẩy lớn nhất, đang 13.99 với độ phủ 33%.
4. **Assertions**. Sàn 18.58 (để rỗng). Luật section phải vượt mốc đó mới đáng bật.

## 8. Ràng buộc vận hành cần tính từ đầu

- Top ~15 đội phải gửi **code + data + model weights + README** để BTC dựng lại và chấm trên **private test**.
- Pipeline phải chạy **offline hoàn toàn**, đóng gói Docker, **không gọi mạng** lúc inference.
- KB phải nằm trong bundle hoặc có script tải rõ ràng.
- Nếu BTC không cài được code → được liên lạc hỗ trợ trong thời gian giới hạn, không kịp thì **bị loại**.
- Hardware có: Colab **L4 + A100**. Đủ cho fine-tune 8B với LoRA.

## 9. Nhật ký làm việc

Mỗi giai đoạn / scope có một file trong [`worklog/`](worklog/). Quy ước và danh mục ở [worklog/README.md](worklog/README.md). Ghi trong lúc làm, ghi cả đường cụt, số liệu luôn kèm cách đo. Phát hiện ảnh hưởng chiến lược thì cập nhật file này, worklog chỉ trỏ tới.

## 10. Việc còn mở

- [ ] Xác nhận Round 2 có thêm field relation giữa các entity hay không (dự kiến công bố 21/7, cần kiểm tra lại trang cuộc thi).
- [x] ~~Nguồn ICD-10 tiếng Việt~~ → đã có `data/raw/icd10_kb.json`, 15.037 mã. Xem [worklog/01](worklog/01-xay-kb-icd10-rxnorm.md).
- [ ] Kiểm tra license của `icd10_danh_muc.csv` trong repo primekg-vn.
- [ ] Kiểm chứng **luật bung mã con ICD** (match tên → nếu mã trúng có cờ "có mã cụ thể hơn" thì bung mã con, bỏ mã cha). Suy ra từ ví dụ K21 → K21.0+K21.9. Chi tiết [worklog/01](worklog/01-xay-kb-icd10-rxnorm.md).
- [ ] Quyết định xử lý 99 chỗ mask `***`: bỏ entity hay giữ không candidate. Nên probe để biết.
- [ ] Xây bảng biệt dược Việt → hoạt chất (Medrol, Omez, Zestril, Fortex, Philpovin, Nitramyl…).
- [ ] Xác nhận giả thuyết corpus EHR = MIMIC-IV dịch máy. Nếu đúng, tái tạo pipeline sinh data của BTC → train set gần như vô hạn cùng phân bố.
