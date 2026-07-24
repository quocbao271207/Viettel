# -*- coding: utf-8 -*-
# ============================================================================
#  SapBERT ICD-10 — dựng index + gán mã cho concept phi-thuốc  (CHẠY TRÊN COLAB GPU)
# ============================================================================
# Dán từng "cell" (# %%) vào Colab. Runtime: chọn GPU (T4/L4). ~2-3 phút tổng.
#
# INPUT cần có trên Colab:
#   - data/icd10_raw/icd10cm_codes_2026.txt   (74.719 mã ICD-10-CM + mô tả EN)
#   - out/baseline_all.json                    (NER mở rộng: python3 src/extract_all.py)
# OUTPUT tải về:
#   - data/icd10_sapbert.pt   (index nhúng 74.719 mã — dùng lại nhiều lần)
#   - out/C_icd.zip           (submission đã gán mã ICD cho chẩn đoán + triệu chứng)
#
# Cách bơm input: hoặc `git clone <repo>` (cell 2a), hoặc Files>Upload 2 file trên (cell 2b).
# ============================================================================

# %% [cell 1] Cài đặt (Colab đã có torch+cuda, chỉ cần transformers)
# !pip -q install "transformers>=4.40" sentencepiece

# %% [cell 2a] Lấy repo (nếu là git). Bỏ qua nếu bạn Upload tay ở 2b.
# !git clone https://github.com/<user>/Viettel.git repo && cd repo
# import os; os.chdir("repo")

# %% [cell 2b] HOẶC upload tay: chạy rồi chọn icd10cm_codes_2026.txt + baseline_all.json
# from google.colab import files; up = files.upload()

# %% [cell 3] Load SapBERT lên GPU
import time, json, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModel, AutoTokenizer

MODEL = "cambridgeltl/SapBERT-UMLS-2020AB-all-lang-from-XLMR"
DEV = "cuda" if torch.cuda.is_available() else "cpu"
assert DEV == "cuda", "Bật GPU: Runtime > Change runtime type > T4 GPU"

tok = AutoTokenizer.from_pretrained(MODEL)
mdl = AutoModel.from_pretrained(MODEL).eval().half().to(DEV)   # fp16 cho nhanh
print(f"{MODEL.split('/')[-1]} | {sum(p.numel() for p in mdl.parameters())/1e6:.0f}M params | {DEV}")

@torch.inference_mode()
def embed(texts, bs=512):
    out, t0 = [], time.time()
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i+bs], return_tensors="pt", padding=True,
                  truncation=True, max_length=32).to(DEV)
        v = mdl(**enc).last_hidden_state[:, 0, :]                # CLS token
        out.append(torch.nn.functional.normalize(v, dim=-1).float().cpu())
        if i and i % (bs*10) == 0:
            r = i/(time.time()-t0); print(f"  {i:,}/{len(texts):,}  ~{(len(texts)-i)/r:.0f}s còn lại")
    return torch.cat(out)

# %% [cell 4] Dựng index: nhúng 74.719 mô tả ICD-10 (phần TỐN GPU, ~1-2 phút)
CODES_TXT = Path("data/icd10_raw/icd10cm_codes_2026.txt")
rows = [(l[:8].strip(), l[8:].strip())
        for l in CODES_TXT.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"nhúng {len(rows):,} mã ICD-10 ...")
t0 = time.time()
E = embed([desc for _, desc in rows])                            # [74719 x 768]
codes = [c for c, _ in rows]
print(f"xong {time.time()-t0:.0f}s -> {tuple(E.shape)}")
Path("data").mkdir(exist_ok=True)
torch.save({"E": E, "codes": codes}, "data/icd10_sapbert.pt")
print("-> data/icd10_sapbert.pt")

# %% [cell 5] Self-test: 12 bệnh tiếng Việt -> ICD (kỳ vọng ~top-1 6/12, top-5 9/12)
PROBE = [("suy tim, không đặc hiệu","I509"),("tăng huyết áp vô căn (nguyên phát)","I10"),
         ("viêm phổi","J189"),("thiếu men G6PD","D550"),("bệnh Kawasaki","M303"),
         ("viêm dạ dày","K2970"),("viêm loét đại tràng","K5190"),("hen phế quản","J45909"),
         ("nhồi máu cơ tim cấp","I219"),("suy thận mạn","N189"),("đái tháo đường type 2","E119"),
         ("viêm túi mật","K819")]
Q = embed([p[0] for p in PROBE]); S = Q @ E.T
t1 = t5 = 0
for i,(vi,want) in enumerate(PROBE):
    val, idx = S[i].topk(5); top = [codes[j] for j in idx]
    t1 += top[0]==want; t5 += want in top
    mark = "✅" if top[0]==want else ("🔶" if want in top else "❌")
    print(f" {mark} {vi[:34]:36s} -> {top[0]:7s} ({val[0]:.3f})  đúng={want}")
print(f">>> top-1 {t1}/12 | top-5 {t5}/12")

# %% [cell 6] Gán mã cho concept phi-thuốc trong baseline_all.json (một chiều, gần như không rủi ro)
preds = json.loads(Path("out/baseline_all.json").read_text(encoding="utf-8"))
tgt = [(fid,i,e) for fid,v in preds.items() for i,e in enumerate(v) if e["type"] != "THUỐC"]
print(f"gán mã cho {len(tgt)} concept phi-thuốc ...")
Qc = embed([e["text"] for _,_,e in tgt])
score, best = (Qc @ E.T).max(dim=1)
for (fid,i,_), b in zip(tgt, best.tolist()):
    preds[fid][i]["candidates"] = [codes[b]]                      # top-1; đổi sang giữ [] nếu score thấp nếu muốn
print(f"cosine trung bình {score.mean():.3f}")

# %% [cell 7] Xuất submission + tải về
import shutil, os
out = Path("out/C_icd/output"); shutil.rmtree(out.parent, ignore_errors=True); out.mkdir(parents=True)
for i in range(1,101):
    (out/f"{i}.json").write_text(json.dumps(preds[str(i)], ensure_ascii=False, indent=1), encoding="utf-8")
shutil.make_archive("out/C_icd","zip", root_dir=out.parent, base_dir="output")
print("-> out/C_icd.zip")
from google.colab import files
files.download("out/C_icd.zip"); files.download("data/icd10_sapbert.pt")
