"""KB ICD-10 tiếng Việt + luật sinh candidate mô phỏng annotator.

Nguồn: danh mục ICD-10 Bộ Y tế (Phụ lục Thông tư), 15.037 mã, có tên VI + EN.

Luật sinh candidate suy ra từ ví dụ trong đề (xem worklog/01):
  mention "bệnh trào ngược dạ dày - thực quản" -> GT = {K21.0, K21.9}
  trong khi K21 có tên VI khớp CHÍNH XÁC từng chữ với mention.
  Danh mục BYT đánh cờ K21 là "không được dùng vì có mã 4-5 ký tự cụ thể hơn".
=> match tên -> nếu mã trúng bị cờ đó thì BUNG ra mã con, BỎ mã cha.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "data" / "raw" / "icd10_byt.csv"
OUT_JSON = ROOT / "data" / "kb" / "icd10.json"

RE_CODE = re.compile(r"^[A-Z]\d{2}(\.\d+)?$")

# Cột trong CSV danh mục BYT (header ở dòng index 2, data từ index 4)
COL_GRP3 = 14  # mã nhóm bệnh 3 ký tự
COL_GRP3_VI = 16  # tên nhóm bệnh 3 ký tự (VI)
COL_CODE = 17  # mã ICD đầy đủ
COL_EN = 19  # disease name WHO 2019 (EN)
COL_VI = 21  # tên bệnh (VI)
COL_NO_PRIMARY = 23  # cờ: không được dùng làm bệnh chính
COL_HAS_SPECIFIC = 25  # cờ: không dùng vì có mã 4-5 ký tự cụ thể hơn


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize(s: str) -> str:
    """Chuẩn hóa để so khớp tên bệnh: bỏ dấu câu, gộp trắng, lower."""
    t = unicodedata.normalize("NFC", s).lower()
    t = re.sub(r"[^\w\s]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class IcdEntry:
    code: str
    vi: str
    en: str
    grp3: str
    grp3_vi: str
    no_primary: bool  # cờ cột 23
    has_specific: bool  # cờ cột 25 -> không nên trả mã này, phải bung mã con


@dataclass
class IcdKB:
    entries: dict[str, IcdEntry] = field(default_factory=dict)
    by_norm_vi: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    children: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def load_csv(cls, path: Path = RAW_CSV) -> "IcdKB":
        kb = cls()
        rows = list(csv.reader(path.open(encoding="utf-8-sig")))
        for r in rows[4:]:
            if len(r) <= COL_HAS_SPECIFIC:
                continue
            code = clean(r[COL_CODE])
            if not RE_CODE.match(code):
                continue
            e = IcdEntry(
                code=code,
                vi=clean(r[COL_VI]),
                en=clean(r[COL_EN]),
                grp3=clean(r[COL_GRP3]),
                grp3_vi=clean(r[COL_GRP3_VI]),
                no_primary=bool(clean(r[COL_NO_PRIMARY])),
                has_specific=bool(clean(r[COL_HAS_SPECIFIC])),
            )
            kb.entries[code] = e
            if e.vi:
                kb.by_norm_vi[normalize(e.vi)].append(code)
            if "." in code:
                kb.children[code.split(".")[0]].append(code)
        return kb

    def expand(self, code: str) -> list[str]:
        """Áp luật annotator: nếu mã bị cờ 'có mã cụ thể hơn' thì bung mã con."""
        e = self.entries.get(code)
        if e is None:
            return []
        if e.has_specific and self.children.get(code):
            return sorted(self.children[code])
        return [code]

    def lookup_exact(self, mention: str) -> list[str]:
        """Tra tên khớp chính xác (sau chuẩn hóa), đã áp luật bung mã con."""
        hits = self.by_norm_vi.get(normalize(mention), [])
        out: list[str] = []
        for h in hits:
            out.extend(self.expand(h))
        return sorted(set(out))

    def save(self, path: Path = OUT_JSON) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": {
                c: {
                    "vi": e.vi,
                    "en": e.en,
                    "grp3": e.grp3,
                    "no_primary": e.no_primary,
                    "has_specific": e.has_specific,
                }
                for c, e in self.entries.items()
            },
            "children": {k: sorted(v) for k, v in self.children.items()},
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    kb = IcdKB.load_csv()
    kb.save()

    n_specific = sum(1 for e in kb.entries.values() if e.has_specific)
    n_no_prim = sum(1 for e in kb.entries.values() if e.no_primary)
    print("=== KB ICD-10 BYT ===")
    print(f"  mã               {len(kb.entries)}")
    print(f"  tên VI độc nhất  {len(kb.by_norm_vi)}")
    print(f"  mã 3 ký tự có con {len(kb.children)}")
    print(f"  cờ 'có mã cụ thể hơn' (cột 25)  {n_specific}")
    print(f"  cờ 'không làm bệnh chính' (cột 23) {n_no_prim}")

    print("\n=== kiểm chứng luật trên ví dụ của đề ===")
    m = "bệnh trào ngược dạ dày - thực quản"
    got = kb.lookup_exact(m)
    print(f"  mention: {m!r}")
    print(f"  → {got}   (GT đề bài: ['K21.0', 'K21.9'])")
    print(f"  KHỚP" if got == ["K21.0", "K21.9"] else f"  LỆCH")
