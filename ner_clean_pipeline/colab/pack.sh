#!/usr/bin/env bash
# Đóng gói phần tối thiểu cần mang lên Colab để train NER.
# Chạy: bash colab/pack.sh
# Output: artifacts/viettel_colab_data.zip
set -euo pipefail
cd "$(dirname "$0")/.."

# Bắt buộc build lại data train trước khi đóng gói: gt_blocks.py là thứ tôi sửa liên tục,
# quên bước này thì Colab train trên GT cũ mà không có gì báo.
python3 src/make_gt.py >/dev/null
python3 src/split.py >/dev/null
python3 src/gt_lexicon.py
python3 src/ner_data.py | tail -3

mkdir -p artifacts
OUT="artifacts/viettel_colab_data.zip"
python3 - <<'PY'
from pathlib import Path
import zipfile

root = Path.cwd()
out = root / "artifacts" / "viettel_colab_data.zip"
paths = [
    "src",
    "data/ner",
    "data/kb/icd10.json",
    "data/kb/rxnorm_drugs.json",
    "data/kb/gt_lexicon.json",
    "data/blocks/split.json",
    "data/gt_block",
    "input",
    "requirements.txt",
]

def keep(p: Path) -> bool:
    parts = set(p.parts)
    if "__pycache__" in parts:
        return False
    if p.name in {".DS_Store"}:
        return False
    return True

with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for rel in paths:
        p = root / rel
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and keep(f.relative_to(root)):
                    zf.write(f, f.relative_to(root).as_posix())
        else:
            zf.write(p, p.relative_to(root).as_posix())
PY

ls -lh "$OUT"
unzip -l "$OUT" | tail -1
