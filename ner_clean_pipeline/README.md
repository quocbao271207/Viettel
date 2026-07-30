# Viettel AI Race 2026 — Đề 2: Chuẩn hoá khái niệm y tế tiếng Việt

Trích xuất khái niệm y tế từ văn bản lâm sàng tiếng Việt, gán `assertions` và tra mã
ICD-10 / RxNorm.

## Chạy để sinh kết quả

```bash
pip install -r requirements.txt
python src/ner_infer.py --model models/ner --input input --out submission
```

Sinh 100 file `submission/<n>.json`, mỗi file là một list các dict
`{text, position, type, assertions, candidates}`.

**Không gọi mạng.** `--model` là đường dẫn thư mục trên đĩa (weights nộp kèm trong
`models/ner`), load bằng `local_files_only=True`. Từ điển ICD-10/RxNorm đọc từ `data/kb/`
dưới dạng JSON đã đóng gói sẵn. Chạy được trong môi trường ngắt mạng hoàn toàn.

Chạy trên CPU được nhưng chậm; có GPU thì tự dùng CUDA. Tham số `--device cpu` để buộc CPU.

## Kiến trúc

Ba tầng, chia theo chỗ nào đo được cái gì:

| tầng | ai làm | vì sao |
|---|---|---|
| `text` + `position` + `type` | model NER (token classification, BIO) | đây là nút thắt điểm |
| `assertions` | luật theo mục văn bản | đo được: bật luật hiện tại LỖ 0.16đ nên mặc định TẮT |
| `candidates` | luật tra từ điển theo bề mặt model trả về | Jaccard phạt mã sai; luật thì hoặc đúng hoặc rỗng |

Model: `xlm-roberta-large` fine-tune token classification, 11 nhãn
(`O` + `B-`/`I-` × 5 loại). Chọn XLM-R chứ không PhoBERT vì 22.7% bề mặt khái niệm là
thuần ASCII (tên thuốc tiếng Anh) và vì XLM-R có `return_offsets_mapping` nên map ngược về
offset ký tự gốc chính xác — đề chấm theo `position` nên sai offset là mất điểm.

Model **không** đoán mã. `candidates_score` dùng Jaccard nên trả mã sai vừa mất điểm khái
niệm đó vừa không được gì, trong khi rỗng-khớp-rỗng vẫn được J=1. Tra mã bằng 3 luật xếp
tầng (chi tiết + số đo trong `worklog/08`):

1. từ điển bề mặt → mã, học từ phần train của dữ liệu gán tay (`src/gt_lexicon.py`)
2. tên chuẩn ICD-10/RxNorm, khớp chính xác sau lower/strip
3. tra gần đúng theo tập từ, ngưỡng Jaccard-từ 0.7

Mã tra từ tên chuẩn còn đi qua `collapse_group()`: tra ra nhiều mã con cùng nhóm 3 ký tự thì
quy về mã nhóm, vì bề mặt trong văn bản là tên trần không nói cấp/thể.

## Dữ liệu huấn luyện

100 file trong `input/` được gán nhãn **thủ công** ở cấp block (`src/gt_blocks.py` →
`data/gt_block/`): **3473 khái niệm**. Không dùng model ngoài để gán.

Gán theo block chứ không theo file vì corpus có lặp: cùng một đoạn nguồn xuất hiện ở nhiều
file với chất lượng dịch và độ che khác nhau. `data/blocks.json` là chỉ mục block; một nhãn
gán một lần được áp cho mọi file chứa block đó.

Chia train/val theo **nhóm block** (`data/blocks/split.json`) để không rò rỉ: 80 file /
256 block train, 20 file / 76 block val, **0 block nằm cả hai bên**. Split đã đóng băng.

Từ điển học ở bước 1 chỉ học từ **train**, không học val — nếu học cả val thì số đo trên val
thành vô nghĩa.

## Huấn luyện lại

```bash
python src/ner_data.py                      # gt_block -> cửa sổ token cho model
python src/ner_train.py --model xlm-roberta-large \
  --out models/ner --epochs 20 --bs 8 --accum 2 --lr 2e-5 --bf16 --all
```

`--bf16` chứ không `--fp16`: XLM-R large với fp16 rất dễ ra NaN loss. `--all` train trên cả
100 file cho bản nộp cuối (chốt số epoch ở vòng có val sạch trước).

Chọn checkpoint theo **recall**, không phải F1: đo được recall 100% với `assertions` và
`candidates` để rỗng đã là 77.35 điểm, tức recall đáng khoảng 22 lần hai trường kia cộng lại.

Notebook Colab: `colab/train_ner.ipynb`. Đóng gói dữ liệu: `bash colab/pack.sh`.

## Đánh giá offline

```bash
python src/score.py --gt data/gt_block --pred submission --split val
```

Cài đúng công thức của đề (`0.3·text + 0.3·assertions + 0.4·candidates`, WER cho text,
Jaccard cho hai trường kia). Ghép khái niệm pred↔GT theo `overlap`: cùng `type` và có giao
ký tự, ghép 1-1 greedy — theo đúng "Lưu ý" của đề rằng đoán đúng text nhưng sai loại thì bị
tính 2 lần và cả hai lần đều 0 điểm.

Mốc trên val (split đã đóng băng):

| | val |
|---|---|
| luật thuần, không model | 24.10 |
| trần nếu model đoán span hoàn hảo | 84.62 |

## Cấu trúc

```
src/ner_infer.py     sinh kết quả cuối (điểm vào khi chấm)
src/ner_train.py     train token classification
src/ner_data.py      gt_block -> cửa sổ huấn luyện
src/gt_blocks.py     dữ liệu gán tay, cấp block
src/make_gt.py       gt_blocks -> data/gt_block/*.json
src/gt_lexicon.py    học từ điển bề mặt -> mã, từ train
src/lexicon.py       đọc từ điển ICD-10 / RxNorm
src/score.py         chấm offline theo công thức đề
src/predict.py       luật (dedup span, assertions)
src/blocks.py        tìm block lặp giữa các file
src/split.py         chia train/val theo nhóm block
data/kb/             từ điển đã đóng gói (JSON, dùng lúc inference)
data/gt_block/       nhãn gán tay, 100 file
models/ner/          weights
worklog/             nhật ký làm việc, mọi số đo và ngõ cụt
```

## Nguồn dữ liệu ngoài và ghi nhận

**RxNorm** (mã thuốc): dùng dữ liệu công khai của U.S. National Library of Medicine (NLM).

> This product uses publicly available data from the U.S. National Library of Medicine
> (NLM), National Institutes of Health, Department of Health and Human Services; NLM is not
> responsible for the product and does not endorse or recommend this or any other product.

File gốc `RXNCONSO.RRF` (RxNorm full monthly release, phần không cần UMLS license) được rút
thành `data/kb/rxnorm_drugs.json` (10910 tên thuốc → RxCUI, ưu tiên IN > BN > PIN). Bản
đóng gói chỉ chứa file JSON đã rút, không chứa bản RxNorm gốc.

**ICD-10** (mã bệnh): Phụ lục Danh mục ICD-10 theo Thông tư của Bộ Y tế Việt Nam, có cả tên
tiếng Việt và tên WHO English. Đây là phụ lục văn bản quy phạm pháp luật Việt Nam — theo
Luật Sở hữu trí tuệ Điều 15, văn bản quy phạm pháp luật không thuộc phạm vi bảo hộ quyền tác
giả. Rút thành `data/kb/icd10.json` (13882 tên bệnh → mã).

Không dùng UMLS. Không gọi API ngoài lúc inference. Không dùng model ngoài để gán nhãn.

## Môi trường

Python 3.13, `transformers>=4.44`, `torch`, `accelerate`, `sentencepiece`, `numpy`. Xem
`requirements.txt`. Train trên Colab L4/A100 (bf16).
