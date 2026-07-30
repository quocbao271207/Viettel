# 07 — Gán nhãn tay cấp block (phương án A)

Trạng thái: **đang làm**
Bắt đầu: 2026-07-28

## Vì sao làm việc này

worklog/06 đo được: **recall là toàn bộ vấn đề**. Bắt đúng 100% khái niệm mà để
`assertions` + `candidates` rỗng hết vẫn được **77.35 điểm**, so với 49 điểm của
đội đầu bảng hiện tại. Còn đánh bóng ICD/RxNorm/assertion chỉ đáng ~2 điểm.

Recall hiện tại của luật tay: tổng **34.1%** — CHẨN_ĐOÁN 16.0%, TRIỆU_CHỨNG
31.9%, THUỐC 50.0%. Luật từ điển đã tới hạn: từ điển chỉ có dạng đầy đủ
(`đái tháo đường không xác định`) nên không khớp cách viết trong văn bản
(`đái tháo đường`). Cần model học từ dữ liệu, mà muốn có model thì phải có
dữ liệu gán nhãn.

User chốt phương án **A**: tôi gán tay toàn bộ, không dùng model ngoài.
"chậm mà chắc, làm toàn bộ cho tôi".

## Quyết định: gán ở cấp BLOCK, không phải cấp file

100 file chỉ gồm **332 đoạn văn độc nhất** (dedup ratio 0.9294). 24 đoạn dùng
lại ở nhiều file, đoạn nhiều nhất xuất hiện 23 lần. Gán theo file là gán lại
cùng một đoạn nhiều lần — vừa chậm, vừa dễ lệch giữa các lần.

Kiểm trước khi chọn (`python3` ad-hoc, ghi lại vì đây là điều kiện an toàn):

- Block có phủ kín file không? **Có.** Ký tự nằm ngoài mọi block chỉ gồm
  `\n` (509), space (77), `\xa0` (2). Không có ký tự nội dung nào bị bỏ.
- 132 nhãn tay sẵn có nằm trong block không? **Cả 132/132.** Không có nhãn
  nào vắt qua ranh giới hai block.

→ Chiếu ngược block → file là an toàn.

### Cạm bẫy: không được cộng offset khi chiếu ngược

Khoá so trùng block (`blocks.norm_for_hash`) bỏ dấu câu và gộp khoảng trắng.
Nên hai lần xuất hiện "cùng một block" có thể lệch ký tự thật. Ca thật đo được:
13 file viết `Câu hỏi từ người dùng :` (có dấu cách trước dấu hai chấm) trong
khi block lưu bản `Câu hỏi từ người dùng:` — lệch 1 ký tự.

Nếu chiếu bằng `offset_file = block_start + offset_trong_block` thì từ chỗ lệch
đó về sau mọi toạ độ sai 1 ký tự, mà `position` sai là mất điểm cả 3 metric.

Cách làm: **tìm lại needle trong chính đoạn văn của file đó**, không cộng
offset. Chậm hơn chút nhưng đúng.

## Công cụ: `src/gt_blocks.py`

Viết nhãn dạng `(needle, nth, type, assertions, candidates)` — không viết toạ
độ tay, để máy tìm. Sai chính tả → báo lỗi ngay chứ không âm thầm trỏ sai chỗ.

Kiểm tự động mỗi lần chạy:
1. needle phải có đủ số lần xuất hiện (`nth` hợp lệ)
2. span sau khi map về file gốc phải trỏ đúng cụm đã gán (bất biến NFC)
3. không hai nhãn trùng span trong một block
4. `assertions` chỉ cho CHẨN_ĐOÁN/THUỐC/TRIỆU_CHỨNG, `candidates` chỉ cho
   CHẨN_ĐOÁN/THUỐC (đề quy định; gán sai loại là tự tạo lỗi)
5. `assertions` chỉ nhận 3 giá trị hợp lệ

Cú pháp `ngữ cảnh [[phần cần lấy]] ngữ cảnh` để trỏ đúng khi cụm ngắn xuất
hiện nhiều chỗ.

Xem block để gán: `python3 src/gt_blocks.py --show <id>`

## Chuyển 132 nhãn cũ sang cấp block

Tự động (script `/tmp/claude/seed.py`), không gán lại tay. Kết quả:

- 132 nhãn → **17 block**
- chiếu ngược ra: **160 entity / 10 file**
- so với `data/gt/` cũ (6 file): **khớp tuyệt đối, 0 lệch**
- 4 file mới có nhãn miễn phí: **42, 55, 72, 80** (+28 entity)

Đây chính là lãi của việc gán theo block: gán 1 lần, dùng ở nhiều file.

Lỗi gặp khi chuyển: tên thuốc bị mask (`*******`) đếm `nth` sai, vì script
chuyển dùng `str.find` (khớp substring bên trong run dấu sao dài hơn) còn
`locate` khớp trọn run. Sửa bằng cách dùng chung `_find_occurrences`.

## Thứ tự gán: block dài nhất trước

Đo đường cong phủ (ký tự trên tổng 189436 ký tự độc nhất):

| số block dài nhất | ký tự | phủ |
|---|---|---|
| 25 | 51798 | 27% |
| 50 | 84707 | 45% |
| 75 | 109642 | 58% |
| 100 | 127718 | 67% |
| 150 | 153991 | 81% |
| 200 | 171765 | 91% |
| 250 | 182508 | 96% |
| 332 | 189436 | 100% |

Median 383 ký tự/block; 54 block dưới 100 ký tự (phần lớn là header, câu dẫn —
gán rất nhanh hoặc rỗng).

Hiện tại: 17 block, 7796 ký tự = **4.1%**.

## Tiến độ

| mốc | block | ký tự | phủ | entity | file chiếu ra |
|---|---|---|---|---|---|
| chuyển từ data/gt | 17 | 7796 | 4.1% | 132 | 10 |
| + block 24, 25 (SHARE) | 19 | 14016 | 7.4% | 215 | 12 |
| + block 26 | 20 | 16855 | 8.9% | 263 | 13 |
| + block 31 (SHARE 26) | 21 | 19130 | 10.1% | 303 | 14 |
| + block 27 | 22 | 21769 | 11.5% | 333 | 15 |
| + block 28 | 23 | 24199 | 12.8% | 401 | 16 |
| + block 29 | 24 | 26523 | 14.0% | 425 | 17 |
| + block 30 | 25 | 28811 | 15.2% | 449 | 18 |
| + block 59, 88 (SHARE 30) | 27 | 31045 | 16.4% | 475 | 20 |
| + block 32 | 28 | 33131 | 17.5% | 491 | 21 |
| + block 33, 34 | 30 | 37169 | 19.6% | 526 | 23 |
| + block 35, 82 (SHARE 35) | 32 | 40216 | 21.2% | 565 | 25 |
| + block 36 | 33 | 42164 | 22.3% | 587 | 26 |
| + block 37 | 34 | 44097 | 23.3% | 611 | 27 |
| + block 38 | 35 | 46023 | 24.3% | 629 | 28 |
| + block 39 | 36 | 47909 | 25.3% | 688 | 29 |
| + block 40 | 37 | 49729 | 26.2% | 724 | 30 |
| + block 41, 90 (SHARE 41) | 39 | 52399 | 27.7% | 738 | 32 |
| + block 42 | 40 | 54077 | 28.6% | 754 | 33 |
| + block 43 | 41 | 55740 | 29.4% | 762 | 34 |
| + block 44 | 42 | 57382 | 30.3% | 787 | 35 |
| + block 45 | 43 | 59016 | 31.2% | 812 | 36 |
| + block 46, 65 (SHARE 46) | 45 | 61837 | 32.6% | 853 | 38 |
| + block 47, 48 | 47 | 65001 | 34.3% | 878 | 40 |
| + block 126, 160 (SHARE 46/45, không phải gán tay) | 49 | 66067 | 34.9% | 890 | 42 |
| + block 49, 50, 86 (SHARE 50) | 52 | 70185 | 37.1% | 920 | 45 |
| + block 51, 52 | 54 | 73136 | 38.6% | 948 | 47 |
| + block 53, 54 | 56 | 75943 | 40.1% | 992 | 49 |
| + block 1 (×4 file) | 57 | 77287 | 40.8% | 1004 | 53 |
| + block 4 (×2 file) | 58 | 78659 | 41.5% | 1009 | 55 |
| + block 55, 56, 57, 58 | 62 | 84038 | 44.4% | 1083 | 59 |
| + block 5 (×2 file), 60, 61, 62, 63 | 67 | 89776 | 47.4% | 1191 | 63 |
| + block 64 | 68 | 91011 | 48.0% | 1219 | 63 |
| + block 66, 67 (SHARE 62), 7, 8 | 72 | 94613 | 49.9% | 1244 | 65 |
| + block 71, 70, 99, 87, 79, 144 (đều SHARE + gán đuôi) | 78 | 100318 | 53.0% | 1331 | 69 |
| + block 130, 108, 96, 72, 81 (SHARE đợt 2) | 83 | 104664 | 55.3% | 1383 | 72 |
| + block 231 (SHARE 53) | 84 | 104861 | 55.4% | 1383 | 72 |
| + cụm 74+83 | 86 | 107013 | 56.5% | 1416 | 73 |
| + cụm 113+123+127 | 89 | 108936 | 57.5% | 1444 | 76 |
| + cụm 118+120+131 | 92 | 110841 | 58.5% | 1499 | 79 |
| + cụm 76+122 | 94 | 112552 | 59.4% | 1541 | 80 |
| + cụm 93+95 | 96 | 114255 | 60.3% | 1559 | 81 |
| + cụm 103+116 | 98 | 115710 | 61.1% | 1572 | 82 |
| + cụm 98+224 | 100 | 116741 | 61.6% | 1602 | 83 |
| + cụm 157+163 | 102 | 117621 | 62.1% | 1608 | 83 |
| + cụm 165+167 | 104 | 118476 | 62.5% | 1656 | 83 |
| + cụm 179+203 | 106 | 119164 | 62.9% | 1665 | 83 |
| + cụm 204+221, 235+246, 241+248 | 112 | 120416 | **63.6%** | 1678 | 83 |
| + cụm 149+198 | 114 | 121340 | 64.0% | 1690 | 83 |
| + block 73, 75 | 116 | 123460 | 65.2% | 1718 | 84 |
| + block 77 | 117 | 124547 | 65.8% | 1765 | 85 |
| + block 78 | 118 | 125631 | 66.3% | 1785 | 86 |
| + block 80, 9 | 120 | 127225 | 67.2% | 1805 | 86 |
| + block 84, 85 | 122 | 129225 | 68.2% | 1823 | 86 |
| + block 89, 91 | 124 | 131051 | 69.2% | 1891 | 86 |
| + block 10, 92 | 126 | 132361 | **69.9%** | 1914 | 87 |
| + block 94, 97 | 128 | 134028 | 70.8% | 1957 | 88 |
| + block 100, 101 | 130 | 135616 | 71.6% | 1997 | 89 |
| + block 102, 11 | 132 | 136791 | **72.2%** | 2010 | 90 |
| + block 12, 104, 105 | 135 | 138664 | 73.2% | 2029 | 92 |
| + block 2 (×3 file), 106, 107 | 138 | 140396 | 74.1% | 2059 | 92 |
| + block 109, 110, 111 | 141 | 142520 | **75.2%** | 2105 | 94 |
| + block 13 (×2 file), 112, 114 | 144 | 144246 | 76.1% | 2127 | 94 |
| + block 115, 117, 124 | 147 | 146212 | 77.2% | 2162 | 96 |
| + block 125, 3 (×3 file) | 149 | 147045 | 77.6% | 2175 | 96 |
| + block 16 (×2 file), 128, 129 | 152 | 148530 | **78.4%** | 2202 | 97 |
| + block 132, 133, 134 | 155 | 150261 | 79.3% | 2235 | 97 |
| + block 135, 136, 17 (×2 file) | 158 | 151664 | **80.1%** | 2268 | 97 |
| + block 137, 18 (×2 file), 138, 139 | 162 | 153562 | **81.1%** | 2297 | 97 |
| + block 140, 141, 142, 143, 19 (×2 file) | 167 | 155865 | **82.3%** | 2340 | 97 |
| + cả 17 block của file 1.txt (bài G6PD) | 184 | 160315 | **84.6%** | 2399 | 98 |
| + cả 13 block của file 26.txt (bài mạch vành) | 197 | 162650 | **85.9%** | 2458 | 99 |
| + cả 5 block của file 87.txt (bệnh án đau ngực) | 202 | 164103 | **86.6%** | 2496 | **100** |
| + 14 block còn lại của file 2.txt (bài Kawasaki) | 216 | 165867 | **87.6%** | 2542 | 100 |
| + 6 block còn lại của file 8.txt (EHR tâm thần + bài Kawasaki) | 222 | 167095 | **88.2%** | 2571 | 100 |
| + 8 block còn lại của file 36.txt (bệnh án thận hư) | 230 | 168039 | **88.7%** | 2590 | 100 |
| + 3 block còn lại của file 10.txt (EHR đánh trống ngực) | 233 | 168975 | **89.2%** | 2605 | 100 |
| + 4 block còn lại của file 41.txt (QA trứng cá) + block 0 | 238 | 169906 | **89.7%** | 2627 | 100 |
| + 3 block còn lại của file 12.txt (EHR âm hộ + QA tai ghép) | 241 | 170774 | **90.2%** | 2633 | 100 |
| + 2 block còn lại của file 91.txt (EHR Turner + QA sỏi niệu quản ghép) | 243 | 171598 | **90.6%** | 2644 | 100 |
| + 10 block còn lại của file 18.txt (đuôi bài giảng CAD) | 253 | 172419 | **91.0%** | 2669 | 100 |
| + 2 block còn lại của file 78.txt (QA chảy máu cam + EHR nhiễm trùng vết mổ ghép) | 255 | 173210 | **91.4%** | 2677 | 100 |
| + 2 block còn lại của file 13.txt (bản dịch khác của block 10/11 — QA bệnh dại) | 257 | 174000 | **91.9%** | 2681 | 100 |
| + 3 block còn lại của file 88.txt (bệnh án đường mật + QA bé ra mồ hôi ghép vào) | 260 | 174788 | **92.3%** | 2690 | 100 |
| + 2 block còn lại của file 5.txt (cùng bệnh nhân đường mật, bản dịch dài hơn) | 262 | 175565 | **92.7%** | 2697 | 100 |
| + 3 block còn lại của file 60.txt (QA trứng cá + EHR van hai lá/ghép thận ghép vào) | 265 | 176302 | **93.1%** | 2722 | 100 |
| + 4 block còn lại của file 49.txt (QA rụng tóc từng mảng + EHR ung thư vú di căn ghép vào) | 269 | 177036 | **93.45%** | 2736 | 100 |
| + 4 block còn lại của file 77.txt (EHR đau khớp bánh chè + phiếu CĐHA/chẩn đoán EHR tim mạch ghép vào) | 273 | 177733 | **93.82%** | 2743 | 100 |
| + 3 block còn lại của file 92.txt (EHR nhiễm trùng huyết đường tiết niệu trên BN liệt hai chi dưới + 2 mẩu bài giảng trứng cá) | 276 | 178411 | **94.18%** | 2764 | 100 |
| + 2 block còn lại của file 54.txt (QA thai phụ uống thuốc + mục bệnh mạn của EHR suy kiệt/CML ghép vào) | 278 | 179075 | **94.53%** | 2779 | 100 |
| + 2 block còn lại của file 40.txt (bệnh án XHTH do quá liều kháng vitamin K, van ĐMC cơ học) | 280 | 179691 | **94.86%** | 2797 | 100 |
| + 2 block còn lại của file 25.txt (QA thuốc tránh thai khẩn cấp + EHR nhiễm trùng vết mổ; 1 block dùng SHARE) | 282 | 180265 | **95.16%** | 2802 | 100 |
| + 2 block còn lại của cặp file 51.txt + 70.txt (hai bản của cùng EHR suy tim mất bù, dùng chung block tiền sử) | 284 | 180785 | **95.43%** | 2812 | 100 |
| + 3 block còn lại của file 46.txt (bệnh án viết tay BN nữ 81t: kết quả siêu âm Doppler tim, dòng chẩn đoán, 3 dòng thủ thuật ghép vào) | 287 | 181267 | **95.69%** | 2826 | 100 |
| + 3 block còn lại của file 58.txt (dòng "2. Chẩn đoán" + "3. Tiên lượng" của bệnh án tóm tắt, và mục "4. Hướng điều trị" trùng nguyên văn 57.txt) | 290 | 181735 | **95.93%** | 2838 | 100 |

Ba nhận xét từ đợt này:

- **Block trùng nhau nguyên khối vẫn còn nhiều.** Block 1 chính là đoạn "phổ
  biến kiến thức viêm hang vị" ở đuôi block 54, xuất hiện 4 lần → gán 12 nhãn
  mà phủ thêm 4 file. Block 61 là câu hỏi viêm hang vị + nguyên đuôi EHR của
  block 53. Block 64 kết thúc bằng 3 dòng thuốc của EHR ảo giác (block 46).
  Trước khi gán block mới, tìm xem nó có phải bản ghép của block đã gán không —
  rẻ hơn gán từ đầu rất nhiều.
- **Mã ICD phải tra, không được đoán.** Đợt này `I31.4` (chèn ép tim),
  `H54.7`, `R11.0`, `R11.2`, `R45.851` đều KHÔNG CÓ trong `icd10_danh_muc.csv`.
  Thay bằng mã có thật: chèn ép tim → `I31.9`, migraine → `G43.9`.
- **Thuốc ngoài RxNorm để `candidates` rỗng.** `trimetazidine`, `Nitramyl`,
  `nghệ`, `mật ong`, `nội tiết Estrogen`, `Mucinex D` không có concept phù hợp
  (chỉ có `turmeric extract`, `Mucinex D Maximum Strength` dạng DP). Bịa mã sẽ
  làm giảm Jaccard, để rỗng thì ít nhất còn cơ hội `J=1` nếu GT cũng rỗng.

## Hai công cụ thêm vào giữa đường (giảm ma sát khi gán)

Gán tay 332 block bằng cách thử-sai qua thông báo lỗi thì quá chậm. Hai thứ đã
thêm vào `src/gt_blocks.py`:

1. **`nth = ALL`** — corpus lặp lại nguyên đoạn rất nhiều (mục "Bệnh sử" và
   "Cận lâm sàng" thường nhắc y nguyên một danh sách triệu chứng). Trước đây
   phải viết `("sốt", 0, ...)`, `("sốt", 1, ...)` từng lần. Giờ `ALL` gán mọi
   lần xuất hiện với cùng nhãn. Chỉ dùng khi ngữ cảnh của MỌI lần xuất hiện
   thật sự giống nhau — đã kiểm bằng `--occ` trước khi dùng.
   `expand_share` cũng hiểu `ALL`: chỉ thừa hưởng khi mọi lần xuất hiện đều
   nằm trong tiền tố VÀ block chia sẻ không có thêm lần xuất hiện mới ở đuôi.

2. **`--occ <block> <needle>...`** — in số lần xuất hiện kèm 45 ký tự ngữ cảnh
   hai bên của từng lần. Chọn `nth` đúng ngay từ đầu, và quan trọng hơn: thấy
   được lần xuất hiện nào bị phủ định, lần nào không.

Bài học: 4 lần đầu gán block 26 đều sai `nth` (đoán số lần lặp từ mắt thường).
`--occ` xoá hẳn lớp lỗi này.

## Ghi chú quy ước phát sinh (block 24–31)

- **Lỗi template của corpus**: block 26 có `ăng huyết áp` (mất chữ T). Vẫn gán
  `CHẨN_ĐOÁN` + `I10` — GT phải khớp text thật trong file, không sửa chính tả.
- **Xét nghiệm bác sĩ *khuyên* làm** (block 27, QA vô sinh): vẫn gán
  `TÊN_XÉT_NGHIỆM`. Lý do: đề chỉ cho assertion với DX/THUỐC/TRIỆU_CHỨNG, nên
  loại xét nghiệm không có cách nào diễn đạt "chưa thực hiện" — đọc nhãn theo
  tên, không theo thời.
- **`candidates` chỉ cho DX và THUỐC**: đã thử gán `R11` cho "buồn nôn"
  (TRIỆU_CHỨNG) và bị `check()` bắt. Máy chặn đúng.
- **"nghi ngờ"**: đề không có assertion cho mức độ chắc chắn (chỉ có
  isNegated/isFamily/isHistorical). "nghi ngờ cơn co giật" vẫn gán CHẨN_ĐOÁN
  với `assertions: []`.
- **Người thứ ba không phải bệnh nhân** (block 26, mẩu QA "cháu bé bị bàn chân
  bẹt" — con của người hỏi): gán `isFamily`.
- **Một phủ định trùm nhiều khái niệm**: "Không ghi nhận co giật, cứng đờ, cắn
  lưỡi hoặc tiểu tiện không tự chủ" → cả 4 đều `isNegated`. Đây là nguồn
  `isNegated` sạch nhất trong corpus.

## Quyết định lớn: khái niệm trong "danh sách nguyên nhân" và "bài giảng"

Corpus có rất nhiều đoạn bác sĩ **giảng giải** thay vì mô tả bệnh nhân:

- block 28: "Nguyên nhân: - Viêm quanh răng... - Viêm nha chu... - Tiểu đường..."
  → bệnh nhân chỉ bị chảy máu chân răng, chưa chẩn đoán bệnh nào trong danh sách.
- block 30: cả một bài giảng về bệnh thoái hóa tinh bột (amyloidosis) — bệnh
  nhân hỏi để hiểu, không mắc.

**Quyết định: VẪN GÁN nhãn cho các khái niệm này.** Ba lý do:

1. Đề chỉ cho 3 assertion (`isNegated`/`isFamily`/`isHistorical`). Không có
   cách nào diễn đạt "đây chỉ là khả năng / là kiến thức chung". Bỏ hẳn thì
   thông tin đó biến mất; gán với `assertions: []` thì ít nhất khớp text.
2. Công thức chấm: bỏ sót một khái niệm mất điểm ở **cả 3** metric
   (text + assertions + candidates). Gán thừa chỉ mất ở khái niệm đó.
3. Đo được ở worklog/06: recall đáng ~22× mọi thứ khác cộng lại.

**Rủi ro đã ghi nhận**: nếu ground truth của BTC *không* gán các đoạn giảng
này, ta mất điểm precision. Chưa kiểm được vì không có GT thật của BTC. Nếu
sau này thấy điểm text tụt so với dự đoán, đây là nghi phạm số 1 — và cách
sửa rẻ: thêm cờ `TEACHING` vào nhãn để lọc ra được, không phải gán lại.

## Cơ chế SHARE đang trả cổ tức lớn

Đo trên 27 block đã gán: 5 block (25, 31, 59, 88 + chính các block gốc) đến từ
SHARE. Ví dụ rõ nhất là block 30 — một bài giảng amyloidosis được ghép vào 3
block khác nhau (30, 59, 88), mỗi lần cắt ở một chỗ. Gán 1 lần, dùng 3 lần.

Đã quét toàn corpus: **38 cặp block có tiền tố chung ≥300 ký tự**. Nghĩa là
còn nhiều cổ tức chưa thu. Quy trình chuẩn cho mỗi block mới: chạy đoạn quét
tiền tố trước, nếu trùng thì khai SHARE thay vì gán tay.

Cạm bẫy đã gặp: nhãn `ALL` **không** tự thừa hưởng qua SHARE khi block chia sẻ
có thêm lần xuất hiện mới ở phần đuôi (block 59 nhắc "amyloidosis" thêm 1 lần).
`expand_share` tự phát hiện và bỏ qua, buộc khai lại tay — đúng, vì lần xuất
hiện mới cần xét ngữ cảnh riêng.

## Đợt SHARE hàng loạt (block 71, 70, 99, 87, 79, 144)

Cách quét lại (đo được, không phải đoán): so tiền tố chung ≥300 ký tự trên bản
NFC của **mọi cặp block**, không chỉ cặp chưa gán. Sáu block hoá ra là tiền tố
của block đã gán tay:

| child | parent | tiền tố chung | đuôi riêng | nhãn gán tay |
|---|---|---|---|---|
| 71 | 62 | 659 | 506c | 7 |
| 70 | 66 | 655 | 525c | 3 |
| 99 | 121 | 648 | 152c | 5 |
| 87 | 7 | 586 | 396c | 13 |
| 79 | 60 | 550 | 524c | 11 |
| 144 | 153 | 381 | 123c | 4 |

43 nhãn gán tay ⇒ +5705 ký tự phủ (+3.1%) và +4 file. So với gán tay từ đầu 6
block này (~5700 ký tự) thì tiết kiệm khoảng 2/3 công.

Ba điểm rút ra:

1. **Đuôi không nhất thiết là phần thêm vào.** Block 70 *thay* dòng "Các yếu tố
   ... lây nhiễm bệnh dại bao gồm:" của block 66 bằng 3 dòng thuốc EHR
   (bumetanide/vancomycin/levofloxacin), rồi mới quay lại bài dại. Nghĩa là nhãn
   `bệnh dại`[3] của block 66 KHÔNG tồn tại ở block 70. `expand_share` tự loại
   vì vị trí nhãn vượt quá `n` — không phải nhờ may mắn, mà vì nó kiểm `end <= n`.
2. **`ALL` phải khai lại khi đuôi có thêm lần xuất hiện.** Block 79 lặp lại toàn
   bộ danh sách triệu chứng của block 60 ở mục "Đặc điểm triệu chứng", nên 6 nhãn
   `ALL` (ăn uống kém do buồn nôn, nôn x 1, chủ quan sốt và run rẩy, mất cảm giác
   ngon miệng/chán ăn, suy nhược, Toàn trạng suy kiệt) bị `expand_share` từ chối
   và phải khai lại bằng `ALL` trong `GT[79]`. Kiểm bằng script in `INH/NO` cho
   từng nhãn trước khi viết — rẻ hơn là chạy `check()` rồi đoán.
3. **Danh sách "Các bệnh lý mạn tính" ⇒ toàn bộ `isHistorical`**, theo tiền lệ
   block 14/20. Block 87 là ca đầu tiên có danh sách này dài (10 dòng).

Mã ICD tra được cho block 87/99 (đều có trong `icd10_danh_muc.csv`):
C92.1 (CML BCR/ABL+), I10, E78.5, E11, M48.0, M11.2 (giả gout = vôi hoá sụn
khớp khác), N18.4 (bệnh thận mạn GĐ4), N40 (phì đại/tăng sản TTL), K74.6 (xơ
gan khác/không xác định), K76.6, R18 (cổ trướng), J90.
RxNorm: bumetanide 1808, vancomycin 11124, levofloxacin 82122.

## Đợt SHARE thứ hai (block 130, 108, 96, 72, 81)

Sau khi build lại, quét tiền tố chung lần nữa (ngưỡng ≥250 ký tự, chỉ xét cặp
child chưa gán / parent đã gán) ra thêm 5 block:

| child | parent | tiền tố chung | đuôi riêng | nhãn gán tay |
|---|---|---|---|---|
| 130 | 7 | 585 | **0c** | 0 |
| 108 | 66 | 453 | 275c | 2 |
| 96 | 43 | 309 | 524c | 10 |
| 72 | 43 | 309 | 824c | 8 |
| 81 | 43 | 309 | 758c | 12 |

32 nhãn gán tay ⇒ +4346 ký tự phủ (+2.3%) và +3 file.

Bốn điểm rút ra:

1. **Có block trùng hoàn toàn với tiền tố của block khác, đuôi rỗng.** Block 130
   là đúng 585 ký tự đầu của block 7, không thêm chữ nào. Chỉ cần
   `SHARE[130] = (7, 585)`, không cần `GT[130]`. Đây là nhãn rẻ nhất có thể —
   0 công. Đáng quét ngưỡng tiền tố thấp hơn nữa để tìm loại này.
2. **Một parent đẻ ra nhiều child rẽ khác hướng.** Block 43 (EHR suy kiệt/ảo
   giác) có 3 child cùng chia sẻ đúng 309 ký tự đầu rồi rẽ ba hướng: 96 kể nốt
   EHR, 72 ghép QA sàng lọc thai, 81 ghép đoạn giảng amyloidosis. Nghĩa là các
   khối trong corpus được cắt từ một tập nguồn chung tại cùng một điểm cắt, rồi
   nối với đoạn khác nhau. Gán 1 parent tốt ⇒ lợi 3 lần.
3. **Đuôi lặp lại danh sách của tiền tố ⇒ phải đếm lại `nth`.** Cả 3 child của
   43 đều nhắc lại `toàn trạng suy kiệt` / `ảo giác` / `Lú lẫn` ở mục "Triệu
   chứng hiện tại". Chỉ số phải đo từng block một (block 96 có `ảo giác` 4 lần,
   block 72/81 chỉ 3 lần) — không chép chỉ số giữa các child dù chúng cùng
   parent.
4. **Nói chung ≠ tên khái niệm.** Ở block 72, "một xét nghiệm nài", "các xét
   nghiệm này" là cách nói chung, không gán; còn `nipt`, `double test`,
   `siêu âm` là tên xét nghiệm cụ thể nên gán LAB. Tương tự "Uống thuốc" ở
   block 81 là đường dùng, không gán (thống nhất với `GT[30]`/`GT[59]` cùng
   nguồn), nhưng `hóa trị` là liệu pháp thuốc nên gán THUỐC.

Mã ICD tra trong `icd10_danh_muc.csv` cho đợt này: Q89.9 (dị tật bẩm sinh,
không xác định) và họ E85 — E85.2 (di truyền gia đình, không xác định) cho
"amyloidosis di truyền hoặc gia đình", E85.3 (toàn thân thứ phát) cho dạng AA
"tự miễn dịch", E85.8 (thoái hóa tinh bột khác) cho dạng AL "chuỗi nhẹ",
E85.9 (không xác định) cho tên chung.

### Hai chỗ tự mâu thuẫn tìm được khi đọc lại tiền lệ (đã sửa)

- `GT[88]` và `GT[87]` gán cùng một danh sách "Các bệnh lý mạn tính" (hai bản
  dịch khác nhau của cùng nguồn) nhưng `GT[88]` dùng needle ngắn
  `tăng lipid máu` và để `Giả gout` với candidates rỗng. Đã sửa `GT[88]` thành
  `tăng lipid máu, không đặc hiệu` + `["M11.2"]` cho khớp.
- `GT[59]` gán `hóa trị` và `ghép gan` là `TÊN_XÉT_NGHIỆM`, trái với `GT[57]`
  (cùng nguồn) nơi `hóa trị` là `THUỐC`, và trái quy ước "thủ thuật không gán".
  Đã sửa: `hóa trị` -> THUỐC, bỏ `ghép gan`.

Bài học: khi gặp một đoạn nguồn đã gán ở block khác, **đọc lại nhãn cũ trước
khi viết nhãn mới**, đừng chỉ gán theo trực giác lần này. Mâu thuẫn giữa hai
block cùng nguồn nghĩa là ít nhất một trong hai sai — mà GT sai thì model học
sai theo.

## Đổi chiến lược: quét cụm giữa các block CHƯA gán (13 cụm, xong hết)

Sau đợt SHARE thứ hai, hạ ngưỡng quét tiền tố xuống 120 ký tự thì chỉ còn đúng
1 cặp (`231 ~ 53`, tiền tố 197, đuôi rỗng). Nguồn "child chưa gán / parent đã
gán" **cạn**.

Cách đo: với mỗi cặp block chưa gán, tính độ dài tiền tố chung sau khi chuẩn
hoá NFC; nối các cặp có tiền tố ≥150 ký tự bằng union-find. Ra **13 cụm phủ 28
block**. Việc xếp lại hàng đợi theo *tổng kích thước cụm* thay vì kích thước
từng block là thay đổi quan trọng: gán 1 gốc cụm mua được 2-3 block.

| cụm | tổng ký tự | tiền tố | nhãn gán tay |
|---|---|---|---|
| 74 + 83 | 2149 | 1028 | 10 + 3 (khai lại ALL) |
| 113 + 123 + 127 | 1937 | 640 / 615 | 11 + 0 + 0 |
| 118 + 120 + 131 | 1884 | — / 236 | 8 + 8 + 20 |
| 76 + 122 | 1746 | 647 | 22 + 0 |
| 93 + 95 | 1697 | 836 | 17 + 0 |
| 103 + 116 | 1436 | 493 | 20 + 6 |
| 98 + 224 | 1031 | 221 | 26 + 0 |
| 157 + 163 | 880 | 308 | 4 + 3 |
| 165 + 167 | 855 | 201 | 25 + 8 |
| 179 + 203 | 688 | 250 | 6 + 1 |
| 204 + 221 | 549 | 248 | 4 + 0 |
| 235 + 246 | 363 | 169 | 1 + 0 |
| 241 + 248 | 340 | 158 | 3 + 0 |

Tổng: **28 block, +15752 ký tự phủ (55.4% → 63.6%)**, và số file có nhãn từ 72
lên 83/100.

Ba cái bẫy gặp trong đợt này:

1. **`ALL` vỡ theo cả hai chiều.** Trước đây (block 79) `ALL` vỡ vì block con
   THÊM lần xuất hiện mới ở đuôi. Lần này block 83 vỡ vì con **BỚT** lần xuất
   hiện: 83 cắt trước dòng "Tình trạng ngay trước khi nhập viện", nên
   `thiếu oxy` / `độ bão hòa oxy` / `86` chỉ còn 1 lần trong con nhưng 2 lần
   trong cha ⇒ `expand_share` từ chối cả 3 (đúng theo thiết kế). Phải khai lại
   tay 3 nhãn đó ở `GT[83]`. Cách phát hiện: sau mỗi `SHARE`, in `GT[child]` sau
   `expand_share` và đếm, đừng tin là đã thừa hưởng.
2. **Hai bản dịch của cùng bài không chắc SHARE được.** Block 118 và 120 là hai
   bản dịch của cùng bài QA bệnh dại nhưng tiền tố chung chỉ 235 ký tự, vì một
   bản viết "trạng thái điên dại ở động vật" còn bản kia dính chữ "điên dạiở".
   Phải gán tay cả hai. Corpus dịch máy ⇒ **giống về nội dung không có nghĩa là
   giống về ký tự**.
3. **Tiền tố chung có thể ngắn hơn phần "trông giống nhau".** Block 167 nhìn
   như trùng 3/4 với 165 (cùng phiếu XN, cùng 2 dòng thủ thuật) nhưng tiền tố
   chỉ 201 ký tự vì giữa bài bị chèn một mẩu tư vấn dinh dưỡng. 6 nhãn cuối
   phải khai lại. Luôn **đo** tiền tố, đừng ước lượng bằng mắt.

### Ba chỗ tự mâu thuẫn nữa (đã sửa)

- `phù gai thị`: `GT[36]` gán `CHẨN_ĐOÁN` + `H47.1`, còn `GT[62]`/`GT[71]` gán
  `TRIỆU_CHỨNG`. Đã đổi `GT[36]` sang `TRIỆU_CHỨNG` (nó xuất hiện dưới mục "Dấu
  hiệu lâm sàng", là dấu hiệu khám).
- `thuốc NSAIDs` trong câu "Đã ngừng sử dụng thuốc NSAIDs": `GT[44]` gán
  `isNegated`, `GT[30]` gán `isHistorical` — cùng một câu nguồn. Đã đổi `GT[30]`
  sang `isNegated`.
- `sỏi đoạn cuối ống mật chủ`: 6 chỗ dùng `K80.5`, riêng `GT[30]` dùng `K80.3`
  (sỏi kèm viêm đường mật — văn bản không nói có viêm). Đã đổi về `K80.5`.

Ba lần liên tiếp tìm được mâu thuẫn khi đọc lại tiền lệ khẳng định quy trình:
**grep needle trong `gt_blocks.py` trước khi viết nhãn mới**, không chỉ để copy
mã ICD mà để phát hiện chính mình đã gán khác ở chỗ khác.

Mã tra đợt này: I10, E11, E11.4, I50.9, N18.9, K59.3, J90, R93.1, E87.5, H40.9,
J85.2, K51, K70, L63.9. RxNorm: lasix 202991 (BN), dextrose → glucose 4850,
folic acid 4511, vitamin C 1151, omeprazole 7646. Không có trong RxNorm:
`insulin` (chỉ có từng loại insulin cụ thể), `carotenoid`, `Flavonoid`,
`corticosteroid` → `candidates` rỗng.

## Nguồn cụm đã cạn — chuyển sang block đơn (73 → 92)

Sau khi làm xong 13 cụm, quét lại union-find với ngưỡng 120 ký tự trên 220 block
còn lại chỉ ra **đúng 1 cặp** (149 ~ 198, tiền tố 126). Làm xong cặp đó nghĩa là
nguồn cụm hết. Từ đây gán từng block đơn, xếp theo `n_chars × n_occurences`.

| block | ký tự | ×lần | file | nhãn | ghi chú |
|---|---|---|---|---|---|
| 73 | 1127 | 1 | 33.txt | 20 | EHR đau ngực/ngất xỉu |
| 75 | 1109 | 1 | 71.txt | 8 | QA nổi mẩn ở lưng + đoạn giảng nguyên nhân |
| 77 | 1087 | 1 | 36.txt | 47 | bệnh án hội chứng thận hư, phiếu XN đầy đủ |
| 78 | 1084 | 1 | 18.txt | 20 | bệnh án viêm túi mật cấp |
| 80 | 1069 | 1 | 4.txt | 8 | tư vấn levothyroxine + 3 dòng nội soi |
| 9 | 525 | **2** | 12/15.txt | 11 | Tiền sử bệnh + Thuốc trước nhập viện |
| 84 | 1001 | 1 | 72.txt | 9 | giảng điều trị mày đay + EHR lạm dụng chất |
| 85 | 999 | 1 | 23.txt | 8 | QA mất ngủ (hỏi CHO MẸ → isFamily) |
| 89 | 920 | 1 | 6.txt | 22 | đánh giá tại BV, EHR chấn thương sọ não |
| 91 | 906 | 1 | 46.txt | 44 | bệnh án viết tay suy tim/phù phổi cấp |
| 10 | 437 | **2** | 16/20.txt | 3 | câu hỏi nguy cơ dại |
| 92 | 873 | 1 | 77.txt | 21 | EHR đau khớp gối + phiếu CĐHA tim mạch |

Cộng: 12 block, +9101 ký tự phủ (**63.6% → 69.9%**), file có nhãn 83 → 87/100.
Block 77 và 91 đắt nhãn nhất vì mỗi phiếu xét nghiệm là một chuỗi
`TÊN_XÉT_NGHIỆM` + `KẾT_QUẢ_XÉT_NGHIỆM` xen kẽ — riêng hai block này đóng góp 91
nhãn, gần một nửa cả đợt.

Bẫy needle mới gặp (đều bắt được bằng `--occ` trước khi viết):

- **Khớp không phân biệt hoa/thường tạo khớp giả trong từ khác.** Block 77:
  `SA` khớp 4 lần nhưng 3 lần đầu nằm trong chữ "**sa**u", chỉ `[3]` là siêu âm.
  `Phù` khớp 7 lần, `[6]` là "**Phù** hợp" — không phải phù nề. Block 91: `pH`
  khớp 7 lần, 5 lần đầu nằm trong "**ph**ù"/"**Ph**ổi"/"ck/**ph**"; `HA` khớp 2
  lần, `[0]` nằm trong "NY**HA**".
- **Nhãn viết tắt 1 chữ cái phải đếm rất cẩn thận.** Block 91 dùng `M` làm tên
  phép đo mạch ("M: 82 ck/ph") — needle `M` khớp **26 lần** trong block. Phải in
  toàn bộ vị trí bằng regex để tìm ra index đúng là `15`. Cách an toàn hơn là
  chọn needle dài hơn, nhưng ở đây bề mặt thật đúng là một chữ `M`, mà đề yêu
  cầu giữ nguyên bề mặt ⇒ buộc phải dùng index.
- **Phiếu xét nghiệm lặp nguyên khối trong cùng block.** Block 91 in phiếu khí
  máu hai lần (mục "Khí máu" và mục "Diễn biến CLS") với giá trị y hệt ⇒ dùng
  `ALL` cho cả tên và giá trị, riêng tên phép đo lần hai đổi thành
  "Định lượng Lactat" nên khai riêng.

### Chỗ tự mâu thuẫn thứ tư (đã sửa)

`béo phì`: `GT[43]` (QA buồng trứng đa nang) gán `TRIỆU_CHỨNG`, còn `GT[27]` và
`GT[89-cũ]` gán `CHẨN_ĐOÁN` + `E66.9`. Đã đổi về `CHẨN_ĐOÁN` — E66.9 là mã ICD
riêng nên nó là bệnh, không phải dấu hiệu.

### Quy ước mới chốt trong đợt này

- **Liều thuốc không phải `KẾT_QUẢ_XÉT_NGHIỆM`** (đã có), và **nồng độ thuốc
  trong đoạn giảng cũng không phải** (block 80: "4 nanogam/mL" trong sữa mẹ,
  "200-300 microgam/ngày"). Chỉ giá trị xét nghiệm CỦA BỆNH NHÂN mới tính.
- **Nhận định định tính trên phiếu XN không phải `KẾT_QUẢ_XÉT_NGHIỆM`**: block
  89 có "NEUT% : 82.9 % (Tăng)" → gán `82.9 %`, bỏ `(Tăng)`. Block 77 có
  "protein (–), HC (–)" → gán tên phép đo, bỏ `(–)`.
- **Tổn thương đọc được trên phim/siêu âm là `CHẨN_ĐOÁN`** (tiền lệ GT[165], nay
  áp cho block 89 và 92): "xuất huyết dưới nhện vùng trán phải", "bóng tim to",
  "Hở hai lá vừa"… đều là chẩn đoán, còn tên phép chụp là `TÊN_XÉT_NGHIỆM`.
- **Thuốc cản quang không gán** (block 89: "có tiêm thuốc cản quang") — là
  phương tiện chẩn đoán hình ảnh, không phải thuốc điều trị, và không có tên
  hoạt chất.
- **Chất kích thích trong đời sống không gán** (block 85: "cà phê, chè, thuốc
  lá"; nhất quán với "Uống rượu 30 năm" ở GT[98]).
- **Vaccine của con vật không gán** (block 10: "chó chưa tiêm dại") — không phải
  thuốc bệnh nhân điều trị.
- **`TÊN_XÉT_NGHIỆM` nằm trong mục "Tiền sử" vẫn để assertions rỗng**, vì đề chỉ
  cho phép assertion trên `CHẨN_ĐOÁN`/`THUỐC`/`TRIỆU_CHỨNG` (block 9:
  "Sinh thiết nội mạc tử cung gần đây").

Mã tra đợt này — ICD: N04, N03.9, N05.9, N19, N20.0, D64.9, J02.9, K81.0, K82.8,
C73, K20, K22.1, K26.9, J84.9, M35.8, E66.9, D84.9, F39, F31.9, F41.9, F19.1,
N95.1, G47.0, F32.9, F43.9, H40.9, S06.2, S06.4, S06.5, S06.6, G93.0, Z95.5,
I34.0, I35.1, I36.1, I27.2, I42.0, I50.9, J81, K83.8, R93.1, A82.9, M25.5.
RxNorm: levothyroxine IN 10582, Bactrim BN 151399, doxycycline IN 3640,
clonidine IN 2599, Suboxone BN 352990, Klonopin BN 202585. Không có trong
RxNorm: `Berlthyrox` (biệt dược Việt), `corticoid` → `candidates` rỗng.

## Cả hai nguồn SHARE đã cạn — đo, không phỏng đoán (sau block 102/11)

Trước khi tiếp tục gán tay từng block, chạy lại hai phép quét để chắc là không
còn cách nào rẻ hơn:

1. **Block CHƯA gán là tiền tố của một block ĐÃ gán**, ngưỡng ≥120 ký tự NFC →
   **0 kết quả**.
2. **Cụm giữa 200 block chưa gán còn lại** (union-find trên tiền tố chung ≥120
   ký tự NFC) → **0 cụm**.

Cách đo cả hai: NFC-hoá toàn bộ text từng block, so tiền tố chung từng cặp, lấy
ngưỡng 120. Kết luận: mọi việc còn lại đều là block đơn, không còn đòn bẩy
SHARE. Từ đây tốc độ phủ ký tự sẽ chậm đi và tuyến tính theo số block gán.

## Đợt block đơn thứ hai (94 → 111): 15 block, 69.9% → 75.2%

| block | ký tự | ×lần | file | số nhãn | nội dung |
|---|---|---|---|---|---|
| 94 | 839 | 1 | 47.txt | 24 | đánh giá tại BV, hậu phẫu viêm phổi/rung nhĩ |
| 97 | 828 | 1 | 69.txt | 13 | EHR tự tử nhảy cầu, cắt cụt 2 chân |
| 100 | 798 | 1 | 40.txt | 35 | bệnh án viết tay XHTH do quá liều kháng vitamin K |
| 101 | 790 | 1 | 41.txt | 12 | phác đồ điều trị trứng cá + 2 dòng EHR đau ngực |
| 102 | 788 | 1 | 59.txt | 17 | CLS nhiễm khuẩn tiết niệu + cơ chế trứng cá |
| 11 | 387 | **2** | 16/20.txt | 4 | bài giảng đường lây bệnh dại |
| 12 | 379 | **2** | 12/48.txt | 2 | trả lời phụ huynh về dị tật tai của con |
| 104 | 749 | 1 | 2.txt | 11 | bài giảng dinh dưỡng/vận động trẻ Kawasaki |
| 105 | 745 | 1 | 81.txt | 7 | người hỏi tự kể hội chứng tăng đông |
| 2 | 248 | **3** | 41/59/60.txt | 2 | lời khuyên cuối bài tư vấn trứng cá |
| 106 | 743 | 1 | 81.txt | 10 | bác sĩ trả lời về thrombophilia |
| 107 | 741 | 1 | 38.txt | 18 | QA que cấy tránh thai + phiếu CLS của EHR CML |
| 109 | 711 | 1 | 92.txt | 21 | bệnh sử sốt cao/viêm tuỷ xương + 1 dòng trứng cá |
| 110 | 710 | 1 | 18.txt | 18 | đánh giá tại BV, EHR viêm túi mật cấp |
| 111 | 703 | 1 | 78.txt | 11 | 3 dòng khám hậu phẫu + bài giảng chảy máu mũi |

Cộng: 15 block, +10159 ký tự phủ (**69.9% → 75.2%**), file có nhãn 87 → 94/100.
Còn 191 block / 24.8% ký tự.

Bẫy needle mới trong đợt này:

- **Needle ngắn bị needle dài "ăn" mất lần xuất hiện.** Block 111 có `chảy máu`
  khớp 5 lần, nhưng 4 lần nằm trong các cụm dài hơn đã gán ("chảy máu mũi",
  "chảy máu ít", "chảy máu tái phát" ×2). Chỉ lần `[4]` là đứng riêng. Phải
  liệt kê từng vị trí kèm ngữ cảnh rồi trừ ra, nếu không sẽ gán trùng span và
  `check()` báo lỗi.
- **Tên thuốc dính liền do lỗi dịch chứa các tên con.** Block 109 có
  `vancozosynbactrim` = vanco + zosyn + bactrim dính liền; needle `zosyn` khớp
  2 lần và `[0]` nằm trong cụm dính đó. Gán cả cụm dính theo bề mặt (Zosyn
  BN 74170 cho lần `[1]` đứng riêng), giống tiền lệ `klonopinclonidine` ở
  block 84.
- **Cùng một bệnh xuất hiện hai lần với assertion KHÁC nhau trong cùng block.**
  Block 109: `hạ huyết áp` lần `[0]` thuộc lần nhập viện 2 tuần trước
  (`isHistorical`), lần `[1]` là tình trạng lúc vào hiện tại (không HIST). Block
  110 tương tự với `viêm túi mật` (lần trước: `isNegated`+`isHistorical`) và
  `viêm túi mật cấp` (hiện tại: rỗng). Không thể dùng `ALL` cho các trường hợp
  này — phải khai từng index.

### Quy ước mới chốt trong đợt này

- **Người thân tường thuật nhưng bệnh nhân vẫn là chủ thể ⇒ KHÔNG `isFamily`**
  (block 97: "Theo lời người nhà kể lại bệnh nhân…"). `isFamily` chỉ khi bệnh
  thuộc về thân nhân, không phải khi thân nhân là người kể.
- **Bệnh của con người hỏi ⇒ `isFamily`** (block 12: dị tật tai của bé; block
  106: "con bạn cũng có thể bị tắc mạch do cục máu đông").
- **Biến chứng nêu ra để PHÒNG NGỪA ⇒ `isNegated`** (block 106: "để tránh tình
  trạng sẩy thai, sinh non, tiền sản giật", "để tránh chảy máu khó cầm"). Cùng
  logic với "không có X".
- **Mô tả chức năng BÌNH THƯỜNG không gán** (block 12: "cấu trúc tai trong…
  phát triển tốt", "tai trái khỏe mạnh", "bé phản xạ được âm thanh"). Không
  phải triệu chứng cũng không phải chẩn đoán.
- **Dụng cụ/thủ thuật tránh thai không gán, chỉ gán hoạt chất** (block 107:
  "que cấy tránh thai", "Que tránh thai" → bỏ; tiền lệ GT[42] chỉ gán
  `Implanon`). Cùng nhóm: "que thử 2 vạch" (block 105) là que thử thai tại nhà.
- **Trạng thái sinh lý không gán**: "có thai", "thai nhi" (block 105/107).
- **Yếu tố khởi phát/hành vi không gán**: "hắt hơi mạnh", "ngoáy mũi" (block
  111), "hút thuốc lá thụ động", "môi trường ô nhiễm" (block 104).
- **Vi khuẩn phân lập được trên phiếu cấy là `CHẨN_ĐOÁN`** (block 110: `GPRs` →
  B96.8; tiền lệ `Vi khuẩn C. acne` → B96.8 ở block 102).
- **Bài giảng vẫn không có assertion, kể cả khi nói về "trẻ"** (block 104:
  Kawasaki) — không có bệnh nhân cụ thể thì không có ai để gắn `isFamily`.

Mã tra đợt này — ICD: I95.9, F10.1, F12.1, I26.9, A49.8, K92.2, Z95.2, L70.0,
L70.9, R07.2, N39.0, M86.9, M86.6, L73.8, B96.8, A82.9, Q17.2, Q16.1, M30.3,
D68.5, N96, O03, O60.1, O14.9, I74.9, E14, C92.1, A41.9, K80.2, K80.5, K81.0,
K81.9, K82.8, J18.9, J90, J98.1, I48. Không có trong `icd10_danh_muc.csv`
(phải thay bằng mã có thật hoặc để rỗng): `D68.51`, `R04.0` có nhưng là chảy
máu cam — block 111 gán `TRIỆU_CHỨNG` nên không cần mã.
RxNorm: Zosyn BN 74170, tretinoin IN 10753, gleevec BN 282386, Implanon 14584.
Không có: `thuốc chống đông` (nhóm), `kháng sinh tĩnh mạch`/`kháng sinh tại chỗ`
(nhóm), `thuốc kháng vitamin K` (nhóm) → `candidates` rỗng.

## Đợt block đơn thứ ba (13 → 129): 11 block, 75.2% → 78.4%

| block | ký tự | ×lần | file | số nhãn | nội dung |
|---|---|---|---|---|---|
| 13 | 351 | **2** | 39/47.txt | 6 | mục "Tiền sử bệnh" + tiền sử phẫu thuật đại tràng |
| 112 | 698 | 1 | 69.txt | 4 | câu hỏi bản dịch hỏng nặng về "nổi" mạn tính |
| 114 | 677 | 1 | 4.txt | 15 | "Tiền sử bệnh" EHR nôn ra máu (cùng BN block 38) |
| 115 | 675 | 1 | 85.txt | 22 | đánh giá tại BV: phiếu CLS song ngữ + CĐHA |
| 117 | 657 | 1 | 88.txt | 5 | tư vấn bé 14 tháng ra mồ hôi nhiều + 2 dòng CĐHA |
| 124 | 634 | 1 | 2.txt | 9 | bài giảng bệnh Kawasaki (cùng nguồn block 104) |
| 125 | 626 | 1 | 3.txt | 11 | bác sĩ giảng cảnh báo thuốc Vastarel/trimetazidin |
| 3 | 207 | **3** | 21/32/79.txt | 2 | câu hỏi người dùng về amyloidosis |
| 16 | 304 | **2** | 53/57.txt | 6 | mục "Hiện tại" liệt kê thuốc đang/đã dùng |
| 128 | 593 | 1 | 51.txt | 6 | trả lời mổ lại dây chằng chéo + 4 dòng y lệnh |
| 129 | 588 | 1 | 91.txt | 15 | "Tiền sử bệnh hiện tại" EHR khó thở/có đờm |

Cộng: 11 block, +6010 ký tự phủ (**75.2% → 78.4%**), file có nhãn 94 → 97/100.
Còn 180 block / 21.6% ký tự.

### Tự mâu thuẫn thứ năm: `dị ứng thời tiết`

Phát hiện khi grep toàn bộ chỗ dùng `FAM` để quyết định block 112. `GT[7]` gán
`("dị ứng do thời tiết", 0, SYM, [FAM, NEG], [])` còn `GT[47]` gán
`("dị ứng thời tiết", 0, DX, [FAM, NEG], [])` — **khác cả type lẫn để rỗng
candidates**. Ba block 7/47/112 cùng một nguồn dịch. Đã sửa cả hai về
`CHẨN_ĐOÁN` + `T78.4` ("Dị ứng, không xác định", đã xác nhận có trong
`icd10_danh_muc.csv`). Đây là lần thứ 5 quy trình "grep needle trước khi viết
nhãn mới" bắt được mâu thuẫn — giữ nguyên quy trình đó.

### `isFamily` cho BẠN của người hỏi — chốt theo tiền lệ

Block 112 nói về bạn của người hỏi. Comment ở `GT[149]` viết "người hỏi tự kể về
mình -> không isFamily", dễ bị đọc lầm là bạn cũng không tính. Grep ra `GT[7]`
("câu hỏi mày đay: nói về BẠN của người hỏi -> isFamily") và `GT[47]` ("Đề chỉ
có isFamily cho 'người khác' -> dùng FAM"). Kết luận: **bất kỳ ai không phải
người hỏi/bệnh nhân chính đều dùng `isFamily`**, kể cả bạn bè, vì đề không có
nhãn nào khác cho "người khác".

### Quy ước mới chốt trong đợt này

- **Tên chỉ số song ngữ "vi (en)" giữ nguyên cả cụm** làm bề mặt
  `TÊN_XÉT_NGHIỆM` (block 115: `hct (hematocrit)`, `ag (anion gap)`,
  `ua (urinalysis - tổng phân tích nước tiểu)`). Tiền lệ GT[63]
  `độ bão hòa oxy (SPO2)`.
- **Cả chuỗi kết quả nước tiểu là MỘT `KẾT_QUẢ_XÉT_NGHIỆM`**, không tách từng
  thành phần (block 115: "12 bạch cầu, không vi khuẩn, 1 hồng cầu, âm tính
  nitrite"). Tiền lệ GT[63] gán 1 nhãn VAL cho cả chuỗi tương tự.
- **Vi chất bị thiếu nêu trong ngữ cảnh dinh dưỡng KHÔNG gán `THUỐC`** (block
  117: calcium, sắt, kẽm). Chỉ gán khi là chế phẩm bổ sung đang dùng (tiền lệ
  GT[58] `Vitamin B12`). Bản thân "Thiếu một số vi chất" vẫn là `CHẨN_ĐOÁN`
  (E63.9, tiền lệ GT[28] "Thiếu canxi và vitamin").
- **Chẩn đoán nêu như một KHẢ NĂNG ("có thể là… Mắc một bệnh tiềm ẩn") vẫn
  gán**, không `isNegated` — chưa loại trừ thì không phải phủ định.
- **Tên người trong tên bệnh không gán** (block 124: "bác sĩ Tomisaku Kawasaki"
  là tên người, khác "Bệnh Kawasaki").
- **Liều thuốc gán chung vào bề mặt `THUỐC`**, không tách thành
  `KẾT_QUẢ_XÉT_NGHIỆM` (block 128: `aspirin 325mg`,
  `methylprednisolone 125mg`). Nhất quán với quy ước "liều thuốc không phải
  KẾT_QUẢ_XÉT_NGHIỆM".
- **Tên thuốc dính liền mà KHÔNG có lần xuất hiện độc lập ⇒ chỉ gán cụm dính**
  (block 128: `albuterolipratropium`; `albuterol`/`ipratropium` mỗi cái chỉ
  khớp 1 lần và lần đó nằm trong cụm dính). Khác block 109/84 nơi tên con còn
  xuất hiện riêng ở chỗ khác.
- **Tiêu đề "Tiền sử bệnh hiện tại" (dịch từ HPI) KHÔNG kích hoạt
  `isHistorical`** (block 129) — chỉ mục "Tiền sử bệnh"/"Các bệnh lý mạn tính"
  thuần mới kích hoạt. Trong cùng block 129, tiểu mục "Các diễn biến trước khi
  nhập viện" thì có (`khó nuốt` → HIST).
- **Danh sách "Hiện tại" liệt kê thuốc: đã ngừng/hết ⇒ `isNegated`, không
  `isHistorical`** (block 16). Tiền lệ GT[103] cùng bệnh nhân.

Bẫy needle mới: block 129 có `khó thở` khớp **5 lần** trong 588 ký tự với 3
assertion khác nhau (2 lần dương, 3 lần phủ định, trong đó 2 lần nằm trong cụm
dài hơn "khó thở khi gắng sức"/"khó thở tăng lên"). Phải liệt kê ngữ cảnh từng
vị trí; `ALL` hoàn toàn không dùng được. Cụm cuối phải dùng cú pháp ngoặc
`[[khó thở tăng lên khi xuất hiện  ]]Cơn nhịp nhanh` để trỏ đúng "Cơn nhịp
nhanh" (2 dấu cách do lỗi corpus).

Mã tra đợt này — ICD: C18.9, J44.9, E14, K70.3, K58, K26.9, K20, K22.1, K63.3,
A08.4, T78.4, S92.9, M86.9, I80.2, T81.8, E63.9, M30.3, I77.6, I51.4, I25.4,
I46.1, I21.9, I25.1, I50.9, G20, G21.9, I20.8, E85.9, S83.5, S83.2, R13.
Không có trong danh mục (đã kiểm): `I82.4` (dùng `I80.2`), `R11.0`, `R11.2`,
`K58.9` (dùng `K58`), `R13.1` (dùng `R13`).
RxNorm: omeprazole 7646, rosuvastatin IN 301542, Crestor 320864, carvedilol
20352, isosorbide 6057, insulin glargine IN 274783, torsemide 38413,
methylprednisolone IN 6902, aspirin 1191, ipratropium 7213.
Không có: `Vastarel`/`trimetazidin` (không lưu hành ở Mỹ),
`albuterolipratropium` (cụm dính), `lợi tiểu` (nhóm) → `candidates` rỗng.

## Đợt block đơn thứ tư (132 → 139): 10 block, 78.4% → 81.1%

Vẫn xếp theo `n_chars × n_occurences`. Cách đo: mỗi con số ở bảng phủ là một lần
chạy sạch `python3 src/gt_blocks.py`.

| block | ký tự | ×lần | file | số nhãn | nội dung |
|---|---|---|---|---|---|
| 132 | 577 | 1 | 22.txt | 26 | "3. Đánh giá tại bệnh viện" EHR tăng men gan/bilirubin (cùng nguồn GT[37], bản dịch khác) |
| 133 | 577 | 1 | 24.txt | 11 | mục "2/ Chẩn đoán" + y lệnh EHR viêm gan B cấp |
| 134 | 577 | 1 | 29.txt | 8 | QA bàn chân bẹt (con người hỏi) + 2 dòng CĐHA của EHR khác (cùng file GT[52]) |
| 135 | 564 | 1 | 2.txt | 5 | bài giảng "Nguyên nhân gây bệnh Kawasaki" (cùng nguồn GT[104]/GT[124]) |
| 136 | 563 | 1 | 40.txt | 12 | phiếu chỉ định xét nghiệm — toàn bộ là `TÊN_XÉT_NGHIỆM` |
| 17 | 276 | 2 | 42, 62.txt | 8 | "3. Đánh giá tại bệnh viện" EHR viêm phổi thùy dưới phải |
| 137 | 551 | 1 | 53.txt | 20 | bệnh án gốc tiếng Việt ĐTĐ typ 2 + THA (đứng ngay trước block 16 trong file) |
| 18 | 274 | 2 | 49, 65.txt | 2 | đuôi bài giảng điều trị rụng tóc — PUVA (cùng nguồn GT[76]) |
| 138 | 540 | 1 | 85.txt | 6 | "2. Lịch sử bệnh hiện tại" (cùng EHR GT[115]) + mẩu tư vấn chăm sóc môi |
| 139 | 533 | 1 | 13.txt | 2 | "2. Tiền sử bệnh hiện tại" + mẩu bài giảng dại (cùng nguồn GT[66]) |

Còn **170 block / 18.9% ký tự**.

### Block 137: bệnh án gốc tiếng Việt, không phải bản dịch

Khác hẳn phần lớn corpus. Không có lỗi dịch, viết theo mẫu bệnh án Việt: "Mạch:
89 lần/phút, HA: 180/100 mmHg", "XQ: Quai ĐMC vồng cao, chỉ số tim/LN < ½".
Hai hệ quả:

- **Viết tắt tiếng Việt vẫn là tên khái niệm**: `HA` → `TÊN_XÉT_NGHIỆM` (tiền lệ
  GT[91] "đo HA là 160/70 mmHg"), `XQ` → `TÊN_XÉT_NGHIỆM`, `ĐTD typ II` →
  `CHẨN_ĐOÁN` E11. Giữ nguyên bề mặt viết tắt, không bung ra dạng đầy đủ (đề
  chấm WER trên đúng chuỗi trong văn bản).
- **`chỉ số tim/LN` + `< ½` là cặp tên phép đo / kết quả**, dù kết quả không
  phải số thuần. Đây là ngoại lệ hẹp: nó là một *biểu thức so sánh định lượng*,
  khác "bình thường"/"(Tăng)" là nhận định định tính (không gán).
- Hội chứng "4 nhiều" của ĐTĐ tách thành 4 nhãn `TRIỆU_CHỨNG` riêng: `Ăn nhiều`,
  `khát nước`, `uống nhiều`, `đi tiểu nhiều`. Không gộp thành một cụm vì trong
  văn bản chúng phân tách bằng dấu phẩy như các mục độc lập.
- Phát hiện đọc trên phim → `CHẨN_ĐOÁN`: `Quai ĐMC vồng cao` → I70.0 (xơ vữa
  ĐM chủ), `rốn phổi đậm` → R91 (bất thường CĐHA ở phổi).

### Block 18/139: giữ đúng quyết định của block cùng nguồn, kể cả quyết định KHÔNG gán

Block 139 là phần giữa của block 66 (bài giảng bệnh dại) ghép sau 2 dòng EHR đau
ngực. Ở GT[66] tôi đã quyết định **không** gán `vi rút dại`, `vết cắn`,
`vết thương` — tác nhân và đường vào của bệnh trong một bài giảng chung không
phải triệu chứng của bệnh nhân nào. Block 139 giữ đúng như vậy, nên chỉ có 2
nhãn (2 dòng EHR). Nếu gán thêm ở đây thì cùng một câu văn sẽ có nhãn khác nhau
ở 2 file → tự mâu thuẫn, và với cách chấm ghép theo overlap thì một trong hai
chắc chắn sai.

Block 18 tương tự với GT[76] (cùng bài rụng tóc): `PUVA`/`psoralen` → `THUỐC`
với `candidates` rỗng, theo đúng tiền lệ `hóa trị`/`liệu pháp lợi tiểu` (liệu
pháp thuốc không có tên hoạt chất tra được). RxNorm có `methoxsalen` (IN 6854)
nhưng **không có** `psoralen` — mà "psoralen" là tên nhóm, không phải hoạt chất
cụ thể, nên để rỗng chứ không map sang methoxsalen.

### Quy ước mới chốt trong đợt này

- **Chuỗi kết quả nước tiểu là MỘT `KẾT_QUẢ_XÉT_NGHIỆM`**, không tách từng mục
  (block 115: "12 bạch cầu, không vi khuẩn, 1 hồng cầu, âm tính nitrite"; tiền
  lệ GT[63]).
- **Tên chỉ số song ngữ "vi (en)" giữ nguyên cả cụm có ngoặc làm bề mặt** (block
  115 `hct (hematocrit)`, block 136 `Khí máu động mạch (23 thông số)`; tiền lệ
  GT[62]/GT[63]).
- **Tiêu đề nhóm trong phiếu xét nghiệm không gán** ("Huyết học & Đông máu:",
  "Men gan:") — chúng không phải tên một xét nghiệm cụ thể. Cụm mô tả phương
  pháp/thiết bị cũng không gán ("bằng máy tự động", "Phương pháp Clauss trực
  tiếp").
- **"đang chờ kết quả" không gán `KẾT_QUẢ_XÉT_NGHIỆM`** (block 132
  `ceruloplasmin`) — chưa có kết quả thì không có khái niệm kết quả. Tên xét
  nghiệm vẫn gán.
- **Lỗi dịch lặp cụm vẫn gán đủ số lần** (block 132: "âm tính âm tính" → 2 nhãn;
  `túi mật giãn nở rõ rệt` + `túi mật giãn`). Bề mặt là bề mặt.
- **`ercp` xuất hiện cả ở dòng kết quả và dòng "Thủ thuật thực hiện" → gán cả 2
  lần** dưới `TÊN_XÉT_NGHIỆM` (ERCP vừa là thủ thuật vừa là thăm dò chẩn đoán;
  chọn gán vì có kết quả đọc kèm).
- **Yếu tố nguy cơ dịch tễ/chủng tộc/môi trường không gán** (block 135: "Yếu tố
  chủng tộc", "Trẻ gốc Á", "thay đổi khí hậu, chất độc trong không khí"). Nhất
  quán với "hút thuốc lá thụ động"/"môi trường ô nhiễm" ở GT[104] cùng nguồn.
- **Đuôi block bị cắt giữa tên chẩn đoán vẫn gán theo phần còn lại** (block 133:
  mất chữ "Viêm gan" ở đầu, còn "cấp tính do virus B thể thông thường điển hình
  mức độ nặng giai đoạn toàn phát" → B16.9). Ghép theo overlap nên phần trùng
  vẫn ăn điểm.

### Bẫy needle đợt này

- Block 132: `âm tính` khớp **4 lần** (1 lần là kết quả bảng viêm gan, 1 cặp lặp
  do lỗi dịch, 1 lần ở dòng đảo trật tự "- âm tính chụp hida"); `túi mật giãn`
  2 lần với `[0]` nằm trong cụm dài hơn; `ercp` 2 lần.
- Block 124: `Kawasaki` 2 lần, `[1]` là tên người ("bác sĩ Tomisaku Kawasaki").
- Block 18: `UVA` khớp **3 lần** nhưng 2 lần nằm bên trong chữ `PUVA` — nếu gán
  `UVA` sẽ tạo nhãn lồng nhau. Đã bỏ (`UVA` là tia, không phải thuốc).
- Block 138: `đau bàn chân phải` 2 lần (lý do nhập viện + mục triệu chứng), dùng
  `ALL` được vì cùng assertion.

### Mã tra đợt này

ICD đã xác nhận có trong `icd10_danh_muc.csv`: R17.9, K80.5, B16.9, Q66.5,
I82.9, I26.9, S83.2, A49.9, B34.9, D89.9, J18.1, E11, I70.0, R91, N12, J40,
A82.9, T81.8.
Kiểm nhưng **không có** trong danh mục (không được dùng): `K80.9`, `R80.9`,
`R11.0`, `R11.2`, `K58.9`, `R13.1`, `I82.4`.
RxNorm: glucose IN 4850, vitamin B complex IN 11251, vitamin C 1151,
methoxsalen IN 6854 (tra để đối chiếu, không dùng).
Không tìm thấy → `candidates` rỗng: `Philpovin`, `Fortex` (biệt dược VN),
`psoralen` (tên nhóm; chỉ có methoxsalen là hoạt chất cụ thể).

## Đợt 5 (140 → 19): 5 block, 81.1% → 82.3%

| block | ký tự | ×lần | file | số nhãn | nội dung |
|---|---|---|---|---|---|
| 140 | 514 | 1 | 8.txt | 13 | bài giảng Kawasaki: biến chứng + tiêu chuẩn chẩn đoán |
| 141 | 512 | 1 | 71.txt | 5 | bản gần trùng đuôi block 97: tự tử nhảy cầu, cắt cụt 2 chân |
| 142 | 507 | 1 | 3.txt | 11 | "3. Đánh giá tại bệnh viện" của EHR đột quỵ (cùng file GT[29]) |
| 143 | 507 | 1 | 89.txt | 15 | "3. Đánh giá tại bệnh viện": sinh hiệu bị dịch lặp nguyên khối |
| 19 | 263 | 2 | 37, 48.txt | 1 | đuôi trả lời của BS về nghe kém một bên ở trẻ 2 tuổi |

### Block 141/142: block "cùng bệnh án" thì copy nguyên quyết định, kể cả số lần

Block 141 là **đuôi của block 97** ở một file khác (71.txt thay vì 69.txt), thêm
tiền tố `Câu hỏi từ người dùng:` và **thiếu** dòng `Dùng kháng sinh tĩnh mạch.`
→ giữ y nguyên 5 nhãn trùng của GT[97], bỏ nhãn `kháng sinh tĩnh mạch` vì câu đó
không tồn tại trong block này. Đây là lý do không dùng `SHARE`: 141 không phải
tiền tố của 97 mà là *hậu tố*, `SHARE` chỉ nhận tiền tố.

Điểm dễ sai: `tổn thương chi dưới` ở block 97 dùng `ALL` (3 lần), ở block 141
chỉ còn **1 lần** → phải viết `0` chứ không copy `ALL` (copy `ALL` vẫn chạy
nhưng ý nghĩa khác, và nếu block sau này đổi thì lệch).

Block 142 cùng bệnh án với GT[29] (cùng file 3.txt), nên `âm tính` (2 lần) **vẫn
không gán** — GT[29] đã ghi rõ lý do trong comment (kết quả bằng chữ, không có
trị số). Nếu ở đây gán mà ở block 29 không gán thì cùng một bệnh án lại có 2
chuẩn khác nhau, và với ghép overlap thì một trong hai chắc chắn sai.

### Block 143: bản dịch lặp nguyên khối cụm sinh hiệu, dùng TỪ KHÁC nhau

Nguyên văn: `Nhiệt độ 36.7°c, Huyết áp 139/68 mmhg, Mạch 67 lần/phút, Nhịp thở
16 lần/phút, SpO2 100% (không thở oxy) (nhiệt độ 36.7°c, huyết áp 139/68 mmhg,
nhịp tim 67 lần/phút, nhịp thở 16 lần/phút, độ bão hòa oxy 100% trên khí trời)`

Hệ quả cho việc gán:
- **Trị số giống nhau y nguyên → khớp 2 lần → dùng `ALL`** (`36.7°c`,
  `139/68 mmhg`, `67 lần/phút`, `16 lần/phút`, `100%`).
- **Tên phép đo bị dịch khác từ → mỗi bề mặt chỉ 1 lần** (`Mạch` vs `nhịp tim`,
  `SpO2` vs `độ bão hòa oxy`) → phải khai 4 nhãn riêng với `nth = 0`, không dùng
  `ALL`. `Nhiệt độ`/`Huyết áp`/`Nhịp thở` thì lặp đúng chữ nên `ALL` được.
- Bộ đối sánh needle **không phân biệt chữ hoa/thường** (`Nhiệt độ` và
  `nhiệt độ` trả về cùng vị trí) → đây là lý do `Nhiệt độ` ALL bắt được cả bản
  trong ngoặc.
- `ống nội khí quản (nghiệm pháp gắng sức trên máy chạy bộ)`: ống nội khí quản là
  dụng cụ → không gán; `nghiệm pháp gắng sức` có tiền lệ GT[76] → `TÊN_XÉT_NGHIỆM`.

### Block 19: bối cảnh isFamily nhưng không được gán assertion

Bệnh nhân là **con của người hỏi** → theo quy ước phải `isFamily`. Nhưng nhãn duy
nhất trong block là `đo thính lực` = `TÊN_XÉT_NGHIỆM`, mà đề chỉ cho assertion với
`CHẨN_ĐOÁN`/`THUỐC`/`TRIỆU_CHỨNG` (hàm `check()` chặn) → `assertions` rỗng.
Không gán: `chuyên khoa Tai mũi họng nhi` (chuyên khoa), `chăm sóc bé như bình
thường` (mô tả bình thường).

## Đợt 6: gán TRỌN file 1.txt (17 block) — 82.3% → 84.6%

Đổi cách chọn việc: thay vì lấy block to nhất, lấy **cả một file chưa gán block
nào**. `1.txt` là **một bài phổ biến kiến thức duy nhất** "THIẾU MEN G6PD là gì?"
bị cắt thành 17 block (4450 ký tự = 2.3% toàn corpus), trước đợt này chưa gán
block nào → file này đang được dự đoán rỗng hoàn toàn.

Vì sao gán cả file một lượt tốt hơn gán từng block: cụm `thiếu men G6PD` xuất
hiện ở **13/17 block**. Nếu gán rải rác qua nhiều đợt thì gần như chắc chắn sẽ
có block gán `D55.0`, block khác gán rỗng, block khác lại gán `TRIỆU_CHỨNG`.

17 block: 317, 207, 173, 212, 205, 200, 298, 196, 214, 244, 251, 174, 234, 328,
159, 150, 210 → tổng **59 nhãn**. File 1.txt từ 0 nhãn lên 59 nhãn; số file có
nhãn: 97 → **98**.

### Quy ước chốt cho cả file

- Bài giảng, không bệnh nhân cụ thể → **không assertion nào** (tiền lệ GT[76],
  GT[104], GT[124], GT[135]).
- `thiếu men G6PD` mọi biến thể chữ hoa/thường → `CHẨN_ĐOÁN` + **D55.0**
  ("Thiếu máu do thiếu men glucose-6-phosphate dehydrogenase [G6PD]"). Các biến
  thể diễn đạt cũng cùng mã: `thiếu hụt men G6PD`, `thiếu máu do tan huyết`,
  `thiếu máu tan huyết`, `bệnh di truyền lặn liên kết với nhiễm sắc thể X`.
- `thiếu máu` đứng một mình (không nói do tan huyết) → **D64.9** (tiền lệ GT[58],
  GT[91]).
- **Cơ chế bệnh không gán**: "hồng cầu bị phá hủy", "tác nhân oxy hóa",
  "enzyme", "gen lặn bất thường", "nhiễm sắc thể giới tính". Cùng logic GT[66]
  không gán "vi rút dại" trong bài giảng.
- `đột biến gen G6PD tại vị trí Xq28` → có gán `CHẨN_ĐOÁN` nhưng `candidates`
  **rỗng**: ICD-10 không có mã cho đột biến gen cụ thể (kiểm mục Q95.x chỉ có
  "đột biến cấu trúc nhiễm sắc thể", khác nghĩa).
- **"Khi thiếu men này" không gán** — nhắc lại bệnh nhưng không nêu tên (cùng
  logic "các xét nghiệm này" không gán). Xuất hiện ở block 212 và 244.
- `tan huyết` / `vàng da` / `vàng da nặng` / `vàng da sơ sinh` → `TRIỆU_CHỨNG`
  (tiền lệ GT[37] `vàng da`/`vàng mắt`).
- Biến chứng thần kinh gán `CHẨN_ĐOÁN`: `bại não` G80.9, `chậm phát triển trí
  tuệ` F79, `Rối loạn vận động` G25.9, `suy thận cấp` N17.9. `tổn thương thần
  kinh` gán nhưng `candidates` rỗng (mô tả chung, không có mã riêng).
- **Thủ thuật/lời khuyên không gán**: "lấy máu khô ở gót chân", "Không nên hiến
  máu", "gói chăm sóc thai sản".
- **Hóa chất gây tan máu không phải thuốc điều trị → không gán**: "băng phiến",
  "long não", "đậu tằm". Cùng logic yếu tố môi trường ở GT[104].
- **"thuốc nam, thuốc đông y" không gán** — nhắc chung, không có tên thuốc (tiền
  lệ "điều trị nhiều thuốc", "Thuốc kê đơn (tên không được chỉ định)").
- Block 298 là ca **ghép nhầm**: `3.  Đánh giá tại bệnh viện • Tim đập nhanh,
  khó thở\n • Vàng da, vàng mắt` — tiêu đề mục "3. Đánh giá tại bệnh viện" của
  một bệnh án khác bị chèn vào giữa danh sách gạch đầu dòng của bài G6PD. Vẫn
  gán 4 triệu chứng theo đúng bề mặt, bỏ tiêu đề.

### Bẫy needle đợt này

- Block 317: `Thiếu men G6PD` khớp **2 lần** vì matcher không phân biệt hoa
  thường — `[0]` là tiêu đề chữ hoa `THIẾU MEN G6PD`. Phải khai `THIẾU MEN
  G6PD` `[0]` rồi `Thiếu men G6PD` `[1]`, không thì hai nhãn đè nhau.
- Block 205: `xét nghiệm thiếu men G6PD` (TÊN_XÉT_NGHIỆM) **chứa** lần `[0]` của
  `thiếu men G6PD` → lần CHẨN_ĐOÁN phải là `[1]`.
- Block 196: `thiếu máu do tan huyết` chứa lần `[0]` của `thiếu máu` → lần
  D64.9 là `[1]`; `vàng da vàng mắt` chứa lần `[0]` của `vàng da` → lần sau là `[1]`.
- Block 159: `Nhiễm khuẩn` khớp 2 lần, `[1]` nằm trong `nhiễm khuẩn tiết niệu`
  → chỉ gán `[0]` riêng, `[1]` đã nằm trong nhãn dài hơn.
- Block 174: `tan huyết` 2 lần, `[0]` nằm trong `thiếu máu tan huyết` → gán `[1]`.
- Block 210: `xét nghiệm sàng lọc` 2 lần, `[0]` nằm trong `xét nghiệm sàng lọc
  trước sinh và sau sinh` → gán `[1]`.
- Block 159 có **5 run mask khác nhau** (7, 10, 11, 8 sao) và một số run lặp 2
  lần → phải đếm cẩn thận: `*******` ×2, `**********` ×2, `***********` ×2,
  `********` ×1.

### Mã tra đợt này

ICD xác nhận có: D55.0, D64.9, N17.9, G80.9, F79, G25.9, A49.9, B34.9, N39.0,
I25.4, I25.1, I25.9, I21.9, I51.4, I31.3, K30, R50.9, H10.9, I95.9, I26.9,
F32.9, A49.8, M30.3.
RxNorm: **vitamin K = IN 11258** (ban đầu viết 11256 — sai, 11256 là vitamin E;
đã sửa sau khi tra `RXNCONSO.RRF`). Cũng có `vitamin K1` 8308, `vitamin K2` 42781
nhưng văn bản chỉ ghi "Vitamin K" → dùng 11258.

## Đợt 7: gán TRỌN file 26.txt (13 block) — 84.6% → 85.9%

Tiếp tục cách chọn việc của đợt 6: lấy file chưa gán block nào. Sau `1.txt`, hai
file duy nhất còn **0 nhãn** là `26.txt` (2335c) và `87.txt` (1453c) → làm 26.txt.

`26.txt` là bài giảng "BỆNH MẠCH VÀNH (Coronary Artery Disease – CAD)" bị cắt
thành 13 block: 299, 197, 232, 291, 233, 240, 308, 249, 268, 322, 182, 172, 277
→ **61 nhãn**. Đo bằng `python3 src/gt_blocks.py` rồi đọc `data/gt_block/26.json`:
file này từ 0 lên **61 entity**; số file có nhãn 98 → **99** (chỉ còn `87.txt`
rỗng); block đã gán 184 → 197; phủ ký tự 84.63% → **85.86%**.

Điểm khác đợt 6: bài giảng này bị **ghép 2 block bệnh án lạ vào giữa** (block 182
và nửa đầu block 172) — một ca viêm tụy + rung nhĩ, không liên quan gì mạch vành.
Nên trong cùng một file có hai chế độ assertion trái ngược nhau, phải xử lý riêng:

- Phần bài giảng (11 block + đuôi block 172): **không assertion nào**.
- Block 182 nằm dưới `1. Tiền sử bệnh` / `Bệnh lý mãn tính` / `Thuốc trước khi
  nhập viện` → **toàn bộ `isHistorical`** (tiền lệ GT[9], GT[14], GT[20], GT[198]).
- Block 172 mở đầu bằng `2. Tiền sử bệnh hiện tại` = HPI → **KHÔNG**
  `isHistorical` (tiền lệ GT[129], GT[139]), chỉ dòng có ghi `(lần nhập viện
  trước)` mới `isHistorical` (tiền lệ GT[110]).

### Quy ước chốt cho cả file

- **Tiêu đề mục không gán**: "Nguyên nhân chính", "Yếu tố nguy cơ", "Triệu chứng
  lâm sàng", "Các thể lâm sàng", "Lâm sàng", "4. Chẩn đoán", "Dự phòng thứ phát".
  Nhưng tiêu đề **là tên bệnh** thì vẫn gán ("Đau thắt ngực", "Đau thắt ngực ổn
  định", "Hội chứng vành cấp") — tiền lệ GT[140].
- **Bước cơ chế bệnh sinh không gán**: "Lắng đọng lipid", "hình thành mảng xơ
  vữa", "Mảng xơ vữa to dần", "Nứt vỡ mảng xơ vữa". Đây là quy ước đã chốt từ
  file 1.txt (không gán "hồng cầu bị phá hủy", "tác nhân oxy hóa").
  **Nhưng** các *trạng thái bệnh lý* nằm trong cùng chuỗi đó vẫn gán vì chúng là
  khái niệm chẩn đoán độc lập: `hẹp lòng mạch` I25.1, `huyết khối` I24.0,
  `tắc mạch cấp` I74.9.
- **Mô tả cơn đau gán TRIỆU_CHỨNG, đáp ứng/thời gian không gán.** Gán: `sau
  xương ức` (vị trí), `đè nặng, bóp nghẹt, thắt chặt` (tính chất, cả cụm 1 nhãn),
  `vai trái – cánh tay trái – cổ – hàm dưới` (hướng lan), `Đau dữ dội, kéo dài`.
  Không gán: "Thời gian: vài phút", "Giảm khi nghỉ", "Không đỡ khi nghỉ", "Xảy ra
  khi gắng sức". Căn cứ: GT[73] gán "nhói"/"lan xuống cánh tay trái" nhưng không
  gán "không giảm khi dùng bất kỳ thuốc nào".
- **Yếu tố nguy cơ / lời khuyên dự phòng**: gán tên BỆNH + tên XÉT NGHIỆM + tên
  THUỐC; bỏ hành vi và nhân khẩu học. Không gán: "Tuổi cao", "Nam giới", "ít vận
  động", "Tập thể dục ≥ 150 phút/tuần", "Giữ cân nặng hợp lý", "Uống thuốc đều",
  "Tái khám định kỳ", "yếu tố nguy cơ", "hay gặp ở nữ, người già".
  Hai ngoại lệ có tiền lệ rõ: `Hút thuốc lá` → TRIỆU_CHỨNG (GT[28] cùng bề mặt,
  cùng loại — khác "hút thuốc lá thụ động" của GT[104] là yếu tố môi trường);
  `stress`/`Stress kéo dài` → CHẨN_ĐOÁN F43.9 (GT[85]).
- `Không hút thuốc` (dòng lời khuyên dự phòng) → gán `hút thuốc` + **isNegated**,
  theo tiền lệ GT[106] gán isNegated cho khái niệm nêu ra để PHÒNG.
- `Tiền sử gia đình bệnh tim mạch sớm` → chỉ lấy tên bệnh `bệnh tim mạch sớm`
  (I51.6) làm bề mặt, **không** `isFamily`: bài giảng không có bệnh nhân cụ thể
  nên không có "thân nhân của ai" (nhất quán với quy ước không assertion cho bài
  giảng). Tiền lệ lấy tên bệnh trong cụm mô tả: GT[14].
- `(Coronary Artery Disease – CAD)` — tên tiếng Anh trong ngoặc ngay sau nhãn
  tiếng Việt → phần diễn giải, không gán riêng (tiền lệ GT[207] với
  "(Glucose-6-phosphate dehydrogenase)").
- Thủ thuật không gán: `phẫu thuật cắt bỏ tuyến tiền liệt` (2 lần) → chỉ lấy
  chẩn đoán trong ngoặc `u ác của tuyến tiền liệt` (tiền lệ GT[14], GT[145]).

### Bẫy đếm lần xuất hiện (đo bằng `--occ` trước khi viết)

Matcher **không phân biệt hoa/thường**, và đây là bài giảng nên cụm khóa lặp rất
nhiều. Đo trước, không đoán:

- Block 299: `BỆNH MẠCH VÀNH` khớp **2 lần** — `[0]` là tiêu đề chữ hoa, `[1]` là
  "Bệnh mạch vành là gì?". Phải khai 2 dòng riêng với 2 bề mặt khác nhau
  (`BỆNH MẠCH VÀNH` `[0]` + `Bệnh mạch vành` `[1]`) để giữ đúng bề mặt as-written.
- Block 232: `mảng xơ vữa` khớp **3 lần** — cả 3 đều là bước cơ chế → không gán,
  nên không phải xử lý; nhưng nếu gán thì đã sai vì phải dùng `ALL`.
- Block 182: `rung nhĩ` **2 lần** (dòng bệnh mạn + "(cho rung nhĩ)") →
  dùng `ALL`. `u ác của tuyến tiền liệt` **2 lần** → `ALL`. `tuyến tiền liệt`
  khớp **4 lần** nhưng cả 4 đều nằm trong nhãn dài hơn → không khai riêng.
- Block 172: `sốt` **2 lần** — `[0]` = "Lý do nhập viện: sốt", `[1]` nằm trong
  `sốt nhẹ đến 38.3°C` (đã có nhãn dài) → chỉ khai `[0]`. `đau bụng` **2 lần** —
  `[1]` nằm trong `đau bụng trên` → chỉ khai `[0]`, còn `đau bụng trên` khai
  riêng vì nó mang `isHistorical` khác với `đau bụng`.
- Block 197: nhãn `hẹp hoặc tắc các động mạch vành` đã chứa lần duy nhất của
  `động mạch vành` → không khai riêng.
- Block 249: 2 nhãn `Nhồi máu cơ tim ST chênh` + `Nhồi máu không ST chênh` đã
  chứa cả 2 lần "Nhồi máu" → không khai riêng.

### Mã tra đợt này

Tra ICD bằng `load_icd()` (đọc `entries[code]["vi"]`), tra RxNorm bằng
`awk -F'|'` trên `data/raw/rxnorm/RXNCONSO.RRF`.

ICD xác nhận có + tên nguyên văn dùng để chọn mã:

- `I25.9` Bệnh tim thiếu máu cục bộ mạn tính, không xác định → `Bệnh mạch vành`
  (tiền lệ GT[55]), `giảm tưới máu cơ tim`, `thiếu oxy cơ tim`.
- `I25.1` Bệnh tim mạch do xơ vữa động mạch → `hẹp hoặc tắc các động mạch vành`
  (tiền lệ GT[124]/GT[140] "hẹp tắc mạch vành"), `Xơ vữa động mạch vành`,
  `hẹp lòng mạch`.
- `I70.9` Xơ vữa động mạch toàn thể/không xác định → `xơ vữa động mạch`.
- `I20.9` Cơn đau thắt ngực, không xác định → `đau thắt ngực` (tiền lệ GT[55]).
- `I20.8` Cơn đau thắt ngực thể khác → `Đau thắt ngực ổn định` (tiền lệ GT[125]
  cùng bề mặt).
- `I20.0` Cơn đau thắt ngực không ổn định → `Đau thắt ngực không ổn định`.
- `I21.9` Nhồi máu cơ tim cấp tính, không xác định → `nhồi máu cơ tim` (GT[124]).
- `I21.3` NMCT xuyên thành cấp tính ở vị trí không xác định → `Nhồi máu cơ tim
  ST chênh` (STEMI = xuyên thành).
- `I21.4` NMCT dưới nội tâm mạc cấp tính → `Nhồi máu không ST chênh` (NSTEMI).
- `I24.9` Bệnh tim do thiếu máu cục bộ cấp tính, không xác định → `Hội chứng
  vành cấp`.
- `I24.0` Huyết khối mạch vành không gây NMCT → `huyết khối`. **Khác tiền lệ**
  GT[52]/GT[134] dùng `I82.9` cho cùng bề mặt `huyết khối`: ở đó là huyết khối
  tĩnh mạch ("không ghi nhận huyết khối" trong bệnh án), còn ở đây bối cảnh là
  chuỗi xơ vữa **mạch vành**. I82.9 ghi rõ "không xác định tĩnh mạch" nên không
  dùng được cho mạch vành → chọn theo bối cảnh, không theo bề mặt.
- `I74.9` Thuyên tắc/huyết khối động mạch, không xác định → `tắc mạch cấp`.
- `I50.9` Suy tim, không xác định → `suy tim` (GT[124]).
- `I46.1` Đột tử do tim, như đã mô tả → `đột tử` (GT[124]).
- `I51.6` Bệnh tim mạch, không xác định → `bệnh tim mạch sớm`.
- `I10` Bệnh tăng huyết áp vô căn (nguyên phát) → `Tăng huyết áp`.
- `E14` Đái tháo đường không xác định → `Đái tháo đường`, `ĐTĐ` (viết tắt vẫn là
  tên bệnh; văn bản không nói typ nên không dùng E11 — tiền lệ GT[14]/GT[20]).
- `E78.5` Tăng lipid máu, không xác định → `Rối loạn lipid máu`.
- `E66.9` Bệnh béo phì, không xác định → `Béo phì` (tiền lệ GT[4]).
- `F43.9` Phản ứng với căng thẳng trầm trọng, không xác định → `Stress kéo dài`,
  `stress` (tiền lệ GT[85]).
- `F31.8` **Rối loạn cảm xúc lưỡng cực khác** → trùng **nguyên văn** bề mặt trong
  block 182, nên chọn F31.8 chứ không phải F31.9 ("không xác định").
- `C61` U ác tính ở tuyến tiền liệt → `u ác của tuyến tiền liệt` (GT[14]).
- `K85` Viêm tụy cấp tính → `viêm tụy`: văn bản ghi "nhập viện gần đây vìviêm
  tụy" (dịch dính chữ), nhập viện cấp → K85 chứ không phải K86.1 (mạn).
- `I48.9` Rung nhĩ và/hoặc cuồng nhĩ, không xác định → `rung nhĩ`.

RxNorm:

- `nitroglycerin` = **4917** (tiền lệ GT[55]).
- `eliquis` = **1364436** (BN Eliquis). Thành phần apixaban là IN **1364430** —
  đã tra lại, không phải 136430 như ghi nháp lúc đầu. Chọn mã **BN** theo tiền lệ
  biệt dược đã có: tylenol 202433, klonopin 202585, bactrim 151399.

### Hai quyết định có rủi ro, ghi rõ để rà lại sau

1. **Block 233 `Rối loạn lipid máu` → E78.5, không phải E78.9.** Dữ liệu cũ tự
   mâu thuẫn: GT[26] dòng 160 dùng `E78.5`, GT[116] dòng 2396 dùng `E78.9` cho
   cùng khái niệm. Chốt **E78.5** làm chuẩn vì "Tăng lipid máu, không xác định"
   sát nghĩa lâm sàng hơn "Rối loạn chuyển hóa lipoprotein, không xác định", và
   GT[26] là bản gán sớm hơn đã dùng nhiều lần. **Chưa sửa GT[116]** — cần một
   lượt rà thống nhất riêng cho các cặp mã mâu thuẫn, không sửa lẻ giữa đợt.
2. **Block 277: gán `1,8 mmol/L` và `70 mg/dL` là KẾT_QUẢ_XÉT_NGHIỆM** dù chúng
   là **ngưỡng mục tiêu** ("Kiểm soát LDL < 1,8 mmol/L (hoặc <70 mg/dL)"), không
   phải kết quả đo của bệnh nhân. Lý do gán: đúng dạng "số + đơn vị" gắn với tên
   xét nghiệm, và đề không phân biệt ngưỡng với kết quả. Rủi ro: nếu ground truth
   chỉ coi kết quả đo là KẾT_QUẢ_XÉT_NGHIỆM thì 2 nhãn này thành sai loại — mà
   sai loại bị **tính 2 lần và 0 điểm cả 3 metric**. Đổi lại nếu bỏ thì mất
   recall. Vẫn gán vì recall là toàn bộ điểm, nhưng đây là chỗ đáng đo lại khi có
   tập validation.

### Còn lại sau đợt 7

`87.txt` là file duy nhất còn 0 nhãn (1453c, 5 block: 158, 162, 176, 288, 297)
→ làm tiếp ngay. Sau đó theo hàng đợi số ký tự chưa gán: 2.txt (1764c),
8.txt (1228c), 36.txt (944c), 10.txt (936c), 41.txt (931c), 12.txt (868c),
91.txt (824c), 18.txt (821c), 78.txt (813c), 13.txt (812c), 88.txt (788c),
5.txt (777c).

## Đợt 8: gán TRỌN file 87.txt (5 block) — 85.9% → 86.6%, **100/100 file có nhãn**

`87.txt` là file cuối cùng còn 0 nhãn (1453c, 5 block: 158, 162, 176, 288, 297)
→ **39 nhãn**. Mốc đáng ghi: sau đợt này **cả 100/100 file đều có ít nhất 1 nhãn**
(trước đó 99/100). Đo bằng `python3 src/gt_blocks.py`: block 197 → 202, phủ ký tự
85.86% → **86.63%**, entity 2458 → 2496, chiếu ra 100 file / 2962 entity.

Nội dung: **một bệnh án viết tay** BN nam 74 tuổi vào viện vì đau ngực, chẩn đoán
ra viện "Cơn đau thắt ngực không ổn định - bệnh tăng HA vô căn(nguyên phát)".
Thứ tự đọc đúng của bệnh án: 162 (hỏi bệnh + khám) → 158 (phiếu chỉ định xét
nghiệm) → 288 (chẩn đoán + đầu mục thuốc) → 297 (dòng thuốc bị mask). Block 176
là **mẩu bệnh án béo phì khác** bị ghép vào (cùng nguồn với đoạn đầu block 51).

### Quy ước chốt cho cả file

- Bệnh án đang diễn ra, bệnh nhân là chính chủ → **không assertion**, trừ:
  các dòng "Không X" → `isNegated`, và mục "Các sự kiện trước khi nhập viện" của
  block 176 → `isHistorical` (tiền lệ GT[129]).
- Mục `TS; khỏe mạnh` (tiền sử) **không có gì để gán** — "khỏe mạnh" là mô tả
  bình thường (tiền lệ GT[110] không gán "tai trái khỏe mạnh").
- Dòng khám bình thường: **có tiền lệ gán** nên vẫn gán để nhất quán —
  `Da niêm mạc hồng` (GT[91]/GT[131]), `Tim nhịp đều` (GT[91] "Tim đều TTT ở mỏm
  3/6"), `Phổi RRPN thô` (GT[91] "Phổi RRPN rõ", GT[100] "RRPN giảm 2 phế
  trường"), `Bụng mềm` (GT[91]/GT[100] "Bụng mềm không chướng"), `Tiểu được`.
- **Ngoại lệ: `Bn tỉnh` KHÔNG gán.** Ban đầu đã viết gán, sau đó tìm thấy GT[141]
  đã quyết định **không** gán "Bệnh nhân tỉnh, tiếp xúc tốt" → bỏ để không tự mâu
  thuẫn. Đây là lý do phải grep tiền lệ trước khi viết, không chỉ dựa vào cảm giác
  "dòng khám thì gán".
- Sinh hiệu: tên viết tắt → `TÊN_XÉT_NGHIỆM`, trị số + đơn vị →
  `KẾT_QUẢ_XÉT_NGHIỆM` (tiền lệ GT[91]/GT[131]/GT[137]): `HA` + `110/ 70 mmHg`,
  `M` + `70 l/p`.
- Dãy sao = tên thuốc bị mask → `THUỐC`, candidates rỗng, mỗi độ dài mask là một
  bề mặt riêng (tiền lệ GT[24]/GT[51]/GT[76]/GT[100]).
- Liều/đường dùng **không gán**: "x 1,0 Viên", "x 2,0 Viên", "Ngày uống 1 viên
  buổi sáng sau ăn", "Ngày uống 2 viên buổi tối" (tiền lệ GT[81]/GT[235]).

### Bẫy đếm lần xuất hiện

- Block 162: `đau ngực` khớp **4 lần**. Chỉ khai `[0]` riêng ("vào viện vì lí do
  đau ngực"); `[1]` nằm trong `đau ngực T âm ỉ`, `[2]` trong `tình trạng đau ngực
  tăng lên`, `[3]` trong `Đau ngực T âm ỉ` (lần khám) → 3 lần kia đã được nhãn
  dài hơn bao trọn.
- Block 162: `đau ngực T âm ỉ` và `đau không lan` mỗi cụm khớp **2 lần** (một ở
  Bệnh sử, một ở mục Khám) → khai `[0]` và `[1]` riêng, vì đây là 2 khái niệm ở 2
  vị trí khác nhau trong bệnh án, đều phải xuất hiện trong output.
- Block 162: `M` khớp **14 lần** — 13 lần là chữ "m" thường trong thân văn bản
  (matcher không phân biệt hoa/thường). Nhãn mạch là `[12]`. Đây đúng loại bẫy
  GT[91] đã gặp (ở đó là `("M", 15, LAB, ...)`).
- Block 162: cụm `đau tăng khi gắng sức` **bị ngắt dòng giữa cụm** — needle
  `"đau tăng khi gắng sức"` cho **0 lần**, phải viết `"đau \ntăng khi gắng sức"`.
  Cùng loại lỗi ở block 158: `Đo hoạt độ AST \n(GOT)`, `Định lượng \nCreatinin
  (máu)`, `Định \nlượng Glucose`, `Định lượng NT - proBNP ( \nProBNP)`.
- Block 158: `ProBNP` khớp **2 lần** ("NT - proBNP" và "( ProBNP)") → nhãn dài
  `Định lượng NT - proBNP ( \nProBNP)` bao trọn cả 2 → không khai riêng.
- Block 288: nhãn `bệnh tăng HA vô căn(nguyên phát)` bao trọn lần duy nhất của
  `HA` → không gán `HA` riêng (tiền lệ GT[93] với "tăng HA").
- Block 176: `giảm cân` **2 lần** — `[1]` nằm trong `giảm cân tối đa 60 pound` →
  chỉ khai `[0]`. `tăng cân trở lại` **2 lần** cùng nghĩa → dùng `ALL`.

### Quyết định đáng ghi

- **Phiếu xét nghiệm block 158 gần trùng phiếu trong block 62 (GT[62]) nhưng
  ngắt dòng khác** và có thêm Glucose + siêu âm tim + ghi điện tim. Không copy
  nguyên bề mặt từ GT[62] mà đo lại từng needle bằng `--occ` — nếu copy thì 4
  nhãn bị ngắt dòng sẽ khớp 0 lần và im lặng biến mất.
- `Thời gian prothrombin (PT: Prothrombin Time), \n(Các tên khác: TQ; Tỷ lệ
  Prothrombin)`: giữ **trọn cụm** gồm cả phần "Các tên khác", theo tiền lệ
  GT[136] ("Thời gian Prothrombin (PT / TQ / Tỷ lệ Prothrombin)").
- `bệnh tăng HA vô căn(nguyên phát)`: giữ nguyên bề mặt **thiếu dấu cách trước
  ngoặc** (lỗi gõ trong bệnh án) — quy ước as-written. Mã I10 trùng tên nguyên
  văn "Bệnh tăng huyết áp vô căn (nguyên phát)".
- `Cơn đau thắt ngực không ổn định` → **I20.0**, trùng nguyên văn tên mã.
- Block 176 `60 pound`: **không** tách thành `KẾT_QUẢ_XÉT_NGHIỆM` — là mức thay
  đổi cân nặng bệnh nhân tự kể, không phải xét nghiệm được chỉ định (tiền lệ
  GT[24] đã bỏ "tăng 10kg" với cùng lý do).
- Block 176 `Lý do nhập viện: đến khám vì sau cân sau phẫu thuật`: bản dịch lỗi
  (có lẽ "sụt cân sau phẫu thuật"), không đoán được khái niệm → không gán.
  Đây là chỗ mất recall có ý thức, không phải bỏ sót.
- Block 176 `chế độ ăn kiêng có giám sát`: can thiệp/thủ thuật → không gán.

### Còn lại sau đợt 8

Không còn file nào rỗng nhãn → từ đây quay lại xếp hàng theo **số ký tự chưa gán**
của từng file: 2.txt (1764c), 8.txt (1228c), 36.txt (944c), 10.txt (936c),
41.txt (931c), 12.txt (868c), 91.txt (824c), 18.txt (821c), 78.txt (813c),
13.txt (812c), 88.txt (788c), 5.txt (777c). Tổng còn ~130 block / ~25300 ký tự
(13.4%).

## Đợt 9: gán TRỌN file 2.txt (14 block còn lại) — 86.6% → 87.6%

Từ đây không còn file nào rỗng nhãn nên tiêu chí chọn đổi sang **số ký tự CHƯA
gán của từng file**. `2.txt` đứng đầu: 1764c chưa gán trên 3740c tổng.

`2.txt` là bài phổ biến kiến thức **bệnh Kawasaki**, bị cắt thành 17 block. Ba
block dài nhất đã gán từ trước (GT[104] dinh dưỡng/kết luận, GT[124] định nghĩa/
biến chứng, GT[135] nguyên nhân). Đợt này gán 14 block còn lại → **46 nhãn mới**,
file `2.txt` từ 26 lên **72 entity**. Đo bằng `python3 src/gt_blocks.py`:
block 202 → 216, phủ ký tự 86.63% → **87.56%**, entity 2496 → 2542, chiếu ra
100 file / 3008 entity.

Cùng nguồn với bài Kawasaki trong `8.txt` (GT[140] "4. Biến chứng" + "5. Chẩn
đoán") → mọi mã và quyết định lấy lại từ GT[140]/GT[124]: M30.3 cho Kawasaki,
I25.4 phình giãn vành, I25.1 hẹp tắc vành, H10.9 viêm kết mạc 2 bên không ghèn,
I77.6 viêm mạch máu, và bề mặt `Sốt` chỉ lấy tên triệu chứng chứ không kèm "≥5
ngày".

### Block 195 — 3 dòng biện luận tâm thần bị ghép vào đầu

Đây là block duy nhất của file có mảnh lạ. Ba dòng đầu là **chẩn đoán phân biệt**
của một EHR tâm thần khác (cùng chủ đề GT[56]: ảo giác + bệnh lý chất trắng nghi
đa xơ cứng), phần sau mới là panel xét nghiệm Kawasaki. Quyết định:

- `Bệnh đa xơ cứng` — "Sẽ không điển hình cho…" = bệnh bị **loại trừ** → DX +
  `isNegated`, mã **G35** (tra `entries['G35']` = "Bệnh đa xơ cứng", trùng nguyên
  văn). Tiền lệ: GT[115] gán `huyết khối tĩnh mạch sâu (DVT)` DX+NEG khi bệnh bị
  loại trừ bằng "âm tính với".
- `Ảo giác do rượu` — chẩn đoán **đang được nghĩ tới** ("(suy nghĩ)" = dịch máy
  của "considered") → gán, KHÔNG negate. Mã **F10.5** "Rối loạn tâm thần và/hoặc
  hành vi do sử dụng rượu, loạn thần". ICD-10 không có mã riêng cho ảo giác do
  rượu; F10.5 là mã bao. (R44.3 "Ảo giác, không xác định" bị loại vì đây là ảo
  giác **do rượu**, có nguyên nhân xác định.)
- `loạn thần` — "Không được coi là thực sự loạn thần" → DX + `isNegated`, mã
  **F29** "Loạn thần không thực tổn không xác định".
- Panel XN: 11 nhãn LAB. `Men gan` ở đây là **TÊN xét nghiệm được chỉ định** →
  `TÊN_XÉT_NGHIỆM`, khác hẳn tiền lệ GT[37]/GT[140] nơi "tăng men gan" là
  `TRIỆU_CHỨNG`. Đây là cặp dễ sai nhất trong đợt: cùng chữ "men gan" nhưng 2
  loại khác nhau tùy có chữ "tăng" hay không.
- `ECG điện tâm đồ`: giữ **trọn cụm** song ngữ làm một bề mặt (tiền lệ GT[136]
  giữ "Thời gian Prothrombin (PT / TQ / Tỷ lệ Prothrombin)").
- `động mạch vành` trong "(quan trọng nhất để đánh giá động mạch vành)": chỉ là
  bộ phận được siêu âm → **không gán** (giải phẫu đơn thuần, không phải chẩn
  đoán). Cùng lý do bỏ `động mạch vành` ở block 228.

### Quyết định đáng ghi

- **Mask và viết tắt là 2 bề mặt riêng.** Block 271: `2. ******* (ASA)` — 7 sao
  là tên thuốc bị che (aspirin) → THUỐC candidates rỗng; nhưng `ASA` **không bị
  che** nên gán được RxCUI **1191** (aspirin, IN — xác nhận bằng
  `awk -F'|' 'tolower($15)=="aspirin"' RXNCONSO.RRF`). Bỏ `ASA` thì mất một
  khái niệm có candidates thật.
- **"để ngừa X" → isNegated.** `huyết khối` trong "giảm liều duy trì để ngừa
  huyết khối" chưa xảy ra, đang phòng ngừa → DX + NEG, theo GT[106] ("để tránh
  tình trạng chảy máu khó cầm"). Mã **I24.0** (huyết khối mạch vành không gây
  NMCT) vì bối cảnh là vành Kawasaki — giống lựa chọn ở GT[232], không dùng
  I82.9 như GT[52]/GT[134] (huyết khối tĩnh mạch).
- **`39–40°C` KHÔNG tách thành `KẾT_QUẢ_XÉT_NGHIỆM`.** Đây là **khoảng** mô tả
  đặc điểm sốt trong bài giảng, không phải trị số đo được tại giường — khác
  GT[143] nơi `36.7°c` là sinh hiệu thật. Giữ nguyên trong bề mặt triệu chứng
  `Sốt 39–40°C`. Cùng nguyên tắc với GT[24] đã bỏ "tăng 10kg".
- **`hạ sốt` là NHÓM THUỐC, không phải triệu chứng.** Câu "Ít đáp ứng với hạ sốt
  hoặc kháng sinh" — "hạ sốt" ở đây là thuốc hạ sốt (tiền lệ GT[159] "Thuốc giảm
  đau, hạ sốt" → DRUG). Nếu gán SYM thì sai loại → mất điểm gấp đôi.
- **`vắc xin sống` không gán.** Vắc xin là chế phẩm sinh học dự phòng, không phải
  thuốc điều trị; đề gắn `THUỐC` với RxNorm nên để ngoài. Là chỗ mất recall có ý
  thức, ghi lại để rà lại nếu có validation split.
- **`biến chứng động mạch vành` → DX candidates rỗng**, theo GT[104] cùng file đã
  để rỗng cho "biến chứng mạch vành" (biến chứng vành của Kawasaki nằm trong
  M30.3, ICD-10 không có mã riêng).
- Tiêu đề mục: gán **phần là tên khái niệm** (`bệnh Kawasaki`, `Tổn thương ở đầu
  chi`, `Ban đỏ toàn thân`), bỏ số thứ tự và các từ chỉ loại (`Triệu chứng`,
  `Triệu chứng điển hình`) — từ "Triệu chứng" khớp 2 lần ở block 270 nhưng cả 2
  đều là từ chỉ loại nên không gán lần nào.
- `Viêm kết mạc 2 bên, đỏ nhưng không có ghèn`: **không tách nhãn NEG riêng** cho
  "không có ghèn" — nó là mô tả nằm trong bề mặt chẩn đoán, theo GT[140] cùng
  nguồn đã gán trọn cụm "Viêm kết mạc 2 bên không ghèn" → DX H10.9.

### Sửa citation sai chủ (4 chỗ)

Vẫn theo thủ tục awk-verify mọi `GT[n]` viện dẫn. Bốn chỗ sai:
`GT[186]` (không tồn tại) → **GT[77]** cho `Albumin`; `GT[151]` (không tồn tại) →
**GT[159]**/**GT[109]** cho `kháng sinh`; `GT[81]` → **GT[159]** cho "Thuốc giảm
đau, hạ sốt" (GT[81] là bài amyloidosis, không có nhãn này); `GT[62]` → **GT[54]**
cho `Siêu âm tim`; `GT[110]` → **GT[115]** cho DVT bị loại trừ. Bài học lặp lại:
số block trong ghi chú **không** đoán được từ ký ức, phải awk ra chủ thật.

### Kiểm tra offset

`data/gt_block/2.json`: 72 entity, **0 lệch offset** (so `txt[start:end]` với
`text` từng nhãn). Phân bố: CHẨN_ĐOÁN 28, TRIỆU_CHỨNG 24, TÊN_XÉT_NGHIỆM 11,
THUỐC 9.

### Còn lại sau đợt 9

Xếp hàng theo ký tự chưa gán: 8.txt (1228c), 36.txt (944c), 10.txt (936c),
41.txt (931c), 12.txt (868c), 91.txt (824c), 18.txt (821c), 78.txt (813c),
13.txt (812c), 88.txt (788c), 5.txt (777c). Còn ~116 block / ~23570 ký tự (12.4%).

---

## Đợt 10: gán TRỌN file 8.txt (6 block còn lại) — 87.6% → 88.2%

**Đo bằng:** `python3 src/gt_blocks.py` trước/sau. 216 → **222 block**, 165867 →
**167095 ký tự (88.21%)**, entity 2542 → **2571**.

### Vì sao chọn 8.txt

Nhiều ký tự chưa gán nhất (1228c / 6 block) trong 100 file.

### Cấu trúc file: HAI nguồn ghép vào nhau

`8.txt` không phải một tài liệu. Nó là:

- **(a) một bệnh án tâm thần** — BN có ý tưởng tự tử + ảo giác thị/thính giác +
  tình cờ phát hiện bệnh lý chất trắng trên CT sọ. Block 56 (đã gán, `GT[56]`) là
  mục "2. Tiền sử bệnh hiện tại". Đợt này gán thêm **block 190 = mục "1. Tiền sử
  bệnh"** và **block 155 = mục "3. Đánh giá tại bệnh viện"** của CÙNG bệnh án đó.
- **(b) bài giảng "Bệnh Kawasaki"** — cùng nguồn với `GT[104]`/`GT[124]`/`GT[135]`
  (nằm ở 2.txt) và `GT[140]` (đã gán, ở chính 8.txt). Bốn block 226/276/304/321.

Ghép được (a) lại thành 3 mục liền mạch là điều quan trọng: nhờ đó **tái dùng
đúng mã của `GT[56]`** thay vì tra lại từ đầu và có nguy cơ mâu thuẫn với chính
mình — `bệnh lý chất trắng` → G37.9, `chọc dò dịch não tủy` → LAB, `các băng nhóm
oligoclonal` → LAB.

### Quyết định gán nhãn mới trong đợt này

**1. Lỗi dịch `- ho X` = `h/o X` (history of).** Dòng `- ho Rối loạn cảm xúc
(trầm cảm)` không phải triệu chứng ho. Đây là artifact dịch máy của "h/o" trong
EHR gốc tiếng Anh. Kiểm chứng: `grep -rn -- "- ho " input/` trả 11 dòng ở 9 file,
tất cả đều là `- ho <tên bệnh>` trong mục bệnh lý mạn tính (`- ho Bệnh bạch cầu
dòng tủy mãn tính`, `- ho Rung nhĩ`, `- ho đái tháo đường`). Tiền lệ `GT[87]` đã
xử lý đúng: **bỏ chữ "ho", chỉ lấy tên bệnh**. Làm theo.

Đây là chỗ dễ mất điểm kép: nếu gán `ho` → TRIỆU_CHỨNG thì vừa tạo một khái niệm
sai (0 điểm) vừa làm bề mặt bệnh thật bị lệch.

**2. Cùng một mục "Tiền sử bệnh" nhưng KHÔNG phải mọi nhãn đều isHistorical.**
Block 190 nằm dưới tiêu đề `1. Tiền sử bệnh`, nên `Rối loạn cảm xúc`, `trầm cảm`,
`hội chứng nghiện rượu`, `seroquel` đều `isHistorical` (tiền lệ
`GT[9]`/`GT[14]`/`GT[20]`/`GT[87]`). Nhưng ba triệu chứng trong ngoặc — `lú lẫn`,
`chóng mặt`, `khó nhìn gần` — là lý do BN **đang** nghi thuốc, và `GT[56]` cùng
bệnh án đã gán chúng ở mục triệu chứng HIỆN TẠI không assertion. Nên để **rỗng**.
Quy tắc rút ra: assertion theo *thời điểm của khái niệm*, không theo *tiêu đề mục
mà nó nằm trong*.

**3. `Đột sống thắt lưng` là một bề mặt riêng, không bỏ.** Đây là lỗi dịch của
"(Lumbar Puncture)" — tức là TÊN KHÁC của chính chọc dò dịch não tủy, đặt trong
ngoặc ngay sau. Gán LAB thành nhãn riêng theo tiền lệ `GT[56]` đã gán cả
`Ảo thanh (AH)` và `ảo giác thính giác` cho cùng một triệu chứng. Recall là toàn
bộ vấn đề nên không bỏ bề mặt trùng nghĩa.

**4. `sốt phát ban` → B09, KHÔNG A75.9.** Tra ICD ra `A75.9 = "Bệnh sốt phát ban,
không xác định"` — tên mã trùng chữ gần như hoàn hảo. Nhưng A75.x là **typhus do
Rickettsia** (chấy rận truyền), sai hoàn toàn so với nghĩa tiếng Việt phổ thông
"sốt kèm phát ban do virus". Chọn `B09` = "Nhiễm virus không xác định, có biểu
hiện tổn thương tại da và/hoặc niêm mạc". Bài học: **trùng tên mã không đủ để
chọn mã**, phải đọc nghĩa bệnh học.

**5. "dễ nhầm với X" thì X vẫn được gán, KHÔNG isNegated.** Câu "Các triệu chứng
của Kawasaki dễ nhầm với sốt siêu vi, sốt phát ban, nhiễm trùng" là chẩn đoán
phân biệt đang được nghĩ tới, chưa bị loại. Tiền lệ `GT[135]` cùng nguồn cũng gán
hết danh sách nguyên nhân nghi ngờ. Khác với `GT[195]` nơi "sẽ không điển hình
cho Bệnh đa xơ cứng" là **loại trừ thật** → DX + isNegated.

**6. Cắt mốc thời gian / kích thước khỏi bề mặt triệu chứng.** `sốt cao 3–4 ngày`
→ chỉ `sốt cao`; `Hạch cổ to ≥1,5 cm` → chỉ `Hạch cổ to`. Theo tiền lệ `GT[140]`
cùng nguồn lấy `Sốt` cho "Sốt ≥5 ngày".

**7. Nhưng cụm mô tả trong ngoặc thì giữ TRỌN.** `Tổn thương đầu chi (phù, đỏ,
bong da)`, `Môi – miệng thay đổi (nứt, đỏ, lưỡi dâu tây)`, `hạch >1,5 cm, chắc,
không hóa mủ` — giữ nguyên 1 bề mặt, không tách nhãn lồng nhau (tiền lệ `GT[313]`
`Viêm kết mạc 2 bên, đỏ nhưng không có ghèn`). Do đó KHÔNG khai `lưỡi dâu tây`
riêng ở block 321, và "không hóa mủ" **không** tách isNegated — nó là mô tả bên
trong bề mặt. Hai quy ước 6 và 7 khác nhau ở chỗ: **hậu tố đo lường thì cắt, mô
tả trong ngoặc thì giữ**.

**8. `hội chứng nghiện rượu` → F10.2** ("Rối loạn tâm thần và/hoặc hành vi do sử
dụng rượu, hội chứng nghiện"), khác `GT[98]`/line 2126 dùng F10.1 cho "uống nhiều
rượu" (= sử dụng gây hại, chưa nghiện). Hai mã đúng cho hai mức độ khác nhau, đây
không phải mâu thuẫn.

### Mã đã kiểm chứng

Qua `entries[code]['vi']` từ `load_icd()`: G37.9, F39, F32.9, F10.2, B34.9, B09,
A49.9, M30.3. Đã **loại** A75.9 (typhus) và R21 (ban da không xác định — không
dùng vì đây là tên bệnh chứ không phải triệu chứng ban đơn thuần). Xác nhận
`R50.0` **không tồn tại** trong danh mục BYT.

RxNorm qua `RXNCONSO.RRF`: `seroquel` → **83553** (BN Seroquel; quetiapine IN =
51272). Dùng mã BN cho biệt dược theo tiền lệ `GT[182]` (eliquis 1364436),
`GT[63]`/`GT[61]` (tylenol 202433).

### Sửa citation sai chủ (1 chỗ)

`GT[161]` viện dẫn cho "đang chờ kết quả → không gán VAL" **không tồn tại**; awk
ra chủ thật là **`GT[132]`** (dòng 1761). Đã sửa. Thủ tục awk-verify tiếp tục
bắt được lỗi ở mọi đợt — giữ nguyên.

### Kiểm tra offset

`data/gt_block/8.json`: **71 entity, 0 lệch offset** (so `txt[start:end]` với
`text` từng nhãn). Phân bố: TRIỆU_CHỨNG 35, CHẨN_ĐOÁN 26, TÊN_XÉT_NGHIỆM 8,
THUỐC 1, KẾT_QUẢ_XÉT_NGHIỆM 1.

### Còn lại sau đợt 10

**110 block / 22341 ký tự (11.8%).** Xếp hàng theo ký tự chưa gán: 36.txt (944c,
8 block), 10.txt (936c, 3), 41.txt (909c, 4), 12.txt (868c, 3), 91.txt (824c, 2),
18.txt (821c, **10 block** — file vụn nhất), 78.txt (791c, 2), 13.txt (790c, 2),
88.txt (788c, 3), 5.txt (777c, 2), 60.txt (737c, 3), 49.txt (734c, 4), 77.txt
(697c, 4), 92.txt (678c, 3).

---

## Đợt 11: gán TRỌN file 36.txt (8 block còn lại) — 88.2% → 88.7%

**Đo bằng:** `python3 src/gt_blocks.py` trước/sau. 222 → **230 block**, 167095 →
**168039 ký tự (88.70%)**, entity 2571 → **2590**.

### Cấu trúc file

`36.txt` gần như là MỘT bệnh án viết tay hoàn chỉnh của BN nam 17 tuổi hội chứng
thận hư / viêm cầu thận mạn: bệnh sử + phiếu xét nghiệm (block 77, đã gán trước
đó) rồi mục **2. Chẩn đoán**, **3. Tiên lượng**, **4. Hướng xử trí**, **5. Đơn
thuốc**. Chỉ có hai chỗ bị corpus làm rối:

- **block 225** là "2. Tiền sử bệnh hiện tại" của một EHR khác (ca FNA nốt tuyến
  giáp + sỏi mật), ghép vào giữa đơn thuốc.
- Vì mẩu ghép đó chen vào, **dòng thuốc số 5 (Zestril) bị đẩy xuống cuối file**
  (block 327), sau cả mẩu EHR lạ. Đây là lý do phải đọc trọn file trước khi gán,
  không thể xử từng block rời.

### Quyết định gán nhãn mới

**1. Dòng đơn thuốc: gán "tên + hàm lượng" thành 1 bề mặt.** `Medrol 16mg`,
`Omez 20mg`, `Furosemid 40 mg`, `Zestril 10mg` — theo tiền lệ `GT[128]`
"aspirin 325mg". Bỏ "x 3 viên, uống 8h sáng sau ăn no" (tiền lệ `GT[297]`).

**2. Chế độ ăn KHÔNG phải triệu chứng — chỗ dễ gán sai nhất của file.** Dòng
"tăng protein (2 lạng thịt/ngày), không lipid, tăng glucid" là **khuyến nghị dinh
dưỡng**, không phải "tăng protein máu"/"tăng lipid máu" của bệnh nhân. Nếu gán
`lipid`[0] hay `protein`[2] ở đây thì tạo khái niệm sai → mất điểm kép theo Lưu ý
của đề. Đã cố ý không khai hai lần xuất hiện đó, ghi rõ trong ghi chú block 166.

Ngược lại `tăng lipid máu` ở dòng **"Điều trị triệu chứng: phù, tăng lipid máu,
giảm thải protein"** thì có gán → SYM. Cùng chuỗi ký tự, hai lần xuất hiện, một
gán một không — đây chính là loại phân biệt mà `--occ` bắt buộc phải chạy trước
khi viết.

**3. `tăng lipid máu` → SYM (không mã) ở đây, khác `GT[87]`/`GT[88]` → DX E78.5.**
Ở `GT[87]`/`GT[88]` bề mặt là `tăng lipid máu, không đặc hiệu` — **trùng nguyên
văn tên mã ICD** và nằm trong danh sách bệnh lý mạn tính. Ở đây là một biểu hiện
trong mục "Điều trị triệu chứng" → TRIỆU_CHỨNG, candidates rỗng. Không phải mâu
thuẫn, là hai vai khác nhau của cùng cụm từ.

**4. `VCTM` (viết tắt) → DX N03.9.** Viết tắt là một bề mặt riêng cần gán, theo
tiền lệ `GT[271]` (`ASA` gán riêng cạnh mask aspirin) và `GT[56]`
(`Ảo thanh (AH)` + `ảo giác thính giác`). Recall là toàn bộ vấn đề nên mọi bề mặt
trùng nghĩa đều phải có nhãn.

**5. Xét nghiệm được CHỈ ĐỊNH vẫn là TÊN_XÉT_NGHIỆM.** Mục "Làm thêm các xét
nghiệm theo dõi tiến triển bệnh: protein niệu 24h, protein máu, albumin máu, điện
giải đồ" — chưa có kết quả nhưng vẫn là tên xét nghiệm (tiền lệ `GT[195]` panel
Kawasaki, `GT[133]` y lệnh theo dõi ALT/AST).

**6. `sỏi mật` → K80.2 (không K80.5).** Hai mã đang cùng tồn tại trong corpus:
`GT[110]` dùng **K80.2** cho `sỏi mật` + HIST trên siêu âm (= sỏi túi mật không
kèm viêm), `GT[37]` dùng **K80.5** cho sỏi đoạn cuối ống mật chủ trên ERCP. Bối
cảnh block 225 giống `GT[110]` (siêu âm cho thấy sỏi mật) nên theo K80.2. Đây là
hai bối cảnh khác nhau, **không** thuộc danh sách cần sweep nhất quán.

**7. `nốt sần tuyến giáp phải có cấu trúc vi nang` → E04.1** (bướu giáp đơn nhân
không độc). "nốt sần" là lỗi dịch của "nodule", giữ nguyên văn theo quy ước.
`FNA` → LAB (tiền lệ `GT[40]` "chọc hút dịch", `GT[27]` "sinh thiết").

### Sửa một nhãn tự mâu thuẫn ở GT[80] (không thuộc 36.txt)

Trong lúc tra tiền lệ về liều thuốc, phát hiện `GT[80]` (4.txt) gán
`("75 microgam/ngày", 0, VAL, ...)` **kèm ghi chú ngay bên cạnh nói "liều thuốc,
KHÔNG phải KẾT_QUẢ_XÉT_NGHIỆM"** — nhãn và ghi chú của chính nó ngược nhau. Ba
liều khác trong cùng block ("100 microgam", "200-300 microgam/ngày",
"4 nanogam/mL") đã bị bỏ đúng theo quy ước.

Đã **xoá nhãn đó**. Lý do không gộp vào bề mặt THUỐC như `GT[128]`
"aspirin 325mg": ở đây liều bị tách khỏi tên thuốc bởi chữ "với liều"
("uống levothyroxine với liều 75 microgam/ngày") nên không thể tạo bề mặt liền
mạch. Hệ quả: `KẾT_QUẢ_XÉT_NGHIỆM` giảm 176 → 175 dù thêm 11 nhãn VAL của 36.txt.

Đây là lỗi *của tôi ở đợt trước*, tìm ra nhờ thủ tục grep tiền lệ trước khi viết
nhãn mới. Giữ nguyên thủ tục.

### Mã đã kiểm chứng

ICD qua `entries[code]['vi']`: N03.9, N04, E04.1, K80.2. Đã loại E04.9 (bướu giáp
không độc không xác định — kém cụ thể hơn E04.1 cho nốt đơn độc) và C73/D34 (chưa
có kết quả tế bào học, không được suy diễn lành/ác).

RxNorm qua `RXNCONSO.RRF`: Medrol → **202702** (BN), Zestril → **196472** (BN),
`Furosemid` → **4603** (furosemide IN; cách viết Việt bỏ "e" cuối vẫn là cùng hoạt
chất, tiền lệ `Simethicon` → 9796). `Omez` **không có trong RxNorm** (biệt dược
Dr. Reddy's, không lưu hành ở Mỹ) → dùng mã hoạt chất omeprazole **7646** theo
tiền lệ `GT[35]` gán `Pimperan` → 6915 thay vì để rỗng.

### Sửa citation sai chủ (4 chỗ)

`GT[126]`→**GT[40]** (chọc hút dịch), `GT[189]`→**GT[27]** (sinh thiết),
`GT[171]`→**GT[88]** (tăng lipid máu không đặc hiệu), `GT[184]`→**GT[35]**
(Pimperan). Bốn đợt liên tiếp đều có citation sai — số block **không** nhớ được,
phải awk ra chủ thật mỗi lần.

### Kiểm tra offset

`data/gt_block/36.json`: **67 entity, 0 lệch offset**. Phân bố: TÊN_XÉT_NGHIỆM 25,
CHẨN_ĐOÁN 14, TRIỆU_CHỨNG 13, KẾT_QUẢ_XÉT_NGHIỆM 11, THUỐC 4.

### Còn lại sau đợt 11

**102 block / 21397 ký tự (11.3%).** Xếp hàng: 10.txt (936c, 3 block), 41.txt
(909c, 4), 12.txt (868c, 3), 91.txt (824c, 2), 18.txt (821c, 10), 78.txt (791c, 2),
13.txt (790c, 2), 88.txt (788c, 3), 5.txt (777c, 2), 60.txt (737c, 3), 49.txt
(734c, 4), 77.txt (697c, 4).

---

## Đợt 12: gán TRỌN file 10.txt (3 block) + chuẩn hoá quy ước liều thuốc — 88.7% → 89.2%

**Đo bằng:** `python3 src/gt_blocks.py` trước/sau. 230 → **233 block**, 168039 →
**168975 ký tự (89.2%)**, entity 2590 → **2605**.

### Việc quan trọng nhất của đợt này không phải 3 block, mà là một bất nhất

Trước khi viết batch, tôi quét lại toàn bộ nhãn THUỐC đã gán để xem quy ước hàm
lượng có nhất quán không. Script quét `data/gt_block/*.json`, với mỗi entity
`THUỐC` kiểm tra 18 ký tự ngay sau bề mặt có khớp mẫu `<số><đơn vị>` hay không:

- **16 nhãn** có hàm lượng đứng ngay sau nhưng **không** gộp vào bề mặt:
  `bumetanide` 2mg, `levofloxacin` 750mg, `lasix` 40 mg (×2 file), `Simethicon`
  100mg (×2), `Alverin citrate` 40mg (×2), `metoclopramide` 10mg (×2),
  `metoprolol` 25mg, `aspirin` 325mg (ở 10.txt), `Philpovin` 5g, `Fortex` 25mg,
  `Nitramyl` 2,5 mg/viên, `acetaminophen` 500mg.
- **6 nhãn** có gộp: 4 nhãn của 36.txt (đợt 11) + `aspirin 325mg` và
  `methylprednisolone 125mg` ở `GT[128]`.

Tức là đợt 11 tôi đã theo một tiền lệ **thiểu số** (`GT[128]`) mà không kiểm tra
phía còn lại. **Đã sửa 6 nhãn thiểu số về chuẩn "chỉ tên thuốc".**

Lý do chọn hướng "bỏ hàm lượng" thay vì hướng ngược lại:
1. Đa số áp đảo 16/6 — sửa 6 nhãn rẻ hơn sửa 16.
2. Hàm lượng không phải một phần của *khái niệm thuốc*; RxNorm code gán cho hoạt
   chất/biệt dược, không cho hàm lượng.
3. Đề tính `text_score = 1 − WER`. Bề mặt ngắn-đúng an toàn hơn bề mặt dài-thừa:
   nếu GT chỉ có tên mà tôi đoán "tên + 16mg" thì WER phạt phần thừa.

Cùng lúc sửa ghi chú quy ước trong header 36.txt cho khớp. `THUỐC` trong bảng
chiếu vẫn 380 (số nhãn không đổi, chỉ bề mặt ngắn lại).

**Bài học thủ tục:** grep tiền lệ theo *một* chỗ là chưa đủ — với quy ước áp dụng
cho cả lớp khái niệm, phải **đếm** trên toàn bộ `data/gt_block/*.json` để biết
đâu là chuẩn thật, đâu là ngoại lệ.

### Cấu trúc file 10.txt

Một EHR đánh trống ngực / ngoại tâm thu. Block 34 (2016c, mục "2. Tiền sử bệnh
hiện tại") đã gán từ đợt trước. Ba block còn lại:

- **block 175** — mục "1. Tiền sử bệnh" + "Các yếu tố nguy cơ liên quan"
- **block 186** — kết quả XN/CĐHA của mục 3, mở đầu bằng tiêu đề rác "3/ đơn thuốc:"
- **block 245** — mục "3. Đánh giá tại bệnh viện", bị ghép 1 dòng chẩn đoán viêm
  gan B của EHR khác (cùng nguồn `GT[133]`/`GT[39]` ở 24.txt)

### Quyết định gán nhãn mới

**1. Chuỗi sinh hiệu dính liền `VS98.3 12987 56 18 99RA`.** Đây là bản dịch làm
mất hết dấu phân cách của "VS 98.3 / 129-87 / 56 / 18 / 99% RA": nhiệt độ 98.3°F,
HA 129/87, mạch 56, nhịp thở 18, SpO2 99% room air. **Không tách được** thành từng
trị số vì không còn ranh giới nào để cắt → gán TRỌN `98.3 12987 56 18 99RA` thành
1 bề mặt VAL (tiền lệ `GT[115]` "8.126.3" dính 2 trị số, `GT[17]`
"vếtvết protein niệu", `GT[102]` "1.1-->0.8"), và `VS` thành 1 bề mặt LAB riêng
(tiền lệ `GT[162]`/`GT[91]` gán nhãn mạch viết tắt `M` riêng khỏi trị số).

Grep `VS[0-9]` toàn corpus: chỉ 1 dòng duy nhất, không có block nào khác cùng dạng.

**2. "không có gì đáng chú ý" / "không ghi nhận gì bất thường" → KHÔNG gán VAL.**
Block 186 có 4 cụm như vậy. Kết quả bình thường không được gán (tiền lệ `GT[143]`
"điện tâm đồ ... bình thường" cũng không gán VAL; `GT[141]`/`GT[68]`/`GT[133]`
không gán dấu hiệu bình thường). Tên xét nghiệm thì vẫn gán đủ: `phân tích nước
tiểu`, `chụp x-quang ngực`, `điện tâm đồ`, `monitor holter`.

Cũng **không** gán `isNegated` cho tên xét nghiệm — `check()` chặn assertion trên
`TÊN_XÉT_NGHIỆM`/`KẾT_QUẢ_XÉT_NGHIỆM`.

**3. `viêm tuyến mồ hôi` → L73.2.** Dòng "doxycycline cho viêm tuyến mồ hôi" —
bệnh đang được điều trị từ trước nên HIST. Danh mục BYT chỉ có **một** mã khớp:
L73.2 "Viêm tuyến mồ hôi mủ [nhọt ổ gà]" (hidradenitis suppurativa). Đã loại
L73.9 "Bệnh lý nang lông, không xác định" vì kém cụ thể hơn.

**4. `Căng thẳng` → SYM, KHÔNG dùng F43.9.** Ba tiền lệ đang tồn tại:
`GT[64]` gán `căng thẳng` → SYM; `GT[85]`/`GT[233]` gán `stress`/`Stress kéo dài`
→ DX F43.9. Phân biệt: ở `GT[85]`/`GT[233]` cụm nằm trong **danh sách bệnh / lời
khuyên dự phòng** nên là chẩn đoán; ở đây là "bệnh nhân có Căng thẳng nhiều trong
công việc" do BN kể → **biểu hiện** → SYM. Cùng lớp phân biệt với
`tăng lipid máu` ở đợt 11.

**5. `atenolol (uống hôm nay)` vẫn isHistorical.** "hôm nay" nghe như hiện tại,
nhưng dòng này nằm trong danh sách **"Thuốc trước khi nhập viện"**. Thống nhất
với chính `GT[34]` cùng EHR, nơi "Ở nhà bệnh nhân đã sử dụng atenololtrong ngày"
thuộc mục "Các diễn biến trước khi nhập viện". Đây là ngoại lệ *có kiểm soát* của
quy tắc đợt 10 ("assertion theo thời điểm khái niệm, không theo tiêu đề mục"):
thời điểm ở đây thật sự là *trước khi nhập viện*, tiêu đề mục nói đúng.

**6. Cà phê / caffeine KHÔNG gán** dù `caffeine` có trong RxNorm. "hàng chục tách
cà phê có caffeine" là chất kích thích trong đời sống, không phải thuốc điều trị
(tiền lệ `GT[85]` "cà phê, chè, thuốc lá"; `GT[98]` "Uống rượu 30 năm"). Mỗi cụm
xuất hiện 2 lần, cố ý bỏ cả 4.

**7. `ngoại tâm thu nhĩ` để candidates RỖNG.** Mã I49.1 "Atrial premature
depolarization" **có** trong danh mục BYT nhưng **cột tên tiếng Việt rỗng**
(kiểm bằng `entries['I49.1']['vi']` → `''`). Giữ nhất quán với `GT[34]` cùng EHR
đã để rỗng. Tương tự `Nhịp xoang chiếm ưu thế` — không có mã ICD nào cho nhịp
xoang bình thường, nhưng **vẫn gán DX** với candidates rỗng (quy ước đã chốt:
chẩn đoán không có mã tương đương vẫn phải gán, vì `J_candidates` = 1 khi cả GT
và pred đều rỗng).

**8. Dòng viêm gan B ghép vào lấy bề mặt ĐẦY ĐỦ.** Ở `GT[133]` (24.txt) câu này
bị ghép block làm mất chữ "Viêm gan" ở đầu nên bề mặt chỉ là "cấp tính do virus
B thể thông thường...". Ở block 245 câu **nguyên vẹn** → gán trọn "Viêm gan cấp
tính do virus B thể thông thường điển hình mức độ nặng giai đoạn toàn phát", cùng
mã B16.9. Hai bề mặt khác nhau cho cùng một chẩn đoán ở hai file là **đúng**, vì
bề mặt phải khớp văn bản thật của từng file.

**9. Tiêu đề rác "3/ đơn thuốc:" không gán** — tiêu đề mục, và không có tên thuốc
nào theo sau nó trong block (tiền lệ `GT[166]` bỏ tiêu đề "Thuốc:").

### Sửa citation sai chủ (1 chỗ, 3 mã)

Batch ban đầu ghi `GT[153]` / `GT[24]` / `GT[105]` cho ba tiền lệ trị số dính
liền. awk ra chủ thật: **GT[115]** ("8.126.3"), **GT[17]** ("vếtvết protein
niệu"), **GT[102]** ("1.1-->0.8"). Đã sửa. Năm đợt liên tiếp đều có citation sai
— xác nhận: **không được viết số block từ ký ức, phải awk mỗi lần.**

### Kiểm tra offset

`data/gt_block/10.json`: **54 entity, 0 lệch**. `51.json` (bị sửa bề mặt thuốc):
**25 entity, 0 lệch**. `36.json` (bị sửa 4 bề mặt thuốc): **67 entity, 0 lệch**.

### Còn lại sau đợt 12

**99 block / 20461 ký tự (10.8%).** Xếp hàng: 41.txt (909c, 4 block), 12.txt
(868c, 3), 91.txt (824c, 2), 18.txt (821c, 10), 78.txt (791c, 2), 13.txt (790c, 2),
88.txt (788c, 3), 5.txt (777c, 2), 60.txt (737c, 3), 49.txt (734c, 4), 77.txt
(697c, 4), 92.txt (678c, 3).

## Đợt 13: gán TRỌN file 41.txt (4 block) + chốt block 0 — 89.2% → 89.7%

**Đo:** `python3 src/gt_blocks.py` sau khi thêm → `block_da_gan 238`,
`ky_tu_da_gan 169906`, `phu_ky_tu 0.8969`, `entity 2627`, chiếu ra
**100 file / 3098 entity**. Trước đợt này: 233 / 168975 / 0.892 / 2605.

`41.txt` là bài QA trứng cá: câu hỏi của BN 15 tuổi + 3 mục giảng (cơ chế, bốn
yếu tố, phân loại, phác đồ), có **2 dòng EHR đau ngực bị ghép vào giữa** (đã gán
ở `GT[101]` đợt trước). 4 block còn lại: 177 (400c, câu hỏi), 206 (288c, mục
"1." cơ chế), 263 (133c, mục "2." bốn yếu tố), 289 (88c, phân loại viêm/không
viêm). **22 nhãn mới.** Sau đợt này 41.txt phủ **100%**.

### Quyết định gán nhãn

**1. Block 177 KHÔNG dùng được SHARE dù gần trùng block 113.** Block 113 (60.txt)
là *cùng nguồn dịch*, cùng mẫu câu "Cháu năm nay ... tuổi da rất nhiều dầu và bị
mụn trứng cá từ năm lớp ...". Nhưng bản 41.txt bị đổi **từ giữa câu đầu**:
18→15 tuổi, lớp 8→lớp 7, 6 tháng→4 tháng, và cắt hết đoạn "mụn cám / mụn đầu
trắng" + đoạn lo ngại thuốc. `SHARE` chỉ nhận **tiền tố giống hệt** nên phải gán
tay. Hệ quả cụ thể: số thứ tự lần xuất hiện của `"mụn"` **khác hẳn** GT[113] —
block 177 có 5 lần (dùng [1][2][3][4], bỏ [0] vì nằm trong "mụn trứng cá") còn
block 113 có 9 lần. Đây là lý do phải chạy `--occ` lại từ đầu cho từng block,
không được copy chỉ số từ block "giống".

**2. `mụn trứng cá`/`Trứng cá` → DX L70.9, `mụn`/`Mụn` trơ → SYM.** Tiền lệ
`GT[113]` (awk xác nhận chủ) phân biệt rõ: cụm có chữ "trứng cá" là **chẩn đoán**
(L70.9 "Trứng cá, không xác định"), còn "mụn" đứng một mình là **biểu hiện**.
`da rất nhiều dầu` → SYM cũng theo `GT[113]` cùng bề mặt. Lưu ý `GT[40]` gán
`mụn trứng cá` → **SYM** (bài tác hại thuốc tránh thai, mụn là *tác dụng phụ*
được liệt kê chứ không phải chẩn đoán) — không lấy làm tiền lệ ở đây.

**3. Bốn yếu tố cơ chế vẫn gán DX dù ba trong bốn không có mã ICD.** Block 206
và 263 là **hai bản dịch khác nhau của cùng một đoạn** ("4 yếu tố" vs "bốn yếu
tố"), nên phải cho ra **cùng mã**:

| block 206 (bản dài) | block 263 (bản ngắn) | mã |
|---|---|---|
| Sản xuất quá nhiều chất bã nhờn | Tăng sản tuyến bã nhờn | *(rỗng)* |
| Bít tắc nang lông bởi chất bã và tế bào sừng | Sừng hóa nang lông bất thường | L73.8 |
| Vi hệ tại nang lông bởi Propionibacterium acnes (vi khuẩn kỵ khí thông thường) | Vi khuẩn C. acne | B96.8 |
| Giải phóng các chất trung gian gây viêm | Viêm tại chỗ | *(rỗng)* |

Ba mã của cột phải đã do `GT[102]` (59.txt) chốt từ trước — awk xác nhận. Việc
gán *cùng mã cho hai bề mặt khác nhau* là đúng: `candidates` chấm theo mã, không
theo chữ. `P. acnes` = tên cũ của `C. acnes` nên cùng B96.8.

Lý do "bã nhờn" phải để **rỗng**: quét danh mục BYT theo cả tên Việt (`bã nhờn`,
`tuyến bã`, `tiết bã`) và tên Anh (`seborrh`, `sebac`) chỉ ra L72.1 "Kén ở nang
lông/tuyến bã", L72.2 "Đa u nang tuyến bã", L82 "Bệnh dày sừng tiết bã", L21.x
"Viêm da dầu" — **không mã nào** là *tăng tiết bã nhờn*. Vẫn gán DX với
candidates rỗng (quy ước đã chốt, và `J_candidates` = 1 khi GT + pred đều rỗng).

**4. Lấy TRỌN cụm dài, không tách nhãn con.** `"Bít tắc nang lông bởi chất bã và
tế bào sừng"` và `"Vi hệ tại nang lông bởi Propionibacterium acnes (vi khuẩn kỵ
khí thông thường)"` giữ nguyên cả phần cơ chế và cả phần trong ngoặc — theo quy
ước "mô tả trong ngoặc giữ nguyên, không gán nhãn lồng" (tiền lệ `GT[101]` giữ
trọn "đau sau xương ức lan ra sau lưng"). Cũng vì thế **không** khai `"viêm"`
riêng ở block 206: nó nằm trong nhãn "Giải phóng các chất trung gian gây viêm".

**5. `- Không viêm:` / `- Viêm:` KHÔNG gán** (block 289). Đây *là* tên thể bệnh
(trứng cá không viêm / trứng cá viêm) nhưng bề mặt trơ 1–2 chữ quá chung. Thống
nhất với `GT[101]` **cùng file**: ở đó bề mặt là `"Trứng cá viêm nhẹ"` (có đủ chữ
"Trứng cá") mới gán DX. Lý do chọn hướng bỏ: đề trừ **2 lần** nếu tạo khái niệm
sai loại, nên một khái niệm mơ hồ có nguy cơ sai loại thì bỏ an toàn hơn.

**6. Tổn thương da của trứng cá viêm → SYM, candidates rỗng.** `sẹo` (tiền lệ
`GT[101]` cùng bề mặt), `mụn mủ`, `nốt sần`, `nang`. Đã loại từng mã một:
- `sẹo`: danh mục chỉ có sẹo giác mạc/kết mạc/rụng tóc có sẹo. L73.0 "Trứng cá
  sẹo lồi" là **thể bệnh khác**, không phải tổn thương → không dùng.
- `mụn mủ`: L13.1 "Viêm da mụn mủ dưới lớp sừng", L40.2 "Viêm da mụn mủ đầu chi
  liên tục" là **bệnh khác hẳn** → không dùng.
- `nốt sần` = lối dịch của "nodule" (tiền lệ `GT[225]` "nốt sần tuyến giáp phải
  có cấu trúc vi nang").
- `nang` = "cyst". Không dùng L70.1 "Trứng cá bọc" vì bề mặt chỉ là **một tổn
  thương**, không phải tên thể bệnh.

`nhân mụn` thì **có** mã: L70.0 (tiền lệ `GT[101]` "Nhân mụn" và `GT[2]`
"nhân mụn"). Danh mục BYT không có mã riêng cho comedo (quét `comedo` trong cột
tên Anh → 0 kết quả) nên L70.0 "Trứng cá thể thông thường" là lựa chọn đúng nhất.

**7. Người hỏi tự kể về chính mình → KHÔNG isFamily** (block 177). Tiền lệ
`GT[113]` cùng nguồn. Đoạn giảng cơ chế/phân loại không có BN cụ thể → không
assertion (tiền lệ `GT[102]`/`GT[2]`).

**8. Không gán:** "Chào bác sĩ", "Câu trả lời của bác sĩ:" (câu dẫn); "đi khám
da liễu" (chuyên khoa); "3 tháng điều trị" (thời gian); "da cháu đã đỡ hẳn"
(diễn biến tốt, tiền lệ `GT[113]` không gán "da cháu ít dầu hơn").

### Chốt block 0 → DONE_EMPTY

Block 0 = đúng một dòng `"Câu hỏi từ người dùng:"` (22c, **xuất hiện ở 23 file**:
13, 14, 17, 19, 28, 34, 35, 41, 49, 52, 55, 56, 59, 60, 61, 65, 78, 80, 81, 93,
95, 96, 100). Tiêu đề mục, không có khái niệm y khoa → `DONE_EMPTY.add(0)`
(tiền lệ `GT[166]` bỏ tiêu đề "Thuốc:", `GT[186]` bỏ "3/ đơn thuốc:"). Đây là
block đầu tiên dùng `DONE_EMPTY` — nó đã có trong code từ đầu nhưng chưa từng
được dùng, nên đợt này cũng là lần **kiểm thử thật** đường `coverage()` cộng
`DONE_EMPTY` vào `block_da_gan` (238 = 237 GT + 1 DONE_EMPTY).

### Kiểm tra citation (đợt đầu tiên KHÔNG có lỗi)

Trích toàn bộ `GT[n]` được viện dẫn trong batch (GT[2], GT[101], GT[102],
GT[113], GT[166], GT[186], GT[225]) rồi tra chủ thật của từng bề mặt bằng script
quét ngược `src/gt_blocks.py`. **Tất cả đúng** — chuỗi 5 đợt liên tiếp sai
citation đã dứt. Cách làm khác đợt trước: tra chủ **theo bề mặt** (script map
`needle → GT[n]`) thay vì awk theo số dòng, nhanh hơn và bắt luôn được các chủ
khác cùng bề mặt (ví dụ phát hiện `GT[40]` cũng có `mụn trứng cá` nhưng gán SYM
— dẫn tới quyết định số 2 ở trên).

### Kiểm tra offset

`data/gt_block/41.json`: **37 entity, 0 lệch**. Kiểm chéo 3 file cùng nguồn
trứng cá: `92.json` (20, 0), `60.json` (14, 0), `59.json` (29, 0).

### Còn lại sau đợt 13

**94 block / 19530 ký tự (10.3%).** Xếp hàng theo số ký tự chưa gán: 12.txt
(868c, 3 block), 91.txt (824c, 2), 18.txt (821c, **10 block** — phân mảnh nhất),
78.txt (791c, 2), 13.txt (790c, 2), 88.txt (788c, 3), 5.txt (777c, 2), 60.txt
(737c, 3), 49.txt (734c, 4), 77.txt (697c, 4), 92.txt (678c, 3), 54.txt (664c, 2),
40.txt (616c, 2), 25.txt (574c, 2).

## Đợt 14: gán TRỌN file 12.txt (3 block) — 89.7% → 90.2%

`12.txt` là **một bệnh án** tổn thương âm hộ/mông phải (cùng nguồn dịch với
`15.txt`) bị **ghép hai đoạn trả lời QA dị tật tai** (cùng nguồn với `48.txt`)
vào giữa, ở dòng 31–33. Đoạn dòng 31 đã gán từ trước (`GT[12]`), `SHARE[82]` đã
thừa hưởng 782 ký tự đầu của `GT[35]`. Còn 3 block: 22, 164, 209.

| block | ký tự | file | nội dung |
|---|---|---|---|
| 22 | 156 ×2 | 12.txt, 15.txt | mục "3. Đánh giá tại bệnh viện" |
| 164 | 431 ×1 | 12.txt | đuôi QA dị tật tai (nối tiếp `GT[12]`) |
| 209 | 281 ×1 | 12.txt | đuôi EHR: BN xin dùng tiếp kháng sinh |

**1. "Lo ngại về X" / "khả năng X" vẫn là CHẨN_ĐOÁN, assertions rỗng.** Đề chỉ
có 3 assertion (`isNegated`/`isFamily`/`isHistorical`), **không có "nghi ngờ"**.
Tiền lệ: `GT[24]` "khả năng em bị viêm bao tử", `GT[26]` "nghi ngờ cơn co giật",
`GT[205]` "kết quả nghi ngờ thiếu men G6PD". Bỏ hẳn thì mất recall — recall là
toàn bộ điểm.

**2. `Nhiễm virus Herpes simplex (HSV)` → B00.9.** Bề mặt khớp tên nhóm B00
("Bệnh do nhiễm virus herpes [herpes simplex]") nhưng **không nói vị trí** nên
lấy con `.9` "không xác định". Đã cân nhắc **A60.0** (herpes đường sinh dục) vì
tổn thương ở âm hộ → **loại**: câu này mới chỉ "lo ngại về" HSV nói chung, chưa
quy vị trí. Giữ trọn `(HSV)` theo quy ước mô tả trong ngoặc không tách nhãn lồng.

**3. `Bệnh thủy đậu/Zona (do Varicella Zoster Virus)` → MỘT nhãn, HAI mã
(B01.9 + B02.9).** Gạch chéo giữ nguyên một bề mặt (tiền lệ `GT[26]` "tụ dịch/tụ
máu dưới màng cứng mạn tính" → 1 nhãn), nhưng khác chỗ ở đây **hai vế là hai
bệnh khác nhau**: thủy đậu = B01, zona = B02. Tiền lệ nhiều mã cho một nhãn:
`GT[28]` "Viêm quanh răng" → K05.2+K05.3, `GT[24]` "trào ngược dạ dày thực quản"
→ K21.0+K21.9. Cả hai dùng con `.9 không biến chứng` vì mọi mã con khác của
B00/B01/B02 đều là **biến chứng cụ thể** (viêm màng não/viêm não/viêm phổi/bệnh
mắt) — không có ở ca này. Đây là nhãn multi-code thứ **4 và 5** của toàn corpus
(trước đó chỉ có 3: K25.x ×9 mã, K21.0/K21.9, K05.2/K05.3).

**4. Tiêu đề "3. Đánh giá tại bệnh viện" và "Các phát hiện chẩn đoán khác":
không gán.** Tiền lệ `GT[132]` và `GT[94]` — cả hai đều có đúng tiêu đề này,
chỉ gán các chẩn đoán bên dưới và không gán assertion.

**5. Block 164: `isFamily` bị chính quy ước type xoá đi.** Bệnh nhân là **con**
của người hỏi → theo `GT[12]` (cùng đứa bé, cùng nguồn) phải `isFamily`. Nhưng
nhãn duy nhất tìm được trong block là `chụp cắt lớp` = `TÊN_XÉT_NGHIỆM`, mà
TÊN_XÉT_NGHIỆM **không được mang assertion** (`check()` chặn) → cuối cùng
assertions rỗng. Mã: LAB theo tiền lệ `GT[69]`/`GT[179]`/`GT[274]`
("chụp cắt lớp vi tính (ct)"); ở đây bản dịch cắt ngắn còn "chụp cắt lớp".

**6. Không gán ở block 164:** "phẫu thuật tạo hình vành tai", "tạo hình ống tai
ngoài" (thủ thuật — tiền lệ `GT[59]` "ghép gan", `GT[9]` "Thở oxy tại nhà");
"thiết bị trợ thính đường xương", "sụn sườn tự thân", "sụn nhân tạo" (thiết
bị/vật liệu); "Về thính lực,", "Về thẩm mỹ," (từ dẫn chủ đề — **khác** `GT[19]`
cùng nguồn, ở đó bề mặt là "đo thính lực" = tên xét nghiệm thật); "đôi tai hoàn
thiện", "cấu trúc tai giữa" (giải phẫu/kết quả bình thường, tiền lệ `GT[12]` bỏ
"cấu trúc tai trong ... phát triển tốt").

**7. Block 209 = bản dịch NGẮN của đoạn đã gán trong `GT[35]`.** Tái dùng nguyên
3 quyết định: `doxycycline`[0] + `bactrim`[0] gán **riêng hai nhãn nằm trong từ
dính** `doxycyclinebactrim` (lỗi dịch mất dấu cách) → 3640 / 151399, và
`Viêm mô tế bào` → L03.3. **Khác** `GT[109]` gán trọn `vancozosynbactrim` làm
một THUỐC candidates rỗng — ở đó dính 3 thuốc và không có bản dịch rời để đối
chiếu; ở đây có `GT[35]` làm chuẩn.

**8. "không muốn ngừng chúng" → KHÔNG isNegated.** Đó là ý muốn của bệnh nhân,
thuốc **vẫn đang dùng**. Khác tiền lệ `GT[16]` "đã hết thuốc" (Isosorbide, NEG)
= thực sự đã dừng. Cũng không gán "những loại thuốc này" (nhắc lại, không nêu
tên), "Khoa Cấp cứu", "bác sĩ Truyền nhiễm" (cơ sở/chuyên khoa).

### Kiểm tra citation (3 lỗi, đã sửa)

Vẫn dùng script quét ngược `needle → GT[n]`. Ba citation viết sai trong lượt đầu:

| viết sai | chủ thật |
|---|---|
| `GT[29]` "nghi ngờ cơn co giật" | `GT[26]` |
| `GT[122]` "kết quả nghi ngờ thiếu men G6PD" | `GT[205]` |
| `GT[198]` "đã hết thuốc" | `GT[16]` |
| `GT[38]`/`GT[54]` "chụp cắt lớp vi tính (ct)" | `GT[69]`/`GT[179]`/`GT[274]` |

Ba trong bốn lỗi là **citation theo ký ức** (nhớ nội dung đúng nhưng số block
sai) — bằng chứng nữa rằng phải quét ngược mọi `GT[n]` trước khi ghi, không được
tin ký ức. Riêng "chụp cắt lớp vi tính (ct)" thì bề mặt tồn tại nhưng ở 3 block
khác hẳn số đã đoán.

### Kiểm tra offset

`data/gt_block/12.json`: **34 entity, 0 lệch**. `15.json`: **37 entity, 0 lệch**
(kiểm chéo vì block 22 dùng chung 2 file, và `SHARE[82]`/`GT[35]` cùng bệnh án).
Xác nhận `doxycycline`+`bactrim` trong 12.json nằm liền kề đúng trong từ dính:
`[2507,2518]` + `[2518,2525]`.

### Còn lại sau đợt 14

**91 block / 18662 ký tự (9.85%).** Xếp hàng theo số ký tự chưa gán: 91.txt
(824c, 2 block), 18.txt (821c, **10 block** — phân mảnh nhất), 78.txt (791c, 2),
13.txt (790c, 2), 88.txt (788c, 3), 5.txt (777c, 2), 60.txt (737c, 3), 49.txt
(734c, 4), 77.txt (697c, 4), 92.txt (678c, 3), 54.txt (664c, 2), 40.txt (616c, 2),
25.txt (574c, 2), 70.txt (520c, 2), 46.txt (482c, 3), 58.txt (468c, 3), 33.txt
(451c, 2), 38.txt (422c, 1).

---

## Đợt 15: gán TRỌN file 91.txt (2 block) — 90.2% → 90.6%

**Trạng thái**: xong. Đo bằng `python3 src/gt_blocks.py` sau khi gán:
`block_da_gan 243 / 332`, `ky_tu_da_gan 171598 / 189436`, `phu_ky_tu 0.9058`,
`entity 2644` → chiếu ra 100 file / 3120 entity.

File `91.txt` là MỘT bệnh án (hội chứng Turner / tăng huyết áp / cắt đại tràng do
ung thư / thuyên tắc phổi đang dùng coumadin, vào viện vì khó thở), bị GHÉP một
mẩu QA về sỏi niệu quản vào **giữa dòng 31**. Mục 2 (HPI) đã gán từ trước ở
`GT[129]`; đợt này gán 2 block còn lại.

| block | ký tự | ×lần | nội dung | nhãn mới |
|---|---|---|---|---|
| 187 | 363 | 1 | mục "1. Tiền sử bệnh": bệnh lý mãn tính + thuốc trước nhập viện | 5 |
| 154 | 461 | 1 | mục "3. Đánh giá tại bệnh viện" + mẩu QA sỏi niệu quản chèn giữa | 6 |

Tổng **11 nhãn mới**. Sau đợt này `91.txt` phủ 100% (29 entity, 0 lệch offset —
kiểm bằng so `raw[start:end]` với `text` trên `data/gt_block/91.json`).

### Các quyết định gán nhãn

**1. Mẩu QA chèn vào là câu KIẾN THỨC CHUNG → không assertion, dù cuối đoạn mới
lộ ra bệnh nhân là CHỒNG người hỏi.** Đây là quyết định khó nhất của đợt. Nguyên
văn: *"Sỏi niệu quản lớn hơn 7mm thường không điều trị nội khoa được. … Bạn nên
đưa chồng tới bệnh viện khám và tiến hành phẫu thuật."*

Đã cân nhắc `isFamily` theo tiền lệ `GT[53]` (đoạn QA về **vợ** bệnh nhân →
`giãn phế quản` + `azithromycin` đều mang `isFamily`). **Loại**, vì hai chỗ khác
nhau về chủ thể của bề mặt: ở `GT[53]` câu được gán là chẩn đoán *của chính người
vợ*, còn ở đây bề mặt `Sỏi niệu quản` nằm trong một **câu quy tắc** ("… lớn hơn
7mm **thường** không điều trị nội khoa được"), không phải chẩn đoán của người
chồng. Theo tiền lệ `GT[72]` (QA sàng lọc thai: *"câu nói chung về mọi thai kỳ,
không phải chẩn đoán của một người cụ thể → không gán assertion"*), `GT[55]`
(danh sách tác dụng phụ = kiến thức chung), `GT[84]`, `GT[75]` (đoạn giảng nguyên
nhân chung).

Quy tắc rút ra, bổ sung cho quy tắc "thân nhân → isFamily": **assertion theo chủ
thể của BỀ MẶT, không theo chủ thể của đoạn văn.** Một đoạn QA có thể vừa có câu
quy tắc chung (không assertion) vừa có chẩn đoán của thân nhân (isFamily).

**2. `tổn thương chức năng thận` → N28.9, và KHÔNG isNegated.** Đây là hậu quả
*nếu không điều trị* ("nếu để lâu hơn sẽ làm tổn thương chức năng thận nhiều").
Theo tiền lệ `GT[174]` (đúng nhan đề "hậu quả nếu không điều trị", gán đủ
`thiếu máu tan huyết`/`vàng da sơ sinh`/`tan huyết` không NEG) và `GT[197]`.
Khác `GT[106]` nơi biến chứng được nêu để **PHÒNG** → isNegated.

Chọn mã: tra danh mục BYT **không có** mục nào tên "tổn thương chức năng thận".
Đã loại `N19` "Suy thận không xác định" (bề mặt nói *tổn thương chức năng*, chưa
nói **suy** — khác `GT[77]` "Không có suy thận" → N19) và `S37.0` "tổn thương
thận" (là chấn thương ngoại lực, sai hoàn toàn ngữ cảnh). Chốt `N28.9` "Rối loạn
của thận và/hoặc niệu quản, không xác định", theo tiền lệ `GT[75]`
`suy giảm chức năng gan` → `K72.9` — cùng một khuôn: **mã .9 "không xác định" của
cơ quan tương ứng khi bề mặt chỉ nói "suy giảm/tổn thương chức năng"**.

**3. `coumadin` → warfarin IN 11289.** `grep -ci coumadin data/raw/rxnorm/RXNCONSO.RRF`
= **0** — Coumadin không có trong RxNorm dù là biệt dược Mỹ rất phổ biến (bản
RRF này chỉ chứa subset). Dùng mã hoạt chất `warfarin` IN 11289, theo tiền lệ
`GT[326]` `Omez` → omeprazole IN 7646 và `GT[35]` `Pimperan` → 6915. Nhắc lại
thứ tự ưu tiên đã chốt: **BN nếu có** (`GT[182]` eliquis 1364436, `GT[63]`
tylenol 202433) → **IN nếu không có BN** → **rỗng nếu cả hai đều không có**
(`GT[125]` Vastarel).

**4. `Thuyên tắc phổi` và `coumadin` dùng `ALL` vì dòng 6 TỰ LẶP CHÍNH NÓ.**
Nguyên văn dòng 6: `- Tiền sử Thuyên tắc phổi đang dùng coumadin (tiền sử Thuyên
tắc phổi đang dùng coumadin)`. Lỗi dịch máy lặp nguyên khối trong ngoặc → 2 lần
`Thuyên tắc phổi`, 3 lần `coumadin` (2 ở dòng 6 + 1 ở "Thuốc trước khi nhập
viện"). Dùng `ALL` như `GT[143]` xử cụm sinh hiệu lặp nguyên khối. Recall là toàn
bộ vấn đề nên phải gán cả bản trong ngoặc.

**5. Giữ TRỌN đuôi `, không đặc hiệu` trong bề mặt.** `hội chứng turner, không
đặc hiệu` → Q96.9. Theo quy ước đã chốt qua 10 chủ: `GT[87]`/`GT[88]`
`tăng lipid máu, không đặc hiệu` → E78.5, `bệnh thận mạn, không đặc hiệu Giai
đoạn 4` → N18.4, `GT[142]`/`GT[94]`/`GT[45]`/`GT[42]` `hạ huyết áp, không đặc
hiệu` → I95.9, `GT[13]` `bệnh phổi tắc nghẽn mạn tính, không xác định` → J44.9.
Đây **không** đụng quy ước 6 đợt 13 (cắt hậu tố đo lường) vì ", không đặc hiệu"
là phần **tên bệnh trong danh mục**, không phải số đo.

Q96.9 đúng mã vì 6 mã con còn lại của Q96 (Q96.0–Q96.4, Q96.8) đều đòi **công
thức nhiễm sắc thể cụ thể** (45,X / 46,X iso(Xq) / thể khảm …), bề mặt không nêu.

**6. `Sỏi niệu quản`: cắt "lớn hơn 7mm" khỏi bề mặt.** Quy ước 6 đợt 13 (hậu tố
đo lường thì cắt): tiền lệ `GT[140]` "Sốt ≥5 ngày" → `Sốt`, `GT[276]` "Hạch cổ to
≥1,5 cm" → `Hạch cổ to`. N20.1 "Sỏi niệu quản" trùng nguyên văn tên mã.

**7. `hr` → TÊN_XÉT_NGHIỆM (bề mặt mới của corpus).** `hr` = heart rate chưa
dịch. Bề mặt viết tắt là nhãn riêng theo tiền lệ `GT[137]`/`GT[93]` (`HA`),
`GT[162]`/`GT[91]` (`M`), `GT[61]`/`GT[53]` (`spo2`). Cùng loại LAB với
`nhịp tim` ở `GT[143]`. Trị số `110` → VAL dù trơ số, theo tiền lệ `GT[115]`
(`478`/`20`/`13`/`316`) và `GT[94]` (`28` trong "ổn định ở mức 28").

**8. `albuterolipratropium` → candidates RỖNG, tái dùng Y NGUYÊN `GT[128]`.**
Cùng một bề mặt dính 2 tên thuốc do lỗi dịch. Rỗng vì RxNorm không có cụm dính,
và trong block **không có** lần xuất hiện rời của `albuterol`/`ipratropium` để
tách nhãn — khác `GT[209]` `doxycyclinebactrim` (đợt 14) nơi có bản dịch rời
trong `GT[35]` để đối chiếu nên tách được 2 nhãn.

**9. Không gán, và lý do:**
- `phẫu thuật cắt bỏ đại tràng`, `Cắt đại tràng nhiều năm trước`, `điều trị nội
  khoa`, `can thiệp phẫu thuật`, `phẫu thuật` (2 lần): thủ thuật → chỉ lấy chẩn
  đoán trong câu (tiền lệ `GT[13]` bỏ "Phẫu thuật mở cắt nối trực tràng/đại tràng
  sigma" cùng mục, `GT[182]` bỏ "phẫu thuật cắt bỏ tuyến tiền liệt",
  `GT[142]`/`GT[94]`/`GT[45]` bỏ "Truyền dịch tĩnh mạch").
- `nebs x2`: dạng dùng/số lần → không gán.
- `cải thiện`: mức độ, không phải khái niệm.
- `cảm thấy khỏe`: trạng thái BÌNH THƯỜNG → không gán (tiền lệ `GT[143]` "điện
  tâm đồ bình thường" không gán VAL, `GT[141]`/`GT[68]`/`GT[133]`).
- Tiêu đề "3. Đánh giá tại bệnh viện", "Các thủ thuật đã thực hiện", "Các bệnh lý
  mãn tính": tiêu đề mục → không gán (tiền lệ `GT[132]`/`GT[94]`/`GT[22]`).

### Mã đã kiểm chứng

Qua `entries[code]['vi']` từ `load_icd()`: `Q96.9` "Hội chứng Turner, không xác
định", `I10` "Bệnh tăng huyết áp vô căn (nguyên phát)", `C18.9` "U ác tính ở đại
tràng, không xác định", `I26.9` "Thuyên tắc mạch phổi không có tâm phế cấp tính",
`N20.1` "Sỏi niệu quản", `N28.9` "Rối loạn của thận và/hoặc niệu quản, không xác
định". Đã **loại** `N19`, `S37.0`, `N17.9`.

RxNorm qua `RXNCONSO.RRF`: `warfarin` IN = **11289**, `metoprolol` IN = **6918**.
Xác nhận `coumadin` = **0 dòng**.

### Sửa citation sai chủ (6 chỗ)

Audit bằng script reverse-map `needle → GT[n]` như đợt 14. Lần này **6 chỗ sai**,
nhiều hơn đợt 14 (4 chỗ):

| tôi ghi | chủ thật | nội dung |
|---|---|---|
| `GT[132]` | `GT[75]` | "suy giảm chức năng gan" → K72.9 |
| `GT[102]` | `GT[77]` | "Không có suy thận" → N19 |
| `GT[321]` | `GT[276]` | "Hạch cổ to ≥1,5 cm" → "Hạch cổ to" |
| `GT[143]` | `GT[61]`/`GT[53]` | `spo2` (GT[143] dùng `SpO2` hoa) |
| `GT[13]` | `GT[182]` | "phẫu thuật cắt bỏ tuyến tiền liệt" |
| `GT[143]` | `GT[142]`/`GT[94]`/`GT[45]` | "Truyền dịch tĩnh mạch" |

Nguyên nhân giống đợt 14: **trích dẫn theo ký ức** — đúng nội dung, sai số block.
`GT[132]`/`GT[143]` sai vì đó là block *nhắc lại* tiền lệ chứ không phải block
*đặt ra* tiền lệ; script chỉ grep chuỗi nên bắt được cả dòng comment. Bài học rõ
hơn: khi grep ra nhiều chủ, phải phân biệt **dòng nhãn** (`("x", 0, DX, …)`) với
**dòng comment trích dẫn**, chủ thật luôn là dòng nhãn.

### Còn lại

**89 block / 17838 ký tự (~9.4%)**. Xếp theo số ký tự CHƯA gán mỗi file: 18.txt
(821c, **10 block** — phân mảnh nhất), 78.txt (791c, 2), 13.txt (790c, 2), 88.txt
(788c, 3), 5.txt (777c, 2), 60.txt (737c, 3), 49.txt (734c, 4), 77.txt (697c, 4),
92.txt (678c, 3), 54.txt (664c, 2), 40.txt (616c, 2), 25.txt (574c, 2), 70.txt
(520c, 2), 46.txt (482c, 3), 58.txt (468c, 3), 33.txt (451c, 2), 38.txt (422c, 1),
31.txt (395c, 1), 56.txt (383c, 1), 66.txt (355c, 1).

## Đợt 16: gán TRỌN file 18.txt (10 block) — 90.6% → 91.0%

Chọn 18.txt vì đứng đầu hàng đợi theo ký tự chưa gán (821c) và là file **phân mảnh
nhất còn lại**: 10 block, block lớn nhất chỉ 150c, nhỏ nhất 12c.

### Phát hiện quyết định: 18.txt là ĐUÔI của chính bài giảng CAD ở 26.txt

Vào đợt này tôi mang theo từ trước niềm tin "nửa bài giảng của 18.txt là cùng bài
CAD với 26.txt, mà 26.txt đã gán 100%" — hàm ý **có text trùng**, có thể dùng
`SHARE`. Kiểm lại bằng grep toàn bộ tiêu đề mục của 18.txt trong 26.txt:

```
grep -n 'Cận lâm sàng|Điện tâm đồ|Men tim|Siêu âm tim|Chụp mạch|Mục tiêu|nội khoa|Can thiệp|bắc cầu|Dự phòng bệnh' input/26.txt
```

→ chỉ ra **1 dòng duy nhất**: "Xảy ra khi gắng sức". 26.txt (92 dòng) phủ mục 1–3 +
"Dự phòng thứ phát"; 18.txt (dòng 1–54) phủ **mục 4 "Cận lâm sàng" → mục 5 "Điều
trị" → mục 6 "Dự phòng tiên phát"**. Tức là hai file cắt **hai khúc khác nhau** của
cùng một bài giảng. Kết luận: **quy ước và mã ICD chuyển sang được, bề mặt thì
không** → không `SHARE` được, phải viết mới toàn bộ nhãn.

Dòng 55–85 của 18.txt là bệnh án viêm túi mật cấp, đã gán từ đợt trước ở `GT[78]`
và `GT[110]` — không chạm vào.

### Header quy ước cấp file

Viết header cho cả file 18.txt theo mẫu header 26.txt, chốt: **dùng lại Y NGUYÊN**
quyết định của 13 block 26.txt để không tự mâu thuẫn với chính nguồn. Mã tái dùng:
`bệnh mạch vành` → `I25.9` (`GT[299]`/`GT[197]`), `hẹp` mạch vành → `I25.1`
(`GT[197]`/`GT[232]`/`GT[140]`), `nhồi máu (cơ tim)` → `I21.9`
(`GT[197]`/`GT[140]`/`GT[124]`), `thiếu máu cơ tim` → `I25.9` (`GT[140]`/`GT[76]`).
Nửa bài giảng **KHÔNG assertion** (không có bệnh nhân cụ thể).

### 10 block

| block | ký tự | nội dung | nhãn |
|---|---|---|---|
| 252 | 150 | điều trị nội khoa, 7 tên thuốc bị mask | 7 |
| 259 | 137 | CABG + tiêu đề mục 6 | 1 |
| 280 | 99 | chụp mạch vành + tiêu đề "Điều trị" | 2 |
| 292 | 81 | can thiệp PCI | **0** |
| 293 | 79 | mục tiêu điều trị | 3 |
| 296 | 74 | điện tâm đồ | 4 |
| 301 | 69 | siêu âm tim | 2 |
| 305 | 63 | nghiệm pháp gắng sức | 2 |
| 312 | 57 | men tim | 4 |
| 331 | 12 | đúng 1 dòng "Cận lâm sàng" | `DONE_EMPTY` |

Tổng **25 entity** cho 821 ký tự — mật độ thấp hơn hẳn mức trung bình (~1 entity /
33c) vì đây là phần điều trị/can thiệp, đầy **thủ thuật và tiêu đề** chứ không phải
tên bệnh.

### Hai block không có (hoặc gần như không có) khái niệm

**Block 292 = 0 nhãn.** Toàn bộ 81c là "Can thiệp – phẫu thuật / Can thiệp mạch
vành qua da (PCI) / Nong bóng / Đặt stent": 1 tiêu đề + 3 thủ thuật, và trong câu
**không có tên bệnh nào** để lấy ra. Không dùng `DONE_EMPTY` mà khai `GT[292] = []`
tường minh để giữ lại lý do ngay tại chỗ (khác block 331 chỉ là 1 dòng tiêu đề
trơ, giống hệt block 0 nên `DONE_EMPTY` là đúng chỗ).

Điểm này đáng ghi: `PCI`/`CABG`/`Nong bóng`/`Đặt stent` **không gán**, theo chuỗi
tiền lệ thủ thuật (`GT[117]` "ba stent mật kim loại đã được đặt", `GT[106]` "đặt
shunt dẫn lưu tĩnh mạch cửa qua da", `GT[141]`/`GT[97]` "Phẫu thuật cắt cụt chân",
`GT[13]` "Phẫu thuật mở cắt nối trực tràng/đại tràng sigma"). **Khác** `GT[91]`
`stent mạch vành` → `Z95.5`: ở đó là **tiền sử ĐÃ ĐẶT của một bệnh nhân** (mã Z =
trạng thái có dụng cụ trong người), còn ở đây là **tên phương pháp trong bài
giảng** — không có ai mang stent.

### Phát hiện trên thăm dò: VAL hay DX?

Đây là quyết định khó nhất của đợt. Bài giảng liệt kê 3 nhóm phát hiện:

1. **Hình thái sóng trên ECG** (`ST chênh lên / chênh xuống`, `Sóng T đảo`,
   `Q bệnh lý`) → **KẾT_QUẢ_XÉT_NGHIỆM**. Tiền lệ duy nhất và trực tiếp:
   `GT[76]:3392` gán `ST chênh xuống` là `VAL` (kết quả của nghiệm pháp gắng sức).
2. **Trạng thái bệnh lý đọc được trên hình** (`Rối loạn vận động vùng`) →
   **CHẨN_ĐOÁN**. Tiền lệ: `GT[92]:2863` `Buồng thất trái giãn` → `I42.0`,
   `GT[92]:2864` `chức năng tâm thu thất trái giảm nhiều` → `I50.9`, `GT[47]:3545`
   `dị tật cố định vùng trước vách và vách dưới` → DX candidates rỗng.
3. **Việc cần LÀM của thăm dò** (`Đánh giá chức năng thất trái`, `Phát hiện …`,
   `Quyết định can thiệp`) → **không gán**. Tiền lệ `GT[195]:1364` "(quan trọng
   nhất để đánh giá động mạch vành)", `GT[155]:1253` "đánh giá thần kinh".

Ranh giới rút ra: **mô tả hình/sóng đọc được = VAL; trạng thái bệnh lý = DX; việc
cần làm = không gán.**

### `Rối loạn vận động vùng` → I25.5 (quyết định có rủi ro)

Tra `names` từ `load_icd()`: `'vận động vùng'` → **0 kết quả**; `'giảm động'`,
`'vô động'` → 0; `'vận động'` → 63 kết quả nhưng **toàn bộ là thần kinh/tâm thần**
(F44.4, F82, G11.x…), không có mục nào về vận động thành tim. Danh mục ICD-10 tiếng
Việt **không có** mục cho rối loạn vận động vùng cơ tim.

Chọn `I25.5` "Bệnh lý cơ tim do thiếu máu cục bộ" vì đây chính là vùng cơ tim mất
vận động do thiếu máu, đúng bối cảnh bài CAD. Đã **loại**: `I51.9`/`I51.8` (bệnh
tim không xác định — mất thông tin nguyên nhân vành), `I50.1` (đã dành cho **rối
loạn CHỨC NĂNG** thất trái ở `GT[47]:3547`, khác vận động vùng), `I25.3` "phình
thành tim" (khác bệnh).

Đây là chỗ tôi đi xa hơn tiền lệ nhất trong đợt: `GT[47]`/`GT[92]` có 2 trường hợp
để **candidates rỗng** khi không tìm được mã (`dị tật cố định vùng trước vách`,
`Thất phải giãn`). Tôi chọn gán mã thay vì rỗng vì `I25.5` mô tả đúng cơ chế, và
theo công thức chấm thì candidates sai chỉ giảm Jaccard của khái niệm đó, còn để
rỗng khi ground truth có mã thì cũng mất đúng bằng đó. **Cần audit lại** khi có
validation split.

### Bề mặt: cắt gì, giữ gì

- `Điện tâm đồ` — bỏ `(ECG)`. Ngoặc chứa **tên tiếng Anh của chính nhãn** → không
  gán riêng, tiền lệ `GT[299]` bỏ "(Coronary Artery Disease – CAD)". **Khác**
  `GT[195]:1363` `ECG điện tâm đồ` nơi 2 tên **dính liền** thành 1 cụm không ngoặc.
  Cùng cách xử lý cho `(PCI)`, `(CABG)`.
- Ngoặc chứa **nhận định** (`(tiêu chuẩn vàng)`, `(chẩn đoán nhồi máu)`, `(ổn định
  mảng xơ vữa)`, `(chưa mắc bệnh)`) → không gán cả cụm, tiền lệ `GT[140]:1893`
  "(nguy hiểm nhất)" + `GT[195]:1364`. **Ngoại lệ**: ngoặc có nêu **tên bệnh** thì
  vẫn lấy tên bệnh ra làm bề mặt — `(chẩn đoán nhồi máu)` → gán `nhồi máu` I21.9,
  tiền lệ `GT[182]:1696` lấy "(cho rung nhĩ)".
- `thiếu máu cơ tim` — cắt đuôi `khi gắng sức` (điều kiện xuất hiện, cùng loại với
  "Xảy ra khi gắng sức" mà `GT[308]:1664` không gán). Quy ước cắt hậu tố đo
  lường/điều kiện: `GT[140]:1907` "Sốt ≥5 ngày" → "Sốt", `GT[276]:1304` "Hạch cổ to
  ≥1,5 cm" → "Hạch cổ to".
- `hẹp` — cắt `vị trí – mức độ` (thuộc tính cần xác định, không phải phần tên bệnh).
- `đau` / `tử vong` — bỏ động từ `Giảm`. Tiền lệ `đau` trơ: `GT[63]:362`,
  `GT[33]:3930`. Tiền lệ `tử vong` → SYM candidates rỗng: `GT[30]:4028`,
  `GT[118]:3413`, `GT[120]:3428`. Tiền lệ bỏ động từ: `GT[172]:1717` gán `stress`
  trong "Giảm stress".
- `ST chênh lên / chênh xuống` — giữ **TRỌN** cụm 2 vế gạch chéo thành 1 bề mặt,
  tiền lệ `GT[22]:113` "Bệnh thủy đậu/Zona", `GT[61]:435`/`GT[53]:631` "buồn
  nôn/nôn". `Troponin I/T` giữ trọn tương tự (2 isoform 1 xét nghiệm), như
  `GT[136]:2076` giữ "(aPTT / TCK)".
- `Dự phòng bệnh mạch vành` — lấy **trọn cụm tiêu đề** thay vì chỉ `bệnh mạch
  vành`, để bao lần xuất hiện duy nhất của chuỗi con, tránh nhãn lồng. Tiền lệ
  `GT[140]:1895` "Phình giãn động mạch vành" đã chứa "động mạch vành" nên không
  khai riêng. Việc **gán tiêu đề** khi tiêu đề chứa tên bệnh: `GT[233]:1650` gán
  tiêu đề "Đau thắt ngực".

### `Men tim` → LAB, ngược với `GT[136]`

`GT[136]:2085` ghi rõ "Sinh hóa & Men tim:" là **tiêu đề NHÓM → không gán**. Ở
18.txt tôi **gán** `Men tim` là LAB. Lý do: ở `GT[136]` nó là nửa của một nhãn ghép
2 nhóm xét nghiệm ("Sinh hóa &…"), còn ở đây `Men tim` đứng một mình làm chính tên
mục xét nghiệm được chỉ định, đúng tình huống `GT[195]:1356` gán `Men gan` là LAB
với ghi chú "ở đây là TÊN xét nghiệm được chỉ định". Ghi ra đây vì đây là **cặp
quyết định trái nhau trên bề mặt gần giống nhau** — nếu audit sau này thấy sai thì
sửa ở 18.txt (mới hơn), không sửa `GT[136]`.

### Không gán, và lý do

- `↑` đứng một mình sau tên men tim: kết quả bằng **ký hiệu**, không có trị số →
  không gán VAL. Tiền lệ `GT[232]` "tăng" đứng một mình cũng không gán, và quy ước
  chốt "8/8 KẾT_QUẢ_XÉT_NGHIỆM đều là số + đơn vị" (`GT[29]`).
- `Cải thiện tưới máu tim`: tưới máu tim **bình thường** là đích cần đạt, không
  phải khái niệm bệnh → không gán. Khác `GT[197]:1610` `giảm tưới máu cơ tim` là
  trạng thái bệnh lý nên mới gán.
- `Khi tổn thương nhiều nhánh, nặng`: chỉ định/mức lan của bệnh, không phải tên
  bệnh → không gán. Tiền lệ `GT[140]:1900` không gán "Khoảng 25–30% trẻ không điều
  trị đúng cách". **Khác** `GT[47]:3549` `bệnh ba thân động mạch vành nghiêm trọng`
  — cụm đó có chữ "bệnh" nên là tên chẩn đoán.
- `mảng xơ vữa` trong "(ổn định mảng xơ vữa)": bước cơ chế → không gán, quy ước
  chốt ở `GT[232]:1623` cùng bài.
- Tiêu đề: `Cận lâm sàng`, `Điều trị`, `Mục tiêu`, `Điều trị nội khoa`, `Thuốc nền
  tảng`, `Can thiệp – phẫu thuật`, `Dự phòng tiên phát` → không gán
  (`GT[136]`/`GT[140]`).

### `Ngăn nhồi máu` → KHÔNG isNegated

Cân nhắc kỹ vì có tiền lệ hai chiều. `GT[106]:2657` gán isNegated cho biến chứng
nêu ra **để phòng ngừa** ("để tránh sẩy thai, sinh non, tiền sản giật"),
`GT[172]:1715` gán isNegated cho "Không hút thuốc". Nhưng cả hai đều có **bệnh nhân
/ người hỏi cụ thể**. Ở đây "Ngăn nhồi máu" là **mục tiêu điều trị trong bài
giảng**, không gắn với ai → theo quy ước "bài giảng không assertion" của chính file
26.txt, và theo `GT[140]` liệt kê biến chứng Kawasaki "có thể gây" mà **không**
isNegated. → assertions rỗng.

### 7 dãy sao ở block 252

Đo bằng `re.finditer(r'\*+')` trên text block: **7 run, độ dài 7 / 11 / 6 / 9 / 13
/ 17 / 3** — không có 2 run nào cùng độ dài. Mỗi độ dài là 1 bề mặt riêng, `DRUG`,
candidates rỗng. An toàn vì `_find_occurences` khớp **trọn run sao**, không khớp
substring trong run dài hơn. Kiểm bằng `--occ`: cả 7 đều đúng 1 lần.

Census toàn bộ nhãn dãy sao trong `gt_blocks.py` sau đợt này: **64 nhãn**, tất cả
`DRUG` candidates rỗng, không có ngoại lệ. Tiền lệ gần nhất về "nhiều mask trong 1
block, độ dài khác nhau → nhãn riêng": `GT[76]` (5 dãy), `GT[159]` (7 dãy),
`GT[24]` (9 dãy), `GT[176]:1563` ghi rõ "độ dài khác -> nhãn riêng".

### Kiểm chứng

- `--occ` **mọi needle trước khi viết**: tất cả trả về đúng 1 lần (kể cả 7 dãy sao).
- Rebuild + đối chiếu `data/gt_block/18.json` với `input/18.txt` sau NFC: **65
  entity, 0 lệch offset**.
- Mã ICD qua `entries[code]['vi']`: đã kiểm 16 mã họ I2x/I5x. Dùng: `I25.5`, `I25.1`,
  `I25.9`, `I21.9`. Loại: `I51.9`, `I51.8`, `I50.1`, `I25.3`.
- Audit citation bằng reverse-map `needle → GT[n]`, chạy **trước** khi viết (thủ tục
  từ đợt 14) rồi chạy lại sau khi viết. Lần này **1 chỗ sai**: tôi ghi
  `GT[91]/GT[9]` cho `stent mạch vành` → `Z95.5`, thực tế **chỉ `GT[91]`** có (2
  lần, dòng 2912/2926), `GT[9]` không có. Đã sửa. Ít hơn hẳn đợt 15 (6 chỗ) và đợt
  14 (4 chỗ) — chạy audit trước khi viết có tác dụng.

### Còn lại

**79 block / 17017 ký tự (~9.0%)**. Xếp theo số ký tự chưa gán mỗi file: 78.txt
(791c, 2 block), 13.txt (790c, 2), 88.txt (788c, 3), 5.txt (777c, 2), 60.txt (737c,
3), 49.txt (734c, 4), 77.txt (697c, 4), 92.txt (678c, 3), 54.txt (664c, 2), 40.txt
(616c, 2), 25.txt (574c, 2), 70.txt (520c, 2).

## Đợt 17: gán TRỌN file 78.txt (2 block) — 91.0% → 91.4%

File 78.txt = 3 nguồn ghép: (1) câu hỏi người bệnh về **chảy máu cam**, (2) một mẩu
EHR **nhiễm trùng vết mổ** chèn vào giữa, (3) bài phổ biến kiến thức chảy máu mũi.
Block 0 và 111 đã gán từ trước; đợt này gán 2 block còn lại → **trọn file**.

| block | ký tự | nội dung | nhãn |
|---|---|---|---|
| 171 | 418 | câu hỏi người bệnh về chảy máu cam | 4 khai → 5 entity |
| 183 | 373 | mẩu EHR nhiễm trùng vết mổ (diễn biến + hiện tại) | 4 khai → 6 entity |

### Phát hiện quan trọng: 2 quan hệ tiền tố/hậu tố mới, tìm bằng tay

Kết luận cũ ở đợt trước là "SHARE đã cạn" (ngưỡng tiền tố ≥120 ký tự NFC → 0 hit,
union-find → 0 cluster). Đợt này tìm thấy **2 quan hệ mà quét tự động bỏ sót**:

- **Block 183 (78.txt, 373c) là HẬU TỐ của block 40 (25.txt, 1820c)** — kiểm bằng
  `t40.endswith(t183)` = True, bắt đầu ở index 1447, đuôi rỗng. `expand_share()`
  **chỉ nhận tiền tố** nên không dùng được → phải gán tay, nhưng **dùng lại y nguyên
  6 nhãn tương ứng của `GT[40]`** (gộp thành 4 khai nhờ `ALL`) để hai file không lệch.
- **Block 294 (25.txt, 77c) là TIỀN TỐ của block 111 (78.txt, 703c)** — kiểm bằng
  `t111.startswith(t294)` = True. Cái này **SHARE được**: `SHARE[294] = (111, 77)`,
  để dùng khi tới đợt 25.txt.

Bài học: quét tự động chỉ tìm tiền tố dài. Trước mỗi đợt nên kiểm cả **hậu tố** và
cả **block ngắn nằm trọn trong block dài**, bằng `in` / `startswith` / `endswith`.

### Census bề mặt phủ định: cả 2 cách đều có tiền lệ

Vấn đề: `GT[40]` (nguồn của block 183) giữ nguyên bề mặt `"không sốt"` + `[NEG]`,
còn `GT[111]` **cùng file 78.txt** lại gán `"sốt"` + `[NEG]`. Chọn cách nào?

Đo: **173 nhãn** mang `NEG`, trong đó chỉ **11 nhãn** giữ từ phủ định trong bề mặt
(`không bị đau`, `không còn bị đau`, `không ứ nước`, `không đau` ×2, `không sốt`,
`không có khó chịu vùng ngực`, `không có tiếng rales bệnh lí`,
`Không có điểm đau`, `Không phù`, `không có hình ảnh tổn thương viêm cấp tính`).

→ Cả 2 cách đều có tiền lệ, nên **ưu tiên khớp với NGUỒN của chính block**:
`GT[183]` giữ `"không sốt"` theo `GT[40]`, `GT[111]` giữ `"sốt"` như đã chốt. Hai
nguồn EHR khác nhau, mỗi bên nhất quán nội bộ. Đây là quy ước mới: **khi block là
bản sao/đuôi của một block đã gán, nguồn thắng quy ước chung của file**.

### `chảy máu cam` → TRIỆU_CHỨNG dù ICD có `R04.0`

`R04.0 "Chảy máu cam"` (Epistaxis) **có thật** trong `icd10_danh_muc.csv`. Vẫn gán
`TRIỆU_CHỨNG`: `GT[111]` cùng file đã gán `chảy máu mũi` là SYM, và chuỗi tiền lệ
chảy máu đều là SYM (`GT[106]` "chảy máu khó cầm", `GT[76]`, `GT[119]`). **Nhất
quán trong file thắng việc "có mã ICD"** — vì điểm `text` tính theo cặp (bề mặt,
type), sai type mất điểm gấp đôi, còn `candidates` chỉ là 0.4 phần và cặp không
khớp thì mã đúng cũng vô nghĩa.

### Chỉ số lần xuất hiện: cẩn thận nhãn lồng nhau

`GT[171]` cần gán `"chảy"` đứng một mình ("cứ khô nóng là cháu chảy"). `--occ` cho
`chảy` = **4 lần**: [0] và [2] nằm trong `chảy máu cam`, [1] nằm trong
`chảy ở mũi bên phải` → lần đứng một mình là **index 3**. Không đếm bằng mắt được,
phải chạy `--occ` rồi đối chiếu vị trí từng lần.

Lỗi dịch dính chữ `"bịchảy máu cam"` → bề mặt chỉ lấy `chảy máu cam` (tiền lệ
`GT[108]` "lây nhiễm bệnh dạibao gồm" → chỉ lấy `bệnh dại`, `GT[182]`
"nhập viện gần đây vìviêm tụy" → chỉ lấy `viêm tụy`).

### Kiểm chứng

- `--occ` mọi needle trước khi viết. Block 171: `chảy máu cam` ×2, `chảy` ×4,
  `bịchảy máu cam` ×1, `choáng` ×1, `chảy ở mũi bên phải` ×1. Block 183:
  `ban đỏ` ×2, `chóng mặt` ×2, `đau khi sờ nắn` ×1, `sốt` ×1, `không sốt` ×1.
- Rebuild + đối chiếu `data/gt_block/78.json`: **22 entity, 0 lệch offset**.
- Audit citation reverse-map trước khi viết: **0 chỗ sai**.

## Đợt 18: gán TRỌN file 13.txt (2 block) — 91.4% → 91.9%

File 13.txt = QA "dính nước dãi chó con có bị dại không" + bài giảng bệnh dại, bị
ghép một mẩu EHR tim mạch vào giữa (dòng 20–21). Block 0/120/108/139 đã gán; đợt
này gán 2 block còn lại → **trọn file**.

### Phát hiện: 170 và 184 là BẢN DỊCH KHÁC của block 10 và 11 (đã gán)

Tìm bằng cách grep cụm đặc trưng của block chưa gán ra toàn bộ `blocks.json`:

```
'chó chưa tiêm dại'              -> block 10 (437c, 16.txt+20.txt), block 170 (420c, 13.txt)
'Đường lây bệnh dại phổ biến nhất'-> block 11 (387c, 16.txt+20.txt), block 184 (370c, 13.txt)
```

Diff hai cặp cho thấy khác biệt **chỉ là dòng tiêu đề và chỗ ngắt dòng**:

| cặp | khác nhau ở |
|---|---|
| 10 ↔ 170 | tiêu đề "Câu hỏi của người dùng gửi đến hệ thống" vs "Em chào bác sỹ"; 170 gộp 2 dòng thành 1 và có thêm dòng cuối "Câu trả lời của bác sĩ:" |
| 11 ↔ 184 | dòng "Bác sĩ trả lời" chỉ có ở 11; 11 ngắt dòng giữa "mèo dại / hoặc động vật khác" |

Vì tiền tố **lệch ngay ký tự đầu** (`commonprefix` = 0) nên `SHARE` không dùng
được → gán tay, nhưng **dùng lại y nguyên nhãn của `GT[10]`/`GT[11]`**. Đây là lý do
quy trình "tìm bản ghép/bản dịch khác trước khi gán" đáng làm mỗi đợt: 2 block, 790
ký tự, gán xong trong vài phút vì mọi quyết định đã có sẵn.

### Nhãn

| block | nhãn | nguồn quyết định |
|---|---|---|
| 170 | `thương nhẹ ở tay` SYM, `chảy máu` SYM, `bệnh dại` DX A82.9 | y nguyên `GT[10]` |
| 184 | `bệnh dại` ALL (4 lần) DX A82.9 | khớp 1-1 với 4 nhãn rời của `GT[11]` |

Dùng `ALL` thay 4 dòng rời được vì `resolve()` lấy bề mặt bằng `block_text[a:b]` —
tức **lát nguyên văn của block**, không phải chuỗi needle — nên `Bệnh dại` hoa và
`bệnh dại` thường vẫn ra đúng chữ gốc dù matcher không phân biệt hoa/thường.

Không gán (chốt ở `GT[11]`, nhắc lại ở `GT[139]`): `vết cắn của động vật`,
`động vật dại`, `nước bọt của chó, mèo dại`, `vết thương`, `vùng da bị trầy xước`
— **tác nhân và đường vào của bệnh trong bài giảng chung**. Và `chó chưa tiêm dại`:
vaccine của con chó, không phải thuốc bệnh nhân dùng (chốt ở `GT[10]`).

Người hỏi tự kể về mình → **không isFamily** (`GT[4]`/`GT[105]`). Bài phổ biến kiến
thức → **không assertion** (`GT[11]`/`GT[66]`).

### Kiểm chứng

- `--occ` trước khi viết: block 170 `thương nhẹ ở tay` ×1, `chảy máu` ×1,
  `bệnh dại` ×1, `chó chưa tiêm dại` ×1. Block 184 `bệnh dại` ×**4**,
  `vết thương` ×1, `trầy xước` ×1, `động vật dại` ×1.
- Rebuild + đối chiếu `data/gt_block/13.json`: **21 entity, 0 lệch offset**.
- Audit citation: `GT[119]` (nguy cơ chưa mắc vẫn gán DX) — đọc nguyên văn, có thật
  ở dòng 4369. `GT[10]`, `GT[11]`, `GT[139]` đọc nguyên văn. **0 chỗ sai.**

### Còn lại

**75 block / 15436 ký tự (~8.1%)**. Xếp theo ký tự chưa gán mỗi file: 88.txt (788c,
3 block), 5.txt (777c, 2), 60.txt (737c, 3), 49.txt (734c, 4), 77.txt (697c, 4),
92.txt (678c, 3), 54.txt (664c, 2), 40.txt (616c, 2), 25.txt (574c, 2 — **block 294
dùng `SHARE[294] = (111, 77)`**), 70.txt (520c, 2), 46.txt (482c, 3), 58.txt (468c,
3), 33.txt (451c, 2), 38.txt (422c, 1), 31.txt (395c, 1), 56.txt (383c, 1), 66.txt
(355c, 1), 22.txt (337c, 1), 67.txt (333c, 1), 64.txt (331c, 1).

---

## Đợt 19: gán TRỌN file 88.txt (3 block) — 91.9% → 92.3%

File 88.txt là **một bệnh án đường mật liền mạch** bị chèn một mẩu tư vấn khác vào
giữa: mục 1 tiền sử phẫu thuật (block 208) → mục 2 bệnh sử hiện tại (block 161) →
mục 3 tiêu đề (block 306) → **mẩu QA "bé 14 tháng ra mồ hôi nhiều" (block 117, đã
gán từ trước)** → dòng cuối mục 3. Bệnh nhân: đã cắt ống mật chủ + cắt gan trái +
nối gan-hỗng tràng vì nghi ung thư đường mật, đặt 3 stent; lần này vào vì run rẩy
kèm sốt.

### Quy ước chốt cho file

- Mục **"1. Tiền sử bệnh nội khoa / Tiền sử phẫu thuật"** → `isHistorical`
  (tiền lệ `GT[13]` cùng dạng mục, `GT[9]`/`GT[87]`).
- Mục **"2. Tiền sử bệnh hiện tại"** = HPI → **KHÔNG** `isHistorical`
  (`GT[225]`/`GT[129]`); nhưng các gạch đầu dòng dưới **"Các sự kiện trước khi nhập
  viện"** là việc đã qua → `isHistorical` (`GT[225]`:1182).
- Phẫu thuật/thủ thuật/stent → không gán, chỉ lấy **chẩn đoán là LÝ DO mổ**
  (`GT[13]`:892 "ung thư tuyến đại tràng"; và `GT[117]` CÙNG FILE này đã bỏ
  "ba stent mật kim loại đã được đặt").

### Ba quyết định mới

**1. `áp xe` → `CHẨN_ĐOÁN` với `candidates` RỖNG.** Đã tra `entries`: danh mục có
~50 mục "áp xe" nhưng **tất cả đều theo VỊ TRÍ** (K63.0 ruột, K75.0 gan, D73.3
lách, J85.x phổi, L02.x da, K61.x hậu môn, M65.0x bao gân, N15.1 thận…). Không có
mã nào cho áp xe ổ bụng hay áp xe không xác định. Bề mặt ("được cho là áp xe")
không nói vị trí → không chọn được mã nào → để rỗng, theo tiền lệ `GT[111]`
"tổn thương điểm mạch". Vẫn gán DX vì chẩn đoán **nghi ngờ** vẫn là chẩn đoán
(`GT[205]`/`GT[22]` "lo ngại về").

**2. Hậu tố "không thể cắt bỏ" bị CẮT khỏi bề mặt.** "nghi ờ ung thư đường mật
không thể cắt bỏ" → chỉ lấy `ung thư đường mật`. Lý do: *unresectable* là thuộc
tính **khả năng cắt bỏ**, không phải phần tên bệnh — cùng loại với "vị trí – mức
độ" bị cắt ở `GT[280]` và "≥1,5 cm" bị cắt ở `GT[276]`. Ghi rõ để khi gán block
201 (5.txt, cùng câu bản dịch khác) cắt y như vậy — và đợt 20 đã làm đúng thế.

**3. Triệu chứng nối bằng "kèm" mà KHÔNG có từ bổ nghĩa chung thì TÁCH.**
"run rẩy kèm sốt kèm theo sốt" → 3 bề mặt rời (`run rẩy`, `sốt`[0], `sốt`[1]).
Khác `GT[60]`/`GT[79]` "chủ quan sốt và run rẩy" — ở đó "chủ quan" bổ nghĩa cho
cả hai nên giữ trọn cụm. Cụm "kèm theo sốt" là **lỗi dịch lặp**, vẫn gán cả hai
lần theo `GT[132]`:2164 ("âm tính âm tính") và "túi mật giãn" lặp.

### Mã ICD tra được

- `ung thư đường mật` → **C24.0** "U ác tính ở ống mật ngoài gan". `names` **không
  có** mục tên "ung thư đường mật" (đã tra). Dùng lại mã của `GT[27]`:4291 cho
  "ung thư biểu mô tuyến" của **cùng bệnh nhân / cùng nguồn EHR** ở 5.txt. Nhóm C24
  là "u ác tính ở phần khác của đường mật"; bệnh nhân đã mổ ống mật CHỦ (ngoài gan)
  → C24.0 khớp nhất.
- `ổ dịch trong ổ bụng` → **T81.8** "Biến chứng khác do can thiệp", khớp với
  `GT[117]` CÙNG FILE đã gán "ổ dịch sau phẫu thuật" → T81.8. Danh mục không có mục
  nào tên "ổ dịch".
- `Augmentin` → **151392** (RxNorm BN, tiền lệ `GT[47]`:3640).
- `kháng sinh tĩnh mạch` → DRUG, `candidates` rỗng (nhóm thuốc, tiền lệ
  `GT[97]`:2931 cùng bề mặt).

### Kiểm chứng

- Block 306 (62c) = **đúng 2 dòng tiêu đề** ("3. Đánh giá tại bệnh viện" + "Kết quả
  chụp chẩn đoán hình ảnh") → `DONE_EMPTY` (tiền lệ `GT[22]`/`GT[142]`:1941).
- Rebuild + đối chiếu `data/gt_block/88.json`: **14 entity, 0 lệch offset**.
- Audit citation trước khi viết (Python scanner map dòng → `GT[n]` chứa nó):
  **0 chỗ sai.**

---

## Đợt 20: gán TRỌN file 5.txt (2 block) — 92.3% → 92.7%

**Phát hiện quyết định:** 5.txt là **cùng bệnh nhân đường mật với 88.txt**, ở một
bản dịch dài hơn/chi tiết hơn. Tìm ra bằng đúng quy trình đã thành chuẩn từ đợt 17:
*grep một cụm đặc trưng của block TODO qua cả 332 block trước khi gán*.

| | 88.txt | 5.txt |
|---|---|---|
| mục 1 tiền sử phẫu thuật | block 208 (286c) | block 201 (309c) |
| mục 2 HPI (bị chèn QA) | block 161 | block 27 (đã gán) |
| mục 3 đánh giá | block 306 + 117 + dòng cuối | block 152 (468c) |

Hai câu tiền sử phẫu thuật chung **60 ký tự tiền tố** rồi rẽ:
`- cắt bỏ ống dẫn mật chủ` (88.txt) vs `: Đã thực hiện phẫu thuật cắt bỏ ống dẫn
mật chung` (5.txt). 60 ký tự là quá ít để `SHARE` có ích (phần đuôi mới là phần có
nhãn) → **gán tay nhưng bám đúng quyết định của `GT[208]`**.

Block 152 (mục 3) là **tóm tắt lại** các phát hiện đã gán ở `GT[27]` cùng file →
dùng lại y nguyên nhãn của `GT[27]` để hai block cùng bệnh án không lệch nhau:
`đau khi sờ nắn xung quanh vị trí đặt ống dẫn` (SYM), `lấy mẫu bằng bàn chải` (LAB),
`tế bào bất thường` → R85.6, `ung thư biểu mô tuyến` → C24.0, `cholangiogram` (LAB),
`tắc nghẽn kéo dài gần chỗ nối mật tụy` → K83.1.

### Hai chỗ phải quyết

**Bề mặt lấy đúng nguyên văn bản dịch tại chỗ, không đồng nhất hoá.** 88.txt viết
`ung thư đường mật`, 5.txt viết `ung thư biểu mô tế bào mật`. **Giữ nguyên từng bản**
— cùng mã C24.0, khác bề mặt. Vì `text_score` chấm bằng WER trên chính chuỗi trong
văn bản, sửa bề mặt cho "đẹp" là mất điểm.

**Đã cân nhắc C22.1 và loại.** C22.1 = "Ung thư biểu mô ống mật **TRONG** gan".
Bệnh nhân mổ ống mật **CHUNG** (ngoài gan) → C24.0.

`tế bào bất thườngtế bào bất thường` — lỗi dịch lặp **dính liền không có dấu cách**
→ vẫn gán **cả hai lần** (`ALL`), theo `GT[132]`:2164.

### Kiểm chứng

- Rebuild + đối chiếu `data/gt_block/5.json`: **56 entity, 0 lệch offset**.
- Audit citation: **0 chỗ sai.**

---

## Đợt 21: gán TRỌN file 60.txt (3 block) — 92.7% → 93.1%

60.txt = QA mụn trứng cá (block 113 + block 2 lời khuyên cuối, đã gán từ trước) bị
**chèn nguyên một bệnh án tim/thận** vào giữa, ngay sau dòng "Trứng cá bắt nguồn từ
bốn yếu tố chính:" — chỗ chèn đặc biệt thô: dòng tiếp theo lẽ ra là 4 yếu tố sinh
mụn, thay vào đó là gạch đầu dòng tiền sử phẫu thuật tim.

Bệnh nhân EHR: thay van hai lá cơ học + ghép thận thất bại (đang chạy thận), dùng
coumadin, vào viện vì INR dưới ngưỡng điều trị (1.7) và chảy máu mũi.

- **block 273** (113c) = tiền sử phẫu thuật + "Thuốc trước khi nhập viện" → `isHistorical`
  (`GT[187]` cùng dạng mục, `GT[100]` "Tiền sử bệnh: Bản thân").
- **block 151** (470c) = mục "2. Bệnh sử hiện tại" = HPI → **không** `isHistorical`
  (`GT[225]`/`GT[129]`/`GT[161]`).
- **block 250** (154c) = mục "3. Khám tại bệnh viện", sinh hiệu → không assertion
  (`GT[143]`/`GT[152]`), dùng đúng khuôn `GT[131]` (cùng kiểu đơn vị `l/p`, `độ C`).

### Mã ICD tra được

- `van hai lá cơ học` → **Z95.2** "Sự có mặt của van tim nhân tạo cơ học". Dùng lại
  đúng mã `GT[100]`:2918 đã chọn cho "Van động mạch chủ cơ học". Cắt tiền tố
  "Phẫu thuật thay" (thủ thuật → không gán, `GT[187]`/`GT[13]`). Loại **Z95.4** ("van
  tim thay thế khác") vì bề mặt nói rõ CƠ HỌC; loại **I34.0** (`GT[91]` "HoHL" = hở
  van hai lá) vì đây là van **đã thay**, không phải bệnh van còn lại.
- `ghép thận thất bại` → **T86.1** "Thất bại và/hoặc thải ghép thận" — khớp gần như
  nguyên văn. `names` không có mục này nên phải **quét `entries`** mới thấy; chỉ có
  T86.1 và Z94.0 ("Tình trạng ghép thận"), chọn T86.1 vì bề mặt nhấn THẤT BẠI.
- `coumadin` → **11289** (warfarin IN). Dùng lại `GT[187]`:2281: Coumadin không có
  trong `RXNCONSO.RRF` nên phải dùng mã hoạt chất.

### Ba quyết định mới, đều là quyết định KHÔNG gán

**1. Không gán `INR dưới ngưỡng điều trị` / `chỉ số đông máu dưới ngưỡng điều trị`
làm `CHẨN_ĐOÁN`.** "dưới ngưỡng điều trị" là **nhận định bằng chữ về trị số**, mà
tiền lệ chỉ gán `KẾT_QUẢ_XÉT_NGHIỆM` cho **giá trị số (+đơn vị)** — chính vì lẽ đó
`GT[25]`:4447 và `GT[163]`:3449 đã bỏ "chưa phát hiện bất thường trên phim chụp".
Đã cân nhắc D68.3 ("Xuất huyết do có kháng đông lưu hành") cho tình trạng này nhưng
loại: bề mặt nói INR **THẤP** (1.7, dưới ngưỡng), tức thuốc chưa đủ liều — ngược
hẳn với quá liều kháng đông.

**2. Không gán `chỉ số đông máu` làm `TÊN_XÉT_NGHIỆM` thứ hai.** Trong cùng một câu,
"chỉ số đông máu … ( kết quả là INR 1.7)" — "chỉ số đông máu" chính là **cách gọi
chung của INR**, không phải một phép đo khác → chỉ giữ tên chỉ số thật (`INR` ×2),
theo tiền lệ `GT[136]` bỏ tiêu đề nhóm panel xét nghiệm. Mất recall ở đây là **cố
ý**, đánh đổi lấy không sinh khái niệm trùng.

**3. Nhưng `xét nghiệm` đứng trần thì CÓ gán.** "Khi làm xét nghiệm tại khoa chạy
thận, phát hiện …" — nêu chung nhưng **đã thực hiện và có kết quả ngay sau** → gán,
theo `GT[103]`:3487 ("xét nghiệm bất thường") và `GT[25]`:4442 ("xét nghiệm máu").
Khác "các xét nghiệm này" / "một xét nghiệm nào" (`GT[289]`/`GT[1]`) là **nêu giả
định**, không gán. Ranh giới: *có thực hiện* thì gán, *nói phiếm* thì không.
Không gán `khoa chạy thận` (tên khoa) và không gán `chạy thận` (thủ thuật).

### Sáu phát hiện âm tính của mục "Khám hiện tại"

`Không chảy máu mũi` / `Không có đau ngực` / `Không có khó thở` / `Không có đau bụng`
/ `Không có buồn nôn, không nôn` → 6 bề mặt SYM + `isNegated`
(`GT[129]`:2335-2336, `GT[27]`:4359-4360, `GT[78]`:3228, `GT[162]`:1500).

`buồn nôn` và `nôn` tách thành **2 bề mặt** vì bản dịch viết rời và **mỗi cụm có từ
phủ định riêng** ("không có buồn nôn, **không** nôn"). Khác `GT[131]`:3603 nơi
"nôn ra thức ăn và dịch dạ dày, không có máu" là một cụm liền. Bẫy index: `nôn`
lần [0] nằm **bên trong** "buồn nôn" → phải lấy index **1**.

`Các cơ quan khác chưa phát hiện bất thường` và `không có biểu hiện bất thường khác`
→ **kết quả BÌNH THƯỜNG, không gán** (chốt ở `GT[289]`:1064 và `GT[186]`:1110).

`chảy máu mũi` lần [0] là triệu chứng thật (SYM, không assertion), lần [1] nằm trong
"Không chảy máu mũi" (SYM + NEG) — cùng bề mặt, hai nhãn khác nhau theo ngữ cảnh
từng lần. `chảy máu mũi` → SYM (không phải DX dù có R04.0 "Chảy máu cam") theo
`GT[111]`:2747 cùng bề mặt và `GT[171]`:2763. `khoảng 01 lần/ tuần`: tần suất →
không gán (`GT[226]`:1290, `GT[240]`:1658).

### Kiểm chứng

- `--occ` trước khi viết cả 3 block: block 151 `INR` ×**2**, `chảy máu mũi` ×**2**,
  `nôn` ×**2**, `xét nghiệm` ×1, `1.7` ×1, 4 triệu chứng âm tính ×1. Block 273 và
  250: mọi needle ×1.
- Rebuild + đối chiếu `data/gt_block/60.json`: **39 entity, 0 lệch offset**
  (16 SYM / 9 LAB / 7 DX / 6 VAL / 1 DRUG).
- Audit citation: 15 dòng được dẫn, đọc nguyên văn bằng scanner map dòng → `GT[n]`.
  **0 chỗ sai.** (Đợt 16 sai 1, đợt 15 sai 6, đợt 14 sai 4 → chạy audit TRƯỚC khi
  viết vẫn là bước đáng giá nhất.)

### Còn lại

**67 block / 13134 ký tự (~6.9%)**. Xếp theo ký tự chưa gán mỗi file: 49.txt (734c,
4 block), 77.txt (697c, 4), 92.txt (678c, 3), 54.txt (664c, 2), 40.txt (616c, 2),
25.txt (574c, 2 — **block 294 dùng `SHARE[294] = (111, 77)`**), 70.txt (520c, 2),
46.txt (482c, 3), 58.txt (468c, 3), 33.txt (451c, 2), 38.txt (422c, 1), 31.txt
(395c, 1), 56.txt (383c, 1), 66.txt (355c, 1), 22.txt (337c, 1), 67.txt (333c, 1),
64.txt (331c, 1), 48.txt (330c, 1), 89.txt (314c, 2), 74.txt (277c, 1), 53.txt
(276c, **5 block nhỏ**), rồi 25 file còn lại mỗi file 1–2 block dưới 270c.

---

## Đợt 22: gán TRỌN file 49.txt (4 block) — 93.1% → 93.45%

**Ngày:** 2026-07-28. **File:** `49.txt`. **Block:** 180, 219, 318, 324
(block 0/18/122/246 đã xong từ các đợt trước).

### Hình dạng file

49.txt = **QA rụng tóc từng mảng** (cùng nguồn với 65.txt) bị **chèn một mẩu bệnh án
ung thư vú di căn** vào giữa, ngay sau câu hỏi của người dùng:

```
1  Câu hỏi từ người dùng:                          <- block 246 (đã xong, SHARE từ 235)
3  Em bị bệnh rụng tóc từng mảng...
5  Ung thư vú di căn, tràn dịch màng phổi trái tái phát   <- block 318  (EHR chèn)
7  2. Bệnh sử hiện tại / Lý do vào việni: khó thở         <- block 324  (EHR chèn)
9  3. Khám tại bệnh viện ... - dẫn lưu dịch màng tim      <- block 219  (EHR chèn)
14 Mình xin tư vấn một số phương pháp điều trị dưới đây
15 1. Liệu pháp ************ ...                          <- block 122 (đã xong)
19 2. Liệu phát miễn dịch tiếp xúc (contac immunotherapy) <- block 180
21 3. PUVA (psoralen kết hợp UVA)                         <- block 18  (đã xong)
```

### Phát hiện quan trọng: block 180 là một PHẦN của GT[76]

Ở 65.txt cả bài giảng dồn vào **một** block 1099c (`GT[76]`). Ở 49.txt cùng bài đó bị
cắt thành **ba** block: 122 + 180 + 18. Nghĩa là `GT[180]` phải dùng lại **y nguyên**
các quyết định của `GT[76]` để hai bản không lệch nhau.

Nhưng **không dùng được `SHARE`**: `commonprefix(180, 76) = 0` vì block 180 mở đầu
bằng dòng tiêu đề `2.        Liệu phát miễn dịch tiếp xúc (contac immunotherapy)` —
dòng này KHÔNG có trong block 76. `180 in 76` cũng False. → gán tay, copy nhãn.

**Bẫy chỉ số (bắt được TRƯỚC khi viết, nếu không sẽ `SystemExit`):** trong block 180
`--occ` đo được `rụng tóc` ×**2** và `viêm da tiếp xúc` ×**2**, còn `GT[76]` dùng
index **3 và 4** cho `rụng tóc` (vì ở block 76 có thêm đoạn đầu chứa 3 lần khác).
→ block 180 phải dùng index **0 và 1**. Copy nguyên index của GT[76] là chết.

**Ghi chú cho sau:** block **237** (89.txt, còn TODO) chung **62 ký tự tiền tố** với
block 180 — cùng đúng dòng tiêu đề đó — nhưng đuôi là một câu ECG hoàn toàn khác.
Overlap chỉ ở tiêu đề nên vô dụng với `SHARE`; điều nó nói lên là 89.txt cũng thuộc
cùng nguồn bị ghép sai. Khi tới 89.txt, giữ quyết định "không gán dòng tiêu đề" giống
ở đây.

### Quyết định mới

**1. `Liệu phát miễn dịch tiếp xúc (contac immunotherapy)` → KHÔNG gán.**
Đây là tên *phương pháp*, thuốc thật là 2 chất gây mẫn cảm kể ngay sau
(`diphenylcyclopropenone`, `dinitrochlorobenzene`) — đã gán 2 chất đó nên gán thêm
tiêu đề là tạo khái niệm trùng lặp. Khác 2 tiền lệ ngược:
- `GT[18]:2018` gán `PUVA` — PUVA *là* psoralen + UVA, tức chính tên thuốc.
- `GT[76]:3544` gán `("**************", ALL, DRUG)` — tên thuốc bị mask nằm **trong**
  tiêu đề `Liệu pháp ****`, tức tiêu đề đó có tên thuốc thật.

Ở đây tiêu đề không chứa tên thuốc nào. Bản dịch còn sai chính tả (`Liệu phát`,
`contac`) → càng không phải tên khái niệm chuẩn. `(contac immunotherapy)` là chú thích
tiếng Anh trong ngoặc ngay sau nhãn Việt → không gán riêng (`GT[299]:1600`).

**2. `Ung thư vú di căn` → DX `C50.9`** (mã u NGUYÊN PHÁT, không phải mã di căn).
`names` không có mục `ung thư vú` → phải quét `entries`. C50.9 "U ác tính ở vú, không
xác định" là mã duy nhất không đòi vị trí 1/4 cụ thể. Giữ chữ "di căn" trong bề mặt
(nó nằm liền trong tên chẩn đoán) nhưng **mã vẫn là mã bệnh gốc**: C79.9 ("U ác tính
thứ phát, vị trí không xác định") là mã cho *ổ* di căn, còn bề mặt này nêu bệnh gốc ở
vú. Chỉ 1 mã — không thêm C79.9 cho "chắc", vì candidates chấm bằng Jaccard trên tập
mã: thêm mã sai làm **giảm** điểm (|gt ∩ pred| / |gt ∪ pred|).

**3. `ung thư di căn theo đường bạch huyết ở hai phổi` → DX `C78.0`** (mã THỨ PHÁT).
Ngược lại với block 318: đây là kết quả CĐHA mô tả chính *ổ di căn*. Đã cân nhắc
**C77.1** ("thứ phát ở hạch trong khoang ngực") vì bề mặt nói "theo đường bạch huyết",
nhưng vị trí tổn thương là HAI PHỔI chứ không phải hạch → C78.0 "U ác tính thứ phát ở
phổi". Giữ **trọn** cụm làm bề mặt: kiểu lan + vị trí gắn liền trong tên phát hiện,
tiền lệ `GT[94]:2985` "xẹp phổi thùy dưới phải do chèn ép" và `GT[141]:1927` "nhiễm
trùng chi dưới bên phải do Enterococcus kháng vancomycin" đều giữ cả phần nguyên nhân.

**4. `tràn dịch màng ngoài tim` → DX `I31.3`, cắt "mức độ trung bình".**
I31.3 "Tràn dịch màng ngoài tim (không do viêm)" khớp chính xác qua `names`. Cắt hậu
tố mức độ theo `GT[280]` (cắt "vị trí – mức độ") / `GT[276]` (cắt "≥1,5 cm").

**5. QUYẾT ĐỊNH CÓ RỦI RO — `tràn dịch màng phổi trái tái phát` → cắt còn `tràn dịch
màng phổi`, mã J90.** Hai tiền lệ đối nhau:
- Giữ: `GT[58]:503` và `GT[165]:3410` giữ trọn "tràn dịch màng phổi **hai bên nhẹ**";
  `GT[78]` giữ "đau hạ sườn phải **tái phát**, ngày càng nặng hơn".
- Cắt: `GT[280]`/`GT[276]` cắt hậu tố thuộc tính.

Chọn **cắt** vì trong câu này "tái phát" đứng cuối và bổ nghĩa cho **cả hai** chẩn
đoán nối bằng dấu phẩy (`Ung thư vú di căn, tràn dịch màng phổi trái tái phát`) → nó
không thuộc riêng bề mặt nào. Còn "trái" là vị trí. **Cần rà lại khi có validation
split** — thêm vào danh sách quyết định rủi ro cùng `GT[277]`, E78.5/E78.9, I25.5,
`Men tim`.

**6. Không gán:** `dẫn lưu dịch màng tim` (thủ thuật — `GT[117]`/`GT[208]`/`GT[201]`);
các tiêu đề mục và tiêu đề nhóm `Lâm sàng` / `Kết quả chẩn đoán hình ảnh` / `Các thủ
thuật đã thực hiện` / `Lý do vào việni` (`GT[142]:1941`, `GT[186]:1113`); `01
lần/tuần` và `trong 06 tháng` (tần suất/thời gian); câu dẫn `Mình xin tư vấn một số
phương pháp điều trị dưới đây` (chỗ nối trở lại bài giảng).

**7. Assertion: cả 4 block đều RỖNG.** Block 180 là bài giảng không có bệnh nhân cụ
thể (tiền lệ `GT[76]`, `GT[18]` cùng file). Ba block EHR (318/324/219) là lần nhập
viện HIỆN TẠI: dòng chẩn đoán → `2. Bệnh sử hiện tại` (HPI) → `3. Khám tại bệnh viện`
→ không `isHistorical` (tiền lệ `GT[22]`/`GT[142]`/`GT[152]`, vừa chốt lại ở đợt 21).

### Kết quả đo

- 269/332 block, 177036/189436 ký tự → **93.45%**, 2736 entity, chiếu ra 100 file /
  3219 entity.
- `data/gt_block/49.json`: **28 entity / 0 lệch offset** (13 DX / 12 DRUG / 3 SYM).
  Cách đo: NFC-hoá `input/49.txt` rồi so `NFC(raw[s:t]) == NFC(e['text'])`.
  (12 DRUG vì các dãy sao bị mask ở block 122/18 cũng tính.)
- Audit citation: 20 dòng được dẫn → **sai 1** (`GT[45]:3875` thực ra là `GT[47]`;
  dòng đúng là `GT[45]:3964`). Đã sửa trước khi build.

### Còn lại

**63 block / 12400 ký tự (~6.55%)**. Kế tiếp: 77.txt (697c, 4 block), 92.txt (678c,
3), 54.txt (664c, 2), 40.txt (616c, 2), 25.txt (574c, 2 — **block 294 dùng
`SHARE[294] = (111, 77)`**), 70.txt (520c, 2), 46.txt (482c, 3), 58.txt (468c, 3),
33.txt (451c, 2), 38.txt (422c, 1), 31.txt (395c, 1), 56.txt (383c, 1), 66.txt (355c,
1), 22.txt (337c, 1), 67.txt (333c, 1), 64.txt (331c, 1), 48.txt (330c, 1), 89.txt
(314c, 2 — **block 237 chung tiêu đề với block 180**), 74.txt (277c, 1), 53.txt (276c,
**5 block nhỏ**), rồi 25 file còn lại mỗi file 1–2 block dưới 270c.

---

## Đợt 23: gán TRỌN file 77.txt (4 block) — 93.45% → 93.82%

**Ngày:** 2026-07-28. **File:** `77.txt`. **Block:** 256, 311, 217, 223
(block 92 đã xong từ đợt trước).

### Hình dạng file

77.txt = **một EHR đau khớp bánh chè – đùi phải** viết theo mẫu OPQRST, bị chèn
**phiếu CĐHA + dòng chẩn đoán của một EHR tim mạch khác** vào giữa:

```
1   1. Tiền sử bệnh — đau vùng xương bánh chè – đùi phải dữ dội   <- block 256
3   2. Tiền sử bệnh hiện tại ... đau đầu gối phải                 <- block 92 (đã xong)
12  Siêu âm ổ bụng / Doppler tim / Xquang ngực                    <- block 92 (phần chèn)
16  Chẩn đoán: suy tim - suy thận mạn giai đoạn 5tăng huyết áp    <- block 311 (chèn)
18  - Thời gian / Tần suất / Chiếu xạ: Không ghi rõ ...           <- block 217
25  3. Đánh giá tại bệnh viện — x-quang, CT khớp bánh chè đùi     <- block 223
```

Block 311 là **dòng chẩn đoán của chính EHR tim mạch** mà phiếu CĐHA đã gán ở
`GT[92]` (thất trái giãn, EF 28%, hở van, bóng tim to) — khớp nhau: suy tim.

### Quyết định mới

**1. Cùng một triệu chứng, hai assertion khác nhau, đúng quy ước.**
Block 256 (`1. Tiền sử bệnh`) → `đau vùng xương bánh chè – đùi phải dữ dội` +
`isHistorical`. Nhưng `GT[92]:3021` gán gần như cùng bề mặt
(`Đau bánh chè đùi phải dữ dội`) mà **không** HIST, vì ở đó nó nằm dưới
`2. Tiền sử bệnh hiện tại` (HPI). Đây không phải mâu thuẫn — **assertion theo MỤC
chứa bề mặt, không theo nội dung y khoa** (quy ước đã chốt ở `GT[289]:1059` /
`GT[128]:2248`). Giữ trọn cụm vị trí + mức độ theo đúng GT[92] cùng file.

**2. `suy thận mạn giai đoạn 5` → GIỮ "giai đoạn 5" trong bề mặt, mã `N18.5`.**
Khác với `GT[219]` đợt 22 (cắt `mức độ trung bình`) vì ở đây **giai đoạn là phần
định danh của mã**: N18.1…N18.5 phân theo đúng giai đoạn. Tiền lệ nguyên văn
`GT[14]:4728` `("Suy thận mạn giai đoạn V", 0, DX, [HIST], ["N18.5"])` — corpus ở
77.txt ghi số Ả Rập nên bề mặt là "5" (không đồng nhất hoá — WER chấm chuỗi nguyên).

**3. `tăng huyết áp` bị corpus dính chữ `giai đoạn 5tăng huyết áp`** → needle chỉ lấy
đúng phần tên bệnh, mã I10. Tiền lệ dính chữ: `GT[120]:3762` "Bệnh dạithường",
`GT[163]:3532` "chụp ctchưa phát hiện", `GT[25]:4701` "tăng bạch cầuNgày nay".
Không HIST — dòng `Chẩn đoán:` là lần nhập viện hiện tại (`GT[233]:1643`,
`GT[68]:4774`).

**4. `thay đổi thoái hóa nghiêm trọng của khớp bánh chè đùi phải` → DX `M17.9`.**
Bỏ mạo từ `những` ở đầu nhưng giữ trọn phần còn lại: mức độ `nghiêm trọng` nằm
**giữa** cụm nên không cắt rời được, và tiền lệ giữ bề mặt dài có cả mức độ:
`GT[245]:1126` ("... mức độ nặng giai đoạn toàn phát"), `GT[94]:2985` ("... do chèn
ép"). Mã M17.9 "Thoái hóa khớp gối, không xác định": "thay đổi thoái hóa" = thoái
hóa khớp, khoang bánh chè – đùi thuộc khớp gối.
**Đã loại M22.2** ("Rối loạn của khớp gối (xương bánh chè - xương đùi)") dù khớp
đúng hơn về *vị trí*, vì M22.2 là mục "rối loạn" chung không mang bệnh lý THOÁI HÓA
mà bề mặt nêu rõ → **ưu tiên khớp bệnh lý hơn khớp vị trí**, cùng lối chọn với
`GT[219]` đợt 22 (chọn T86.1 "thất bại ghép" thay Z94.0 "tình trạng ghép").
Không dùng M17.1/M17.5 (nguyên phát/thứ phát) vì bề mặt không nói.

**5. `x-quang` đứng một mình vẫn là LAB** (không có chữ "chụp") — tiền lệ
`GT[137]:2001` gán viết tắt `XQ`.

**6. `góc tăng lên` → KHÔNG gán**, hai lý do độc lập:
- Không phải VAL: nhận định bằng chữ, không có giá trị số (`GT[89]:3142` bỏ
  `(Tăng)`, `GT[151]:3848` bỏ `dưới ngưỡng điều trị`).
- `góc` cũng không gán riêng làm LAB: số đo chung chung không nêu tên phép đo nào
  (tiền lệ `GT[151]` bỏ `chỉ số đông máu` vì gọi chung).

**7. Block 217 = danh sách RỖNG tường minh** (không dùng `DONE_EMPTY`, theo cách làm
`GT[292]:2717` để giữ lại lý do). Toàn block là 6 trường của mẫu OPQRST:
- 5 trường ghi `Không ghi rõ` = **không có dữ liệu**, không phải phủ định một triệu
  chứng có tên → không gán. Khác `không sốt` ở `GT[183]:2795` (có tên để phủ định).
- `Chiếu xạ` là **dịch sai** chữ "Radiation" của mẫu OPQRST (đúng nghĩa là "đau
  lan") — vẫn chỉ là tên trường, nội dung "Không ghi rõ" → không gán.
- `hầu hết các hoạt động, đặc biệt là leo cầu thang và gập sâu`: yếu tố làm nặng là
  **hoạt động**, không phải triệu chứng/bệnh → không gán.

Đây là block **thứ 2** trong toàn corpus không có khái niệm nào mà vẫn đáng ghi lý
do (sau `GT[292]` toàn thủ thuật). Đáng chú ý cho model: mẫu bệnh án có nhiều trường
trống, học được "Không ghi rõ" → rỗng là có giá trị.

**8. Không gán thêm:** `triệu chứng tương tự` (nhắc chung không tên — `GT[183]:2801`);
tiêu đề mục/trường (`GT[142]:1941`, `GT[186]:1113`); `xảy ra cách đây vài tháng`,
`vào thời điểm đó`, `kể từ lần khám cuối cùng` (mốc thời gian — `GT[226]:1290`);
lỗi dịch thêm chữ `C` trong `CGhi nhận`.

### Kết quả đo

- 273/332 block, 177733/189436 ký tự → **93.82%**, 2743 entity, chiếu ra 100 file /
  3226 entity.
- `data/gt_block/77.json`: **28 entity / 0 lệch offset**
  (14 DX / 7 LAB / 5 SYM / 2 VAL). Cách đo: NFC-hoá `input/77.txt` rồi so
  `NFC(raw[s:t]) == NFC(e['text'])`.
- Audit citation: **sai 11/25** — nhưng **tất cả 11 đều do CÙNG một nguyên nhân**:
  ghi chú mang theo từ trước khi chèn 4 block đợt 22 (+84 dòng), nên mọi số dòng
  dưới điểm chèn đều lệch đúng 84. Đã tính lại từng dòng bằng scanner
  (khớp `owner[line] == GT[n]` + khớp nội dung) rồi sửa trước khi build; audit lần 2
  **0 sai**.
  → **Bài học:** số dòng trong ghi chú mang từ session trước là RÁC nếu đã chèn thêm
  block. Phải chạy scanner map dòng → `GT[n]` mỗi lần, không tin số dòng cũ.

### Còn lại

**59 block / 11703 ký tự (~6.18%)**. Kế tiếp: 92.txt (678c, 3 block), 54.txt (664c,
2), 40.txt (616c, 2), 25.txt (574c, 2 — **block 294 dùng `SHARE[294] = (111, 77)`**),
70.txt (520c, 2), 46.txt (482c, 3), 58.txt (468c, 3), 33.txt (451c, 2), 38.txt (422c,
1), 31.txt (395c, 1), 56.txt (383c, 1), 66.txt (355c, 1), 22.txt (337c, 1), 67.txt
(333c, 1), 64.txt (331c, 1), 48.txt (330c, 1), 89.txt (314c, 2 — **block 237 chung
tiêu đề với block 180**), 74.txt (277c, 1), 53.txt (276c, **5 block nhỏ**), rồi 25
file còn lại mỗi file 1–2 block dưới 270c.

---

## Đợt 24: gán TRỌN file 92.txt (3 block) — 93.82% → 94.18%

### Bối cảnh: cách làm chuyển từ "theo block" sang "theo file"

User đề xuất đọc trọn từng file, chấp nhận trùng lặp token. Đo lại để trả lời:

- **56/100 file đã xong 100%**, 44 file còn dở.
- Còn **61 block / 11929 ký tự**. Trong 61 block đó, **59 block chỉ thuộc đúng 1
  file**; chỉ 2 block thuộc 2 file (block 21 → 51.txt+70.txt, block 23 →
  6.txt+11.txt). Cách đo: đọc `data/blocks/file_to_blocks.json`, đếm số file chứa
  mỗi block còn lại.
- → **Làm theo file gần như KHÔNG trùng lặp công gán nhãn.** Chi phí duy nhất là
  đọc lại phần đã gán của file để lấy ngữ cảnh (~80k ký tự cho 44 file ≈ 25k
  token) — user đã chấp nhận.
- Ghi nhận: thực tế từ đợt 20 tôi đã đọc trọn file rồi, vì block bị cắt giữa câu
  nên không đọc cả file thì không biết bề mặt nằm dưới MỤC nào (mà assertion lại
  quyết định theo mục). Đề xuất của user trùng với cách đang làm, nay chốt thành
  quy ước chính thức.
- **Bỏ số dòng trong citation từ đợt này.** Đợt 23 sai 11/25 citation chỉ vì chèn
  block làm lệch số dòng. Chỉ ghi `GT[n]`, không ghi `:dòng` → mất gần như không
  thông tin, bỏ hẳn được bước audit số dòng.

### Hình dạng file 92.txt

MỘT EHR nhiễm trùng huyết đường vào tiết niệu, bệnh nhân liệt hai chi dưới có bàng
quang thần kinh + sonde tiểu lưu + loét tì đè độ IV + viêm tuỷ xương mãn. Bị chèn
**2 mẩu của bài giảng TRỨNG CÁ**: 1 dòng ở cuối block 109 (đã gán) và dòng
"Tăng sản tuyến bã nhờn" ở đầu block 227.

Thứ tự đọc: `185` (mục 1 Tiền sử) → `109` (mục 2 Bệnh sử hiện tại, đã xong) →
`227` (cận lâm sàng + dòng chẩn đoán) → `282` (Điều trị).

Kiểm tra SHARE trước khi gán tay: block 185 vs block 267 (99.txt, cũng có
"viêm tủy xương / bàng quang thần kinh / liệt hai chi dưới") → `267 in 185` =
**False**, tiền tố chung = **3 ký tự** (`'1. '`) → **không SHARE được**, phải gán tay.

### Quyết định mới chốt trong đợt này

1. **Cùng bệnh nhân thì dùng lại y nguyên mã của block đã gán.** GT[109] đã dùng
   M86.6 (viêm tuỷ xương mãn) và A41.9 (nhiễm trùng huyết) → GT[185]/GT[227] dùng
   đúng 2 mã đó. Nếu để lệch, 2 khái niệm cùng bệnh trong cùng file sẽ có tập mã
   khác nhau → Jaccard tụt ở cả 2.

2. **`loét tì đè giai đoạn IV mãn tính` → L89.3, GIỮ "giai đoạn IV" trong bề mặt.**
   L89.0–L89.3 phân theo ĐỘ loét → giai đoạn là phần **định danh mã**, cùng quy tắc
   với `suy thận mạn giai đoạn 5` → N18.5 (GT[311]). Khác `mức độ trung bình` bị
   CẮT ở GT[219] vì mức độ không làm đổi mã. `names` không có "loét tì đè" → tra
   bằng quét `entries`.

3. **`nhiễm khuẩn đường tiết niệu tái phát` GIỮ "tái phát"** (khác GT[318] cắt
   "tái phát"). Lý do phân biệt: ở đây "tái phát" bổ nghĩa trực tiếp cho đúng một
   cụm (tiền lệ GT[78] `đau hạ sườn phải tái phát, ngày càng nặng hơn`); ở GT[318]
   nó đứng sau HAI chẩn đoán nối bằng dấu phẩy nên không thuộc riêng bề mặt nào.

4. **`vancozosyn` → DRUG `[NEG, HIST]`.** Lỗi dịch dính vanco+zosyn (cùng kiểu
   `vancozosynbactrim` ở GT[109]) → RxNorm không có concept → candidates rỗng. NEG
   vì "nhưng hiện tại đang dừng" (tiền lệ GT[16] "đã hết thuốc", GT[60]/GT[79]
   "ngừng thuốc giảm đau opioid", chính GT[109] "dừng tất cả kháng sinh").

5. **`bactrim` chỉ HIST, KHÔNG NEG** dù đang dùng thật — vì assertion theo **MỤC**
   ("Thuốc đã dùng trước đây"), không theo nội dung. Quy ước chốt từ GT[256]/GT[289].

6. **`thâm nhiễm` → DX `[NEG]`, bề mặt KHÔNG lấy chữ "không thấy".** Theo đúng
   GT[109] cùng file gán `("khó thở", NEG)` cho "không khó thở". Khác GT[68] lấy
   trọn `không có hình ảnh tổn thương viêm cấp tính` — ở đó "hình ảnh tổn thương"
   không đứng riêng được. **candidates rỗng**: mã duy nhất chứa "thâm nhiễm" là
   L98.6 (rối loạn thâm nhiễm ở DA) → sai vị trí, không dùng.

7. **`svo2`/`cvp` → LAB, `82`/`6` → VAL.** Trị số trơ không đơn vị vẫn là VAL
   (tiền lệ GT[115]). `Đặt ống thông tĩnh mạch trung tâm` = thủ thuật → không gán.

8. **`nhiễm trùng huyết đường vào tiết niệu` → A41.9, GIỮ "đường vào tiết niệu".**
   Bảng ICD **không có tên nào chứa "nhiễm trùng huyết"** (đã quét `entries`) → dùng
   A41.9 "Nhiễm trùng hệ thống, không xác định". Ngõ vào nằm liền trong tên chẩn
   đoán → giữ (tiền lệ GT[94] `xẹp phổi thùy dưới phải do chèn ép`). **Không thêm
   N39.0** dù có chữ "tiết niệu" — candidates chấm bằng Jaccard, thêm mã sai làm
   giảm điểm.

9. **`Truyền dịch` KHÔNG gán (thủ thuật) nhưng `NS 0.9 %` CÓ gán → DRUG 9863.**
   Ranh giới: dịch truyền **có tên** thì là thuốc (tiền lệ GT[133] `Glucose 5%` →
   4850); `Truyền dịch tĩnh mạch` gọi chung thì là thủ thuật (GT[142]/GT[94]/GT[45]).
   `4000 ml` = thể tích → không gán. Bề mặt giữ nguyên khoảng trắng trước `%` như
   corpus viết (WER chấm chuỗi literal).

10. **`Cefepim` → IN 20481.** Không có BN nào khớp bề mặt → theo quy ước BN → IN →
    rỗng thì dùng IN. `Vancomycin` → 11124 y như GT[70].

### Lỗi tự phát hiện

Bản Edit đầu tiên tôi ghi `("viêm tủy xương mãn tính", 1, DX, ...)` trong GT[227] với
lý giải "lần [0] ở block 185". **Sai**: chỉ số lần xuất hiện đếm **trong block**, không
cộng dồn qua block. Block 227 chỉ có 1 lần → index 0. Đã sửa ngay trước khi build
(nếu để nguyên sẽ `SystemExit` vì không tìm được lần thứ 2).

### Kết quả đo

- 276/332 block, 178411/189436 ký tự → **94.18%**, 2764 entity, chiếu ra 100 file /
  3247 entity.
- `data/gt_block/92.json`: **41 entity / 0 lệch offset**
  (16 DX / 11 DRUG / 9 SYM / 3 LAB / 2 VAL). Cách đo: NFC-hoá `input/92.txt` rồi so
  `NFC(raw[s:t]) == NFC(e['text'])`.

### Còn lại

**56 block / 11251 ký tự (~5.94%)**, thuộc 43 file. Kế tiếp theo thứ tự nhiều ký tự
chưa gán nhất: 54.txt (664c, 2 block), 40.txt (616c, 2), 25.txt (574c, 2 — **block 294
dùng `SHARE[294] = (111, 77)`**), 70.txt (520c, 2), 46.txt (482c, 3), 58.txt (468c, 3),
33.txt (451c, 2), 38.txt (422c, 1), 31.txt (395c, 1), 56.txt (383c, 1), 66.txt (355c,
1), 22.txt (337c, 1), 67.txt (333c, 1), 64.txt (331c, 1), 48.txt (330c, 1), 89.txt
(314c, 2 — **block 237 chung tiêu đề với block 180**), 74.txt (277c, 1), 53.txt (276c,
**5 block nhỏ**), rồi 25 file còn lại mỗi file 1–2 block dưới 270c.

---

## Đợt 25: gán TRỌN 4 lượt file — 94.18% → 95.43%

Đợt này làm liền 4 lượt, mỗi lượt đóng trọn 1 file (lượt cuối đóng 2 file cùng lúc).
Cách làm giống đợt 24: đọc **cả file `input/<n>.txt`** để biết mỗi block nằm dưới mục
nào (mục quyết định assertion), rồi mới gán từng block.

### 25a. file 54.txt (block 222 + 168) — 94.18% → 94.53%

Hình dạng file: QA "uống thuốc lúc mới mang thai có ảnh hưởng thai nhi không" bị **chèn**
mục "Các bệnh lý mạn tính" + "2. Tiền sử bệnh hiện tại" của một EHR suy kiệt/ảo giác
(bệnh nhân CML dùng gleevec) vào giữa, rồi trở lại câu trả lời của bác sĩ.
Thứ tự đọc: **222** (câu hỏi QA) → **168** (danh sách bệnh mạn của EHR chèn) → **72**
(mục 2 của EHR + phần trả lời QA — đã gán từ trước, `SHARE[72] = (43, 309)`).

Block 168 là **bản dịch khác** của cùng đoạn đã gán ở `GT[87]` (14.txt) và `GT[88]`:
danh sách 9 gạch đầu dòng trùng từng chữ → dùng lại y nguyên nhãn + mã của `GT[87]`.
Không `SHARE` được vì block 168 mở đầu bằng câu hỏi QA "Và e có nên làm xét nghiệm..."
còn `GT[87]`/`GT[88]` mở đầu bằng tiêu đề mục — `SHARE` chỉ nhận **tiền tố**.

Hai quyết định:

1. **`mang thai được hơn 6 tuần` → TRIỆU_CHỨNG.** Đây là một **xung đột tiền lệ thật**:
   `GT[148]` (100.txt) gán `("mang thai được 22 tuần", SYM)`, nhưng `GT[105]`/`GT[107]`
   coi "có thai"/"không có thai" là trạng thái sinh lý → **không gán**. Chọn theo
   `GT[148]` vì bề mặt ở đây có **mốc tuần thai cụ thể** và là trạng thái mà cả câu hỏi
   xoay quanh, giống hệt `GT[148]`; hai bề mặt trơ "có thai" kia vẫn để nguyên.
   → **Ghi vào danh sách rủi ro, rà lại khi có validation split.**
2. **`bcs invisible` (bao cao su) không gán** — là dụng cụ tránh thai, theo tiền lệ
   `GT[107]`/`GT[42]` đã bỏ "que cấy tránh thai"/"Que tránh thai".

**Lỗi có sẵn phát hiện được nhờ đối chiếu:** `GT[88]` gán `("gleevec", 1, DRUG, [HIST])`
mà **thiếu `NEG`**, trong khi `GT[87]` cùng đoạn cùng ngữ cảnh "(dừng theo chỉ dẫn sau
xuất viện)" có `[HIST, NEG]`. Thuốc đã dừng = `isNegated` (`GT[16]`/`GT[60]`/`GT[79]`/
`GT[198]`). **Đã sửa `GT[88]` thành `[HIST, NEG]`** cho khớp cả 3 chỗ.

Đo: 278/332 block, 179075 ký tự → **94.53%**, 2779 entity. `data/gt_block/54.json`:
**29 entity / 0 lệch offset** (14 SYM / 9 DX / 3 DRUG / 3 LAB).

### 25b. file 40.txt (block 247 + 156) — 94.53% → 94.86%

Hình dạng file: **một bệnh án viết tay** (BN nữ 75t, xuất huyết tiêu hoá do quá liều
kháng vitamin K, van động mạch chủ cơ học) đọc liền mạch:
**100** (bệnh sử + khám, đã gán) → **247** (dòng chẩn đoán) → **136** (phiếu chỉ định
XN, đã gán) → **156** (kết quả XN + CĐHA + y lệnh). Bị chèn 1 câu khám thần kinh của
EHR khác vào đầu block 156 (câu "Không ghi nhận co giật..." đã gán ở `GT[186]`).
Cả file là lần nhập viện **hiện tại** → không assertion, trừ mục "Tiền sử" ở `GT[100]`.

Bốn quyết định:

1. **`quá liều kháng vitamin K` → T45.7** ("Ngộ độc thuốc đối kháng chống đông máu,
   vitamin K..."). Đã cân nhắc và **loại** D68.3 ("Xuất huyết do có kháng đông lưu
   hành") vì D68.3 là mã cho **hậu quả xuất huyết** — hậu quả đó đã do K92.2 gánh —
   còn bề mặt này nêu **ngộ độc/quá liều thuốc**. Cũng loại T45.5 (thuốc chống đông
   nói chung) vì bề mặt nói rõ "kháng vitamin K".
2. **`theo dõi` cắt khỏi bề mặt.** "theo dõi Xuất huyết tiêu hóa" → bề mặt là "Xuất
   huyết tiêu hóa"; "theo dõi" chỉ mức độ chắc chắn của chẩn đoán (tiền lệ `GT[194]`).
3. **Bề mặt giữ nguyên dấu xuống dòng thật:** `"Van động mạch chủ cơ \nhọc"` — corpus
   ngắt dòng **giữa cụm từ**. WER chấm chuỗi literal nên phải giữ đúng (tiền lệ
   `GT[88]` `("[[Ngã]]\n", ...)`). Kiểm bằng `--occ` phải truyền newline thật:
   `$(printf 'Van động mạch chủ cơ \nhọc')` → ×1. Truyền `\n` kiểu shell escape ra
   "0 lần" — **bẫy đã gặp**.
4. **`Hình ảnh dày thành một số quai ruột non` → CHẨN_ĐOÁN, candidates RỖNG.** Phát
   hiện CĐHA mang trạng thái bệnh lý → DX (quy ước đã chốt). Nhưng bảng ICD **không có
   mã nào** cho "dày thành ruột": đã quét `entries`, chỉ có K90.2 "Hội chứng quai ruột"
   (bệnh khác hẳn) và K63.8 "Bệnh xác định khác của ruột" (quá chung) → **không thêm mã
   đoán**, vì candidates chấm bằng Jaccard nên mã sai làm **giảm** điểm.

Ngoài ra: `Đái tháo đường` không rõ typ → **E14** (khác E11 khi nêu rõ típ);
thông số máy "(64–128 dãy, có thuốc cản quang, không in phim)" và thuốc cản quang
không gán; `Ceftriaxone` → IN 2193.

Đo: 280/332 block, 179691 ký tự → **94.86%**, 2797 entity. `data/gt_block/40.json`:
**64 entity / 0 lệch offset** (23 LAB / 20 SYM / 9 VAL / 8 DX / 4 DRUG).

### 25c. file 25.txt (block 146 gán tay + block 294 dùng SHARE) — 94.86% → 95.16%

Hình dạng file: QA "uống nhiều thuốc tránh thai khẩn cấp có sao không" (block **146**
câu hỏi + **40** câu trả lời, đã gán) bị **chèn** một EHR nhiễm trùng vết mổ vào giữa
phần trả lời; đuôi file là 3 dòng "khám tại bệnh viện" của EHR đó (block **294**).

Ba quyết định:

1. **Mask 10 dấu sao là bề mặt riêng.** Block 40 cùng file có mask rộng **25** dấu sao
   đã gán DRUG. Không lo lẫn nhau: needle toàn dấu sao **chỉ khớp đúng dải sao dài bằng
   nó**, không khớp làm con của dải dài hơn (ngữ nghĩa `_find_occurences`).
2. **Một chữ "k" phủ định phủ cả 2 triệu chứng.** "nhưng k chảy máu với trễ kinh"
   (k = không) → cả `chảy máu` và `trễ kinh` đều `[NEG]`, theo tiền lệ `GT[186]` nơi
   1 phủ định phủ 4 triệu chứng.
3. **Block 294 = tiền tố 77 ký tự của block 111** (78.txt) → dùng
   `SHARE[294] = (111, 77)` thay vì gán tay. Kiểm: 77 ký tự đầu đúng 3 dòng
   "3. khám tại bệnh viện / Dấu hiệu lâm sàng / - ban đỏ ở vị trí phẫu thật"; đuôi rỗng
   nên chỉ thừa hưởng 1 nhãn `ban đỏ ở vị trí phẫu thuật`, 2 nhãn còn lại của `GT[111]`
   nằm ngoài 77 ký tự (`expand_share` tự loại).

Cũng không gán: `kinh tới rất đều` (phát hiện **bình thường**), `test` (que thử thai
tại nhà — tiền lệ `GT[105]` bỏ "que thử 2 vạch"), `tác dụng phụ` (nói chung).

Đo: 282/332 block, 180265 ký tự → **95.16%**, 2802 entity.
`data/gt_block/25.json`: **44 entity / 0 lệch** (28 SYM / 7 DRUG / 6 DX / 3 LAB).
`data/gt_block/78.json` đo lại sau khi thêm `SHARE[294]`: **22 entity / 0 lệch**.

### 25d. cặp file 51.txt + 70.txt (block 21 + 199) — 95.16% → 95.43%

**Đây là lượt đóng 2 file một lúc** — block 21 xuất hiện ở **cả hai** file.
51.txt và 70.txt là **hai bản của cùng một EHR** (BN suy tim mất bù, khó thở, phù chi
dưới), dùng chung y nguyên block 21 ở đầu:

```
70.txt = 21 (tiền sử) -> 74 (mục 2, đã gán)            -> 199 (mục 3 + 4 dòng y lệnh)
51.txt = 21 (tiền sử) -> 83 (SHARE 1028c của 74, đã gán) -> 128 (đã gán)
```

Chỗ khác nhau: 70.txt chèn 3 dòng bài giảng **bệnh dại** vào đầu mục 3; 51.txt chèn câu
trả lời của bác sĩ về dây chằng chéo. **4 dòng y lệnh cuối giống hệt nhau ở cả hai
file** — ở 51.txt đã gán trong `GT[128]` → block 199 **dùng lại y nguyên** mã
(aspirin 1191 / albuterolipratropium rỗng / methylprednisolone 6902 / lợi tiểu rỗng).

Ba quyết định:

1. **`Dị ứng furosemide` → CHẨN_ĐOÁN + Z88.8.** Dị ứng thuốc là trạng thái bệnh lý có
   mã ICD riêng. Z88.8 = "Tiền sử cá nhân dị ứng với dược chất, thuốc điều trị và/hoặc
   sinh phẩm **khác**": furosemide là thuốc lợi tiểu, **không** thuộc Z88.0–Z88.7
   (penicillin / kháng sinh / gây mê / ma tuý / giảm đau / huyết thanh-vắc xin) → đúng
   con ".8". **Không** dùng T78.4 "Dị ứng, không xác định" như `GT[7]`/`GT[113]` gán cho
   "dị ứng do thời tiết": ở đó tác nhân không phải thuốc nên không có mã Z88 nào dùng
   được, còn ở đây tác nhân là thuốc và Z88.8 khớp chính xác hơn.
   Bề mặt lấy **trọn** "Dị ứng furosemide", **không** tách "furosemide" thành nhãn THUỐC
   riêng: đây không phải thuốc bệnh nhân đang dùng mà là **tác nhân gây dị ứng**, nằm
   liền trong tên chẩn đoán (tiền lệ `GT[94]` "xẹp phổi thùy dưới phải do chèn ép" giữ
   cả nguyên nhân).
2. **`ngừng thở khi ngủ` → G47.3** dù bảng ICD viết "ng**ư**ng thở khi ngủ". Giữ bề mặt
   **literal của corpus** (WER chấm literal), mã vẫn G47.3 y như `GT[20]`/`GT[9]`.
   Không dùng P28.3 — đó là mã của **trẻ sơ sinh**.
3. **`suy tim, không đặc hiệu` giữ cả ", không đặc hiệu" trong bề mặt** vì đó là phần
   định danh đúng con mã `.9` (I50.9), cùng kiểu `GT[87]` "tăng lipid máu, không đặc
   hiệu" → E78.5. Ngược lại `đái tháo đường được kiểm soát bằng chế độ ăn` **cắt** phần
   "được kiểm soát bằng chế độ ăn" — đó là **cách điều trị**, không đổi mã (→ E14, không
   rõ típ). Không `NEG`: bệnh vẫn đang có, chỉ là kiểm soát được.

`bệnh dại` trong block 199 → A82.9 y như `GT[66]`/`GT[11]`/`GT[108]`. Ở `GT[66]` nó là
lần `[3]`, nhưng trong block 199 chỉ có 1 lần → **index 0** (chỉ số đếm **trong block**,
không cộng dồn — chính lỗi tôi mắc ở đợt 24). "Loại hình tiếp xúc và loại động vật cắn",
"Mức độ nghiêm trọng của vết cắn" không gán, y như `GT[66]`/`GT[11]`/`GT[139]` đã bỏ
"vết cắn"/"vết thương".

Đo: 284/332 block, 180785 ký tự → **95.43%**, 2812 entity, chiếu ra 100 file / 3302
entity. `data/gt_block/70.json`: **32 entity / 0 lệch** (18 SYM / 6 DX / 4 DRUG /
2 LAB / 2 VAL). `data/gt_block/51.json`: **30 entity / 0 lệch** (17 SYM / 7 DX /
4 DRUG / 1 LAB / 1 VAL).

### Còn lại sau đợt 25

**48 block / 8651 ký tự (4.57%)**, thuộc **38 file**. Cách đo: `done = set(GT) |
DONE_EMPTY | set(SHARE)`, rồi quét `file_to_blocks.json` lấy block chưa thuộc `done`
(**phải có `SHARE` trong `done`, thiếu là đếm dư**).

Thứ tự tiếp theo (nhiều ký tự chưa gán nhất): 46.txt (482c, 3 block), 58.txt (468c, 3),
33.txt (451c, 2), 38.txt (422c, 1), 31.txt (395c, 1), 56.txt (383c, 1), 66.txt (355c, 1),
22.txt (337c, 1), 67.txt (333c, 1), 64.txt (331c, 1), 48.txt (330c, 1), 89.txt (314c,
2 — **block 237 chung tiêu đề 62 ký tự với block 180**), 74.txt (277c, 1), 53.txt (276c,
**5 block nhỏ**), rồi 24 file còn lại mỗi file 1 block dưới 270c.

**Không còn block nào chung nhiều file** — cả 2 block chia sẻ cuối cùng (21 ở 51/70.txt,
23 ở 6/11.txt) đã xử lý ở đợt này và trước đó, nên từ giờ mỗi block đóng đúng 1 file.

### Ghi chú quy trình đổi ở đợt 25

**Bỏ số dòng khỏi mọi citation, chỉ ghi `GT[n]`.** Lý do đo được ở đợt 24: chèn batch
49.txt làm mọi dòng bên dưới **dịch đúng +84**, khiến 11/25 citation của đợt sau trỏ sai
chỗ. Số dòng là thông tin **tự hỏng sau mỗi lần Edit**, còn `GT[n]` thì vĩnh viễn đúng.

---

## Đợt 26: gán TRỌN 2 lượt file — 95.43% → 95.93%

### 26a. file 46.txt (block 213 + 295 + 260) — 95.43% → 95.69%

46.txt là **một bệnh án viết tay** (BN nữ 81 tuổi, phù phổi cấp / suy tim / stent mạch
vành / tăng huyết áp / hở hai lá) đọc liền mạch, cộng 2 mẩu EHR khác ghép vào cuối:

```
91  (đã gán) bệnh sử + khám + khí máu + điện tim
213 kết quả "Siêu âm doper tim"     <- gán đợt này
295 dòng "Chẩn đoán:" + tiêu đề "Xử trí"   <- gán đợt này
260 3 dòng thủ thuật của EHR KHÁC    <- gán đợt này
144 (đã gán, SHARE 381c của 153) mục "2. Bệnh sử hiện tại" của EHR khác nữa
```

**Quyết định chốt:**

- Block 213 là **phần kết quả** của tên xét nghiệm "Siêu âm doper tim" đã gán LAB ở
  `GT[91]` → mọi phát hiện bệnh lý trên phiếu gán `CHẨN_ĐOÁN`, khớp 1-1 với phiếu siêu âm
  tim ở `GT[92]` (77.txt): `EF BP`→LAB, `55%`→VAL, `Hở hai lá nhiều`→I34.0,
  `Hở chủ vừa`→I35.1, `Tăng áp lực động mạch phổi nhẹ`→I27.2 (tăng áp phổi **thứ phát**,
  không dùng I27.0 nguyên phát vì BN có suy tim/hở van).
- `Phình thành sau và thành bên thất trái` → **I25.3** "Phình thành tim", giữ trọn phần
  định vị vì nằm liền trong tên phát hiện (cùng kiểu `GT[92]` "Buồng thất trái giãn").
- `Giảm vận động 2/3 thành bên và 2/3 thành sau dưới thất trái về phía đáy` → **I25.5**
  "Bệnh lý cơ tim do thiếu máu cục bộ", theo đúng `GT[301]` "Rối loạn vận động vùng"; BN
  có stent mạch vành nên bối cảnh thiếu máu vành là chắc chắn.
- `Thành thất trái dày` → DX **candidates RỖNG**. Đã quét toàn bộ `entries`: không có mã
  nào cho dày thành thất trái đơn thuần. I42.1/I42.2 là **bệnh cơ tim phì đại nguyên
  phát** — sai cơ chế (ở đây dày thành là hậu quả của tăng huyết áp). Không thêm I11.9
  "cho chắc" vì candidates chấm Jaccard, mã sai làm **giảm** điểm.
- Phát hiện **bình thường** trên phiếu ("buồng thất trái không giãn", "chức năng tâm thu
  thất trái bảo tồn") → không gán, y như `GT[92]` chỉ gán các phát hiện bất thường.
- Block 295 **cùng bệnh nhân** với `GT[91]` → dùng lại y nguyên mã: J81 / I50.9 / Z95.5 /
  I10, để hai block không lệch. 4 chẩn đoán nối bằng dấu "-" → tách 4 khái niệm. Không
  HIST: đây là dòng chẩn đoán của lần nhập viện hiện tại (`GT[311]`/`GT[233]`).
- Block 260: `u dây thần kinh số VIII` → **D33.3** "U lành ở thần kinh sọ não" (u dây VIII
  = schwannoma tiền đình, bản chất **lành**). Loại C72.4 "U ác tính ở thần kinh thính
  giác" vì sai bản chất; loại D43.3 (u không tiên lượng được) vì bản chất đã xác định.
  `Sinh thiết tuyến tiền liệt` → LAB (y `GT[14]`). Thủ thuật "Phẫu thuật cắt bỏ" và
  "Đặt shunt động tĩnh mạch (AVF)" → không gán (`GT[106]`/`GT[292]`).

Đo: 287/332 block, 181267 ký tự → **95.69%**, 2826 entity. `data/gt_block/46.json`:
**85 entity / 0 lệch** (33 SYM / 20 DX / 17 LAB / 14 VAL / 1 DRUG). Cách đo lệch:
chuẩn hoá NFC file gốc rồi so `NFC(raw[s:t]) == NFC(entity['text'])`.

### 26b. file 58.txt (block 302 + 283 + 202) — 95.69% → 95.93%

58.txt ghép nhiều nguồn:

```
98  (đã gán) tiền sử + XN của EHR đái tháo đường
224 (đã gán, SHARE 221c của 98)
165 (đã gán) mục "3. Đánh giá tại bệnh viện" của EHR tăng kali máu
302 dòng "2. Chẩn đoán" của một BỆNH ÁN TÓM TẮT   <- gán đợt này
283 mục "3. Tiên lượng" cùng bệnh án tóm tắt đó   <- gán đợt này
202 mục "4. Hướng điều trị" — TRÙNG NGUYÊN VĂN 57.txt/GT[103]  <- gán đợt này
```

**Quyết định chốt:**

- `Đái tháo đường typ II` → **E11**, **giữ** "typ II" trong bề mặt vì chính nó key ra E11
  thay vì E14 (quy ước "giai đoạn/độ nào key ra mã thì giữ"). Khớp `GT[68]` và `GT[98]`
  cùng file.
- Dấu `/` ở "Đái tháo đường typ II/Tăng HA độ III" nối **hai chẩn đoán độc lập** → tách 2
  khái niệm. Đây là **ngoại lệ** của quy ước "cụm nối bằng `/` là một bề mặt" — quy ước đó
  áp cho `/` nối 2 cách gọi **cùng một thứ**.
- `Tăng HA` → I10, **cắt "độ III"**. Lý do: ICD-10 **không** có mã con theo độ tăng huyết
  áp (I11–I13 phân theo tổn thương tim/thận, không theo độ), nên "độ III" là hậu tố mức độ
  thuần → cắt. Ngược với N18.5 / L89.3 nơi giai đoạn có mã con riêng nên phải giữ.
  "đáp ứng với thuốc" không gán và **không NEG** (bệnh vẫn đang có, chỉ kiểm soát được —
  y `GT[21]` "đái tháo đường được kiểm soát bằng chế độ ăn").
- Block 283 theo đúng tiền lệ `GT[303]` (cũng là mục "3. Tiên lượng"): lời văn tiên lượng
  không gán, tên bệnh nằm trong đó thì gán. `Bệnh mạn tính` → DX **candidates rỗng**
  (không nêu bệnh cụ thể; không gán E11/I10 "cho khớp bệnh án" vì bề mặt không nêu bệnh
  nào, thêm mã sẽ hạ Jaccard). `biến chứng tại cơ quan đích` → DX + **isNegated**,
  candidates rỗng: "cần chú ý biến chứng" = biến chứng **chưa** xảy ra, đang dự phòng cho
  **một BN cụ thể** → đúng quy ước `GT[121]`/`GT[247]`. Khác mục tiêu điều trị trong bài
  giảng (không assertion) vì đây là bệnh án BN thật.
- Block 202 trùng nguyên văn 3 dòng cuối `GT[103]` → dùng lại y nguyên mã và assertion
  (quy ước "block là bản sao thì quyết định của block **nguồn** thắng"): isosorbide 6057,
  crestor 320864, carvedilol 20352, mỗi thuốc 2 lần. `kali` ở block 202 là **index 0**
  (trong block này chỉ có 1 lần), còn ở `GT[103]` là index 1 vì có "tăng kali máu" đứng
  trước — chỉ số đếm **trong block**, không cộng dồn.
- "mẫu không tan máu" (nhận xét chất lượng mẫu), "bác sĩ nội trú trực", "khoa Cấp cứu",
  "Các xét nghiệm xét nghiệm được kiểm tra bởi PCP" (lỗi dịch lặp chữ, là nhãn mục) →
  không gán.

**Lỗi tự phát hiện & đã sửa ở đợt này:** `GT[103]` gán `isosorbide`/`crestor`/`carvedilol`
lần **[0]** không có assertion, nhưng lần **[1]** có `isNegated`. Hai câu nói **cùng một
sự việc** ("(…) đã hết khi đi khám PCP" và "Hết isosorbide, crestor, carvedilol khoảng 3
tuần trước") → thuốc đã hết = `isNegated` cho cả 6 nhãn (tiền lệ `GT[16]` "đã hết thuốc",
`GT[60]`/`GT[79]`). Để lệch giữa 2 lần trong cùng một block là tự mâu thuẫn. Đã sửa
`GT[103]` **và** áp đúng cho `GT[202]`.

Đo: 290/332 block, 181735 ký tự → **95.93%**, 2838 entity, chiếu ra 100 file / 3328
entity (SYM 1270, DX 955, LAB 488, DRUG 422, VAL 193). `data/gt_block/58.json`:
**62 entity / 0 lệch** (19 LAB / 17 VAL / 15 DX / 9 DRUG / 2 SYM).
`data/gt_block/57.json` (kiểm tra lại sau khi sửa `GT[103]`): **52 entity / 0 lệch**.

### Còn lại sau đợt 26

**42 block / 7720 ký tự (4.08%)**, thuộc **36 file**. Cách đo như cũ:
`done = set(GT) | DONE_EMPTY | set(SHARE)` rồi quét `file_to_blocks.json`.

Thứ tự tiếp theo (nhiều ký tự chưa gán nhất): 33.txt (451c, 2 block: 189+281), 38.txt
(422c, 169), 31.txt (395c, 178), 56.txt (383c, 181), 66.txt (355c, 188), 22.txt (337c,
191), 67.txt (333c, 192), 64.txt (331c, 193), 48.txt (330c, 194), 89.txt (314c, 237+266 —
**block 237 chung tiêu đề 62 ký tự với block 180**), 74.txt (277c, 211), 53.txt (276c,
**5 block nhỏ**: 309/310/314/315/325), 3.txt (263c, 215), 47.txt (262c, 216), 85.txt
(258c, 218), 34.txt (251c, 220), 75.txt (208c, 229), 17.txt (199c, 230), 52.txt (192c,
236), 29.txt (185c, 238), 90.txt (179c, 242), 80.txt (165c, 272+320), rồi 14 file nhỏ
dưới 150c. Ba trường hợp cuối gần như chắc SHARE/rỗng: 6.txt + 11.txt (cùng block 23,
19c) và 98.txt (block 330, 16c — nằm **trong** block 208).

---

## Đợt 27–33: gán TRỌN 36 lượt file — 95.93% → **100%**

**Ghi bù (nợ nhật ký).** Từ đợt 27 trở đi tôi chạy liên tục hết hàng đợi 42 block cuối
mà không dừng ghi nhật ký từng đợt, nên phần dưới được viết bù ngay sau khi phủ 100%.
Số liệu **không dựng lại từ ký ức**: thứ tự đợt lấy từ thứ tự chèn trong
`src/gt_blocks.py` (entry mới luôn chèn lên đầu → đọc ngược file ra đúng thứ tự thời
gian), độ phủ tính lại bằng cách cộng dồn `n_chars` theo đúng thứ tự đó, số entity từng
file đọc lại từ `data/gt_block/*.json`. Đây là điểm cần rút kinh nghiệm: viết bù thì
mất phần "vì sao lúc đó chọn thế", chỉ giữ lại được cái đã kết tinh thành comment trong
source.

### Tiến trình độ phủ (đo lại, cộng dồn theo thứ tự thực tế)

| # | file | block gán mới | block | ký tự | phủ |
|---|---|---|---|---|---|
| 27a | 33.txt | 189, 281 | 292 | 137164 | 72.41%* |
| 27b | 38.txt | 169 | 293 | 139160 | 73.46%* |
| 27c | 31.txt | 178 | 294 | 141379 | 74.63%* |
| 27d | 56.txt | 181 | 295 | 143128 | 75.55%* |
| 28a | 66.txt | 188 | 296 | 144808 | 76.44%* |
| 28b | 22.txt | 191 | 297 | 147301 | 77.76%* |
| 28c | 67.txt | 192 | 298 | 147634 | 77.93%* |
| 28d | 64.txt | 193 | 299 | 149322 | 78.82%* |
| 29a | 48.txt | 194 | 300 | 151205 | 79.82%* |
| 29b | 89.txt | 237, 266 | 302 | 152631 | 80.57%* |
| 29c | 74.txt | 211 | 303 | 154230 | 81.42%* |
| 29d | 53.txt | 309, 310, 314, 315, 325 | 308 | 156019 | 82.36%* |
| 30a | 3.txt | 215 | 309 | 159739 | 84.32%* |
| 30b | 47.txt | 216 | 310 | 161631 | 85.32%* |
| 30c | 85.txt | 218 | 311 | 163104 | 86.10%* |
| 30d | 34.txt | 220 | 312 | 165216 | 87.21%* |
| 31a | 75.txt | 229 | 313 | 166796 | 88.05%* |
| 31b | 17.txt | 230 | 314 | 169425 | 89.44%* |
| 31c | 52.txt | 236 | 315 | 171221 | 90.38%* |
| 31d | 29.txt | 238 | 316 | 173453 | 91.56%* |
| 32a | 90.txt | 242 | 317 | 174877 | 92.31%* |
| 32b | 80.txt | 272, 320 | 319 | 176366 | 93.10%* |
| 32c | 42.txt | 253 | 320 | 178318 | 94.13%* |
| 32d | 55.txt | 254 | 321 | 180087 | 95.06%* |
| 32e | 28.txt | 255 | 322 | 181776 | 95.96%* |
| 32f | 30.txt | 257 | 323 | 184003 | 97.13%* |
| 33a | 69.txt | 261 | 324 | 185664 | 98.01% |
| 33b | 86.txt | 264 | 325 | 185794 | 98.08% |
| 33c | 35.txt | 275 | 326 | 185904 | 98.14% |
| 33d | 84.txt | 279 | 327 | 186005 | 98.19% |
| 33e | 65.txt | 287 | 328 | 187665 | 99.07% |
| 33f | 68.txt | 290 | 329 | 189330 | 99.94% |
| 33g | 93.txt | 300 | 330 | 189401 | 99.98% |
| 33h | 6.txt + 11.txt | 23 (rỗng) | 331 | 189420 | 99.99% |
| 33i | 98.txt | 330 (rỗng) | **332** | **189436** | **100.00%** |

\* Cột "phủ" là **ký tự đã gán / 189436 tổng**, cộng dồn theo thứ tự chèn. Các mốc có
dấu \* thấp hơn con số tôi báo tại thời điểm chạy (ví dụ đợt 33f tôi báo 99.94% và ở đây
cũng 99.94%, nhưng 27a tôi báo ~96.1% trong khi cộng dồn ra 72.41%). Lý do: mỗi đợt gán
**trọn một file**, nên block đóng góp cho một file thường đã được gán từ những đợt
trước qua `SHARE`/trùng lặp; bảng này chỉ tính phần **block mới thêm vào**, còn con số
báo lúc chạy là độ phủ **thực tế của toàn bộ** `GT | DONE_EMPTY | SHARE` ở thời điểm đó.
Hai cách đo khác nhau ở chỗ nào thì cột "block" nói rõ: từ 290 block (95.93%, cuối đợt
26) tăng đúng 42 block lên 332. **Con số chốt duy nhất đáng tin: 332/332 block,
189436/189436 ký tự = 100%.**

### Kết quả cuối

```
block_da_gan   332      block_tong     332
ky_tu_da_gan   189436   ky_tu_tong     189436
phu_ky_tu      1.0
entity         2987   (cấp block)
chiếu ra       100 file, 3484 entity
  TRIỆU_CHỨNG 1319 | CHẨN_ĐOÁN 1023 | TÊN_XÉT_NGHIỆM 498 | THUỐC 450 | KẾT_QUẢ 194
```

Entity từng file của các đợt này (đọc từ `data/gt_block/*.json`): 33→48, 38→49, 31→42,
56→20, 66→36, 22→54, 67→21, 64→22, 48→9, 89→38, 74→24, 53→48, 3→69, 47→48, 85→35,
34→40, 75→11, 17→71, 52→13, 29→34, 90→40, 80→22, 42→49, 55→29, 28→15, 30→28, 69→19,
86→18, 35→24, 84→8, 65→27, 68→25, 93→24, 6→63, 11→48, 98→24.

### Kiểm chứng offset: 0 lệch / 3484 entity

Cách đo (chạy sau khi phủ 100%, so trên **raw nguyên bản**, không normalize file):

```python
raw = open('input/'+f, encoding='utf-8').read()
for e in json.load(open('data/gt_block/'+f.replace('.txt','.json'))):
    s, t = e['position']
    assert raw[s:t] == e['text']
```

→ `entity 3484 mismatch RAW==text: 0`. Kiểm thêm bản mềm
`NFC(raw[s:t]) == NFC(e['text'])` cũng **0 lệch**.

**Bẫy đã sa vào và cách thoát.** Lần verify đầu tiên tôi NFC-hoá **cả file** trước khi
cắt (`raw = NFC(open(...).read())` rồi `raw[s:t]`) và nhận **360 mismatch**, toàn bộ rơi
vào 20 file NFD. Không phải data sai: NFC hợp nhất tổ hợp dấu NFD nên **rút ngắn chuỗi**,
mọi offset phía sau bị trôi. Offset trong `data/gt_block/*.json` được đánh trên **raw
gốc**, nên verify phải cắt trên raw gốc. Ghi lại vì bẫy này sẽ tái xuất mỗi lần viết
script kiểm tra mới.

### Quyết định mới chốt trong 7 đợt này

**Mã ICD/RxNorm mới tra được**

| bề mặt | mã | căn cứ |
|---|---|---|
| `ntg` (viết tắt nitroglycerin) | 4917 | RxNorm không có concept tên "ntg" → lấy mã hoạt chất IN, y `GT[271]` gán `ASA`→1191 |
| `asa` | 1191 | aspirin IN |
| `dilaudid` | 224913 | biệt dược **có** trong RxNorm → dùng BN (quy ước BN → IN → rỗng) |
| `diltiazem` | 3443 | IN |
| `methadone` | 6813 | IN, không có BN |
| `Giả gout` | M11.2 | pseudogout/CPPD = vôi hoá sụn khớp khác |
| `bệnh Graves` | E05.0 | bảng ICD VN không có tên "Graves"/"Basedow"; E05.0 là mã chính thức |
| `covid` | U07.1 | mã COVID-19 mặc định (U07.2 dành cho ca chẩn đoán lâm sàng chưa XN) |
| `u lành về tuyến vú` | D24 | khớp trực tiếp hơn N60.9 vì bề mặt nói "u" |
| `khối u lành tính` | D36.9 | nói chung, không nêu vị trí; không D48.9 vì bề mặt nói rõ "lành tính" |
| `khối u trực tràng` | D37.5 | chưa rõ lành/ác → mã "không tiên lượng được" |
| `u ác trực tràng` | C20 | |
| `u tuyến` (sinh thiết trực tràng) | D12.8 | ưu tiên mã khớp giải phẫu bệnh |
| `quá liều` (hỗn hợp thuốc) | T50.9 | `GT[100]` dùng T45.7 cho quá liều kháng vitamin K; ở đây benzo + clonidine → mã chung |
| `hẹp lỗ liên hợp` | M99.6 | không có mã trung tính nào khác |
| `Táo bón mãn tính` | K59.0 | |
| `Nhiễm trùng đường tiết niệu (UTIs) tái phát` | N39.0 | giữ cả "tái phát" và ngoặc viết tắt |
| `thận bệnh` (lỗi dịch đảo chữ) | N28.9 | giữ bề mặt as-written |
| `bệnh tim mạch` | I51.6 | y `GT[118]` |
| `bệnh lý thần kinh ngoại biên` | G62.9 | |

**Quy ước mới về cắt bề mặt**

- **Từ chỉ lượng ở ĐẦU cụm thì CẮT nếu tách sạch**: `nhiều mảng bám quanh răng` → cắt
  `nhiều`. Khác `hơi sốt` (`GT[220]`) và `đau nhẹ` (`GT[178]`): cắt ra thì phần còn lại
  trơ nghĩa nên giữ. Tiêu chí: **cắt xong còn đứng vững một mình hay không**.
- **Giai đoạn/độ thì GIỮ khi nó key ra mã con, ngược lại thì không tồn tại**:
  `bệnh thận mạn, không đặc hiệu Giai đoạn 4` → N18.4 (`GT[169]`), còn
  `bệnh thận mạn, không đặc hiệu` (`GT[238]`) → N18.9. Quyết định **chỉ dựa vào bề mặt**,
  không suy từ bệnh cảnh.
- **Vị trí sau bề mặt thì CẮT, kể cả khi ICD có mã theo vùng**: `hẹp ống sống` giữ M48.0
  chứ không M48.02 vì "C4-5, C5-6, C6-7" nằm sau bề mặt.
- **Viết tắt trong ngoặc nằm trong CÙNG một bề mặt**:
  `chụp cộng hưởng từ (mri) cột sống cổ`, `Nhiễm trùng đường tiết niệu (UTIs) tái phát`,
  `tăng huyết áp vô căn (nguyên phát)`.
- **Nhãn mục không key ra mã**, chỉ key ra assertion: dưới tiêu đề "Các bệnh lý mạn
  tính" vẫn gán `rung nhĩ` → I48.9 chứ không I48.2 "Rung nhĩ mạn tính" (`GT[281]`).

**Quy ước mới về assertion**

- **Assertion đi theo MỤC/CÂU chứa bề mặt, không theo file** — đây là quy ước đã có
  nhưng 7 đợt này thử thách nó ba lần và đều giữ:
  - `acetaminophen` ở `GT[191]` có HIST (nằm dưới "Thuốc trước khi nhập viện") trong khi
    `GT[49]` **cùng bệnh nhân** không có (nằm trong bệnh sử hiện tại).
  - `GT[261]` (69.txt) có HIST **không** NEG, còn `GT[97]` cùng file cùng bệnh nhân có
    NEG vì câu ở đó mở bằng "Không xác nhận…".
  - `methadone` "đang dùng" nhưng nằm dưới "Thuốc trước khi nhập viện" → HIST, không NEG.
- **"Không có tiền sử X … nào được biết đến"** → DX + `[NEG, HIST]` (`GT[257]`).
- **"Cải thiện"/"đỡ" KHÔNG phải NEG**, chỉ "hết/ngừng" mới NEG: `khó thở` ở `GT[189]`
  giữ assertion rỗng dù câu nói "khó thở cải thiện".
- **Hậu quả-nếu-không-điều-trị không phải phủ định**: `lúng túng khi xác định hướng âm
  thanh` (`GT[194]`) có "có thể" nhưng vẫn assertion rỗng.

**Quyết định KHÔNG gán (mới)**

- **TEM** ("tem (viết tắt)", transanal endoscopic microsurgery) — viết tắt thủ thuật
  chưa mở rộng → không gán.
- **Thể tích dịch dẫn lưu** (`3L4`, `7L` ở `GT[272]`) → không VAL, cùng lẽ với liều thuốc.
- **Thuốc nhắc mà không nêu tên** → không gán, **và do đó cũng không có nhãn NEG nào**
  cho câu "đã ngừng dùng thuốc" (`GT[178]`, `GT[211]`, `GT[215]`, `GT[287]`).
- **Hậu quả diễn đạt dân dã** ("làm hỏng dạ dày của cô ấy") → không gán, **không thêm
  K25 phòng hờ**.
- **Lo ngại về hậu quả** ("sợ ảnh hưởng tinh trùng ảnh hưởng sinh sản") → không gán,
  khác `GT[44]` "vô sinh thứ phát" là tên chẩn đoán bác sĩ nêu.
- **Diễn biến** ("tái phát lại", "không bị lây lan", "độ giãn không giảm") → không gán.
- **Mô tả bình thường** ("bé nghe khá tốt", "Bệnh nhân đang có đi tiêu mỗi ngày",
  "Chưa phát hiện bất thường") → không gán.
- **Cách theo dõi tại nhà** ("thử gọi con từ nhiều góc khuất") → không gán, khác
  `GT[19]` "đo thính lực" là tên thăm dò có định danh.

**Hai bản dịch dính nhau thì gán CẢ HAI, cùng mã** — gặp 5 lần trong 7 đợt:
`Tiểu đường loại 1 đái tháo đường` (E10 cho cả hai, `GT[218]`),
`tăng huyết áp (tăng huyết áp)` (`GT[242]`), `Đái tháo đường` ×2 + `tăng huyết áp vô căn
(nguyên phát)` (`GT[266]`), `khó thở nhẹ-vừa` + `khó thở khi gắng sức` (`GT[264]`),
`Nhiễm trùng đường tiết niệu (UTIs) tái phát` + `nhiễm khuẩn đường tiết niệu, vị trí
không xác định` (`GT[218]`). Dòng lặp nguyên văn do lỗi corpus cũng gán đủ mọi lần
(`ntg` lần [1] và [2] ở `GT[189]`).

**Tránh nhãn lồng nhau**: `GT[236]` gán `quá liều` (DX) và `klonopinclonidine` (DRUG)
**riêng**, không lấy trọn "quá liều klonopinclonidine". Và `clonidine` **không** gán
riêng vì lần xuất hiện duy nhất của nó nằm bên trong cụm dính — khác `GT[84]` nơi có
một lần độc lập.

**Ba block rỗng khai tường minh** (`GT[320] = []`, `GT[23] = []`, `GT[330] = []`) thay
vì `DONE_EMPTY.add(...)`, để lý do "chỉ là tiêu đề mục" nằm ngay tại chỗ.

### Lỗi tự phát hiện & đã sửa: `GT[204]` thiếu `isHistorical`

Trong đợt 33d (84.txt) tôi gán `thuốc giảm đau opioid` + HIST, rồi đối chiếu thấy
`GT[204]` (73.txt) có **cùng bề mặt, cũng nằm dưới "Thuốc trước khi nhập viện"** nhưng
assertion rỗng. Đã sửa `GT[204]` thành `[HIST]` kèm comment giải thích vì sao tiền lệ
`GT[60]`/`GT[79]` **đúng khi không có HIST**: ở đó bề mặt nằm trong phần bệnh sử hiện
tại, không phải mục thuốc trước nhập viện. `SHARE[221] = (204, 248)` thừa hưởng nên
73.txt và block con đã verify lại: `73.json` **26 entity / 0 lệch**.

### Còn lại

**Không còn gì.** 332/332 block, 189436/189436 ký tự. Hàng đợi gán nhãn tay đóng.

### Việc mở, chuyển sang worklog khác

1. **Rà mâu thuẫn mã** giữa các entry cũ/mới: `Rối loạn lipid máu` → E78.5 (`GT[169]`,
   `GT[193]`, `GT[218]`) trong khi `GT[116]` vẫn E78.9.
2. **Sáu quyết định rủi ro** đã đánh dấu ở các đợt trước, cần đo lại trên tập validation:
   (1) E78.5 vs E78.9; (2) `GT[277]` gán `1,8 mmol/L`/`70 mg/dL` là VAL dù chúng là
   **ngưỡng mục tiêu**, không phải trị số đo được; (3) I25.5 cho `Rối loạn vận động
   vùng`; (4) `Men tim` → LAB, ngược với quy ước "tiêu đề nhóm không gán" của `GT[136]`;
   (5) `GT[318]` cắt `trái tái phát`; (6) `GT[222]` gán `mang thai được hơn 6 tuần`.
   Cộng thêm `vắc xin sống` cố ý không gán.
3. **Chia tập validation** rồi train NER — recall vẫn là nút thắt duy nhất (đo ở
   `worklog/06`: recall 100% với `assertions`/`candidates` rỗng = 77.35đ).

---

## Rà mâu thuẫn sau khi phủ 100%

Việc mở số 1 ở trên đã làm xong ngay, nên chép kết quả vào đây luôn.

### Cách rà

Không đọc lại 3484 nhãn bằng mắt. Chiếu `data/gt_block/*.json` ra rồi nhóm theo
**bề mặt chữ đã lower + strip**, đếm xem một bề mặt có bao nhiêu bộ `candidates` khác
nhau và bao nhiêu `type` khác nhau. Bề mặt nào có >1 giá trị thì bật lên để xét tay.

```python
cand[key][tuple(sorted(e['candidates']))] += 1   # key = e['text'].strip().lower()
typ[key][e['type']] += 1
```

Đo được: **12 mâu thuẫn mã + 5 mâu thuẫn loại**. Đây không phải "12 lỗi" — mâu thuẫn
chỉ là *tín hiệu*, một bề mặt giống nhau vẫn có thể đáng mã khác nếu bệnh cảnh khác.
Xét từng cái, sửa 9 chỗ thật sai, còn 5 giữ nguyên có lý do.

### 9 chỗ đã sửa

| # | Bề mặt | Trước | Sau | Vì sao |
|---|---|---|---|---|
| 1 | `rối loạn lipid máu` (`GT[116]`) | E78.9 | **E78.5** | Chốt E78.5 "Tăng lipid máu, không xác định" làm chuẩn cho mọi bề mặt `rối loạn/tăng lipid máu`, y `GT[233]`/`GT[169]`/`GT[193]`/`GT[218]`/`GT[26]`. E78.9 rộng hơn một bậc, để dành cho bề mặt nói `rối loạn chuyển hóa lipoprotein`. |
| 2 | `Rung nhĩ kèm nhịp nhanh trên thất` | I48.9 | **I48** | Bề mặt không nói kịch phát/dai dẳng/mạn tính nên không key ra mã con nào → mã nhóm I48 khớp đúng mức chi tiết. Y `GT[94]`, `GT[238]`. Khác `GT[281]` `rung nhĩ` trơ đứng một mình → I48.9. |
| 3–5 | `mụn trứng cá`, `nám`, `tàn nhang` (`GT[40]`) | SYM, rỗng | **DX** + L70.9 / L81.1 / L81.2 | Cả 4 dòng trước gán SYM chỉ vì nằm trong danh sách "tác dụng phụ" của thuốc tránh thai. **Loại của khái niệm không phụ thuộc nó là tác dụng phụ hay bệnh chính.** 3 trong 4 là tên bệnh da liễu có mã ICD. `sạm da` giữ SYM (mô tả tình trạng, không định danh bệnh — y `GT[243]` gán `da sạm` SYM). |
| 6 | `hạt tophi` (`GT[53]`) | SYM, rỗng | **DX** + M10, giữ FAM | Cùng nguồn QA gút và cùng bệnh nhân (ông của người hỏi) với `GT[121]` — nơi đó gán DX M10 ×5. Hạt tophi là lắng đọng urat = biểu hiện định danh của gút. |
| 7 | `chỉ nghe một bên` (block 194) | SYM, rỗng | **DX** + H90.1, giữ FAM | Block 71 cùng bé, cùng câu trả lời bác sĩ, đã gán DX H90.1 "Giảm thính lực dẫn truyền một bên, tai còn lại nghe tốt". |
| 8 | `mucinex d` ×2 block | rỗng | **352777** | RxNorm không có concept tên đúng "Mucinex D", chỉ có DP "Mucinex D Maximum Strength". Nhưng BN 352777 "Mucinex" là mã thương hiệu của chính chế phẩm đó → dùng, y `GT[20]`. |
| 9 | `nang màng nhện` ×2 (`GT[26]`) | rỗng | **G93.0** | G93.0 "Bệnh u nang não" là mã của arachnoid cyst, y block 132 cùng bệnh án. |
| 10 | `tiền sản giật` (`GT[106]`) | O14.9 | **O14** | Bề mặt trơ không nêu thể nhẹ/nặng → mã nhóm khớp đúng mức chi tiết, và trùng 2 nhãn cùng bề mặt ở block 100. Cùng lý lẽ với I48 ở #2. |
| 11 | `tụ máu dưới màng cứng mạn tính` + `tụ máu ngoài màng cứng phải cấp tính` (`GT[26]`, 4 nhãn) | I62.0 / I62.1 | **S06.5 / S06.4** | Xem dưới. |

(Đánh số tới 11 vì #3–5 gộp một hàng.)

### Chỗ khó nhất: S06.x hay I62.x

ICD tách hai họ mã cho cùng một tổn thương: `S06.x` = **do chấn thương**,
`I62.x` = **không do chấn thương**. Chọn sai họ là sai hẳn mã.

`GT[26]` (11.txt) dùng I62.x, `GT[89]` (6.txt) dùng S06.x cho cùng bề mặt. Ban đầu tôi
định giữ cả hai, coi là hai ca khác nhau. Đọc lại thì không phải:

- block 89: `...nghĩ đến nang màng nhện hoặc tụ máu dưới màng cứng mạn tính.Tụ máu ngoài màng cứng phải cấp tính trên nền tổn thương mạn tính.`
- block 26: `...nang màng nhện hoặc tụ dịch/tụ máu dưới màng cứng mạn tính.`

Cùng một câu kết luận CT, hai bản dịch máy khác nhau — đúng kiểu trùng lặp đã gặp
suốt corpus này. Thêm hai bằng chứng chốt:

1. Bệnh cảnh trong block 26 là **`ngã`** (đã gán SYM ở dòng ngay trên) → chấn thương.
2. **Ngay trong chính block 26**, `xuất huyết dưới nhện` đã gán **S06.6** (họ chấn
   thương). Để I62.x ở hai dòng dưới là block tự mâu thuẫn với chính nó.

→ Chốt **S06.x** cho cả cụm, sửa 4 nhãn trong `GT[26]` (cả hai occurrence index).

### 5 mâu thuẫn còn lại — giữ nguyên có chủ ý

| Bề mặt | Các mã | Lý do giữ khác nhau |
|---|---|---|
| `đái tháo đường` | E14 ×14, E11 ×2, E10 ×1 | E14 "không xác định" là mặc định cho bề mặt trơ. Chỉ dùng E11/E10 khi câu đó là bản dịch rút gọn của một chẩn đoán **đã nêu type** ngay trong cùng dòng. |
| `huyết khối` | I24.0 ×2, I82.9 ×2 | I24.0 = huyết khối mạch vành, I82.9 = huyết khối tĩnh mạch. Khác vị trí, khác bệnh. |
| `huyết khối` (loại) | DX ×4, LAB ×2 | 2 lần LAB là **lỗi dịch máy**: nguồn là "hematocrit" bị dịch thành "huyết khối". Ở đó nó thật sự là tên xét nghiệm. Gán theo cái bề mặt đang đóng vai, không theo nghĩa từ. |
| `sỏi` | N20.0 ×2, K80.5 ×1 | Sỏi thận vs sỏi ống mật chủ. |
| `sỏi mật` | K80.2 ×2, K80.5 ×1 | K80.2 = sỏi túi mật không viêm; K80.5 = sỏi ống mật chủ thấy trên ERCP. |
| `bệnh lý thần kinh ngoại biên` | E11.4 ×2, G62.9 ×2 | E11.4 khi cùng danh sách có đái tháo đường (biến chứng của ĐTĐ); G62.9 khi không có ĐTĐ nào. |

### Quy ước mới rút ra từ đợt rà

- **Loại của khái niệm không phụ thuộc vị trí văn bản.** Nằm trong danh sách "tác dụng
  phụ" vẫn là DX nếu nó là tên bệnh định danh có mã ICD.
- **Bề mặt trơ → mã nhóm, không mã con.** Không tự thêm chi tiết bề mặt không nói
  (I48 chứ không I48.9; O14 chứ không O14.9).
- **Một block không được tự mâu thuẫn.** Nếu trong cùng block đã chọn một họ mã cho
  một tổn thương do cơ chế X, mọi tổn thương cùng cơ chế trong block đó phải cùng họ.
- **Bản dịch khác của cùng câu phải cùng mã.** Kiểm bằng cách so câu quanh nó, không
  so tên file.
- **Mã thương hiệu dùng được cho biến thể cùng thương hiệu** khi RxNorm không có
  concept tên đúng (Mucinex D → BN của Mucinex).

### Xác nhận lại sau khi sửa

```
entity 3484   mismatch 0        (offset kiểm bằng raw[s:t], KHÔNG normalize)
cand conflicts: 5   type conflicts: 1     (đều thuộc bảng "giữ nguyên" ở trên)
block 332/332   ký tự 189436/189436   phủ 1.0
TRIỆU_CHỨNG 1313  CHẨN_ĐOÁN 1029  TÊN_XÉT_NGHIỆM 498  THUỐC 450  KẾT_QUẢ_XÉT_NGHIỆM 194
```

So với trước đợt rà: 6 nhãn chuyển SYM→DX (1319/1023 → 1313/1029), tổng entity không đổi.

### Cái bẫy đã mất thời gian: đừng normalize khi kiểm offset

Script kiểm đầu tiên làm `raw = NFC(open(file).read())` rồi so `raw[s:t] == e['text']`
→ báo **360 sai**. Cả 360 đều rơi vào đúng 20 file NFD. Nguyên nhân: NFC **ghép** các
combining sequence lại nên **chuỗi ngắn đi**, mọi offset sau lần ghép đầu tiên bị lệch.
Offset trong `data/gt_block/*.json` ghi theo **văn bản gốc thô**. Bỏ normalize đi →
0 sai. Đây là bug script, không phải hỏng dữ liệu. Ghi lại vì bẫy này sẽ lặp mỗi lần
viết script kiểm mới.

## Rà lại 6 quyết định gán nhãn rủi ro

Trong lúc gán tôi có đánh dấu 6 chỗ "quyết định có rủi ro, rà lại khi có validation split".
Split đã có (worklog/08) nên rà. Trước hết xem chúng nằm bên nào:

```
block 277 -> train  (26.txt)   block 318 -> train  (49.txt)
block 222 -> train  (54.txt)   block 312 -> train  (18.txt)
block 301 -> train  (18.txt)   block 228 -> train  ( 2.txt)
```

Cả 6 đều ở **train** — nên chúng ảnh hưởng cái model học được, không bóp méo điểm val.
Cách rà: mỗi chỗ đếm xem quy ước tôi *thực tế* đã dùng ở 99 file còn lại là gì, rồi sửa
chỗ lệch. Đếm bằng số, không phán bằng cảm giác.

### 1. `GT[277]` — hai ngưỡng LDL: BỎ NHÃN

Văn bản: `Kiểm soát LDL < 1,8 mmol/L (hoặc <70 mg/dL)`, nằm ở mục dặn dò ra viện. Đây là
**ngưỡng mục tiêu điều trị**, không phải kết quả đo của bệnh nhân.

Đếm 194 nhãn `KẾT_QUẢ_XÉT_NGHIỆM` trong GT: **193 cái là trị số đo thật**
(`130/76 mmHg`, `6,7 mmol/l`, `99 %`, `79 micromol/l`...), chỉ 2 cái này là ngưỡng. Giữ
chúng là dạy model một luật mà chính nó chỉ có 2 ví dụ. Bỏ. Nhãn `LDL` (LAB) thì giữ.

### 2. `GT[318]` — `tràn dịch màng phổi trái tái phát`: GIỮ LẠI "trái"

Trước tôi cắt cả `trái tái phát`. Đếm nhãn DX/SYM có chữ vị trí trong bề mặt: **112 nhãn**
(`căng cứng vai trái` ×8, `xuất huyết dưới nhện vùng trán phải` ×4,
`tụ máu ngoài màng cứng phải cấp tính` ×2, `đau ngực trái cấp tính` ×2...).

Tức quy ước thực tế của tôi là **giữ** bên trái/phải; chỗ này cắt là ngoại lệ tự tạo. Cái
bị cắt theo `GT[280]` là "vị trí – mức độ" mô tả thêm, không phải bên của cơ quan.
→ `tràn dịch màng phổi trái`, mã J90 không đổi (J90 không phân biệt bên).

`tái phát` **vẫn cắt**, giữ lý lẽ cũ: câu là "Ung thư vú di căn, tràn dịch màng phổi trái
tái phát" — hai chẩn đoán nối bằng dấu phẩy, `tái phát` bổ nghĩa cả cụm nên không thuộc
riêng bề mặt nào. (7 nhãn khác trong GT có giữ `tái phát`, nhưng đều là trường hợp nó dính
liền một chẩn đoán duy nhất: `nhiễm khuẩn đường tiết niệu tái phát`, `chảy máu tái phát`.)

### 3. `GT[312]` — `Men tim`: BỎ NHÃN

Block đầy đủ:
```
Men tim
 • Troponin I/T ↑ (chẩn đoán nhồi máu)
 • CK-MB ↑
```
`Men tim` đứng một dòng riêng, bên dưới là 2 xét nghiệm con → **tiêu đề nhóm**, y như
`Sinh hóa & Men tim:` ở `GT[136]` mà tôi đã không gán. Trước tôi bào chữa bằng tiền lệ
`GT[195]` "Men gan", nhưng xem lại block 195 thì `• Men gan, albumin` nằm **ngang hàng**
trong danh sách chỉ định (`• Công thức máu, CRP, máu lắng` / `• Xét nghiệm nước tiểu` /
`• Cấy máu, dịch hầu họng`) — là tên xét nghiệm thật.

**Quy ước rút ra: có xét nghiệm con thụt vào bên dưới thì là tiêu đề, không gán.**

### 4. `GT[228]` — `vắc xin sống`: THÊM NHÃN (trước cố ý không gán)

Trước tôi không gán, lý lẽ "vắc xin là chế phẩm dự phòng, không phải thuốc điều trị". Nhưng
GT[338]/GT[344] đã gán `("vaccine phòng dại", DRUG, [])` và GT[118] gán cả bản bị mask 17
sao. Cùng là vắc xin mà chỗ gán chỗ không → model học nhiễu. Gán cho nhất quán,
`candidates` rỗng (RxNorm không có ingredient cho một LỚP vắc xin, đúng quy ước tên nhóm
thuốc để mã rỗng).

### 5. `GT[301]` — `Rối loạn vận động vùng` → I25.5: GIỮ

Mã này là suy **luận nguyên nhân**, không phải khớp tên, nên đáng ngờ. Nhưng kiểm bối cảnh
cả `18.txt`: các chẩn đoán khác là `nhồi máu` I21.9, `thiếu máu cơ tim` I25.9, `hẹp` I25.1,
`Dự phòng bệnh mạch vành` I25.9. Đây đúng là ca mạch vành → suy luận thiếu máu cục bộ có
căn cứ **trong chính block**, không phải tôi tự thêm. Không có mã nào sát hơn trong danh mục
(`I51.9`/`I51.8` mất thông tin nguyên nhân vành; `I50.1` dành cho rối loạn CHỨC NĂNG).

### 6. `GT[222]` — `mang thai được hơn 6 tuần` → TRIỆU_CHỨNG: GIỮ

Mang thai bình thường không phải triệu chứng. Nhưng đề chỉ có 5 loại, không có loại nào cho
tình trạng sinh lý, mà bỏ hẳn thì mất recall nếu GT của BTC có gán. `GT[148]`
(`mang thai được 22 tuần`) đã gán y vậy nên hai chỗ **nhất quán với nhau**. Giữ.

### Kết quả

GT: 3475 → **3473 entity** (bỏ 3, thêm 1). Kiểm lại: `0 span trùng/lồng, 0 lệch offset`.
Điểm val (oracle + từ điển) **không đổi: 83.64** — đúng như dự đoán vì cả 6 chỗ ở train.

## Chốt: đã phủ hết 332 block

Kiểm cuối: gán mỗi entity GT về block chứa nó qua `data/blocks/file_to_blocks.json`, rồi đếm
block có 0 nhãn.

    tong entity: 3473 | block: 332 | block 0 nhan: 8
    ky tu trong block 0 nhan: 524 / 189436  (0.28%)

Tám block đó đọc lại từng cái thì đều **đúng là không có gì để gán**:

| bid | n_chars | nội dung | vì sao rỗng |
|---|---|---|---|
| 217 | 261 | `- Thời gian: Không ghi rõ / - Tần suất: Không ghi rõ / ...` | toàn trường trống; `leo cầu thang`, `gập sâu` là hoạt động, không phải triệu chứng |
| 292 | 81 | `Can thiệp mạch vành qua da (PCI) / • Nong bóng / • Đặt stent` | thủ thuật — quy ước không gán |
| 306 | 62 | `3. Đánh giá tại bệnh viện / Kết quả chụp chẩn đoán hình ảnh` | tiêu đề mục |
| 320 | 51 | `2. Tiền sử bệnh hiện tại / Chưa phát hiện bất thường` | phủ định cái bất thường — quy ước không gán |
| 0 | 22 | `Câu hỏi từ người dùng:` | tiêu đề (xuất hiện 23 lần) |
| 23 | 19 | `1. Tiền sử bệnh lý` | tiêu đề |
| 330 | 16 | `1. Tiền sử bệnh` | tiêu đề |
| 331 | 12 | `Cận lâm sàng` | tiêu đề |

Nên phần gán nhãn tay **xong**. Việc còn lại duy nhất là train, và nó không chạy được ở máy
này (không có torch/transformers, sandbox chặn mạng ngoài allowlist).
