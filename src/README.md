# src/ — bản đồ script

## Pipeline ĐANG DÙNG (Phase 1: NER LLM → mã → submission)

| Bước | Script | Vai trò |
|---|---|---|
| 0 | `sections.py` | đọc raw input (xử lý 20 file Unicode NFD) |
| 0 | `gazetteer.py` | nạp `data/gaz.json` (RxNorm 17.5k + ICD-10-CM 74.7k) |
| 1 | `gold_vote.py` | 1 LLM voter (API) NER 100 file → `dev/votes/<tên>.json` (cache resume) |
| 1 | `build_gold.py` | orchestrator: chạy mọi voter trong `dev/voters.json` + triangulate |
| 1 | `merge_votes.py` | gộp phiếu chạy theo mảnh (nếu có) → 1 file voter |
| 1 | `force_drugs.py` | pre-pass kiểm/ép concept tên-thuốc bị gán sai type (dùng `--dry` để kiểm) |
| 2 | `gold_triangulate.py` | gộp phiếu → `dev/gold_resolved.json`. Cờ: `--k` đồng thuận, `--voters` lọc, `--trust claude` giữ mọi cụm claude, `--out` |
| 3 | `rerank_prepare.py` | cụm distinct phi-thuốc → top-K SapBERT (`--skip-done` chỉ cụm mới) |
| 3 | `rerank_llm.py` | LLM (OpenAI API) chọn mã ICD đúng → `dev/rerank_out/<tên>.json` |
| 4 | `rerank_apply.py` | áp mã re-rank + THÊM DẤU CHẤM ICD → `out/candidates/<tên>.zip` |
| — | `evaluate.py` | chấm cục bộ pred vs gold |
| — | `test_sapbert.py` | dựng lại index `data/icd10_sapbert.pt` (220MB, không push git) |

Chuỗi lệnh chuẩn: xem HANDOFF.md §"Pipeline bản nộp KẾ TIẾP".

## Legacy (pipeline rule cũ, đã bị LLM vượt — giữ để tham chiếu / Phase 2)

| Script | Vai trò cũ |
|---|---|
| `extract.py` / `extract_all.py` | NER rule thuốc/bệnh/triệu chứng + RxNorm (extract.py vẫn được import: `find_drugs`, `build_drug_index`, `resolve_rxnorm`) |
| `autolabel.py` | dò từ điển (vẫn được import: `DISEASES` curated ICD) |
| `add_icd10.py` / `finalize_submission.py` | gán ICD bằng SapBERT top-1 (thay bằng re-rank LLM) |
| `context_vi.py` | assertion rule ConText (LLM làm tốt hơn) |
| `make_devset.py` / `probes.py` / `review_csv.py` | devset/probe/duyệt CSV thời data cũ |

Phiếu/nhãn tay thời cũ nằm ở `archive/` (xem `archive/dev-manual`, `archive/rerank_batches`).
