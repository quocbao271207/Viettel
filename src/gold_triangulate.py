#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gộp phiếu các LLM -> dev/gold_resolved.json (đồng thuận + map mã tự động).

    python3 src/gold_triangulate.py --k 2                 # giữ concept ≥2 voter đồng thuận
    python3 src/gold_triangulate.py --k 2 --sapbert       # + gán ICD cho bệnh/tc ngoài từ điển

Đọc mọi dev/votes/*.json. Với mỗi file:
  1. Định vị span mỗi phiếu bằng "before"+text (xử lý được lần nhắc lặp).
  2. Gom cụm: cùng type + span chồng lấn -> 1 cụm; support = số VOTER khác nhau.
  3. Giữ cụm có support ≥ k. Span đại diện = span nhiều voter chọn nhất; assertion = đa số.
  4. Map mã: THUỐC->RxNorm(gazetteer) | CHẨN_ĐOÁN->curated/SapBERT | TRIỆU_CHỨNG->chương R.
"""
from __future__ import annotations
import argparse, glob, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import gazetteer, sections, extract, autolabel  # noqa: E402

# Triệu chứng phổ biến -> mã chương R (verify tồn tại trong gazetteer lúc chạy)
SYMPTOM_ICD = {
    "sốt": "R509", "sốt cao": "R509", "ho": "R059", "khó thở": "R0600", "đau đầu": "R519",
    "đau bụng": "R109", "đau ngực": "R079", "buồn nôn": "R110", "nôn": "R1110", "ói": "R1110",
    "chóng mặt": "R42", "mệt mỏi": "R5383", "phù": "R609", "vàng da": "R17", "tiêu chảy": "R197",
    "táo bón": "K5900", "chảy máu": "R58", "co giật": "R569", "sụt cân": "R634", "chán ăn": "R630",
    "khó nuốt": "R1310", "mất ngủ": "G4700", "đánh trống ngực": "R002", "hồi hộp": "R002",
}


def resolve_positions(raw: str, concepts: list) -> list:
    """[(start,end,type,assertion,text)] — định vị bằng before+text; bỏ mục không tìm thấy."""
    out, cursor = [], {}
    for c in concepts:
        text = (c.get("text") or "").strip()
        typ = (c.get("type") or "").strip()
        if not text or typ not in {"THUỐC", "CHẨN_ĐOÁN", "TRIỆU_CHỨNG"}:
            continue
        before = (c.get("before") or "")[-15:]
        pos = raw.find(before + text)
        pos = pos + len(before) if pos >= 0 else raw.find(text, cursor.get(text, 0))
        if pos < 0:
            pos = raw.find(text)          # thử lại từ đầu
        if pos < 0 or raw[pos:pos + len(text)] != text:
            continue
        cursor[text] = pos + len(text)
        out.append((pos, pos + len(text), typ, c.get("assertion") or "", text))
    return out


def cluster(spans: list) -> list:
    """Union-find: cùng type + chồng lấn -> 1 cụm. spans: [(voter, s,e,type,assert,text)]."""
    n = len(spans)
    par = list(range(n))
    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for i in range(n):
        for j in range(i + 1, n):
            _, s1, e1, t1, _, _ = spans[i]
            _, s2, e2, t2, _, _ = spans[j]
            if t1 == t2 and min(e1, e2) > max(s1, s2):     # chồng lấn
                par[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(spans[i])
    return list(groups.values())


class Coder:
    def __init__(self, use_sapbert: bool):
        self.gaz = gazetteer.load()
        self.drug_idx = extract.build_drug_index(self.gaz)
        self.valid = set(self.gaz.get("icd_code2en", {}))
        self.sap = None
        if use_sapbert:
            import torch
            from transformers import AutoModel, AutoTokenizer
            idx = torch.load(ROOT / "data/icd10_sapbert.pt", weights_only=False)
            self.torch = torch
            self.E, self.codes = idx["E"], idx["codes"]
            self.r_mask = torch.tensor([c.startswith("R") for c in self.codes])
            self.tok = AutoTokenizer.from_pretrained("cambridgeltl/SapBERT-UMLS-2020AB-all-lang-from-XLMR")
            dev = "mps" if torch.backends.mps.is_available() else "cpu"
            self.mdl = AutoModel.from_pretrained("cambridgeltl/SapBERT-UMLS-2020AB-all-lang-from-XLMR").eval().to(dev)
            self.dev = dev
            self.sap = True

    def _sapbert(self, text: str, r_only: bool):
        enc = self.tok([text], return_tensors="pt", truncation=True, max_length=32).to(self.dev)
        with self.torch.inference_mode():
            q = self.torch.nn.functional.normalize(self.mdl(**enc).last_hidden_state[:, 0, :], dim=-1).float().cpu()[0]
        E = self.E[self.r_mask] if r_only else self.E
        sims = q @ E.T
        i = int(sims.argmax())
        code = (self.codes[j] for j, m in enumerate(self.r_mask) if m) if r_only else self.codes
        idx_map = [j for j, m in enumerate(self.r_mask.tolist()) if m] if r_only else None
        return self.codes[idx_map[i]] if r_only else self.codes[i]

    def code(self, typ: str, text: str) -> list:
        if typ == "THUỐC":
            hits = extract.find_drugs(text, self.drug_idx)
            if hits:
                return extract.resolve_rxnorm(self.gaz, text, hits[0][2])
            return []
        low = text.lower()
        if typ == "CHẨN_ĐOÁN":
            for term, cd in autolabel.DISEASES.items():         # curated trước
                if term in low and cd in self.valid:
                    return [cd]
            return [self._sapbert(text, r_only=False)] if self.sap else []
        # TRIỆU_CHỨNG
        for term, cd in SYMPTOM_ICD.items():
            if low == term or term in low.split():
                if cd in self.valid:
                    return [cd]
        return [self._sapbert(text, r_only=True)] if self.sap else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=2, help="số voter tối thiểu đồng thuận")
    ap.add_argument("--sapbert", action="store_true", help="gán ICD cho bệnh/tc ngoài từ điển")
    ap.add_argument("--voters", help="chỉ dùng các voter này (phân cách dấu phẩy), VD: claude,gpt")
    ap.add_argument("--trust", help="voter tin cậy: cụm có voter này LUÔN giữ (bỏ qua k), "
                                    "và span/assertion ưu tiên theo voter này")
    ap.add_argument("--out", default="dev/gold_resolved.json")
    args = ap.parse_args()

    vote_files = sorted(glob.glob(str(ROOT / "dev/votes/*.json")))
    if not vote_files:
        raise SystemExit("Chưa có phiếu nào ở dev/votes/. Chạy: python3 src/build_gold.py")
    voters = {Path(f).stem: json.loads(Path(f).read_text(encoding="utf-8")) for f in vote_files}
    if args.voters:
        keep_names = {v.strip() for v in args.voters.split(",")}
        missing = keep_names - set(voters)
        if missing:
            raise SystemExit(f"Không thấy voter: {missing} (có: {list(voters)})")
        voters = {n: d for n, d in voters.items() if n in keep_names}
    if args.trust and args.trust not in voters:
        raise SystemExit(f"--trust {args.trust!r} không nằm trong voter đang dùng {list(voters)}")
    print(f"voter: {list(voters)}  | đồng thuận k={args.k}"
          + (f" | trust={args.trust}" if args.trust else ""))

    coder = Coder(args.sapbert)
    gold, kept, total = {}, 0, 0
    for fid in map(str, range(1, 101)):
        raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
        spans = []
        for vname, data in voters.items():
            for (s, e, t, a, txt) in resolve_positions(raw, data.get(fid, [])):
                spans.append((vname, s, e, t, a, txt))
        total += len(spans)
        ents = []
        for grp in cluster(spans):
            support = len({g[0] for g in grp})
            trusted = [g for g in grp if args.trust and g[0] == args.trust]
            if support < args.k and not trusted:
                continue
            if trusted:  # span + assertion theo voter tin cậy
                (s, e, typ) = Counter((g[1], g[2], g[3]) for g in trusted).most_common(1)[0][0]
                assertion = Counter(g[4] for g in trusted).most_common(1)[0][0]
            else:
                (s, e, typ) = Counter((g[1], g[2], g[3]) for g in grp).most_common(1)[0][0]
                assertion = Counter(g[4] for g in grp).most_common(1)[0][0]
            txt = raw[s:e]
            ents.append({"text": txt, "type": typ,
                         "candidates": coder.code(typ, txt),
                         "assertions": [assertion] if assertion else [],
                         "position": [s, e]})
        ents.sort(key=lambda x: x["position"][0])
        gold[fid] = ents
        kept += len(ents)

    out_path = ROOT / args.out
    out_path.write_text(json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out_path.relative_to(ROOT)}  | {kept} concept giữ / {total} phiếu thô")
    coded = sum(1 for v in gold.values() for e in v if e["candidates"])
    print(f"   có mã: {coded}  | Đo: python3 src/evaluate.py out/baseline_all.json dev/gold_resolved.json")


if __name__ == "__main__":
    main()
