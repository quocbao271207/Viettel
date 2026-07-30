#!/usr/bin/env bash
# Tải wheel PyPI (và file HuggingFace) về ./.wheels bằng curl chạy trong shell, để cài offline.
#
# VÌ SAO CẦN. `pip install` ở máy này chết ngay:
#     ProxyError('Cannot connect to proxy.', OSError('Tunnel connection failed: 403 Forbidden'))
# Tiến trình bị tiêm 20 biến proxy trỏ `localhost:59763`; pip và urllib đọc chúng rồi bị proxy
# chặn pypi.org. Gỡ biến proxy ra thì `curl: (6) Could not resolve host` — DNS cũng chỉ đi qua
# proxy đó. Nhưng `curl` gọi từ shell thì HTTP 200 và tải được file thật (kiểm: wheel numpy
# 16.8MB mở được bằng zip, JSON 3.5MB parse được). Nên đường duy nhất là:
#     shell curl -> file trên đĩa -> pip install --no-index --find-links .wheels
#
# 403 KHÔNG phải chặn cứng, mà là QUOTA NHỊP. Số đo: `for i in 1 2 3` (3 curl liền) -> cả 3
# đều 200; làm dày thêm thì cả 4 đều 000; nghỉ ~6s rồi gọi lại -> 200. Nên script này (a) nghỉ
# GAP giây trước mỗi request, (b) thử lại TRIES lần, (c) GHI NHỚ file đã tải xong nên chạy lại
# nhiều lần là tiếp tục chỗ dở, không tải lại từ đầu. Cứ chạy lại đến khi in "DU HET".
#
# Dùng: bash tools/fetch_wheels.sh cp311 numpy==1.26.4 torch==2.2.2 ...
set -u
DEST=".wheels"; TRIES=3; GAP=7
PYTAG="$1"; shift
mkdir -p "$DEST"

get() {  # get <url> <outfile>  -- 0 nếu tải xong
  local i=1
  while [ "$i" -le "$TRIES" ]; do
    sleep "$GAP"
    if curl -sS -L --max-time 900 -o "$2.part" "$1" 2>/dev/null; then
      mv -f "$2.part" "$2"; return 0
    fi
    rm -f "$2.part"; i=$((i+1))
  done
  return 1
}

miss=0; done_=0
for spec in "$@"; do
  name="${spec%%==*}"; ver="${spec#*==}"
  # đã có wheel của gói này chưa? (khớp tiền tố tên, không cần biết tên file đầy đủ)
  pre=$(printf '%s' "$name" | tr '[:upper:]-' '[:lower:]_')
  if ls "$DEST" 2>/dev/null | tr '[:upper:]-' '[:lower:]_' | grep -q "^${pre}-"; then
    done_=$((done_+1)); continue
  fi
  if [ "$ver" = "$spec" ]; then url="https://pypi.org/pypi/$name/json"
  else url="https://pypi.org/pypi/$name/$ver/json"; fi
  if ! get "$url" "$DEST/.meta.json"; then echo "  hoan  $spec (quota)"; miss=$((miss+1)); continue; fi
  python3 - "$DEST" "$PYTAG" <<'PY' > "$DEST/.pick"
import json, sys
dest, pytag = sys.argv[1], sys.argv[2]
d = json.load(open(f"{dest}/.meta.json"))
whl = [f for f in d["urls"] if f["filename"].endswith(".whl") and not f.get("yanked")]
def mac(n):
    return "macosx" in n and ("x86_64" in n or "universal2" in n)
bins = [f for f in whl if mac(f["filename"]) and (pytag in f["filename"] or "abi3" in f["filename"])]
pure = [f for f in whl if "py3-none-any" in f["filename"] or "py2.py3-none-any" in f["filename"]]
p = (sorted(bins, key=lambda f: f["filename"])[-1] if bins
     else sorted(pure, key=lambda f: f["filename"])[-1] if pure else None)
print("" if p is None else f"{p['url']}\t{p['filename']}\t{p['size']}")
PY
  line=$(cat "$DEST/.pick"); rm -f "$DEST/.meta.json" "$DEST/.pick"
  [ -z "$line" ] && { echo "  BO QUA $spec: khong co wheel $PYTAG/x86_64"; continue; }
  u=$(printf '%s' "$line" | cut -f1); fn=$(printf '%s' "$line" | cut -f2); sz=$(printf '%s' "$line" | cut -f3)
  if get "$u" "$DEST/$fn"; then
    got=$(wc -c < "$DEST/$fn" | tr -d ' ')
    if [ "$got" = "$sz" ]; then echo "  ok    $fn ($((sz/1000000))MB)"; done_=$((done_+1))
    else rm -f "$DEST/$fn"; echo "  thieu $fn $got/$sz"; miss=$((miss+1)); fi
  else
    echo "  hoan  $fn (quota)"; miss=$((miss+1))
  fi
done
echo "co $done_ goi / thieu $miss"
[ "$miss" = 0 ] && echo "DU HET"
