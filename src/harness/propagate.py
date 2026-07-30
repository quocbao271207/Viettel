#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LAN TRUYỀN nhãn qua các ĐOẠN VĂN TRÙNG NGUYÊN VĂN giữa các file.

    python3 -m src.harness.propagate --base out/candidates/42_tighten.zip --dry
    python3 -m src.harness.propagate --base out/candidates/42_tighten.zip \
        --out out/candidates/46_propagate.zip

Bộ data có nhiều file dùng lại nguyên xi từng đoạn của nhau (vd file 6 và 11 giống 78.5%,
chung nguyên văn phần mở đầu). Gold gần như chắc chắn gán nhãn NHẤT QUÁN trên các đoạn
giống hệt nhau — nên chỗ nào ta gán ở file này mà quên ở file kia là LỖI CỦA TA.

Vì sao tín hiệu này mạnh hơn mọi cách THÊM đã thử:
- bản 15/16/17 thêm concept do LLM tự nghĩ ra  -> lỗ, vì không có gì bảo chứng.
- bản 14 nhân bản text đã ăn điểm sang lần nhắc khác -> +1.26, cách THÊM duy nhất từng thắng.
- ở đây còn chặt hơn bản 14: không chỉ khớp `text` mà khớp NGUYÊN VĂN cả cửa sổ ~90 ký tự
  bao quanh. Cùng một câu, cùng một ngữ cảnh -> gold không có lý do gì gán khác nhau.

Đối chứng tự có: cùng cơ chế này xác nhận 1421 concept ĐÃ gán đúng chỗ ở cả hai file.
Tỉ lệ 1421 khớp / 118 sót cho thấy bộ nhãn vốn đã khá nhất quán — 118 ca kia là ngoại lệ.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import unicodedata                            # noqa: E402
from src.harness import spec, validate        # noqa: E402
from src.harness.build import code_map_from_base, write_zip  # noqa: E402

WIN = 45          # ký tự ngữ cảnh mỗi bên


def harmonize(args) -> None:
    """Cùng một đoạn văn ở 2 file mà ta gán 2 ranh giới khác nhau -> lấy bản NGẮN HƠN.

    Đây là oracle NỘI BỘ: không cần model, không cần gold. Gold gán nhãn đoạn giống hệt
    nhau thì phải giống nhau, nên hai ranh giới khác nhau nghĩa là ít nhất một bên sai.
    Chọn bản ngắn theo đúng thứ leaderboard đã xác nhận hai lần (bản 23 rồi bản 36).
    """
    base = validate.load_zip(Path(args.base))
    raws = {str(i): validate.read_raw(i) for i in range(1, 101)}
    # map: (file, start, end) -> ranh giới ngắn hơn tìm được ở file trùng đoạn
    better: dict[tuple[str, int, int], tuple[int, int]] = {}
    stats = Counter()
    for fid, items in base.items():
        ra = raws[fid]
        for e in items:
            s, t = e["position"]
            lo = max(0, s - args.win)
            win = ra[lo:t + args.win]
            if len(win) < (t - s) + 40:
                continue
            off = s - lo
            for f2, r2 in raws.items():
                if f2 == fid:
                    continue
                k = r2.find(win)
                if k < 0:
                    continue
                ns, nt = k + off, k + off + (t - s)   # vị trí TƯƠNG ỨNG ở file kia
                for e2 in base[f2]:
                    a, bnd = e2["position"]
                    if not (ns < bnd and nt > a) or (a, bnd) == (ns, nt):
                        continue
                    if e2["type"] != e["type"]:
                        stats["chồng lấn nhưng KHÁC TYPE — bỏ"] += 1
                        continue
                    if args.prefer_longer:
                        if (bnd - a) <= (t - s):
                            continue                  # bản kia không dài hơn
                    elif (bnd - a) >= (t - s):
                        continue                      # bản kia không ngắn hơn
                    # chiếu ranh giới ngắn của file kia về toạ độ file này
                    ms, mt = s + (a - ns), s + (bnd - ns)
                    if ms < 0 or mt > len(ra) or ra[ms:mt] != r2[a:bnd]:
                        stats["chiếu ngược không khớp nguyên văn — bỏ"] += 1
                        continue
                    cur = better.get((fid, s, t))
                    if cur is None or ((mt - ms) > (cur[1] - cur[0]) if args.prefer_longer
                                       else (mt - ms) < (cur[1] - cur[0])):
                        better[(fid, s, t)] = (ms, mt)
    cmap = code_map_from_base() if args.safe else {}
    out, changes = {}, []
    for fid, items in base.items():
        ra, rows, used = raws[fid], [], set()
        for e in items:
            s, t = e["position"]
            nb = better.get((fid, s, t))
            if nb is None or nb in used:
                rows.append(e)
                continue
            if args.safe:
                # "ngắn hơn thắng" được chứng minh cho việc cắt TỪ RÁC, không phải cắt
                # ĐỘ ĐẶC HIỆU LÂM SÀNG. Hai lá chắn:
                nt_ = ra[nb[0]:nb[1]]
                if spec.is_weak(nt_, e["type"]) or spec.is_banned(nt_, e["type"]):
                    stats["an toàn: rút về cụm bị cấm/1 âm tiết — GIỮ NGUYÊN"] += 1
                    rows.append(e)
                    continue
                key = (unicodedata.normalize("NFC", nt_).strip().lower(), e["type"])
                if e["candidates"] and e["type"] in spec.CODED_TYPES and key not in cmap:
                    stats["an toàn: rút ngắn làm MẤT MÃ — GIỮ NGUYÊN"] += 1
                    rows.append(e)
                    continue
            used.add(nb)
            changes.append((fid, e["text"], ra[nb[0]:nb[1]], e["type"]))
            rows.append({**e, "text": ra[nb[0]:nb[1]], "position": [nb[0], nb[1]]})
        out[fid] = sorted(rows, key=lambda r: (r["position"][0], r["position"][1]))

    print(f"nền {Path(args.base).name} | ĐỒNG BỘ RANH GIỚI qua đoạn văn trùng\n")
    for k, n in stats.most_common():
        print(f"   {n:5d}  {k}")
    print(f"\n{len(changes)} ranh giới thu ngắn theo bản của file trùng đoạn")
    for fid, old, new, ty in changes[:25]:
        print(f"   file {fid:>3s} {ty:18s} {old[:42]!r}  =>  {new[:30]!r}")
    if args.dry or not args.out:
        return
    n0, n1 = sum(len(v) for v in base.values()), sum(len(v) for v in out.values())
    assert n0 == n1, "số concept phải BẤT BIẾN"
    errs = validate.validate(out)
    if errs:
        print(f"\n❌ {len(errs)} lỗi — KHÔNG ghi zip")
        for e in errs[:20]:
            print("  -", e)
        raise SystemExit(1)
    write_zip(out, Path(args.out))
    print(f"\n✅ ghi {args.out}  ({n1} concept, số lượng bất biến)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="out/candidates/42_tighten.zip")
    ap.add_argument("--win", type=int, default=WIN,
                    help="ngữ cảnh mỗi bên (ký tự). Lớn hơn = chắc hơn nhưng ít ca hơn.")
    ap.add_argument("--harmonize", action="store_true",
                    help="ĐỒNG BỘ RANH GIỚI thay vì chỉ thêm: khi cùng một đoạn văn xuất hiện ở "
                         "2 file mà ta gán 2 ranh giới khác nhau, lấy bản NGẮN HƠN cho cả hai. "
                         "Đúng theo bằng chứng bản 23/36 (thu ngắn = +0.42, 85%% từ WER).")
    ap.add_argument("--prefer-longer", action="store_true",
                    help="ĐẢO HƯỚNG: lấy bản DÀI HƠN. Bằng chứng bản 48: đồng bộ về ngắn làm "
                         "WER xấu đi 0.72 trong khi J phẳng -> gold giữ bản DÀI ở các span đó.")
    ap.add_argument("--safe", action="store_true",
                    help="với --harmonize: KHÔNG rút ngắn nếu kết quả rơi vào cụm bị cấm/1 âm tiết "
                         "hoặc làm MẤT MÃ. 'Ngắn hơn thắng' đúng cho cắt TỪ RÁC, không đúng cho "
                         "cắt ĐỘ ĐẶC HIỆU LÂM SÀNG (mày đay vô căn L50.1 -> mày đay L50.9).")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    if args.harmonize:
        return harmonize(args)

    base = validate.load_zip(Path(args.base))
    raws = {str(i): validate.read_raw(i) for i in range(1, 101)}
    have = {f: {(e["position"][0], e["position"][1]) for e in v} for f, v in base.items()}
    spans = {f: sorted((e["position"][0], e["position"][1]) for e in v) for f, v in base.items()}

    add: dict[str, dict[tuple[int, int], dict]] = {f: {} for f in base}
    stats = Counter()
    for fid, items in base.items():
        ra = raws[fid]
        for e in items:
            s, t = e["position"]
            lo = max(0, s - args.win)
            win = ra[lo:t + args.win]
            if len(win) < (t - s) + 40:        # sát biên file -> ngữ cảnh yếu, bỏ
                stats["ngữ cảnh quá ngắn (sát biên file)"] += 1
                continue
            off = s - lo
            for f2, r2 in raws.items():
                if f2 == fid:
                    continue
                k = r2.find(win)
                if k < 0:
                    continue
                ns, nt = k + off, k + off + (t - s)
                if r2[ns:nt] != e["text"]:
                    continue
                if (ns, nt) in have[f2]:
                    stats["đã có ở file kia — XÁC NHẬN"] += 1
                    continue
                if any(ns < b and nt > a for a, b in spans[f2]):
                    stats["chồng lấn span sẵn có ở file kia — BỎ"] += 1
                    continue
                if (ns, nt) in add[f2]:
                    stats["đã xếp hàng thêm rồi"] += 1
                    continue
                add[f2][(ns, nt)] = {"text": e["text"], "type": e["type"],
                                     "candidates": list(e["candidates"]),
                                     "assertions": list(e["assertions"]),
                                     "position": [ns, nt], "_from": fid}
                stats["THÊM"] += 1

    out = {f: sorted(list(v) + [{k2: v2 for k2, v2 in r.items() if not k2.startswith("_")}
                                for r in add[f].values()],
                     key=lambda r: (r["position"][0], r["position"][1]))
           for f, v in base.items()}
    n0, n1 = sum(len(v) for v in base.values()), sum(len(v) for v in out.values())
    print(f"nền {Path(args.base).name}: {n0} concept | ngữ cảnh ±{args.win} ký tự\n")
    for k, n in stats.most_common():
        print(f"   {n:5d}  {k}")
    print(f"\nTHÊM {n1-n0} concept -> {n1}")
    ty = Counter(r["type"] for f in add for r in add[f].values())
    for k, n in ty.most_common():
        print(f"   {k:22s} {n:4d}")
    coded = sum(1 for f in add for r in add[f].values() if r["candidates"])
    print(f"   {coded} concept thêm vào ĐÃ CÓ SẴN mã (chép từ file nguồn)")

    print("\n20 ca đầu:")
    for f in sorted(add, key=int):
        for r in list(add[f].values())[:2]:
            print(f"   file {r['_from']:>3s} -> {f:>3s}  {r['type']:18s} {r['text'][:40]!r}")

    if args.dry or not args.out:
        return
    errs = validate.validate(out)
    if errs:
        print(f"\n❌ {len(errs)} lỗi — KHÔNG ghi zip")
        for e in errs[:20]:
            print("  -", e)
        raise SystemExit(1)
    write_zip(out, Path(args.out))
    print(f"\n✅ ghi {args.out}  ({n1} concept)")


if __name__ == "__main__":
    main()
