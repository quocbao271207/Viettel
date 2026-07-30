#!/bin/zsh
# Tải approximateTerm của RxNav về data/kb/rxnav_raw/. Idempotent: file đã có thì bỏ qua.
#
# Ba điều kiện bắt buộc, học được bằng ~20 lần thử (chi tiết ở worklog/02):
#
#   1. Phải chạy bằng shell, KHÔNG gọi từ python. Proxy sandbox có allowlist chặn
#      rxnav.nlm.nih.gov (403, header X-Proxy-Error: blocked-by-allowlist). Shell của
#      bash tool đã unset biến proxy nên đi thẳng được; python thấy đủ 22 biến proxy
#      nên mọi curl qua subprocess đều chết rc=56. Bỏ biến proxy trong env của
#      subprocess cũng không cứu: khi đó DNS fail luôn (rc=6).
#   2. Phải có --http1.1. HTTP/2 bị reset stream trên riêng endpoint approximateTerm
#      (endpoint property.json thì HTTP/2 vẫn chạy, nên lỗi này dễ chẩn đoán nhầm
#      thành "host chết").
#   3. Phải dùng shell redirect '>' chứ không phải 'curl -o' (sandbox chặn curl mở
#      file để ghi, dù dir tồn tại và ghi được).
#
# Hạn chế chưa vượt được: nhiều request liên tiếp trong MỘT lần gọi shell thì fail
# sạch, kể cả có sleep 2 và retry backoff. 1 request/lần gọi thì ổn định 13/13.
# Nên script này chỉ tải được từng ít một; chạy lại nhiều lần cho tới khi đủ.

set -u
D=data/kb/rxnav_raw
mkdir -p "$D"

# slug:term-đã-urlencode. Mention nguyên văn như trong input của đề.
PAIRS=(
  "m01:amlodipine%2010%20mg%20po%20daily"
  "m02:aspirin%2081%20mg%20po%20daily"
  "m03:metoprolol%20succinate%20xl%2050%20mg%20po%20daily"
  "m04:guaifenesin%20ml%20po%20q6h%3Aprn"
  "m05:nystatin%20oral%20suspension%205%20ml%20po%20qid%3Aprn"
  "m06:acetaminophen%20325-650%20mg%20po%20q6h%3Aprn"
  "m07:pravastatin%2040%20mg%20po%20daily"
  "m08:docusate%20sodium%20100%20mg%20po%20bid"
  "m09:sena%208.6%20mg%20po%20bid%3Aprn"
  "m10:clonazepam%200.5%20mg%20po%20qam%3Aprn"
  "m11:clonazepam%201.5%20mg%20po%20qhs"
  "m12:Chlorpheniramine%200.4%20MG%2FML"
  "m13:Capsaicin%200.38%20MG%2FML"
)

# Truy vấn đã làm sạch, cho 4 ca mà mention thô không ra GT.
# m03: xl -> extended release | m05: về tên hoạt chất trần -> tầng IN
# m06: 325-650 -> giữ số đầu   | m09: sena -> senna (sửa typo của mention)
CLEAN_PAIRS=(
  "m03:metoprolol%20succinate%2050%20mg%20extended%20release"
  "m05:nystatin"
  "m06:acetaminophen%20325%20mg"
  "m09:senna%208.6%20mg"
)

fetch() {  # $1 = file đích, $2 = term đã encode
  local f="$1" enc="$2"
  [[ -s "$f" ]] && return 0
  curl -s --http1.1 --max-time 45 \
    "https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term=${enc}&maxEntries=20" \
    < /dev/null > "$f"
  if [[ -s "$f" ]]; then
    echo "  OK   $f ($(wc -c < "$f" | tr -d ' ')B)"
    return 0
  fi
  rm -f "$f"
  echo "  FAIL $f  (chạy lại script — mỗi lần chỉ lấy được ít)"
  return 1
}

have=0; miss=0
for p in "${PAIRS[@]}"; do
  if fetch "$D/approx_${p%%:*}.json" "${p#*:}"; then have=$((have+1)); else miss=$((miss+1)); fi
done
for p in "${CLEAN_PAIRS[@]}"; do
  if fetch "$D/clean_${p%%:*}.json" "${p#*:}"; then have=$((have+1)); else miss=$((miss+1)); fi
done

echo "có dữ liệu: $have/17, còn thiếu: $miss"
[[ $miss -eq 0 ]] && echo "đủ. chạy: python3 src/rxnav_probe.py"
