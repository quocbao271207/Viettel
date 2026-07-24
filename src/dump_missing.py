#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In raw + concept ĐÃ CÓ (bản assert_sol10) để Fable 5 trích THÊM concept thiếu.
    python3 src/dump_missing.py 11 13
"""
import json, sys, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import sections
ROOT=Path(__file__).resolve().parent.parent
z=zipfile.ZipFile(ROOT/'out/candidates/assert_sol10.zip')
a,b=int(sys.argv[1]),int(sys.argv[2])
for fid in range(a,b+1):
    raw=sections.read_raw(ROOT/'input'/f'{fid}.txt')
    ents=json.loads(z.read(f'output/{fid}.json'))
    print(f"\n{'='*70}\n### FILE {fid}  ({len(ents)} concept đã có)\n{'='*70}\n{raw}")
    print(f"\n--- ĐÃ CÓ ({len(ents)}) ---")
    for e in sorted(ents,key=lambda x:x['position'][0]):
        print(f"  [{e['type'][:3]}] {e['text']}")
