# Viettel AI Race 2026 — Bài 2 — Chiến lược
> Soạn 17/07/2026. Mọi số liệu dưới đây đo trực tiếp trên `input/` (100 file) hoặc verify từ nguồn gốc.

---

## 0. TL;DR — 5 quyết định

1. **Deadline là 04/08, KHÔNG phải 30/07. Và đề sẽ ĐỔI vào 21/07** (4 ngày nữa). ⇒ Từ nay đến 21/07 **không xây model cuối**. Chỉ xây thứ sống sót qua đổi đề.
2. **Bài này ~90% là NER, không phải entity linking.** Toàn bộ RxNorm chỉ đáng ~2 điểm. Kéo NER từ Jc 0.60→0.80 đáng **+18 điểm**. Top đang kẹt ở Jc≈0.60.
3. **Vũ khí chính: gazetteer ICD-10-CM + RxNorm dịch sang tiếng Việt.** Text gold được sinh ra TỪ terminology, nên tra từ điển ngược lại cho ra *cả span lẫn mã*. Đây là đòn bẩy lớn nhất và rẻ nhất.
4. **Đốt 20 lượt nộp từ giờ đến 21/07 để dò cơ chế chấm.** Leaderboard đang đóng băng ở Round 1 — thời điểm rẻ nhất để học. Cơ chế chấm sẽ sống sót qua đổi đề.
5. **Tài sản quý nhất của đội = nền y + nhiều người.** Dùng để gán nhãn dev set 30 file và dựng bảng quyết định TRIỆU_CHỨNG vs CHẨN_ĐOÁN (chỗ mất điểm kép).

---

## 1. Sự thật đã xác minh

### 1.1 Lịch — ĐỌC TRỰC TIẾP TỪ TRANG THI (17/07)
- Bài y tế = **"Bài 2 - Ontological Reasoning in Medical Knowledge Retrieval"** ⇒ thông báo "nâng cấp Đề 2" **áp dụng cho ta**.
- **PHASE 1: 02/07 → 04/08** (đồng hồ đếm ngược: 18 ngày). `PROJECT_CONTEXT.md` ghi 30/07 là **đã lỗi thời**.
- Trích nguyên văn thông báo:
  > *"Do phát sinh sự cố kỹ thuật, BTC tạm thời chưa công bố phiên bản nâng cấp tại Round 2 của Đề 2... đề thi và bảng xếp hạng của Đề 2 sẽ được **giữ nguyên theo Round 1 đến thứ Ba, ngày 21/7**, để các đội tiếp tục huấn luyện mô hình. Dự kiến, **phiên bản nâng cấp của Đề 2 sẽ được công bố vào thứ Ba, ngày 21/7**. Đồng thời, BTC sẽ **gia hạn thêm 05 ngày thi đấu, đến hết ngày 04/8**."*
- PHASE 2: 15–18/08 (API endpoint). PHASE 3: 09–10/09.

### 1.2 Đề thật RỘNG HƠN `PROJECT_CONTEXT.md` — nguyên văn từ trang thi
> *"Hệ thống cần xác định loại khái niệm (**triệu chứng, kết quả xét nghiệm, bệnh, thuốc, thông tin bệnh nhân**), ánh xạ **bệnh với chuẩn ICD-10** và **thuốc với chuẩn RxNorm**, đồng thời suy luận mối liên hệ ngữ cảnh (**phủ định, người nhà, tiền sử**) cũng như **quan hệ giữa các khái niệm**."*

⇒ **5 loại khái niệm** (không phải 3), **ICD-10 cho bệnh**, và **quan hệ giữa khái niệm**. Bản Round 1 hiện tại chỉ là *tập con*. Bản nâng cấp 21/07 nhiều khả năng bổ sung: `XÉT_NGHIỆM`, `THÔNG_TIN_BỆNH_NHÂN`, ICD-10 candidates, relations.

### 1.3 `position` — đã giải mã và xác minh
Truy ngược offset trong ví dụ đề: delta so với text 1 dòng tăng **đúng +2 mỗi mục danh sách** ⇒ input thật là list xuống dòng + thụt lề 2 space.

**Kết luận:** `position` = chỉ số ký tự **NFC** trên nội dung file **đọc thô** (kể cả `\n`, thụt lề), `end` **exclusive**.
```python
raw = open(f, encoding="utf-8").read()      # KHÔNG strip, KHÔNG chuẩn hoá lại
assert raw[start:end] == entity_text
```
Đã kiểm: cả 100 file đều **NFC thuần**, không BOM, không CRLF, không tab. `len(gt_span)` khớp `len(text)` 17/17 trong ví dụ.

### 1.4 RxNorm — verify qua RxNav API (`/REST/rxcui/{id}/properties.json`)
| RXCUI | Tên | TTY |
|---|---|---|
| 308135 | amlodipine 10 MG Oral Tablet | **SCD** |
| 243670 | aspirin 81 MG Oral Tablet | **SCD** |
| 866436 | 24 HR metoprolol succinate 50 MG ER Oral Tablet | **SCD** |
| 392085 | guaifenesin 800 MG Oral Tablet | **SCD** |
| **7597** | **nystatin** | **IN** ← ngoại lệ |
| 313782 | acetaminophen 325 MG Oral Tablet | SCD |
| 904475 | pravastatin sodium 40 MG Oral Tablet | SCD |
| 1099279 | docusate sodium 100 MG Oral Tablet | SCD |
| 312935 | sennosides, USP 8.6 MG Oral Tablet | SCD |
| 197527 / 197528 | clonazepam 0.5 / 1 MG Oral Tablet | SCD |

**Quy tắc 2 tầng (quan trọng):** có liều + dạng/đường dùng → **SCD**; không có → lùi về **IN** (đó là lý do `nystatin`=7597). Không có SBD/BN nào — biệt dược bị quy về generic.

⚠️ **Đừng dùng RxNav `approximateTerm`**: nó dừng ở **SCDC** (thiếu dạng bào chế) vì không suy được "po" → "Oral Tablet". Luôn hụt 1 tầng. Phải tự map route→dose form rồi lọc `TTY=SCD`.

### 1.5 `assertions` = tên thuộc tính medspaCy ConText, camelCase hoá
```python
# medspacy/context/context.py — DEFAULT_ATTRIBUTES
"NEGATED_EXISTENCE": {"is_negated": True}     -> isNegated
"POSSIBLE_EXISTENCE": {"is_uncertain": True}  -> isUncertain
"HISTORICAL":        {"is_historical": True}  -> isHistorical   ← khớp literal quan sát được
"HYPOTHETICAL":      {"is_hypothetical": True}-> isHypothetical
"FAMILY":            {"is_family": True}      -> isFamily
```
Đề chính thức ghi "(**phủ định, người nhà, tiền sử**)" — khớp đúng 3/5 trục. Không hệ nào khác (cTAKES dùng `historyOf`, AWS dùng `PAST_HISTORY`, JSL dùng `present/absent`) sinh ra literal `isHistorical`.

**Tập nhãn nhiều khả năng nhất:** `{isNegated, isHistorical, isFamily, isHypothetical, isUncertain}`.
**Đây là cờ độc lập, `[]` = present/affirmed** (không có `isPresent`). medspaCy Sectionizer gán `is_historical=True` cho cả section `past_medical_history` — giải thích vì sao danh sách thuốc tiền sử đều `["isHistorical"]`.

### 1.6 ⭐ CHẨN_ĐOÁN = thuật ngữ ICD-10-CM dịch máy
Đo trên `input/`, 36 cụm mang dấu vân tay ICD-10:

| Text trong file | ICD-10-CM | Mã |
|---|---|---|
| u cơ trơn tử cung, **không đặc hiệu** | Leiomyoma of uterus, unspecified | D25.9 |
| xuất huyết nội sọ không do chấn thương, **không đặc hiệu** | Nontraumatic intracranial hemorrhage, unspecified | I62.9 |
| bệnh thận mạn, **không đặc hiệu** | Chronic kidney disease, unspecified | N18.9 |
| suy tim, **không đặc hiệu** | Heart failure, unspecified | I50.9 |
| tăng huyết áp vô căn (nguyên phát) | Essential (primary) hypertension | I10 |
| bệnh phổi tắc nghẽn mạn tính, không xác định | COPD, unspecified | J44.9 |
| nhiễm khuẩn đường tiết niệu, vị trí không xác định | Urinary tract infection, site not specified | N39.0 |
| hội chứng turner, **không đặc hiệu** | Turner's syndrome, unspecified | Q96.9 |
| cường cận giáp nguyên phát | Primary hyperparathyroidism | E21.0 |

**Hệ quả — đây là chỗ ăn thua:**
- Ranh giới span của `CHẨN_ĐOÁN` **là biên của thuật ngữ ICD-10**, không phải do người gán tuỳ ý. Có thể **tra từ điển** thay vì đoán.
- ICD-10-CM public, free (CMS.gov), ~74.000 mã kèm mô tả. Dịch toàn bộ mô tả sang tiếng Việt bằng cùng loại MT ⇒ **gazetteer VI→mã**, string/fuzzy match ra **span + code cùng lúc**.
- Việc này ăn cả `text_score`, `candidates_score` và cải thiện `Jc` (⇒ ăn lây cả `assertions_score`).

### 1.7 Giả thuyết: gold sinh bằng pipeline tự động (INFERENCE, độ tin cậy cao)
Docs AWS Comprehend Medical `InferRxNorm` tái hiện *đồng thời* 4 đặc điểm: (a) "p.o."→Oral Tablet ⇒ SCD top-1; (b) IN làm fallback; (c) `RxNormConcepts` là **mảng xếp hạng** (khớp tên field `candidates` số nhiều); (d) span gộp entity+attributes ⇒ `"amlodipine 10 mg po daily"`.
Không corpus public nào (n2c2 2018/2019/2022, i2b2, MADE, CADEC, Med7) gán nhãn kiểu này — tất cả tách Drug/Strength/Route riêng và/hoặc không có normalization.

⇒ **Gold là silver-standard do Viettel tự sinh.** Chiến lược đúng là **bắt chước cỗ máy sinh nhãn, không phải "gán nhãn cho đúng về mặt y khoa"**. Chỗ nào tool sai một cách hệ thống, ta phải sai theo.

> ⚠️ **Ranh giới tuân thủ:** KHÔNG đưa API ngoài (AWS/GPT/Claude) vào pipeline nộp bài — luật cấm rõ. Cách ICD-10/RxNorm gazetteer ở §1.6 đạt cùng mục tiêu mà **không cần API nào**. Nếu định dùng model lớn để sinh dữ liệu train offline, **hỏi BTC trước** bằng văn bản.

---

## 2. Mô hình điểm — vì sao NER là tất cả

`final = 0.3·T + 0.3·A + 0.4·C`

`assertions` và `candidates` **chỉ được chấm trên concept khớp được với GT**. Concept trượt (miss hoặc thừa) = 0 cả 3 metric (đề nói rõ: sai loại → tính 2 lần, mỗi lần 0đ). Do đó, với `Jc` = Jaccard giữa tập concept dự đoán và GT:

```
final ≈ 0.3·T + 0.3·(Jc · acc_assertion) + 0.4·(Jc · acc_candidate)
```

**Kiểm chứng ngược với leaderboard:**

| Jc | F1 tương đương | final dự đoán |
|---|---|---|
| 0.55 | 0.710 | 50.65 |
| **0.60** | **0.750** | **55.20** ← top thật = **54.66** |
| 0.70 | 0.824 | 64.30 |
| 0.80 | 0.889 | 73.40 |

Mô hình tái tạo gần như chính xác. Cả 10 đội top nằm trong dải 51–54 ⇒ **tất cả đang kẹt cùng chỗ: Jc ≈ 0.55–0.60**. (Hạng 3 và 4 trùng điểm tới 5 chữ số — dấu hiệu nhiều đội hội tụ về cùng một baseline.)

**Đo thực tế tỉ lệ thuốc:** ~40 loại thuốc, ~145–250 lượt nhắc / **~2.500 concept** ⇒ **d ≈ 6–10%**. Chỉ 29/100 file có mục "Thuốc trước khi nhập viện" (ví dụ trong đề là file danh sách thuốc — **không điển hình**).

| Đòn bẩy | Giá trị |
|---|---|
| RxNorm 0% → 100% (d=0.08) | **+1.9 điểm** |
| Assertion 0.65 → 0.90 | **+4.5 điểm** |
| **Jc 0.60 → 0.70** | **+9.4 điểm** |
| **Jc 0.60 → 0.80** | **+18.2 điểm** |

**⇒ NER > RxNorm khoảng 5–10 lần.** Và ~92% `candidates_score` (trọng số 0.4) là **điểm cho không**: chỉ cần trả `candidates` rỗng cho triệu chứng — vì `J=1` khi cả gt lẫn pred đều rỗng.

> Lưu ý: nếu bản 21/07 thêm ICD-10 cho bệnh, `d` tăng lên ~40% ⇒ candidates thành ~10–12 điểm. **Gazetteer ICD-10 (§1.6) phòng sẵn cho việc này.**

### 2.1 Bẫy: WER không bị chặn dưới bởi 0
`T = mean(1 − WER)`. WER = (S+D+I)/N. **Dự đoán thừa tạo Insertion, WER có thể > 1 ⇒ (1−WER) ÂM.** Dự đoán rỗng chỉ về 0.
⇒ **Precision > Recall.** Khi phân vân, ĐỪNG trích. Đây có thể là lý do một số đội điểm thấp bất thường.

---

## 3. Kế hoạch 18 ngày

### GIAI ĐOẠN A: 17/07 → 21/07 (4 ngày) — CHỈ xây thứ sống sót qua đổi đề

**KHÔNG** fine-tune model cuối. **KHÔNG** tối ưu format hiện tại.

| # | Việc | Ai | Sống sót đổi đề? |
|---|---|---|---|
| A1 | **Dò cơ chế chấm bằng 20 lượt nộp** (§4) | 1 người | ✅ Cơ chế không đổi |
| A2 | **Gán nhãn dev set 30 file** theo hiểu biết tốt nhất | Nhóm y | ✅ Phần lớn |
| A3 | **Dựng gazetteer ICD-10-CM tiếng Việt** (74K mã) | 1 người | ✅ Đề yêu cầu ICD-10 |
| A4 | **Dựng gazetteer RxNorm SCD+IN** | 1 người | ✅ |
| A5 | Harness: đọc offset, eval script, section parser | 1 người | ✅ |
| A6 | **Bảng quyết định TRIỆU_CHỨNG vs CHẨN_ĐOÁN** | Nhóm y | ✅ Chỗ mất điểm kép |

**A3 làm thế nào:** tải `icd10cm-codes-2026.txt` từ CMS → dịch 74K mô tả EN→VI bằng model MT (chạy 1 lần trên Colab, cache lại) → index bằng embedding (`AITeamVN/Vietnamese_Embedding_v2`, Apache-2.0, XLM-R large, 8K ctx) + string match. Đây là tài sản dùng lại cho mọi vòng.

### GIAI ĐOẠN B: 21/07 → 04/08 (14 ngày)
1. **21/07: đọc kỹ đề mới ngay trong ngày.** So với §1.2 để biết thêm gì.
2. Ghép pipeline (§5), đo trên dev set, không đo bằng lượt nộp.
3. Mỗi ngày: 1–2 lượt nộp để hiệu chỉnh, giữ lại 2–3 lượt dự phòng.
4. **Chốt trước 02/08.** Chừa 2 ngày cho code + weights + README (top ~15 phải nộp để BTC dựng lại).

---

## 4. Kế hoạch dò leaderboard (bắt đầu NGAY)

Leaderboard trả **5 chữ số thập phân** trên đúng 100 file này ⇒ oracle chính xác. 1 sample = 1/100 ⇒ ~1 điểm/sample: **đo được rõ ràng**.

**Nguyên tắc:** mỗi lượt đổi **đúng 1 biến** so với lượt trước. Delta = câu trả lời.

| # | Nộp gì | Trả lời câu hỏi |
|---|---|---|
| P1 | `[]` cho cả 100 file | **Baseline rỗng.** Nếu > 0 ⇒ concept bị miss vẫn được J=1 khi gt rỗng (lỗ hổng lớn). Nếu = 0 ⇒ miss = 0 (như đề mô tả). **Quan trọng nhất — làm đầu tiên.** |
| P2 | 1 concept đúng/file (thuốc chắc chắn) | Concept khớp theo gì: text? position? cả hai? |
| P3 | Như P2, đổi `type` sang sai | Kiểm chứng quy tắc "tính 2 lần, mỗi lần 0đ" |
| P4 | Như P2, sai lệch `position` 1 ký tự | `position` có dùng để khớp không? |
| P5 | Như P2, nhân đôi mỗi entity | Có dedup không? |
| P6 | Như P2, đảo thứ tự mảng | `text_score` có nối chuỗi theo thứ tự không? |
| P7 | Bỏ hẳn key `candidates` vs `"candidates": []` | Key thiếu = rỗng? |
| P8 | Thêm `candidates` cho 1 triệu chứng | Triệu chứng có candidates trong GT không? |
| P9 | Thêm ICD-10 cho 1 chẩn đoán | **Bệnh có ICD-10 candidates ở Round 1 chưa?** |
| P10 | Tất cả assertions = `[]` vs gán cờ | Tỉ lệ concept có cờ trong GT |

P1, P9 là 2 lượt giá trị nhất. P9 trả lời trực tiếp câu "candidates đáng 2 điểm hay 12 điểm".

> **Hợp lệ:** dò để học **quy tắc gán nhãn** → là một phần thuật toán, tổng quát hoá sang private test.
> **Vi phạm:** hard-code output theo điểm → chết ở vòng BTC dựng lại code trên private test. Đừng làm.

---

## 5. Kiến trúc đề xuất

```
raw text (NFC, đọc thô)
   │
   ├─► [1] Section parser (rule)  ── 3 section chính, ~40 sub-header cố định
   │        └─ 746 "Tiền sử bệnh hiện tại" | 504 "Bệnh sử hiện tại" | 388 "Đánh giá tại bệnh viện"
   │
   ├─► [2] Sinh span ứng viên  (2 nguồn hợp lại — recall cao)
   │        ├─ (a) Gazetteer match: ICD-10-VI (74K) + RxNorm SCD/IN  ← độ chính xác biên span cao
   │        └─ (b) LLM ≤9B few-shot trên từng dòng bullet             ← bắt free-text
   │
   ├─► [3] Lọc precision: self-consistency k/n runs  ← CHỐNG WER insertion (§2.1)
   │
   ├─► [4] Gán type: THUỐC (gazetteer) | CHẨN_ĐOÁN (khớp ICD-10) | TRIỆU_CHỨNG (còn lại)
   │        └─ §6: bảng quyết định của nhóm y
   │
   ├─► [5] Assertions: ConText tiếng Việt (rule) + prior theo section
   │        └─ ⚠️ chặn cue nằm TRONG tên thực thể (§6)
   │
   ├─► [6] Candidates: THUỐC→RxNorm 2 tầng (SCD/IN) | CHẨN_ĐOÁN→ICD-10 | TRIỆU_CHỨNG→[]
   │
   └─► [7] Resolve offset: khớp chuỗi ngược vào raw, xử lý trùng lặp theo thứ tự
```

### Model (Colab Pro: chủ yếu L4 24GB / T4 16GB, hiếm khi A100 40GB)
- **Phase 1 nộp file ZIP ⇒ KHÔNG bị 600s.** Chạy bao lâu tuỳ ý trên Colab. Cứ ensemble thoải mái.
- 600s chỉ áp cho Phase 2/3 (API endpoint) và vòng BTC dựng lại code. Thiết kế hướng tới nó, nhưng **đừng hy sinh điểm Round 1 vì nó**.
- **⚠️ T4 (16GB) KHÔNG chạy nổi model 8B FP16** — riêng weights đã 16.06GB. Bắt buộc INT4-AWQ, mà Turing (sm75) không có Marlin kernel, không FlashAttention-2, không bf16 (phải `--dtype=half`). Tránh.
- **L4 (24GB)**: chạy được 8B FP16 nhưng KV cache chỉ ~45K token. Đủ cho bài này (100 file ≈ 50K token input).
- **Chọn model:** `Qwen3-8B` (8.2B — an toàn dưới trần 9B). `Qwen3.5-9B` (ra 03/2026, hybrid thinking) mạnh hơn nhưng **phải verify param count thật < 9B trước khi cam kết** — nó là multimodal nên có thể vượt trần.
- **BẮT BUỘC tắt thinking mode**: `/no_think` **không hoạt động trên Qwen3.5**. Dùng `--reasoning-parser qwen3 --default-chat-template-kwargs '{"enable_thinking": false}'` (cờ `--enable-reasoning` đã bị **xoá** từ vLLM 0.10). Thinking mode đo được **30.7× wall-clock** và **22% response rỗng** do tràn budget — tệ hơn cả không nghĩ.
- Sampling: temp 0.7 / top_p 0.8 / top_k 20. **Không dùng greedy** (card Qwen cảnh báo lặp vô hạn).

### Encoder tiếng Việt (nếu fine-tune token classification)
| Model | Params | Ctx | License | Ghi chú |
|---|---|---|---|---|
| `AITeamVN/Vietnamese_Embedding_v2` | 568M | 2048 | **Apache-2.0** ✅ | Tốt nhất cho retrieval/gazetteer match |
| `Fsoft-AIC/videberta-base` | 142M | 512 | ⚠️ **không khai báo** | PhoNER F1 94.5, fast tokenizer |
| `demdecuong/vihealthbert-base-word` | 135M | **256** ✗ | ⚠️ **không khai báo** | Domain y tế nhưng ctx quá ngắn + cần word-seg |
| `cbc-528a/BamiBERT-ViMedNER` | 102M | 2048 | ⚠️ Qualcomm RAIL | Mới 07/2026, F1 0.686 |

⚠️ Họ PhoBERT (`vihealthbert`, `bkai/vietnamese-bi-encoder`, `dangvantuan/vietnamese-embedding`) đều **chặn ở 256 token** và **cần word segmentation** (pyvi/underthesea) — quên là mất điểm âm thầm. **Nhiều model không khai báo license** — trên HF, thiếu license ≠ được phép dùng. Kiểm tra trước khi nộp code cho BTC.

---

## 6. Hai chỗ mất điểm nhiều nhất

### 6.1 TRIỆU_CHỨNG vs CHẨN_ĐOÁN — phạt kép
Đề nói rõ: đúng text nhưng sai type ⇒ **tính 2 lần, mỗi lần 0đ cả 3 metric**. Đây là lỗi đắt nhất.
**Heuristic mạnh nhất (từ §1.6):** khớp được thuật ngữ ICD-10 ⇒ `CHẨN_ĐOÁN`. Không khớp + nằm trong "Triệu chứng hiện tại"/"Lý do nhập viện" ⇒ `TRIỆU_CHỨNG`.
Nếu giả thuyết Comprehend Medical đúng (§1.7): một `MEDICAL_CONDITION` được tách bằng trait `SIGN`/`SYMPTOM`/`DIAGNOSIS` — tức `TRIỆU_CHỨNG` = SIGN ∪ SYMPTOM, `CHẨN_ĐOÁN` = DIAGNOSIS. Split khá máy móc, không phải phán đoán lâm sàng.

### 6.2 Bẫy phủ định — cue nằm TRONG tên thực thể
Đo trên `input/`: "không" xuất hiện **249 lần**, nhưng nhiều lần là **một phần của tên bệnh**:
- `xuất huyết nội sọ **không do chấn thương**, không đặc hiệu` → **KHÔNG** phải phủ định (là ICD-10 I62.9)
- `tiểu tiện **không** tự chủ` → **KHÔNG** phải phủ định (là incontinence)
- `bệnh gút **không đặc hiệu**` → **KHÔNG** phải phủ định

NegEx ngây thơ sẽ gắn `isNegated` cho hàng loạt ⇒ `J=0` cho từng cái (vì gt là `[]`).
**Fix:** chạy gazetteer ICD-10 TRƯỚC, khoá span, rồi mới chạy ConText — và chỉ xét cue **ngoài** span. Đúng thứ tự medspaCy làm.

### 6.3 Thống kê cue tiếng Việt (đo trên `input/`)
| Trục | Cue | Số lần |
|---|---|---|
| **Negation** | không có (69), âm tính (22), chưa (18), phủ nhận (17), không ghi nhận (16), loại trừ (2) | ~150 |
| **Historical** | tiền sử (217), trước khi nhập viện (116), mãn/mạn tính (89), trước đây (23), cách đây (13) | ~460 |
| **Uncertain** | có thể (13), theo dõi (10), nghi ngờ (7), khả năng (6) | ~36 |
| **Family** | gia đình (5), con trai (2), mẹ (1) | ~8 — hiếm |
| Future/plan | chỉ định (14), tái khám (9), lên lịch (1) | ~24 |

⇒ `isHistorical` là cờ đáng đầu tư nhất. `isFamily` gần như không xuất hiện — đừng tốn công.

---

## 7. Rủi ro

| Rủi ro | Mức | Xử lý |
|---|---|---|
| **Đề đổi 21/07 làm hỏng công sức** | **CAO** | Giai đoạn A chỉ xây thứ sống sót. Không fine-tune trước 21/07. |
| Suy luận Comprehend Medical sai | Trung bình | Gazetteer ICD-10/RxNorm vẫn đúng độc lập với giả thuyết này |
| Over-predict → WER âm | **CAO** | Self-consistency filter; khi phân vân thì bỏ |
| Overfit public test | Trung bình | Dò để học **quy tắc**, không hard-code. Top 15 bị dựng lại trên private test. |
| Qwen3.5-9B vượt trần 9B | Trung bình | Verify param count; fallback `Qwen3-8B` |
| License model không rõ | Trung bình | Ưu tiên Apache-2.0; BTC sẽ đọc code |
| Colab Pro hết compute unit | Trung bình | Phase 1 nộp ZIP nên chạy được ngắt quãng; cache mọi bước |

---

## 8. ĐÃ XÂY XONG (chạy được ngay)

Xem [README.md](README.md). Toàn bộ chạy cục bộ ~1 giây, không GPU, không API.

| Thành phần | Kết quả đo thật |
|---|---|
| `src/sections.py` | **2.217/2.217 offset khớp** `raw[start:end]==text` |
| `src/gazetteer.py` | RxNorm offline; **selftest 8/8 SCD** + fallback IN đúng |
| `src/extract.py` | **153 thuốc, 100% có mã RxNorm** (sau khi lọc dương tính giả) |
| `src/evaluate.py` | Metric tái dựng; xác nhận over-predict → điểm âm |
| `src/probes.py` | **`probes/P1.zip` sẵn sàng nộp** |

**Dữ liệu đã tải:** ICD-10-CM 2026 (74.719 mã, CMS) · RxNorm SCD 17.552 / IN 14.648 / SBD 9.696 (RxNav).

### 8.1 Kết quả kiểm chứng đáng chú ý

**✅ Đã CHỨNG MINH insight ICD-10** (§1.6): 12/12 khớp nguyên văn với CMS.

**✅ Đã CHỨNG MINH rủi ro trích thừa** bằng `src/evaluate.py`:

| Kịch bản | text_score | FINAL |
|---|---|---|
| pred = gold | +1.000 | +100.00 |
| pred rỗng | 0.000 | 0.00 |
| **over-predict 4×** | **−2.000** | **−42.50** |
| **over-predict 8×** | **−6.000** | **−171.25** |

**✅ Đã bắt được dương tính giả thật** trong bản v0: `creatinine` (13 lần), `guaiac` (4),
`caffeine` (2) — đều là chất **xét nghiệm**, không phải thuốc. Lọc bằng "hoạt chất phải
xuất hiện trong tên SCD nào đó" (không dùng `scd_by_ing` — `metoprolol` có 0 SCD vì
RxNorm đặt tên SCD theo **PIN** `metoprolol succinate`).

**❌ Cầu nối VI→ICD-10 CHƯA giải xong** — đây là việc còn lại lớn nhất:

| Cách | Kết quả đo | Kết luận |
|---|---|---|
| `opus-mt-en-vi` dịch EN→VI | fuzzy **42/100**, 0/10 đạt ngưỡng, sinh rác lặp | ❌ bỏ |
| `VietAI/envit5-translation` | vỡ với `transformers 5.7` | ❌ cần transformers<5 |
| `multilingual-MiniLM` khớp chéo | top-1 **1/10** | ❌ không đủ chuyên y sinh |
| `SapBERT-XLMR` khớp chéo | xem `out/sapbert.log` | 🔬 đang thử |
| **LLM ≤9B dịch VI→EN + exact match** | chưa thử | ⬅️ **phương án mạnh nhất còn lại** |

Phương án LLM đáng tin nhất: Qwen3-8B dịch cụm tiếng Việt → tiếng Anh, rồi **khớp CHÍNH XÁC**
với 74.719 mô tả. Chỉ ~2.500 cụm cần dịch (rẻ hơn nhiều so với dịch cả 74.719 mã), và khớp ở
phía tiếng Anh là exact nên không cần fuzzy. Chạy trên Colab.

## 9. Việc làm ngay hôm nay
1. ✅ **Sửa `PROJECT_CONTEXT.md`: deadline 04/08, không phải 30/07.**
2. 🔥 **Nộp `probes/P1.zip` ngay** — đã sinh sẵn, 1 lượt, trả lời câu hỏi đắt nhất.
3. 🔥 **Nhóm y gán nhãn dev set 30 file** → `dev/gold.json` (format như `out/baseline.json`).
4. 🔥 **Giải cầu nối VI→ICD-10** bằng LLM trên Colab (§8.1).
5. 📅 **21/07: đọc đề mới ngay trong ngày.**
