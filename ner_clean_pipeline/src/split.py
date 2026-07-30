"""Chia train/val CHỐNG RÒ RỈ cho corpus 100 file.

Vì sao không chia theo file: corpus này dịch máy và trùng lặp nặng. Cùng một đoạn
nguồn xuất hiện ở nhiều file, ở nhiều chất lượng dịch và nhiều độ rộng mask. Nếu
chia theo file thì một đoạn có thể vừa nằm train vừa nằm val -> val đo được điểm cao
giả, model chỉ cần nhớ chứ không cần học.

Nên chia theo GROUP. Group = thành phần liên thông của đồ thị, nối bằng 3 loại cạnh:

  1. file - block  : file chứa block (data/blocks/file_to_blocks.json)
  2. block - block : SHARE[bid] = (src, n) - block bid dùng chung n ký tự đầu với src
  3. block - block : near-duplicate, jaccard 8-gram >= NEAR_TH trên chuỗi đã bỏ dấu
                     cách/hoa/ký tự lạ. Bắt trường hợp "cùng nguồn, hai bản dịch".

Kết quả đo được: 39 group. Group lớn nhất chứa 42 file / 117 block — nó lớn vì có
block xuất hiện ở tới 23 file, không phải vì ngưỡng near-dup lỏng (thử NEAR_TH từ 0.5
tới 0.9 group này vẫn 42 file). Đây là ràng buộc cứng: group đó phải nằm nguyên một
bên. Nên nó vào TRAIN, và val chọn từ 58 file còn lại.
"""

from __future__ import annotations

import collections
import json
import re
import sys
import unicodedata as ud
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gt_blocks as G  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NEAR_TH = 0.5  # jaccard 8-gram; đủ lỏng để bắt hai bản dịch cùng nguồn
NGRAM = 8
MIN_SIG = 20  # block quá ngắn thì bỏ qua so near-dup (nhiễu)
VAL_TARGET = 20  # số file muốn có trong val
SEED = 20260728


def _sig(text: str) -> set[str]:
    t = ud.normalize("NFC", text).lower()
    t = re.sub(r"[^a-zà-ỹ0-9]+", "", t)
    return {t[i : i + NGRAM] for i in range(max(1, len(t) - NGRAM + 1))}


class _DSU:
    def __init__(self) -> None:
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def build_groups() -> list[dict]:
    f2b = json.loads((ROOT / "data/blocks/file_to_blocks.json").read_text("utf-8"))
    blocks = {
        b["block_id"]: b
        for b in json.loads((ROOT / "data/blocks/blocks.json").read_text("utf-8"))
    }

    d = _DSU()
    for fname, spans in f2b.items():
        for s in spans:
            d.union("F" + fname, "B%d" % s["block_id"])
    for bid, (src, _n) in G.SHARE.items():
        d.union("B%d" % bid, "B%d" % src)

    sig = {b: _sig(blocks[b]["text"]) for b in blocks}
    ids = sorted(blocks)
    for i, a in enumerate(ids):
        sa = sig[a]
        if len(sa) < MIN_SIG:
            continue
        for b in ids[i + 1 :]:
            sb = sig[b]
            if len(sb) < MIN_SIG:
                continue
            if len(sa & sb) / len(sa | sb) >= NEAR_TH:
                d.union("B%d" % a, "B%d" % b)

    comp: dict[str, dict] = collections.defaultdict(lambda: {"files": [], "blocks": []})
    for node in list(d.p):
        c = comp[d.find(node)]
        if node[0] == "F":
            c["files"].append(node[1:])
        else:
            c["blocks"].append(int(node[1:]))

    out = []
    for c in comp.values():
        c["files"].sort()
        c["blocks"].sort()
        c["n_chars"] = sum(blocks[b]["n_chars"] for b in c["blocks"])
        c["n_ent"] = sum(len(G.GT.get(b, ())) for b in c["blocks"])
        out.append(c)
    out.sort(key=lambda c: (-len(c["files"]), -c["n_chars"]))
    return out


LABELS = (G.SYM, G.DX, G.LAB, G.DRUG, G.VAL)


def _dist(groups) -> list[float]:
    c = collections.Counter(
        a[2] for g in groups for b in g["blocks"] for a in G.GT.get(b, ())
    )
    tot = sum(c.values()) or 1
    return [c[x] / tot for x in LABELS]


def make_split() -> dict:
    """Chọn val bằng greedy CÂN BẰNG PHÂN BỐ, không phải "val càng dày entity càng tốt".

    Bản đầu tôi xếp theo entity/file giảm dần -> val hút hết group dày, kết quả
    TÊN_XÉT_NGHIỆM ở val (210) còn nhiều hơn train (195). Val như thế không đại diện
    cho tập test, đo xong không suy ra được gì.

    Nên mỗi bước thử thêm 1 group vào val và chọn group nào làm khoảng cách L1 giữa
    phân bố nhãn của val và của TOÀN corpus nhỏ nhất. Dừng khi đủ VAL_TARGET file.
    """
    groups = build_groups()
    ref = _dist(groups)
    chosen: set[int] = set()
    val_g: list[dict] = []
    nval = 0
    while nval < VAL_TARGET:
        best, best_cost = None, None
        for i, g in enumerate(groups):
            if i in chosen or nval + len(g["files"]) > VAL_TARGET:
                continue
            d = _dist(val_g + [g])
            cost = sum(abs(a - b) for a, b in zip(d, ref))
            # ưu tiên nhẹ group nhiều file để về đích, tránh nhặt toàn group 1 file
            cost -= 0.001 * len(g["files"])
            if best_cost is None or cost < best_cost:
                best, best_cost = i, cost
        if best is None:
            break
        chosen.add(best)
        val_g.append(groups[best])
        nval += len(groups[best]["files"])
    train_g = [g for i, g in enumerate(groups) if i not in chosen]

    def flat(gs, key):
        return sorted({x for g in gs for x in g[key]}, key=lambda v: str(v))

    return {
        "seed": SEED,
        "near_th": NEAR_TH,
        "n_group": len(groups),
        "train": {
            "files": flat(train_g, "files"),
            "blocks": sorted(int(b) for b in flat(train_g, "blocks")),
            "n_chars": sum(g["n_chars"] for g in train_g),
            "n_ent": sum(g["n_ent"] for g in train_g),
        },
        "val": {
            "files": flat(val_g, "files"),
            "blocks": sorted(int(b) for b in flat(val_g, "blocks")),
            "n_chars": sum(g["n_chars"] for g in val_g),
            "n_ent": sum(g["n_ent"] for g in val_g),
        },
    }


def main() -> None:
    out = ROOT / "data/blocks/split.json"
    # ĐÓNG BĂNG. Tiêu chí chọn val cân bằng theo phân bố nhãn, tức nó phụ thuộc G.GT — mà
    # GT tôi còn sửa (dọn span lồng nhau đã làm split trôi 262/70 -> 256/76 block). Split
    # trôi thì mọi số đo val trước và sau không so được với nhau nữa, mất luôn mục đích
    # của việc có tập val. Nên: đã có file thì giữ nguyên, muốn tính lại phải --rebuild và
    # tự biết là các số đo cũ thành vô hiệu.
    if out.exists() and "--rebuild" not in sys.argv:
        sp = json.loads(out.read_text("utf-8"))
        print("giữ split đã đóng băng ở", out.relative_to(ROOT), "(--rebuild để tính lại)")
    else:
        sp = make_split()
        out.write_text(json.dumps(sp, ensure_ascii=False, indent=1), "utf-8")

    tr, va = sp["train"], sp["val"]
    print("group          ", sp["n_group"])
    print("train  file %3d  block %3d  chars %6d  ent %4d"
          % (len(tr["files"]), len(tr["blocks"]), tr["n_chars"], tr["n_ent"]))
    print("val    file %3d  block %3d  chars %6d  ent %4d"
          % (len(va["files"]), len(va["blocks"]), va["n_chars"], va["n_ent"]))

    # kiểm rò rỉ: không block nào ở cả hai bên
    both = set(tr["blocks"]) & set(va["blocks"])
    print("block ở cả 2 bên:", len(both))

    # kiểm phân bố nhãn hai bên
    for name, part in (("train", tr), ("val", va)):
        c = collections.Counter(
            a[2] for b in part["blocks"] for a in G.GT.get(b, ())
        )
        print(name, dict(c.most_common()))
    print("->", out)


if __name__ == "__main__":
    main()
