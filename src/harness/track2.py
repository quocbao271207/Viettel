#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRACK 2 — data train + giải mã inference cho model self-host ≤9B.

    python3 -m src.harness.track2 prep    --gold out/candidates/82x_cleanroom4_k2.zip
    python3 -m src.harness.track2 verify                       # trần trên, KHÔNG cần GPU
    python3 -m src.harness.track2 decode  --pred qwen_out.jsonl --out out/candidates/track2.zip

## Vì sao viết lại thay vì dùng `src/track2_*.py` cũ

**Định dạng cũ sẽ TIMEOUT.** Đề cho 600 giây cho toàn bộ inference (Phase 2/3) = 6 giây/file.
Nhãn JSON đầy đủ nặng ~99 ký tự/concept ⇒ ~1060 token/file ⇒ cần ~177 token/giây.
Model 7B trên T4 với HF transformers chạy 15-25 token/s — **chậm gấp 9 lần**. Track 2 sẽ
timeout dù model học tốt đến đâu, và không ai phát hiện cho tới lúc chấm.

Định dạng gọn ở đây: **~22 ký tự/concept**, giảm 4.5 lần.

    D|Bệnh Kawasaki|1.
    TH|sốt|nhân có
    MN|paracetamol|dùng

  ký tự 1     : type   M=THUỐC D=CHẨN_ĐOÁN T=TRIỆU_CHỨNG X=TÊN_XÉT_NGHIỆM K=KẾT_QUẢ_XÉT_NGHIỆM
  ký tự 2..   : assertion  N=isNegated H=isHistorical F=isFamily  (rỗng = [])
  trường 2    : text nguyên văn
  trường 3    : 6 ký tự ngay trước span, để định vị

**Vì sao `before` chỉ 6 ký tự:** đo trên gold thật với locator harness —
15 ký tự → 99.93% khôi phục · **6 ký tự → 99.73%** · 0 ký tự → 97.37%.
Cắt từ 15 xuống 6 gần như không mất gì mà tiết kiệm 9 ký tự mỗi concept.

Dấu phân cách `|` an toàn: 0/2932 concept trong gold chứa nó.

## Vì sao KHÔNG train mã (candidates)

Mã gán bằng **bảng tra tĩnh** lúc inference (`code_map.json`) — không LLM, không API, nên
hợp lệ với hệ thống nộp bài ≤9B. Bắt model học thuộc mã ICD vừa tốn token vừa kém chính xác
hơn tra bảng, và verify cho thấy tra bảng đạt **100%** khớp mã.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import locate as loc      # noqa: E402
from src.harness import spec, validate     # noqa: E402
from src.harness.build import write_zip    # noqa: E402

OUT = ROOT / "dev/track2"
SEP = "|"
CTX = 6                                    # ký tự ngữ cảnh — xem chú thích đầu file

T2C = {"THUỐC": "M", "CHẨN_ĐOÁN": "D", "TRIỆU_CHỨNG": "T",
       "TÊN_XÉT_NGHIỆM": "X", "KẾT_QUẢ_XÉT_NGHIỆM": "K"}
C2T = {v: k for k, v in T2C.items()}
A2C = {"isNegated": "N", "isHistorical": "H", "isFamily": "F"}
C2A = {v: k for k, v in A2C.items()}

SYSTEM = (
    "Trích MỌI lần nhắc khái niệm y tế trong văn bản. Mỗi dòng một khái niệm:\n"
    "<LOAI><ASSERT>|<text nguyên văn>|<6 ký tự ngay trước text>\n"
    "LOAI: M=thuốc D=chẩn đoán T=triệu chứng X=tên xét nghiệm K=kết quả xét nghiệm\n"
    "ASSERT (bỏ trống nếu đang có/khẳng định): N=phủ định H=tiền sử F=của người nhà\n"
    "text phải NGUYÊN VĂN. Trích mỗi lần nhắc riêng. Theo thứ tự xuất hiện."
)


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip().lower()


def esc(s: str) -> str:
    """Định dạng theo DÒNG nên xuống dòng trong `text`/`before` phải escape.

    Bỏ qua bước này là lỗi ÂM THẦM: `before` như ' gì?\n\n' bị cắt mất phần sau xuống dòng,
    span không định vị được, và trần Track 2 rơi 99.7% -> 96.7% mà không có thông báo lỗi nào.
    """
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def unesc(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append({"n": "\n", "r": "\r", "\\": "\\"}.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def encode(raw: str, concepts: list) -> str:
    lines = []
    for e in sorted(concepts, key=lambda x: tuple(x["position"])):
        s = e["position"][0]
        a = "".join(A2C[x] for x in sorted(e.get("assertions") or []) if x in A2C)
        lines.append(f"{T2C[e['type']]}{a}{SEP}{esc(e['text'])}{SEP}{esc(raw[max(0, s-CTX):s])}")
    return "\n".join(lines)


def decode_lines(text: str) -> list[dict]:
    """Chuỗi model sinh -> list {text,type,assertions,before}. Bỏ qua dòng hỏng, không đoán."""
    out = []
    for line in text.splitlines():
        parts = line.split(SEP)
        if len(parts) < 2 or not parts[0]:
            continue
        tag, txt = parts[0].strip(), parts[1]
        before = parts[2] if len(parts) > 2 else ""
        ty = C2T.get(tag[:1])
        if not ty or not txt:
            continue
        txt, before = unesc(txt), unesc(before)
        out.append({"text": txt, "type": ty, "before": before,
                    "assertions": sorted({C2A[c] for c in tag[1:] if c in C2A})})
    return out


def to_records(raw: str, items: list[dict], cmap: dict) -> list[dict]:
    """Định vị + gán mã. Dùng locator harness (đã chứng minh 99.96% trên vòng khứ hồi)."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in items:
        groups[(e["text"], e["type"], e["before"])].append(e)
    cand = []
    for (txt, ty, before), reqs in groups.items():
        spans, _ = loc.locate_group(raw, txt, before, "", len(reqs))
        for e, (s, t, _m) in zip(reqs, spans):
            cand.append((s, t, ty, txt, tuple(e["assertions"])))

    # Gold thật có **0 cặp span chồng lấn** (đã đếm) ⇒ mọi chồng lấn trong output model
    # đều là lỗi. Lọc theo thứ tự tài liệu, tất định. Không lọc thì cổng cứng TỪ CHỐI ghi zip
    # khi model hơi lộn xộn — tức ngày chấm không có bài nộp nào.
    rows, taken = [], []
    for s, t, ty, txt, asserts in sorted(set(cand)):
        if any(s < b and t > a for a, b in taken):
            continue
        taken.append((s, t))
        rows.append({"text": raw[s:t], "type": ty,
                     "candidates": list(cmap.get(f"{norm(txt)}\t{ty}", []))
                                   if ty in spec.CODED_TYPES else [],
                     "assertions": list(asserts), "position": [s, t]})
    return rows


# ------------------------------------------------------------------ lệnh con

def cmd_prep(args) -> None:
    gold = validate.load_zip(ROOT / args.gold)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, nc, nch = [], 0, 0
    for i in range(1, 101):
        raw = validate.read_raw(i)
        tgt = encode(raw, gold.get(str(i), []))
        nc += len(gold.get(str(i), []))
        nch += len(tgt)
        rows.append({"file": i, "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": raw},
            {"role": "assistant", "content": tgt}]})
    dev_ids = set(range(1, 101, 7))
    for name, sel in (("train", lambda r: r["file"] not in dev_ids),
                      ("dev", lambda r: r["file"] in dev_ids)):
        sub = [r for r in rows if sel(r)]
        (OUT / f"{name}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in sub), encoding="utf-8")
        print(f"-> dev/track2/{name}.jsonl  ({len(sub)} mẫu)")

    cmap: dict[str, Counter] = defaultdict(Counter)
    for v in gold.values():
        for e in v:
            if e["type"] in spec.CODED_TYPES and e.get("candidates"):
                cmap[f"{norm(e['text'])}\t{e['type']}"][tuple(e["candidates"])] += 1
    codes = {k: list(c.most_common(1)[0][0]) for k, c in cmap.items()}
    (OUT / "code_map.json").write_text(json.dumps(codes, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(f"-> dev/track2/code_map.json ({len(codes)} cụm)")

    old = 99.4 * nc
    print(f"\n{nc} concept | output {nch} ký tự = {nch/100:.0f}/file  "
          f"({nch/nc:.1f} ký tự/concept)")
    print(f"   định dạng JSON cũ: {old/100:.0f}/file → giảm {old/nch:.1f}×")
    tok = nch / 100 / 2.75
    print(f"   ước ~{tok:.0f} token/file ⇒ cần {tok/6:.0f} token/giây để kịp 600s/100 file")


def cmd_verify(args) -> None:
    """Giả lập model sinh ĐÚNG nhãn gold, chạy qua đúng đường ống inference thật.

    Nếu tỉ lệ thấp thì lỗi ở PIPELINE — phải sửa TRƯỚC khi tốn GPU. Cao thì pipeline đúng,
    điểm Track 2 chỉ còn phụ thuộc model học lại nhãn tốt đến đâu.
    """
    gold = validate.load_zip(ROOT / args.gold)
    cmap = json.loads((OUT / "code_map.json").read_text(encoding="utf-8"))
    rows = [json.loads(l) for s in ("train", "dev")
            for l in (OUT / f"{s}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    ng = ns = ncg = nco = 0
    miss = []
    recon = {}
    for r in rows:
        fid = str(r["file"])
        raw = validate.read_raw(r["file"])
        ans = next(m["content"] for m in reversed(r["messages"]) if m["role"] == "assistant")
        got = to_records(raw, decode_lines(ans), cmap)
        recon[fid] = got
        by = {(tuple(c["position"]), c["type"]): c for c in got}
        for c in gold.get(fid, []):
            ng += 1
            k = (tuple(c["position"]), c["type"])
            if k in by:
                ns += 1
                if c["type"] in spec.CODED_TYPES and c["candidates"]:
                    ncg += 1
                    nco += by[k]["candidates"] == c["candidates"]
            else:
                miss.append((fid, c["text"], c["type"]))

    print(f"gold           : {ng} concept / {len(rows)} file")
    print(f"khớp span+type : {ns}  ({ns/ng:.2%})   <- TRẦN TRÊN của Track 2")
    print(f"khớp mã        : {nco}/{ncg}  ({nco/max(ncg,1):.1%})")
    errs = validate.validate(recon)
    print(f"cổng cứng      : {'✅ SẠCH' if not errs else f'❌ {len(errs)} lỗi'}")
    for e in errs[:5]:
        print("   -", e)
    if miss:
        print(f"\n{len(miss)} concept pipeline làm mất:")
        for fid, t, ty in miss[:10]:
            print(f"   file {fid:>3s} {ty:20s} {t[:44]!r}")


def cmd_decode(args) -> None:
    """Output thô của model -> zip nộp bài, qua cổng cứng."""
    cmap = json.loads((OUT / "code_map.json").read_text(encoding="utf-8"))
    preds = {}
    for line in Path(args.pred).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        preds[str(r["file"])] = r.get("output", r.get("text", ""))
    out, stats = {}, Counter()
    for i in range(1, 101):
        fid = str(i)
        raw = validate.read_raw(i)
        items = decode_lines(preds.get(fid, ""))
        stats["dòng model sinh"] += len(items)
        rec = to_records(raw, items, cmap)
        stats["định vị được"] += len(rec)
        out[fid] = rec
    print(f"{stats['dòng model sinh']} dòng -> {stats['định vị được']} concept định vị được "
          f"({stats['định vị được']/max(stats['dòng model sinh'],1):.1%})")
    errs = validate.validate(out)
    if errs:
        print(f"❌ {len(errs)} lỗi — KHÔNG ghi zip")
        for e in errs[:15]:
            print("  -", e)
        raise SystemExit(1)
    write_zip(out, Path(args.out))
    print(f"✅ ghi {args.out}  ({sum(len(v) for v in out.values())} concept)")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep");   p.add_argument("--gold", default="out/candidates/82x_cleanroom4_k2.zip")
    v = sub.add_parser("verify"); v.add_argument("--gold", default="out/candidates/82x_cleanroom4_k2.zip")
    d = sub.add_parser("decode"); d.add_argument("--pred", required=True); d.add_argument("--out", required=True)
    args = ap.parse_args()
    {"prep": cmd_prep, "verify": cmd_verify, "decode": cmd_decode}[args.cmd](args)


if __name__ == "__main__":
    main()
