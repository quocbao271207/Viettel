#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Áp assertion đã duyệt theo ngữ cảnh (bởi Fable 5) vào dev/gold_curated.json.

    python3 src/apply_assertions.py dev/assertion_patch.json
patch = {"73": {"0":"isHistorical","1":"isHistorical",...}, ...}  (chỉ ghi index có mặt; "" = ∅).
An toàn: chỉ đổi trường assertions của concept theo index, KHÔNG đụng text/type/candidates/position.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "dev/gold_curated.json"


def main():
    patch = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    g = json.loads(GOLD.read_text(encoding="utf-8"))
    changed = 0
    for fid, m in patch.items():
        ents = g.get(fid, [])
        for idx, a in m.items():
            i = int(idx)
            if 0 <= i < len(ents):
                new = [a] if a else []
                if ents[i].get("assertions", []) != new:
                    ents[i]["assertions"] = new
                    changed += 1
    GOLD.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"đã đổi {changed} assertion trong {len(patch)} file -> {GOLD.name}")


if __name__ == "__main__":
    main()
