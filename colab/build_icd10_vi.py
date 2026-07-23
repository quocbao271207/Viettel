# %% [markdown]
# # Dựng gazetteer ICD-10-CM tiếng Việt  (chạy trên Colab Pro, GPU T4/L4)
#
# **Vì sao đây là vũ khí chính của Bài 2.**
#
# Đã kiểm chứng: các cụm chẩn đoán trong `input/` CHÍNH LÀ preferred term của
# ICD-10-CM được dịch máy sang tiếng Việt. Đối chiếu tay 12/12 khớp **nguyên văn**:
#
# | Text trong file | ICD-10-CM | Mã |
# |---|---|---|
# | `u cơ trơn tử cung, không đặc hiệu` | Leiomyoma of uterus, unspecified | D25.9 |
# | `xuất huyết nội sọ không do chấn thương, không đặc hiệu` | Nontraumatic intracranial hemorrhage, unspecified | I62.9 |
# | `bệnh thận mạn, không đặc hiệu` | Chronic kidney disease, unspecified | N18.9 |
# | `tăng huyết áp vô căn (nguyên phát)` | Essential (primary) hypertension | I10 |
#
# Đuôi "**, không đặc hiệu**" là dấu vân tay của ICD-10. Hệ quả: **ranh giới span của
# `CHẨN_ĐOÁN` là biên của thuật ngữ ICD-10, không phải do người gán tuỳ ý** => có thể
# TRA TỪ ĐIỂN ra cả span lẫn mã, thay vì đoán bằng LLM.
#
# Vì `final ≈ 0.3·T + 0.3·Jc·acc_ass + 0.4·Jc·acc_cand` (Jc = Jaccard tập concept),
# việc này ăn cả 3 thành phần cùng lúc. Kéo Jc 0.60→0.80 = **+18 điểm**.
#
# **Lưu ý tuân thủ:** model dịch chỉ dùng OFFLINE để dựng gazetteer, KHÔNG nằm trong
# pipeline nộp bài (luật cấm API ngoài; trần 9B áp cho model trong giải pháp).
# Gazetteer sinh ra là một *file dữ liệu* — nhớ kê khai trong mục "Data nhóm sử dụng".

# %%
!pip -q install rapidfuzz sentencepiece transformers accelerate

import json, re, unicodedata, time, os
from pathlib import Path
import torch

DEV = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", DEV, torch.cuda.get_device_name(0) if DEV == "cuda" else "")

# %% [markdown]
# ## 1. Tải ICD-10-CM 2026 (CMS, chính thức, free, không cần đăng ký)

# %%
!wget -q -O icd10.zip https://www.cms.gov/files/zip/2026-code-descriptions-tabular-order.zip
!unzip -o -q icd10.zip -d icd10_raw

rows = []
for ln in open("icd10_raw/icd10cm_codes_2026.txt", encoding="utf-8"):
    if ln.strip():
        rows.append((ln[:8].strip(), ln[8:].strip()))
print(f"{len(rows):,} mã ICD-10-CM")          # kỳ vọng 74,719
print(rows[:3])

# %% [markdown]
# ## 2. Dịch EN -> VI
#
# **Chọn model.** `facebook/nllb-200-distilled-600M` bị **CC-BY-NC-4.0 (phi thương
# mại)** — TRÁNH, vì giải có thưởng 200M VNĐ và BTC sẽ đọc code.
#
# | Model | License | Ghi chú |
# |---|---|---|
# | `VietAI/envit5-translation` | openrail | chuyên Việt, chất lượng tốt hơn — mặc định |
# | `Helsinki-NLP/opus-mt-en-vi` | **apache-2.0** | nhỏ/nhanh nhất, license sạch nhất |
# | `vinai/vinai-translate-en2vi-v2` | agpl-3.0 | copyleft, cân nhắc |
#
# envit5 cần tiền tố `"en: "` và sinh ra `"vi: ..."`.

# %%
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL = "VietAI/envit5-translation"   # đổi sang Helsinki-NLP/opus-mt-en-vi nếu cần license sạch
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, torch_dtype=torch.float16).to(DEV).eval()

def translate(texts, bs=96, max_new=64):
    out = []
    t0 = time.time()
    for i in range(0, len(texts), bs):
        batch = [f"en: {t}" for t in texts[i:i+bs]]
        enc = tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=64).to(DEV)
        with torch.inference_mode():
            gen = model.generate(**enc, max_new_tokens=max_new, num_beams=1)
        out += [re.sub(r"^vi:\s*", "", s) for s in tok.batch_decode(gen, skip_special_tokens=True)]
        if i % (bs*40) == 0:
            done = i + len(batch)
            rate = done / max(time.time()-t0, 1e-9)
            print(f"  {done:6,}/{len(texts):,}  {rate:5.0f}/s  còn ~{(len(texts)-done)/max(rate,1e-9)/60:.0f} phút")
    return out

# Chạy thử 12 câu ĐÃ BIẾT ĐÁP ÁN trước khi đốt 30 phút cho cả 74k.
probe_en = ["Leiomyoma of uterus, unspecified",
            "Nontraumatic intracranial hemorrhage, unspecified",
            "Chronic kidney disease, unspecified",
            "Heart failure, unspecified",
            "Essential (primary) hypertension",
            "Chronic obstructive pulmonary disease, unspecified",
            "Urinary tract infection, site not specified",
            "Gout, unspecified",
            "Hypotension, unspecified",
            "Primary hyperparathyroidism"]
expect_vi = ["u cơ trơn tử cung, không đặc hiệu",
             "xuất huyết nội sọ không do chấn thương, không đặc hiệu",
             "bệnh thận mạn, không đặc hiệu",
             "suy tim, không đặc hiệu",
             "tăng huyết áp vô căn (nguyên phát)",
             "bệnh phổi tắc nghẽn mạn tính, không xác định",
             "nhiễm khuẩn đường tiết niệu, vị trí không xác định",
             "bệnh gút không đặc hiệu",
             "hạ huyết áp, không đặc hiệu",
             "cường cận giáp nguyên phát"]

from rapidfuzz import fuzz
got = translate(probe_en, bs=16)
print("\n=== SANITY CHECK: bản dịch của ta có gần bản dịch của BTC không? ===")
print("(không cần khớp 100% — chỉ cần đủ gần để fuzzy match bắt được)\n")
scores = []
for en, vi_got, vi_want in zip(probe_en, got, expect_vi):
    s = fuzz.token_set_ratio(vi_got.lower(), vi_want.lower())
    scores.append(s)
    print(f"  [{s:3.0f}] {en[:44]:46s}\n        ta  : {vi_got}\n        BTC : {vi_want}")
print(f"\n>>> fuzzy trung bình: {sum(scores)/len(scores):.1f}/100")
print(">>> >=80 : gazetteer sẽ chạy tốt.  60-80 : phải hạ ngưỡng + thêm embedding.")
print(">>> <60  : ĐỔI MODEL DỊCH (thử Helsinki-NLP/opus-mt-en-vi hoặc vinai) trước khi chạy 74k.")

# %% [markdown]
# ## 3. Dịch toàn bộ 74.719 mã  (~15-30 phút trên T4)
#
# CHỈ chạy khi sanity check ở trên đạt. Kết quả cache ra file để khỏi chạy lại.

# %%
CACHE = Path("icd10_vi.json")
if CACHE.exists():
    icd_vi = json.loads(CACHE.read_text())
    print(f"đọc lại cache: {len(icd_vi):,}")
else:
    descs = [d for _, d in rows]
    vi = translate(descs)
    icd_vi = [{"code": c, "en": d, "vi": v} for (c, d), v in zip(rows, vi)]
    CACHE.write_text(json.dumps(icd_vi, ensure_ascii=False))
    print(f"xong: {len(icd_vi):,} -> {CACHE}")

# %% [markdown]
# ## 4. Khớp gazetteer vào văn bản  (sinh span CHẨN_ĐOÁN + mã ICD-10 cùng lúc)
#
# 74k thuật ngữ × mọi cửa sổ từ = quá lớn để so tất cả. Dùng **inverted index theo
# token hiếm** để lọc ứng viên trước, rồi mới cho rapidfuzz chấm điểm.

# %%
from collections import defaultdict, Counter

def norm(s):
    s = unicodedata.normalize("NFC", s).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\sÀ-ỹ]", " ", s)).strip()

df = Counter()
for r in icd_vi:
    df.update(set(norm(r["vi"]).split()))

STOP = {w for w, c in df.items() if c > 3000}   # token quá phổ biến -> vô dụng để lọc
inv = defaultdict(list)
for i, r in enumerate(icd_vi):
    toks = [t for t in set(norm(r["vi"]).split()) if t not in STOP and len(t) > 2]
    for t in sorted(toks, key=lambda x: df[x])[:3]:   # 3 token hiếm nhất
        inv[t].append(i)
print(f"inverted index: {len(inv):,} token | bỏ {len(STOP)} token quá phổ biến")

def match_span(text, threshold=88):
    """Trả (mã, thuật ngữ VI, điểm) khớp tốt nhất cho một đoạn text, hoặc None."""
    q = norm(text)
    if len(q) < 6:
        return None
    cand = set()
    for t in q.split():
        cand.update(inv.get(t, ())[:400])
    best = None
    for i in cand:
        s = fuzz.token_set_ratio(q, norm(icd_vi[i]["vi"]))
        if s >= threshold and (best is None or s > best[2]):
            best = (icd_vi[i]["code"], icd_vi[i]["vi"], s)
    return best

# %% [markdown]
# ## 5. Chạy thử trên các cụm đã biết đáp án

# %%
tests = [("u cơ trơn tử cung, không đặc hiệu", "D259"),
         ("xuất huyết nội sọ không do chấn thương, không đặc hiệu", "I629"),
         ("bệnh thận mạn, không đặc hiệu", "N189"),
         ("suy tim, không đặc hiệu", "I509"),
         ("bệnh phổi tắc nghẽn mạn tính, không xác định", "J449"),
         ("hội chứng turner, không đặc hiệu", "Q969"),
         ("bệnh gút không đặc hiệu", "M109")]
ok = 0
for vi, want in tests:
    m = match_span(vi)
    hit = m and m[0] == want
    ok += bool(hit)
    print(f"  {'✅' if hit else '❌'} {vi[:44]:46s} -> {m[0] if m else None:>6} (đúng {want})")
print(f"\n>>> {ok}/{len(tests)}")

# %% [markdown]
# ## 6. Quét toàn bộ input/ -> ứng viên CHẨN_ĐOÁN
#
# Upload `input/` và `src/sections.py` lên Colab trước khi chạy ô này.

# %%
import sys; sys.path.insert(0, ".")
import sections

found, lines_tot = [], 0
for i in range(1, 101):
    raw = sections.read_raw(f"input/{i}.txt")
    for ln in sections.parse(raw):
        if ln.skip:
            continue
        lines_tot += 1
        m = match_span(ln.text)
        if m:
            found.append({"file": i, "text": ln.text, "code": m[0], "icd_vi": m[1], "score": m[2],
                          "position": [ln.start, ln.end]})

print(f"Khớp ICD-10 ở {len(found)}/{lines_tot} dòng nội dung ({len(found)/lines_tot:.1%})\n")
for f in found[:25]:
    print(f"  [{f['score']:3.0f}] {f['code']:6s} {f['text'][:44]:46s} <- {f['icd_vi'][:40]}")

Path("icd10_matches.json").write_text(json.dumps(found, ensure_ascii=False, indent=1))
print(f"\n-> icd10_matches.json ({len(found)} khớp). Tải về máy, đặt vào data/.")

# %% [markdown]
# ## 7. Bước tiếp theo
#
# 1. **Chỉnh `threshold`** (mục 4). Cao = precision (an toàn cho WER), thấp = recall.
#    Đo trên dev set đã gán nhãn bằng `src/evaluate.py`, ĐỪNG đo bằng lượt nộp.
# 2. **Cắt span cho khít.** Hiện đang khớp cả dòng. Gold chỉ lấy đúng phần thuật ngữ
#    ICD (VD dòng `bệnh thận mạn, không đặc hiệu Giai đoạn 4` thì gold có thể chỉ là
#    `bệnh thận mạn, không đặc hiệu`). Cần dò cửa sổ con để tìm span khít nhất.
# 3. **Định dạng mã**: file CMS ghi `D259` (không chấm). Chưa rõ BTC muốn `D259` hay
#    `D25.9` — probe **P9 vs P9b** trả lời (xem `src/probes.py`).
# 4. **Round 1 đã chấm ICD-10 chưa?** Probe **P9**. Nếu chưa thì để `candidates: []`
#    cho CHẨN_ĐOÁN và giữ gazetteer chỉ để tìm span (vẫn ăn text + Jc).
