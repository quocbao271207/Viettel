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

build_teacher() {
  local tag="$1"
  local zip="$2"
  local make_ner="${3:-0}"
  if [[ -f "$zip" ]]; then
    python3 src/teacher_from_zip.py --zip "$zip" --out "data/teacher_${tag}"
    if [[ "$make_ner" == "1" ]]; then
      python3 src/gt_lexicon.py --gt "data/teacher_${tag}" --out "data/kb/gt_lexicon_teacher_${tag}.json" --split all
      python3 src/ner_data.py --gt "data/teacher_${tag}" --out "data/ner_teacher_${tag}" | tail -3
    fi
  else
    echo "WARN: không thấy $zip, bỏ qua data/teacher_${tag}"
  fi
}

build_teacher 82x artifacts/teammate_latest_candidates/82x_cleanroom4_k2.zip 1
build_teacher 85 artifacts/teammate_latest_candidates/85_cleanroom_curated_assert.zip 0
build_teacher 87 artifacts/teammate_latest_candidates/87_cleanroom_k1_curated.zip 1
build_teacher 88 artifacts/teammate_latest_candidates/88_cleanroom_k3_curated.zip 1

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
    "data/ner_teacher_82x",
    "data/ner_teacher_87",
    "data/ner_teacher_88",
    "data/kb/icd10.json",
    "data/kb/rxnorm_drugs.json",
    "data/kb/gt_lexicon.json",
    "data/kb/gt_lexicon_teacher_82x.json",
    "data/kb/gt_lexicon_teacher_87.json",
    "data/kb/gt_lexicon_teacher_88.json",
    "data/blocks/split.json",
    "data/gt_block",
    "data/teacher_82x",
    "data/teacher_85",
    "data/teacher_87",
    "data/teacher_88",
    "input",
    "requirements.txt",
    "colab/viettel_distill_82x_colab.ipynb",
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
        if not p.exists():
            continue
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and keep(f.relative_to(root)):
                    zf.write(f, f.relative_to(root).as_posix())
        else:
            zf.write(p, p.relative_to(root).as_posix())
PY

ls -lh "$OUT"
unzip -l "$OUT" | tail -1
