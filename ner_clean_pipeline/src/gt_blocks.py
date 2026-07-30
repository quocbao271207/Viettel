"""Gán nhãn tay ở cấp BLOCK, rồi chiếu ngược ra 100 file.

Vì sao không gán theo file: 100 file chỉ gồm 332 đoạn văn độc nhất, 24 đoạn
được dùng lại ở nhiều file (block #0 xuất hiện 23 lần). Gán theo file là gán
lại cùng một đoạn nhiều lần — vừa chậm vừa dễ lệch giữa các lần.

Cách viết nhãn giống `make_gt.py`: (needle, nth, type, assertions, candidates).
Toạ độ KHÔNG viết tay, để máy tự tìm — sai chính tả thì báo lỗi ngay chứ không
âm thầm trỏ sai chỗ.

Chiếu ngược (`project`): với mỗi lần block xuất hiện trong một file, tìm LẠI
needle trong chính đoạn văn của file đó, không cộng offset. Lý do: khoá so
trùng block (`blocks.norm_for_hash`) bỏ dấu câu và gộp khoảng trắng, nên hai
lần xuất hiện "cùng một block" có thể lệch nhau vài ký tự — `Câu hỏi từ người
dùng :` so với `Câu hỏi từ người dùng:` là ca thật, 13 file. Cộng offset sẽ
lệch dần từ chỗ đó về sau.

Chạy:  python3 src/gt_blocks.py          # ghi data/gt_block/*.json + báo cáo
       python3 src/gt_blocks.py --show 7 # in nguyên văn block để gán nhãn
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import normalize, to_raw_span  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
BLOCKS = ROOT / "data" / "blocks" / "blocks.json"
F2B = ROOT / "data" / "blocks" / "file_to_blocks.json"
OUT_DIR = ROOT / "data" / "gt_block"

DX, SYM, DRUG, LAB, VAL = (
    "CHẨN_ĐOÁN",
    "TRIỆU_CHỨNG",
    "THUỐC",
    "TÊN_XÉT_NGHIỆM",
    "KẾT_QUẢ_XÉT_NGHIỆM",
)
NEG, FAM, HIST = "isNegated", "isFamily", "isHistorical"

# `nth = ALL`: gán mọi lần xuất hiện của needle trong block, không phải chỉ một.
ALL = "ALL"

# (needle, nth occurrence starting at 0 hoặc ALL, type, assertions, candidates)
Ann = tuple[str, int | str, str, list[str], list[str]]

# block_id -> danh sách nhãn. Trống = chưa gán (khác với "gán rồi, không có
# khái niệm nào" — dùng [] tường minh cho ca đó, xem DONE_EMPTY).
GT: dict[int, list[Ann]] = {}

# Block đã đọc và xác nhận KHÔNG có khái niệm nào (header, câu dẫn...).
DONE_EMPTY: set[int] = set()

# Nhiều block chỉ khác nhau ở phần đuôi: block 25 trùng block 24 đúng 2677 ký
# tự đầu rồi ghép một mẩu EHR khác. Khai `SHARE[25] = (24, 2677)` để tái dùng
# nhãn của block 24 nằm trong 2677 ký tự đó, thay vì gán lại tay.
# Máy tự kiểm tiền tố có giống thật không, lệch là báo lỗi.
SHARE: dict[int, tuple[int, int]] = {}


# ===================== gán tay cấp block (worklog/07) =====================

# block 25 = block 24 (2677 ký tự đầu giống hệt) + mẩu EHR khác ở cuối.
SHARE[25] = (24, 2677)
# block 31 = 1843 ký tự đầu của block 26 + mục "Triệu chứng khi nhập viện" riêng.
SHARE[31] = (26, 1843)
# block 59 và 88 dùng chung phần đầu bài giảng amyloidosis của block 30.
# Lưu ý: nhãn `ALL` KHÔNG được thừa hưởng khi block chia sẻ có thêm lần xuất
# hiện ở đuôi (máy tự chặn) -> phải khai lại tay trong GT của block đó.
SHARE[59] = (30, 1048)
SHARE[88] = (30, 551)
# block 82 = 782 ký tự đầu của block 35 (EHR tổn thương âm hộ) + mục
# "Triệu chứng khi nhập viện" riêng. Block 35 chèn 2 mẩu tờ HDSD thuốc vào giữa.
SHARE[82] = (35, 782)
# block 90 = 911 ký tự đầu của block 41 (QA teo ống tai) và HẾT ở đó — nghĩa là
# block 90 thừa hưởng toàn bộ nhãn phần QA, không cần gán tay gì thêm.
SHARE[90] = (41, 911)

# ------------------------------------------------
# File 12.txt = MỘT bệnh án tổn thương âm hộ/mông phải (cùng nguồn với 15.txt),
# bị GHÉP 2 đoạn trả lời QA dị tật tai (cùng nguồn với 48.txt) vào giữa ở dòng
# 31-33. Đoạn dòng 31 đã gán ở GT[12]; đoạn dòng 33 là block 164 dưới đây.
# 3 block còn lại: block 22 (mục "3. Đánh giá tại bệnh viện", dùng chung với
# 15.txt), block 164 (đuôi QA tai), block 209 (đuôi EHR trước mục 3).
# Quy ước chốt cho cả file:
#  - Phần QA tai: bệnh nhân là CON của người hỏi -> isFamily (tiền lệ GT[12]
#    cùng nguồn, cùng đứa bé).
#  - Phần EHR: bệnh nhân tự là chủ thể, đang điều trị -> không assertion (tiền
#    lệ GT[35] là bản dịch dài hơn của CHÍNH bệnh án này).
#  - "Lo ngại về X" / "khả năng X" = chẩn đoán nghi ngờ. Đề chỉ có 3 assertion
#    (isNegated/isFamily/isHistorical), KHÔNG có "nghi ngờ" -> vẫn gán CHẨN_ĐOÁN,
#    assertions rỗng (tiền lệ GT[24] "khả năng em bị viêm bao tử", GT[26] "nghi
#    ngờ cơn co giật", GT[205] "kết quả nghi ngờ thiếu men G6PD").
# ------------------------------------------------

GT[22] = [  # 156c ×2  12.txt, 15.txt — mục "3. Đánh giá tại bệnh viện"
    # Tiêu đề "3. Đánh giá tại bệnh viện" và "Các phát hiện chẩn đoán khác":
    # tiêu đề mục -> không gán (tiền lệ GT[132]/GT[94] cùng tiêu đề này, chỉ gán
    # các chẩn đoán bên dưới, không gán chính tiêu đề, và không assertion).
    ("Nhiễm virus Herpes simplex (HSV)", 0, DX, [], ["B00.9"]),
    # B00.9 "Bệnh do nhiễm virus herpes [herpes simplex], không xác định". Bề mặt
    # KHÔNG nói vị trí nên dùng mã .9 của nhóm B00. Đã cân nhắc A60.0 (herpes
    # đường sinh dục) vì tổn thương ở âm hộ, nhưng loại: câu này chỉ là chẩn đoán
    # "lo ngại về" chưa quy vị trí cho HSV, mà bề mặt lại khớp tên nhóm B00.
    # Giữ TRỌN cả "(HSV)" theo quy ước mô tả trong ngoặc không tách nhãn lồng.
    ("Bệnh thủy đậu/Zona (do Varicella Zoster Virus)", 0, DX, [],
     ["B01.9", "B02.9"]),
    # MỘT bề mặt (tiền lệ gạch chéo: "tụ dịch/tụ máu dưới màng cứng mạn tính" ->
    # 1 nhãn) nhưng khác ở chỗ hai vế là HAI bệnh khác nhau: thủy đậu = B01,
    # zona = B02. Nên để 2 mã — tiền lệ nhiều mã cho 1 nhãn: GT[28] "Viêm quanh
    # răng" -> K05.2+K05.3, GT[24] "trào ngược dạ dày thực quản" -> K21.0+K21.9.
    # Cả hai dùng con ".9 không biến chứng" vì các mã con khác đều là biến chứng
    # cụ thể (viêm màng não/viêm não/viêm phổi/bệnh mắt), không có ở đây.
]

GT[164] = [  # 431c ×1  12.txt — đuôi câu trả lời QA dị tật tai (nối tiếp GT[12])
    # Cùng đứa bé với GT[12] -> isFamily. Nhưng nhãn duy nhất ở đây là XÉT NGHIỆM,
    # mà TÊN_XÉT_NGHIỆM không được mang assertion (check() chặn) -> rốt cuộc rỗng.
    ("chụp cắt lớp", 0, LAB, [], []),  # tiền lệ "chụp cắt lớp vi tính (ct)" ->
    # LAB ở GT[69]/GT[179]/GT[274]; ở đây bản dịch cắt ngắn còn "chụp cắt lớp".
    # KHÔNG gán:
    #  - "phẫu thuật tạo hình vành tai", "tạo hình ống tai ngoài": thủ thuật
    #    (tiền lệ "ghép gan", "Thở oxy tại nhà" không gán).
    #  - "thiết bị trợ thính đường xương", "sụn sườn tự thân", "sụn nhân tạo":
    #    thiết bị/vật liệu -> không gán.
    #  - "Về thính lực,", "Về thẩm mỹ,": từ dẫn chủ đề, không phải khái niệm.
    #    (Khác GT[19] cùng nguồn: ở đó bề mặt là "đo thính lực" = tên xét nghiệm.)
    #  - "đôi tai hoàn thiện", "cấu trúc tai giữa": mô tả giải phẫu/kết quả mong
    #    đợi bình thường -> không gán (tiền lệ GT[12] bỏ "cấu trúc tai trong ...
    #    phát triển tốt").
]

GT[209] = [  # 281c ×1  12.txt — đuôi EHR: bệnh nhân xin dùng tiếp kháng sinh
    # Đây là bản dịch NGẮN của đúng đoạn đã gán ở GT[35] (15.txt, cùng bệnh án),
    # nên tái dùng nguyên các quyết định của GT[35] cho 3 nhãn dưới đây.
    ("doxycycline", 0, DRUG, [], ["3640"]),  # nằm TRONG từ dính
    ("bactrim", 0, DRUG, [], ["151399"]),  # "doxycyclinebactrim" (lỗi dịch mất
    # dấu cách). Tách 2 thành phần thành 2 nhãn, KHÔNG gán cả từ dính — đúng như
    # GT[35] làm với cùng câu này (`doxycycline`[1] + `bactrim`[1]). Khác GT[109]
    # gán trọn "vancozosynbactrim" làm 1 THUỐC vì ở đó dính 3 thuốc và không có
    # bản dịch rời để đối chiếu.
    ("Viêm mô tế bào", 0, DX, [], ["L03.3"]),  # tiền lệ GT[35] cùng bệnh án
    # (L03.3 "Viêm mô bào ở thân"). "cho khả năng" = nghi ngờ -> không assertion.
    # KHÔNG gán:
    #  - "những loại thuốc này": nhắc lại thuốc không nêu tên -> không gán.
    #  - "không muốn ngừng chúng": ý muốn của bệnh nhân, thuốc vẫn ĐANG dùng ->
    #    KHÔNG isNegated (khác tiền lệ GT[16] "đã hết thuốc" = thực sự dừng).
    #  - "Khoa Cấp cứu", "bác sĩ Truyền nhiễm": cơ sở/chuyên khoa -> không gán.
]

GT[24] = [  # 3208c ×1  7.txt — QA thai 20 tuần + đau bao tử, ghép mẩu EHR ở cuối
    # Người bệnh tự kể tiền sử: "Từ năm 24-26 tuổi em có dấu hiệu đau bao tử".
    # Đây là triệu chứng đã qua -> isHistorical.
    ("đau bao tử", 0, SYM, [HIST], []),
    ("thỉnh thoảng đau", 0, SYM, [HIST], []),
    # "Năm 27 tuổi em đi nội soi" -> xét nghiệm đã thực hiện
    ("nội soi", 0, LAB, [], []),
    # "BS nói em có ổ loét trong bao tử" -> chẩn đoán của bác sĩ, đã qua
    ("ổ loét trong bao tử", 0, DX, [HIST], ["K25.0", "K25.1", "K25.2", "K25.3",
                                            "K25.4", "K25.5", "K25.6", "K25.7", "K25.9"]),
    # "hầu như em không bị đau lại nữa" -> phủ định
    ("không bị đau", 0, SYM, [NEG], []),
    ("không còn bị đau", 0, SYM, [NEG], []),
    # "em đã tăng 10kg" — cân nặng là chỉ số đo được; nhưng "tăng 10kg" là mức
    # thay đổi cân nặng người bệnh tự kể, không phải xét nghiệm bác sĩ chỉ định.
    # Theo tiền lệ GT cũ (chỉ gán KẾT_QUẢ khi có tên xét nghiệm đi kèm) -> bỏ.
    ("ói", 0, SYM, [], []),
    # đợt cấp đang diễn ra
    ("đau bụng râm ran", 0, SYM, [], []),
    ("cơn đau càng dồn đạp", 0, SYM, [], []),
    ("quá đau", 0, SYM, [], []),
    # "BS chích cho em liều giảm đau" -> thuốc, nhưng không có TÊN thuốc cụ thể.
    # Đề: "Tên thuốc mà bệnh nhân điều trị". "liều giảm đau" không phải tên -> bỏ.
    ("siêu âm", 0, LAB, [], []),
    # "kết quả không thấy gì cả" -> kết quả mô tả bằng chữ. Tiền lệ GT cũ chỉ gán
    # KẾT_QUẢ_XÉT_NGHIỆM cho giá trị số (97/99.json) -> bỏ để giữ nhất quán.
    # "chỉ thấy mỗi bên thận có 1 viên sỏi 4mm" -> sỏi thận, phát hiện qua siêu âm
    ("sỏi", 0, DX, [], ["N20.0"]),
    ("không ứ nước", 0, SYM, [NEG], []),
    ("sỏi thận", 0, DX, [], ["N20.0"]),
    # "nói khả năng em bị viêm bao tử" -> chẩn đoán (dù còn "khả năng"; đề không
    # có assertion cho mức độ chắc chắn, chỉ có 3 giá trị)
    ("viêm bao tử", 0, DX, [], ["K29.7"]),
    # Danh sách thuốc bị che tên. 3 run 6/7/14 ký tự là 3 thuốc riêng; hai run
    # 19 và 16 nằm trong ngoặc sau run 7 -> thành phần của thuốc đó, vẫn là THUỐC.
    ("******", 0, DRUG, [], []),
    ("******", 1, DRUG, [], []),
    ("*******", 0, DRUG, [], []),
    ("*******************", 0, DRUG, [], []),
    ("****************", 0, DRUG, [], []),
    ("**************", 0, DRUG, [], []),
    # phần trả lời: tên thuốc và hoạt chất
    ("Aquima", 0, DRUG, [], []),
    ("nhôm hydroxid", 0, DRUG, [], ["612"]),
    ("magie hydroxid", 0, DRUG, [], ["6581"]),
    ("**********", 0, DRUG, [], []),
    ("Simenic", 0, DRUG, [], []),
    ("Alverin citrate", 0, DRUG, [], []),
    ("Simethicon", 0, DRUG, [], ["9796"]),
    ("Pimperam", 0, DRUG, [], []),
    ("metoclopramide", 0, DRUG, [], ["6915"]),
    ("Nhôm hydroxid", 1, DRUG, [], ["612"]),
    ("magie hydroxid", 1, DRUG, [], ["6581"]),
    ("ợ nóng", 0, SYM, [], []),
    ("trào ngược dạ dày thực quản", 0, DX, [], ["K21.0", "K21.9"]),
    ("**********", 1, DRUG, [], []),
    ("**********", 2, DRUG, [], []),
    # mẩu EHR ghép vào giữa: mục "Triệu chứng khi nhập viện"
    ("tổn thương vùng âm hộ và mông bên phải", 0, SYM, [], []),
    ("Tổn thương cực kỳ đau đớn", 0, SYM, [], []),
    ("tổn thương dạng bóng nước ngày càng nặng", 0, SYM, [], []),
    ("Lan đến mông bên phải", 0, SYM, [], []),
    ("có dịch giống mủ có màu vàng", 0, SYM, [], []),
    # câu khuyên chung ở cuối ("tránh tình trạng ... dẫn đến viêm dạ dày") là
    # nguy cơ giả định, không phải bệnh bệnh nhân mắc -> vẫn gán vì đề chỉ hỏi
    # "tên chẩn đoán của bác sĩ về bệnh mà bệnh nhân mắc phải"; đây KHÔNG mắc.
    # -> bỏ. Ghi lại để lần sau không lật lại.
]

GT[26] = [  # 2839c ×1  11.txt — EHR thần kinh (ngã, xuất huyết dưới nhện) + mẩu QA bàn chân bẹt
    # 4 dòng đầu là mục bệnh mạn tính (không có header vì block bị cắt) -> isHistorical
    ("Bệnh tim mạch do xơ vữa động mạch", 0, DX, [HIST], ["I25.1"]),
    # lỗi template của corpus: "ăng huyết áp" mất chữ T đầu. Vẫn là tăng huyết áp.
    ("ăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("Rối loạn lipid máu", 0, DX, [HIST], ["E78.5"]),
    ("Đái tháo đường", 0, DX, [HIST], ["E14"]),
    # mục "Bệnh sử" / "Lý do vào viện"
    ("Cơn rối loạn ý thức thoáng qua", 0, SYM, [], []),
    # "nghi ngờ cơn co giật" -> chưa xác định, nhưng đề chỉ có 3 assertion, không
    # có "nghi ngờ". Là chẩn đoán bác sĩ đặt ra -> giữ, mã cơn co giật toàn thể.
    ("cơn co giật", 0, DX, [], ["G40.6"]),
    ("ngã", 0, SYM, [HIST], []),
    ("xuất huyết dưới nhện", 0, DX, [HIST], ["S06.6"]),
    ("Chụp cắt lớp vi tính sọ não", 0, LAB, [], []),
    ("xuất huyết dưới nhện vùng trán phải", 0, DX, [HIST], ["S06.6"]),
    ("bầm dập nhu mô vùng trán phải", 0, DX, [HIST], []),
    ("lớp dịch dưới màng cứng mỏng vùng thùy trán phải", 0, DX, [HIST], []),
    ("nang màng nhện", 0, DX, [HIST], ["G93.0"]),  # SỬA (rà mâu thuẫn): trước để rỗng.
    # G93.0 "Bệnh u nang não" là mã ICD của nang màng nhện (arachnoid cyst) -> y block
    # 132 cùng bệnh án. Đây là tổn thương BẨM SINH/không do chấn thương, khác các dòng
    # S06.x/I62.x quanh nó.
    ("tụ dịch/tụ máu dưới màng cứng mạn tính", 0, DX, [HIST], ["S06.5"]),  # SỬA (rà mâu
    # thuẫn): trước dùng I62.0 "Xuất huyết dưới màng cứng KHÔNG do chấn thương". Block 89
    # (6.txt) là BẢN DỊCH KHÁC của cùng câu CT này, ở đó đã dùng S06.5. Bệnh cảnh là
    # NGÃ -> chấn thương, và ngay trên đây "xuất huyết dưới nhện" đã gán S06.6 (nhóm
    # chấn thương). Chốt S06.x cho cả cụm để nội bộ block khỏi tự mâu thuẫn.
    ("chụp CT", 0, LAB, [], []),
    ("đau đầu kéo dài", 0, SYM, [HIST], []),
    ("Chụp kiểm tra", 0, LAB, [], []),
    ("tụ máu ngoài màng cứng phải cấp tính", 0, DX, [HIST], ["S06.4"]),  # SỬA: y trên,
    # I62.1 -> S06.4 "Xuất huyết ngoài màng cứng do chấn thương".
    ("chụp CT kiểm tra", 0, LAB, [], []),
    ("đau đầu vùng thái dương phải và đỉnh đầu", 0, SYM, [], []),
    ("tê bì nửa mặt phải", 0, SYM, [], []),
    # ngày vào viện: cơn hiện tại
    ("bất thường", 0, SYM, [], []),
    ("mất định hướng", 0, SYM, [], []),
    ("đi lại không vững", 0, SYM, [], []),
    ("gần như ngất", 0, SYM, [], []),
    ("lúc mở mắt, lúc nhắm mắt", 0, SYM, [], []),
    ("ngửa đầu ra sau", 0, SYM, [], []),
    ("không đáp ứng được các câu hỏi", 0, SYM, [], []),
    ("kích thích nhẹ", 0, SYM, [], []),
    ("Tình trạng ý thức dao động", 0, SYM, [], []),
    # mẩu QA ghép vào: bàn chân bẹt (cháu bé — người khác, nhưng đề không có
    # assertion cho "người khác" ngoài isFamily; đây là con của người hỏi -> FAM)
    ("bệnh bàn chân bẹt", 0, DX, [FAM], ["Q66.5"]),
    ("không đau", 0, SYM, [FAM, NEG], []),
    # "Khám lâm sàng" nhắc lại
    ("mất định hướng", 1, SYM, [], []),
    ("đi lại không vững", 1, SYM, [], []),
    ("kích thích nhẹ", 1, SYM, [], []),
    ("ngửa đầu ra sau", 1, SYM, [], []),
    ("nhắm mắt từng lúc", 0, SYM, [], []),
    # "Không ghi nhận co giật, cứng đờ, cắn lưỡi hoặc tiểu tiện không tự chủ"
    # -> một phủ định phủ lên cả 4 triệu chứng
    ("co giật", 1, SYM, [NEG], []),
    ("cứng đờ", 0, SYM, [NEG], []),
    ("cắn lưỡi", 0, SYM, [NEG], []),
    ("tiểu tiện không tự chủ", 0, SYM, [NEG], []),
    # "Cận lâm sàng: CT sọ não trước đó ghi nhận..."
    ("CT sọ não", 0, LAB, [], []),
    ("xuất huyết dưới nhện vùng trán phải", 1, DX, [HIST], ["S06.6"]),
    ("Bầm dập nhu mô vùng trán phải", 1, DX, [HIST], []),
    ("Lớp dịch dưới màng cứng mỏng vùng thùy trán phải", 1, DX, [HIST], []),
    ("nang màng nhện", 1, DX, [HIST], ["G93.0"]),  # SỬA: y trên, chuẩn hoá G93.0
    ("tụ máu dưới màng cứng mạn tính", 1, DX, [HIST], ["S06.5"]),  # SỬA: y trên
    ("Tụ máu ngoài màng cứng phải cấp tính", 1, DX, [HIST], ["S06.4"]),  # SỬA: y trên
]

GT[67] = [  # 1188c — đuôi riêng (659c đầu thừa hưởng block 62 qua SHARE)
    ("CT ngực", ALL, LAB, [], []),  # đoạn giảng về viêm phổi hoại tử, không phải BN
    ("VPHT", ALL, DX, [], ["J85.0"]),  # viêm phổi hoại tử
    ("đông đặc phổi", 0, DX, [], []),
    ("Phù gai thị", 1, SYM, [], []),
]

GT[66] = [  # 1198c ×1  20.txt — QA phổ biến kiến thức bệnh dại (không có BN cụ thể)
    ("Bệnh dại", 0, DX, [], ["A82.9"]),
    ("bệnh dại", 1, DX, [], ["A82.9"]),  # "gây bệnh dại ở người tại Đông Nam Á"
    ("bệnh dại", 2, DX, [], ["A82.9"]),  # "ca mắc bệnh dại ở người"
    ("bệnh dại", 3, DX, [], ["A82.9"]),  # "lây nhiễm bệnh dại bao gồm"
]

GT[8] = [  # 605c ×2  35/89.txt — EHR đau ngực do gắng sức (nghiệm pháp gắng sức bất thường)
    ("xét nghiệm gắng sức bất thường", ALL, LAB, [], []),
    ("khó chịu vùng ngực gián đoạn", 0, SYM, [], []),
    ("chóng mặt", ALL, SYM, [], []),
    ("khó thở", ALL, SYM, [], []),  # 3 lần, kể cả lần trong ngoặc
    ("đổ mồ hôi", ALL, SYM, [], []),
]

GT[7] = [  # 611c ×2  28/52.txt — câu hỏi mày đay: nói về BẠN của người hỏi -> isFamily
    ("mề đay", ALL, DX, [FAM], ["L50.9"]),
    ("ngứa", ALL, SYM, [FAM], []),
    # "dị ứng (do) thời tiết" gán CHẨN_ĐOÁN + T78.4 thống nhất ở cả 3 block cùng
    # nguồn (7, 47, 112) — trước đây block 7 gán TRIỆU_CHỨNG, đã sửa.
    ("dị ứng do thời tiết", 0, DX, [FAM, NEG], ["T78.4"]),
]

GT[64] = [  # 1235c ×1  34.txt — QA đau nửa đầu migraine (người hỏi) + 3 dòng thuốc EHR (= block 46)
    ("Bệnh lý đau nửa đầu", 0, DX, [], ["G43.9"]),
    ("bệnh đau nửa đầu Migraine", 0, DX, [], ["G43.9"]),
    ("đau nửa đầu", 2, SYM, [], []),
    ("mạch đập", 0, SYM, [], []),
    ("đau nửa đầu", 3, SYM, [], []),
    ("thị giác bị nhòe", 0, SYM, [], []),
    ("ruồi bay", 0, SYM, [], []),
    ("buồn nôn", 0, SYM, [], []),
    ("mạch đập ở vùng thái dương", 0, SYM, [], []),
    ("buồn nôn", 1, SYM, [], []),
    ("sợ ánh sáng", 0, SYM, [], []),
    ("sợ tiếng động", 0, SYM, [], []),
    ("căng thẳng", 0, SYM, [], []),
    ("đau nửa đầu", 4, SYM, [], []),
    ("đau nửa đầu bên trái", 0, SYM, [], []),
    ("viêm xoang", 0, DX, [], ["J32.9"]),
    ("đau nửa đầu", 6, SYM, [], []),  # "cơn đau nửa đầu trái hành hạ"
    ("suy giảm trí nhớ", 0, SYM, [], []),
    ("khó tập trung", 0, SYM, [], []),
    ("trầm cảm", 0, DX, [], ["F32.9"]),
    ("đột quỵ", 0, DX, [], ["I64"]),
    ("suy thoái võng mạc", 0, DX, [], ["H35.9"]),
    ("mất thị lực", 0, SYM, [], []),
    ("mù vĩnh viễn", 0, DX, [], ["H54.0"]),
    ("đau nửa đầu", 7, SYM, [], []),
    # --- 3 dòng thuốc từ EHR ảo giác (cùng nguồn block 46) ---
    ("gleevec", 0, DRUG, [NEG], ["282386"]),
    ("allopurinol", 0, DRUG, [NEG], ["519"]),
    ("Thuốc giảm đau", 0, DRUG, [NEG], []),
]

GT[63] = [  # 1245c ×1  90.txt — EHR nhịp thở nhanh/thiếu oxy, viêm phổi kẽ
    ("nhịp thở nhanh", ALL, SYM, [], []),  # 3 lần, đều của BN
    ("thiếu oxy", ALL, SYM, [], []),  # khớp cả "Thiếu oxy"
    ("mệt mỏi", ALL, SYM, [], []),
    ("ho", 1, SYM, [], []),  # [0] trong "khoảng", [3]/[4] trong "cho"/"hoặc"
    ("ho", 2, SYM, [], []),
    ("chảy nước mũi", ALL, SYM, [], []),
    ("nhiễm trùng đường hô hấp trên", 0, DX, [], ["J06.9"]),
    ("độ bão hòa oxy (SPO2)", 0, LAB, [], []),
    ("88-92 %", 0, VAL, [], []),
    ("đau", 0, SYM, [], []),
    ("bạch cầu", 0, LAB, [], []),
    ("26.7", 0, VAL, [], []),
    ("bnp", 0, LAB, [], []),
    ("4227", 0, VAL, [], []),
    ("kali", 0, LAB, [], []),
    ("3.2", 0, VAL, [], []),
    ("troponin", 0, LAB, [], []),
    ("0.01", 0, VAL, [], []),
    ("lactate", 0, LAB, [], []),
    ("1.8", 0, VAL, [], []),
    ("tổng phân tích nước tiểu", 0, LAB, [], []),
    ("dương tính  với 182bạch cầuvài vi khuẩn (vi khuẩn), nitrite", 0, VAL, [], []),
    ("chụp x-quang ngực", 0, LAB, [], []),
    ("viêm phổi kẽ", 0, DX, [], ["J84.9"]),
    ("Albuterol", 0, DRUG, [], ["435"]),
    ("Ipratropium", 0, DRUG, [], ["7213"]),
    ("Ceftriaxone", 0, DRUG, [], ["2193"]),
    ("Tylenol", 0, DRUG, [], ["202433"]),
    ("cấy máu", 0, LAB, [], []),
    ("cấy nước tiểu", 0, LAB, [], []),
]

GT[62] = [  # 1254c ×1  45.txt — EHR não úng thuỷ/phù gai thị + chèn phiếu XN & QA còn ống ĐM
    ("đau đầu kéo dài", 0, SYM, [], []),
    ("mờ mắt", 0, SYM, [], []),
    ("nhìn mờ tiến triển", 0, SYM, [], []),
    ("não úng tuỷ", 0, DX, [HIST], ["G91.8"]),
    ("não úng thủy", 0, DX, [HIST], ["G91.8"]),
    ("tăng đau đầu", 0, SYM, [HIST], []),
    ("đau đầu", 2, SYM, [HIST], []),  # "để điều trị chứng đau đầu" (lần nhập viện trước)
    ("phù gai thị", 0, SYM, [HIST, NEG], []),  # "không có phù gai thị"
    ("mờ mắt", 1, SYM, [], []),  # "hôm nay bệnh nhân bị mờ mắt ở cả hai mắt"
    # --- chèn phiếu chỉ định xét nghiệm (nguồn khác) ---
    ("Tổng phân tích tế bào máu ngoại vi", 0, LAB, [], []),
    ("Thời gian prothrombin", 0, LAB, [], []),
    ("Định lượng \nTroponin Ths", 0, LAB, [], []),
    ("Định lượng NT - proBNP ( ProBNP)", 0, LAB, [], []),
    ("Đo hoạt độ AST (GOT)", 0, LAB, [], []),
    ("Đo hoạt độ ALT (GPT)", 0, LAB, [], []),
    ("Định lượng Creatinin (máu)", 0, LAB, [], []),
    ("Điện giải đồ", 0, LAB, [], []),
    ("Dị tật còn ống động mạch", 0, DX, [], ["Q25.0"]),
    ("***********************", 0, DRUG, [], []),
    ("************************", 0, DRUG, [], []),
    ("*********", 0, DRUG, [], []),
    # --- trở lại EHR ---
    ("Tăng nhãn áp", 0, DX, [HIST], ["H40.9"]),
    ("chụp cắt lớp vi tính (ct) đầu", 0, LAB, [], []),
    ("Phù gai thị", 1, SYM, [], []),
]

GT[61] = [  # 1278c ×1  42.txt — câu hỏi viêm hang vị (người hỏi) + đuôi EHR ho/thiếu oxy (= block 53)
    ("đau bụng vùng thượng vị", 0, SYM, [], []),
    ("ợ hơi", 0, SYM, [], []),
    ("ợ chua", 0, SYM, [], []),
    ("nội soi dạ dày", 0, LAB, [], []),
    ("hang vị, tiền môn vị, niêm mạc phù nề, sung huyết đỏ", 0, DX, [], ["K29.6"]),
    ("nghệ", 0, DRUG, [], []),
    ("mật ong", 0, DRUG, [], []),
    # --- đuôi EHR ho/thiếu oxy, trùng block 53 ---
    ("mệt mỏi", 0, SYM, [], []),
    ("sốt", 0, SYM, [], []),
    ("101", 0, VAL, [], []),
    ("tiêu chảy", ALL, SYM, [], []),
    ("đi tiểu nhiều lần vào ban đêm", 0, SYM, [], []),
    ("đau buốt khi đi tiểu", 0, SYM, [NEG], []),
    ("khó thở khi gắng sức", 0, SYM, [], []),
    ("ho đặc như bã", 0, SYM, [], []),
    ("khạc nhổ", 0, SYM, [NEG], []),
    ("sốt", 1, SYM, [], []),
    ("sốt", 2, SYM, [], []),
    ("đau ngực", 0, SYM, [NEG], []),
    ("buồn nôn/nôn", 0, SYM, [NEG], []),
    ("đổ mồ hôi đêm", 0, SYM, [NEG], []),
    ("khó thở khi nằm", 0, SYM, [NEG], []),
    ("khó thở khi nằm đột ngột (paroxysmal nocturnal dyspnea)", 0, SYM, [NEG], []),
    ("giãn phế quản", 0, DX, [FAM], ["J47"]),
    ("azithromycin", 0, DRUG, [FAM], ["18631"]),
    ("tylenol", 0, DRUG, [], ["202433"]),
    ("mucinex d", 0, DRUG, [], ["352777"]),  # SỬA (rà mâu thuẫn): trước để rỗng.
    # RxNorm không có concept tên đúng "Mucinex D" nhưng CÓ BN 352777 "Mucinex" —
    # "Mucinex D" là biến thể cùng thương hiệu -> dùng mã brand đó, y GT[20].
    ("spo2", ALL, LAB, [], []),
    ("90-92%", 0, VAL, [], []),
    ("93%", 0, VAL, [], []),
]

GT[60] = [  # 1306c ×1  73.txt — EHR buồn nôn/thiểu niệu (ống thông hồi tràng) + chèn QA amyloidosis
    ("ăn uống kém do buồn nôn", ALL, SYM, [], []),
    ("đau bụng/khó chịu vùng bụng tăng dần", 0, SYM, [], []),
    ("buồn nôn", 1, SYM, [], []),  # dòng gạch đầu dòng riêng
    ("nôn x 1", ALL, SYM, [], []),
    ("chủ quan sốt và run rẩy", ALL, SYM, [], []),
    ("mất cảm giác ngon miệng/chán ăn", ALL, SYM, [], []),
    ("suy nhược", ALL, SYM, [], []),
    ("Toàn trạng suy kiệt", ALL, SYM, [], []),  # khớp không phân biệt hoa/thường -> 2 lần
    ("giảm lượng nước tiểu", 0, SYM, [], []),
    ("tăng đáng kể lượng dịch từ ống thông hồi tràng", 0, SYM, [], []),
    # --- chèn 3 dòng QA amyloidosis (cùng nguồn block 57) ---
    ("Bệnh amyloidosis di truyền hoặc gia đình", 0, DX, [], ["E85.2"]),
    ("Bệnh thoái hóa tinh bột", 0, DX, [], ["E85.9"]),
    ("amyloidosis", 1, DX, [], ["E85.9"]),
    # --- trở lại EHR ---
    ("thiểu niệu", 0, SYM, [], []),
    ("chảy dịch từ lỗ dò tăng đáng kể", 0, SYM, [], []),
    ("thuốc giảm đau opioid", 0, DRUG, [], []),  # nhóm thuốc
    ("thuốc giảm đau opioid", 1, DRUG, [NEG], []),  # "ngừng thuốc giảm đau opioid"
]

GT[5] = [  # 655c ×2  45/50.txt — mục "Tiền sử bệnh" (não úng thuỷ, shunt) -> toàn bộ isHistorical
    ("thông não", 0, LAB, [], []),  # "thông não so với chụp ct đầu" (dịch máy: shunt series)
    ("chụp cắt lớp vi tính (ct) đầu", 0, LAB, [], []),
    ("tăng đau đầu", 0, SYM, [HIST], []),
    ("đau đầu", 1, SYM, [HIST], []),  # "để điều trị chứng đau đầu"
    ("phù gai thị", 0, SYM, [HIST, NEG], []),  # "không phát hiện phù gai thị"
    ("não úng thuỷ khác", 0, DX, [HIST], ["G91.8"]),
    ("tăng nhãn áp", 0, DX, [HIST], ["H40.9"]),
]

GT[58] = [  # 1325c ×1  66.txt — QA vitamin B12 + u vú (kiến thức chung) + chèn 2 dòng EHR x-quang
    ("Vitamin B12", 0, DRUG, [], ["11248"]),
    ("vitamin B12", 1, DRUG, [], ["11248"]),  # "Những người dễ thiếu vitamin B12"
    ("viêm teo niêm mạc dạ dày", 0, DX, [], ["K29.4"]),
    ("B12", 2, DRUG, [], ["11248"]),  # "Khi thiếu B12"
    ("dị cảm", 0, SYM, [], []),
    ("giảm cảm giác vị thế", 0, SYM, [], []),
    ("khả năng trí óc giảm", 0, SYM, [], []),
    ("hạ huyết áp tư thế đứng", 0, SYM, [], []),
    ("ung thư", 0, DX, [], ["C80.9"]),
    ("B12", 3, DRUG, [], ["11248"]),
    ("u nang tuyến vú", ALL, DX, [], ["N60.1"]),
    ("u xơ tuyến vú", ALL, DX, [], ["N60.2"]),
    ("B12", 4, DRUG, [], ["11248"]),
    ("ung thư", 1, DX, [], ["C80.9"]),
    ("B12", 5, DRUG, [], ["11248"]),
    ("thiếu máu", 0, DX, [], ["D64.9"]),
    ("nội tiết Estrogen", 0, DRUG, [], []),  # RxNorm chỉ có estradiol/estrogens conjugated
    # --- 2 dòng EHR ghép vào ---
    ("cúm", 0, LAB, [], []),  # "cúm âm tính" -> tên xét nghiệm (LAB không được có assertion)
    ("âm tính", 0, VAL, [], []),
    ("chụp x-quang ngực", 0, LAB, [], []),
    ("Tăng gánh nhẹ tuần hoàn phổi", 0, DX, [], []),
    ("tràn dịch màng phổi hai bên nhẹ", 0, DX, [], ["J90"]),
    ("tim to", 0, DX, [], ["R93.1"]),
]

GT[57] = [  # 1342c ×1  82.txt — EHR sỏi ống mật chủ (cùng nguồn block 44) + chèn 3 dòng QA amyloidosis
    ("đau vùng hạ sườn phải", ALL, SYM, [], []),
    ("chướng bụng", ALL, SYM, [], []),
    ("buồn nôn thoáng qua", ALL, SYM, [], []),
    ("nôn ói", 0, SYM, [NEG], []),  # "không ghi nhận nôn ói"
    ("đau lưng kéo dài", ALL, SYM, [HIST], []),
    ("Đau bụng", 0, SYM, [], []),
    ("nôn", 3, SYM, [NEG], []),  # "buồn nôn thoáng qua, không nôn"
    ("đau bụng vùng hạ sườn phải", 0, SYM, [], []),
    # --- 3 dòng QA amyloidosis ghép vào (của người hỏi) ---
    ("amyloidosis", 0, DX, [], ["E85.9"]),
    ("hóa trị", 0, DRUG, [], []),  # phương pháp điều trị, không tên thuốc -> để rỗng
    # --- trở lại EHR ---
    ("Nội soi thực quản - dạ dày - tá tràng", 0, LAB, [], []),
    ("viêm dạ dày", 0, DX, [], ["K29.7"]),
    ("Cộng hưởng từ mật tụy", 0, LAB, [], []),
    ("sỏi đoạn cuối ống mật chủ", 0, DX, [], ["K80.5"]),
    ("Nội soi mật tụy ngược dòng (ERCP)", 0, LAB, [], []),
    ("ERCP", 1, LAB, [], []),
    ("02 viên sỏi tại đoạn cuối ống mật chủ (CBD)", 0, DX, [], ["K80.5"]),
    ("chụp cộng hưởng từ mật tụy tụi mật", 0, LAB, [], []),
    ("sỏi ống dẫn mật chung đoạn cuối", 0, DX, [], ["K80.5"]),
]

GT[56] = [  # 1355c ×1  8.txt — EHR tâm thần: ý tưởng tự tử + ảo giác + bệnh lý chất trắng
    ("tự tử", 0, SYM, [], []),
    ("tự tử", 1, SYM, [], []),
    ("Lú lẫn từng đợt gần đây", 0, SYM, [], []),
    ("cảm giác chóng mặt", 0, SYM, [], []),
    ("khó khăn khi nhìn gần", 0, SYM, [], []),
    ("rối loạn thị giác", ALL, SYM, [], []),
    ("ảo giác thị giác", ALL, SYM, [], []),  # 3 lần, kể cả lần trong ngoặc
    ("Ảo thanh (AH)", ALL, SYM, [], []),
    ("ảo giác thính giác", 0, SYM, [], []),
    ("tự tử", 2, SYM, [], []),
    ("Lú lẫn", 1, SYM, [], []),
    ("chóng mặt", 1, SYM, [], []),
    ("Khó khăn về thị lực gần", 0, SYM, [], []),
    ("tự tử", 3, SYM, [], []),
    ("chụp ct sọ", 0, LAB, [], []),
    ("bệnh lý chất trắng", ALL, DX, [], ["G37.9"]),
    ("chọc dò dịch não tủy", 0, LAB, [], []),
    ("các băng nhóm oligoclonal", 0, LAB, [], []),
    ("tự tử chủ động", 0, SYM, [NEG], []),  # "Phủ nhận tự tử chủ động"
]

GT[55] = [  # 1357c ×1  64.txt — QA về MẸ của người hỏi (run tay do trimetazidine, thuốc Nitramyl)
    ("run rẩy tay chân", 0, SYM, [], []),  # câu mô tả tác dụng phụ chung
    ("mất thăng bằng khi đi đứng", 0, SYM, [], []),
    ("run tay", ALL, SYM, [FAM], []),  # 2 lần, đều là của mẹ người hỏi
    ("trimetazidine", 0, DRUG, [FAM], []),  # không có trong RxNorm (không lưu hành ở Mỹ)
    ("Nitramyl", ALL, DRUG, [FAM], []),  # biệt dược VN của nitroglycerin
    ("nitroglycerin", 0, DRUG, [FAM], ["4917"]),
    # --- danh sách tác dụng phụ là kiến thức chung -> không gán assertion
    ("đau thắt ngực", 0, DX, [], ["I20.9"]),
    ("bệnh mạch vành", 0, DX, [], ["I25.9"]),
    ("đau đầu", 0, SYM, [], []),
    ("chóng mặt", 0, SYM, [], []),
    ("buồn nôn", 0, SYM, [], []),
    ("đỏ mặt", 0, SYM, [], []),
    ("tụt huyết áp thế đứng", 0, SYM, [], []),
]

GT[4] = [  # 1372c ×2  75/84.txt — QA nấm bẹn, toàn bộ là tư vấn cho chính người hỏi
    ("Nấm bẹn", ALL, DX, [], ["B35.6"]),  # ALL bắt cả 2 lần "nấm bẹn" thường
    ("nhiễm nấm", 0, DX, [], ["B36.9"]),
    ("nhiễm nấm da", 0, DX, [], ["B35.9"]),
    ("béo phì", 0, DX, [], ["E66.9"]),  # trong danh sách yếu tố nguy cơ chung
    ("thuốc kháng nấm", 0, DRUG, [], []),  # nhóm thuốc, không tên cụ thể
]

GT[1] = [  # 1344c ×4  35/56/67/86.txt — bài phổ biến kiến thức viêm hang vị (= đuôi block 54)
    ("Viêm hang vị sung huyết", 0, DX, [], ["K29.6"]),
    ("đau bụng cồn cào", 0, SYM, [], []),
    ("ợ hơi", 0, SYM, [], []),
    ("ợ chua", 0, SYM, [], []),
    ("buồn nôn", 0, SYM, [], []),
    ("nôn", 1, SYM, [], []),
    ("bệnh dạ dày", 0, DX, [], ["K31.9"]),
    ("nội soi", 0, LAB, [], []),
    ("viêm sung huyết hang vị dạ dày", ALL, DX, [], ["K29.6"]),
    ("nội soi dạ dày", 0, LAB, [], []),
    ("nghệ", 0, DRUG, [], []),
    ("mật ong", 0, DRUG, [], []),
]

GT[54] = [  # 1387c ×1  94.txt — 2 dòng EHR (chèn ép tim) + bài phổ biến kiến thức viêm hang vị
    ("Siêu âm tim", 0, LAB, [], []),
    ("chèn ép tim", 0, DX, [], ["I31.9"]),  # tamponade; CSV không có I31.4
    # --- sang đoạn phổ biến kiến thức: nói chung, không phải BN nào cụ thể -> không assertion
    ("Viêm hang vị sung huyết", 0, DX, [], ["K29.6"]),
    ("đau bụng cồn cào", 0, SYM, [], []),
    ("ợ hơi", 0, SYM, [], []),
    ("ợ chua", 0, SYM, [], []),
    ("buồn nôn", 0, SYM, [], []),
    ("nôn", 1, SYM, [], []),  # [0] nằm trong "buồn nôn"
    ("bệnh dạ dày", 0, DX, [], ["K31.9"]),
    ("nội soi", 0, LAB, [], []),
    ("viêm sung huyết hang vị dạ dày", ALL, DX, [], ["K29.6"]),
    ("nội soi dạ dày", 0, LAB, [], []),  # = "nội soi"[1] mở rộng
    ("nghệ", 0, DRUG, [], []),  # thuốc nam, RxNorm chỉ có turmeric extract -> để rỗng
    ("mật ong", 0, DRUG, [], []),
]

GT[53] = [  # 1420c ×1  62.txt — đuôi QA gút (ông của người hỏi) + EHR ho/thiếu oxy
    ("hạt tophi", 0, DX, [FAM], ["M10"]),  # SỬA (rà mâu thuẫn): trước gán SYM +
    # candidates rỗng. Cùng nguồn QA gút với GT[121] (block 121 gán "hạt tophi" ×5 ->
    # DX M10) và cùng bệnh nhân (ông của người hỏi) -> phải trùng loại và trùng mã.
    # Hạt tophi là lắng đọng urat = biểu hiện định danh của gút, không phải triệu chứng
    # chung. Giữ isFamily vì bệnh của ông người hỏi.
    ("acid uric máu", 0, LAB, [], []),
    ("ho", 1, SYM, [], []),  # "Lý do nhập viện: ho, thiếu oxy" — [0] trong "chuyên khoa"
    ("thiếu oxy", 0, SYM, [], []),
    ("ho", 2, SYM, [], []),
    ("nghẹt ngực", 0, SYM, [], []),
    ("khó thở nhẹ-vừa", 0, SYM, [], []),
    ("khó thở khi gắng sức", ALL, SYM, [], []),
    ("mệt mỏi", ALL, SYM, [], []),
    ("sốt", 0, SYM, [], []),
    ("101", 0, VAL, [], []),  # "sốt lên đến 101" (độ F, đề không có đơn vị)
    ("tiêu chảy", ALL, SYM, [], []),
    ("đi tiểu nhiều lần vào ban đêm", 0, SYM, [], []),
    ("đau buốt khi đi tiểu", 0, SYM, [NEG], []),
    ("ho đặc như bã", 0, SYM, [], []),  # bao trọn "ho"[4], không gán "ho"[4] nữa
    ("khạc nhổ", 0, SYM, [NEG], []),  # "ông ấy không khạc nhổ gì"
    ("sốt", 1, SYM, [], []),
    ("sốt", 2, SYM, [], []),  # lỗi dịch máy lặp "sốt lần cuối sốt là vào ngày"
    ("đau ngực", 0, SYM, [NEG], []),
    ("buồn nôn/nôn", 0, SYM, [NEG], []),
    ("đổ mồ hôi đêm", 0, SYM, [NEG], []),
    ("khó thở khi nằm", 0, SYM, [NEG], []),
    ("khó thở khi nằm đột ngột (paroxysmal nocturnal dyspnea)", 0, SYM, [NEG], []),
    # --- vợ bệnh nhân -> isFamily
    ("giãn phế quản", 0, DX, [FAM], ["J47"]),
    ("azithromycin", 0, DRUG, [FAM], ["18631"]),
    ("tylenol", 0, DRUG, [], ["202433"]),
    ("mucinex d", 0, DRUG, [], ["352777"]),  # SỬA (rà mâu thuẫn): trước để rỗng vì
    # RxNorm chỉ có DP "Mucinex D Maximum Strength"; nhưng BN 352777 "Mucinex" là mã
    # thương hiệu của chính chế phẩm này -> dùng, y GT[20].
    ("spo2", ALL, LAB, [], []),
    ("90-92%", 0, VAL, [], []),
    ("93%", 0, VAL, [], []),
]

GT[52] = [  # 1470c ×1  29.txt — EHR khó thở/nhiễm khuẩn huyết MSSA + QA bàn chân bẹt (bé 3,5 tuổi)
    ("Khó thở tăng dần", 0, SYM, [], []),
    ("nghẹt ngực", ALL, SYM, [], []),
    ("sốt", 0, SYM, [], []),
    ("38,3°C", 0, VAL, [], []),
    ("sốt", 1, SYM, [NEG], []),  # "Sau đó không còn sốt"
    ("khó thở tăng dần", 1, SYM, [], []),
    ("phù ngoại vi tăng dần", 0, SYM, [], []),
    ("sốt", 2, SYM, [HIST], []),  # "tiền sử nhập viện gần đây vì sốt và đau vai"
    ("đau vai", 0, SYM, [HIST], []),
    ("suy hô hấp", 0, DX, [HIST], ["J96.9"]),
    ("tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("lợi tiểu", 0, DRUG, [HIST], []),  # nhóm thuốc, không có tên cụ thể
    ("nhiễm khuẩn huyết do tụ cầu vàng nhạy cảm methicillin", 0, DX, [HIST], ["A41.0"]),
    ("Siêu âm mạch máu chi trên", 0, LAB, [], []),
    ("huyết khối", 0, DX, [NEG], ["I82.9"]),  # "không ghi nhận huyết khối"
    ("xạ hình thông khí - tưới máu phổi", 0, LAB, [], []),
    ("thuyên tắc phổi", 0, DX, [], ["I26.9"]),  # "xác suất thấp" -> vẫn gán, không NEG
    # --- sang QA bàn chân bẹt: con của người hỏi -> FAM (tiền lệ block 26/45) ---
    ("hội chứng bàn chân bẹt bẩm sinh", 0, DX, [FAM], ["Q66.5"]),
    ("gót chân của con cháu khi nhìn ngoại quan nó hơi lệch", 0, SYM, [FAM], []),
    ("lòng bàn chân phẳng", 0, SYM, [FAM], []),
    ("chân có hơi vòng kiềng", 0, SYM, [FAM], []),
]

GT[51] = [  # 1481c ×1  83.txt — đuôi EHR béo phì + QA mày đay bản dịch lỗi (giống block 48)
    ("giảm cân", 0, SYM, [], []),  # "nhiều lần cố gắng giảm cân và tăng cân trở lại"
    ("MÀY đay VÔ CĂN", 0, DX, [], ["L50.1"]),
    ("MÀY đay MẠN", 0, DX, [], ["L50.8"]),
    ("mày đay vô căn", 1, DX, [], ["L50.1"]),
    ("Bạn đay vô căn", 0, DX, [], ["L50.1"]),
    ("***************", ALL, DRUG, [], []),
    ("*********", 0, DRUG, [], []),
]

GT[50] = [  # 1546c ×1  28.txt — QA mày đay vô căn, bản dịch sạch (giống block 43/33), không có EHR
    ("MÀY ĐAY VÔ CĂN", 0, DX, [], ["L50.1"]),
    ("MÀY ĐAY MẠN TÍNH", 0, DX, [], ["L50.8"]),
    ("mày đay vô căn", 1, DX, [], ["L50.1"]),
    ("Mày đay vô căn", 2, DX, [], ["L50.1"]),
    ("****************", ALL, DRUG, [], []),  # kháng histamin H1 thế hệ 2 rồi thế hệ 1
    ("corticoid", 0, DRUG, [], []),
]

# block 86 = 911 ký tự đầu của block 50 và HẾT ở đó -> thừa hưởng toàn bộ.
SHARE[86] = (50, 911)
# block 67 = 659 ký tự đầu của block 62 (EHR não úng thuỷ) + đoạn giảng về viêm
# phổi hoại tử (VPHT) ghép vào giữa, trước dòng "Phù gai thị" cuối.
SHARE[67] = (62, 659)

# ---------------------------------------------------------------------------
# Sáu block dưới đây là TIỀN TỐ của block đã gán tay: chỉ khai SHARE rồi gán
# tay phần đuôi riêng. Rẻ hơn gán lại từ đầu rất nhiều.
# ---------------------------------------------------------------------------

# block 71 = 659 ký tự đầu của block 62 (EHR não úng thuỷ) + đuôi riêng: mục
# "Triệu chứng hiện tại"/"Đặc điểm triệu chứng" của cùng bệnh nhân đó.
SHARE[71] = (62, 659)
GT[71] = [  # 1165c ×1  23.txt — đuôi 506c (659c đầu thừa hưởng block 62)
    ("đau đầu", 3, SYM, [], []),  # "tăng tần suất đau đầu gián đoạn"
    ("đau đầu kéo dài", 1, SYM, [], []),
    ("nhìn mờ ở cả hai mắt, bên trái nặng hơn bên phải", 0, SYM, [], []),
    ("đau đầu", 5, SYM, [], []),  # "cơn  đau đầu nhiều hơn"
    ("nhìn mờ", 2, SYM, [], []),  # "- nhìn mờ: tiến triển trong 2 tuần qua"
    ("đau đầu", 6, SYM, [], []),  # "- đau đầu: nhiều hơn"
    ("phù gai thị", 1, SYM, [], []),  # lý do chuyển cấp cứu -> có thật, khác [0]
]

# block 70 = 655 ký tự đầu của block 66 (QA bệnh dại); dòng "Các yếu tố ... lây
# nhiễm bệnh dại bao gồm:" bị THAY bằng 3 dòng thuốc EHR, nên "bệnh dại"[3]
# của block 66 không tồn tại ở đây (expand_share tự loại vì vượt tiền tố).
SHARE[70] = (66, 655)
GT[70] = [  # 1180c ×1  16.txt — đuôi 525c: 3 dòng thuốc EHR ghép vào giữa bài QA
    ("bumetanide", 0, DRUG, [], ["1808"]),
    ("vancomycin", 0, DRUG, [], ["11124"]),
    ("levofloxacin", 0, DRUG, [], ["82122"]),
]

# block 99 = 648 ký tự đầu của block 121 (QA gút/hạt tophi) + 2 dòng EHR xơ gan.
SHARE[99] = (121, 648)
GT[99] = [  # 800c ×1  80.txt — đuôi 152c: 2 dòng EHR xơ gan mất bù ghép vào
    ("xơ gan mất bù", 0, DX, [], ["K74.6"]),
    ("tăng áp lực tĩnh mạch cửa", 0, DX, [], ["K76.6"]),
    ("cổ trướng", 0, DX, [], ["R18"]),
    ("tràn dịch màng phổi", 0, DX, [], ["J90"]),
    ("liệu pháp lợi tiểu", 0, DRUG, [HIST], []),  # "Thuốc trước khi nhập viện"
]

# block 87 = 586 ký tự đầu của block 7 (câu hỏi mày đay của BẠN người hỏi) +
# danh sách bệnh lý mạn tính của một EHR khác ghép vào đuôi.
SHARE[87] = (7, 586)
GT[87] = [  # 982c ×1  14.txt — đuôi 396c: mục "Các bệnh lý mạn tính" -> isHistorical
    ("Bệnh bạch cầu dòng tủy mãn tính", 0, DX, [HIST], ["C92.1"]),
    ("gleevec", 0, DRUG, [HIST], ["282386"]),
    ("Tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("tăng lipid máu, không đặc hiệu", 0, DX, [HIST], ["E78.5"]),
    ("Đái tháo đường típ 2", 0, DX, [HIST], ["E11"]),
    ("hẹp ống sống", 0, DX, [HIST], ["M48.0"]),
    ("Giả gout", 0, DX, [HIST], ["M11.2"]),  # pseudogout = vôi hoá sụn khớp
    ("bệnh thận mạn, không đặc hiệu Giai đoạn 4", 0, DX, [HIST], ["N18.4"]),
    ("tăng sản tuyến tiền liệt", 0, DX, [HIST], ["N40"]),
    ("Nhiều lần ngã gần đây", 0, SYM, [HIST], []),
    ("Ngã", 1, SYM, [HIST], []),  # [0] nằm trong "Nhiều lần ngã gần đây"
    ("ảo giác", 0, SYM, [HIST], []),
    ("gleevec", 1, DRUG, [HIST, NEG], ["282386"]),  # "(dừng theo chỉ dẫn...)"
]

# block 79 = 550 ký tự đầu của block 60 (EHR buồn nôn/thiểu niệu) + mục "Đặc
# điểm triệu chứng"/"Sự kiện trước khi nhập viện" của cùng bệnh nhân. Block 60
# bị chèn QA amyloidosis vào giữa nên nhiều nhãn ALL của nó không thừa hưởng
# được (đuôi block 79 có thêm lần xuất hiện) -> khai lại bằng ALL ở đây.
SHARE[79] = (60, 550)
GT[79] = [  # 1074c ×1  74.txt — đuôi 524c, cùng bệnh nhân với block 60
    ("ăn uống kém do buồn nôn", ALL, SYM, [], []),
    ("nôn x 1", ALL, SYM, [], []),
    ("chủ quan sốt và run rẩy", ALL, SYM, [], []),
    ("mất cảm giác ngon miệng/chán ăn", ALL, SYM, [], []),
    ("suy nhược", ALL, SYM, [], []),
    ("Toàn trạng suy kiệt", ALL, SYM, [], []),
    ("đau bụng/khó chịu vùng bụng tăng dần", 1, SYM, [], []),  # [0] thừa hưởng
    ("thiểu niệu", 0, SYM, [], []),
    ("chảy dịch từ lỗ dò tăng đáng kể", 0, SYM, [], []),
    ("thuốc giảm đau opioid", 0, DRUG, [], []),
    ("thuốc giảm đau opioid", 1, DRUG, [NEG], []),  # "ngừng thuốc giảm đau"
]

# block 144 = 381 ký tự đầu của block 153 (EHR mệt mỏi/mất trí nhớ); đuôi khác
# hẳn: block 153 rẽ sang câu hỏi bệnh trĩ, block 144 tiếp danh sách triệu chứng.
SHARE[144] = (153, 381)
GT[144] = [  # 504c ×1  46.txt — đuôi 123c
    ("khó thở khi gắng sức", 1, SYM, [], []),
    ("buồn nôn", 1, SYM, [], []),
    ("nôn", 3, SYM, [], []),  # [2] nằm trong "buồn nôn"[1]
    ("*********************", 0, DRUG, [], []),  # 21 sao, dòng kê thuốc
]

# ------------------------------------------------------------------
# Đợt SHARE thứ hai: 5 block dưới đây cũng là tiền tố của block đã gán tay.
# ------------------------------------------------------------------

# block 130 = ĐÚNG 585 ký tự đầu của block 7, không có đuôi riêng -> thừa hưởng
# toàn bộ, không cần GT[130]. Tương tự block 231 = 197 ký tự đầu của block 53.
SHARE[130] = (7, 585)
SHARE[231] = (53, 197)

# block 108 = 453 ký tự đầu của block 66 (QA bệnh dại) + đuôi kể tiếp cùng bài.
# Hai lần "bệnh dại" cuối nằm ở đuôi nên phải khai lại tay.
SHARE[108] = (66, 453)
GT[108] = [  # 728c ×1  13.txt — đuôi 275c của bài QA bệnh dại
    ("bệnh dại", 2, DX, [], ["A82.9"]),  # "ca mắc bệnh dại ở người"
    # bản dịch dính chữ: "lây nhiễm bệnh dạibao gồm" -> chỉ lấy đúng "bệnh dại"
    ("bệnh dại", 3, DX, [], ["A82.9"]),
]

# Ba block 96 / 72 / 81 dùng chung 309 ký tự đầu của block 43 (EHR suy
# kiệt/ảo giác) rồi rẽ ba hướng khác nhau. Năm nhãn EHR đầu thừa hưởng được;
# phần còn lại của EHR + đoạn ghép vào phải gán tay.

SHARE[96] = (43, 309)
GT[96] = [  # 833c ×1  38.txt — đuôi 524c: nốt phần EHR của cùng bệnh nhân
    ("yếu cơ dẫn đến ngã hôm nay", 0, SYM, [], []),
    ("toàn trạng suy kiệt", 1, SYM, [], []),  # "Triệu chứng hiện tại"
    ("toàn trạng suy kiệt", 2, SYM, [], []),  # "Tình trạng ngay trước khi nhập viện"
    ("ảo giác", 2, SYM, [], []),
    ("ảo giác", 3, SYM, [], []),  # "chẩn đoán cho ảo giác bình thường"
    ("Lú lẫn", 2, SYM, [], []),  # [0][1] nằm trong "Lú lẫn ngày càng nặng"
    ("Ăn uống kém, ăn vào dễ nôn", ALL, SYM, [], []),
    ("Nôn không ra máu, không ra dịch mật", ALL, SYM, [], []),
    ("trượt ngã xuống sàn do yếu cơ", 0, SYM, [], []),
    ("gleevec", 0, DRUG, [NEG], ["282386"]),  # "Được hướng dẫn ngừng gleevec"
]

# ------------------------------------------------
# 2 block còn lại của file 54.txt (block 72 đã xong) -> gán TRỌN file.
# 54.txt = QA "uống thuốc lúc mới mang thai có ảnh hưởng thai nhi không" bị CHÈN mục
# "Các bệnh lý mạn tính" + "2. Tiền sử bệnh hiện tại" của EHR suy kiệt/ảo giác (CML
# dùng gleevec) vào giữa, rồi trở lại câu trả lời của bác sĩ.
# Thứ tự đọc: 222 (câu hỏi QA) -> 168 (danh sách bệnh mạn của EHR chèn) -> 72 (mục 2
# của EHR + phần trả lời QA, đã gán, SHARE 309 ký tự đầu với block 43).
# Block 168 là BẢN DỊCH KHÁC của cùng đoạn đã gán ở GT[87] (14.txt) và GT[88] —
# danh sách 9 gạch đầu dòng trùng từng chữ. -> DÙNG LẠI Y NGUYÊN nhãn + mã của GT[87].
# Không SHARE được vì block 168 mở đầu bằng câu hỏi QA "Và e có nên làm xét nghiệm..."
# còn GT[87]/GT[88] mở đầu bằng tiêu đề mục.
# ------------------------------------------------

GT[222] = [  # 241c ×1  54.txt — câu hỏi QA của một thai phụ
    # "Hỏi :", "Xin chào ad.", "Em muốn hỏi 1 vấn đề được không ah?": lời mở đầu
    # -> không gán.
    ("mang thai được hơn 6 tuần", 0, SYM, [], []),  # theo tiền lệ GT[148] cùng dạng
    # câu mở đầu QA gán ("mang thai được 22 tuần", SYM) và cũng giữ số tuần trong bề
    # mặt. LƯU Ý XUNG ĐỘT: GT[105]/GT[107] ghi "có thai"/"không có thai" là trạng thái
    # sinh lý -> KHÔNG gán. Chọn theo GT[148] vì bề mặt ở đây có mốc tuần thai cụ thể
    # và là trạng thái mà cả câu hỏi xoay quanh, giống hệt GT[148]; hai bề mặt trơ
    # "có thai" kia vẫn để nguyên không gán. Ghi vào worklog để rà lại khi có
    # validation split.
    # Người hỏi tự kể về MÌNH -> KHÔNG isFamily (quy ước chốt ở GT[105]).
    ("************", 0, DRUG, [], []),  # tên thuốc bị mask, gán như bề mặt (tiền lệ
    # GT[148] cùng độ rộng mask, GT[43]). RxNorm không tra được -> candidates rỗng.
    # "4 ngày", "ngày 2 viên": thời gian dùng + liều -> không gán (GT[297]/GT[316]).
    # "thai nhi": trạng thái sinh lý, không phải bệnh -> không gán (GT[105]).
]

GT[168] = [  # 423c ×1  54.txt — mục bệnh lý mạn tính của EHR chèn (bản dịch khác GT[87])
    # "Và e có nên làm xét nghiệm gì để sàng lọc không ah?": nói chung, không có tên
    # xét nghiệm -> không gán (tiền lệ GT[72] cùng file bỏ "một xét nghiệm nài"/
    # "các xét nghiệm này").
    # Cả danh sách nằm dưới mục bệnh mạn tính + "Thuốc trước khi nhập viện"
    # -> isHistorical toàn block (y như GT[87]/GT[88]).
    ("Bệnh bạch cầu dòng tủy mãn tính", 0, DX, [HIST], ["C92.1"]),  # y như GT[87]
    ("gleevec", 0, DRUG, [HIST], ["282386"]),  # "đang dùng gleevec" -> chỉ HIST
    ("Tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("tăng lipid máu, không đặc hiệu", 0, DX, [HIST], ["E78.5"]),
    ("Đái tháo đường típ 2", 0, DX, [HIST], ["E11"]),
    ("hẹp ống sống", 0, DX, [HIST], ["M48.0"]),
    ("Giả gout", 0, DX, [HIST], ["M11.2"]),  # pseudogout = vôi hoá sụn khớp
    ("bệnh thận mạn, không đặc hiệu Giai đoạn 4", 0, DX, [HIST], ["N18.4"]),
    ("tăng sản tuyến tiền liệt", 0, DX, [HIST], ["N40"]),
    ("Nhiều lần ngã gần đây", 0, SYM, [HIST], []),
    ("Ngã", 1, SYM, [HIST], []),  # [0] nằm trong "Nhiều lần ngã gần đây" (khớp không
    # phân biệt hoa/thường) -> lấy lần [1] là chữ "Ngã" đứng riêng, y như GT[87].
    ("ảo giác", 0, SYM, [HIST], []),
    ("gleevec", 1, DRUG, [HIST, NEG], ["282386"]),  # "(dừng theo chỉ dẫn sau xuất
    # viện)" -> thuốc đã dừng = isNegated (GT[16]/GT[60]/GT[79]/GT[198]). GT[88] gán
    # cùng bề mặt này mà THIẾU NEG -> đã sửa GT[88] cho khớp, xem worklog đợt 25.
]

SHARE[72] = (43, 309)
GT[72] = [  # 1133c ×1  54.txt — đuôi 824c: nốt EHR rồi ghép QA sàng lọc thai
    ("yếu cơ dẫn đến ngã hôm nay", 0, SYM, [], []),
    ("toàn trạng suy kiệt", 1, SYM, [], []),
    ("ảo giác", 2, SYM, [], []),
    ("Lú lẫn", 2, SYM, [], []),
    # --- QA sàng lọc thai ghép vào: câu nói chung về mọi thai kỳ, không phải
    # chẩn đoán của một người cụ thể -> không gán assertion (như các đoạn giảng).
    ("dị tật bẩm sinh", 0, DX, [], ["Q89.9"]),
    ("nipt", 0, LAB, [], []),
    ("double test", 0, LAB, [], []),
    ("siêu âm", 0, LAB, [], []),
    # "một xét nghiệm nài" / "các xét nghiệm này" là nói chung, không phải tên
    # xét nghiệm -> không gán.
]

SHARE[81] = (43, 309)
GT[81] = [  # 1067c ×1  32.txt — đuôi 758c: nốt EHR rồi ghép đoạn giảng amyloidosis
    ("yếu cơ dẫn đến ngã hôm nay", 0, SYM, [], []),
    ("toàn trạng suy kiệt", 1, SYM, [], []),
    ("ảo giác", 2, SYM, [], []),
    ("Lú lẫn", 2, SYM, [], []),
    ("Ăn uống kém, ăn vào dễ nôn", 0, SYM, [], []),
    ("Nôn không ra máu, không ra dịch mật", 0, SYM, [], []),
    # --- đoạn giảng amyloidosis (không có bệnh nhân cụ thể -> không assertion) ---
    ("Bệnh amyloidosis chuỗi nhẹ", 0, DX, [], ["E85.8"]),  # AL = thoái hóa tinh bột khác
    ("Bệnh amyloidosis tự miễn dịch", 0, DX, [], ["E85.3"]),  # AA = toàn thân thứ phát
    ("Bệnh amyloidosis di truyền hoặc gia đình", 0, DX, [], ["E85.2"]),
    ("Bệnh thoái hóa tinh bột", 0, DX, [], ["E85.9"]),
    ("amyloidosis", 3, DX, [], ["E85.9"]),  # [1][2] nằm trong 2 nhãn dài ở trên
    ("amyloidosis", 4, DX, [], ["E85.9"]),
    # "Uống thuốc" quá chung (đường dùng, không phải thuốc) -> không gán, thống
    # nhất với GT[30]/GT[59] cùng nguồn. "ghép gan" là thủ thuật -> không gán.
    ("hóa trị", 0, DRUG, [], []),
]

GT[102] = [  # 788c ×1  59.txt — CLS EHR nhiễm khuẩn tiết niệu + cơ chế trứng cá (đuôi giống 101)
    ("Phổi thông khí đều", 0, SYM, [], []),
    # "Còn sonde tiểu": thiết bị -> không gán.
    ("nước tiểu có cặn", 0, SYM, [], []),
    ("lactate", 0, LAB, [], []),
    ("1.1-->0.8", 0, VAL, [], []),  # ghi diễn biến 2 giá trị dính nhau, giữ nguyên bề mặt
    ("Cấy nước tiểu", 0, LAB, [], []),
    ("nhiễm khuẩn đường tiết niệu có các vi khuẩn hỗn hợp", 0, DX, [], ["N39.0"]),
    ("cấy máu", 0, LAB, [], []),
    ("âm tính", 0, VAL, [], []),  # tiền lệ cặp "cúm"/"âm tính" ở GT[58]/GT[165]
    ("marker viêm", 0, LAB, [], []),
    ("MRI", 0, LAB, [], []),
    ("viêm xương tủy", 0, DX, [], ["M86.9"]),  # "không thấy ... nặng hơn" = vẫn đang có
    # --- đoạn cơ chế/giảng trứng cá (không có BN cụ thể -> không assertion) ---
    ("Sừng hóa nang lông bất thường", 0, DX, [], ["L73.8"]),
    ("Vi khuẩn C. acne", 0, DX, [], ["B96.8"]),
    ("Viêm tại chỗ", 0, DX, [], []),
    ("mụn trứng cá", 0, DX, [], ["L70.9"]),
    ("mụn", 1, SYM, [], []),  # "thói quen chà xát và nặn mụn"
]

GT[11] = [  # 387c ×2  16.txt, 20.txt — câu trả lời của bác sĩ về đường lây bệnh dại
    # Bài phổ biến kiến thức, không có BN cụ thể -> không assertion (tiền lệ GT[66]).
    ("Bệnh dại", 0, DX, [], ["A82.9"]),
    ("bệnh dại", 1, DX, [], ["A82.9"]),  # "Đường lây bệnh dại phổ biến nhất"
    ("Bệnh dại", 2, DX, [], ["A82.9"]),  # "Bệnh dại còn có thể lây truyền"
    ("bệnh dại", 3, DX, [], ["A82.9"]),  # "động vật khác mắc bệnh dại"
    # "vết thương", "vùng da bị trầy xước": đường vào của virus, mô tả chung của bài
    # giảng, không phải triệu chứng của BN nào -> không gán.
]

GT[13] = [  # 351c ×2  39.txt, 47.txt — mục "1. Tiền sử bệnh" + tiền sử phẫu thuật
    # Cả block nằm dưới "Tiền sử bệnh"/"Các bệnh lý mạn tính" -> isHistorical
    # (tiền lệ block 14/20/87/88/98/9/198/204/241).
    ("Ung thư biểu mô tuyến đại tràng", 0, DX, [HIST], ["C18.9"]),
    ("bệnh phổi tắc nghẽn mạn tính, không xác định", 0, DX, [HIST], ["J44.9"]),
    ("Đái tháo đường", 0, DX, [HIST], ["E14"]),
    ("xơ gan do rượu", ALL, DX, [HIST], ["K70.3"]),  # 2 lần: bệnh mạn + yếu tố nguy cơ
    # "Phẫu thuật mở cắt nối trực tràng/đại tràng sigma": thủ thuật -> không gán.
    ("ung thư tuyến đại tràng", 0, DX, [HIST], ["C18.9"]),  # lý do mổ
]

GT[112] = [  # 698c ×1  69.txt — câu hỏi bản dịch hỏng nặng về "nổi" mạn tính + 1 dòng EHR tâm thần
    # Bản dịch máy hỏng gần hết nghĩa: "nổi những nét nhẹ nhàng nhẹ nhàng rất đến
    # và khắp nơi", "Mẹ của bạn cũng là người nên Yên tĩnh chắc chắn là dây truyền
    # tải" — không suy ra được khái niệm y tế nào chắc chắn. Chỉ gán những bề mặt
    # còn đọc được nghĩa, theo nguyên tắc giữ nguyên văn.
    # Bệnh nhân là BẠN của người hỏi ("em có một người, hiện tại bạn ấy") ->
    # isFamily? Không: isFamily dành cho thân nhân/gia đình. Tiền lệ GT[149] gán
    # isFamily cho bạn của người hỏi -> theo tiền lệ đó, dùng isFamily.
    ("nổi những nét nhẹ nhàng nhẹ nhàng rất đến và khắp nơi", 0, SYM, [FAM], []),
    ("nổi quanh năm", 0, SYM, [FAM], []),
    ("thuốc giảm đau", 0, DRUG, [FAM], []),  # nhóm thuốc, không tên cụ thể
    # "sử dụng rất nhiều thuốc nhưng không đỡ": không có tên thuốc -> không gán.
    ("dị ứng thời tiết", 0, DX, [NEG, FAM], ["T78.4"]),  # "đều không phải dị ứng thời tiết"
    # "hay thức ăn": dị ứng thức ăn dạng rút gọn, bề mặt "thức ăn" một mình không
    # phải khái niệm bệnh -> không gán.
    # --- 1 dòng diễn biến của EHR tâm thần ghép vào cuối: không có khái niệm ---
]

GT[114] = [  # 677c ×1  4.txt — mục "1. Tiền sử bệnh" của EHR nôn ra máu (cùng BN với block 38)
    # Toàn bộ nằm dưới "Tiền sử bệnh" -> isHistorical. Mã dùng lại đúng như GT[38]
    # để không tự mâu thuẫn giữa hai block cùng bệnh nhân.
    ("buồn nôn", 0, SYM, [HIST], []),
    ("tiêu chảy", 0, SYM, [HIST], []),
    ("Nôn ra máu", ALL, SYM, [HIST], []),  # 2 lần
    ("viêm dạ dày ruột do virus", 0, DX, [HIST], ["A08.4"]),
    ("hội chứng ruột kích thích", ALL, DX, [HIST], ["K58"]),  # 2 lần (nhắc lại trong ngoặc)
    ("nội soi", ALL, LAB, [], []),  # 3 lần; LAB không được mang assertion
    ("loét tá tràng", ALL, DX, [HIST], ["K26.9"]),  # 2 lần
    ("hồi tràng", 0, DX, [HIST], ["K63.3"]),  # "nhiều loét tá tràng và hồi tràng"
    ("Viêm thực quản độ C", 0, DX, [HIST], ["K20"]),
    ("loét thực quản dưới 6 mm có điểm sắc tố", 0, DX, [HIST], ["K22.1"]),
    ("nhiều loét nông sạch đáy ở tá tràng và hồi tràng sớm", 0, DX, [HIST], ["K26.9"]),
    # -> nhãn này chứa lần [1] của "hồi tràng" nên không khai "hồi tràng" ALL.
    ("omeprazole", 0, DRUG, [NEG, HIST], ["7646"]),  # "(vừa ngừng để làm test...)"
    ("test hơi thở h. pylori", 0, LAB, [], []),
]

# ---------------------------------------------------------------------------
# File 41.txt = MỘT bài QA trứng cá (BN 15 tuổi tự kể) + phần giảng cơ chế/phân
# loại/điều trị, có 2 dòng EHR đau ngực bị GHÉP vào giữa (đã gán ở GT[101]).
# 4 block còn lại: câu hỏi của BN (block 177), mục "1." cơ chế (block 206),
# mục "2." bốn yếu tố (block 263), phân loại viêm/không viêm (block 289).
#
# Quy ước chốt cho cả file:
#  - Người hỏi tự kể về CHÍNH MÌNH -> KHÔNG isFamily (tiền lệ GT[113] cùng
#    nguồn, cùng mẫu câu "Cháu năm nay ... tuổi da rất nhiều dầu và bị mụn
#    trứng cá").
#  - Đoạn GIẢNG cơ chế/phân loại (không có BN cụ thể) -> không assertion
#    (tiền lệ GT[102]/GT[2]).
#  - Tái dùng đúng mã đã chốt ở các block cùng nguồn: "mụn trứng cá"/"Trứng cá"
#    -> L70.9 (GT[113]/GT[101]/GT[102]), "nhân mụn"/"Nhân mụn" -> L70.0
#    (GT[101]/GT[2]), "Sừng hóa nang lông bất thường" -> L73.8, "Vi khuẩn C.
#    acne" -> B96.8, "Viêm tại chỗ" -> rỗng (cả 3 từ GT[102]).
#  - "mụn" đứng riêng -> TRIỆU_CHỨNG (tiền lệ GT[113]: mụn trứng cá là CHẨN_ĐOÁN
#    còn "mụn" trơ trọi là biểu hiện). "da rất nhiều dầu" -> TRIỆU_CHỨNG
#    (tiền lệ GT[113] cùng bề mặt).
# ---------------------------------------------------------------------------

GT[177] = [  # 400c ×1  41.txt — câu hỏi của BN 15 tuổi (bản ngắn của block 113)
    # Cùng nguồn với GT[113] (60.txt) nhưng bản dịch NGẮN hơn: đổi 18->15 tuổi,
    # lớp 8->lớp 7, 6 tháng->4 tháng, cắt hết đoạn "mụn cám/mụn đầu trắng" và
    # đoạn lo ngại thuốc. Vì vậy KHÔNG dùng SHARE được (khác từ giữa câu), phải
    # gán tay và số thứ tự lần xuất hiện của "mụn" cũng khác GT[113].
    ("da rất nhiều dầu", 0, SYM, [], []),  # tiền lệ GT[113] cùng bề mặt -> SYM
    ("mụn trứng cá", 0, DX, [], ["L70.9"]),  # tiền lệ GT[113]/GT[101]/GT[102]
    # "mụn" có 5 lần: [0] nằm trong nhãn "mụn trứng cá" ở trên nên bỏ.
    ("mụn", 1, SYM, [], []),  # "da cháu bắt đầu lên mụn trở lại"
    ("mụn", 2, SYM, [], []),  # "gồm mụn ở trán"
    ("mụn", 3, SYM, [], []),  # "chăm sóc da dầu mụn" — tiền lệ GT[113] gán lần
    # này là "mụn" trơ chứ không lấy cả cụm "da dầu mụn" (GT[2] có nhãn dài
    # "da mụn" nhưng bề mặt ở đó là "chăm sóc da mụn", không có chữ "dầu").
    ("mụn", 4, SYM, [], []),  # "làm thế nào để da hết mụn không tái phát"
    # "Chào bác sĩ", "Câu trả lời của bác sĩ:", "đi khám da liễu" (chuyên khoa),
    # "3 tháng điều trị" (thời gian): không phải khái niệm -> không gán.
    # "da cháu đã đỡ hẳn": diễn biến tốt, không phải triệu chứng -> không gán
    # (tiền lệ GT[113] không gán "da cháu ít dầu hơn").
]

GT[206] = [  # 288c ×1  41.txt — mục "1." cơ chế sinh mụn + mở đầu phần phân loại
    # Đoạn giảng, không có BN -> không assertion.
    ("Mụn", 0, SYM, [], []),  # "1.Mụn xuất hiện thông qua..." — nói về hiện
    # tượng mụn nói chung, bề mặt trơ 1 chữ -> SYM như tiền lệ "mụn" ở GT[113].
    ("Sản xuất quá nhiều chất bã nhờn", 0, DX, [], []),  # 1 trong 4 yếu tố sinh
    # bệnh, dạng CĐ mô tả. Không có mã: danh mục BYT chỉ có L72.1/L72.2 (kén /
    # u nang tuyến bã) và L82 (dày sừng tiết bã), không mã nào là "tăng tiết bã
    # nhờn" -> candidates rỗng nhưng VẪN gán (tiền lệ GT[102] "Viêm tại chỗ").
    ("Bít tắc nang lông bởi chất bã và tế bào sừng", 0, DX, [], ["L73.8"]),
    # L73.8 "Bệnh lý nang lông xác định khác" — cùng mã GT[102] đã chốt cho
    # "Sừng hóa nang lông bất thường" (cùng họ bệnh lý nang lông). Lấy TRỌN cụm
    # vì "bởi chất bã và tế bào sừng" là cơ chế của chính nó, không tách nhãn con
    # (tiền lệ GT[101] giữ trọn "đau sau xương ức lan ra sau lưng").
    ("Vi hệ tại nang lông bởi Propionibacterium acnes (vi khuẩn kỵ khí thông thường)",
     0, DX, [], ["B96.8"]),  # cùng khái niệm với "Vi khuẩn C. acne" ở GT[102]
    # (C. acnes = tên mới của P. acnes) -> cùng mã B96.8. Giữ TRỌN cả phần trong
    # ngoặc theo quy ước "mô tả trong ngoặc giữ nguyên, không gán nhãn lồng".
    ("Giải phóng các chất trung gian gây viêm", 0, DX, [], []),  # tương ứng
    # "Viêm tại chỗ" của GT[102] -> cũng để candidates rỗng. Không tách "viêm"
    # riêng vì đã nằm trong nhãn này.
    ("Trứng cá", 0, DX, [], ["L70.9"]),  # "Trứng cá có thể được phân loại là"
    # -> tiền lệ GT[113] ("Trứng cá" -> L70.9).
]

GT[263] = [  # 133c ×1  41.txt — mục "2." bốn yếu tố (bản trùng đoạn đuôi GT[102])
    # 4 dòng gạch đầu dòng này CHÍNH LÀ đoạn đã gán ở GT[102] (59.txt), chỉ khác
    # dòng đầu "- Tăng sản tuyến bã nhờn" mà ở 59.txt bị cắt mất. Đo bằng grep:
    # "Tăng sản tuyến bã nhờn" chỉ có ở 41.txt và 92.txt. Không SHARE được vì
    # block này có tiêu đề "2. Trứng cá bắt nguồn..." ở đầu, không phải tiền tố
    # của block 102.
    ("Trứng cá", 0, DX, [], ["L70.9"]),  # tiền lệ GT[113]
    ("Tăng sản tuyến bã nhờn", 0, DX, [], []),  # không có mã (xem lý do ở
    # GT[206] "Sản xuất quá nhiều chất bã nhờn") -> rỗng nhưng vẫn gán.
    ("Sừng hóa nang lông bất thường", 0, DX, [], ["L73.8"]),  # tiền lệ GT[102]
    ("Vi khuẩn C. acne", 0, DX, [], ["B96.8"]),  # tiền lệ GT[102]
    ("Viêm tại chỗ", 0, DX, [], []),  # tiền lệ GT[102] (để rỗng)
]

GT[289] = [  # 88c ×1  41.txt — phân loại trứng cá viêm / không viêm
    # Đoạn giảng -> không assertion. "Không viêm"/"Viêm" ở đây là TÊN THỂ BỆNH
    # trứng cá (trứng cá không viêm / trứng cá viêm), nhưng bề mặt trơ 1-2 chữ
    # quá chung nên KHÔNG gán riêng — thống nhất với GT[101] cùng file: ở đó bề
    # mặt là "Trứng cá viêm nhẹ" (có đủ chữ "Trứng cá") mới gán DX. Ở đây chỉ có
    # "- Viêm:" nên bỏ, tránh tạo khái niệm sai loại (đề trừ 2 lần nếu sai loại).
    ("nhân mụn", 0, DX, [], ["L70.0"]),  # tiền lệ GT[101] "Nhân mụn" / GT[2]
    # "nhân mụn" -> L70.0 (Trứng cá thể thông thường = acne vulgaris; comedo
    # không có mã riêng trong danh mục BYT).
    ("sẹo", 0, SYM, [], []),  # tiền lệ GT[101] cùng bề mặt -> SYM, candidates
    # rỗng (danh mục chỉ có sẹo giác mạc/kết mạc/rụng tóc có sẹo, không có sẹo
    # do trứng cá; L73.0 "Trứng cá sẹo lồi" là thể bệnh khác, không dùng).
    ("mụn mủ", 0, SYM, [], []),  # tổn thương da (pustule). L13.1/L40.2 là bệnh
    # viêm da mụn mủ khác hẳn -> không dùng, SYM candidates rỗng.
    ("nốt sần", 0, SYM, [], []),  # "nốt sần" là lối dịch của "nodule" (tiền lệ
    # GT[225] "nốt sần tuyến giáp...") -> tổn thương da, SYM.
    ("nang", 0, SYM, [], []),  # "cyst" — tổn thương da của trứng cá bọc. Không
    # dùng L70.1 "Trứng cá bọc" vì bề mặt chỉ là 1 tổn thương, không phải tên
    # thể bệnh. 1 lần duy nhất trong block (các chữ "nang" khác nằm trong nhãn
    # dài của block 206, khác block).
]

# Block 0 = đúng 1 dòng "Câu hỏi từ người dùng:" (22c, xuất hiện ở 23 file):
# tiêu đề mục, không có khái niệm y khoa -> DONE_EMPTY (tiền lệ GT[166] bỏ
# tiêu đề "Thuốc:", GT[186] bỏ "3/ đơn thuốc:").
DONE_EMPTY.add(0)

# ---------------------------------------------------------------------------
# File 10.txt = MỘT EHR đánh trống ngực / ngoại tâm thu (block 34, đã gán ở đợt
# trước là mục 2 "Tiền sử bệnh hiện tại" dài 2016c) + 3 block còn lại: mục 1
# "Tiền sử bệnh" (block 175), mục 3 "Đánh giá tại bệnh viện" (block 245) và phần
# kết quả cận lâm sàng (block 186). Block 245 bị GHÉP thêm 1 dòng chẩn đoán viêm
# gan B của EHR khác (cùng nguồn với GT[133]/GT[39] ở file 24.txt).
#
# QUY ƯỚC LIỀU THUỐC — chuẩn hoá ở đợt này (trước đó bất nhất):
#   Bề mặt THUỐC chỉ gồm TÊN thuốc, KHÔNG gồm hàm lượng.
#   Đo bằng cách quét lại data/gt_block/*.json: 16 nhãn THUỐC có hàm lượng đứng
#   ngay sau nhưng KHÔNG gộp vào bề mặt (bumetanide 2mg, levofloxacin 750mg,
#   lasix 40 mg, Simethicon 100mg, metoclopramide 10mg, metoprolol 25mg,
#   aspirin 325mg ở 10.txt, Philpovin 5g, Fortex 25mg, acetaminophen 500mg...)
#   so với chỉ 6 nhãn có gộp (4 nhãn 36.txt + "aspirin 325mg"/"methylprednisolone
#   125mg" ở GT[128]). Đa số áp đảo -> lấy "chỉ tên thuốc" làm chuẩn và SỬA 6 nhãn
#   thiểu số về đúng chuẩn. Lý do chọn hướng này thay vì hướng ngược lại: hàm lượng
#   không phải một phần của khái niệm thuốc, và đề tính WER trên bề mặt nên bề mặt
#   ngắn-đúng an toàn hơn bề mặt dài-thừa.
#
# Quy ước chốt cho cả file:
#  - Mục "1. Tiền sử bệnh" / "Thuốc trước khi nhập viện" -> isHistorical (tiền lệ
#    GT[9]/GT[14]/GT[20]/GT[87]). Mục "3. Đánh giá tại bệnh viện" là lần nhập viện
#    HIỆN TẠI -> không assertion (tiền lệ GT[143]/GT[98]).
#  - Tái dùng đúng mã của GT[34] (cùng EHR) cho khái niệm trùng: metoprolol 6918,
#    atenolol 1202, ngoại tâm thu thất I49.3, ngoại tâm thu nhĩ, Nhịp xoang chiếm
#    ưu thế, monitor holter, chụp x-quang ngực, phân tích nước tiểu.
#  - "không có gì đáng chú ý" / "không ghi nhận gì bất thường" = kết quả BÌNH
#    THƯỜNG -> KHÔNG gán KẾT_QUẢ_XÉT_NGHIỆM (tiền lệ GT[143] "điện tâm đồ bình
#    thường" cũng không gán VAL, GT[141]/GT[68]/GT[133] không gán dấu hiệu bình
#    thường). Tên xét nghiệm thì vẫn gán.
# ---------------------------------------------------------------------------

GT[175] = [  # 403c ×1  10.txt — mục "1. Tiền sử bệnh" + "Các yếu tố nguy cơ liên quan"
    # --- "Thuốc trước khi nhập viện" -> isHistorical ---
    ("metoprolol", 0, DRUG, [HIST], ["6918"]),  # tiền lệ GT[34] cùng EHR (mã 6918)
    ("doxycycline", 0, DRUG, [HIST], ["3640"]),  # tiền lệ GT[9]/GT[46] cùng mã
    ("viêm tuyến mồ hôi", 0, DX, [HIST], ["L73.2"]),  # "doxycycline cho viêm tuyến mồ
    # hôi" = bệnh đang được điều trị từ trước -> HIST. L73.2 "Viêm tuyến mồ hôi mủ
    # [nhọt ổ gà]" là mã duy nhất khớp trong danh mục BYT (hidradenitis suppurativa).
    ("atenolol", 0, DRUG, [HIST], ["1202"]),  # tiền lệ GT[34] cùng EHR. Dù "(uống hôm
    # nay)" là hôm nay, dòng này nằm trong danh sách thuốc DÙNG TRƯỚC khi nhập viện
    # nên vẫn HIST — thống nhất với chính GT[34] ("Ở nhà bệnh nhân đã sử dụng
    # atenololtrong ngày" thuộc "Các diễn biến trước khi nhập viện").
    # --- "Các yếu tố nguy cơ liên quan" ---
    ("Căng thẳng", 0, SYM, [], []),  # tiền lệ GT[64] cùng bề mặt "căng thẳng" -> SYM
    # (không dùng F43.9 như GT[85]/GT[233]: ở hai chỗ đó bề mặt là "stress"/"Stress
    # kéo dài" nằm trong danh sách BỆNH/lời khuyên, còn đây là căng thẳng công việc
    # do BN kể -> biểu hiện, không phải chẩn đoán). Yếu tố nguy cơ đang tồn tại
    # -> không HIST.
    # "Mất việc làm 8 ngày trước": sự kiện xã hội -> không gán.
    # "hàng chục tách cà phê có caffeine", "1 tách cà phê không caffeine": chất kích
    # thích trong đời sống -> KHÔNG gán (tiền lệ GT[85] "cà phê, chè, thuốc lá",
    # GT[98] "Uống rượu 30 năm"). Vì vậy không khai "cà phê"/"caffeine" (mỗi cụm 2 lần).
    # Lưu ý: caffeine CÓ trong RxNorm nhưng ở đây không phải thuốc điều trị.
    # "Theo lời bệnh nhân kể lại": chính BN là người bệnh -> KHÔNG isFamily
    # (tiền lệ GT[141]).
]

GT[186] = [  # 363c ×1  10.txt — kết quả XN/CĐHA của mục 3 + tiêu đề "3/ đơn thuốc"
    # Lần nhập viện hiện tại -> không assertion.
    # "3/ đơn thuốc:" — tiêu đề mục bị ghép, không có tên thuốc nào theo sau
    # -> không gán (tiền lệ GT[166] bỏ tiêu đề "Thuốc:").
    ("phân tích nước tiểu", 0, LAB, [], []),  # tiền lệ GT[34] cùng EHR
    ("chụp x-quang ngực", 0, LAB, [], []),  # tiền lệ GT[34] cùng EHR
    ("điện tâm đồ", 0, LAB, [], []),  # tiền lệ GT[143]/GT[89]; GT[34] cùng EHR gán "ecg"
    ("monitor holter", 0, LAB, [], []),  # tiền lệ GT[34] cùng EHR
    ("Nhịp xoang chiếm ưu thế", 0, DX, [], []),  # tiền lệ GT[34]: không có mã ICD cho
    # nhịp xoang bình thường/chiếm ưu thế -> candidates rỗng nhưng VẪN gán.
    ("ngoại tâm thu nhĩ", 0, DX, [], []),  # tiền lệ GT[34] cùng EHR để rỗng. (I49.1
    # "Atrial premature depolarization" tồn tại trong danh mục BYT nhưng cột tên
    # tiếng Việt RỖNG -> không dùng, giữ nhất quán với GT[34].)
    ("ngoại tâm thu thất", 0, DX, [], ["I49.3"]),  # tiền lệ GT[34] cùng mã
    # "không có gì đáng chú ý" (2 lần), "không ghi nhận gì bất thường" (2 lần):
    # kết quả bình thường -> không gán VAL, cũng không gán isNegated cho tên XN
    # (TÊN_XÉT_NGHIỆM không được mang assertion, check() chặn).
    # "Các kết quả chẩn đoán khác", "Kết quả xét nghiệm", "Kết quả chẩn đoán hình
    # ảnh": tiêu đề mục -> không gán.
]

GT[245] = [  # 170c ×1  10.txt — mục "3. Đánh giá tại bệnh viện" + 1 dòng chẩn đoán EHR khác ghép vào
    ("98.3 12987 56 18 99RA", 0, VAL, [], []),  # chuỗi sinh hiệu bị dịch làm dính hết
    # vào nhau: "VS" (vital signs) 98.3°F / 129-87 mmHg / mạch 56 / nhịp thở 18 /
    # SpO2 99% RA (room air). KHÔNG tách được thành từng trị số vì không có dấu phân
    # cách nào -> gán TRỌN 1 bề mặt VAL, giữ nguyên văn (tiền lệ GT[115] "8.126.3"
    # dính 2 trị số, GT[17] "vếtvết protein niệu", GT[102] "1.1-->0.8").
    ("VS", 0, LAB, [], []),  # nhãn tên phép đo viết tắt, dính liền trị số -> bề mặt
    # riêng (tiền lệ GT[162] ("M", 12) và GT[91] ("M", 15) cho nhãn mạch viết tắt).
    # --- dòng ghép từ EHR viêm gan B (cùng nguồn GT[133]/GT[39], file 24.txt) ---
    ("Viêm gan cấp tính do virus B thể thông thường điển hình mức độ nặng giai đoạn toàn phát",
     0, DX, [], ["B16.9"]),  # ở GT[133] cùng câu này bị cắt mất chữ "Viêm gan" đầu
    # nên bề mặt ngắn hơn; ở đây câu ĐẦY ĐỦ -> lấy trọn. Cùng mã B16.9 (viêm gan B
    # cấp không kèm viêm gan D, không hôn mê gan) như GT[133]/GT[39].
    # "Kết quả khám lâm sàng": tiêu đề mục -> không gán.
]

# ---------------------------------------------------------------------------
# File 36.txt = MỘT bệnh án viết tay hoàn chỉnh (BN nam 17t hội chứng thận hư /
# viêm cầu thận mạn): phần bệnh sử + phiếu XN (block 77, đã gán) rồi mục 2 Chẩn
# đoán, 3 Tiên lượng, 4 Hướng xử trí, 5 Đơn thuốc. TRỪ block 225 là "2. Tiền sử
# bệnh hiện tại" của một EHR khác (ca FNA tuyến giáp + sỏi mật) bị ghép vào giữa
# đơn thuốc, và dòng thuốc số 5 (block 327) bị đẩy xuống sau mẩu ghép đó.
# Quy ước chốt cho cả file:
#  - Bệnh án của BN cụ thể, các mục 2–5 nói về tình trạng HIỆN TẠI -> KHÔNG
#    assertion (chỉ mục "Tiền sử" ở block 77 mới có HIST, đã gán ở đợt trước).
#  - Dòng đơn thuốc "<Tên> <hàm lượng> x <n> viên, uống ...": chỉ gán TÊN THUỐC,
#    bỏ hàm lượng / "x n viên" / đường-giờ dùng (chuẩn hoá ở đợt 12; xem ghi chú
#    quy ước liều thuốc ở đầu batch 10.txt).
#  - Mục "Làm thêm các xét nghiệm ..." = xét nghiệm được CHỈ ĐỊNH -> vẫn là
#    TÊN_XÉT_NGHIỆM (tiền lệ GT[195] panel Kawasaki, GT[133] y lệnh theo dõi ALT/AST).
#  - Chế độ ăn (cơm nhạt, tăng protein/glucid, không lipid): dinh dưỡng, không phải
#    thuốc/xét nghiệm/triệu chứng -> không gán.
# ---------------------------------------------------------------------------

GT[166] = [  # 425c ×1  36.txt — mục "4. Hướng xử trí" + tiêu đề mục 5
    # Xét nghiệm chỉ định theo dõi -> LAB (tiền lệ GT[133]/GT[195]).
    ("protein niệu 24h", 0, LAB, [], []),  # tiền lệ GT[77] cùng bệnh án ("Protein niệu 24h")
    ("protein máu", 0, LAB, [], []),  # tiền lệ GT[77] "Protein máu"
    ("albumin máu", 0, LAB, [], []),  # tiền lệ GT[77] "Albumin"
    ("điện giải đồ", 0, LAB, [], []),  # tiền lệ GT[77] "Điện giải"
    # "tăng protein (2 lạng thịt/ngày)", "không lipid", "tăng glucid": chế độ ĂN,
    # không phải triệu chứng tăng/giảm chất trong máu -> không gán (đây là chỗ dễ
    # gán sai thành SYM "tăng lipid máu"). Vì vậy KHÔNG khai "protein"[2] và
    # "lipid"[0].
    # "uống ít nước < 1l/ngày": chế độ ăn uống -> không gán.
    # "Thuốc:": tiêu đề mục -> không gán.
    ("VCTM", 0, DX, [], ["N03.9"]),  # viết tắt "viêm cầu thận mạn" — tiền lệ GT[77]
    # cùng bệnh án gán "Tổn thương cầu thận mạn tính" -> N03.9. Viết tắt là một bề
    # mặt riêng (tiền lệ GT[271] "ASA" vs mask, GT[56] "Ảo thanh (AH)").
    # "theo cơ chế bệnh sinh": cơ chế -> không gán.
    ("phù", 0, SYM, [], []),  # "Điều trị triệu chứng: phù" — tiền lệ GT[77] cùng bệnh án
    ("tăng lipid máu", 0, SYM, [], []),  # ở đây là triệu chứng ĐANG điều trị của BN.
    # Khác GT[87]/GT[88] gán "tăng lipid máu, không đặc hiệu" -> DX E78.5: ở đó bề
    # mặt trùng nguyên văn TÊN MÃ ICD (bệnh lý mạn tính trong danh sách chẩn đoán),
    # còn đây là một biểu hiện trong mục "Điều trị triệu chứng" -> SYM, không mã.
    ("giảm thải protein", 0, SYM, [], []),  # chứa lần [3] của "protein"
]

GT[225] = [  # 217c ×1  36.txt — MẨU EHR LẠ ghép vào: "2. Tiền sử bệnh hiện tại" ca FNA tuyến giáp
    # "Tiền sử bệnh hiện tại" = HPI -> KHÔNG isHistorical (tiền lệ GT[129]/GT[139]/GT[176]).
    ("FNA", 0, LAB, [], []),  # chọc hút kim nhỏ = xét nghiệm tế bào học (tiền lệ
    # GT[40] "chọc hút dịch" -> LAB, GT[27] "sinh thiết" -> LAB).
    ("nốt sần tuyến giáp phải có cấu trúc vi nang", 0, DX, [], ["E04.1"]),  # bướu
    # giáp đơn nhân không độc; "nốt sần" là lỗi dịch của "nodule" -> giữ nguyên văn.
    ("đau vùng hạ sườn phải", 0, SYM, [], []),  # tiền lệ GT[57]/GT[44]
    # --- "Các sự kiện trước khi nhập viện" -> đã qua -> isHistorical (tiền lệ GT[129]/GT[176]) ---
    ("siêu âm", 0, LAB, [], []),  # LAB không được có assertion (check() chặn)
    ("sỏi mật", 0, DX, [HIST], ["K80.2"]),  # tiền lệ GT[110] cùng bề mặt + HIST -> K80.2
    # (K80.2 = sỏi túi mật không kèm viêm; GT[37] dùng K80.5 nhưng ở đó là sỏi ống
    # mật chủ trên ERCP -> hai bối cảnh khác nhau, không phải mâu thuẫn).
]

GT[303] = [  # 65c ×1  36.txt — mục "3. Tiên lượng"
    ("bệnh tổn thương mạn tính", 0, DX, [], ["N03.9"]),  # nói về chính viêm cầu thận
    # mạn của BN (tiền lệ GT[77] "Tổn thương cầu thận mạn tính" -> N03.9).
    # "Tiên lượng: vừa", "tỉ lệ tái phát cao": tiên lượng/dịch tễ -> không gán.
]

GT[316] = [  # 54c ×1  36.txt — đơn thuốc dòng 1
    ("Medrol", 0, DRUG, [], ["202702"]),  # RxNorm BN Medrol (methylprednisolone
    # IN = 6902); gán cả hàm lượng vào bề mặt theo tiền lệ GT[128] "aspirin 325mg".
    # "x 3 viên, uống 8h sáng sau ăn no": liều/đường dùng -> không gán (GT[297]).
]

GT[319] = [  # 51c ×1  36.txt — mục "2. Chẩn đoán"
    ("Viêm cầu thận mạn", 0, DX, [], ["N03.9"]),  # tiền lệ GT[77] cùng bệnh án
    ("Hội chứng thận hư", 0, DX, [], ["N04"]),  # tiền lệ GT[77] cùng bệnh án
]

GT[323] = [  # 46c ×1  36.txt — đơn thuốc dòng 3
    ("Furosemid", 0, DRUG, [], ["4603"]),  # furosemide IN = 4603; cách viết
    # Việt bỏ "e" cuối vẫn là cùng hoạt chất (tiền lệ "Simethicon" -> 9796,
    # "nhôm hydroxid" -> 612, "trimetazidin").
]

GT[326] = [  # 43c ×1  36.txt — đơn thuốc dòng 2
    ("Omez", 0, DRUG, [], ["7646"]),  # Omez = biệt dược omeprazole (Dr. Reddy's),
    # KHÔNG có trong RxNorm (không lưu hành ở Mỹ) -> dùng mã hoạt chất omeprazole
    # IN 7646, theo tiền lệ GT[35] "Pimperan" -> 6915 (mã hoạt chất) thay vì để rỗng.
]

GT[327] = [  # 43c ×1  36.txt — đơn thuốc dòng 5 (bị mẩu EHR lạ đẩy xuống cuối file)
    ("Zestril", 0, DRUG, [], ["196472"]),  # RxNorm BN Zestril (lisinopril IN = 29046)
]

# ---------------------------------------------------------------------------
# File 8.txt = HAI nguồn ghép: (a) bệnh án tâm thần (ý tưởng tự tử + ảo giác +
# bệnh lý chất trắng) — block 56 và block 190/155 là mục 1/2/3 của CÙNG bệnh án
# này; (b) bài giảng "Bệnh Kawasaki" cùng nguồn GT[104]/GT[124]/GT[135]/GT[140].
# Block 56 và 140 đã gán ở đợt trước; đợt này gán 6 block còn lại cho trọn file.
# Quy ước chốt cho cả file:
#  - Phần bệnh án: mục "1. Tiền sử bệnh" / "Các bệnh lý mạn tính" / "Thuốc trước
#    khi nhập viện" -> isHistorical (tiền lệ GT[9]/GT[14]/GT[20]/GT[87]); mục
#    "3. Đánh giá tại bệnh viện" là lần nhập viện HIỆN TẠI -> KHÔNG assertion.
#  - Tái dùng đúng mã của GT[56] cho các khái niệm trùng: bệnh lý chất trắng
#    -> G37.9, chọc dò dịch não tủy -> LAB, các băng nhóm oligoclonal -> LAB.
#  - Lỗi dịch "- ho X" (= "h/o X", history of) -> BỎ chữ "ho", chỉ lấy tên bệnh
#    (tiền lệ GT[87] với "- ho Bệnh bạch cầu dòng tủy mãn tính").
#  - Phần bài giảng Kawasaki: KHÔNG assertion (tiền lệ GT[104]/GT[140]); mốc thời
#    gian/kích thước sau tên triệu chứng cắt khỏi bề mặt (tiền lệ GT[140] lấy
#    "Sốt" cho "Sốt ≥5 ngày"); cụm mô tả trong ngoặc cùng dòng giữ TRỌN thành 1
#    bề mặt, không tách nhãn lồng nhau (tiền lệ GT[313]).
# ---------------------------------------------------------------------------

GT[155] = [  # 452c ×1  8.txt — "3. Đánh giá tại bệnh viện" của bệnh án tâm thần (cùng bệnh án GT[56])
    # Đây là lần nhập viện hiện tại -> KHÔNG isHistorical.
    ("chọc dò dịch não tủy", ALL, LAB, [], []),  # 2 lần: dòng kết quả XN + dòng
    # "Các thủ thuật đã thực hiện". Tiền lệ GT[56] cùng bệnh án -> LAB.
    ("âm tính", 0, VAL, [], []),  # "chọc dò dịch não tủy là âm tính" — kết quả bằng
    # chữ, tiền lệ cặp tên XN + "âm tính" ở GT[58]/GT[102]/GT[165].
    ("chụp ct sọ", 0, LAB, [], []),  # tiền lệ GT[56]
    ("bệnh lý chất trắng", ALL, DX, [], ["G37.9"]),  # 3 lần, tiền lệ GT[56] cùng mã
    ("Đột sống thắt lưng", 0, LAB, [], []),  # lỗi dịch của "(Lumbar Puncture)" —
    # là TÊN KHÁC của chính chọc dò dịch não tủy, đặt trong ngoặc nên là một bề mặt
    # riêng (tiền lệ GT[56] gán cả "Ảo thanh (AH)" và "ảo giác thính giác").
    ("các băng nhóm oligoclonal", 0, LAB, [], []),  # tiền lệ GT[56]
    # "đánh giá thần kinh": đánh giá/thủ thuật, không phải tên xét nghiệm cụ thể
    # -> không gán (GT[56] cùng câu cũng không gán).
    # "đang chờ kết quả" -> chưa có kết quả, không gán VAL (tiền lệ GT[132]).
    # "Nguyên nhân chưa rõ", "được phát hiện tình cờ": nhận định -> không gán.
]

GT[190] = [  # 344c ×1  8.txt — "1. Tiền sử bệnh" của cùng bệnh án tâm thần -> isHistorical
    ("Rối loạn cảm xúc", 0, DX, [HIST], ["F39"]),  # tiền lệ GT[84]/GT[147] cùng mã.
    # Bỏ chữ "ho" đứng trước (lỗi dịch của "h/o") theo tiền lệ GT[87].
    ("trầm cảm", 0, DX, [HIST], ["F32.9"]),  # lần [0] nằm trong ngoặc "(trầm cảm)"
    ("giai đoạn trầm cảm không đặc hiệu", 0, DX, [HIST], ["F32.9"]),  # trùng nghĩa
    # tên mã F32.9 "Giai đoạn trầm cảm, không xác định"; chứa lần [1] của "trầm cảm".
    ("hội chứng nghiện rượu", ALL, DX, [HIST], ["F10.2"]),  # 2 lần: dòng bệnh mạn +
    # dòng "Các yếu tố nguy cơ liên quan". F10.2 = rối loạn do rượu, hội chứng nghiện.
    ("seroquel", 0, DRUG, [HIST], ["83553"]),  # RxNorm BN Seroquel (quetiapine IN =
    # 51272); tiền lệ dùng mã BN cho biệt dược: eliquis 1364436, tylenol 202433.
    # "Thuốc trước khi nhập viện lần này" -> isHistorical (tiền lệ GT[9]/GT[87]).
    # 3 triệu chứng dưới đây là lý do BN nghi thuốc, đang DIỄN RA ở lần nhập viện
    # này (GT[56] cùng bệnh án gán chúng ở mục triệu chứng hiện tại, không
    # assertion) -> KHÔNG isHistorical dù nằm trong mục tiền sử.
    ("lú lẫn", 0, SYM, [], []),
    ("chóng mặt", 0, SYM, [], []),
    ("khó nhìn gần", 0, SYM, [], []),
    # "(ngụ ý, ...)": nhận định của người ghi -> không gán.
]

GT[226] = [  # 213c ×1  8.txt — bài giảng Kawasaki: "Lưu ý quan trọng" (chẩn đoán phân biệt)
    ("Kawasaki", ALL, DX, [], ["M30.3"]),  # 2 lần, tiền lệ GT[104]
    # "dễ nhầm với X" = X đang được nghĩ tới để phân biệt, KHÔNG bị loại trừ ->
    # gán, không isNegated (tiền lệ GT[135] cùng nguồn: danh sách nguyên nhân nghi
    # ngờ vẫn gán hết; khác GT[195] nơi "sẽ không điển hình cho X" là loại trừ).
    ("sốt siêu vi", 0, DX, [], ["B34.9"]),  # tiền lệ "nhiễm virus" -> B34.9 ở GT[135]
    ("sốt phát ban", 0, DX, [], ["B09"]),  # nghĩa tiếng Việt phổ thông = sốt kèm ban
    # do virus -> B09 "Nhiễm virus không xác định, có biểu hiện tổn thương tại da".
    # KHÔNG dùng A75.9 dù tên mã trùng chữ ("Bệnh sốt phát ban" = typhus do
    # Rickettsia), sai hoàn toàn về bệnh học.
    ("nhiễm trùng", 0, DX, [], ["A49.9"]),  # tiền lệ "Nhiễm khuẩn" -> A49.9 ở GT[135]/GT[159]
    ("sốt cao", 0, SYM, [], []),  # "sốt cao 3–4 ngày" — cắt mốc thời gian khỏi bề mặt
    # (tiền lệ GT[140] cùng nguồn lấy "Sốt" cho "Sốt ≥5 ngày").
    ("đỏ mắt", 0, SYM, [], []),  # tiền lệ GT[104] cùng nguồn
    ("phát ban", 1, SYM, [], []),  # lần [0] nằm trong nhãn "sốt phát ban" ở trên
    ("môi đỏ", 0, SYM, [], []),  # tiền lệ GT[104] "môi đỏ – nứt"
    ("lưỡi đỏ", 0, SYM, [], []),  # tiền lệ GT[104] "lưỡi đỏ dâu tây"
    # "Các triệu chứng", "cần nghĩ đến", "đưa trẻ đi khám sớm": từ chỉ loại khái
    # niệm / lời khuyên -> không gán.
]

GT[276] = [  # 108c ×1  8.txt — bài giảng Kawasaki: tiêu chuẩn chẩn đoán 3–5 + tiêu đề
    ("Tổn thương đầu chi (phù, đỏ, bong da)", 0, SYM, [], []),  # cụm mô tả trong
    # ngoặc cùng dòng -> giữ TRỌN 1 bề mặt (tiền lệ GT[313]), không tách nhãn lồng.
    ("Ban đỏ toàn thân", 0, SYM, [], []),  # tiền lệ GT[307] cùng nguồn
    ("Hạch cổ to", 0, SYM, [], []),  # "Hạch cổ to ≥1,5 cm" — cắt kích thước khỏi bề
    # mặt theo cùng quy ước với "sốt cao 3–4 ngày" ở GT[226].
    # "Các xét nghiệm cần làm": tiêu đề mục -> không gán.
]

GT[304] = [  # 64c ×1  8.txt — bài giảng Kawasaki: tiêu chuẩn chẩn đoán 6 (hạch cổ)
    ("Sưng hạch cổ", 0, SYM, [], []),  # tiền lệ GT[104] "sưng hạch cổ"
    ("hạch >1,5 cm, chắc, không hóa mủ", 0, SYM, [], []),  # cụm mô tả đặc điểm hạch,
    # giữ trọn 1 bề mặt (tiền lệ GT[313] "Viêm kết mạc 2 bên, đỏ nhưng không có
    # ghèn"): "không hóa mủ" là mô tả BÊN TRONG bề mặt, KHÔNG tách isNegated riêng.
    # Chứa lần [1] của "hạch" nên không khai "hạch" riêng.
]

GT[321] = [  # 47c ×1  8.txt — bài giảng Kawasaki: tiêu chuẩn chẩn đoán 2 (môi–miệng)
    ("Môi – miệng thay đổi (nứt, đỏ, lưỡi dâu tây)", 0, SYM, [], []),  # giữ trọn cụm
    # kể cả ngoặc, cùng quy ước với GT[276]; do đó KHÔNG khai "lưỡi dâu tây" riêng
    # (tránh nhãn lồng nhau, tiền lệ ghi chú ở GT[140]).
]

# ---------------------------------------------------------------------------
# File 2.txt = bài giảng "Bệnh Kawasaki" (cùng nguồn với bài trong 8.txt, xem
# GT[140]) bị cắt thành 17 block, TRỪ block 195 bị ghép 3 dòng biện luận tâm
# thần của một EHR khác vào ĐẦU. Ba block dài nhất đã gán ở đợt trước
# (GT[104]/GT[124]/GT[135]); đợt này gán 14 block còn lại cho trọn file.
# Quy ước chốt cho cả file:
#  - Bài phổ biến kiến thức, không có bệnh nhân cụ thể -> KHÔNG assertion
#    (tiền lệ GT[104]/GT[124]/GT[135]/GT[140] cùng nguồn).
#  - Biến chứng/triệu chứng được liệt kê vẫn gán, KHÔNG isNegated, dù câu mở đầu
#    là "nếu không điều trị kịp thời có thể gây" (tiền lệ GT[124]/GT[140]).
#    Ngoại lệ: cụm "để ngừa X" trong phần điều trị -> isNegated theo GT[106].
#  - Tiêu đề mục ("3. Triệu chứng...", "4. Tổn thương ở đầu chi") chỉ gán phần
#    là tên khái niệm y khoa; số thứ tự và chữ "Triệu chứng điển hình" không gán.
#  - Dãy sao = tên thuốc bị mask, mỗi độ dài mask là 1 bề mặt riêng, candidates
#    rỗng (tiền lệ GT[104] cùng file đã gán "****" -> THUỐC).
#  - Liều/đường dùng/tỉ lệ hiệu quả không gán (tiền lệ GT[81]/GT[235]).
# ---------------------------------------------------------------------------

GT[195] = [  # 328c ×1  2.txt — 3 dòng biện luận tâm thần ghép vào + panel XN Kawasaki
    # Ba dòng đầu là biện luận CHẨN ĐOÁN PHÂN BIỆT của một EHR tâm thần khác
    # (cùng chủ đề với GT[56]: ảo giác + bệnh lý chất trắng nghi đa xơ cứng).
    # "Sẽ không điển hình cho Bệnh đa xơ cứng" -> bệnh bị LOẠI TRỪ -> isNegated
    # (tiền lệ GT[115] "âm tính với huyết khối tĩnh mạch sâu (DVT)" -> DX+NEG).
    ("Bệnh đa xơ cứng", 0, DX, [NEG], ["G35"]),
    # "Ảo giác do rượu (suy nghĩ)" = chẩn đoán đang được nghĩ tới -> gán, không NEG.
    # F10.5 = rối loạn tâm thần do rượu, loạn thần (bao ảo giác do rượu).
    ("Ảo giác do rượu", 0, DX, [], ["F10.5"]),
    # "Không được coi là thực sự loạn thần" -> loại trừ -> DX + isNegated.
    ("loạn thần", 0, DX, [NEG], ["F29"]),
    # --- phần còn lại: panel xét nghiệm chẩn đoán Kawasaki, toàn bộ LAB ---
    ("Công thức máu", 0, LAB, [], []),
    ("CRP", 0, LAB, [], []),  # tiền lệ GT[136] "Định lượng CRP"
    ("máu lắng", 0, LAB, [], []),
    ("Men gan", 0, LAB, [], []),  # ở đây là TÊN xét nghiệm được chỉ định, khác
    # tiền lệ GT[37]/GT[140] nơi "tăng men gan" là TRIỆU_CHỨNG.
    ("albumin", 0, LAB, [], []),  # tiền lệ GT[77] "Albumin"
    ("Xét nghiệm nước tiểu", 0, LAB, [], []),
    ("Cấy máu", 0, LAB, [], []),  # tiền lệ GT[63]/GT[102]/GT[78]
    ("dịch hầu họng", 0, LAB, [], []),  # "Cấy máu, dịch hầu họng" -> cấy dịch hầu họng
    ("Siêu âm tim", 0, LAB, [], []),  # tiền lệ GT[54]
    ("ECG điện tâm đồ", 0, LAB, [], []),  # giữ trọn cụm song ngữ (tiền lệ GT[136])
    # "(quan trọng nhất để đánh giá động mạch vành)": mục đích xét nghiệm, không
    # phải chẩn đoán -> không gán "động mạch vành" (giải phẫu đơn thuần).
]

GT[228] = [  # 208c ×1  2.txt — mục "7. Theo dõi trẻ sau điều trị"
    ("siêu âm tim", 0, LAB, [], []),
    # "động mạch vành" ở đây là bộ phận được siêu âm đánh giá -> không gán.
    # "Dùng thuốc đúng chỉ định": không nêu tên thuốc -> không gán (GT[235]
    # "điều trị nhiều thuốc").
    # SỬA (rà lại quyết định rủi ro): trước KHÔNG gán "vắc xin sống" với lý lẽ "vắc xin là
    # chế phẩm dự phòng, không phải thuốc điều trị". Nhưng GT[338]/GT[344] đã gán
    # ("vaccine phòng dại", DRUG, candidates rỗng) và GT[118] gán cả bản bị mask 17 sao.
    # Cùng là vắc xin mà chỗ gán chỗ không thì model học nhiễu -> gán cho nhất quán.
    # candidates để RỖNG: RxNorm không có ingredient chung cho "vắc xin sống" (đây là một
    # LỚP vắc xin, không phải chế phẩm cụ thể), đúng quy ước tên nhóm thuốc -> mã rỗng.
    ("vắc xin sống", 0, DRUG, [], []),
    ("****", 0, DRUG, [], []),  # mask 4 sao = IVIG, tiền lệ GT[104] cùng file
]

GT[239] = [  # 183c ×1  2.txt — mục điều trị số 1 (IVIG bị mask 21 sao)
    ("*********************", 0, DRUG, [], []),  # 21 sao
    # "Dùng liều cao truyền tĩnh mạch", "Hiệu quả 80% nếu truyền trước ngày thứ
    # 10": liều/đường dùng/tỉ lệ -> không gán.
    ("biến chứng động mạch vành", 0, DX, [], []),  # tiền lệ GT[104] "biến chứng
    # mạch vành" cũng để candidates rỗng (biến chứng vành của Kawasaki nằm trong
    # M30.3, ICD-10 không có mã riêng).
]

GT[258] = [  # 139c ×1  2.txt — tiêu chuẩn chẩn đoán 4: tổn thương đầu chi
    ("Tổn thương ở đầu chi", 0, SYM, [], []),
    ("Sưng, đỏ mu bàn tay – chân", 0, SYM, [], []),
    ("Đỏ gan bàn tay – chân", 0, SYM, [], []),
    ("Bong da đầu ngón tay, ngón chân", 0, SYM, [], []),
    # "vào ngày 7–14 của bệnh": mốc thời gian -> không gán.
]

GT[262] = [  # 133c ×1  2.txt — mục điều trị số 3 + tiêu đề mục 7
    ("****", 0, DRUG, [], []),  # mask 4 sao = IVIG lần 2
    ("thuốc ức chế miễn dịch", 0, DRUG, [], []),  # tên NHÓM thuốc, không có tên
    # cụ thể -> candidates rỗng (tiền lệ GT[159] "Kháng sinh", GT[106] "thuốc
    # chống đông").
    # "7. Theo dõi trẻ sau điều trị": tiêu đề mục -> không gán.
]

GT[265] = [  # 125c ×1  2.txt — tiêu đề mục 6
    ("bệnh Kawasaki", 0, DX, [], ["M30.3"]),
    # "bệnh viện có chuyên khoa tim mạch nhi": cơ sở/chuyên khoa -> không gán.
]

GT[270] = [  # 114c ×1  2.txt — tiêu đề mục 3 + điều kiện chẩn đoán
    ("bệnh Kawasaki", 0, DX, [], ["M30.3"]),
    # "Triệu chứng" (2 lần) và "Triệu chứng điển hình": từ chỉ loại khái niệm,
    # không phải một triệu chứng cụ thể -> không gán.
    ("sốt", 0, SYM, [], []),  # "kèm sốt ≥5 ngày"; bề mặt chỉ lấy tên triệu chứng
    # (tiền lệ GT[140] cùng nguồn: ("Sốt", 0, SYM) cho "Sốt ≥5 ngày").
]

GT[271] = [  # 114c ×1  2.txt — mục điều trị số 2 (aspirin bị mask 7 sao)
    ("*******", 0, DRUG, [], []),  # 7 sao = aspirin
    ("ASA", 0, DRUG, [], ["1191"]),  # viết tắt aspirin KHÔNG bị mask -> gán được
    # RxCUI 1191 (aspirin, IN). Mask và viết tắt là 2 bề mặt riêng.
    ("viêm", 0, SYM, [], []),  # "liều cao giai đoạn cấp tính để giảm viêm"
    ("huyết khối", 0, DX, [NEG], ["I24.0"]),  # "để ngừa huyết khối" -> chưa xảy
    # ra, đang phòng ngừa -> isNegated (tiền lệ GT[106] "để tránh ... chảy máu
    # khó cầm"). Bối cảnh mạch vành Kawasaki -> I24.0 như GT[232], không I82.9.
]

GT[284] = [  # 94c ×1  2.txt — câu tóm lại
    ("Kawasaki", 0, DX, [], ["M30.3"]),
    ("bệnh viêm mạch máu", 0, DX, [], ["I77.6"]),  # tiền lệ GT[124] "viêm lan tỏa
    # hệ mạch máu nhỏ và vừa" -> I77.6 (viêm động mạch, không xác định).
    # "biến chứng nặng": nói chung, không nêu biến chứng nào -> không gán.
]

GT[285] = [  # 93c ×1  2.txt — tiêu chuẩn chẩn đoán 1: sốt cao kéo dài
    ("Sốt cao kéo dài", 0, SYM, [], []),  # chứa lần [0] của "Sốt"
    ("Sốt 39–40°C", 0, SYM, [], []),  # chứa lần [1]; giữ cả trị số trong bề mặt
    # triệu chứng vì "39–40°C" là KHOẢNG mô tả, không phải kết quả xét nghiệm đo
    # được -> không tách KẾT_QUẢ_XÉT_NGHIỆM (khác GT[143] nơi "36.7°c" là sinh
    # hiệu đo tại giường).
    # "trong hơn 5 ngày": thời gian -> không gán.
    ("hạ sốt", 0, DRUG, [], []),  # "Ít đáp ứng với hạ sốt hoặc kháng sinh" -> ở
    # đây "hạ sốt" chỉ NHÓM THUỐC hạ sốt (tiền lệ GT[159] "Thuốc giảm đau, hạ
    # sốt"), chứa lần [2] của "sốt".
    ("kháng sinh", 0, DRUG, [], []),  # tiền lệ GT[159] "Kháng sinh"/GT[109]
]

GT[286] = [  # 93c ×1  2.txt — tiêu chuẩn chẩn đoán 3: thay đổi niêm mạc miệng
    ("Thay đổi niêm mạc miệng", 0, SYM, [], []),
    ("Môi đỏ, nứt", 0, SYM, [], []),
    ("rỉ máu", 0, SYM, [], []),  # "có thể rỉ máu"
    ("Lưỡi đỏ như dâu tây", 0, SYM, [], []),  # tiền lệ GT[104] "lưỡi đỏ dâu tây"
    ("Họng đỏ", 0, SYM, [], []),
]

GT[307] = [  # 61c ×1  2.txt — tiêu chuẩn chẩn đoán 5: ban đỏ toàn thân
    ("Ban đỏ toàn thân", 0, SYM, [], []),  # tiền lệ GT[104] "ban đỏ"
    ("Ban dạng đa hình: dát – sẩn – mảng đỏ", 0, SYM, [], []),
]

GT[313] = [  # 56c ×1  2.txt — tiêu chuẩn chẩn đoán 2: mắt đỏ
    ("Mắt đỏ", 0, SYM, [], []),
    ("Viêm kết mạc 2 bên, đỏ nhưng không có ghèn", 0, DX, [], ["H10.9"]),
    # tiền lệ GT[140] cùng nguồn: "Viêm kết mạc 2 bên không ghèn" -> DX H10.9.
    # "không có ghèn" là mô tả bên trong bề mặt, KHÔNG tách nhãn NEG riêng.
]

GT[329] = [  # 23c ×1  2.txt — tiêu đề mục 1
    ("Bệnh Kawasaki", 0, DX, [], ["M30.3"]),
]

# ---------------------------------------------------------------------------
# File 87.txt = MỘT bệnh án viết tay (BN nam 74t đau ngực -> đau thắt ngực không
# ổn định) bị cắt thành 5 block, TRỪ block 176 là mẩu bệnh án béo phì khác ghép
# vào. Trước đợt này chưa gán block nào -> gán trọn 5 block.
# Thứ tự đọc đúng của bệnh án: 162 (hỏi bệnh + khám) -> 158 (phiếu chỉ định XN)
# -> 288 (chẩn đoán + đầu mục thuốc) -> 297 (dòng thuốc bị mask).
# Quy ước chốt cho cả file:
#  - Bệnh án của chính bệnh nhân, đang diễn ra -> không isHistorical, trừ mục
#    "TS" (tiền sử) — nhưng ở đây TS ghi "khỏe mạnh" nên không có gì để gán.
#  - Khám bình thường không gán ("Bn tỉnh", "Da niêm mạc hồng" thì CÓ tiền lệ gán
#    ở GT[91]/GT[131] nên vẫn gán để nhất quán, xem chú thích từng dòng).
#  - Dòng "Không X" -> gán X + isNegated (tiền lệ GT[91]/GT[129]).
#  - Dãy sao = tên thuốc bị mask, gán THUỐC theo đúng bề mặt, candidates rỗng
#    (tiền lệ GT[24]/GT[51]/GT[76]/GT[100]).
# ---------------------------------------------------------------------------

GT[162] = [  # 439c ×1  87.txt — hỏi bệnh + khám lúc vào
    ("đau ngực", 0, SYM, [], []),  # "vào viện vì lí do đau ngực"
    # "TS; khỏe mạnh": tiền sử bình thường -> không gán (tiền lệ GT[68] "tai trái
    # khỏe mạnh" là mô tả chức năng bình thường).
    ("đau ngực T âm ỉ", 0, SYM, [], []),  # bệnh sử 2 tháng; chứa lần [1] của "đau ngực"
    ("đau không lan", 0, SYM, [], []),
    ("tình trạng đau ngực tăng lên", 0, SYM, [], []),  # chứa lần [2] của "đau ngực"
    ("đau \ntăng khi gắng sức", 0, SYM, [], []),  # bị ngắt dòng giữa cụm
    # --- "Khám lúc vào" ---
    # "Bn tỉnh": tri giác BÌNH THƯỜNG -> không gán, theo tiền lệ GT[141] đã quyết
    # định không gán "Bệnh nhân tỉnh, tiếp xúc tốt" (khác các dòng khám khác bên
    # dưới đều có tiền lệ gán ở GT[91]/GT[100]/GT[131]).
    ("Đau ngực T âm ỉ", 1, SYM, [], []),  # khám lặp lại triệu chứng (chứa "đau ngực"[3])
    ("đau không lan", 1, SYM, [], []),
    ("khó thở", 0, SYM, [NEG], []),  # "không khó thở"
    ("Da niêm mạc hồng", 0, SYM, [], []),  # tiền lệ GT[91]/GT[131]
    ("phù", 0, SYM, [NEG], []),  # "KHông phù"
    ("xuất huyết", 0, SYM, [NEG], []),  # "không xuất huyết"
    ("Tim nhịp đều", 0, SYM, [], []),  # tiền lệ GT[91] "Tim đều TTT ở mỏm 3/6"
    ("Phổi RRPN thô", 0, SYM, [], []),  # tiền lệ GT[91] "Phổi RRPN rõ", GT[100] "RRPN giảm 2 phế trường"
    ("Bụng mềm", 0, SYM, [], []),  # tiền lệ GT[91]/GT[100] "Bụng mềm không chướng"
    ("Tiểu được", 0, SYM, [], []),  # chức năng bài niệu ghi trong khám -> giữ cho nhất quán với các dòng khám khác
    ("HA", 0, LAB, [], []),  # tiền lệ GT[93]/GT[137]
    ("110/ 70 mmHg", 0, VAL, [], []),
    ("M", 12, LAB, [], []),  # nhãn mạch viết tắt "M: 70 l/p"; [0..11] là chữ m thường
    # trong thân văn bản (matcher không phân biệt hoa/thường) — tiền lệ GT[91] ("M", 15).
    ("70 l/p", 0, VAL, [], []),
    # "Cận lâm sàng :": tiêu đề mục -> không gán.
]

GT[158] = [  # 444c ×1  87.txt — phiếu chỉ định xét nghiệm/siêu âm/thủ thuật
    # Gần trùng phiếu XN trong block 62 (GT[62]) nhưng ngắt dòng khác và có thêm
    # Glucose + siêu âm tim + điện tim -> phải đo lại bề mặt, không copy nguyên.
    ("Thời gian prothrombin (PT: Prothrombin Time), \n(Các tên khác: TQ; Tỷ lệ Prothrombin)", 0, LAB, [], []),
    # -> giữ trọn cụm gồm cả các tên khác trong ngoặc, tiền lệ GT[136]
    # ("Thời gian Prothrombin (PT / TQ / Tỷ lệ Prothrombin)").
    ("Định lượng Troponin Ths", 0, LAB, [], []),  # tiền lệ GT[62]
    ("Đo hoạt độ AST \n(GOT)", 0, LAB, [], []),  # tiền lệ GT[62]/GT[136], ở đây bị ngắt dòng
    ("Đo hoạt độ ALT (GPT)", 0, LAB, [], []),
    ("Định lượng \nCreatinin (máu)", 0, LAB, [], []),
    ("Điện giải đồ", 0, LAB, [], []),  # tiền lệ GT[62]; "(Na, K, Cl)" là thành phần -> không gán riêng
    ("Định \nlượng Glucose", 0, LAB, [], []),
    ("Định lượng NT - proBNP ( \nProBNP)", 0, LAB, [], []),  # tiền lệ GT[62], bao cả 2 lần "proBNP"
    ("Tổng phân tích tế bào máu ngoại vi", 0, LAB, [], []),  # tiền lệ GT[62]/GT[136]
    ("Siêu âm Doppler tim, van tim", 0, LAB, [], []),  # tiền lệ GT[92]
    ("Ghi điện tim cấp cứu tại giường", 0, LAB, [], []),  # tiền lệ GT[89]
]

GT[288] = [  # 93c ×1  87.txt — chẩn đoán ra viện + đầu mục thuốc
    ("Cơn đau thắt ngực không ổn định", 0, DX, [], ["I20.0"]),  # trùng nguyên văn tên mã I20.0
    ("bệnh tăng HA vô căn(nguyên phát)", 0, DX, [], ["I10"]),  # trùng tên mã I10 (thiếu dấu cách
    # trước ngoặc do lỗi gõ) -> giữ nguyên bề mặt as-written; nhãn này bao trọn "HA"
    # nên không gán "HA" riêng (tiền lệ GT[93] với "tăng HA").
    # "Thuốc điều trị :": tiêu đề mục -> không gán.
]

GT[297] = [  # 74c ×1  87.txt — dòng thuốc bị mask
    ("*****************************", 0, DRUG, [], []),  # 29 sao = 1 tên thuốc bị mask
    # "x 1,0 Viên", "Ngày uống 1 viên buổi sáng sau ăn": liều/đường dùng, không có
    # tên thuốc -> không gán (tiền lệ GT[81]/GT[235]).
]

GT[176] = [  # 403c ×1  87.txt — MẨU BỆNH ÁN LẠ ghép vào: "2. Tiền sử bệnh hiện tại" ca béo phì
    # Cùng nguồn với đoạn đầu block 51 (GT[51]) — ở đó chỉ gán "giảm cân" (SYM);
    # giữ nguyên cách đó để không tự mâu thuẫn.
    # "Tiền sử bệnh hiện tại" = HPI -> không isHistorical (tiền lệ GT[129]/GT[139]).
    # "Lý do nhập viện: đến khám vì sau cân sau phẫu thuật": bản dịch lỗi
    # ("sụt cân sau phẫu thuật"?), không đoán được khái niệm -> không gán.
    # --- "Các sự kiện trước khi nhập viện" -> đã qua -> isHistorical (tiền lệ GT[129]) ---
    ("giảm cân", 0, SYM, [HIST], []),  # tiền lệ GT[51] cùng câu, cùng loại
    ("tăng cân trở lại", ALL, SYM, [HIST], []),  # 2 lần, cùng một sự kiện lặp lại
    # "chế độ ăn kiêng có giám sát": can thiệp/thủ thuật -> không gán.
    ("giảm cân tối đa 60 pound", 0, SYM, [HIST], []),  # chứa lần [1] của "giảm cân";
    # "60 pound" là mức thay đổi cân nặng bệnh nhân tự kể, không phải xét nghiệm
    # chỉ định -> không tách thành KẾT_QUẢ_XÉT_NGHIỆM (tiền lệ GT[2] "tăng 10kg").
    # --- đuôi: dòng kê thuốc của một EHR khác ---
    ("***********************", 0, DRUG, [], []),  # 23 sao
    ("**************", 0, DRUG, [], []),  # 14 sao — mask thứ 2, độ dài khác -> nhãn riêng
    # "x 2,0 Viên", "Ngày uống 1/2 viên ...": liều/đường dùng -> không gán.
]

# ---------------------------------------------------------------------------
# File 26.txt = bài giảng "BỆNH MẠCH VÀNH (CAD)" bị cắt thành 13 block, TRỪ 2 block
# (182, 172) bị ghép một mẩu bệnh án lạ (viêm tụy + rung nhĩ) vào giữa. Trước đó
# chưa gán block nào -> gán trọn 13 block một lượt cho nhất quán.
# Quy ước chốt cho cả file:
#  - Phần bài giảng: KHÔNG assertion (tiền lệ GT[104]/GT[124]/GT[135]/1.txt).
#  - Phần bệnh án ghép (block 182 dưới "1. Tiền sử bệnh" + "Thuốc trước khi nhập
#    viện") -> toàn bộ isHistorical (tiền lệ GT[9]/GT[14]/GT[20]/GT[198]).
#    Riêng "2. Tiền sử bệnh hiện tại" (block 172) KHÔNG isHistorical
#    (tiền lệ GT[129]/GT[139]), chỉ dòng ghi "(lần nhập viện trước)" mới có.
#  - Tiêu đề mục ("Nguyên nhân chính", "Yếu tố nguy cơ", "Triệu chứng lâm sàng",
#    "Các thể lâm sàng", "Lâm sàng", "4. Chẩn đoán", "Dự phòng thứ phát"):
#    không gán (tiền lệ tiêu đề nhóm ở GT[136]/GT[140]).
#  - Bước CƠ CHẾ bệnh sinh ("Lắng đọng lipid", "hình thành/to dần/nứt vỡ mảng xơ
#    vữa"): mô tả cơ chế -> không gán (quy ước chốt ở file 1.txt). Nhưng các
#    TRẠNG THÁI bệnh lý trong chuỗi đó ("hẹp lòng mạch", "huyết khối", "tắc mạch
#    cấp") vẫn là khái niệm chẩn đoán -> gán.
#  - Đặc điểm cơn đau (vị trí, tính chất, hướng lan) gán TRIỆU_CHỨNG
#    (tiền lệ GT[73] gán "nhói", "lan xuống cánh tay trái"); còn thời gian
#    ("vài phút") và đáp ứng ("Giảm khi nghỉ", "Không đỡ khi nghỉ", "Xảy ra khi
#    gắng sức") thì không gán (tiền lệ GT[73] không gán "không giảm khi dùng
#    bất kỳ thuốc nào").
#  - Trong danh sách yếu tố nguy cơ / lời khuyên dự phòng: gán tên BỆNH, tên
#    XÉT NGHIỆM, tên THUỐC; bỏ hành vi/lối sống ("Tuổi cao", "Nam giới",
#    "ít vận động", "Tập thể dục", "Giữ cân nặng hợp lý", "Uống thuốc đều",
#    "Tái khám định kỳ") — tiền lệ GT[104]/GT[117]/GT[135].
#    Ngoại lệ có tiền lệ rõ: "hút thuốc lá" đã được gán TRIỆU_CHỨNG ở GT[28]
#    -> ở đây cũng gán (khác "hút thuốc lá thụ động" của GT[104] là yếu tố môi
#    trường), và "stress" đã được gán CHẨN_ĐOÁN F43.9 ở GT[85].
# ---------------------------------------------------------------------------

GT[299] = [  # 72c ×1  26.txt — tiêu đề bài + tiêu đề mục 1
    ("BỆNH MẠCH VÀNH", 0, DX, [], ["I25.9"]),  # tiền lệ GT[55] "bệnh mạch vành" -> I25.9
    # "(Coronary Artery Disease – CAD)": tên tiếng Anh trong ngoặc ngay sau nhãn
    # -> phần diễn giải, không gán riêng (tiền lệ GT[207] với "(Glucose-6-...)").
    ("Bệnh mạch vành", 1, DX, [], ["I25.9"]),  # lần [0] là tiêu đề chữ hoa (matcher không phân biệt hoa/thường)
]

GT[197] = [  # 321c ×1  26.txt — định nghĩa bệnh + hậu quả
    ("Bệnh mạch vành", 0, DX, [], ["I25.9"]),
    ("hẹp hoặc tắc các động mạch vành", 0, DX, [], ["I25.1"]),  # tiền lệ GT[124]/GT[140] "hẹp tắc mạch vành" -> I25.1
    # nhãn trên đã chứa lần [0] (duy nhất) của "động mạch vành" -> không khai riêng.
    ("xơ vữa động mạch", 0, DX, [], ["I70.9"]),  # xơ vữa động mạch không xác định
    ("giảm tưới máu cơ tim", 0, DX, [], ["I25.9"]),  # = thiếu máu cơ tim, tiền lệ GT[140]
    ("thiếu oxy cơ tim", 0, DX, [], ["I25.9"]),  # thiếu máu/thiếu oxy cơ tim -> cùng mã
    ("đau thắt ngực", 0, DX, [], ["I20.9"]),  # tiền lệ GT[55]
    ("nhồi máu cơ tim", 0, DX, [], ["I21.9"]),  # tiền lệ GT[124]/GT[140]
    ("suy tim", 0, DX, [], ["I50.9"]),  # tiền lệ GT[124]
    ("đột tử", 0, DX, [], ["I46.1"]),  # tiền lệ GT[124] (đột tử do tim)
]

GT[232] = [  # 195c ×1  26.txt — chuỗi cơ chế xơ vữa mạch vành
    ("Xơ vữa động mạch vành", 0, DX, [], ["I25.1"]),
    ("LDL-cholesterol", 0, LAB, [], []),  # tiền lệ GT[98] "LDL - cholesterol"
    # "tăng" đứng một mình: kết quả bằng chữ, không có trị số -> không gán VAL
    # (tiền lệ 8/8 KẾT_QUẢ_XÉT_NGHIỆM đều là số + đơn vị, xem GT[29]).
    # "Lắng đọng lipid", "mảng xơ vữa" (3 lần): bước cơ chế -> không gán.
    ("hẹp lòng mạch", 0, DX, [], ["I25.1"]),
    ("huyết khối", 0, DX, [], ["I24.0"]),  # bối cảnh mạch vành -> "huyết khối mạch vành
    # không gây NMCT"; KHÁC tiền lệ GT[52]/GT[134] dùng I82.9 vì ở đó là huyết khối
    # tĩnh mạch (I82.9 ghi rõ "không xác định tĩnh mạch") — xem worklog/07.
    ("tắc mạch cấp", 0, DX, [], ["I74.9"]),  # tắc/thuyên tắc động mạch không xác định
]

GT[291] = [  # 82c ×1  26.txt — yếu tố nguy cơ KHÔNG thay đổi được
    # "Tuổi cao", "Nam giới": yếu tố dịch tễ/nhân khẩu -> không gán (tiền lệ
    # "Yếu tố chủng tộc"/"Trẻ gốc Á" ở GT[135]).
    # "Tiền sử gia đình ...": chỉ lấy TÊN BỆNH làm bề mặt (tiền lệ GT[14] lấy
    # "u ác của tuyến tiền liệt" trong cụm mô tả phẫu thuật).
    # Bài giảng không có bệnh nhân cụ thể nên KHÔNG gán isFamily (không có
    # "thân nhân của ai") — theo quy ước không assertion cho bài giảng.
    ("bệnh tim mạch sớm", 0, DX, [], ["I51.6"]),
]

GT[233] = [  # 195c ×1  26.txt — yếu tố nguy cơ CÓ THỂ thay đổi + tiêu đề triệu chứng
    ("Hút thuốc lá", 0, SYM, [], []),  # tiền lệ GT[28] cùng bề mặt, cùng loại
    ("Tăng huyết áp", 0, DX, [], ["I10"]),
    ("Đái tháo đường", 0, DX, [], ["E14"]),  # tiền lệ GT[14]/GT[20]: không rõ typ -> E14
    ("Rối loạn lipid máu", 0, DX, [], ["E78.5"]),  # tiền lệ GT[26] (E78.5); GT[116] từng
    # dùng E78.9 cho cùng bề mặt -> chốt E78.5 (tăng lipid máu) làm chuẩn, ghi worklog.
    ("Béo phì", 0, DX, [], ["E66.9"]),  # tiền lệ GT[4] (béo phì trong danh sách nguy cơ chung)
    # "ít vận động": lối sống -> không gán.
    ("Stress kéo dài", 0, DX, [], ["F43.9"]),  # tiền lệ GT[85] "stress" -> F43.9
    ("Đau thắt ngực", 0, DX, [], ["I20.9"]),  # tiêu đề mục nhưng là tên bệnh -> gán (tiền lệ GT[140])
]

GT[240] = [  # 182c ×1  26.txt — đặc điểm cơn đau thắt ngực điển hình
    ("sau xương ức", 0, SYM, [], []),  # vị trí đau (tiền lệ GT[73] gán mô tả cơn đau)
    ("đè nặng, bóp nghẹt, thắt chặt", 0, SYM, [], []),  # cả cụm là một trường "Tính chất"
    # (tiền lệ GT[78] "đau hạ sườn phải tái phát, ngày càng nặng hơn" gán 1 nhãn).
    ("vai trái – cánh tay trái – cổ – hàm dưới", 0, SYM, [], []),  # hướng lan
    # "Thời gian: vài phút", "Giảm khi nghỉ": thời gian/đáp ứng -> không gán.
    ("nitroglycerin", 0, DRUG, [], ["4917"]),  # tiền lệ GT[55]
]

GT[308] = [  # 61c ×1  26.txt — thể đau thắt ngực ổn định
    ("Đau thắt ngực ổn định", 0, DX, [], ["I20.8"]),  # tiền lệ GT[125] cùng bề mặt -> I20.8
    # "Xảy ra khi gắng sức", "Giảm khi nghỉ": đáp ứng -> không gán.
]

GT[249] = [  # 156c ×1  26.txt — hội chứng vành cấp và các thể
    ("Hội chứng vành cấp", 0, DX, [], ["I24.9"]),  # bệnh tim thiếu máu cục bộ cấp, không xác định
    ("Đau dữ dội, kéo dài", 0, SYM, [], []),
    # "Không đỡ khi nghỉ", "Gồm:": đáp ứng/từ nối -> không gán.
    ("Nhồi máu cơ tim ST chênh", 0, DX, [], ["I21.3"]),  # STEMI = NMCT xuyên thành cấp
    ("Nhồi máu không ST chênh", 0, DX, [], ["I21.4"]),  # NSTEMI = NMCT dưới nội tâm mạc
    ("Đau thắt ngực không ổn định", 0, DX, [], ["I20.0"]),
    # 2 nhãn NMCT ở trên đã chứa cả 2 lần "Nhồi máu ..." -> không khai riêng.
]

GT[268] = [  # 121c ×1  26.txt — triệu chứng không điển hình + tiêu đề mục 4
    # "Triệu chứng không điển hình", "hay gặp ở nữ, người già": nhóm dân số -> không gán.
    ("ĐTĐ", 0, DX, [], ["E14"]),  # viết tắt của đái tháo đường, vẫn là tên bệnh
    ("Khó thở", 0, SYM, [], []),
    ("Mệt", 0, SYM, [], []),
    ("Buồn nôn", 0, SYM, [], []),
    ("Đau thượng vị", 0, SYM, [], []),
]

GT[322] = [  # 47c ×1  26.txt — chẩn đoán lâm sàng
    ("đau ngực", 0, SYM, [], []),  # "Khai thác đau ngực"
    # "yếu tố nguy cơ": nhắc chung, không có tên -> không gán.
]

GT[182] = [  # 380c ×1  26.txt — MẨU BỆNH ÁN LẠ ghép vào: "1. Tiền sử bệnh"
    # Cả block nằm dưới "1. Tiền sử bệnh" + "Bệnh lý mãn tính" + "Thuốc trước khi
    # nhập viện" -> toàn bộ isHistorical (tiền lệ GT[9]/GT[14]/GT[20]/GT[198]).
    ("viêm tụy", 0, DX, [HIST], ["K85"]),  # "nhập viện gần đây vìviêm tụy" (dịch dính chữ);
    # nhập viện cấp -> viêm tụy cấp K85 (không phải K86.1 mạn).
    ("rung nhĩ", ALL, DX, [HIST], ["I48.9"]),  # 2 lần: dòng bệnh mạn + "(cho rung nhĩ)"
    # "phẫu thuật cắt bỏ tuyến tiền liệt" (2 lần): thủ thuật -> không gán, chỉ lấy
    # chẩn đoán trong ngoặc (tiền lệ GT[14]/GT[145]).
    ("u ác của tuyến tiền liệt", ALL, DX, [HIST], ["C61"]),  # 2 lần, tiền lệ GT[14]
    ("rối loạn cảm xúc lưỡng cực khác", 0, DX, [HIST], ["F31.8"]),  # trùng nguyên văn tên mã F31.8
    ("eliquis", 0, DRUG, [HIST], ["1364436"]),  # RxNorm BN Eliquis (apixaban IN = 1364430);
    # tiền lệ dùng mã BN cho biệt dược: tylenol 202433, klonopin 202585, bactrim 151399.
]

GT[172] = [  # 416c ×1  26.txt — "2. Tiền sử bệnh hiện tại" của bệnh án lạ, rồi bài giảng nối lại
    # "Tiền sử bệnh hiện tại" = HPI -> KHÔNG isHistorical (tiền lệ GT[129]/GT[139]).
    ("sốt", 0, SYM, [], []),  # "Lý do nhập viện: sốt và đau bụng"
    ("đau bụng", 0, SYM, [], []),
    ("đau bụng trên", 0, SYM, [HIST], []),  # dòng ghi "(lần nhập viện trước)" -> isHistorical
    # (tiền lệ GT[110]); nhãn này chứa lần [1] của "đau bụng".
    ("sốt nhẹ đến 38.3°C", 0, SYM, [], []),  # tiền lệ GT[78] cùng bề mặt (ở đó 2 lần)
    ("đau hạ sườn phải tái phát, ngày càng nặng hơn", 0, SYM, [], []),  # tiền lệ GT[78]
    # --- từ "Tập thể dục" trở đi là bài giảng CAD nối lại (mục dự phòng tiên phát) ---
    # "Tập thể dục ≥ 150 phút/tuần", "Giữ cân nặng hợp lý": lối sống -> không gán.
    ("hút thuốc", 0, SYM, [NEG], []),  # "Không hút thuốc" -> isNegated (tiền lệ GT[106]
    # gán isNegated cho khái niệm nêu ra để PHÒNG trong bài giảng).
    ("stress", 0, DX, [], ["F43.9"]),  # "Giảm stress" — tiền lệ GT[85]
    ("HA", 0, LAB, [], []),  # tiền lệ GT[93]/GT[137] "HA" = huyết áp
    ("đường huyết", 0, LAB, [], []),  # tiền lệ GT[103]
    ("lipid", 0, LAB, [], []),  # bộ mỡ máu, tiền lệ GT[98] "LDL - cholesterol"
]

GT[277] = [  # 107c ×1  26.txt — dự phòng thứ phát
    # "Uống thuốc đều": chỉ có đường dùng, không có tên thuốc -> không gán
    # (tiền lệ GT[81] "Uống thuốc", GT[235] "điều trị nhiều thuốc" đều không gán).
    # "Tái khám định kỳ": lời khuyên -> không gán.
    ("LDL", 0, LAB, [], []),
    # SỬA (rà lại quyết định rủi ro): BỎ 2 nhãn ("1,8 mmol/L", VAL) và ("70 mg/dL", VAL).
    # Văn bản là "Kiểm soát LDL < 1,8 mmol/L (hoặc <70 mg/dL)" trong mục dặn dò ra viện —
    # đây là NGƯỠNG MỤC TIÊU điều trị, không phải kết quả đo của bệnh nhân. Đếm lại toàn
    # bộ 194 nhãn KẾT_QUẢ_XÉT_NGHIỆM trong GT: 193 cái là trị số đo thật ("130/76 mmHg",
    # "6,7 mmol/l"...), chỉ 2 cái này là ngưỡng. Giữ chúng là dạy model một luật mà chính
    # nó chỉ thấy 2 ví dụ -> nhiễu, và mỗi nhãn thừa còn kéo điểm 3 metric xuống 0 theo
    # "Lưu ý" của đề. Nhãn LAB "LDL" ở trên GIỮ: tên xét nghiệm thì vẫn là tên xét nghiệm.
    ("đau ngực", 0, SYM, [], []),
]

# ---------------------------------------------------------------------------
# File 1.txt = MỘT bài phổ biến kiến thức "THIẾU MEN G6PD là gì?" bị cắt thành
# 17 block, trước đó chưa gán block nào. Gán cả 17 trong một lượt để quyết định
# nhất quán (tránh cùng một câu ở hai block lại gán khác nhau).
# Quy ước chung cho cả file:
#  - Bài giảng, không có bệnh nhân cụ thể -> KHÔNG assertion nào
#    (tiền lệ GT[76]/GT[104]/GT[124]/GT[135]).
#  - "thiếu men G6PD" (mọi biến thể chữ hoa/thường) -> CHẨN_ĐOÁN, D55.0
#    ("Thiếu máu do thiếu men glucose-6-phosphate dehydrogenase [G6PD]").
#  - "hồng cầu bị phá hủy", "tác nhân oxy hóa", "đậu tằm", "enzyme", "gen":
#    cơ chế/tác nhân, không phải khái niệm bệnh -> không gán (tiền lệ GT[66]
#    không gán "vi rút dại" trong bài giảng).
#  - "hiến máu", "lấy máu khô ở gót chân": thủ thuật -> không gán.
# ---------------------------------------------------------------------------

GT[317] = [  # 53c ×1  1.txt — tiêu đề bài + tiêu đề mục 1
    ("THIẾU MEN G6PD", 0, DX, [], ["D55.0"]),
    ("Thiếu men G6PD", 1, DX, [], ["D55.0"]),  # lần [0] nằm trong tiêu đề chữ hoa
]

GT[207] = [  # 287c ×1  1.txt — định nghĩa bệnh
    ("Thiếu men G6PD", 0, DX, [], ["D55.0"]),
    # "(Glucose-6-Phosphate Dehydrogenase)" là tên đầy đủ của men, đứng trong
    # ngoặc ngay sau nhãn -> đã nằm trong phần diễn giải, không gán riêng.
    ("bệnh di truyền lặn liên kết với nhiễm sắc thể X", 0, DX, [], ["D55.0"]),
    # "gen lặn bất thường", "nhiễm sắc thể giới tính": cơ chế di truyền -> không gán.
    # "bé trai có nguy cơ mắc bệnh cao hơn bé gái": dịch tễ -> không gán.
]

GT[173] = [  # 411c ×1  1.txt — nguyên nhân ở mức gen
    ("đột biến gen G6PD tại vị trí Xq28", 0, DX, [], []),  # ICD-10 không có mã cho đột biến gen cụ thể
    ("thiếu hụt men G6PD", 0, DX, [], ["D55.0"]),
    # "hơn 140 loại đột biến": số liệu -> không gán.
    # "rối loạn quá trình chuyển hóa và bảo vệ hồng cầu": mô tả cơ chế -> không gán.
]

GT[212] = [  # 276c ×1  1.txt — vai trò của men + tiêu đề mục 2
    # "Khi thiếu men này": nhắc lại bệnh nhưng không nêu tên -> không gán
    # (tiền lệ "các xét nghiệm này" không gán).
    ("thiếu men G6PD", 0, DX, [], ["D55.0"]),  # trong tiêu đề mục 2
]

GT[205] = [  # 292c ×1  1.txt — sàng lọc sơ sinh
    ("xét nghiệm thiếu men G6PD", 0, LAB, [], []),  # tên xét nghiệm (chứa lần [0] của "thiếu men G6PD")
    ("thiếu men G6PD", 1, DX, [], ["D55.0"]),  # "kết quả nghi ngờ thiếu men G6PD"
    # "sàng lọc sớm các bệnh bẩm sinh", "các xét nghiệm chuyên sâu": nhắc chung
    # không có tên -> không gán (tiền lệ "một xét nghiệm nào").
]

GT[200] = [  # 310c ×1  1.txt — dấu hiệu khởi phát
    ("thiếu men G6PD", ALL, DX, [], ["D55.0"]),  # 2 lần
    # "ăn đậu tằm", "thuốc, thực phẩm chứa chất oxy hóa": yếu tố khởi phát
    # -> không gán (tiền lệ yếu tố nguy cơ ở GT[104]/GT[135]).
    ("Sốt cao", 0, SYM, [], []),
]

GT[298] = [  # 72c ×1  1.txt — 2 gạch đầu dòng bị chèn tiêu đề "3. Đánh giá tại bệnh viện" của bệnh án khác
    ("Tim đập nhanh", 0, SYM, [], []),
    ("khó thở", 0, SYM, [], []),
    ("Vàng da", 0, SYM, [], []),
    ("vàng mắt", 0, SYM, [], []),
]

GT[196] = [  # 326c ×1  1.txt — kết quả xét nghiệm và biến chứng
    ("xét nghiệm máu", 0, LAB, [], []),  # tiền lệ GT[136]
    ("thiếu máu do tan huyết", 0, DX, [], ["D55.0"]),  # tan máu do thiếu G6PD (chứa lần [0] "thiếu máu")
    ("thiếu máu", 1, DX, [], ["D64.9"]),  # tiền lệ GT[58]/GT[91] "thiếu máu" -> D64.9
    ("vàng da vàng mắt", 0, SYM, [], []),  # chứa lần [0] của "vàng da"
    ("suy thận cấp", 0, DX, [], ["N17.9"]),
    ("vàng da", 1, SYM, [], []),  # "trẻ sơ sinh bị vàng da nặng"
    ("tổn thương thần kinh", 0, DX, [], []),  # mô tả chung, không có mã ICD-10 riêng
    ("bại não", 0, DX, [], ["G80.9"]),
    ("chậm phát triển trí tuệ và vận động", 0, DX, [], ["F79"]),
]

GT[214] = [  # 268c ×1  1.txt — mức độ nhẹ/nặng + tiêu đề mục 3
    ("tan huyết", 0, SYM, [], []),  # "các yếu tố gây tan huyết" — hiện tượng tan máu
    ("thiếu máu", 0, DX, [], ["D64.9"]),
    # "các triệu chứng rõ ràng và nặng": nhắc chung -> không gán.
    ("Thiếu men G6PD", 0, DX, [], ["D55.0"]),  # tiêu đề mục 3
]

GT[244] = [  # 172c ×1  1.txt — nhắc lại vai trò của men
    # "Khi thiếu men này": không nêu tên bệnh -> không gán (như GT[212]).
    ("thiếu máu tan huyết", 0, DX, [], ["D55.0"]),
]

GT[251] = [  # 150c ×1  1.txt — biến chứng của vàng da nặng
    ("vàng da nặng", 0, SYM, [], []),
    ("thiếu men G6PD", 0, DX, [], ["D55.0"]),
    ("Bại não", 0, DX, [], ["G80.9"]),
    ("Chậm phát triển trí tuệ", 0, DX, [], ["F79"]),
    ("Rối loạn vận động", 0, DX, [], ["G25.9"]),
]

GT[174] = [  # 407c ×1  1.txt — hậu quả nếu không điều trị
    ("thiếu máu tan huyết", 0, DX, [], ["D55.0"]),  # chứa lần [0] của "tan huyết"
    ("vàng da sơ sinh", 0, SYM, [], []),
    ("thiếu men G6PD", 0, DX, [], ["D55.0"]),
    ("tan huyết", 1, SYM, [], []),  # "các tác nhân gây tan huyết"
    # "đậu tằm, thuốc và thực phẩm có tính oxy hóa cao": tác nhân -> không gán.
]

GT[234] = [  # 194c ×1  1.txt — trấn an
    ("thiếu men G6PD", 0, DX, [], ["D55.0"]),
    # "sống và phát triển hoàn toàn bình thường": mô tả bình thường -> không gán.
]

GT[328] = [  # 40c ×1  1.txt — tiêu đề mục 4
    ("thiếu men G6PD", 0, DX, [], ["D55.0"]),
]

GT[159] = [  # 441c ×1  1.txt — danh sách yếu tố cần tránh (5 nhóm thuốc bị mask)
    ("thiếu men G6PD", 0, DX, [], ["D55.0"]),
    ("Nhiễm khuẩn", 0, DX, [], ["A49.9"]),  # tiền lệ GT[135] cùng bề mặt/mã
    ("nhiễm virus", 0, DX, [], ["B34.9"]),  # tiền lệ GT[135]
    # 3 dòng thuốc: tên nhóm gán THUỐC (tiền lệ "kháng sinh", "thuốc giảm đau"),
    # còn phần bị che sao gán riêng từng run (mỗi độ rộng mask là một bề mặt).
    ("Thuốc giảm đau, hạ sốt", 0, DRUG, [], []),
    ("*******", 0, DRUG, [], []),
    ("**********", 0, DRUG, [], []),
    ("Kháng sinh", 0, DRUG, [], []),
    ("***********", 0, DRUG, [], []),
    ("********", 0, DRUG, [], []),
    ("Thuốc kháng sốt rét", 0, DRUG, [], []),
    ("*******", 1, DRUG, [], []),
    ("***********", 1, DRUG, [], []),
    ("**********", 1, DRUG, [], []),
    ("Vitamin K", 0, DRUG, [], ["11258"]),  # RxNorm IN 11258 = vitamin K
    ("nhiễm khuẩn tiết niệu", 0, DX, [], ["N39.0"]),  # chứa lần [1] của "Nhiễm khuẩn"
    # "Thực phẩm chế biến từ đậu tằm": thực phẩm -> không gán.
    # "băng phiến, long não": hóa chất gây tan máu, không phải thuốc điều trị
    # -> không gán (tiền lệ yếu tố môi trường ở GT[104]).
    # "Không nên hiến máu": thủ thuật/lời khuyên -> không gán.
]

GT[150] = [  # 472c ×1  1.txt — dặn dò cha mẹ + tiêu đề "Phòng ngừa"
    ("tan huyết", 0, SYM, [], []),
    ("thiếu men G6PD", ALL, DX, [], ["D55.0"]),  # 2 lần: dòng dặn dò + tiêu đề "Phòng ngừa"
    # "long não, băng phiến": hóa chất -> không gán (như GT[159]).
    # "thuốc nam, thuốc đông y": nhắc chung, không có tên thuốc -> không gán
    # (tiền lệ "điều trị nhiều thuốc"/"Thuốc kê đơn (tên không được chỉ định)").
    # "các chất chống chỉ định", "không tự ý mua thuốc cho trẻ": không có tên -> không gán.
]

GT[210] = [  # 279c ×1  1.txt — phòng ngừa bằng sàng lọc
    ("thiếu men G6PD", 0, DX, [], ["D55.0"]),
    ("xét nghiệm sàng lọc trước sinh và sau sinh", 0, LAB, [], []),  # chứa lần [0] của "xét nghiệm sàng lọc"
    ("xét nghiệm sàng lọc", 1, LAB, [], []),  # "tích hợp xét nghiệm sàng lọc"
    # "gói chăm sóc thai sản": dịch vụ -> không gán.
]

GT[140] = [  # 514c ×1  8.txt — bài giảng Kawasaki: "4. Biến chứng" + "5. Chẩn đoán" (cùng nguồn GT[104]/GT[124]/GT[135])
    # Bài phổ biến kiến thức, không có bệnh nhân cụ thể -> không assertion.
    # Danh sách biến chứng "có thể gây" vẫn gán (tiền lệ GT[124] cũng liệt kê biến
    # chứng của Kawasaki và gán hết, không isNegated).
    ("bệnh Kawasaki", ALL, DX, [], ["M30.3"]),  # 2 lần: tiêu đề mục 4 và mục 5
    # "Biến chứng tim mạch (nguy hiểm nhất)" / "Biến chứng khác": tiêu đề nhóm
    # -> không gán (tiền lệ tiêu đề nhóm panel xét nghiệm ở GT[136]).
    ("Phình giãn động mạch vành", 0, DX, [], ["I25.4"]),  # tiền lệ GT[124] cùng mã
    ("Hẹp – tắc động mạch vành", 0, DX, [], ["I25.1"]),  # tiền lệ GT[124] "hẹp tắc mạch vành"
    ("Thiếu máu cơ tim", 0, DX, [], ["I25.9"]),  # tiền lệ "thiếu máu cơ tim cục bộ" -> I25.9
    ("Nhồi máu cơ tim", 0, DX, [], ["I21.9"]),  # tiền lệ GT[124] cùng mã
    ("Suy vành mạn tính", 0, DX, [], ["I25.9"]),  # bệnh tim thiếu máu cục bộ mạn tính
    # "Khoảng 25–30% trẻ không điều trị đúng cách": dịch tễ -> không gán
    # (tiền lệ GT[124]/GT[135] cùng nguồn).
    ("Viêm cơ tim", 0, DX, [], ["I51.4"]),  # tiền lệ GT[124] "viêm tim" -> I51.4
    ("Tràn dịch màng tim", 0, DX, [], ["I31.3"]),
    ("Tăng men gan", 0, SYM, [], []),  # tiền lệ GT[37]/GT[30]: tăng men gan = TRIỆU_CHỨNG
    ("Rối loạn tiêu hóa", 0, DX, [], ["K30"]),
    # "Tiêu chuẩn chẩn đoán": tiêu đề -> không gán.
    ("Sốt", 0, SYM, [], []),  # "Sốt ≥5 ngày" — bề mặt chỉ lấy tên triệu chứng
    ("Viêm kết mạc 2 bên không ghèn", 0, DX, [], ["H10.9"]),  # viêm kết mạc không xác định
    # lưu ý: "động mạch vành" xuất hiện 2 lần nhưng cả 2 đều nằm trong nhãn dài hơn
    # ("Phình giãn…", "Hẹp – tắc…") -> KHÔNG khai riêng, tránh nhãn lồng nhau.
]

GT[141] = [  # 512c ×1  71.txt — bản gần trùng của ĐUÔI block 97 (69.txt): EHR tự tử nhảy cầu, cắt cụt 2 chân
    # Cùng nguồn GT[97], chỉ khác: có tiền tố "Câu hỏi từ người dùng:", đuôi
    # "Câu trả lời của bác sĩ:" và THIẾU dòng "Dùng kháng sinh tĩnh mạch."
    # -> giữ nguyên mọi quyết định của GT[97] cho các câu trùng, bỏ nhãn
    # "kháng sinh tĩnh mạch" vì câu đó không có trong block này.
    # Người nhà kể lại nhưng bệnh nhân CHÍNH LÀ người mắc -> không isFamily.
    # "Bệnh nhân tỉnh, tiếp xúc tốt": mô tả bình thường -> không gán.
    ("trầm cảm", 0, DX, [NEG, HIST], ["F32.9"]),  # "Không xác nhận đã bị trầm cảm trước đó"
    ("ý định tự tử", 0, SYM, [NEG], []),  # "không xác nhận có ý định tự tử"
    # ở đây chỉ 1 lần (block 97 có 3 lần) vì đây chỉ là phần đuôi; bề mặt lấy đúng
    # phần sau chữ lặp "tổn thương tổn thương chi dưới" -> khớp lần duy nhất.
    ("tổn thương chi dưới", 0, SYM, [], []),
    # "Phẫu thuật cắt cụt chân trái/phải" (3 lần "cắt cụt chân"): thủ thuật -> không gán.
    ("thuyên tắc phổi hai bên", 0, DX, [], ["I26.9"]),
    ("nhiễm trùng chi dưới bên phải do Enterococcus kháng vancomycin", 0, DX, [], ["A49.8"]),
]

GT[142] = [  # 507c ×1  3.txt — mục "3. Đánh giá tại bệnh viện" của EHR đột quỵ (cùng file/EHR với GT[29])
    # Cùng bệnh án với GT[29] -> dùng lại y nguyên quyết định của GT[29].
    # Toàn bộ là lần nhập viện NÀY -> không isHistorical.
    ("yếu nửa người bên phải", 0, SYM, [], []),
    ("suy giảm tri giác", 0, SYM, [], []),
    ("nhìn song thị", 0, SYM, [], []),  # tiền lệ GT[29]
    ("nhịp tim chậm", 0, SYM, [], []),  # tiền lệ GT[29] "nhịp tim chậm nặng"
    ("hạ huyết áp, không đặc hiệu", 0, DX, [], ["I95.9"]),  # 3 tiền lệ cùng bề mặt/mã
    ("không nhấc chân phải khỏi mặt giường", 0, SYM, [], []),
    ("chân phải liên tục khuỵ xuống", 0, SYM, [], []),
    ("tỉnh chậm, phản xạ kém", 0, SYM, [], []),  # tiền lệ GT[29] cùng bề mặt
    # "Chẩn đoán hình ảnh": tiêu đề nhóm -> không gán.
    ("chụp ct sọ não", ALL, LAB, [], []),  # 3 lần: 2 dòng kết quả + dòng "thủ thuật"
    # "âm tính" (2 lần): kết quả bằng chữ, không có trị số. GT[29] cùng bệnh án đã
    # chốt KHÔNG gán -> giữ nguyên để không tự mâu thuẫn.
    ("chọc dò dịch não tủy", 0, LAB, [], []),
    # "Truyền dịch tĩnh mạch": thủ thuật -> không gán (tiền lệ GT[45]/GT[24]).
]

GT[143] = [  # 507c ×1  89.txt — mục "3. Đánh giá tại bệnh viện" (cùng file với GT[8], EHR đau ngực gắng sức)
    # Bản dịch lặp NGUYÊN KHỐI cụm sinh hiệu trong ngoặc, dùng từ khác nhau
    # ("Mạch" -> "nhịp tim", "SpO2" -> "độ bão hòa oxy") nhưng TRỊ SỐ giống nhau
    # -> tên phép đo gán riêng từng bề mặt, trị số dùng ALL (2 lần).
    ("đau", 0, SYM, [NEG], []),  # "Không có đau tại phòng cấp cứu"
    ("điện tâm đồ", 0, LAB, [], []),  # tiền lệ GT[89]/GT[68]; "bình thường" -> không gán VAL
    ("Nhiệt độ", ALL, LAB, [], []),  # 2 lần (khớp cả "nhiệt độ" trong ngoặc)
    ("36.7°c", ALL, VAL, [], []),
    ("Huyết áp", ALL, LAB, [], []),
    ("139/68 mmhg", ALL, VAL, [], []),
    ("Mạch", 0, LAB, [], []),  # chỉ 1 lần; bản trong ngoặc dùng "nhịp tim"
    ("nhịp tim", 0, LAB, [], []),
    ("67 lần/phút", ALL, VAL, [], []),  # 2 lần, chung cho "Mạch" và "nhịp tim"
    ("Nhịp thở", ALL, LAB, [], []),
    ("16 lần/phút", ALL, VAL, [], []),
    ("SpO2", 0, LAB, [], []),  # chỉ 1 lần; bản trong ngoặc dùng "độ bão hòa oxy"
    ("độ bão hòa oxy", 0, LAB, [], []),  # tiền lệ GT[74]/GT[83]
    ("100%", ALL, VAL, [], []),
    # "(không thở oxy)", "trên khí trời": điều kiện đo -> không gán.
    # "ống nội khí quản": thủ thuật/dụng cụ -> không gán.
    ("nghiệm pháp gắng sức", 0, LAB, [], []),  # tiền lệ GT[76] cùng bề mặt
]

GT[19] = [  # 263c ×2  37.txt, 48.txt — đuôi câu trả lời của bác sĩ về nghe kém một bên ở trẻ 2 tuổi
    # Bệnh nhân là CON của người hỏi -> bối cảnh isFamily (tiền lệ GT[12]/GT[106]/
    # GT[117]/GT[134]). Nhưng nhãn duy nhất ở đây là TÊN_XÉT_NGHIỆM, mà LAB/VAL
    # KHÔNG được mang assertion -> không gán assertion nào.
    ("đo thính lực", 0, LAB, [], []),
    # "chuyên khoa Tai mũi họng nhi": chuyên khoa/cơ sở -> không gán
    # (tiền lệ "viện da liễu", "trung tâm tiêm chủng").
    # "chăm sóc bé như bình thường", "lộ trình điều trị": mô tả bình thường/lời khuyên
    # -> không gán.
]

GT[137] = [  # 551c ×1  53.txt — bệnh án gốc tiếng Việt: ĐTĐ typ 2 + THA (đứng ngay trước block 16)
    # Bệnh nhân là chính chủ bệnh án -> không isFamily. Toàn bộ là bệnh sử/khám lúc
    # vào viện (hiện tại) -> không isHistorical.
    ("mệt mỏi", ALL, SYM, [], []),  # 2 lần: lý do vào viện + "người mệt mỏi"
    ("gầy sút cân", ALL, SYM, [], []),  # 2 lần
    # Hội chứng tăng đường huyết "4 nhiều" — mỗi cụm là một triệu chứng riêng.
    ("Ăn nhiều", 0, SYM, [], []),
    ("khát nước", 0, SYM, [], []),
    ("uống nhiều", 0, SYM, [], []),
    ("đi tiểu nhiều", 0, SYM, [], []),
    # --- "Lúc vào viện trong tình trạng" : tên phép đo + trị số ---
    ("Mạch", 0, LAB, [], []),
    ("89 lần/phút", 0, VAL, [], []),
    ("HA", 0, LAB, [], []),  # tiền lệ GT[91] "đo HA là 160/70 mmHg"
    ("180/100 mmHg", 0, VAL, [], []),
    ("Xét nghiệm máu", 0, LAB, [], []),  # tiền lệ GT[136]
    ("Glucose máu", 0, LAB, [], []),
    ("13,2 mmol/l", 0, VAL, [], []),
    ("XQ", 0, LAB, [], []),  # viết tắt của x-quang, vẫn là tên xét nghiệm
    # Các phát hiện đọc trên phim -> CHẨN_ĐOÁN (tiền lệ GT[165]/GT[94]/GT[69]).
    ("Quai ĐMC vồng cao", 0, DX, [], ["I70.0"]),  # dấu hiệu xơ vữa động mạch chủ
    ("chỉ số tim/LN", 0, LAB, [], []),  # chỉ số tim/lồng ngực = một phép đo trên phim
    ("< ½", 0, VAL, [], []),
    ("rốn phổi đậm", 0, DX, [], ["R91"]),  # phát hiện bất thường CĐHA ở phổi
    ("ĐTD typ II", 0, DX, [], ["E11"]),  # viết tắt của đái tháo đường typ 2
    # "thuốc điều trị ĐTD typ II (không rõ thuốc gì)", "không duy trì thuốc":
    # không có tên thuốc -> không gán (tiền lệ "điều trị thuốc không đều").
]

GT[18] = [  # 274c ×2  49.txt, 65.txt — đuôi bài giảng điều trị rụng tóc (cùng nguồn GT[76])
    # Bài giảng phương pháp điều trị, không có bệnh nhân cụ thể -> không assertion
    # (tiền lệ GT[76] cùng nguồn).
    # PUVA = psoralen + tia UVA: liệu pháp có thuốc -> THUỐC, RxNorm không có
    # "psoralen" (chỉ có methoxsalen là một psoralen cụ thể) -> candidates rỗng.
    # Tiền lệ "hóa trị"/"liệu pháp lợi tiểu" gán THUỐC với candidates rỗng.
    ("PUVA", ALL, DRUG, [], []),  # 2 lần: tiêu đề + "PUVA toàn thân và tại chỗ"
    ("psoralen", 0, DRUG, [], []),
    # "UVA": tia tử ngoại, không phải thuốc -> không gán.
    # "tái phát sau khi ngừng điều trị": không nêu tên bệnh -> không gán.
    # "bác sĩ da liễu": chuyên khoa -> không gán.
]

GT[138] = [  # 540c ×1  85.txt — mục "2. Lịch sử bệnh hiện tại" (cùng EHR với GT[115]) + mẩu tư vấn môi
    # Tiêu đề "hiện tại" -> không isHistorical cho phần triệu chứng hiện tại
    # (tiền lệ GT[129]).
    ("đau bàn chân phải", ALL, SYM, [], []),  # 2 lần: lý do nhập viện + triệu chứng
    ("mất thăng bằng khi đi lại", 0, SYM, [], []),
    # --- "Các sự kiện trước khi nhập viện" -> đã qua -> isHistorical (tiền lệ GT[129]) ---
    ("viêm bể thận", 0, DX, [HIST], ["N12"]),  # không nói rõ cấp/mạn -> mã không xác định
    ("viêm phế quản", 0, DX, [HIST], ["J40"]),  # tiền lệ GT[134] cùng mã
    # --- mẩu tư vấn chăm sóc môi của một bài khác ghép vào (cùng nguồn GT[69]) ---
    # "khẩu trang", "phương pháp bảo hộ", "bụi bẩn", "va chạm, cọ xát": hành vi/vật
    # dụng -> không gán. "khu vực da còn thương tổn": mô tả chung trong lời khuyên,
    # không phải triệu chứng của BN nào -> không gán (tiền lệ GT[11] "vết thương").
    ("vitamin C", 0, DRUG, [], ["1151"]),  # tiền lệ GT[69] cùng nguồn + GT[167]
    # --- trở lại EHR bàn chân ---
    ("không vững khi đứng", 0, SYM, [], []),
]

GT[139] = [  # 533c ×1  13.txt — mục "2. Tiền sử bệnh hiện tại" + mẩu bài giảng dại ghép vào
    # "Tiền sử bệnh hiện tại" = HPI -> không isHistorical (tiền lệ GT[129]).
    ("đau ngực trái cấp tính", 0, SYM, [], []),  # tiền lệ GT[101]
    ("đau sau xương ức lan ra sau lưng", 0, SYM, [], []),  # tiền lệ GT[101]
    # --- mẩu bài giảng bệnh dại (cùng nguồn GT[66]/GT[70]) ---
    # Đoạn này là phần giữa của block 66; ở block 66 KHÔNG gán "vi rút dại",
    # "vết cắn", "vết thương" -> giữ đúng như vậy để không tự mâu thuẫn:
    # tác nhân/đường vào của bệnh trong bài giảng chung -> không gán.
    # "Tình trạng miễn dịch của bệnh nhân", "thời gian ủ bệnh": không phải khái niệm
    # bệnh/triệu chứng -> không gán.
    # "trung tâm tiêm chủng", "chích ngừa": cơ sở/thủ thuật -> không gán.
]

# ------------------------------------------------
# Hai block còn lại của file 13.txt (block 0/120/108/139 đã xong) -> gán TRỌN file.
# PHÁT HIỆN: 170 và 184 là BẢN DỊCH KHÁC của đúng hai block đã gán ở 16.txt/20.txt:
#   170 (420c) <=> block 10 (437c): cùng câu hỏi "dính nước dãi chó con", chỉ khác
#     dòng tiêu đề ("Em chào bác sỹ" vs "Câu hỏi của người dùng gửi đến hệ thống"),
#     cách ngắt dòng, và 170 có thêm dòng "Câu trả lời của bác sĩ:" ở cuối.
#   184 (370c) <=> block 11 (387c): cùng đoạn bác sĩ trả lời về đường lây, chỉ khác
#     dòng "Bác sĩ trả lời" và một chỗ ngắt dòng giữa "mèo dại / hoặc động vật khác".
# Vì tiền tố lệch ngay ký tự đầu nên SHARE không dùng được -> gán tay, nhưng DÙNG LẠI
# Y NGUYÊN nhãn của GT[10]/GT[11] để hai bản dịch của cùng nguồn không lệch nhau.
# ------------------------------------------------

GT[170] = [  # 420c ×1  13.txt — bản dịch khác của block 10 (câu hỏi nguy cơ dại)
    ("thương nhẹ ở tay", 0, SYM, [], []),  # y như GT[10]
    ("chảy máu", 0, SYM, [], []),  # y như GT[10]
    # "chó chưa tiêm dại": vaccine của con chó, không phải thuốc bệnh nhân dùng
    # -> không gán (chốt ở GT[10]).
    # "nước dãi": tác nhân/đường vào -> không gán (GT[10]/GT[139]).
    ("bệnh dại", 0, DX, [], ["A82.9"]),  # "nguy cơ lây bệnh dại" — người hỏi CHƯA mắc,
    # vẫn gán CHẨN_ĐOÁN với assertions rỗng, y như GT[10]. Người hỏi tự kể về mình
    # -> không isFamily (tiền lệ GT[4]/GT[105]).
    # "Em chào bác sỹ", "Mong nhận được sự tư vấn của bác sỹ",
    # "Câu trả lời của bác sĩ:": chào hỏi/tiêu đề -> không gán (tiền lệ block 0).
]

GT[184] = [  # 370c ×1  13.txt — bản dịch khác của block 11 (đường lây bệnh dại)
    # Bài phổ biến kiến thức, không có BN cụ thể -> không assertion (GT[11]/GT[66]).
    ("bệnh dại", ALL, DX, [], ["A82.9"]),  # 4 lần, khớp 1-1 với 4 nhãn của GT[11]:
    # [0] "Bệnh dại chỉ không chỉ lây", [1] "Đường lây bệnh dại phổ biến nhất",
    # [2] "Bệnh dại còn có thể lây truyền", [3] "động vật khác mắc bệnh dại".
    # Matcher không phân biệt hoa/thường và bề mặt lấy đúng lát block nên hoa/thường
    # giữ nguyên -> dùng ALL gọn hơn khai rời 4 dòng như GT[11].
    # "vết cắn của động vật", "động vật dại", "nước bọt của chó, mèo dại",
    # "vết thương", "vùng da bị trầy xước": tác nhân/đường vào của bệnh trong bài
    # giảng chung -> không gán (chốt ở GT[11], nhắc lại ở GT[139]).
    # "Chào bạn", "Để giải đáp thắc mắc của bạn": chào hỏi -> không gán.
]

GT[135] = [  # 564c ×1  2.txt — bài giảng "Nguyên nhân gây bệnh Kawasaki" (cùng nguồn GT[104]/GT[124])
    # Bài phổ biến kiến thức -> không assertion. Danh sách nguyên nhân nghi ngờ vẫn
    # gán theo quy ước "khái niệm trong danh sách nguyên nhân" (worklog/07).
    ("bệnh Kawasaki", 0, DX, [], ["M30.3"]),
    ("Nhiễm khuẩn", 0, DX, [], ["A49.9"]),
    ("nhiễm virus", 0, DX, [], ["B34.9"]),
    ("độc tố vi khuẩn", 0, DX, [], []),  # tác nhân, không có mã ICD riêng
    ("Phản ứng miễn dịch bất thường", 0, DX, [], ["D89.9"]),
    # "Yếu tố chủng tộc", "Trẻ gốc Á", "Yếu tố môi trường: thay đổi khí hậu, chất độc
    # trong không khí": yếu tố nguy cơ dịch tễ/môi trường -> không gán (tiền lệ
    # "hút thuốc lá thụ động", "môi trường ô nhiễm" ở GT[104] cùng nguồn).
    # "Bệnh không lây từ trẻ này sang trẻ khác": nhận định về đường lây -> không gán.
]

GT[136] = [  # 563c ×1  40.txt — phiếu chỉ định xét nghiệm (toàn bộ là TÊN_XÉT_NGHIỆM)
    # Phiếu chỉ định, không có bệnh nhân/triệu chứng. TÊN_XÉT_NGHIỆM không được mang
    # assertion theo đề. Giữ nguyên cả cụm có ngoặc làm bề mặt (tiền lệ GT[62]:
    # "Đo hoạt độ AST (GOT)", "Định lượng NT - proBNP ( ProBNP)").
    ("Xét nghiệm máu", 0, LAB, [], []),
    ("Khí máu động mạch (23 thông số)", 0, LAB, [], []),
    ("Tổng phân tích tế bào máu ngoại vi", 0, LAB, [], []),
    ("Thời gian Thromboplastin một phần hoạt hóa (aPTT / TCK)", 0, LAB, [], []),
    ("Thời gian Prothrombin (PT / TQ / Tỷ lệ Prothrombin)", 0, LAB, [], []),
    ("Định lượng Fibrinogen (Yếu tố I)", 0, LAB, [], []),
    ("Định lượng Glucose, Urê, Creatinin máu", 0, LAB, [], []),
    ("Điện giải đồ (Na+, K+, cl-)", 0, LAB, [], []),
    ("Đo hoạt độ AST (GOT)", 0, LAB, [], []),
    ("ALT (GPT)", 0, LAB, [], []),
    ("Định lượng CRP", 0, LAB, [], []),
    ("Troponin T siêu nhạy (hs-Troponin T)", 0, LAB, [], []),
    # "Huyết học & Đông máu:", "Sinh hóa & Men tim:", "Men gan:", "Viêm & Men tim:":
    # tiêu đề nhóm, không phải tên xét nghiệm cụ thể -> không gán.
    # "bằng máy đếm laser", "bằng máy tự động", "Phương pháp Clauss trực tiếp":
    # phương pháp/thiết bị -> không gán.
]

GT[17] = [  # 276c ×2  42.txt, 62.txt — "3. Đánh giá tại bệnh viện" EHR viêm phổi thùy dưới phải
    ("số lượng bạch cầu", 0, LAB, [], []),
    ("12.5", 0, VAL, [], []),
    ("tổng phân tích nước tiểu", 0, LAB, [], []),
    ("vếtvết protein niệu", 0, VAL, [], []),  # lỗi dịch lặp chữ "vết", giữ nguyên bề mặt;
    # đây là KẾT QUẢ của tổng phân tích nước tiểu (định tính có tiền lệ: "âm tính",
    # "dương tính") -> KẾT_QUẢ_XÉT_NGHIỆM.
    ("troponin", 0, LAB, [], []),
    ("âm tính", 0, VAL, [], []),  # "troponin âm tính x1"
    ("chụp x-quang ngực", 0, LAB, [], []),
    # Phát hiện đọc trên phim là CHẨN_ĐOÁN (tiền lệ GT[165]/GT[94]/GT[110]).
    ("viêm phổi thùy dưới phải (RLL PNA)", 0, DX, [], ["J18.1"]),
]

GT[132] = [  # 577c ×1  22.txt — "3. Đánh giá tại bệnh viện" EHR tăng men gan/bilirubin
    # Cùng nguồn EHR với GT[37] (44.txt) nhưng bản dịch khác và dài hơn ở đuôi —
    # dùng lại đúng mã của GT[37] để không tự mâu thuẫn.
    ("ast", 0, LAB, [], []),
    ("421", 0, VAL, [], []),
    ("alt", 0, LAB, [], []),
    ("336", 0, VAL, [], []),
    ("alp", 0, LAB, [], []),
    ("185", 0, VAL, [], []),
    ("bilirubin toàn phần", 0, LAB, [], []),
    ("0.9", 0, VAL, [], []),
    ("total bili", 0, LAB, [], []),  # tên chỉ số còn nguyên tiếng Anh
    ("6.7", 0, VAL, [], []),
    ("bảng xét nghiệm viêm gan virus", 0, LAB, [], []),
    ("âm tính", 0, VAL, [], []),  # tiền lệ cặp tên XN + "âm tính" ở GT[58]/GT[102]
    ("ferritin", 0, LAB, [], []),
    # "là bình thường": nhận định định tính, không có trị số -> không gán.
    ("ceruloplasmin", 0, LAB, [], []),
    # "đang chờ kết quả": chưa có kết quả -> không gán VAL.
    # --- "Kết quả chẩn đoán hình ảnh" ---
    ("siêu âm bụng có doppler", 0, LAB, [], []),
    ("âm tính", 1, VAL, [], []),  # "âm tính âm tính" — lỗi dịch lặp, gán cả 2 lần
    ("âm tính", 2, VAL, [], []),
    ("âm tính", 3, VAL, [], []),  # dòng "- âm tính chụp hida" (đảo trật tự do dịch)
    ("chụp hida", 0, LAB, [], []),
    ("ercp", ALL, LAB, [], []),  # 2 lần: dòng kết quả + "Thủ thuật thực hiện: ercp"
    ("túi mật giãn nở rõ rệt", 0, DX, [], []),  # chứa lần [0] của "túi mật giãn"
    ("túi mật giãn", 1, DX, [], []),  # lỗi dịch lặp cụm, vẫn là bề mặt riêng
    ("sỏi", 0, DX, [NEG], ["K80.5"]),  # "không có sỏi hoặc bệnh lý giải phẫu bệnh khác"
    # --- "Các phát hiện chẩn đoán khác" ---
    ("tăng men gan", 0, SYM, [], []),  # tiền lệ GT[37]: tăng men gan = TRIỆU_CHỨNG
    ("tăng bilirubin máu", 0, DX, [], ["R17.9"]),
]

GT[133] = [  # 577c ×1  24.txt — mục "2/ Chẩn đoán" + y lệnh EHR viêm gan B cấp
    ("khó chịu vùng ngực", 0, SYM, [NEG], []),  # "không còn cảm giáckhó chịu vùng ngực"
    # (lỗi dịch dính chữ "cảm giáckhó" — needle bắt từ "khó chịu" nên không ảnh hưởng)
    ("Glucose 5%", 0, DRUG, [], ["4850"]),  # dịch truyền, tiền lệ GT[91] "dextrose" -> 4850
    # "nước tiểu 1500ml/ngày", "nước tiểu trong": theo dõi lượng/tính chất nước tiểu,
    # không phải tên xét nghiệm có trị số -> không gán.
    ("Philpovin", 0, DRUG, [], []),  # biệt dược VN, không có trong RxNorm
    ("**********", 0, DRUG, [], []),  # dung môi pha bị mask (tiền lệ GT[24]/GT[100])
    ("ALT", ALL, LAB, [], []),  # 2 lần, đều là chỉ số theo dõi trong y lệnh
    ("AST", ALL, LAB, [], []),  # 2 lần
    ("Fortex", 0, DRUG, [], []),  # biệt dược VN, không có trong RxNorm
    ("Vitamin 3B", 0, DRUG, [], ["11251"]),  # = vitamin B complex (B1+B6+B12)
    # Đuôi block bị cắt giữa câu chẩn đoán: "…cấp tính do virus B thể thông thường
    # điển hình mức độ nặng giai đoạn toàn phát" (mất chữ "Viêm gan" ở đầu do ghép
    # block). Vẫn gán theo bề mặt còn lại — đây là tên chẩn đoán.
    ("cấp tính do virus B thể thông thường điển hình mức độ nặng giai đoạn toàn phát",
     0, DX, [], ["B16.9"]),
]

GT[134] = [  # 577c ×1  29.txt — trả lời QA bàn chân bẹt + 2 dòng CĐHA của EHR (cùng file GT[52])
    # Bệnh nhân là CON của người hỏi -> isFamily (tiền lệ GT[26]/GT[45]/GT[52]).
    ("bệnh bàn chân bẹt", 0, DX, [FAM], ["Q66.5"]),
    ("tật bẩm sinh", 0, DX, [FAM], ["Q66.5"]),  # cùng bệnh, cách gọi khác
    # "chạy nhảy bình thường": chức năng bình thường -> không gán.
    ("đau", 0, SYM, [NEG, FAM], []),  # "không đau"
    # "chỉ định phẫu thuật", "tập vận động", "khám lâm sàng": thủ thuật/điều trị
    # -> không gán. "bất thường về xương", "thiếu hụt về phần mềm": mục tiêu cần
    # đánh giá, quá chung, chưa phải chẩn đoán -> không gán.
    # --- 2 dòng CĐHA của EHR khác: mã dùng lại đúng như GT[52] cùng file 29.txt ---
    ("Siêu âm mạch máu chi trên", 0, LAB, [], []),
    ("huyết khối", 0, DX, [NEG], ["I82.9"]),  # "không ghi nhận huyết khối"
    ("Xạ hình thông khí – tưới máu phổi", 0, LAB, [], []),  # dấu – là en-dash
    ("thuyên tắc phổi", 0, DX, [], ["I26.9"]),  # "xác suất thấp" -> vẫn gán, không NEG
]

GT[16] = [  # 304c ×2  53.txt, 57.txt — danh sách thuốc trước nhập viện
    # Cùng bệnh nhân với GT[103] (57.txt) -> dùng lại đúng mã RxNorm để không mâu thuẫn.
    #
    # SỬA: chú thích cũ ghi "mục Hiện tại -> không isHistorical". Sai, và đây là ca duy
    # nhất trong corpus mà một block nằm dưới HAI tiêu đề khác nhau ở hai file: 53.txt để
    # nó dưới "Hiện tại:", 57.txt để nó dưới "1. Tiền sử bệnh / Thuốc trước khi nhập viện"
    # (đo: 24 block xuất hiện >1 lần, 3 block có tiêu đề mâu thuẫn, 2 trong 3 là do văn
    # bản ghép nên tiêu đề không chi phối -> còn đúng block này). GT gán theo BLOCK nên
    # không thể đúng cả hai file; phải chọn một.
    # Chọn isHistorical vì bằng chứng NẰM TRONG block, không phụ thuộc tiêu đề: 5/6 thuốc
    # ghi "đã hết thuốc khoảng 3 tuần trước nhập viện" / "hiện đã ngừng sử dụng" -> đây là
    # thuốc dùng TRƯỚC khi vào viện. Ví dụ mẫu của đề cũng gán isHistorical cho toàn bộ
    # danh sách thuốc trước nhập viện, nên hướng này khớp quy ước BTC.
    # Thuốc đã ngừng/hết giữ NEG kèm HIST: hai assertion độc lập, ngừng thuốc không làm
    # nó thôi là thuốc quá khứ.
    ("Torsemide", 0, DRUG, [HIST], ["38413"]),
    ("Insulin glargine", 0, DRUG, [NEG, HIST], ["274783"]),  # "hiện đã ngừng sử dụng"
    ("Isosorbide", 0, DRUG, [NEG, HIST], ["6057"]),  # "đã hết thuốc"
    ("Rosuvastatin", 0, DRUG, [NEG, HIST], ["301542"]),
    ("Crestor", 0, DRUG, [NEG, HIST], ["320864"]),  # biệt dược của rosuvastatin, cùng dòng
    ("Carvedilol", 0, DRUG, [NEG, HIST], ["20352"]),
]

GT[128] = [  # 593c ×1  51.txt — bác sĩ trả lời về mổ lại dây chằng chéo + 4 dòng y lệnh EHR khác
    # Trả lời cho chính người hỏi -> không isFamily. Đây là phương án dự kiến, chưa
    # thực hiện, nhưng tổn thương là thật (bệnh nhân đang có) -> không isNegated.
    # "mổ lại (tái tạo lại)": thủ thuật -> không gán.
    ("dây chằng chéo trước", 0, DX, [], ["S83.5"]),  # tổn thương dây chằng chéo trước
    ("tổn thương sụn chêm", 0, DX, [], ["S83.2"]),
    # --- 4 dòng y lệnh của EHR khác ghép vào cuối (không có BN cụ thể trong đoạn) ---
    ("aspirin", 0, DRUG, [], ["1191"]),  # bỏ liều khỏi bề mặt (chuẩn hoá đợt 12)
    # (liều thuốc không phải KẾT_QUẢ_XÉT_NGHIỆM theo quy ước)
    ("albuterolipratropium", 0, DRUG, [], []),  # lỗi dịch dính 2 tên thuốc
    # (khác GT[84] "klonopinclonidine": ở đây KHÔNG có lần xuất hiện độc lập nào của
    # "albuterol"/"ipratropium" nên chỉ gán cụm dính, tránh nhãn lồng nhau)
    ("methylprednisolone", 0, DRUG, [], ["6902"]),
    ("lợi tiểu", 0, DRUG, [], []),  # nhóm thuốc, không tên cụ thể (tiền lệ GT[52])
]

# ---------------------------------------------------------------------------
# File 91.txt = MỘT bệnh án (hội chứng Turner / THA / cắt đại tràng do ung thư /
# thuyên tắc phổi dùng coumadin, vào viện vì khó thở), bị GHÉP một mẩu QA về sỏi
# niệu quản vào GIỮA dòng 31. Mục 2 (HPI) đã gán ở GT[129]; còn 2 block:
# block 187 = mục "1. Tiền sử bệnh", block 154 = mục "3. Đánh giá tại bệnh viện"
# (chứa mẩu QA sỏi niệu quản chèn vào).
# Quy ước chốt cho cả file:
#  - Mục "1. Tiền sử bệnh" / "Thuốc trước khi nhập viện" -> isHistorical (tiền lệ
#    GT[9]/GT[175]/GT[14]/GT[20]/GT[87]). Mục "3. Đánh giá tại bệnh viện" là lần
#    nhập viện HIỆN TẠI -> không assertion (tiền lệ GT[143]/GT[98]).
#  - Thủ thuật/phẫu thuật KHÔNG gán, chỉ lấy chẩn đoán bên trong câu (tiền lệ
#    GT[13]/GT[14]/GT[145]).
#  - Mẩu QA chèn vào là câu kiến thức chung ("... lớn hơn 7mm THƯỜNG không ...")
#    -> KHÔNG gán assertion, dù cuối đoạn mới lộ ra bệnh nhân là CHỒNG người hỏi.
#    Theo tiền lệ GT[72] (QA sàng lọc thai: "câu nói chung về mọi thai kỳ, không
#    phải chẩn đoán của một người cụ thể -> không gán assertion") và GT[55]/GT[84].
#    Đã cân nhắc isFamily theo tiền lệ GT[53] (vợ bệnh nhân) nhưng loại: ở GT[53]
#    câu gán là chẩn đoán CỦA người vợ, còn ở đây bề mặt nằm trong câu quy tắc
#    chung, không phải chẩn đoán của người chồng.
# ---------------------------------------------------------------------------

GT[187] = [  # 363c ×1  91.txt — mục "1. Tiền sử bệnh" (bệnh lý mãn tính + thuốc)
    # Toàn block nằm dưới "1. Tiền sử bệnh" -> tất cả isHistorical.
    ("hội chứng turner, không đặc hiệu", 0, DX, [HIST], ["Q96.9"]),
    # Giữ TRỌN đuôi ", không đặc hiệu" trong bề mặt theo quy ước (tiền lệ GT[87]
    # "tăng lipid máu, không đặc hiệu", GT[88] "bệnh thận mạn, không đặc hiệu
    # Giai đoạn 4", GT[142]/GT[94]/GT[45]/GT[42] "hạ huyết áp, không đặc hiệu").
    # Q96.9 "Hội chứng Turner, không xác định" — đúng mã .9 vì 6 mã con Q96.0–Q96.4
    # /Q96.8 đều đòi công thức nhiễm sắc thể cụ thể, bề mặt không nêu.
    ("Tăng huyết áp", 0, DX, [HIST], ["I10"]),  # tiền lệ 11 block dùng I10 cho
    # "tăng huyết áp"; HIST theo bối cảnh "Các bệnh lý mãn tính" (GT[52]/GT[87]/
    # GT[91]/GT[198]/GT[98]/GT[88]/GT[14]/GT[20]).
    ("Ung thư đại tràng", 0, DX, [HIST], ["C18.9"]),  # tiền lệ GT[13] cùng bề mặt
    # ("ung thư tuyến đại tràng" -> C18.9, cũng isHistorical).
    # KHÔNG gán "phẫu thuật cắt bỏ đại tràng" và "Cắt đại tràng nhiều năm trước":
    # thủ thuật -> chỉ lấy chẩn đoán trong câu (tiền lệ GT[13] bỏ "Phẫu thuật mở
    # cắt nối trực tràng/đại tràng sigma" cùng mục, GT[182] bỏ "phẫu thuật cắt
    # bỏ tuyến tiền liệt", GT[142]/GT[94]/GT[45] bỏ "Truyền dịch tĩnh mạch").
    ("Thuyên tắc phổi", ALL, DX, [HIST], ["I26.9"]),  # 2 lần: dòng 6 tự lặp lại
    # chính nó trong ngoặc (lỗi dịch máy) -> dùng ALL như GT[143] xử cụm sinh hiệu
    # lặp nguyên khối. I26.9 theo tiền lệ GT[52]/GT[134]/GT[141]/GT[97].
    ("coumadin", ALL, DRUG, [HIST], ["11289"]),  # 3 lần (2 lần dòng 6 do lặp
    # trong ngoặc + 1 lần dòng "Thuốc trước khi nhập viện").
    # Coumadin KHÔNG có trong RXNCONSO.RRF (grep -ci coumadin = 0) -> dùng mã hoạt
    # chất warfarin IN 11289, theo tiền lệ GT[326] "Omez" -> omeprazole IN 7646 và
    # GT[35] "Pimperan" -> 6915. Khác các biệt dược CÓ trong RxNorm thì dùng mã BN
    # (GT[182] eliquis 1364436, GT[63] tylenol 202433).
]

GT[154] = [  # 461c ×1  91.txt — mục "3. Đánh giá tại bệnh viện" + QA sỏi niệu quản chèn giữa
    # Tiêu đề mục "3. Đánh giá tại bệnh viện" / "Các thủ thuật đã thực hiện":
    # không gán (tiền lệ GT[132]/GT[94]/GT[22]).
    ("albuterolipratropium", 0, DRUG, [], []),  # tiền lệ GT[128] Y NGUYÊN cùng bề
    # mặt: lỗi dịch dính 2 tên thuốc, candidates RỖNG vì RxNorm không có cụm dính
    # và trong block không có lần xuất hiện rời của "albuterol"/"ipratropium" để
    # tách nhãn (khác GT[209] "doxycyclinebactrim" có bản dịch rời để đối chiếu).
    # "nebs x2": dạng dùng/số lần -> không gán.
    # --- mẩu QA sỏi niệu quản chèn vào giữa dòng: câu chung -> không assertion ---
    ("Sỏi niệu quản", 0, DX, [], ["N20.1"]),  # N20.1 "Sỏi niệu quản" trùng nguyên
    # văn tên mã. Cắt "lớn hơn 7mm" khỏi bề mặt theo quy ước 6 đợt 13 (hậu tố đo
    # lường thì cắt): tiền lệ GT[140] "Sốt ≥5 ngày" -> "Sốt", GT[276] "Hạch cổ to
    # ≥1,5 cm" -> "Hạch cổ to".
    ("tổn thương chức năng thận", 0, DX, [], ["N28.9"]),
    # Hậu quả NẾU KHÔNG điều trị -> vẫn gán, KHÔNG isNegated (tiền lệ GT[174] "hậu
    # quả nếu không điều trị" gán đủ thiếu máu tan huyết/vàng da/tan huyết, và
    # GT[197]). Khác GT[106] nơi biến chứng được nêu để PHÒNG -> isNegated.
    # Mã: N28.9 "Rối loạn của thận và/hoặc niệu quản, không xác định". Đã loại
    # N19 "Suy thận không xác định" (bề mặt nói "tổn thương chức năng", chưa nói
    # SUY — khác GT[77] "Không có suy thận" -> N19) và S37.0 "tổn thương thận"
    # (là chấn thương ngoại lực). Tra danh mục: KHÔNG có mục nào tên "tổn thương
    # chức năng thận". Theo tiền lệ GT[75] "suy giảm chức năng gan" -> K72.9
    # (mã .9 không xác định của cơ quan tương ứng).
    # "điều trị nội khoa", "can thiệp phẫu thuật", "phẫu thuật" (2 lần): thủ
    # thuật/phương pháp -> không gán.
    # --- nốt EHR sau mẩu QA ---
    ("hr", 0, LAB, [], []),  # viết tắt heart rate chưa dịch; bề mặt viết tắt là
    # nhãn riêng theo tiền lệ GT[137] ("HA"), GT[162]/GT[91] ("M"), GT[63]
    # ("spo2" ở GT[61]/GT[53]). Cùng loại LAB với "nhịp tim" ở GT[143].
    ("110", 0, VAL, [], []),  # trị số đo được -> VAL dù trơ số (tiền lệ GT[115]
    # "478"/"20"/"13"/"316", GT[94] "28" trong "ổn định ở mức 28").
    ("metoprolol", 0, DRUG, [], ["6918"]),  # tiền lệ GT[175]/GT[34] cùng mã; ở đây
    # là thuốc dùng TRONG lần nhập viện này -> không HIST.
    # KHÔNG gán "cải thiện" (mức độ, không phải khái niệm) và "cảm thấy khỏe"
    # (trạng thái BÌNH THƯỜNG -> không gán, tiền lệ GT[143]/GT[141]/GT[68]/GT[133]).
]

GT[129] = [  # 588c ×1  91.txt — "2. Tiền sử bệnh hiện tại" EHR khó thở/có đờm
    # Mục "hiện tại" (dù tiêu đề dịch là "Tiền sử bệnh hiện tại" = HPI) -> không
    # isHistorical. Các dòng "Không X" -> isNegated.
    ("khó thở", 0, SYM, [], []),  # "Lý do nhập viện: khó thở"
    ("khó thở", 1, SYM, [], []),  # "Các triệu chứng hiện tại - khó thở"
    ("Cảm giác có đờm ở cổ họng", 0, SYM, [], []),
    ("Cần phải ho nó ra", 0, SYM, [], []),
    ("sốt", 0, SYM, [NEG], []),
    ("ớn lạnh", 0, SYM, [NEG], []),
    ("đau ngực", 0, SYM, [NEG], []),
    ("khó thở", 2, SYM, [NEG], []),  # "Không  khó thở"
    ("thay đổi tính chất cơn đau khi thay đổi tư thế", 0, SYM, [NEG], []),
    ("khó thở khi gắng sức", 0, SYM, [NEG], []),  # chứa lần [3] của "khó thở"
    ("đánh trống ngực", 0, SYM, [NEG], []),
    ("khó thở tăng lên", 0, SYM, [NEG], []),  # chứa lần [4] của "khó thở"
    # SỬA (chống span lồng nhau): trước ghi "[[khó thở tăng lên khi xuất hiện  ]]Cơn nhịp
    # nhanh" — ĐẶT NGOẶC SAI CHỖ. Cú pháp là `ngữ cảnh [[phần cần lấy]] ngữ cảnh`, nên
    # cái đó lấy ra đúng chuỗi "khó thở tăng lên khi xuất hiện  ", trùng đè lên nhãn
    # "khó thở tăng lên" ở dòng trên. Ý ban đầu là lấy "Cơn nhịp nhanh" -> chuyển ngoặc.
    ("khó thở tăng lên khi xuất hiện  [[Cơn nhịp nhanh]]", 0, SYM, [NEG], []),
    # -> "Không khó thở tăng lên khi xuất hiện Cơn nhịp nhanh": phủ định là mối liên
    # hệ, nhưng cơn nhịp nhanh có thật -> vẫn NEG theo bề mặt câu (an toàn hơn).
    ("đau ngực", 1, SYM, [NEG], []),
    # --- "Các diễn biến trước khi nhập viện" -> đã qua -> isHistorical ---
    # "nhập viện để đánh giá tổng quát về tiêu hóa": thủ thuật/lý do -> không gán.
    ("khó nuốt", 0, SYM, [HIST], []),
]

GT[125] = [  # 626c ×1  3.txt — bác sĩ giảng về cảnh báo thuốc Vastarel (trimetazidin)
    # Bài giảng về thuốc, không có bệnh nhân cụ thể -> không assertion
    # (tiền lệ GT[55] phần "danh sách tác dụng phụ là kiến thức chung").
    ("Vastarel", 0, DRUG, [], []),  # không có trong RxNorm (không lưu hành ở Mỹ),
    # tiền lệ GT[55] để candidates rỗng cho trimetazidine.
    ("trimetazidin", 0, DRUG, [], []),
    # --- tác dụng bất lợi: kiến thức chung ---
    ("hội chứng Parkinson", 0, DX, [], ["G21.9"]),  # thuốc gây/làm nặng -> thứ phát
    ("run tay chân", 0, SYM, [], []),
    ("mất thăng bằng khi đi", 0, SYM, [], []),
    ("run rấy toàn thân", 0, SYM, [], []),  # lỗi chính tả corpus ("run rẩy"), giữ nguyên
    # --- chỉ định còn lại ---
    ("đau thắt ngực ổn định", 0, DX, [], ["I20.8"]),  # nằm trong "ổn địnhkhi" (dính chữ)
    # "không dung nạp với các thuốc khác", "các thuốc khác": không có tên -> không gán.
    # --- chống chỉ định: kiến thức chung ---
    ("chóng mặt", 0, SYM, [], []),
    ("ù tai", 0, SYM, [], []),
    ("rối loạn thị lực", 0, SYM, [], []),
    ("Parkinson", 1, DX, [], ["G20"]),  # "người bị Parkinson" -> bệnh Parkinson
    # ([0] nằm trong "hội chứng Parkinson" ở trên)
]

GT[3] = [  # 207c ×3  21.txt, 32.txt, 79.txt — câu hỏi người dùng về amyloidosis
    # Người hỏi chính là bệnh nhân -> không isFamily.
    ("Rối loạn chuyển hóa tinh bột", 0, DX, [], ["E85.9"]),  # cách dịch khác của
    # "bệnh thoái hóa tinh bột" (tiền lệ GT[30]/GT[81]) -> cùng mã E85.9.
    ("amyloidosis", 0, DX, [], ["E85.9"]),
    # "Có dùng thuốc tại viện da liễu trung ương": không có tên thuốc -> không gán
    # (tiền lệ "điều trị nhiều thuốc"/"Uống thuốc").
]

GT[115] = [  # 675c ×1  85.txt — "3. Đánh giá tại bệnh viện" EHR bàn chân/nhiễm trùng, phiếu CLS
    # Tên chỉ số ở đây song ngữ "vi (en)" — giữ nguyên cả cụm làm bề mặt
    # TÊN_XÉT_NGHIỆM (tiền lệ GT[63] "độ bão hòa oxy (SPO2)").
    ("hct (hematocrit)", 0, LAB, [], []),
    ("8.126.3", 0, VAL, [], []),  # lỗi dịch dính 2 trị số, giữ nguyên bề mặt
    ("tiểu cầu (platelets)", 0, LAB, [], []),
    ("478", 0, VAL, [], []),
    ("hco3- (bicarbonate)", 0, LAB, [], []),
    ("20", 0, VAL, [], []),
    ("ag (anion gap)", 0, LAB, [], []),
    ("13", 0, VAL, [], []),
    ("bun/creatinine (ure/creatinine)", 0, LAB, [], []),  # không có trị số kèm
    ("glucose (đường huyết)", 0, LAB, [], []),
    ("316", 0, VAL, [], []),
    ("lactate (acid lactat)", 0, LAB, [], []),
    ("1.3", 0, VAL, [], []),
    ("ua (urinalysis - tổng phân tích nước tiểu)", 0, LAB, [], []),
    # Cả chuỗi kết quả nước tiểu là một KẾT_QUẢ_XÉT_NGHIỆM (tiền lệ GT[63]:
    # "dương tính  với 182bạch cầuvài vi khuẩn (vi khuẩn), nitrite" gán 1 nhãn VAL).
    ("12 bạch cầu, không vi khuẩn, 1 hồng cầu, âm tính nitrite", 0, VAL, [], []),
    # --- "Kết quả chẩn đoán hình ảnh" ---
    ("chụp x-quang ngực", 0, LAB, [], []),
    # "dòng picc đã đặt": thiết bị/thủ thuật -> không gán.
    ("quá trình bệnh lý tim phổi cấp tính", 0, DX, [NEG], []),  # "không có ..."
    ("chụp x-quang bàn chân phải", 0, LAB, [], []),
    ("gãy xương", 0, DX, [NEG], ["S92.9"]),  # x-quang bàn chân -> gãy xương bàn chân
    ("viêm xương tủy", 0, DX, [NEG], ["M86.9"]),
    # "Bên phải âm tính với huyết khối tĩnh mạch sâu (DVT)" -> loại trừ DVT.
    # Ở đây là TÊN BỆNH được loại trừ (khác GT[94] nơi "huyết khối" là tên chỉ số
    # hematocrit dịch sai) -> CHẨN_ĐOÁN + isNegated. I82.4 không có trong danh mục,
    # dùng I80.2 (viêm/tắc tĩnh mạch huyết khối tĩnh mạch sâu chi dưới).
    ("huyết khối tĩnh mạch sâu (DVT)", 0, DX, [NEG], ["I80.2"]),
]

GT[117] = [  # 657c ×1  88.txt — tư vấn bé 14 tháng ra mồ hôi nhiều + 2 dòng CĐHA của EHR khác
    # Bệnh nhân là CON của người hỏi -> isFamily (tiền lệ GT[12]/GT[113]).
    ("ra mồ hôi nhiều", 0, SYM, [FAM], []),
    # "Thiếu một số vi chất": chẩn đoán khả năng (nêu như 1 nguyên nhân có thể),
    # vẫn là khái niệm bệnh -> CHẨN_ĐOÁN. Tiền lệ GT[28] "Thiếu canxi và vitamin"
    # -> CHẨN_ĐOÁN. Mã chung cho thiếu dinh dưỡng không xác định: E63.9.
    ("Thiếu một số vi chất", 0, DX, [FAM], ["E63.9"]),
    # calcium/sắt/kẽm ở đây là VI CHẤT bị thiếu, nêu trong ngữ cảnh dinh dưỡng —
    # không phải thuốc đang điều trị -> không gán THUỐC (khác GT[58] nơi
    # "Vitamin B12" là chế phẩm bổ sung). Không gán.
    ("bệnh tiềm ẩn", ALL, DX, [FAM], []),  # 2 lần: "Mắc một bệnh tiềm ẩn chưa được
    # phát hiện" và "loại trừ một số bệnh tiềm ẩn" — bệnh chưa xác định, không có mã.
    # "dùng nhiều rau quả", "tắm nắng", "ăn uống nhiều loại thức ăn": lời khuyên lối
    # sống -> không gán. "khám bs nhi khoa": chuyên khoa -> không gán.
    # --- 2 dòng CĐHA của EHR khác ghép vào cuối ---
    # "ba stent mật kim loại đã được đặt": thiết bị/thủ thuật -> không gán.
    ("ổ dịch sau phẫu thuật", 0, DX, [], ["T81.8"]),  # biến chứng sau can thiệp
]

# ------------------------------------------------
# 3 block còn lại của file 88.txt (block 117 đã xong) -> gán TRỌN file.
# 88.txt = MỘT bệnh án đường mật (mục 1 tiền sử -> mục 2 HPI -> mục 3 đánh giá), bị
# chèn đoạn tư vấn "bé 14 tháng ra mồ hôi nhiều" vào giữa mục 3 (block 117 đã gán).
# Bệnh nhân: đã cắt ống mật chủ + cắt gan trái + nối gan-hỗng tràng vì nghi ung thư
# đường mật, đặt 3 stent đường mật; lần này vào vì run rẩy + sốt.
# Quy ước chốt cho file:
#  - Mục "1. Tiền sử bệnh nội khoa / Tiền sử phẫu thuật" -> isHistorical (tiền lệ
#    GT[13] cùng dạng mục, GT[9]/GT[87]).
#  - Mục "2. Tiền sử bệnh hiện tại" = HPI -> KHÔNG isHistorical (tiền lệ GT[225]/
#    GT[129]); nhưng các gạch đầu dòng dưới "Các sự kiện trước khi nhập viện" là
#    việc ĐÃ QUA -> isHistorical (tiền lệ GT[225]:1182).
#  - Phẫu thuật/thủ thuật/stent -> không gán, chỉ lấy chẩn đoán là LÝ DO mổ
#    (tiền lệ GT[13]:892 "ung thư tuyến đại tràng" = lý do mổ, và GT[117] cùng
#    file này đã bỏ "ba stent mật kim loại đã được đặt").
#  - Cùng bệnh nhân/cùng nguồn EHR với block 201 (5.txt) và GT[27] (5.txt) -> dùng
#    lại C24.0 của GT[27]:4291 cho ung thư đường mật.
# ------------------------------------------------

DONE_EMPTY.add(306)  # 62c ×1  88.txt — đúng 2 dòng tiêu đề:
# "3. Đánh giá tại bệnh viện" + "Kết quả chụp chẩn đoán hình ảnh" -> tiêu đề mục và
# tiêu đề nhóm, không có khái niệm nào (tiền lệ GT[22]/GT[142]:1941 cùng 2 tiêu đề).

GT[208] = [  # 286c ×1  88.txt — mục "1. Tiền sử bệnh nội khoa / Tiền sử phẫu thuật"
    # "cắt bỏ ống dẫn mật chủ", "cắt bỏ phân đoạn bên trái gan", "phẫu thuật nối ống
    # gan - hỗng tràng", "can thiệp chụp đường mật", "đặt 3 stent đường mật lưu dài
    # hạn": thủ thuật/thiết bị -> không gán (tiền lệ GT[13] bỏ "Phẫu thuật mở cắt nối
    # trực tràng/đại tràng sigma"; GT[117] CÙNG FILE bỏ "ba stent mật kim loại").
    ("ung thư đường mật", 0, DX, [HIST], ["C24.0"]),  # lý do mổ -> vẫn gán, isHistorical
    # (tiền lệ GT[13]:892 "ung thư tuyến đại tràng" + HIST cũng là lý do mổ).
    # C24.0 "U ác tính ở ống mật ngoài gan" — dùng lại mã GT[27]:4291 đã chọn cho
    # "ung thư biểu mô tuyến" của CÙNG bệnh nhân/cùng nguồn EHR ở 5.txt. Danh mục
    # KHÔNG có mục tên "ung thư đường mật" (đã tra `names`), nhóm C24 là
    # "u ác tính ở phần khác của đường mật" -> C24.0 khớp nhất (đã mổ ống mật chủ).
    # Cắt hậu tố "không thể cắt bỏ" khỏi bề mặt: đây là thuộc tính KHẢ NĂNG CẮT BỎ
    # (unresectable), không phải phần tên bệnh — cùng loại với "vị trí – mức độ" bị
    # cắt ở GT[280] và "≥1,5 cm" bị cắt ở GT[276]. Khi gán block 201 (5.txt, cùng
    # câu bản dịch khác) phải cắt y như vậy.
    # "nghi ngờ": đề chỉ có 3 assertion, không có "nghi ngờ" -> vẫn gán DX, không
    # thêm assertion nào ngoài HIST (tiền lệ GT[205]/GT[225] "nghi ngờ").
]

GT[161] = [  # 440c ×1  88.txt — mục "2. Tiền sử bệnh hiện tại" + "Các sự kiện trước khi nhập viện"
    # "Thời điểm khởi phát triệu chứng: Đêm trước khi nhập viện": mốc thời gian
    # -> không gán (tiền lệ GT[79] "Thời gian: 48 giờ qua").
    # --- "Triệu chứng hiện tại" -> lần này -> KHÔNG assertion ---
    ("run rẩy", 0, SYM, [], []),
    ("sốt", 0, SYM, [], []),  # "run rẩy kèm sốt kèm theo sốt" — lỗi dịch lặp cụm,
    ("sốt", 1, SYM, [], []),  # gán CẢ HAI lần (tiền lệ GT[132]:2164 "âm tính âm tính"
    # lỗi dịch lặp vẫn gán từng lần, GT[132] "túi mật giãn" lặp cũng gán 2 bề mặt).
    # Tách "run rẩy" và "sốt" thành 2 bề mặt thay vì giữ trọn cụm: đây là 2 triệu
    # chứng nối bằng "kèm", không có từ bổ nghĩa chung — khác GT[60]/GT[79]
    # "chủ quan sốt và run rẩy" nơi "chủ quan" bổ nghĩa cho cả hai nên giữ trọn.
    # --- "Các sự kiện trước khi nhập viện" -> đã qua -> isHistorical (GT[225]) ---
    ("sốt", 2, SYM, [HIST], []),  # "Gần đây nhập viện vì sốt"
    ("ổ dịch trong ổ bụng", 0, DX, [HIST], ["T81.8"]),  # cùng ổ dịch mà GT[117] CÙNG
    # FILE gán "ổ dịch sau phẫu thuật" -> T81.8 (biến chứng khác do can thiệp): bệnh
    # nhân vừa mổ nối gan-hỗng tràng nên ổ dịch ổ bụng là biến chứng sau mổ. Danh mục
    # không có mục nào tên "ổ dịch" (đã tra `names`).
    ("áp xe", 0, DX, [HIST], []),  # "được cho là áp xe" — chẩn đoán nghi ngờ, vẫn gán
    # DX (tiền lệ GT[205]/GT[22] "lo ngại về"). candidates RỖNG: danh mục chỉ có áp xe
    # THEO VỊ TRÍ (K63.0 ruột, K75.0 gan, D73.3 lách, L02.x da…), không có mã áp xe ổ
    # bụng/không xác định; bề mặt không nói vị trí nên không chọn được mã nào
    # (tiền lệ GT[111] "tổn thương điểm mạch" -> DX candidates rỗng).
    ("kháng sinh tĩnh mạch", 0, DRUG, [HIST], []),  # nhóm thuốc, RxNorm không có
    # concept -> candidates rỗng (tiền lệ GT[97]:2931 cùng bề mặt).
    ("Augmentin", 0, DRUG, [HIST], ["151392"]),  # RxNorm BN Augmentin (tiền lệ
    # GT[47]:3640 cùng mã). "đường uống trong 10 ngày": đường dùng/thời gian
    # -> không gán (tiền lệ GT[297]/GT[316]).
    # "Điều trị bằng ... trong thời gian nằm viện", "Ra viện với đơn": thủ tục nằm
    # viện/ra viện -> không gán.
    # "Tình trạng ổn định ở nhà cho đến đêm trước khi nhập viện": trạng thái BÌNH
    # THƯỜNG -> không gán (quy ước "phát hiện bình thường không gán").
]

GT[124] = [  # 634c ×1  2.txt — bài giảng về bệnh Kawasaki (cùng nguồn với GT[104])
    # Bài phổ biến kiến thức, không có bệnh nhân cụ thể -> không assertion
    # (tiền lệ GT[104] cùng file 2.txt).
    ("Bệnh Kawasaki", 0, DX, [], ["M30.3"]),  # chứa lần [0] của "Kawasaki"
    ("sốt cấp kéo dài", 0, SYM, [], []),
    ("phát ban toàn thân", 0, SYM, [], []),
    ("viêm lan tỏa hệ mạch máu nhỏ và vừa", 0, DX, [], ["I77.6"]),  # viêm động mạch
    # "bác sĩ Tomisaku Kawasaki" (lần [1] của "Kawasaki") là TÊN NGƯỜI -> không gán.
    # "trẻ dưới 5 tuổi", "nhóm bú mẹ", "Trẻ trai/trẻ gái": dịch tễ -> không gán.
    ("viêm tim", 0, DX, [], ["I51.4"]),  # viêm cơ tim
    ("phình giãn động mạch vành", 0, DX, [], ["I25.4"]),
    ("đột tử", 0, DX, [], ["I46.1"]),  # đột tử do tim trong bối cảnh Kawasaki
    ("nhồi máu cơ tim", 0, DX, [], ["I21.9"]),
    ("hẹp tắc mạch vành", 0, DX, [], ["I25.1"]),
    ("suy tim", 0, DX, [], ["I50.9"]),
]

GT[109] = [  # 711c ×1  92.txt — "2. Bệnh sử hiện tại" EHR sốt cao/viêm tuỷ xương + 1 dòng trứng cá
    ("sốt cao", 0, SYM, [], []),  # lý do nhập viện
    # --- "Cách ngày vào viện 2 tuần" = lần nhập viện TRƯỚC -> isHistorical ---
    ("hạ huyết áp", 0, DX, [HIST], ["I95.9"]),
    ("nhiễm trùng huyết", 0, DX, [HIST], ["A41.9"]),
    ("kháng sinh", 0, DRUG, [HIST], []),  # nhóm thuốc, không tên cụ thể
    ("vancozosynbactrim", 0, DRUG, [HIST], []),  # lỗi dịch dính 3 tên: vanco+zosyn+bactrim
    ("bệnh viêm tuỷ xương", 0, DX, [HIST], ["M86.9"]),
    ("zosyn", 1, DRUG, [HIST], ["74170"]),  # [0] nằm trong "vancozosynbactrim"
    ("kháng sinh", 1, DRUG, [NEG, HIST], []),  # "dừng tất cả kháng sinh"
    ("viêm tủy xương mãn tính", 0, DX, [HIST], ["M86.6"]),
    ("thuốc kháng sinh", 0, DRUG, [NEG, HIST], []),  # "không sử dụng thuốc kháng sinh"
    # --- "Sáng cùng ngày vào viện" -> hiện tại, không HIST ---
    ("sốt cao 39.7 độ C", 0, SYM, [], []),
    # --- "Tình trạng lúc vào" ---
    ("Cảm giác khát nước", 0, SYM, [], []),
    ("Da khô, nếp véo da mất chậm", 0, SYM, [], []),
    # "Không ngực": lỗi dịch mất chữ (đau ngực?), không đủ nghĩa -> không gán.
    ("khó thở", 0, SYM, [NEG], []),  # "không khó thở"
    ("Đau bụng", 0, SYM, [], []),
    ("đau hông từng cơn", 0, SYM, [], []),
    ("Hạ huyết áp", 1, DX, [], ["I95.9"]),  # lần này là hiện tại
    ("Mạch nhanh", 0, SYM, [], []),
    ("Tim nhịp nhanh đều", 0, SYM, [], []),
    # --- 1 dòng mở đầu bài giảng trứng cá ghép vào cuối ---
    ("Trứng cá", 0, DX, [], ["L70.9"]),
]

# ------------------------------------------------
# 3 block còn lại của file 92.txt (block 109 đã xong) -> gán TRỌN file.
# 92.txt = MỘT EHR nhiễm trùng huyết đường vào tiết niệu trên bệnh nhân liệt hai chi
# dưới (bàng quang thần kinh, sonde tiểu lưu, loét tì đè độ IV, viêm tuỷ xương mãn),
# bị chèn 2 mẩu của bài giảng TRỨNG CÁ: 1 dòng ở cuối block 109 và dòng
# "Tăng sản tuyến bã nhờn" ở đầu block 227.
# Thứ tự đọc: 185 (mục 1) -> 109 (mục 2) -> 227 (cận lâm sàng + chẩn đoán) -> 282 (điều trị).
# Quy ước chốt:
#  - Block 185 nằm dưới "1. Tiền sử bệnh" + "Thuốc đã dùng trước đây" -> isHistorical
#    toàn block (tiền lệ GT[256], GT[187], GT[14]).
#  - CÙNG BỆNH NHÂN với GT[109] -> DÙNG LẠI Y NGUYÊN mã của GT[109] cho các bệnh
#    trùng (M86.6 viêm tuỷ xương mãn, A41.9 nhiễm trùng huyết) để hai block không lệch.
#  - Block 227/282 là lần nhập viện HIỆN TẠI -> KHÔNG assertion.
# ------------------------------------------------

GT[185] = [  # 368c ×1  92.txt — mục "1. Tiền sử bệnh" + "Thuốc đã dùng trước đây"
    # "1. Tiền sử bệnh", "Thuốc đã dùng trước đây": tiêu đề mục -> không gán (GT[142]).
    ("viêm tủy xương mãn tính", 0, DX, [HIST], ["M86.6"]),  # y như GT[109] cùng file
    # (M86.6 "Viêm xương tủy mạn tính khác"). `names` KHÔNG có "viêm tủy xương mãn tính"
    # -> đã quét `entries` để xác nhận.
    ("bàng quang thần kinh", 0, DX, [HIST], ["N31.9"]),  # y như GT[267]
    # "gây biến chứng": từ nối nhân-quả -> không gán.
    ("liệt hai chi dưới", 0, DX, [HIST], ["G82.2"]),  # y như GT[267]
    ("loét tì đè giai đoạn IV mãn tính", 0, DX, [HIST], ["L89.3"]),  # L89.3 "Loét do tì
    # đè, độ IV" — `names` không có "loét tì đè", tra bằng quét `entries`. GIỮ "giai đoạn
    # IV" trong bề mặt vì L89.0–L89.3 phân theo ĐỘ loét -> giai đoạn là phần định danh mã,
    # cùng quy tắc với "suy thận mạn giai đoạn 5" -> N18.5 ở GT[311]; khác "mức độ trung
    # bình" bị cắt ở GT[219] (mức độ không đổi mã). Giữ cả "mãn tính" vì nằm liền cuối cụm.
    # "đặt lưu sonde tiểu": THIẾT BỊ/thủ thuật -> không gán (tiền lệ GT[102] "Còn sonde
    # tiểu"). Bản dịch để 4 dấu cách trước "gây", không ảnh hưởng needle.
    ("nhiễm khuẩn đường tiết niệu tái phát", 0, DX, [HIST], ["N39.0"]),  # N39.0 "Nhiễm
    # trùng đường tiết niệu, vị trí không xác định" — tiền lệ GT[102]/GT[46]/GT[65].
    # GIỮ "tái phát": bổ nghĩa trực tiếp cho đúng cụm này (tiền lệ GT[78] "đau hạ sườn
    # phải tái phát, ngày càng nặng hơn"), khác GT[318] nơi "tái phát" đứng sau 2 chẩn
    # đoán nối bằng dấu phẩy nên không thuộc riêng bề mặt nào.
    ("vancozosyn", 0, DRUG, [NEG, HIST], []),  # lỗi dịch dính 2 tên vanco+zosyn, y như
    # kiểu "vancozosynbactrim" ở GT[109] -> RxNorm không có concept, candidates rỗng.
    # NEG vì "nhưng hiện tại đang dừng" (tiền lệ GT[16] "đã hết thuốc", GT[60]/GT[79]
    # "ngừng thuốc giảm đau opioid", và chính GT[109] "dừng tất cả kháng sinh").
    # "khám chuyên khoa Truyền nhiễm": chuyên khoa/thủ tục -> không gán.
    ("bactrim", 0, DRUG, [HIST], ["151399"]),  # RxNorm BN Bactrim = 151399 (đã tra).
    # Không NEG: đây là thuốc ĐANG dùng, chỉ HIST vì nằm trong mục "Thuốc đã dùng
    # trước đây" (assertion theo MỤC, quy ước chốt ở GT[256]/GT[289]).
    ("nhiễm khuẩn đường tiết niệu", 1, DX, [HIST], ["N39.0"]),  # lần [0] nằm trong bề
    # mặt "…tái phát" ở trên. "để điều trị X" -> X vẫn là bệnh có mặt, gán như thường.
]

GT[227] = [  # 212c ×1  92.txt — 1 dòng bài giảng trứng cá + cận lâm sàng + dòng chẩn đoán
    ("Tăng sản tuyến bã nhờn", 0, DX, [], []),  # mẩu bài giảng trứng cá ghép vào, gán
    # y như GT[263] cùng bề mặt: không có mã ICD -> candidates rỗng nhưng VẪN gán.
    ("Xquang ngực thẳng", 0, LAB, [], []),  # tiền lệ GT[92] "Chụp Xquang ngực thẳng",
    # GT[137] "XQ" — viết tắt/không có chữ "chụp" vẫn là TÊN_XÉT_NGHIỆM.
    ("thâm nhiễm", 0, DX, [NEG], []),  # "không thấy thâm nhiễm". Bề mặt KHÔNG lấy chữ
    # "không thấy" — theo đúng GT[109] cùng file gán ("khó thở", NEG) cho "không khó
    # thở"; khác GT[68] lấy trọn "không có hình ảnh tổn thương viêm cấp tính" (ở đó
    # "hình ảnh tổn thương" không đứng riêng được). Candidates rỗng: mã duy nhất chứa
    # "thâm nhiễm" là L98.6 (rối loạn thâm nhiễm ở DA) — sai vị trí, không dùng
    # (quy ước không thêm mã "cho chắc" vì candidates chấm bằng Jaccard).
    # "Thủ thuật:", "Đặt ống thông tĩnh mạch trung tâm": tiêu đề + thủ thuật -> không
    # gán (GT[117]/GT[208]/GT[201]).
    ("svo2", 0, LAB, [], []),  # độ bão hoà oxy máu tĩnh mạch trung tâm, tên phép đo
    ("82", 0, VAL, [], []),  # trị số đo được -> VAL dù trơ số, không đơn vị (GT[115])
    ("cvp", 0, LAB, [], []),  # áp lực tĩnh mạch trung tâm; "đo cvp" -> phần tên là "cvp"
    ("6", 0, VAL, [], []),
    ("nhiễm trùng huyết đường vào tiết niệu", 0, DX, [], ["A41.9"]),  # A41.9 "Nhiễm
    # trùng hệ thống, không xác định" — bảng ICD KHÔNG có tên nào chứa "nhiễm trùng
    # huyết" (đã quét `entries`), nên dùng A41.9 y như GT[109] cùng bệnh nhân. GIỮ
    # "đường vào tiết niệu" (ngõ vào nằm liền trong tên chẩn đoán, tiền lệ GT[94]
    # "xẹp phổi thùy dưới phải do chèn ép" giữ cả nguyên nhân). Không thêm N39.0 dù
    # có chữ "tiết niệu": 1 khái niệm 1 mã đúng, thêm mã làm giảm Jaccard.
    ("viêm tủy xương mãn tính", 0, DX, [], ["M86.6"]),  # index 0: chỉ số đếm TRONG
    # block, block 227 chỉ có 1 lần (lần ở block 185 là block khác, không cộng dồn).
]

GT[282] = [  # 98c ×1  92.txt — mục "Điều trị"
    # "Điều trị:": tiêu đề mục -> không gán.
    # "Truyền dịch": THỦ THUẬT truyền dịch, không nêu tên dịch -> không gán (tiền lệ
    # GT[142]/GT[94]/GT[45] "Truyền dịch tĩnh mạch").
    # "4000 ml": thể tích/liều -> không gán (quy ước bề mặt thuốc chỉ lấy tên).
    ("NS 0.9 %", 0, DRUG, [], ["9863"]),  # NS = normal saline (natri clorid 0.9%),
    # RxNorm IN sodium chloride = 9863. Dịch truyền CÓ TÊN thì gán DRUG — tiền lệ
    # GT[133] ("Glucose 5%" -> 4850). Bề mặt giữ nguyên khoảng trắng trước "%" như
    # corpus viết (WER chấm đúng chuỗi literal).
    ("Kháng sinh", 0, DRUG, [], []),  # nhóm thuốc, không tên cụ thể -> candidates rỗng
    # (tiền lệ GT[109] cùng file, GT[97]).
    ("Cefepim", 0, DRUG, [], ["20481"]),  # RxNorm IN cefepime = 20481 (không có BN nào
    # khớp bề mặt này) — quy ước ưu tiên BN, không có BN thì dùng IN.
    ("Vancomycin", 0, DRUG, [], ["11124"]),  # y như GT[70] cùng mã
    # "truyền tĩnh mạch": đường dùng -> không gán (GT[297]/GT[316]).
]

GT[110] = [  # 710c ×1  18.txt — "3. Đánh giá tại bệnh viện" EHR viêm túi mật cấp
    # Các dòng ghi "(lần nhập viện trước)" -> isHistorical; TÊN_XÉT_NGHIỆM và
    # KẾT_QUẢ_XÉT_NGHIỆM không được mang assertion nên vẫn để rỗng.
    ("lipase", 0, LAB, [], []),
    ("623", 0, VAL, [], []),
    ("tăng men gan nhẹ", 0, SYM, [HIST], []),  # tiền lệ GT[37]: tăng men gan = TRIỆU_CHỨNG
    ("tbr", 0, LAB, [], []),  # total bilirubin
    ("1.0", 0, VAL, [], []),
    # "các xét nghiệm khác": nêu chung, không có tên -> không gán.
    ("cấy máu", 0, LAB, [], []),
    ("dương tính", 0, VAL, [], []),  # tiền lệ cặp "cấy máu"/"dương tính" ở GT[78]
    ("GPRs", 0, DX, [], ["B96.8"]),  # trực khuẩn Gram dương phân lập được
    ("siêu âm vùng gan mật", ALL, LAB, [], []),  # 2 lần (lần trước + hiện tại)
    ("sỏi mật", 0, DX, [HIST], ["K80.2"]),
    ("viêm túi mật", 0, DX, [NEG, HIST], ["K81.9"]),  # "không có viêm túi mật" (lần trước)
    ("sỏi ống mật", 0, DX, [NEG, HIST], ["K80.5"]),
    ("chụp ct bụng chậu", 0, LAB, [], []),
    ("túi mật căng to", 0, DX, [], ["K82.8"]),
    ("dịch quanh túi mật", 0, DX, [], []),
    ("viêm túi mật cấp", ALL, DX, [], ["K81.0"]),  # 2 lần: gợi ý trên SA + kết luận
]

# ---------------------------------------------------------------------------
# File 18.txt = ĐUÔI của CHÍNH bài giảng "BỆNH MẠCH VÀNH (CAD)" ở file 26.txt
# (mục 4 "Cận lâm sàng" -> mục 5 "Điều trị" -> mục 6 "Dự phòng"), bị ghép bệnh án
# viêm túi mật cấp vào từ dòng 55 trở đi. Hai block bệnh án (78, 110) đã gán ở đợt
# trước; đợt này gán 10 block bài giảng còn lại.
# Quy ước chốt cho cả file: DÙNG LẠI Y NGUYÊN quyết định của 26.txt (13 block, đã
# gán trọn) để không tự mâu thuẫn với chính nguồn:
#  - Bài giảng, không có bệnh nhân cụ thể -> KHÔNG assertion (tiền lệ GT[299]…GT[322]).
#  - Mã dùng lại: "bệnh mạch vành" -> I25.9 (GT[299]/GT[197]), "hẹp" mạch vành ->
#    I25.1 (GT[197]/GT[232]/GT[140]), "nhồi máu (cơ tim)" -> I21.9 (GT[197]/GT[140]),
#    "thiếu máu cơ tim" -> I25.9 (GT[140]/GT[76]).
#  - Tiêu đề mục ("Cận lâm sàng", "Điều trị", "Mục tiêu", "Điều trị nội khoa",
#    "Thuốc nền tảng", "Can thiệp – phẫu thuật", "Dự phòng tiên phát"): không gán
#    (tiền lệ GT[136]/GT[140]; riêng tiêu đề TRÙNG tên bệnh thì gán, như
#    "Dự phòng bệnh mạch vành" ở đây và "Đau thắt ngực" ở GT[233]).
#  - Tên xét nghiệm/thăm dò -> TÊN_XÉT_NGHIỆM; PHÁT HIỆN đọc được trên thăm dò đó
#    -> KẾT_QUẢ_XÉT_NGHIỆM nếu là mô tả hình/sóng (tiền lệ GT[76] "ST chênh xuống"
#    -> VAL), -> CHẨN_ĐOÁN nếu là một trạng thái bệnh lý (tiền lệ GT[92]/GT[47]).
#  - Thủ thuật/can thiệp (PCI, CABG, nong bóng, đặt stent, "Quyết định can thiệp")
#    -> KHÔNG gán, chỉ lấy khái niệm bệnh trong câu (tiền lệ GT[117] bỏ "ba stent
#    mật kim loại đã được đặt", GT[13] bỏ phẫu thuật cắt đại tràng).
#  - Cụm trong ngoặc là TÊN TIẾNG ANH của chính nhãn ("(ECG)", "(PCI)", "(CABG)")
#    -> không gán riêng, theo tiền lệ GT[299] "(Coronary Artery Disease – CAD)";
#    còn cụm trong ngoặc là NHẬN ĐỊNH ("(tiêu chuẩn vàng)", "(chẩn đoán nhồi máu)",
#    "(ổn định mảng xơ vữa)", "(chưa mắc bệnh)") -> không gán, tiền lệ GT[195]
#    "(quan trọng nhất để đánh giá động mạch vành)" và GT[140] "(nguy hiểm nhất)".
#  - Dãy sao = tên thuốc bị mask: mỗi ĐỘ DÀI là một bề mặt riêng, THUỐC, candidates
#    rỗng (tiền lệ GT[76]/GT[176]/GT[297]; matcher chỉ khớp trọn run sao).
# ---------------------------------------------------------------------------

DONE_EMPTY.add(331)  # 12c ×1  18.txt — đúng 1 dòng tiêu đề "Cận lâm sàng":
# tiêu đề mục, không có khái niệm y khoa -> giống block 0 ("Câu hỏi từ người dùng:").

GT[296] = [  # 74c ×1  18.txt — mục cận lâm sàng: điện tâm đồ
    ("Điện tâm đồ", 0, LAB, [], []),  # tiền lệ GT[186]/GT[143]/GT[89]/GT[68] cùng bề
    # mặt -> LAB. "(ECG)" là tên tiếng Anh của chính nhãn -> không gán riêng
    # (tiền lệ GT[299]); khác GT[195] "ECG điện tâm đồ" nơi 2 tên DÍNH thành 1 cụm.
    # 3 dòng dưới là các HÌNH THÁI đọc trên điện tâm đồ -> KẾT_QUẢ_XÉT_NGHIỆM,
    # theo tiền lệ GT[76] gán "ST chênh xuống" là VAL (kết quả của thăm dò tim).
    ("ST chênh lên / chênh xuống", 0, VAL, [], []),  # giữ TRỌN cụm 2 vế gạch chéo
    # thành 1 bề mặt (tiền lệ GT[22] "Bệnh thủy đậu/Zona", GT[63] "buồn nôn/nôn").
    ("Sóng T đảo", 0, VAL, [], []),
    ("Q bệnh lý", 0, VAL, [], []),  # sóng Q bệnh lý — dấu hiệu nhồi máu cũ trên ECG
]

GT[312] = [  # 57c ×1  18.txt — mục cận lâm sàng: men tim
    # SỬA (rà lại quyết định rủi ro): BỎ nhãn ("Men tim", LAB). Block này là:
    #     Men tim
    #      • Troponin I/T ↑ (chẩn đoán nhồi máu)
    #      • CK-MB ↑
    # "Men tim" đứng một dòng riêng, bên dưới là 2 xét nghiệm con -> đúng dạng TIÊU ĐỀ
    # NHÓM, y như "Sinh hóa & Men tim:" ở GT[136] mà tôi đã không gán. Khác với GT[195]
    # "• Men gan, albumin" — chỗ đó nó nằm ngang hàng trong danh sách chỉ định
    # ("Công thức máu, CRP, máu lắng" / "Xét nghiệm nước tiểu" / "Cấy máu...") nên là tên
    # xét nghiệm thật. Phân biệt: có xét nghiệm con thụt vào bên dưới thì là tiêu đề.
    ("Troponin I/T", 0, LAB, [], []),  # tiền lệ GT[63]/GT[17] "troponin" -> LAB;
    # giữ trọn "I/T" (2 isoform của cùng xét nghiệm) như GT[136] giữ "(aPTT / TCK)".
    ("CK-MB", 0, LAB, [], []),
    # Mũi tên "↑" đứng một mình: kết quả bằng KÝ HIỆU, không có trị số -> không gán
    # VAL (tiền lệ GT[232] "tăng" đứng một mình cũng không gán).
    ("nhồi máu", 0, DX, [], ["I21.9"]),  # "(chẩn đoán nhồi máu)" — bối cảnh men tim
    # -> nhồi máu CƠ TIM, dùng lại I21.9 của GT[197]/GT[140]. Cụm trong ngoặc ở đây
    # là MỤC ĐÍCH xét nghiệm nhưng có nêu TÊN BỆNH -> vẫn lấy tên bệnh làm bề mặt
    # (tiền lệ GT[182] lấy "(cho rung nhĩ)", GT[14] lấy chẩn đoán trong cụm mô tả).
]

GT[301] = [  # 69c ×1  18.txt — mục cận lâm sàng: siêu âm tim
    ("Siêu âm tim", 0, LAB, [], []),  # tiền lệ GT[54]/GT[195]
    ("Rối loạn vận động vùng", 0, DX, [], ["I25.5"]),  # phát hiện trên siêu âm tim là
    # một trạng thái bệnh lý -> CHẨN_ĐOÁN (tiền lệ GT[92] "Buồng thất trái giãn",
    # "chức năng tâm thu thất trái giảm nhiều"; GT[47] "dị tật cố định vùng trước
    # vách"). Danh mục KHÔNG có mục nào tên "rối loạn vận động vùng" -> chọn I25.5
    # "Bệnh lý cơ tim do thiếu máu cục bộ" vì đây là dấu hiệu vùng cơ tim mất vận
    # động do thiếu máu, đúng bối cảnh bài CAD. Đã loại I51.9/I51.8 (bệnh tim không
    # xác định — mất thông tin nguyên nhân vành) và I50.1 (dùng cho RỐI LOẠN CHỨC
    # NĂNG thất trái ở GT[47], không phải vận động vùng).
    # ĐÃ RÀ LẠI: giữ I25.5. Kiểm bối cảnh cả file 18.txt — các chẩn đoán khác là "nhồi máu"
    # I21.9, "thiếu máu cơ tim" I25.9, "hẹp" I25.1, "Dự phòng bệnh mạch vành" I25.9. Đây
    # đúng là ca mạch vành, nên suy luận nguyên nhân thiếu máu cục bộ là có căn cứ trong
    # block chứ không phải tôi tự thêm. Không có mã nào sát hơn trong danh mục.
    # "Đánh giá chức năng thất trái": việc cần LÀM của siêu âm, chưa phải phát hiện
    # -> không gán (tiền lệ GT[195] "(quan trọng nhất để đánh giá động mạch vành)"
    # và GT[155] "đánh giá thần kinh" đều không gán).
]

GT[305] = [  # 63c ×1  18.txt — mục cận lâm sàng: nghiệm pháp gắng sức
    ("Nghiệm pháp gắng sức", 0, LAB, [], []),  # tiền lệ GT[76] cùng bề mặt -> LAB
    ("thiếu máu cơ tim", 0, DX, [], ["I25.9"]),  # tiền lệ GT[140] "Thiếu máu cơ tim"
    # -> I25.9 và GT[76] "thiếu máu cơ tim cục bộ" -> I25.9.
    # Cắt đuôi "khi gắng sức" khỏi bề mặt: đây là ĐIỀU KIỆN xuất hiện, cùng loại với
    # "Xảy ra khi gắng sức" mà GT[308] không gán; bề mặt chỉ lấy tên bệnh (quy ước
    # cắt hậu tố, tiền lệ GT[140] "Sốt ≥5 ngày" -> "Sốt").
    # "Phát hiện": động từ -> không gán.
]

GT[280] = [  # 99c ×1  18.txt — mục cận lâm sàng: chụp mạch vành + tiêu đề "Điều trị"
    ("Chụp mạch vành", 0, LAB, [], []),  # tiền lệ GT[47] "Chụp động mạch vành" -> LAB.
    # "(tiêu chuẩn vàng)": nhận định giá trị -> không gán (tiền lệ GT[140]
    # "(nguy hiểm nhất)", GT[195] "(quan trọng nhất …)").
    ("hẹp", 0, DX, [], ["I25.1"]),  # "Xác định vị trí – mức độ hẹp": bối cảnh chụp
    # mạch vành -> hẹp động mạch vành, dùng lại I25.1 của GT[197] "hẹp hoặc tắc các
    # động mạch vành" / GT[232] "hẹp lòng mạch" / GT[140] "Hẹp – tắc động mạch vành".
    # Bề mặt chỉ lấy "hẹp": "vị trí" và "mức độ" là THUỘC TÍNH cần xác định, không
    # phải phần tên bệnh (quy ước cắt hậu tố/tiền tố đo lường, tiền lệ GT[276]
    # "Hạch cổ to ≥1,5 cm" -> "Hạch cổ to").
    # "Quyết định can thiệp": can thiệp/thủ thuật -> không gán (tiền lệ GT[117]).
    # "Điều trị": tiêu đề mục -> không gán.
]

GT[293] = [  # 79c ×1  18.txt — mục điều trị: mục tiêu điều trị
    # "Mục tiêu": tiêu đề -> không gán.
    ("đau", 0, SYM, [], []),  # "Giảm đau" — bề mặt chỉ lấy tên triệu chứng, bỏ động
    # từ "Giảm" (tiền lệ GT[63]/GT[33] gán "đau" trơ làm TRIỆU_CHỨNG; GT[172] gán
    # "stress" trong "Giảm stress").
    ("nhồi máu", 0, DX, [], ["I21.9"]),  # "Ngăn nhồi máu" — bối cảnh CAD -> NMCT,
    # dùng lại I21.9. KHÔNG isNegated: đây là MỤC TIÊU ĐIỀU TRỊ của bài giảng, không
    # phải biến chứng nêu ra để phòng cho một bệnh nhân cụ thể — tiền lệ GT[140] liệt
    # kê biến chứng Kawasaki "có thể gây" mà không isNegated, và quy ước "bài giảng
    # không assertion" của chính file 26.txt. (Khác GT[106]/GT[172] nơi có người hỏi
    # cụ thể nên "để tránh …"/"Không hút thuốc" mới thành isNegated.)
    # "Cải thiện tưới máu tim": tưới máu tim BÌNH THƯỜNG là đích cần đạt, không phải
    # khái niệm bệnh -> không gán (khác GT[197] "giảm tưới máu cơ tim" là trạng thái
    # bệnh lý nên mới gán).
    ("tử vong", 0, SYM, [], []),  # "Giảm tử vong" — tiền lệ GT[30]/GT[118]/GT[120]/
    # GT[33] đều gán "tử vong" là TRIỆU_CHỨNG.
]

GT[252] = [  # 150c ×1  18.txt — mục điều trị nội khoa: 7 tên thuốc bị mask
    # "Điều trị nội khoa", "Thuốc nền tảng": tiêu đề mục -> không gán.
    # 7 dãy sao = 7 tên thuốc bị mask, ĐỘ DÀI KHÁC NHAU -> 7 bề mặt riêng, mỗi dãy
    # đúng 1 lần trong block (đã kiểm bằng --occ). candidates rỗng vì không suy ra
    # được tên thuốc (tiền lệ GT[76] 5 dãy, GT[176] 2 dãy "độ dài khác -> nhãn
    # riêng", GT[297] 29 sao, GT[118] 17 sao).
    ("*******", 0, DRUG, [], []),  # 7 sao
    ("***********", 0, DRUG, [], []),  # 11 sao
    ("******", 0, DRUG, [], []),  # 6 sao — "(ổn định mảng xơ vữa)" là tác dụng, và
    # "mảng xơ vữa" là BƯỚC CƠ CHẾ -> không gán (quy ước chốt ở GT[232] cùng bài).
    ("*********", 0, DRUG, [], []),  # 9 sao
    ("*************", 0, DRUG, [], []),  # 13 sao
    ("*****************", 0, DRUG, [], []),  # 17 sao
    ("***", 0, DRUG, [], []),  # 3 sao
]

GT[292] = [  # 81c ×1  18.txt — mục can thiệp: PCI
    # "Can thiệp – phẫu thuật": tiêu đề mục -> không gán.
    # "Can thiệp mạch vành qua da (PCI)", "Nong bóng", "Đặt stent": THỦ THUẬT
    # -> không gán, không có khái niệm bệnh nào trong câu để lấy (tiền lệ GT[117]
    # "ba stent mật kim loại đã được đặt", GT[106] "đặt shunt dẫn lưu tĩnh mạch cửa
    # qua da", GT[141] "Phẫu thuật cắt cụt chân"). Lưu ý KHÁC GT[91]
    # "stent mạch vành" -> Z95.5: ở đó là TIỀN SỬ ĐÃ ĐẶT của một bệnh nhân (mã Z =
    # trạng thái có dụng cụ), còn ở đây là tên phương pháp trong bài giảng.
    # -> Block không có khái niệm nào. Không dùng DONE_EMPTY vì cần ghi lại lý do,
    # nên khai danh sách rỗng tường minh.
]

GT[259] = [  # 137c ×1  18.txt — mục can thiệp: CABG + tiêu đề mục 6
    # "Phẫu thuật bắc cầu mạch vành (CABG)": thủ thuật -> không gán (như PCI ở
    # block 292). "Khi tổn thương nhiều nhánh, nặng": chỉ định/mức độ, "tổn thương
    # nhiều nhánh" là mô tả mức lan của bệnh chứ không phải tên bệnh -> không gán
    # (tiền lệ GT[140] không gán "Khoảng 25–30% trẻ không điều trị đúng cách";
    # khác GT[47] "bệnh ba thân động mạch vành nghiêm trọng" có chữ "bệnh" nên là
    # tên chẩn đoán).
    ("Dự phòng bệnh mạch vành", 0, DX, [], ["I25.9"]),
    # Tiêu đề mục nhưng CHỨA tên bệnh -> gán, và bề mặt lấy TRỌN cụm để bao lần
    # duy nhất của "bệnh mạch vành", tránh nhãn lồng (tiền lệ GT[140] "Phình giãn
    # động mạch vành" đã chứa "động mạch vành" nên không khai riêng, và GT[233]
    # gán tiêu đề "Đau thắt ngực" vì chính nó là tên bệnh). I25.9 theo GT[299].
    # "Dự phòng tiên phát (chưa mắc bệnh)": tiêu đề + nhận định -> không gán.
]

GT[111] = [  # 703c ×1  78.txt — 3 dòng khám hậu phẫu + bài giảng chảy máu mũi (2 nguồn ghép)
    ("ban đỏ ở vị trí phẫu thuật", 0, SYM, [], []),
    ("đau ấn vùng mổ", 0, SYM, [], []),
    ("sốt", 0, SYM, [NEG], []),  # "không sốt"
    # --- bài phổ biến kiến thức về chảy máu mũi -> không assertion
    # (tiền lệ GT[11]/GT[66]: bài giảng không có BN cụ thể).
    # "hắt hơi mạnh", "ngoáy mũi": hành vi/yếu tố khởi phát -> không gán.
    # "viêm nhiễm": quá chung, không phải tên bệnh cụ thể -> không gán.
    # "tổn thương điểm mạch": tổn thương giải phẫu do cơ chế, không có mã riêng
    # nhưng vẫn là khái niệm bệnh lý -> gán CHẨN_ĐOÁN, candidates rỗng.
    ("tổn thương điểm mạch", 0, DX, [], []),
    ("chảy máu mũi", 0, SYM, [], []),  # chứa lần [0] của "chảy máu"
    ("chảy máu ít", 0, SYM, [], []),  # chứa lần [1]
    ("chảy máu tái phát", ALL, SYM, [], []),  # 2 lần = lần [2] và [3] của "chảy máu"
    ("chảy máu", 4, SYM, [], []),  # "Khi chảy máu bạn đừng quá hốt hoảng"
    ("choáng", 0, SYM, [], []),
    ("nội soi mũi họng", 0, LAB, [], []),
]

# Block 294 (77c, 25.txt) = 77 ký tự ĐẦU của block 111, tức đúng 3 dòng
# "3. khám tại bệnh viện / Dấu hiệu lâm sàng / - ban đỏ ở vị trí phẫu thuật" (cùng mẩu
# EHR nhiễm trùng vết mổ bị ghép vào 2 file khác nhau). Đuôi rỗng -> chỉ thừa hưởng
# nhãn "ban đỏ ở vị trí phẫu thuật" của GT[111], 2 nhãn còn lại nằm ngoài 77 ký tự.
SHARE[294] = (111, 77)

# ---------------------------------------------------------------------------
# Hai block còn lại của file 78.txt (block 0 và 111 đã xong) -> gán TRỌN file.
# 78.txt = QA chảy máu cam (người hỏi TỰ kể về mình) + một mẩu EHR nhiễm trùng
# vết mổ ghép vào giữa + bài phổ biến kiến thức chảy máu mũi.
# Quy ước chốt: người hỏi tự kể -> KHÔNG isFamily (tiền lệ GT[4]/GT[105]).
# ---------------------------------------------------------------------------

GT[171] = [  # 418c ×1  78.txt — câu hỏi của người bệnh về chảy máu cam
    ("chảy máu cam", ALL, SYM, [], []),  # 2 lần: câu kể + câu hỏi lại. Lần [0] nằm
    # trong lỗi dịch dính chữ "bịchảy máu cam" -> chỉ lấy đúng phần tên triệu chứng
    # (tiền lệ GT[108] "lây nhiễm bệnh dạibao gồm" -> chỉ lấy "bệnh dại",
    # GT[182] "nhập viện gần đây vìviêm tụy" -> chỉ lấy "viêm tụy").
    # Gán TRIỆU_CHỨNG (không phải DX dù ICD có R04.0 "Chảy máu cam"): thống nhất
    # với GT[111] cùng file đã gán "chảy máu mũi" là SYM, và với chuỗi tiền lệ
    # chảy máu là SYM (GT[106] "chảy máu khó cầm", GT[76] các dòng chảy máu).
    ("chảy ở mũi bên phải", 0, SYM, [], []),  # vị trí chảy (tiền lệ GT[73] gán mô tả
    # vị trí/hướng lan của cơn đau, GT[240] "sau xương ức").
    ("choáng", 0, SYM, [], []),  # "người hơi choáng" — tiền lệ GT[111] cùng file
    ("chảy", 3, SYM, [], []),  # "cứ khô nóng là cháu chảy" = lần chảy máu thứ 3;
    # lần [0]/[2] nằm trong "chảy máu cam", lần [1] trong "chảy ở mũi bên phải".
    # "khô nóng" (thời tiết), "thức đêm muộn", "ngủ đủ": yếu tố môi trường/lối sống
    # -> không gán (tiền lệ GT[104] "hút thuốc lá thụ động", "môi trường ô nhiễm").
    # "dấu hiệu bệnh gì", "Phương pháp điều trị", "nghiêm trọng": hỏi chung, không
    # có tên bệnh -> không gán. "Câu trả lời của bác sĩ:": tiêu đề -> không gán.
]

GT[183] = [  # 373c ×1  78.txt — mẩu EHR nhiễm trùng vết mổ (diễn biến + hiện tại)
    # Block này là ĐUÔI 373c của block 40 (25.txt) — `SHARE` chỉ nhận TIỀN TỐ nên
    # phải gán tay, nhưng dùng lại Y NGUYÊN nhãn tương ứng của GT[40] để 2 file
    # không lệch nhau. Đối chiếu: 6 nhãn dưới = GT[40] các nhãn ban đỏ[3],
    # chóng mặt[0], ban đỏ[4], đau khi sờ nắn[3], chóng mặt[1], không sốt[0].
    ("ban đỏ", ALL, SYM, [], []),  # 2 lần: "ban đỏ lan rộng" + "ban đỏ xuất hiện
    # nhiểu ở vị trí phẫu thuật" (lỗi chính tả "nhiểu" của corpus). GT[40] khai rời
    # 2 lần vì ở đó có 5 lần; ở đây chỉ có 2 nên ALL gọn hơn, kết quả trùng khớp.
    # "lan rộng", "xuất hiện nhiểu ở vị trí phẫu thuật": mức độ/vị trí lan -> không
    # gán riêng, đúng như GT[40] chỉ lấy "ban đỏ" (khác GT[111] cùng file gán trọn
    # "ban đỏ ở vị trí phẫu thuật" — đó là nguồn EHR khác, giữ nguyên mỗi bên).
    ("chóng mặt", ALL, SYM, [], []),  # 2 lần, như GT[40]
    ("đau khi sờ nắn", 0, SYM, [], []),  # "đau khi sờ nắn vùng mổ" — GT[40] cũng chỉ
    # lấy "đau khi sờ nắn", bỏ "vùng mổ"/"trên vùng da".
    ("không sốt", 0, SYM, [NEG], []),  # giữ NGUYÊN bề mặt có chữ "không" theo
    # GT[40]:3750 cùng nguồn. (Khác GT[111] cùng file gán "sốt"+NEG — hai nguồn EHR
    # khác nhau, mỗi bên đã chốt riêng; census: 11/173 nhãn NEG giữ chữ phủ định
    # trong bề mặt, nên cả 2 cách đều có tiền lệ.)
    # "tái khám", "được chuyển đến Khoa Cấp cứu": chuyển tuyến/thủ tục -> không gán
    # (tiền lệ GT[40] cùng đoạn không gán, GT[143] "đến khám tại phòng khám").
    # "có các triệu chứng tương tự", "chưa phát hiện các triệu chứng toàn thân
    # khác": nhắc chung không tên -> không gán (tiền lệ GT[322] "yếu tố nguy cơ").
    # "Triệu chứng hiện tại": tiêu đề mục -> không gán.
]

GT[2] = [  # 248c ×3  41.txt, 59.txt, 60.txt — lời khuyên cuối bài tư vấn trứng cá
    # Lời khuyên chung cho người hỏi (chính họ là bệnh nhân) -> không assertion.
    ("da mụn", ALL, DX, [], ["L70.0"]),  # 2 lần "chăm sóc da mụn"
    # "điều trị nhiều phương pháp", "thuốc" (không tên): không gán.
    # "giảm dầu": mô tả kết quả chăm sóc da, không phải triệu chứng -> không gán.
    ("nhân mụn", 0, DX, [], ["L70.0"]),  # tiền lệ GT[101] "Nhân mụn" -> L70.0
]

GT[106] = [  # 743c ×1  81.txt — bác sĩ trả lời về thrombophilia + 1 dòng thủ thuật EHR khác
    # Bài giải thích cho người hỏi (chính họ là bệnh nhân) -> không assertion,
    # trừ các biến chứng được nêu như nguy cơ CẦN TRÁNH -> isNegated.
    ("Thrombophilia", 0, DX, [], ["D68.5"]),
    ("máu có xu hướng vón cục", 0, DX, [], ["D68.5"]),  # định nghĩa của cùng bệnh
    ("bệnh tăng đông máu", 0, DX, [], ["D68.5"]),
    # "để tránh tình trạng sẩy thai, sinh non, tiền sản giật" -> chưa xảy ra,
    # đang phòng ngừa -> isNegated (tiền lệ các cụm "để tránh"/"không có").
    ("sẩy thai", 0, DX, [NEG], ["O03"]),
    ("sinh non", 0, DX, [NEG], ["O60.1"]),
    ("tiền sản giật", 0, DX, [NEG], ["O14"]),  # SỬA (rà mâu thuẫn): trước dùng O14.9
    # "Tiền sản giật, không xác định". Bề mặt trơ "tiền sản giật" không nêu thể nhẹ/nặng
    # -> dùng mã nhóm O14 "Tiền sản giật", khớp đúng mức chi tiết của bề mặt và trùng
    # với 2 nhãn cùng bề mặt ở block 100 (cùng lý lẽ đã áp cho "Rung nhĩ kèm ..." -> I48).
    ("thuốc chống đông", ALL, DRUG, [], []),  # 2 lần, nhóm thuốc không có tên cụ thể
    ("ra máu bất thường", 0, SYM, [], []),  # dấu hiệu cần theo dõi
    ("chảy máu khó cầm", 0, SYM, [NEG], []),  # "để tránh tình trạng chảy máu khó cầm"
    ("tắc mạch do cục máu đông", 0, DX, [FAM], ["I74.9"]),  # "con bạn cũng có thể bị"
    # -> bệnh của CON người hỏi -> isFamily (tiền lệ GT[12]/GT[113]).
    # --- đuôi: 1 dòng "Các thủ thuật đã thực hiện" của EHR khác ---
    # "đặt shunt dẫn lưu tĩnh mạch cửa qua da": thủ thuật -> không gán.
]

GT[107] = [  # 741c ×1  38.txt — QA que cấy tránh thai + phiếu CLS của EHR CML (2 nguồn ghép)
    # "que cấy tránh thai"/"Que tránh thai": thủ thuật/dụng cụ, không có tên hoạt
    # chất -> không gán (tiền lệ GT[42] chỉ gán "Implanon", bỏ "cấy que").
    # "không có thai": trạng thái sinh lý -> không gán.
    # --- "Kết quả xét nghiệm" của EHR khác ---
    ("bạch cầu", 0, LAB, [], []),
    ("39.2", 0, VAL, [], []),
    ("creatinin", 0, LAB, [], []),
    ("3.0", 0, VAL, [], []),
    ("troponin", 0, LAB, [], []),
    ("0.10", 0, VAL, [], []),
    ("inr", 0, LAB, [], []),
    ("1.4", 0, VAL, [], []),
    ("Tăng men gan", 0, SYM, [], []),  # tiền lệ GT[37]/GT[30]: "tăng men gan" = TRIỆU_CHỨNG
    ("alt", 0, LAB, [], []),
    ("176", 0, VAL, [], []),
    ("ast", 0, LAB, [], []),
    ("287", 0, VAL, [], []),
    ("tổng phân tích nước tiểu", 0, LAB, [], []),
    ("đái tháo đườngđái tháo đường", 0, DX, [], ["E14"]),  # lỗi dịch lặp cụm, giữ bề mặt
    ("chụp x-quang ngực", 0, LAB, [], []),
    # "bình thường": nhận định định tính, không có trị số -> không gán.
    ("cml", 0, DX, [], ["C92.1"]),
    ("gleevec", 0, DRUG, [NEG], ["282386"]),  # "trong bối cảnh ngừng gleevec"
]

GT[12] = [  # 379c ×2  12.txt, 48.txt — bác sĩ trả lời phụ huynh về dị tật tai của con
    # Bệnh nhân là CON của người hỏi -> isFamily (tiền lệ block 113).
    ("dị tật thiểu sản vành tai", 0, DX, [FAM], ["Q17.2"]),
    ("tịt ống tai ngoài bẩm sinh", 0, DX, [FAM], ["Q16.1"]),
    # "cấu trúc tai trong ... phát triển tốt", "bé phản xạ được âm thanh",
    # "tai trái khỏe mạnh": mô tả chức năng BÌNH THƯỜNG, không phải triệu chứng
    # cũng không phải chẩn đoán -> không gán.
]

GT[104] = [  # 749c ×1  2.txt — bài giảng dinh dưỡng/vận động cho trẻ Kawasaki + kết luận
    # Bài phổ biến kiến thức, không có bệnh nhân cụ thể -> không assertion
    # (tiền lệ GT[76]/GT[84]/GT[101]/GT[11]).
    ("Kawasaki", 0, DX, [], ["M30.3"]),  # tiêu đề "trẻ mắc Kawasaki"
    ("tổn thương vành mạch", 0, DX, [], []),  # tổn thương ĐM vành do Kawasaki, ICD-10
    # không có mã riêng (M30.3 đã bao gồm) -> để rỗng.
    # "hút thuốc lá thụ động", "môi trường ô nhiễm": yếu tố nguy cơ lối sống
    # -> không gán (tiền lệ "cà phê, chè, thuốc lá" ở GT[85]).
    ("Bệnh Kawasaki", 0, DX, [], ["M30.3"]),  # chứa lần xuất hiện [1] của "Kawasaki"
    ("sốt cao kéo dài", 0, SYM, [], []),
    ("đỏ mắt", 0, SYM, [], []),
    ("ban đỏ", 0, SYM, [], []),
    ("môi đỏ – nứt", 0, SYM, [], []),
    ("lưỡi đỏ dâu tây", 0, SYM, [], []),
    ("sưng hạch cổ", 0, SYM, [], []),
    ("****", 0, DRUG, [], []),  # tên thuốc bị mask (IVIG trong 10 ngày đầu)
    ("biến chứng mạch vành", 0, DX, [], []),
]

GT[105] = [  # 745c ×1  81.txt — người hỏi TỰ kể về hội chứng tăng đông của mình
    # Người hỏi chính là bệnh nhân -> không isFamily (tiền lệ GT[113]/GT[10]/GT[80]).
    ("sảy thai", 0, DX, [HIST], ["N96"]),  # "Sau 2 lần sảy thai" -> sảy thai liên tiếp, đã qua
    ("xét nghiệm máu", 0, LAB, [], []),
    ("hội chứng tăng đông", 0, DX, [], ["D68.5"]),
    ("gen đông máu", 0, DX, [], ["D68.5"]),  # cách gọi khác của cùng bệnh
    ("thrombophilia", ALL, DX, [], ["D68.5"]),  # 2 lần, đều là bệnh của người hỏi
    # "que thử 2 vạch": que thử thai tại nhà, là dụng cụ/không phải tên xét nghiệm
    # lâm sàng -> không gán (tiền lệ bỏ thiết bị và "các xét nghiệm này").
    ("thuốc chống đông máu", ALL, DRUG, [], []),  # 2 lần, nhóm thuốc không có tên cụ thể
    # "Tiêm thuốc đó": tham chiếu lại, không có tên thuốc -> không gán.
    # "có thai", "thai nhi": trạng thái sinh lý, không phải bệnh -> không gán.
]

# ------------------------------------------------
# 2 block còn lại của file 40.txt (block 100/136 đã xong) -> gán TRỌN file.
# 40.txt = MỘT bệnh án viết tay (BN nữ 75t, XHTH do quá liều kháng vitamin K, van động
# mạch chủ cơ học) đọc liền mạch: 100 (bệnh sử + khám) -> 247 (dòng chẩn đoán) ->
# 136 (phiếu chỉ định XN) -> 156 (kết quả XN + CĐHA + y lệnh). Bị chèn 1 câu khám thần
# kinh của EHR khác vào đầu block 156 (câu "Không ghi nhận co giật..." đã gán ở GT[186]).
# Cả file là lần nhập viện HIỆN TẠI -> KHÔNG assertion, trừ mục "Tiền sử" đã gán ở GT[100].
# ------------------------------------------------

GT[247] = [  # 165c ×1  40.txt — dòng chẩn đoán + tiêu đề phiếu xét nghiệm
    # "Chẩn đoán :", "Xét nghiệm cần làm :": tiêu đề -> không gán.
    ("Xuất huyết tiêu hóa", 0, DX, [], ["K92.2"]),  # y như GT[100] gán viết tắt "XHTH"
    # cùng mã K92.2 — cùng file, cùng bệnh nhân nên phải khớp mã.
    # "theo dõi": từ chỉ mức độ chắc chắn của chẩn đoán -> không lấy vào bề mặt
    # (tiền lệ GT[194] "theo dõi viêm cầu thận" gán đúng "viêm cầu thận").
    ("quá liều kháng vitamin K", 0, DX, [], ["T45.7"]),  # T45.7 "Ngộ độc thuốc đối
    # kháng chống đông máu, vitamin K, và/hoặc chất làm đông máu khác" — khớp đúng
    # nhóm thuốc. Đã cân nhắc D68.3 ("Xuất huyết do có kháng đông lưu hành") nhưng
    # D68.3 là mã cho HẬU QUẢ xuất huyết (đã có K92.2 gánh) còn bề mặt này nêu
    # NGỘ ĐỘC/quá liều thuốc -> T45.7. Không dùng T45.5 (thuốc chống đông nói chung)
    # vì bề mặt nói rõ "kháng vitamin K".
    ("Viêm phổi", 0, DX, [], ["J18.9"]),  # tiền lệ GT[94] "Viêm phổi bệnh viện" -> J18.9
    ("Van động mạch chủ cơ \nhọc", 0, DX, [], ["Z95.2"]),  # y như GT[100] cùng bề mặt
    # (ở đó không xuống dòng). Bề mặt CÓ dấu xuống dòng vì corpus ngắt giữa cụm —
    # giữ đúng chuỗi literal (WER chấm literal), tiền lệ GT[88] `("[[Ngã]]\n", ...)`.
    ("Đái tháo đường", 0, DX, [], ["E14"]),  # không rõ typ -> E14 (tiền lệ GT[14]/
    # GT[20]/GT[104]). Khác GT[87] "Đái tháo đường típ 2" -> E11.
    # "TS thay khớp háng": thủ thuật -> không gán, y như GT[100] cùng file đã bỏ
    # "thay khớp háng". ("TS" = tiền sử, chỉ là nhãn mục, cũng không gán.)
]

GT[156] = [  # 451c ×1  40.txt — 1 câu khám TK của EHR khác + kết quả XN + CĐHA + y lệnh
    # "2. Chẩn đoán hình ảnh", ". Chẩn đoán hình ảnh (Ngày 03/07/2026)", "Sinh hóa &
    # Miễn dịch:", "Y lệnh Điều trị", "Kết quả:": tiêu đề mục/nhóm + mốc ngày
    # -> không gán (GT[142]/GT[136]/GT[297]).
    # --- 1 câu khám thần kinh bị ghép vào (đã gán y như vậy ở GT[186]) ---
    ("co giật", 0, SYM, [NEG], []),  # "Không ghi nhận co giật, cứng đờ, cắn lưỡi hoặc
    ("cứng đờ", 0, SYM, [NEG], []),  # tiểu tiện không tự chủ" -> 1 phủ định phủ cả 4
    ("cắn lưỡi", 0, SYM, [NEG], []),  # (y như GT[186] cùng câu, cùng nguồn dịch).
    ("tiểu tiện không tự chủ", 0, SYM, [NEG], []),
    # --- kết quả xét nghiệm ---
    ("CRP", 0, LAB, [], []),  # tiền lệ GT[195]; GT[136] cùng file gán "Định lượng CRP"
    # (bề mặt dài hơn) vì ở đó corpus viết đủ chữ "Định lượng".
    ("227.0 mg/L", 0, VAL, [], []),
    ("Creatinin", 0, LAB, [], []),  # tiền lệ GT[194]
    ("46 µmol/L", 0, VAL, [], []),
    ("Kali +", 0, LAB, [], []),  # bề mặt corpus viết rời dấu + -> giữ nguyên literal
    ("3.6 mmol/L", 0, VAL, [], []),
    # --- chẩn đoán hình ảnh ---
    ("Chụp CT Bụng - Tiểu khung", 0, LAB, [], []),  # tiền lệ GT[26]/GT[179]/GT[186]
    # "(64–128 dãy, có thuốc cản quang, không in phim)": thông số máy + thuốc cản
    # quang -> không gán (GT[186]: thuốc cản quang là phương tiện CĐHA, không phải
    # thuốc điều trị; GT[136]: phương pháp/thiết bị không gán).
    ("Hình ảnh dày thành một số quai ruột non", 0, DX, [], []),  # phát hiện CĐHA là
    # trạng thái BỆNH LÝ -> CHẨN_ĐOÁN (quy ước chốt: phát hiện hình ảnh mang bệnh lý
    # là DX, chỉ mô tả dạng sóng/hình mới là VAL). Giữ trọn cả chữ "Hình ảnh" vì
    # corpus viết liền trong cụm phát hiện (tiền lệ GT[68] "không có hình ảnh tổn
    # thương viêm cấp tính"). CANDIDATES RỖNG: bảng ICD không có mã nào cho "dày
    # thành ruột" (đã quét `entries`, chỉ có K90.2 "Hội chứng quai ruột" — bệnh khác
    # hẳn, và K63.8 "Bệnh xác định khác của ruột" quá chung) -> không thêm mã đoán.
    # --- y lệnh ---
    ("Ceftriaxone", 0, DRUG, [], ["2193"]),  # RxNorm IN ceftriaxone = 2193, y như GT[63]
    # "1g", "2 lọ / ngày", "Truyền tĩnh mạch (sáng)", "30 giọt/phút": hàm lượng/liều/
    # đường dùng/tốc độ -> không gán (GT[297]/GT[316]).
]

GT[100] = [  # 798c ×1  40.txt — bệnh án viết tay BN nữ 75t XHTH do quá liều kháng vitamin K
    ("Đi ngoài phân đen", 0, SYM, [], []),  # lý do vào viện
    ("khó thở", 0, SYM, [], []),
    # --- "Bệnh sử" ---
    ("đau bụng quanh rốn", 0, SYM, [], []),
    ("nôn thức ăn lẫn máu", 0, SYM, [], []),
    ("đi ngoài phân đen", 1, SYM, [], []),
    ("khó thở liên tục", 0, SYM, [], []),
    ("sốt", 0, SYM, [NEG], []),  # "không rõ sốt"
    ("nội soi tiêu hóa", 0, LAB, [], []),
    ("XHTH", 0, DX, [], ["K92.2"]),  # viết tắt "xuất huyết tiêu hóa"
    ("thuốc kháng vitamin K", 0, DRUG, [], []),  # nhóm thuốc, RxNorm không có
    ("INR", 0, LAB, [], []),
    ("15", 0, VAL, [], []),  # "(INR 15)"
    ("**********", ALL, DRUG, [], []),  # 2 tên thuốc bị mask
    # --- "Tiền sử bệnh: Bản thân" -> isHistorical ---
    ("Van động mạch chủ cơ học", 0, DX, [HIST], ["Z95.2"]),
    # "điều trị thuốc không đều": không có tên thuốc -> không gán.
    # "thay khớp háng": thủ thuật -> không gán.
    # --- "Khám lúc vào viện" ---
    ("Mạch", 1, LAB, [], []),  # [0] nằm trong "Van động mạch chủ"
    ("130 lần/phút", 0, VAL, [], []),
    ("glasgow", 0, LAB, [], []),
    ("15 điểm", 0, VAL, [], []),
    ("Da niêm mạc nhợt", 0, SYM, [], []),
    ("Thể trạng nhiễm trùng", 0, SYM, [], []),
    ("phù", 0, SYM, [NEG], []),  # "Không phù"
    ("xuất huyết dưới da", 0, SYM, [NEG], []),
    ("Tim đều, T1T2 rõ tiếng van cơ học", 0, SYM, [], []),
    ("tiếng thổi", 0, SYM, [NEG], []),  # "không tiếng thổi"
    ("RRPN giảm 2 phế trường", 0, SYM, [], []),
    ("Bụng mềm, không chướng", 0, SYM, [], []),
    ("điểm đau thành bụng", 0, SYM, [NEG], []),  # "Không điểm đau thành bụng"
    ("Nhiệt độ", 0, LAB, [], []),
    ("37°C", 0, VAL, [], []),
    ("Huyết áp", 0, LAB, [], []),
    ("130 / 70 mmHg", 0, VAL, [], []),
    ("Nhịp thở", 0, LAB, [], []),
    ("21 l/p", 0, VAL, [], []),
]

GT[101] = [  # 790c ×1  41.txt — phác đồ điều trị trứng cá + 2 dòng EHR đau ngực ghép vào
    # Đoạn giảng/phác đồ chung -> không assertion (tiền lệ GT[76]/GT[84]).
    ("Nhân mụn", 0, DX, [], ["L70.0"]),
    ("Tretinoin", 0, DRUG, [], ["10753"]),
    ("Trứng cá viêm nhẹ", 0, DX, [], ["L70.0"]),
    ("********", 0, DRUG, [], []),
    ("kháng sinh tại chỗ", 0, DRUG, [], []),  # nhóm thuốc, RxNorm không có
    ("****************", 0, DRUG, [], []),
    # --- 2 dòng EHR đau ngực ghép vào giữa ---
    ("đau ngực trái cấp tính", 0, SYM, [], []),
    ("đau sau xương ức lan ra sau lưng", 0, SYM, [], []),
    # --- trở lại bài giảng trứng cá ---
    ("trứng cá", 1, DX, [], ["L70.9"]),  # "điều trị trứng cá để giảm mức độ bệnh"
    ("sẹo", 0, SYM, [], []),
    ("mụn trứng cá", 0, DX, [], ["L70.9"]),
    ("mụn", 2, SYM, [], []),  # "thói quen chà xát và nặn mụn"
]

GT[94] = [  # 839c ×1  47.txt — "3. Đánh giá tại bệnh viện" EHR hậu phẫu viêm phổi/rung nhĩ
    # --- "Kết quả khám thực thể" ---
    ("ran nổ", 0, SYM, [], []),
    ("phù phù", ALL, SYM, [], []),  # 2 lần, lỗi dịch lặp chữ "phù" -> giữ nguyên bề mặt
    ("dịch rỉ huyết thanh từ vết mổ", 0, SYM, [], []),
    ("phân nâu dương tính guaiac", ALL, SYM, [], []),  # 2 lần
    ("dấu hiệu sinh tồn", ALL, LAB, [], []),  # 2 lần (khoa Cấp cứu + MICU)
    # "98.8 65 9360 20 95 2LNC": dãy số sinh hiệu dính liền, không tách được từng
    # phép đo -> gán cả dãy làm KẾT_QUẢ_XÉT_NGHIỆM theo bề mặt.
    ("98.8 65 9360 20 95 2LNC", 0, VAL, [], []),
    ("98.6 70 10356 17 962LNC", 0, VAL, [], []),
    # --- "Dấu hiệu lâm sàng" ---
    ("hạ huyết áp, không đặc hiệu", 0, DX, [], ["I95.9"]),
    ("mệt mỏi", ALL, SYM, [], []),  # 2 lần, bản dịch lặp dòng
    ("khó thở khi gắng sức", 0, SYM, [], []),
    ("ho mạn tính có đờm vàng loãng", 0, SYM, [], []),
    ("ran", 1, SYM, [], []),  # dòng "- ran" riêng ([0] nằm trong "ran nổ")
    ("dịch thanh dịch lẫn máu từ vết mổ", 0, SYM, [], []),
    # --- "Kết quả xét nghiệm" ---
    ("huyết khối", 0, LAB, [], []),  # ở đây là tên chỉ số (hematocrit dịch sai)
    ("26.3", 0, VAL, [], []),
    ("28", 0, VAL, [], []),  # "ổn định ở mức 28 hậu phẫu tuần trước"
    # --- "Kết quả chẩn đoán hình ảnh" ---
    ("chụp x-quang ngực", 0, LAB, [], []),
    ("xẹp phổi thùy dưới phải do chèn ép", 0, DX, [], ["J98.1"]),
    ("tràn dịch màng phổi", 0, DX, [], ["J90"]),
    # "Truyền dịch tĩnh mạch 750cc", "Xông khí dung": thủ thuật -> không gán.
    # --- "Các phát hiện chẩn đoán khác" ---
    ("Viêm phổi bệnh viện", 0, DX, [], ["J18.9"]),
    ("Rung nhĩ kèm nhịp nhanh trên thất", 0, DX, [], ["I48"]),
]

GT[97] = [  # 828c ×1  69.txt — EHR tự tử nhảy cầu, cắt cụt 2 chân
    # Người nhà kể lại nhưng bệnh nhân CHÍNH LÀ người mắc -> không isFamily
    # (isFamily chỉ khi bệnh của thân nhân, không phải khi thân nhân là người kể).
    ("tổn thương chi dưới", ALL, SYM, [], []),  # 3 lần
    ("sốc", 0, SYM, [], []),  # "bị sốc khi chia tay" = sốc tâm lý
    ("buồn chán", 0, SYM, [], []),
    ("uống nhiều rượu", 0, DX, [], ["F10.1"]),
    ("hút cần sa", 0, DX, [], ["F12.1"]),
    ("trầm cảm", 0, DX, [NEG, HIST], ["F32.9"]),  # "Không xác nhận đã bị trầm cảm trước đó"
    ("ý định tự tử", 0, SYM, [NEG], []),  # "không xác nhận có ý định tự tử"
    # "Phẫu thuật cắt cụt chân trái/phải": thủ thuật -> không gán.
    ("thuyên tắc phổi hai bên", 0, DX, [], ["I26.9"]),
    ("nhiễm trùng chi dưới bên phải do Enterococcus kháng vancomycin", 0, DX, [], ["A49.8"]),
    ("kháng sinh tĩnh mạch", 0, DRUG, [], []),  # nhóm thuốc, RxNorm không có
]

GT[10] = [  # 437c ×2  16.txt, 20.txt — câu hỏi của người dùng về nguy cơ dại (tự kể -> không FAM)
    ("thương nhẹ ở tay", 0, SYM, [], []),
    ("chảy máu", 0, SYM, [], []),
    # "chó chưa tiêm dại": vaccine của con chó, không phải thuốc bệnh nhân dùng
    # -> không gán.
    # "nguy cơ lây bệnh dại": người hỏi CHƯA mắc, chỉ lo lây -> theo tiền lệ GT[119]
    # vẫn gán CHẨN_ĐOÁN (khái niệm bệnh có mặt trong văn bản), assertions rỗng.
    ("bệnh dại", 0, DX, [], ["A82.9"]),
]

GT[92] = [  # 873c ×1  77.txt — EHR đau khớp gối + phiếu CĐHA của một EHR tim mạch khác
    ("đau đầu gối phải", ALL, SYM, [], []),  # 2 lần: lý do nhập viện + triệu chứng hiện tại
    ("Đau bánh chè đùi phải dữ dội", 0, SYM, [], []),
    ("đau đau dữ dội", 0, SYM, [], []),  # lỗi dịch lặp chữ "đau"
    # --- phiếu chẩn đoán hình ảnh ghép vào ---
    ("Siêu âm ổ bụng", 0, LAB, [], []),
    ("giãn nh đường mật trong gan hai bên", 0, DX, [], ["K83.8"]),  # lỗi dịch "nhẹ"
    ("Siêu âm Doppler tim, van tim", 0, LAB, [], []),
    ("Buồng thất trái giãn", 0, DX, [], ["I42.0"]),
    ("chức năng tâm thu thất trái giảm nhiều", 0, DX, [], ["I50.9"]),
    ("EF BP", 0, LAB, [], []),
    ("28%", 0, VAL, [], []),
    ("Hở hai lá vừa", 0, DX, [], ["I34.0"]),
    ("Hở chủ nhẹ", 0, DX, [], ["I35.1"]),
    ("Hở ba lá nhiều", 0, DX, [], ["I36.1"]),
    ("Thất phải giãn", 0, DX, [], []),
    ("chức năng tâm thu thất phải giảm", 0, DX, [], ["I50.9"]),
    ("FAC", 0, LAB, [], []),
    ("30%", 0, VAL, [], []),
    ("Tăng áp lực động mạch phổi vừa", 0, DX, [], ["I27.2"]),
    ("Chụp Xquang ngực thẳng", 0, LAB, [], []),
    ("bóng tim to", 0, DX, [], ["R93.1"]),
]

# ------------------------------------------------------------------
# 4 block còn lại của file 77.txt (block 92 đã xong) -> gán TRỌN file.
# 77.txt = MỘT EHR đau khớp bánh chè – đùi phải, viết theo mẫu OPQRST, bị chèn
# phiếu CĐHA + dòng chẩn đoán của một EHR TIM MẠCH khác vào giữa (phần chèn đã gán
# ở GT[92] cho phiếu CĐHA; block 311 là dòng chẩn đoán của chính EHR tim mạch đó).
# Thứ tự đọc trong file: 256 (mục 1) -> 92 (mục 2 + phiếu CĐHA chèn) -> 311 (chẩn
# đoán EHR chèn) -> 217 (các trường OPQRST còn lại) -> 223 (mục 3).
# Quy ước chốt:
#  - Block 256 nằm dưới "1. Tiền sử bệnh" -> isHistorical (tiền lệ GT[187]/GT[9]/
#    GT[14]/GT[20]/GT[87]). LƯU Ý cùng triệu chứng này ở GT[92] KHÔNG có HIST vì ở
#    đó nó nằm dưới "2. Tiền sử bệnh hiện tại" (HPI) — assertion theo MỤC, không
#    theo nội dung, đây là quy ước đã chốt từ GT[289]:1059/GT[128]:2248.
#  - Block 311/223 là lần nhập viện HIỆN TẠI -> KHÔNG assertion.
# ------------------------------------------------------------------

GT[256] = [  # 142c ×1  77.txt — mục "1. Tiền sử bệnh"
    # "1. Tiền sử bệnh", "CGhi nhận ... trước đây" (lỗi dịch thêm chữ "C"): tiêu đề
    # mục -> không gán (GT[142]:1941).
    # "triệu chứng tương tự": nhắc chung không nêu tên -> không gán, tiền lệ
    # GT[183]:2801 ("có các triệu chứng tương tự") cùng dạng câu.
    ("đau vùng xương bánh chè – đùi phải dữ dội", 0, SYM, [HIST], []),  # giữ TRỌN cụm
    # (vị trí + mức độ nằm liền trong tên triệu chứng) theo đúng GT[92]:3021 cùng file
    # gán "Đau bánh chè đùi phải dữ dội". Dấu – là en-dash của corpus, giữ nguyên.
    # "xảy ra cách đây vài tháng": mốc thời gian -> không gán (GT[226]:1290).
]

GT[311] = [  # 58c ×1  77.txt — dòng chẩn đoán của EHR tim mạch bị ghép vào
    # "Chẩn đoán:": tiêu đề -> không gán. Đây là dòng chẩn đoán đi kèm phiếu CĐHA đã
    # gán ở GT[92] (thất trái giãn, EF 28%, hở van, bóng tim to) -> khớp nhau.
    ("suy tim", 0, DX, [], ["I50.9"]),  # tiền lệ GT[124]:2523/GT[197]:1614/GT[91]:3173
    ("suy thận mạn giai đoạn 5", 0, DX, [], ["N18.5"]),  # tiền lệ GT[14]:4728
    # "Suy thận mạn giai đoạn V" -> N18.5 ("Bệnh thận mạn tính, giai đoạn 5"); ở đây
    # corpus ghi số Ả Rập "5". GIỮ phần "giai đoạn 5" trong bề mặt vì mã N18.x phân
    # theo đúng giai đoạn -> giai đoạn là phần định danh chẩn đoán, không phải hậu tố
    # mức độ bị cắt như "mức độ trung bình" ở GT[219].
    ("tăng huyết áp", 0, DX, [], ["I10"]),  # corpus dính chữ "giai đoạn 5tăng huyết áp"
    # -> needle chỉ lấy đúng phần tên bệnh (tiền lệ GT[120]:3762 "Bệnh dạithường",
    # GT[163]:3532 "chụp ctchưa phát hiện", GT[25]:4701 "tăng bạch cầuNgày nay").
    # Không HIST: dòng chẩn đoán của lần nhập viện hiện tại (tiền lệ GT[233]:1643,
    # GT[68]:4774 cùng dạng dòng "Chẩn đoán:").
]

GT[217] = [  # 261c ×1  77.txt — các trường OPQRST còn trống -> KHÔNG có khái niệm nào
    # Toàn block là 6 gạch đầu dòng của mẫu bệnh án, 5 trong 6 trường ghi "Không ghi
    # rõ" (= không có dữ liệu) và trường còn lại chỉ kể HOẠT ĐỘNG:
    #  - "Thời gian", "Tần suất", "Các yếu tố làm giảm", "Các triệu chứng liên quan":
    #    tên trường của mẫu -> không gán (GT[142]:1941; chính GT[92] cùng file đã bỏ
    #    "Thời điểm khởi phát triệu chứng"/"Diễn biến bệnh"/"Tiến triển bệnh").
    #  - "Chiếu xạ": dịch sai chữ "Radiation" trong mẫu OPQRST (đúng nghĩa là "đau
    #    lan"), vẫn chỉ là tên trường và nội dung là "Không ghi rõ" -> không gán.
    #  - "Không ghi rõ" (5 lần): nghĩa là KHÔNG có thông tin, không phải phủ định một
    #    triệu chứng có tên -> không gán (khác "không sốt" ở GT[183]:2795 có tên
    #    triệu chứng để phủ định).
    #  - "hầu hết các hoạt động, đặc biệt là leo cầu thang và gập sâu": yếu tố làm
    #    nặng là HOẠT ĐỘNG, không phải triệu chứng/bệnh -> không gán (tiền lệ bỏ
    #    lối sống/vận động, GT[322] bỏ "yếu tố nguy cơ" nêu chung).
    # -> Danh sách rỗng tường minh (không dùng DONE_EMPTY) để giữ lại lý do,
    # theo đúng cách làm ở GT[292]:2717.
]

GT[223] = [  # 236c ×1  77.txt — mục "3. Đánh giá tại bệnh viện"
    # Tiêu đề mục + "Kết quả chẩn đoán hình ảnh" -> không gán (GT[142]:1941/GT[186]:1113).
    ("x-quang", 0, LAB, [], []),  # tên thăm dò đứng một mình (không có chữ "chụp"),
    # vẫn là TÊN_XÉT_NGHIỆM — tiền lệ GT[137]:2001 gán viết tắt "XQ".
    # "vào thời điểm đó": mốc thời gian -> không gán.
    ("thay đổi thoái hóa nghiêm trọng của khớp bánh chè đùi phải", 0, DX, [], ["M17.9"]),
    # Bỏ mạo từ "những" ở đầu, giữ TRỌN phần còn lại: mức độ "nghiêm trọng" nằm GIỮA
    # cụm nên không cắt được rời, và tiền lệ GT[245]:1126 giữ nguyên bề mặt dài có cả
    # "mức độ nặng giai đoạn toàn phát", GT[94]:2985 giữ "do chèn ép".
    # M17.9 "Thoái hóa khớp gối, không xác định": "thay đổi thoái hóa" = thoái hóa
    # khớp, vị trí bánh chè – đùi là một khoang của khớp gối. Đã cân nhắc M22.2
    # ("Rối loạn của khớp gối (xương bánh chè - xương đùi)") vì khớp đúng hơn về vị
    # trí, nhưng M22.2 là mục "rối loạn" chung, không mang bệnh lý THOÁI HÓA mà bề
    # mặt nêu rõ -> ưu tiên khớp BỆNH LÝ (cùng lối chọn với GT[219] chọn T86.1 thay
    # Z94.0). Không dùng M17.1/M17.5 (nguyên phát/thứ phát) vì bề mặt không nói.
    ("chụp cắt lớp vi tính", 0, LAB, [], []),  # tiền lệ GT[26]:241/GT[179]:3462
    # "kể từ lần khám cuối cùng": mốc thời gian -> không gán.
    # "góc tăng lên": KHÔNG gán, hai lý do:
    #  - Không phải KẾT_QUẢ_XÉT_NGHIỆM: chỉ là nhận định bằng chữ, không có giá trị
    #    số (chốt ở GT[89]:3142 bỏ "(Tăng)", GT[151]:3848 bỏ "dưới ngưỡng điều trị").
    #  - "góc" cũng không gán riêng làm TÊN_XÉT_NGHIỆM: là số đo chung chung không
    #    nêu tên phép đo nào (tiền lệ GT[151] bỏ "chỉ số đông máu" vì gọi chung).
]

GT[89] = [  # 920c ×1  6.txt — mục "3. Đánh giá tại bệnh viện" EHR chấn thương sọ não
    ("mất định hướng", 0, SYM, [], []),
    ("đi lại không vững", 0, SYM, [], []),
    ("kích thích nhẹ", 0, SYM, [], []),
    ("ngửa đầu ra sau", 0, SYM, [], []),
    ("nhắm mắt từng lúc", 0, SYM, [], []),
    ("Chụp cắt lớp vi tính (CT Scanner)", 0, LAB, [], []),
    # "có tiêm thuốc cản quang": thuốc cản quang là phương tiện chẩn đoán hình ảnh,
    # không phải thuốc điều trị -> không gán (không có tên hoạt chất).
    ("Điện tâm đồ", 0, LAB, [], []),
    ("Ghi điện tim cấp cứu tại giường", 0, LAB, [], []),
    ("WBC", 0, LAB, [], []),
    ("14.99 G/L", 0, VAL, [], []),
    ("NEUT%", 0, LAB, [], []),
    ("82.9 %", 0, VAL, [], []),
    # "(Tăng)" là nhận định định tính, không có giá trị số -> không gán.
    ("HGB (Hemoglobin)", 0, LAB, [], []),
    ("92 g/L", 0, VAL, [], []),
    ("PT - INR", 0, LAB, [], []),
    ("1.05", 0, VAL, [], []),
    ("CT sọ não", 0, LAB, [], []),
    # các tổn thương đọc được trên CT -> CHẨN_ĐOÁN (tiền lệ GT[165])
    ("xuất huyết dưới nhện vùng trán phải", 0, DX, [], ["S06.6"]),
    ("Bầm dập nhu mô vùng trán phải và trán - thái dương phải", 0, DX, [], ["S06.2"]),
    ("Lớp dịch dưới màng cứng mỏng vùng thùy trán phải", 0, DX, [], []),
    ("nang màng nhện", 0, DX, [], ["G93.0"]),
    ("tụ máu dưới màng cứng mạn tính", 0, DX, [], ["S06.5"]),
    ("Tụ máu ngoài màng cứng phải cấp tính", 0, DX, [], ["S06.4"]),
]

# ------------------------------------------
# 3 block còn lại của file 46.txt (block 91/144 đã xong) -> gán TRỌN file.
# 46.txt = MỘT bệnh án viết tay (BN nữ 81t, phù phổi cấp/suy tim/stent mạch vành/
# tăng huyết áp/HoHL) đọc liền mạch: 91 (bệnh sử + khám + khí máu + ĐTĐ) ->
# 213 (kết quả siêu âm Doppler tim) -> 295 (dòng chẩn đoán + tiêu đề "Xử trí") ->
# 260 (3 dòng thủ thuật của EHR KHÁC ghép vào) -> 144 (mục "2. Bệnh sử hiện tại"
# của EHR khác nữa, đã gán, SHARE 381c với block 153).
# Cả bệnh án là lần nhập viện HIỆN TẠI -> KHÔNG assertion, trừ mục tiền sử ở GT[91].
# Quy ước chốt:
#  - Block 213 là phần kết quả của "Siêu âm doper tim" đã gán LAB ở GT[91] -> mọi
#    phát hiện bệnh lý gán DX, khớp 1-1 với phiếu siêu âm tim ở GT[92] (77.txt).
#  - Block 295 CÙNG BỆNH NHÂN với GT[91] -> DÙNG LẠI Y NGUYÊN mã của GT[91]
#    (J81, I50.9, Z95.5, I10) để hai block không lệch.
#  - Block 260 chỉ có thủ thuật -> chỉ lấy khái niệm BỆNH (u dây thần kinh) và
#    TÊN XÉT NGHIỆM (sinh thiết), không gán thủ thuật.
# ------------------------------------------

GT[213] = [  # 270c ×1  46.txt — kết quả "Siêu âm doper tim" (tên XN đã gán ở GT[91])
    ("Phình thành sau và thành bên thất trái", 0, DX, [], ["I25.3"]),  # I25.3 "Phình
    # thành tim" — phát hiện trên siêu âm tim là trạng thái bệnh lý -> CHẨN_ĐOÁN
    # (tiền lệ GT[92] "Buồng thất trái giãn", GT[301] "Rối loạn vận động vùng").
    # GIỮ trọn phần vị trí ("thành sau và thành bên thất trái") vì nằm liền trong
    # tên phát hiện, cùng kiểu GT[92] "Buồng thất trái giãn" giữ cả "buồng…trái".
    ("Giảm vận động 2/3 thành bên và 2/3 thành sau dưới thất trái về phía đáy", 0, DX,
     [], ["I25.5"]),  # y như GT[301] "Rối loạn vận động vùng" -> I25.5 "Bệnh lý cơ
    # tim do thiếu máu cục bộ": đây chính là giảm vận động vùng cơ tim do thiếu máu,
    # trên BN có stent mạch vành nên bối cảnh vành là chắc chắn. Giữ trọn bề mặt kể
    # cả phần định vị vì corpus viết liền một câu.
    ("Thành thất trái dày", 0, DX, [], []),  # dày thành thất = phì đại thất trái,
    # NHƯNG bảng ICD chỉ có I42.1/I42.2 ("Bệnh lý cơ tim phì đại") là BỆNH CƠ TIM
    # nguyên phát — ở đây dày thành là hậu quả của tăng huyết áp, không phải bệnh cơ
    # tim phì đại. Đã quét `entries`: KHÔNG có mã nào cho "dày thành thất trái"
    # đơn thuần. -> candidates RỖNG nhưng VẪN gán DX (tiền lệ GT[92] "Thất phải giãn"
    # cũng DX + candidates rỗng). Không thêm I11.9 "cho chắc": Jaccard sẽ giảm.
    # "buồng thất trái không giãn", "chức năng tâm thu thất trái bảo tồn": phát hiện
    # BÌNH THƯỜNG trên phiếu CĐHA -> không gán (quy ước "phát hiện bình thường không
    # gán", tiền lệ GT[92] cùng dạng phiếu siêu âm tim chỉ gán các phát hiện BẤT
    # THƯỜNG; GT[301] bỏ "Đánh giá chức năng thất trái").
    ("EF BP", 0, LAB, [], []),  # y như GT[92] cùng bề mặt -> TÊN_XÉT_NGHIỆM
    ("55%", 0, VAL, [], []),  # y như GT[92] gán "28%" -> KẾT_QUẢ_XÉT_NGHIỆM
    ("Hở hai lá nhiều", 0, DX, [], ["I34.0"]),  # I34.0 "Hở (van) hai lá"; y như
    # GT[92] "Hở hai lá vừa" -> I34.0. GIỮ mức độ "nhiều" trong bề mặt theo đúng
    # GT[92] (mức độ nằm liền trong cụm, không cắt được sạch).
    ("Hở chủ vừa", 0, DX, [], ["I35.1"]),  # y như GT[92] "Hở chủ nhẹ" -> I35.1
    ("Tăng áp lực động mạch phổi nhẹ", 0, DX, [], ["I27.2"]),  # y như GT[92]
    # "Tăng áp lực động mạch phổi vừa" -> I27.2 (thứ phát: BN có suy tim/hở van nên
    # là tăng áp phổi thứ phát, không dùng I27.0 nguyên phát).
]

GT[295] = [  # 77c ×1  46.txt — dòng chẩn đoán + tiêu đề "Xử trí"
    # "Chẩn đoán:", "Xử trí :": tiêu đề -> không gán (GT[142]).
    # 4 chẩn đoán nối bằng dấu "-" -> tách thành 4 khái niệm riêng, DÙNG LẠI Y NGUYÊN
    # mã đã chốt ở GT[91] cùng bệnh nhân. Không HIST: dòng chẩn đoán của lần nhập
    # viện hiện tại (tiền lệ GT[311]/GT[233]/GT[68] cùng dạng dòng "Chẩn đoán:").
    ("Phù phổi cấp", 0, DX, [], ["J81"]),
    ("Suy tim", 0, DX, [], ["I50.9"]),
    ("Stent mạch vành", 0, DX, [], ["Z95.5"]),  # Z95.5 = trạng thái ĐÃ ĐẶT dụng cụ
    # can thiệp mạch vành, y như GT[91]. (Khác GT[292] nơi "Đặt stent" là tên THỦ
    # THUẬT trong bài giảng -> không gán.)
    ("Tăng huyết áp", 0, DX, [], ["I10"]),
]

GT[260] = [  # 135c ×1  46.txt — 3 dòng thủ thuật/XN của một EHR KHÁC ghép vào
    # "Phẫu thuật cắt bỏ": THỦ THUẬT -> không gán, chỉ lấy khái niệm BỆNH là lý do
    # phẫu thuật (tiền lệ GT[182]/GT[14]/GT[145] bỏ "phẫu thuật cắt bỏ tuyến tiền
    # liệt" nhưng gán "u ác của tuyến tiền liệt").
    ("u dây thần kinh số VIII", 0, DX, [], ["D33.3"]),  # dây VIII = thần kinh thính
    # giác (u dây VIII = schwannoma tiền đình, bản chất LÀNH tính). D33.3 "U lành ở
    # thần kinh sọ não" — đã quét `entries`. Loại C72.4 "U ác tính ở thần kinh thính
    # giác": u dây VIII là u lành, dùng mã ung thư sẽ sai bản chất. Loại D43.3 (u
    # không tiên lượng được) vì bản chất u này đã xác định là lành.
    # "Đặt shunt động tĩnh mạch (AVF) ở tay phải (RUE AVF)": THỦ THUẬT tạo đường mạch
    # chạy thận, không có tên bệnh trong câu -> không gán (tiền lệ GT[106] "đặt shunt
    # dẫn lưu tĩnh mạch cửa qua da", GT[292] "Đặt stent").
    ("Sinh thiết tuyến tiền liệt", 0, LAB, [], []),  # y như GT[14] cùng bề mặt -> LAB
]

GT[91] = [  # 906c ×1  46.txt — bệnh án viết tay BN nữ 81t suy tim/phù phổi cấp
    ("khó thở", 0, SYM, [], []),  # lý do vào viện
    # --- mục "tiền sử" -> isHistorical ---
    ("stent mạch vành", 0, DX, [HIST], ["Z95.5"]),
    ("suy tim", 0, DX, [HIST], ["I50.9"]),
    ("tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("HoHL", 0, DX, [HIST], ["I34.0"]),  # viết tắt "hở van hai lá"
    # "điêu trị ngoại trú không rõ đơn": không có tên thuốc -> không gán.
    # --- "Bệnh sử": diễn biến hiện tại ---
    ("khó thở tăng lên", 0, SYM, [], []),
    ("NYHA III-IV", 0, SYM, [], []),  # mức độ khó thở
    ("mệt mỏi", 0, SYM, [], []),
    ("sốt", 0, SYM, [NEG], []),  # "không sốt"
    ("đau bụng", 0, SYM, [NEG], []),  # "không đau bụng"
    # --- chẩn đoán tuyến dưới (lần 2 của các bệnh trên: đang mắc, không HIST) ---
    ("phù phổi cấp", 0, DX, [], ["J81"]),
    ("suy tim", 1, DX, [], ["I50.9"]),
    ("stent mạch vành", 1, DX, [], ["Z95.5"]),
    ("tăng huyết áp", 1, DX, [], ["I10"]),
    ("HoHL", 1, DX, [], ["I34.0"]),
    ("khó thở vừa", 0, SYM, [], []),
    # --- mục "Khám" ---
    ("Glasgow", 0, LAB, [], []),
    ("15 điểm", 0, VAL, [], []),
    ("Da niêm mạc hồng", 0, SYM, [], []),  # tiền lệ GT[131]
    ("phù", 1, SYM, [NEG], []),  # "Không phù" ([0] nằm trong "phù phổi cấp")
    ("sốt", 1, SYM, [NEG], []),  # "Không sốt"
    ("Tim đều TTT ở mỏm 3/6", 0, SYM, [], []),
    ("M", 15, LAB, [], []),  # nhãn mạch viết tắt "M: 82 ck/ph"
    ("82 ck/ph", 0, VAL, [], []),
    ("HA", 1, LAB, [], []),  # [0] nằm trong "NYHA"
    ("160/ 80 mmHg", 0, VAL, [], []),
    ("Phổi RRPN rõ", 0, SYM, [], []),
    ("rale ẩm", 0, SYM, [], []),
    ("Bụng mềm không chướng", 0, SYM, [], []),
    # --- "Cận lâm sàng": phiếu khí máu xuất hiện 2 lần (Khí máu + Diễn biến CLS) ---
    ("Khí máu", 0, LAB, [], []),
    ("Lactat", 0, LAB, [], []),
    ("Định lượng Lactat", 0, LAB, [], []),  # lần 2, tên đầy đủ
    ("0.8", ALL, VAL, [], []),  # 2 lần, cùng một giá trị lặp lại
    ("HCO3", ALL, LAB, [], []),
    ("32.09", ALL, VAL, [], []),
    ("PO2", ALL, LAB, [], []),
    ("97.0", ALL, VAL, [], []),
    ("PCO2", ALL, LAB, [], []),
    ("39", ALL, VAL, [], []),
    ("pH", 5, LAB, [], []),  # [0..4] nằm trong "phù"/"ph"/"Phổi"
    ("pH", 6, LAB, [], []),
    ("7.517", ALL, VAL, [], []),
    ("nhịp  xoang ts 74", 0, SYM, [], []),
    ("biến đổi ST-T", 0, SYM, [NEG], []),  # "không biến đổi ST-T"
    ("Siêu âm doper tim", 0, LAB, [], []),  # lỗi dịch "doppler"
]

GT[84] = [  # 1001c ×1  72.txt — đoạn giảng điều trị mày đay + EHR lạm dụng chất (2 nguồn ghép)
    # Đoạn giảng chung, không có bệnh nhân cụ thể -> không assertion
    # (tiền lệ GT[76]/GT[81]/GT[118]/GT[157]).
    ("****************", ALL, DRUG, [], []),  # 2 lần: kháng histamin H1 thế hệ 2 và 1
    ("buồn ngủ", 0, SYM, [], []),  # "không gây buồn ngủ" = tác dụng phụ của thuốc,
    # không phải triệu chứng phủ định của BN -> vẫn gán, assertions rỗng.
    ("corticoid", 0, DRUG, [], []),  # nhóm thuốc, RxNorm không có IN
    # "2,5 – 5mg mỗi 2-3 tuần": liều giảm dần, không phải KẾT_QUẢ_XÉT_NGHIỆM.
    # --- mục "Các bệnh mãn tính" của EHR -> isHistorical ---
    ("Rối loạn cảm xúc", 0, DX, [HIST], ["F39"]),
    ("Rối loạn lưỡng cực", 0, DX, [HIST], ["F31.9"]),
    ("rối loạn lo âu", 0, DX, [HIST], ["F41.9"]),
    # --- mục "Thuốc đã điều trị trước khi nhập viện lần này" -> isHistorical ---
    # "Thuốc kê đơn (tên không được chỉ định)": không có tên thuốc -> không gán.
    ("klonopinclonidine", 0, DRUG, [HIST], []),  # lỗi dịch dính 2 tên thuốc
    ("clonidine", 1, DRUG, [HIST], ["2599"]),  # [0] nằm trong "klonopinclonidine"
    ("suboxone", 0, DRUG, [NEG, HIST], ["352990"]),  # "dừng thuốc trước nhập viện 01 ngày"
    ("Lạm dụng chất kích thích, chất gây nghiện opioid", 0, DX, [HIST], ["F19.1"]),
]

GT[85] = [  # 999c ×1  23.txt — đoạn giảng mất ngủ (người hỏi hỏi CHO MẸ) + tiền sử thủ thuật
    # "đưa mẹ tới gặp bác sĩ" -> người bệnh là MẸ người hỏi => isFamily
    # (tiền lệ block 113 và các block người hỏi kể về thân nhân).
    # "cà phê, chè, thuốc lá": chất kích thích trong đời sống, không phải thuốc điều
    # trị -> không gán (tiền lệ "Uống rượu 30 năm" ở GT[98]).
    ("mãn kinh", ALL, DX, [FAM], ["N95.1"]),  # 2 lần, đều là thời kỳ mãn kinh của mẹ
    ("đổ mồ hôi đêm", 0, SYM, [FAM], []),
    ("bốc hỏa", 0, SYM, [FAM], []),
    ("Mất ngủ", 0, DX, [FAM], ["G47.0"]),
    # --- "Lời khuyên": các bệnh nêu ra là khả năng chung, vẫn là về mẹ -> isFamily ---
    ("rối loạn lo âu", 0, DX, [FAM], ["F41.9"]),
    ("trầm cảm", 0, DX, [FAM], ["F32.9"]),
    ("stress", 0, DX, [FAM], ["F43.9"]),
    # "không dùng thuốc, các chất kích thích thần kinh trung ương": không có tên
    # thuốc cụ thể -> không gán.
    # --- đuôi: mục "Tiền sử phẫu thuật / thủ thuật" của một EHR khác (trẻ sơ sinh) ---
    # "Phẫu thuật đặt cảng", "Hệ thống dẫn lưu được chỉnh sửa/thay thế": thủ thuật
    # và thiết bị -> không gán, chỉ lấy chẩn đoán.
    ("tăng nhãn áp", 0, DX, [HIST], ["H40.9"]),
]

GT[80] = [  # 1069c ×1  4.txt — câu trả lời tư vấn levothyroxine cho mẹ cho con bú + đuôi nội soi
    # Người hỏi tự kể về mình -> không isFamily. Đây là tư vấn cho chính người hỏi
    # nên các nhãn về họ vẫn không có assertion (tiền lệ GT[113]).
    ("ung thư tuyến giáp", 0, DX, [], ["C73"]),
    ("levothyroxine", ALL, DRUG, [], ["10582"]),  # 2 lần, đều là thuốc đang dùng
    # "75 microgam/ngày": liều thuốc, KHÔNG phải KẾT_QUẢ_XÉT_NGHIỆM -> không gán.
    # (Sửa ở đợt 11: trước đây gán VAL, tự mâu thuẫn với chính ghi chú của nó và với
    # 3 liều khác trong cùng block này đã bỏ, cũng như GT[297]/GT[176]/GT[239].
    # Ở đây liều bị tách khỏi tên thuốc bởi chữ "với liều" nên không thể gộp vào
    # bề mặt THUỐC như GT[128] "aspirin 325mg".)
    ("Berlthyrox", 0, DRUG, [], []),  # biệt dược Việt, RxNorm không có
    # "100 microgam", "200-300 microgam/ngày", "4 nanogam/mL": liều thuốc và nồng độ
    # trong sữa mẹ của đoạn giảng, không phải kết quả XN của bệnh nhân -> không gán
    # (theo quy ước "liều thuốc không phải KẾT_QUẢ_XÉT_NGHIỆM").
    ("hormone tuyến giáp tổng hợp", 0, DRUG, [], ["10582"]),  # = levothyroxine
    # "hormone giáp" (2 lần): nói về hormone nội sinh/bài tiết vào sữa, không phải
    # thuốc bệnh nhân dùng -> không gán.
    ("*************", 0, DRUG, [], []),  # tên thuốc bị mask trong đoạn liều cao
    # --- đuôi: 3 dòng kết quả nội soi của một EHR khác ghép vào ---
    ("Viêm thực quản độ C ở thực quản dưới", 0, DX, [], ["K20"]),
    ("Loét loét thực quản 6 mm có điểm sắc tố", 0, DX, [], ["K22.1"]),  # lỗi dịch lặp chữ
    ("Nhiều loét sạch đáy loét ở tá tràng", 0, DX, [], ["K26.9"]),
]

GT[9] = [  # 525c ×2  12.txt, 15.txt — "Tiền sử bệnh" + "Thuốc trước khi nhập viện"
    # Cả block nằm dưới "1. Tiền sử bệnh" -> toàn bộ isHistorical
    # (tiền lệ block 14/20/87/88/98/198/204/241).
    ("Bệnh phổi kẽ", 0, DX, [HIST], ["J84.9"]),
    ("corticoid", 0, DRUG, [HIST], []),  # nhóm thuốc, RxNorm không có IN
    # "Thở oxy tại nhà" (2 lần): thủ thuật/thiết bị, không phải thuốc -> không gán.
    ("Hội chứng kháng enzym tổng hợp protein", 0, DX, [HIST], ["M35.8"]),
    ("béo phì", 0, DX, [HIST], ["E66.9"]),
    ("Tăng huyết áp nguyên phát", 0, DX, [HIST], ["I10"]),
    # TÊN_XÉT_NGHIỆM không được mang assertion nên dù nằm trong mục Tiền sử vẫn để rỗng.
    ("Sinh thiết nội mạc tử cung", 0, LAB, [], []),
    ("bactrim", 0, DRUG, [HIST], ["151399"]),
    ("doxycycline", 0, DRUG, [HIST], ["3640"]),
    ("Corticoid liều cao kéo dài", 1, DRUG, [HIST], []),  # dòng trong mục Thuốc
    ("Suy giảm miễn dịch", 0, DX, [HIST], ["D84.9"]),
    ("corticoid", 2, DRUG, [HIST], []),  # "do sử dụng corticoid kéo dài"
]

GT[78] = [  # 1084c ×1  18.txt — bệnh án viêm túi mật cấp, mục diễn biến + triệu chứng + đặc điểm
    # "Ăn ít mỡ bão hòa – ít muối": chế độ ăn, không phải thuốc -> không gán.
    ("đau bụng trên", 0, SYM, [], []),
    ("đỡ đau hơn", 0, SYM, [], []),
    ("cấy máu", 0, LAB, [], []),
    ("dương tính", 0, VAL, [], []),  # tiền lệ cặp "cúm"/"âm tính" ở GT[58]/GT[165]
    # --- mục "Triệu chứng hiện tại" ---
    ("sốt", 1, SYM, [], []),
    ("đau bụng", 1, SYM, [], []),
    ("đau hạ sườn phải", 1, SYM, [], []),
    ("sốt nhẹ đến 38.3°C", ALL, SYM, [], []),  # 2 lần: diễn biến + liệt kê
    ("đau hạ sườn phải tái phát, ngày càng nặng hơn", ALL, SYM, [], []),  # 2 lần
    ("đau hạ sườn phải liên tục", 0, SYM, [], []),
    # --- "Triệu chứng liên quan: không thấy ..." -> isNegated cả loạt ---
    ("buồn nôn", 0, SYM, [NEG], []),
    ("nôn", 1, SYM, [NEG], []),  # [0] nằm trong "buồn nôn"
    ("ớn lạnh", 0, SYM, [NEG], []),
    ("thay đổi chức năng ruột", 0, SYM, [NEG], []),
    ("đau ngực", 0, SYM, [NEG], []),
    ("khó thở", 0, SYM, [NEG], []),
    # --- "Diễn biến trước khi nhập viện" ---
    ("siêu âm vùng gan mật", 0, LAB, [], []),
    ("túi mật căng to", 0, DX, [], ["K82.8"]),
    ("dịch quanh túi mật", 0, DX, [], []),
    ("viêm túi mật cấp", 0, DX, [], ["K81.0"]),
]

GT[77] = [  # 1087c ×1  36.txt — bệnh án hội chứng thận hư (BN nam 17 tuổi), có phiếu XN đầy đủ
    ("nặng mặt", 0, SYM, [], []),
    ("tức nặng 2 chi dưới", 0, SYM, [], []),
    ("tiểu ít", 0, SYM, [], []),
    ("Hội chứng thận hư", 0, DX, [], ["N04"]),
    ("Phù", 0, SYM, [], []),  # "Phù: xuất hiện đột ngột..."
    ("phù 2 chi dưới", 0, SYM, [], []),
    ("phù", 2, SYM, [], []),  # "phù tăng về sáng"
    ("phù", 3, SYM, [], []),  # "khi ăn mặn phù tăng lên"
    ("phù mặt", 0, SYM, [NEG], []),  # "Hiện tại hết phù mặt"
    ("phù nhẹ 2 chi dưới", 0, SYM, [], []),
    # "Phù"[6] là chữ "Phù hợp", không phải triệu chứng -> không gán.
    ("Protein niệu 24h", 0, LAB, [], []),
    ("Protein máu", 0, LAB, [], []),
    ("Protein", 2, LAB, [], []),  # "Protein: 52 g/l"
    ("52 g/l", 0, VAL, [], []),
    ("Albumin", 0, LAB, [], []),
    ("20 g/l", 0, VAL, [], []),
    ("Triglycerid", 0, LAB, [], []),
    ("6,7 mmol/l", 0, VAL, [], []),
    ("Tổn thương cầu thận mạn tính", 0, DX, [], ["N03.9"]),
    ("Xét nghiệm nước tiểu", 0, LAB, [], []),
    ("protein", 3, LAB, [], []),  # "nước tiểu protein (–)"
    ("HC", 0, LAB, [], []),
    ("Trụ niệu", 0, LAB, [], []),
    # "(–)" là kết quả âm tính bằng ký hiệu, không có giá trị số -> theo tiền lệ
    # GT[25]/GT[24] chỉ gán KẾT_QUẢ cho giá trị số -> không gán.
    ("SA", 3, LAB, [], []),  # [0..2] là chữ "sau" (khớp không phân biệt hoa/thường)
    ("sỏi đài bể thận", 0, DX, [NEG], ["N20.0"]),  # "không có sỏi đài bể thận"
    ("viêm cầu thận", 0, DX, [], ["N05.9"]),  # "theo dõi viêm cầu thận"
    ("suy thận", 0, DX, [NEG], ["N19"]),  # "Không có suy thận"
    ("Ure", 0, LAB, [], []),
    ("6,4 mmol/l", 0, VAL, [], []),
    ("Creatinin", 0, LAB, [], []),
    ("79 micromol/l", 0, VAL, [], []),
    ("thiếu máu", 0, DX, [NEG], ["D64.9"]),  # "Không có thiếu máu"
    ("HC", 1, LAB, [], []),
    ("4,49 T/l", 0, VAL, [], []),
    ("HST", 0, LAB, [], []),
    ("103 g/l", 0, VAL, [], []),
    ("Điện giải", 0, LAB, [], []),
    ("Na+", 0, LAB, [], []),
    ("141 mmol/l", 0, VAL, [], []),
    ("K+", 0, LAB, [], []),
    ("5 mmol/l", 0, VAL, [], []),
    ("Cl-", 0, LAB, [], []),
    ("106 mmol/l", 0, VAL, [], []),
    ("Ca++", 0, LAB, [], []),
    ("2 mmol/l", 0, VAL, [], []),
    # mục "Tiền sử: Không có ..." -> vừa isHistorical vừa isNegated
    ("viêm họng cấp", 0, DX, [HIST, NEG], ["J02.9"]),
    ("viêm nhiễm ngoài da", 0, DX, [HIST, NEG], []),
]

GT[75] = [  # 1109c ×1  71.txt — bác sĩ hỏi lại người bệnh về nổi mẩn ở lưng + đoạn giảng nguyên nhân
    # Bác sĩ nhắc lại triệu chứng của chính người hỏi -> không isFamily.
    ("nổi mẩn", ALL, SYM, [], []),  # 4 lần, đều là mẩn ở lưng của người hỏi
    ("đỏ hơn trước", 0, SYM, [], []),
    ("nổi sần tạo thành lớp sừng", 0, SYM, [], []),
    ("thuốc viêm nang lông", 0, DRUG, [], []),  # nhóm thuốc theo bệnh, RxNorm không có
    # --- đoạn giảng nguyên nhân chung (không phải BN cụ thể -> không assertion) ---
    ("suy giảm chức năng gan", 0, DX, [], ["K72.9"]),
    ("nổi mề đay", 0, DX, [], ["L50.9"]),
    ("bệnh vảy nến", 0, DX, [], ["L40.9"]),
    # "tác dụng phụ của một số loại thuốc chữa bệnh": không có tên thuốc -> không gán.
]

GT[73] = [  # 1127c ×1  33.txt — EHR đau ngực/ngất xỉu, mục triệu chứng + đặc điểm triệu chứng
    ("mệt mỏi và weak", 0, SYM, [], []),  # dịch máy sót chữ Anh, giữ nguyên bề mặt
    ("ngủ quên", 0, SYM, [], []),
    ("ngất xỉu", 0, SYM, [], []),
    ("giảm khả năng quan hệ tình dục với bạn tình", 0, SYM, [], []),
    ("Đau buốt khi đi tiểu", 0, SYM, [], []),  # ở đây là có thật (khác GT[53] phủ định)
    ("chán ăn", 0, SYM, [], []),
    ("nôn từng đợt sau khi ăn", 0, SYM, [], []),
    # --- mục "Đặc điểm triệu chứng": mô tả chi tiết cơn đau ngực ---
    ("đau ngực", 0, SYM, [], []),
    ("nhói", 0, SYM, [], []),
    ("lan xuống cánh tay trái", 0, SYM, [], []),
    ("tê bì ở cánh tay trái trên", 0, SYM, [], []),
    ("đau ở cánh tay trái dưới và bàn tay", 0, SYM, [], []),
    # "không giảm khi dùng bất kỳ thuốc nào": không có tên thuốc -> không gán.
    ("shortness of breath", 0, SYM, [], []),  # dịch máy để nguyên tiếng Anh
    ("yếu", 0, SYM, [], []),
    ("đau rát khi đi tiểu", 0, SYM, [], []),
    ("Nôn mửa", 0, SYM, [], []),
    ("ngất xỉu", 1, SYM, [], []),  # "cơn ngất xỉu: 2 tháng trước"
    # "không nhớ bị đánh trống ngực, chóng mặt" -> phủ định (tiền lệ "khônghi nhận")
    ("đánh trống ngực", 0, SYM, [NEG], []),
    ("chóng mặt", 0, SYM, [NEG], []),
    ("lasix", 0, DRUG, [], ["202991"]),  # "đã dùng thêm 80mg po lasix ở nhà"
]

GT[198] = [  # 315c ×1  43.txt — "Các bệnh lý mạn tính" + thuốc trước nhập viện (EHR ảo giác)
    ("Bệnh bạch cầu dòng tủy mãn tính", 0, DX, [HIST], ["C92.1"]),
    ("tăng cholesterol máu đơn thuần", 0, DX, [HIST], ["E78.0"]),
    ("tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("gleevec", 0, DRUG, [NEG], ["282386"]),  # "(ngừng uống cách nhập viện 5 ngày)"
    ("allopurinol", 0, DRUG, [NEG], ["519"]),
    ("Thuốc giảm đau", 0, DRUG, [NEG], []),
]
# 149 = 126 ký tự đầu của 198 (hết dòng "tăng cholesterol máu đơn thuần"): dòng
# "tăng huyết áp" + tiêu đề "Thuốc trước khi nhập viện" bị THAY bằng một mẩu QA
# mẩn ngứa, rồi mới quay lại 3 dòng thuốc. Chỉ 2 nhãn đầu thừa hưởng được.
SHARE[149] = (198, 126)
GT[149] = [  # 493c ×1  63.txt — đuôi 367c
    # người hỏi tự kể về mình -> không isFamily
    ("thuốc kháng B-histamin", 0, DRUG, [], []),  # nhóm thuốc, RxNorm không có
    ("mẩn ngứa", 0, SYM, [], []),
    # --- trở lại 3 dòng thuốc của EHR ---
    ("gleevec", 0, DRUG, [NEG], ["282386"]),
    ("allopurinol", 0, DRUG, [NEG], ["519"]),
    ("Thuốc giảm đau", 0, DRUG, [NEG], []),
]

GT[235] = [  # 194c ×1  65.txt — câu hỏi của người bệnh về rụng tóc từng mảng (tự kể -> không FAM)
    ("rụng tóc từng mảng", 0, DX, [], ["L63.9"]),
    # "điều trị nhiều thuốc": không có tên thuốc/nhóm thuốc -> không gán (tiền lệ
    # "bỏ lỡ 3 ngày dùng một số thuốc" ở GT[74]).
]
SHARE[246] = (235, 169)  # 246 = 169 ký tự đầu của 235 (thiếu dòng "Câu trả lời"), đuôi rỗng

GT[241] = [  # 182c ×1  31.txt — mục "Tiền sử bệnh" (tiền sử dùng thuốc)
    ("NSAID", 0, DRUG, [NEG], []),  # "(đã ngừng)" -> isNegated, tiền lệ GT[44]
    ("đau đầu gối", 0, SYM, [HIST], []),  # nằm trong mục Tiền sử bệnh
    ("omeprazole", 0, DRUG, [], ["7646"]),  # "(bắt đầu dùng)" -> đang dùng
]
SHARE[248] = (241, 158)  # 248 = 158 ký tự đầu của 241, đuôi rỗng

GT[204] = [  # 301c ×1  73.txt — mục "Tiền sử bệnh nội khoa" (cùng BN với block 60/79)
    # "Các bệnh lý mạn tính" -> isHistorical (tiền lệ block 14/20/87/88/98)
    ("Viêm loét đại tràng", 0, DX, [HIST], ["K51"]),
    ("Bệnh gan do rượu", 0, DX, [HIST], ["K70"]),
    # "phẫu thuật tạo hậu môn nhân tạo ...": thủ thuật -> không gán.
    ("thuốc giảm đau opioid", 0, DRUG, [HIST], []),  # nhóm thuốc (tiền lệ GT[60]/GT[79]);
    # SỬA đợt 84.txt: bề mặt nằm dưới "Thuốc trước khi nhập viện" -> phải có HIST như
    # GT[9]/GT[87]/GT[257]. Tiền lệ GT[60]/GT[79] không có HIST vì ở đó bề mặt nằm
    # trong phần bệnh sử hiện tại, không phải mục thuốc trước nhập viện.
]
SHARE[221] = (204, 248)  # 221 = 248 ký tự đầu của 204, đuôi rỗng

GT[179] = [  # 385c ×1  27.txt — mục "3. Đánh giá tại bệnh viện" của EHR não úng thuỷ
    ("Phù gai thị", 0, SYM, [], []),
    ("Tăng nhãn áp", 0, DX, [HIST], ["H40.9"]),  # "so với ct đầu từ lần nhập viện trước"
    ("chụp cắt lớp vi tính (ct)", 0, LAB, [], []),
    # --- đoạn giảng VPHT ghép vào cuối (không có BN cụ thể -> không assertion) ---
    ("nang chứa khí hay dịch nhỏ (<2cm)", 0, DX, [], []),
    ("áp-xe phổi", 0, DX, [], ["J85.2"]),
]
# 203 = 250 ký tự đầu của 179 (hết dòng "Tăng nhãn áp ... nhập viện trước"), rồi
# thay đoạn giảng VPHT bằng dòng "Phù gai thị" thứ hai của cùng EHR.
SHARE[203] = (179, 250)
GT[203] = [  # 303c ×1  23.txt — đuôi 53c
    ("Phù gai thị", 1, SYM, [], []),
]

# ------------------------------------
# 3 block còn lại của file 58.txt (98/224/165 đã xong) -> gán TRỌN file.
# 58.txt ghép nhiều nguồn: 98 (tiền sử + XN của EHR đái tháo đường) -> 224 (SHARE 221c
# của 98) -> 165 (mục "3. Đánh giá tại bệnh viện" của EHR tăng kali máu) -> 302 (dòng
# "2. Chẩn đoán" của một BỆNH ÁN TÓM TẮT) -> 283 (mục "3. Tiên lượng" cùng bệnh án tóm
# tắt đó) -> 202 (mục "4. Hướng điều trị" — 4 dòng TRÙNG NGUYÊN VĂN 57.txt/GT[103]).
# Quy ước chốt:
#  - 302 + 283 là cùng một bệnh án tóm tắt (ĐTĐ typ II + tăng HA), lần khám HIỆN TẠI
#    -> KHÔNG assertion (tiền lệ dòng "Chẩn đoán:" ở GT[311]/GT[233]/GT[295]).
#  - 202 trùng nguyên văn GT[103] -> DÙNG LẠI Y NGUYÊN mã + assertion của GT[103].
# ------------------------------------

GT[302] = [  # 69c ×1  58.txt — dòng "2. Chẩn đoán" của bệnh án tóm tắt
    # "2.  Chẩn đoán:": tiêu đề -> không gán (GT[142]).
    ("Đái tháo đường typ II", 0, DX, [], ["E11"]),  # E11 "Đái tháo đường typ 2"; y như
    # GT[68] ("ĐTD typ II" -> E11) và GT[98] cùng file 58.txt. GIỮ "typ II" trong bề mặt
    # vì chính nó key ra mã E11 thay vì E14 (quy ước "giai đoạn/độ nào key ra mã thì giữ",
    # tiền lệ giai đoạn 5 -> N18.5).
    # Dấu "/" ở đây nối HAI chẩn đoán độc lập (ĐTĐ và tăng HA) -> tách 2 khái niệm,
    # KHÁC quy ước "cụm nối bằng / là một bề mặt" (chỗ đó / nối 2 cách gọi cùng một thứ).
    ("Tăng HA", 0, DX, [], ["I10"]),  # I10 "Tăng huyết áp vô căn (nguyên phát)", y như
    # GT[98] cùng file gán "tăng HA". CẮT "độ III" khỏi bề mặt: ICD-10 KHÔNG có mã con
    # theo độ tăng huyết áp (chỉ phân theo tổn thương tim/thận I11–I13), nên "độ III" là
    # hậu tố MỨC ĐỘ thuần -> cắt (quy ước cắt mức độ; ngược với N18.5/L89.3 nơi giai đoạn
    # có mã con riêng). "đáp ứng với thuốc": đáp ứng điều trị -> không gán, và KHÔNG NEG
    # (bệnh vẫn đang có, chỉ là kiểm soát được — y như GT[21] "đái tháo đường được kiểm
    # soát bằng chế độ ăn").
]

GT[283] = [  # 95c ×1  58.txt — mục "3. Tiên lượng" của cùng bệnh án tóm tắt
    # "3.  Tiên lượng:": tiêu đề -> không gán. Lời văn tiên lượng ("ổn định từng đợt",
    # "cần chú ý") không gán, chỉ lấy tên bệnh/biến chứng nằm trong đó (tiền lệ GT[303],
    # cũng là mục "3. Tiên lượng").
    ("Bệnh mạn tính", 0, DX, [], []),  # nói chung "bệnh mạn tính", KHÔNG có tên bệnh cụ
    # thể -> candidates RỖNG. Không gán E11/I10 "cho khớp bệnh án": bề mặt không nêu bệnh
    # nào, thêm mã sẽ hạ Jaccard (quy ước không thêm mã phòng hờ). Vẫn gán DX vì đây là
    # một khái niệm bệnh (tiền lệ GT[303] "bệnh tổn thương mạn tính").
    ("biến chứng tại cơ quan đích", 0, DX, [NEG], []),  # biến chứng cơ quan đích của
    # tăng HA/ĐTĐ là một trạng thái bệnh lý -> DX, nhưng không nêu cơ quan nào nên không
    # có mã ICD tương ứng -> candidates rỗng.
    # NEG: "cần chú ý biến chứng" = biến chứng CHƯA xảy ra, đang dự phòng cho BN CỤ THỂ
    # -> đúng quy ước "biến chứng nêu ra để PHÒNG cho một BN cụ thể => isNegated"
    # (tiền lệ GT[121]/GT[247]). Khác mục tiêu điều trị trong bài giảng (không assertion)
    # vì đây là bệnh án của một BN thật.
]

# ------------------------------------
# 3 BLOCK CUỐI CÙNG -> phủ 100% corpus.
# 300: câu mở đầu QA về huyết áp trong 93.txt; "Huyết áp" ở đây là TÊN phép đo
#      (y GT[157]/GT[254] cùng nguồn QA), không phải bệnh tăng huyết áp.
# 23 + 330: chỉ là tiêu đề mục "Tiền sử bệnh (lý)" -> không có khái niệm nào.
#      Khai rỗng tường minh để giữ lý do tại chỗ.
# ------------------------------------

GT[300] = [  # 71c ×1  93.txt — "Huyết áp có thể tạm thời thay đổi trong..."
    ("Huyết áp", 0, LAB, [], []),  # tên phép đo, y GT[157]/GT[254]
]
GT[23] = []  # 19c ×2  6.txt, 11.txt — chỉ tiêu đề "1.  Tiền sử bệnh lý"
GT[330] = []  # 16c ×1  98.txt — chỉ tiêu đề "1.  Tiền sử bệnh"

# ------------------------------------
# Block 290 = block đầu file 68.txt (47/1582 đã xong) -> gán TRỌN file.
# 290 = mục "1. Tiền sử bệnh / Bệnh lý mãn tính" của CÙNG bệnh nhân với GT[47]
# (EHR bệnh 3 thân động mạch vành) -> isHistorical toàn block.
# ------------------------------------

GT[290] = [  # 83c ×1  68.txt — bệnh mạn: bệnh động mạch vành + bệnh lý TK ngoại biên
    ("bệnh động mạch vành", 0, DX, [HIST], ["I25.9"]),  # y GT[193]/GT[55]
    ("bệnh lý thần kinh ngoại biên", 0, DX, [HIST], ["G62.9"]),  # y GT[47] CÙNG bệnh
    # án -> G62.9. KHÔNG dùng E11.4 như GT[98] vì ở đó bệnh nhân có đái tháo đường
    # kèm theo trong cùng danh sách; ở đây không có ĐTĐ -> mã bệnh TK ngoại biên chung.
]

# ------------------------------------
# Block 287 = block còn lại của file 65.txt (0/235/76/18 đã xong) -> gán TRỌN file.
# 287 = câu mở đầu phần trả lời của bác sĩ, cùng ca với GT[235] (BN tự kể -> không FAM).
# ------------------------------------

GT[287] = [  # 93c ×1  65.txt — "Bạn đang có vấn đề về rụng tóc"
    ("rụng tóc", 0, SYM, [], []),  # tiền lệ GT[76] cùng file: "rụng tóc" đứng một mình
    # (không có "từng mảng/toàn bộ") -> SYM, khác các bề mặt DX có thể loại rõ.
    # "một số phương pháp điều trị": không nêu tên thuốc -> không gán (tiền lệ GT[235]).
]

# ------------------------------------
# Block 279 = block đầu file 84.txt (4/1372 đã xong) -> gán TRỌN file.
# 279 = đúng dòng cuối của block 204 (73.txt, EHR viêm loét đại tràng) bị ghép vào
# dưới nhãn "Câu hỏi từ người dùng"; phần trả lời là QA nấm bẹn (GT[4]) -> 2 nguồn.
# Bề mặt nằm dưới "Thuốc trước khi nhập viện" -> isHistorical (đã sửa GT[204] cho khớp).
# ------------------------------------

GT[279] = [  # 101c ×1  84.txt — "Thuốc trước khi nhập viện: thuốc giảm đau opioid"
    ("thuốc giảm đau opioid", 0, DRUG, [HIST], []),  # nhóm thuốc -> candidates rỗng
]

# ------------------------------------
# Block 275 = block còn lại của file 35.txt (0=DONE_EMPTY, 8/1 đã xong) -> TRỌN file.
# 275 = mẩu "3. Đánh giá tại bệnh viện" của EHR đau ngực gắng sức (CÙNG câu với
# GT[143], 89.txt) ghép giữa QA viêm hang vị. Lần nhập viện này -> không isHistorical.
# ------------------------------------

GT[275] = [  # 110c ×1  35.txt — "Không có đau tại phòng cấp cứu"
    ("đau", 0, SYM, [NEG], []),  # y GT[143] cùng câu, cùng bề mặt
    # Tiêu đề mục + "Kết quả thăm khám lâm sàng" + "Câu trả lời của bác sĩ:" -> không gán.
]

# ------------------------------------
# Block 264 = block đầu file 86.txt (1/1344 đã xong) -> gán TRỌN file.
# 264 = danh sách triệu chứng của EHR ho/thiếu oxy (CÙNG nguồn với GT[53], 62.txt)
# bị ghép vào dưới nhãn "Câu hỏi từ người dùng"; phần trả lời là bài giảng viêm hang
# vị (GT[1]) -> hai nguồn không liên quan. Không có mốc tiền sử -> không assertion.
# ------------------------------------

GT[264] = [  # 130c ×1  86.txt — 4 triệu chứng: ho / nghẹt ngực / khó thở / mệt mỏi
    ("ho", 0, SYM, [], []),  # y GT[53] cùng nguồn
    ("nghẹt ngực", 0, SYM, [], []),  # y GT[53]/GT[52]
    ("khó thở nhẹ-vừa", 0, SYM, [], []),  # y GT[53]: hai bản dịch dính nhau
    ("khó thở khi gắng sức", 0, SYM, [], []),  # -> gán CẢ HAI bề mặt (GT[53] cũng vậy)
    ("mệt mỏi", 0, SYM, [], []),
]

# ------------------------------------
# Block 261 = block đầu file 69.txt (97/112 đã xong) -> gán TRỌN file.
# 261 = mục "1. Tiền sử bệnh" + "Bệnh lý mãn tính" của CÙNG bệnh nhân với GT[97]
# -> isHistorical toàn block. Bệnh nhân chính là người mắc -> không isFamily (y GT[97]).
# Lưu ý: GT[97] gán "trầm cảm"/"ý định tự tử" là NEG vì ở đó câu là "Không xác nhận...".
# Ở block này chúng nằm trong danh sách bệnh mạn/tiền sử KHẲNG ĐỊNH -> KHÔNG NEG.
# Assertion đi theo câu chứa bề mặt, không theo file (quy ước đã chốt).
# ------------------------------------

GT[261] = [  # 135c ×1  69.txt — tiền sử: nhiều lần có ý định tự tử; trầm cảm + lo âu
    ("ý định tự tử", 0, SYM, [HIST], []),  # "trước đây" -> HIST; y cách gán SYM ở GT[97]
    # "do chia tay bạn trai cũ": nguyên nhân đời sống -> không gán.
    ("trầm cảm", 0, DX, [HIST], ["F32.9"]),  # y mã GT[97]
    ("rối loạn lo âu", 0, DX, [HIST], ["F41.9"]),  # y GT[84]/GT[147]/GT[242]
]

# ------------------------------------
# Block 257 = block đầu file 30.txt (32/2086 đã xong) -> gán TRỌN file.
# 257 = mục "Các bệnh mãn tính" + "Thuốc trước khi nhập viện" -> isHistorical toàn
# block. Hai bệnh được PHỦ NHẬN tiền sử -> thêm NEG (tiền lệ GT[141]/GT[97]/GT[9]).
# ------------------------------------

GT[257] = [  # 141c ×1  30.txt — phủ nhận tiền sử tim mạch/thận; đang dùng methadone
    ("bệnh tim mạch", 0, DX, [NEG, HIST], ["I51.6"]),  # "Không có tiền sử ... nào
    # được biết đến" -> bệnh bị loại trừ = DX + NEG; I51.6 "Bệnh tim mạch, không xác
    # định" (tiền lệ GT[118] cùng bề mặt "bệnh tim mạch sớm" -> I51.6).
    ("thận bệnh", 0, DX, [NEG, HIST], ["N28.9"]),  # lỗi dịch đảo chữ của "bệnh thận";
    # giữ nguyên bề mặt bản dịch tại chỗ. N28.9 "Rối loạn của thận..., không xác định".
    ("methadone", 0, DRUG, [HIST], ["6813"]),  # "đang dùng" nhưng nằm dưới mục
    # "Thuốc trước khi nhập viện" -> HIST, không NEG (tiền lệ GT[168] gleevec).
]

# ------------------------------------
# Block 255 = block cuối file 28.txt (0=DONE_EMPTY, 7/50 đã xong) -> gán TRỌN file.
# 255 = mục "3. Đánh giá tại bệnh viện" của EHR hẹp ống sống cổ (cùng nguồn với
# danh sách bệnh mạn ở GT[87]/GT[168]). Lần nhập viện HIỆN TẠI -> không isHistorical.
# ------------------------------------

GT[255] = [  # 143c ×1  28.txt — MRI cột sống cổ: hẹp ống sống + hẹp lỗ liên hợp
    # Tiêu đề "3. Đánh giá tại bệnh viện" / "Kết quả chụp ảnh:" -> không gán.
    ("chụp cộng hưởng từ (mri) cột sống cổ", 0, LAB, [], []),  # giữ TRỌN cụm kể cả
    # viết tắt trong ngoặc thành MỘT bề mặt (tiền lệ GT[63] "độ bão hòa oxy (SPO2)").
    ("hẹp ống sống", 0, DX, [], ["M48.0"]),  # y GT[87]/GT[168]/GT[28] cùng bề mặt.
    # Bảng ICD VN có M48.02 (vùng cổ) nhưng bề mặt KHÔNG chứa vị trí ("C4-5, C5-6,
    # C6-7" là vị trí đứng sau -> cắt) -> giữ M48.0 cho khớp 4 lần đã gán trước.
    ("hẹp lỗ liên hợp", 0, DX, [], ["M99.6"]),  # M99.6 "Hẹp lỗ gian đốt sống" —
    # tên khớp bệnh lý nhất; phần "do cốt hóa/trượt đốt sống" trong tên mã là
    # nguyên nhân, không có trong bề mặt nhưng không có mã trung tính nào khác.
]

# ------------------------------------
# Block 254 = block còn lại của file 55.txt (0=DONE_EMPTY, 95/14/157 đã xong) -> TRỌN file.
# 254 = 2 nguồn ghép: (a) mục "2. Bệnh sử hiện tại" của EHR mệt mỏi/mất trí nhớ
# (= cùng nguồn GT[153], 97.txt), (b) mở đầu câu trả lời QA huyết áp (đuôi ở GT[157]
# cùng file). "Bệnh sử HIỆN TẠI" -> không isHistorical; đoạn giảng chung -> không assertion.
# ------------------------------------

GT[254] = [  # 144c ×1  55.txt — lý do nhập viện: mệt mỏi, mất trí nhớ + mở đầu QA huyết áp
    ("mệt mỏi", 0, SYM, [], []),  # y GT[153] cùng nguồn
    ("mất trí nhớ chi tiết", 0, SYM, [], []),  # y GT[153]
    ("Huyết áp", 0, LAB, [], []),  # tên phép đo, y GT[157] cùng file
]

# ------------------------------------
# Block 253 = block còn lại của file 42.txt (20/61/17 đã xong) -> gán TRỌN file.
# 253 = mục "2. Tiền sử bệnh hiện tại" của EHR ho/thiếu oxy (đuôi ở GT[61] cùng file).
# "Tiền sử bệnh HIỆN TẠI" = HPI của lần nhập viện này -> KHÔNG isHistorical.
# ------------------------------------

GT[253] = [  # 149c ×1  42.txt — lý do nhập viện: ho, thiếu oxy
    ("ho", 0, SYM, [], []),  # tiền lệ GT[61] cùng file / GT[63] gán "ho" là SYM
    ("thiếu oxy", 0, SYM, [], []),  # y GT[63]
    # "Thời điểm khởi phát triệu chứng: 1 tuần trước khi nhập viện": mốc thời gian
    # -> không gán. "Triệu chứng hiện tại": tiêu đề -> không gán.
]

# ------------------------------------
# 80.txt = QA hạt tophi/gout (block 15 + 99 + 231 đã gán) bị CHÈN mấy mục của một
# EHR xơ gan mất bù vào giữa. Còn 2 block -> gán TRỌN file.
#  - block 320 = tiêu đề "2. Tiền sử bệnh hiện tại" + "Chưa phát hiện bất thường"
#    -> kết quả BÌNH THƯỜNG, không có khái niệm nào (tiền lệ GT[163]/GT[93]).
#  - block 272 = "3. Đánh giá tại bệnh viện / Các thủ thuật đã thực hiện".
# ------------------------------------

GT[320] = []  # 51c ×1  80.txt — chỉ tiêu đề mục + "Chưa phát hiện bất thường".
# Khai rỗng tường minh (không dùng DONE_EMPTY) để giữ lại lý do tại chỗ.

GT[272] = [  # 114c ×1  80.txt — 2 thủ thuật chọc dò của EHR xơ gan mất bù
    # Tiêu đề "3. Đánh giá tại bệnh viện" / "Các thủ thuật đã thực hiện" -> không gán
    # (tiền lệ GT[154]/GT[132]/GT[94]).
    ("chọc dò màng phổi", 0, LAB, [], []),  # cùng họ từ với "chọc dò dịch não tủy"
    ("chọc dò dịch ổ bụng", 0, LAB, [], []),  # -> LAB, tiền lệ GT[56]/GT[155]/GT[121].
    # "3L4", "7L": THỂ TÍCH dịch dẫn lưu = lượng của thủ thuật, không phải trị số đo
    # được của xét nghiệm -> không gán VAL (cùng lẽ với liều thuốc, GT[128]).
]

# ------------------------------------
# Block 242 = block đầu file 90.txt (63/1245 đã xong) -> gán TRỌN file.
# 242 = danh sách bệnh mạn tính của CÙNG bệnh nhân với GT[63], bị mất dòng tiêu đề
# "1. Tiền sử bệnh / Các bệnh lý mạn tính" khi ghép (mục kế tiếp là "2. Bệnh sử hiện
# tại") -> vẫn là mục bệnh mạn => isHistorical toàn block (y GT[87]/GT[168]/GT[238]).
# ------------------------------------

GT[242] = [  # 179c ×1  90.txt — bệnh mạn tính: lo âu / THA / táo bón / ngưng thở khi ngủ
    # "Câu trả lời của bác sĩ:", "Chào bạn! Cảm ơn..." -> tiêu đề/lời chào, không gán.
    ("rối loạn lo âu", 0, DX, [HIST], ["F41.9"]),  # y GT[84]/GT[147]
    ("tăng huyết áp", ALL, DX, [HIST], ["I10"]),  # 2 lần: "tăng huyết áp (tăng huyết áp)"
    # = hai bản dịch dính nhau -> gán CẢ HAI cùng mã (tiền lệ GT[266]/GT[218]).
    ("Táo bón mãn tính", 0, DX, [HIST], ["K59.0"]),  # K59.0 "Táo bón"; giữ "mãn tính"
    # trong bề mặt (tiền lệ "Bệnh bạch cầu dòng tủy mãn tính", "bệnh thận mạn").
    ("ngưng thở khi ngủ", 0, DX, [HIST], ["G47.3"]),  # y GT[20]/GT[9]
]

# ------------------------------------
# Block 238 = block đầu file 29.txt (52/134 đã xong) -> gán TRỌN file.
# 238 = mục "1. Tiền sử bệnh nội" / "Các bệnh lý mạn tính" -> isHistorical toàn block
# (y GT[87]/GT[168]). "ho " đứng trước tên bệnh là rác dịch máy -> CẮT khỏi bề mặt
# (tiền lệ GT[87] với "- ho Bệnh bạch cầu dòng tủy mãn tính").
# ------------------------------------

GT[238] = [  # 185c ×1  29.txt — danh sách bệnh mạn tính (CML/THA/ĐTĐ2/rung nhĩ/CKD)
    ("Bệnh bạch cầu dòng tủy mãn tính", 0, DX, [HIST], ["C92.1"]),  # y GT[87]
    ("Tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("Đái tháo đường típ 2", 0, DX, [HIST], ["E11"]),
    ("Rung nhĩ kèm đáp ứng thất nhanh", 0, DX, [HIST], ["I48"]),  # tiền lệ GT[94]
    # "Rung nhĩ kèm nhịp nhanh trên thất" -> I48; giữ phần "kèm ..." trong bề mặt.
    ("bệnh thận mạn, không đặc hiệu", 0, DX, [HIST], ["N18.9"]),  # KHÁC GT[87]:
    # ở đó bề mặt có "Giai đoạn 4" -> N18.4; ở đây không có giai đoạn -> N18.9.
]

# ------------------------------------
# Block 236 = block cuối file 52.txt (0=DONE_EMPTY, 7/86 đã xong) -> gán TRỌN file.
# 236 = mục "1. Tiền sử bệnh" của CÙNG bệnh nhân với GT[147] (98.txt: lạm dụng chất,
# klonopin/clonidine/suboxone) -> dùng lại quyết định của GT[147].
# Cả block nằm dưới nhãn "Tiền sử bệnh" -> isHistorical; dòng về MẸ -> isFamily.
# ------------------------------------

GT[236] = [  # 192c ×1  52.txt — tiền sử: 2 lần tự tử do quá liều thuốc; mẹ đã tử vong
    ("tự tử", 0, SYM, [HIST], []),  # tiền lệ GT[56]/GT[97]/GT[141] gán "tự tử" là SYM
    ("quá liều", 0, DX, [HIST], ["T50.9"]),  # ngộ độc thuốc; tiền lệ GT[100]
    # ("quá liều kháng vitamin K" -> T45.7). Ở đây thuốc là hỗn hợp klonopin
    # (benzodiazepin) + clonidine nên dùng mã chung T50.9 thay vì T42.4/T46.5.
    # KHÔNG lấy trọn "quá liều klonopinclonidine" để tránh nhãn lồng nhau với THUỐC.
    ("klonopinclonidine", 0, DRUG, [HIST], []),  # lỗi dịch dính 2 tên -> y GT[84]/GT[147]
    # "clonidine" ở đây CHỈ nằm bên trong cụm dính (1 lần) -> không gán riêng
    # (khác GT[84], nơi có một lần xuất hiện độc lập).
    # "điều trị đặt nội khí quản" = thủ thuật, "khoa Hồi sức tích cực" = khoa phòng
    # -> không gán.
    ("Đã tử vong", 0, DX, [FAM], []),  # y GT[147] cùng bệnh nhân ("Mẹ Đã tử vong")
]

# ------------------------------------
# Block 230 = block còn lại của file 17.txt (28/2430 đã xong) -> gán TRỌN file.
# 230 = CÂU HỎI người dùng, phần trả lời là GT[28] cùng file. Người hỏi kể
# triệu chứng của CHÍNH MÌNH -> không assertion (y GT[28]).
# ------------------------------------

GT[230] = [  # 199c ×1  17.txt — câu hỏi: chảy máu chân răng + hôi miệng + mảng bám
    ("chảy máu chân răng", 0, SYM, [], []),  # y GT[28] cùng file
    ("hơi thở mùi khó chịu", 0, SYM, [], []),  # cách diễn đạt khác của "hôi miệng"
    # (GT[28] gán "hôi miệng" SYM) -> giữ nguyên bề mặt bản dịch tại chỗ.
    ("mảng bám quanh răng", 0, SYM, [], []),  # CẮT "nhiều" (mức độ/lượng ở ĐẦU cụm,
    # cắt sạch vẫn giữ nghĩa — khác "hơi sốt" ở GT[220] vì "nhiều" tách được).
    # "em 28 tuổi", "bác sĩ tư vấn giúp em với": tuổi/lời nhờ -> không gán.
]

# ------------------------------------
# Block 229 = block còn lại của file 75.txt (block 4 = GT[4] đã xong) -> gán TRỌN file.
# 229 = CÂU HỎI người dùng, nhưng phần trả lời (GT[4]) lại nói về nấm bẹn
# -> đoạn u trực tràng là mẩu EHR khác bị ghép vào. Người hỏi kể bệnh của
# CHÍNH MÌNH (đi khám phân giai đoạn) -> không assertion.
# ------------------------------------

GT[229] = [  # 208c ×1  75.txt — câu hỏi: khối u trực tràng, sinh thiết ra u tuyến
    ("khối u trực tràng", 0, DX, [], ["D37.5"]),  # khối u trực tràng CHƯA rõ lành/ác
    # -> D37.5 "U tân sinh không tiên lượng được tiến triển và tính chất ở trực tràng"
    # (cùng lối chọn với "khối u lành tính" -> D36.9 ở GT trên).
    ("u ác trực tràng", 0, DX, [], ["C20"]),  # C20 "U ác tính ở trực tràng"
    ("sinh thiết", 0, LAB, [], []),  # tiền lệ ("sinh thiết", ALL, LAB) — LAB không assertion
    ("u tuyến", 0, DX, [], ["D12.8"]),  # adenoma; ngữ cảnh là sinh thiết khối trực tràng
    # -> D12.8 "U lành ở trực tràng" (ưu tiên mã khớp giải phẫu bệnh).
    # "phân giai đoạn phẫu thuật", "tem (viết tắt)": thủ thuật/phương pháp mổ
    # (TEM = transanal endoscopic microsurgery) -> KHÔNG gán, đúng quy ước bỏ thủ thuật.
]

# ------------------------------------
# Block 220 = block còn lại của file 34.txt (0=DONE_EMPTY, 64/126 đã xong) -> gán TRỌN.
# 220 = CÂU HỎI của người dùng, phần trả lời là GT[64] (QA đau nửa đầu migraine).
# Người hỏi kể triệu chứng của CHÍNH MÌNH -> không assertion (y GT[64]).
# ------------------------------------

GT[220] = [  # 251c ×1  34.txt — câu hỏi người dùng: đau nửa đầu kèm ớn lạnh/buồn nôn
    # "Chào bác sĩ", "Câu trả lời của bác sĩ:": lời chào/tiêu đề -> không gán.
    ("đau nửa đầu dữ dội", 0, SYM, [], []),  # GT[64] gán "đau nửa đầu" làm SYM; ở đây
    # "dữ dội" nằm liền cuối cụm nên giữ (tiền lệ GT[78]).
    ("ớn lạnh", 0, SYM, [], []),
    ("buồn nôn", 0, SYM, [], []),  # y GT[64] cùng file
    ("hơi sốt", 0, SYM, [], []),  # giữ "hơi" (mức độ nằm ĐẦU cụm, không cắt được sạch
    # mà vẫn giữ nghĩa — tiền lệ "đau nhẹ" ở GT[178]).
    # "có khả năng bị bệnh gì": không nêu tên bệnh -> không gán.
]

# ------------------------------------
# Block 218 = block đầu của file 85.txt (138/115 đã xong) -> gán TRỌN file.
# 218 = mục "1. Tiền sử bệnh nội khoa" / "Các bệnh mãn tính" -> cả block isHistorical.
# Đặc điểm: 2 dòng có bản dịch KÉP nối liền nhau (tên gốc + tên chuẩn ICD) — gán CẢ HAI
# bề mặt với CÙNG mã, y quy ước GT[266] ("Tăng huyết áp (tăng huyết áp vô căn ...)").
# ------------------------------------

GT[218] = [  # 258c ×1  85.txt — mục "Các bệnh mãn tính" (EHR đau bàn chân phải)
    ("Tiểu đường loại 1", 0, DX, [HIST], ["E10"]),  # E10 "Bệnh đái tháo đường típ 1"
    ("đái tháo đường", 0, DX, [HIST], ["E10"]),  # bản dịch thứ hai của CÙNG dòng đó
    # (corpus nối liền "Tiểu đường loại 1 đái tháo đường") -> cùng mã E10, KHÔNG dùng
    # E14: bề mặt này là bản dịch rút gọn của chính chẩn đoán típ 1, không phải một
    # chẩn đoán "không rõ typ" mới (quy ước cùng bệnh nhân dùng mã giống nhau).
    ("tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("tăng lipid máu, không đặc hiệu", 0, DX, [HIST], ["E78.5"]),  # y GT[87]/GT[88]
    ("béo phì", 0, DX, [HIST], ["E66.9"]),  # y GT[4]/GT[281]
    ("Nhiễm trùng đường tiết niệu (UTIs) tái phát", 0, DX, [HIST], ["N39.0"]),  # GIỮ
    # "tái phát" (bổ nghĩa trực tiếp, tiền lệ GT[289]) và giữ ngoặc viết tắt liền cụm.
    ("nhiễm khuẩn đường tiết niệu, vị trí không xác định", 0, DX, [HIST], ["N39.0"]),
    # bản dịch thứ hai = đúng nguyên văn tên mã N39.0 (tiền lệ GT[46]/GT[160]).
]

# ------------------------------------
# Block 216 = block còn lại của file 47.txt (13/94 đã xong, 160=SHARE) -> gán TRỌN file.
# 216 nằm giữa mục 2 và mục 3 của cùng EHR hậu phẫu ung thư đại tràng (GT[13]/GT[94]),
# mở đầu bằng "Chào em" (lỗi ghép nguồn) nhưng nội dung là RÀ SOÁT TRIỆU CHỨNG ÂM TÍNH
# của chính bệnh nhân đó -> toàn bộ là triệu chứng bị PHỦ ĐỊNH -> SYM + isNegated
# (tiền lệ GT[49]: "Phủ nhận buồn nôn, nôn..." -> SYM + NEG; một từ phủ định phủ cả list).
# Không HIST: đây là khám hiện tại.
# ------------------------------------

GT[216] = [  # 262c ×1  47.txt — rà soát triệu chứng âm tính (cùng BN với GT[13]/GT[94])
    # "Chào em": lời chào -> không gán.
    # "đi tiêu không liên quan đến ...": phủ định sự kèm theo -> các triệu chứng liệt kê
    # đều là ÂM TÍNH -> NEG.
    ("đau bụng", ALL, SYM, [NEG], []),  # 2 lần, cả hai đều bị phủ định
    ("buồn nôn", 0, SYM, [NEG], []),
    ("nôn", 1, SYM, [NEG], []),  # [0] nằm trong "buồn nôn"
    ("tiêu chảy", 0, SYM, [NEG], []),
    ("táo bón", 0, SYM, [NEG], []),
    # "Bệnh nhân đang có đi tiêu mỗi ngày": chức năng BÌNH THƯỜNG -> không gán.
    ("sốt", 0, SYM, [NEG], []),
    ("đau ngực", 0, SYM, [NEG], []),
    ("chóng mặt", 0, SYM, [NEG], []),
    ("đánh trống ngực", 0, SYM, [NEG], []),
    ("dịch từ vết mổ", 0, SYM, [NEG], []),  # ở GT[94] cùng BN có "dịch rỉ huyết thanh
    # từ vết mổ" (dương tính) — đây là bản rà soát ngắn, giữ bề mặt as-written.
    ("đỏ da", 0, SYM, [NEG], []),
    ("bục chỉ khâu bụng", 0, SYM, [NEG], []),
]

# ------------------------------------
# Block 215 = block đầu của file 3.txt (125/29/142 đã xong) -> gán TRỌN file.
# 215 là ĐUÔI câu hỏi của cùng người dùng đã gặp ở GT[193]/GT[55] (64.txt): hỏi về MẸ
# bị run tay do thuốc tim -> isFamily. "Nitralmyl" là lỗi gõ của "Nitramyl" (GT[55]).
# ------------------------------------

GT[215] = [  # 263c ×1  3.txt — đuôi câu hỏi người dùng về mẹ bị run tay
    # "1.  Tiền sử bệnh": tiêu đề mục bị ghép lạc vào đây (nội dung phía sau là câu hỏi,
    # không phải tiền sử) -> không gán, và KHÔNG key HIST: triệu chứng đang còn
    # ("không khỏi hẳn").
    ("run tay", ALL, SYM, [FAM], []),  # 2 lần, đều là run tay của mẹ người hỏi (y GT[55])
    # "không khỏi hẳn" -> triệu chứng VẪN CÒN -> không isNegated.
    # "phản ứng phụ của thuốc", "thuốc": không nêu tên thuốc -> không gán (GT[228]).
    ("Nitralmyl", 0, DRUG, [FAM], []),  # lỗi gõ của "Nitramyl" (biệt dược VN của
    # nitroglycerin) -> giữ bề mặt as-written, RxNorm không có -> candidates rỗng (y GT[55]).
]

# ------------------------------------
# 5 block còn lại của file 53.txt (137/16/116 đã xong) -> gán TRỌN file.
# Mỗi block là ĐÚNG MỘT DÒNG của mục "5. Đơn thuốc cho 1 ngày": tên thuốc bị mask bằng
# dãy sao, phần còn lại chỉ là liều/đường dùng.
# Quy ước đã chốt (GT[3]/GT[76]/GT[297]): dãy sao CHÍNH LÀ bề mặt của tên thuốc, gán
# DRUG với candidates rỗng; "x 2 viên", "uống sáng trước ăn"... là liều/cách dùng
# -> không gán. Số thứ tự "1." ... "5." là số dòng -> không gán.
# Đây là đơn thuốc KÊ CHO BỆNH NHÂN ở lần khám hiện tại -> không assertion.
# 314/315 cùng 17 sao và 309/310 cùng 9 sao nhưng ở 4 BLOCK KHÁC NHAU nên mỗi block
# chỉ có 1 lần xuất hiện -> index 0 (chỉ số đếm TRONG block).
# ------------------------------------

GT[314] = [  # 56c ×1  53.txt — dòng 1 đơn thuốc
    ("*****************", 0, DRUG, [], []),  # 17 sao
]

GT[315] = [  # 55c ×1  53.txt — dòng 2 đơn thuốc
    ("*****************", 0, DRUG, [], []),  # 17 sao
]

GT[325] = [  # 44c ×1  53.txt — dòng 3 đơn thuốc
    ("************", 0, DRUG, [], []),  # 12 sao
]

GT[310] = [  # 60c ×1  53.txt — dòng 4 đơn thuốc
    ("*********", 0, DRUG, [], []),  # 9 sao
]

GT[309] = [  # 61c ×1  53.txt — dòng 5 đơn thuốc
    ("*********", 0, DRUG, [], []),  # 9 sao
]

# ------------------------------------
# Block 211 = block còn lại của file 74.txt (221/79 đã xong) -> gán TRỌN file.
# 74.txt ghép: 221 (tiền sử EHR viêm loét đại tràng) -> 211 (một CÂU HỎI QA nấm bẹn
# hoàn toàn khác chèn vào) -> 79 (mục 2 của EHR). 211 là người hỏi tự kể bệnh của MÌNH
# -> KHÔNG assertion (tiền lệ GT[4] cùng chủ đề nấm bẹn).
# ------------------------------------

GT[211] = [  # 277c ×1  74.txt — câu hỏi QA: nam 18t bị nấm bẹn tái phát
    ("bệnh nấm bẹn", 0, DX, [], ["B35.6"]),  # y mã GT[4] "Nấm bẹn" -> B35.6 "Nấm bẹn".
    # GIỮ chữ "bệnh": corpus viết "bị bệnh nấm bẹn", "bệnh" nằm trong tên gọi (tiền lệ
    # GT[193] "bệnh động mạch vành", GT[281] "bệnh Graves").
    # KHÔNG gán:
    #  - "không bị lây lan": phủ định của một diễn biến, không phải tên khái niệm
    #    (quy ước: phủ định-của-bất-thường không gán).
    #  - "chỉ bị hai bên bẹn": vị trí -> không gán.
    #  - "một số loại thuốc", "loại thuốc nào": thuốc không nêu tên -> không gán, nên
    #    cũng không có NEG (tiền lệ GT[228]/GT[235]).
    #  - "tái phát lại": diễn biến -> không gán (tiền lệ GT[318] cắt "tái phát").
]

# ------------------------------------
# 2 block còn lại của file 89.txt (8/143 đã xong) -> gán TRỌN file.
# 89.txt = EHR nghiệm pháp gắng sức bất thường: 266 (mục "Các bệnh lý mãn tính") -> 8
# (mục 2, bệnh sử hiện tại) -> 143 (mục 3, khám) -> 237 (dòng tiêu đề của một bài giảng
# khác bị ghép + 1 câu ECG của chính EHR này).
# Ghi chú: 237 chung 62 ký tự tiền tố với block 180 (49.txt) vì cùng dòng tiêu đề
# "2. Liệu phát miễn dịch tiếp xúc" -> giữ nguyên quyết định của GT[180]: KHÔNG gán
# tiêu đề đó (là tên PHƯƠNG PHÁP, và ở đây thậm chí không có nội dung theo sau).
# ------------------------------------

GT[266] = [  # 123c ×1  89.txt — mục "Các bệnh lý mãn tính"
    # "Các bệnh lý mãn tính": tiêu đề mục -> không gán, key ra HIST cho cả block.
    # Corpus lặp mỗi dòng 2 lần bằng 2 bản dịch khác nhau -> gán ĐỦ CẢ HAI (tiền lệ
    # GT[8] cùng file: "khó thở (khó thở)" gán ALL).
    ("Đái tháo đường", ALL, DX, [HIST], ["E14"]),  # 2 lần; không rõ typ -> E14 (tiền lệ
    # GT[14]/GT[20]). CẮT chữ "tiền sử" khỏi bề mặt: đó là từ đánh dấu thời gian, đã
    # thể hiện bằng isHistorical (tiền lệ GT[45] "tiền sử ... vì sốt" -> gán "sốt").
    ("Tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("tăng huyết áp vô căn (nguyên phát)", 0, DX, [HIST], ["I10"]),  # bản dịch thứ hai,
    # trùng nguyên văn tên mã I10 -> giữ TRỌN cụm kể cả ngoặc (tiền lệ GT[288]
    # "bệnh tăng HA vô căn(nguyên phát)"). Nhãn này bao lần [1] của "tăng huyết áp".
]

GT[237] = [  # 191c ×1  89.txt — tiêu đề bài giảng ghép vào + 1 câu ECG của EHR gắng sức
    # "2. Liệu phát miễn dịch tiếp xúc (contac immunotherapy)": tiêu đề PHƯƠNG PHÁP
    # -> không gán (y GT[180]).
    ("Đoạn ST chênh xuống kiểu xuống dốc", 0, VAL, [], []),  # kết quả nghiệm pháp gắng
    # sức -> VAL (tiền lệ GT[76] "ST chênh xuống" -> VAL). GIỮ "kiểu xuống dốc": đó là
    # hình dạng sóng, phần định danh của phát hiện, không phải hậu tố mức độ.
    # "giai đoạn hồi phục", "sau 1 phút", "sau 5 phút hồi phục": mốc thời gian -> không gán.
]

# ------------------------------------
# Block 194 = block còn lại của file 48.txt (90=SHARE, 12/19 đã xong) -> gán TRỌN file.
# 194 nối tiếp GT[12]/GT[19]: bác sĩ trả lời phụ huynh về đứa CON bị tịt ống tai một bên
# -> bệnh nhân là con người hỏi -> isFamily (tiền lệ GT[12]/GT[19]/GT[164]).
# ------------------------------------

GT[194] = [  # 330c ×1  48.txt — bác sĩ hướng dẫn theo dõi nghe tại nhà (cùng bé với GT[12])
    # "3. Đánh giá tại bệnh viện": tiêu đề mục -> không gán, và mục này KHÔNG key HIST
    # (tiền lệ GT[165]/GT[189]).
    # "bé nghe khá tốt", "quay đúng hướng", "tròn vành rõ chữ": mô tả BÌNH THƯỜNG
    # -> không gán (y GT[12] bỏ "tai trái khỏe mạnh").
    ("chỉ nghe một bên", 0, DX, [FAM], ["H90.1"]),  # SỬA (rà mâu thuẫn): trước gán SYM
    # + rỗng. Block 71 (cùng bé, cùng câu trả lời của bác sĩ) gán bề mặt này DX + H90.1
    # "Giảm thính lực dẫn truyền một bên tai, không hạn chế sức nghe ở tai còn lại" —
    # khớp đúng bệnh cảnh (bé nghe tốt một tai). Giữ isFamily: bệnh của con người hỏi.
    ("lúng túng khi xác định hướng âm thanh", 0, SYM, [FAM], []),  # hậu quả chức năng
    # CỦA CHÍNH BÉ -> vẫn gán (tiền lệ GT[174] gán hậu quả), "có thể" là mức độ chắc chắn
    # -> KHÔNG isNegated (quy ước: hậu quả-nếu-không-điều-trị không phải phủ định).
    # "môi trường ồn ào": bối cảnh -> không gán.
    # "thử gọi con từ nhiều góc khuất": cách theo dõi tại nhà, không phải tên xét nghiệm
    # có định danh -> không gán (khác GT[19] "đo thính lực").
]

# ------------------------------------
# Block 193 = block đầu của file 64.txt (block 55 đã xong) -> gán TRỌN file.
# 193 = câu hỏi của người dùng về MẸ mình (bệnh mạch vành, run tay do Vastarel) -> FAM,
# y GT[55] cùng file (phần trả lời của bác sĩ về cùng người mẹ đó).
# Đuôi block ghép thêm mẩu "Các bệnh lý mạn tính" kiểu EHR (bệnh Graves + tăng lipid máu)
# — KHÔNG phải của người mẹ (corpus ghép nguồn khác) -> chỉ HIST, không FAM.
# ------------------------------------

GT[193] = [  # 331c ×1  64.txt — câu hỏi người dùng về mẹ + mẩu "Các bệnh lý mạn tính"
    ("bệnh động mạch vành", 0, DX, [FAM], ["I25.9"]),  # tiền lệ GT[55] "bệnh mạch vành"
    # -> I25.9. Không HIST: bệnh ĐANG có ("bị ... đã nhiều năm"), không nằm mục tiền sử.
    ("Vastarel", 0, DRUG, [FAM], []),  # biệt dược VN của trimetazidine, KHÔNG có trong
    # RxNorm -> candidates rỗng (y GT[125]).
    ("*********", 0, DRUG, [FAM], []),  # mask là chính bề mặt (quy ước GT[3])
    ("run tay", 0, SYM, [FAM], []),
    ("Vastarel", 1, DRUG, [FAM, NEG], []),  # "đã ngừng sử dụng thuốc Vastarel" -> NEG
    # (quy ước thuốc đã ngừng/hết: GT[16]/GT[103]).
    # "Các bệnh lý mạn tính": tiêu đề mục -> không gán, nhưng key ra HIST cho 2 dòng dưới.
    ("bệnh Graves", 0, DX, [HIST], ["E05.0"]),  # bảng ICD-10 tiếng Việt không có tên
    # "Graves"/"Basedow"; E05.0 "Nhiễm độc tuyến giáp [cường giáp] kèm bướu lan tỏa" là mã
    # chính thức của bệnh Graves.
    ("tăng lipid máu, không đặc hiệu", 0, DX, [HIST], ["E78.5"]),  # y GT[87]/GT[88]
]

# ------------------------------------
# Block 192 = block đầu của file 67.txt (block 1 = bài viêm hang vị, đã xong) -> gán TRỌN.
# 192 là mẩu TIỀN SỬ của cùng EHR (BN nam ung thư dương vật) đã gặp ở GT[28] (17.txt) —
# 6 khái niệm cuối TRÙNG NGUYÊN VĂN -> DÙNG LẠI Y NGUYÊN mã + assertion của GT[28].
# Ở 192 có thêm dòng "- suy tim" mà GT[28] không có (block 17.txt cắt mất dòng đầu).
# Cả list nằm dưới mục kết thúc bằng "Tiền sử phẫu thuật / thủ thuật" -> isHistorical.
# ------------------------------------

GT[192] = [  # 333c ×1  67.txt — mẩu tiền sử EHR ung thư dương vật (y GT[28])
    # "Câu hỏi từ người dùng :", "Tiền sử phẫu thuật / thủ thuật", "Câu trả lời của bác
    # sĩ:": tiêu đề -> không gán.
    ("suy tim", 0, DX, [HIST], ["I50.9"]),  # tiền lệ GT[124]/GT[197]/GT[91]
    ("bệnh mạch máu ngoại biên", 0, DX, [HIST], ["I73.9"]),
    ("bệnh phổi tắc nghẽn mạn tính", 0, DX, [HIST], ["J44.9"]),
    ("Ngưng thở khi ngủ do tắc nghẽn", 0, DX, [HIST], ["G47.3"]),
    ("BiPAP", 0, DRUG, [HIST], []),  # thiết bị thở, không phải thuốc -> candidates rỗng
    ("Ung thư biểu mô tế bào vảy xâm nhập của dương vật", 0, DX, [HIST], ["C60.9"]),
    # CẮT ở "dương vật": trong bản này chữ "dương vậtbiệt" viết liền (lỗi corpus) nhưng
    # ranh giới khái niệm vẫn ở đó, y GT[28].
    ("biệt hóa kém", 0, DX, [HIST], []),
    ("bờ diện cắt dương tính", 0, DX, [HIST], []),
    # "sau cắt bao quy đầu": thủ thuật -> không gán.
]

# ------------------------------------
# Block 191 = block đầu của file 22.txt (49/132 đã xong) -> gán TRỌN file.
# 191 = mục "1. Tiền sử bệnh" + "Thuốc trước khi nhập viện" của CÙNG bệnh nhân với GT[49]
# (BN nữ đau bụng, tự dùng liều cao acetaminophen). Cả block nằm dưới nhãn tiền sử /
# "trước khi nhập viện" -> isHistorical (tiền lệ GT[21]/GT[87]/GT[99] "Thuốc trước khi
# nhập viện" -> HIST). Dùng lại mã của GT[49] cho khái niệm trùng.
# ------------------------------------

GT[191] = [  # 337c ×1  22.txt — mục "1. Tiền sử bệnh" + "Thuốc trước khi nhập viện"
    # "1. Tiền sử bệnh", "Các tập tương tự trước đây:", "Thuốc trước khi nhập viện":
    # tiêu đề mục -> không gán (GT[142]).
    ("khó chịu tương tự", 0, SYM, [HIST], []),  # "Từng bị khó chịu tương tự trong quá
    # khứ" -> triệu chứng của lần trước = isHistorical. Tiền lệ gán "khó chịu" làm SYM:
    # GT[52]/GT[16]. Không NEG: đã từng bị thật.
    # "luôn thuyên giảm khi dùng thuốc": không nêu tên thuốc -> không gán (GT[228]).
    ("acetaminophen", 0, DRUG, [HIST], ["161"]),  # y GT[49] cùng bệnh nhân (RxNorm IN
    # 161). Ở GT[49] không HIST vì bề mặt nằm trong mục "Các sự kiện trước khi nhập viện"
    # của bệnh sử hiện tại; ở đây bề mặt nằm dưới "Thuốc trước khi nhập viện" -> HIST
    # (assertion đi theo MỤC chứa bề mặt).
    # "500mg", "taking 10 pills at a time" (câu chưa dịch), "4 viên mỗi giờ": liều/số
    # lượng -> không gán.
    ("cơn đau dữ dội", 0, SYM, [HIST], []),  # lý do BN tự dùng thuốc trong quá khứ
    ("thuốc an thần", 0, DRUG, [HIST], []),  # nhóm thuốc, không tên cụ thể -> candidates
    # rỗng; y GT[49] cùng bề mặt cũng HIST ("trong quá khứ").
    # "làm hỏng dạ dày của cô ấy": hậu quả diễn đạt dân dã, KHÔNG phải tên chẩn đoán
    # (không nói loét/viêm gì) -> không gán, không thêm K25 phòng hờ.
]

# ------------------------------------
# Block 188 = block đầu của file 66.txt (58 đã xong) -> gán TRỌN file.
# 188 = CÂU HỎI của người dùng (hỏi CHUNG về "những người có u lành tuyến vú" chứ không
# về bản thân hay một người thân cụ thể) -> KHÔNG assertion, y như GT[58] (phần trả lời
# cùng file cũng là kiến thức chung). Dùng lại mã đã chốt ở GT[58] cho khái niệm trùng.
# ------------------------------------

GT[188] = [  # 355c ×1  66.txt — câu hỏi người dùng về vitamin B12 và u lành tuyến vú
    # "Câu hỏi từ người dùng:": tiêu đề -> không gán (GT[142]).
    ("u lành về tuyến vú", 0, DX, [], ["D24"]),  # D24 "U lành ở vú" — cụm chỉ loại u
    # (lành tính ở vú) nhưng vẫn là một khái niệm bệnh -> DX. Không dùng N60.9 "Loạn sản
    # lành tính của tuyến vú": bề mặt nói "u", D24 khớp trực tiếp hơn.
    ("u xơ tuyến vú", 0, DX, [], ["N60.2"]),  # N60.2 trùng nguyên văn tên mã, y GT[58]
    ("u nang tuyến vú", 0, DX, [], ["N60.1"]),  # y GT[58]
    ("vitamin 3b b1 b6 b12", 0, DRUG, [], ["11251"]),  # "vitamin 3b" là CHẾ PHẨM
    # (B1+B6+B12) và "b1 b6 b12" liền sau chỉ là cách viết rõ thành phần, không có dấu
    # phân cách -> lấy TRỌN cụm làm một bề mặt (quy ước "cụm chạy liền thì giữ trọn").
    # Mã 11251 = vitamin B complex, y tiền lệ GT[247] "Vitamin 3B".
    ("vitamin b12", 0, DRUG, [], ["11248"]),  # lần riêng ở câu sau; 11248 = cyanocobalamin,
    # y GT[58] cùng file. (Đây là lần [0] của "vitamin b12" trong block — 3 lần của "b1"
    # đều nằm trong nhãn dài hơn nên không khai riêng.)
    ("khối u ung thư", 0, DX, [], ["C80.9"]),  # y GT[58] gán "ung thư" -> C80.9 (u ác
    # tính không rõ vị trí nguyên phát). Lấy trọn "khối u ung thư" vì corpus viết liền cụm.
    ("khối u lành tính", 0, DX, [], ["D36.9"]),  # D36.9 "U lành ở vị trí không xác định":
    # câu nói CHUNG về u lành tính, không nêu vị trí -> không dùng D24 (đã dành cho bề mặt
    # có chữ "tuyến vú" ở trên). Không dùng D48.9 (u KHÔNG tiên lượng được) vì bề mặt nói
    # rõ "lành tính".
]

# ------------------------------------
# Block 181 = block giữa của file 56.txt (0 và 1 đã xong) -> gán TRỌN file.
# Nội dung TRÙNG NGUYÊN VĂN mục cận lâm sàng của EHR bệnh 3 thân động mạch vành đã gán
# ở GT[47] (68.txt) -> DÙNG LẠI Y NGUYÊN 6 nhãn, không xét lại (quy ước "block là bản
# sao thì quyết định của block nguồn thắng"). Không assertion: đây là kết quả cận lâm
# sàng của lần khám hiện tại.
# ------------------------------------

GT[181] = [  # 383c ×1  56.txt — mục "Cận lâm sàng" của EHR bệnh 3 thân động mạch vành
    # "Cận lâm sàng:", "Kết quả chẩn đoán hình ảnh", "Các thủ thuật đã thực hiện",
    # "Câu trả lời của bác sĩ:": tiêu đề -> không gán (GT[142]).
    ("Đo sức bền cơ tim bằng đồng vị phóng xạ", 0, LAB, [], []),
    ("dị tật cố định vùng trước vách và vách dưới", 0, DX, [], []),  # phát hiện tưới máu
    # cố định trên xạ hình = vùng cơ tim mất sống còn; không có mã ICD tương ứng cho cách
    # diễn đạt này -> candidates rỗng, y GT[47].
    ("giảm chức năng tâm thu thất trái nghiêm trọng", 0, DX, [], ["I50.1"]),
    ("rối loạn chức năng thất trái", 0, DX, [], ["I50.1"]),
    ("Chụp động mạch vành", ALL, LAB, [], []),  # 2 lần: dòng kết quả + dòng thủ thuật
    # ("Chụp động mạch vành can thiệp" — "can thiệp" là phần thủ thuật, không vào bề mặt,
    # nhưng bản thân "Chụp động mạch vành" vẫn là tên thăm dò -> LAB, y GT[47] dùng ALL).
    ("bệnh ba thân động mạch vành nghiêm trọng", 0, DX, [], ["I25.1"]),  # có chữ "bệnh"
    # nên là tên chẩn đoán (đối chiếu GT[233]); I25.1 y GT[47].
]

# ------------------------------------
# Block 178 = block cuối của file 31.txt (241/44 đã xong) -> gán TRỌN file.
# 178 = CÂU HỎI của người dùng kể về EM TRAI mình (giãn thừng tinh) + dòng "Câu trả lời
# của bác sĩ:". Câu trả lời và phần EHR sỏi mật nằm ở block 44 (đã gán).
# Quy ước chốt: chủ thể của mọi triệu chứng ở đây là EM TRAI người hỏi -> isFamily
# (tiền lệ GT[13] mẹ người hỏi, GT[24] con người hỏi, GT[149] bạn người hỏi).
# Ở GT[44] "Giãn thừng tinh" KHÔNG có FAM vì đó là lời bác sĩ giảng chung
# ("Giãn thừng tinh là một trong nhiều nguyên nhân gây vô sinh") — assertion đi theo
# CHỦ THỂ CỦA BỀ MẶT, không theo file.
# ------------------------------------

GT[178] = [  # 395c ×1  31.txt — câu hỏi của người dùng về em trai bị giãn thừng tinh
    ("giãn thừng tinh", 0, DX, [FAM], ["I86.1"]),  # I86.1 "Giãn tĩnh mạch bìu" — y như
    # GT[44] cùng file. CẮT "2.5mm 1 bên" khỏi bề mặt (hậu tố đo lường + vị trí, quy ước
    # đợt 13: GT[154] "Sỏi niệu quản" cắt "lớn hơn 7mm").
    ("đau nhẹ", 0, SYM, [FAM], []),  # "thỉnh thoảng đau nhẹ" — "nhẹ" nằm liền trong cụm
    # 2 chữ, cắt ra thì còn "đau" trơ nghĩa -> giữ nguyên (quy ước mức độ giữa cụm thì giữ).
    ("nóng phần tinh hoàn", 0, SYM, [FAM], []),  # cảm giác nóng vùng tinh hoàn
    ("covid", 0, DX, [], ["U07.1"]),  # tên bệnh được nhắc trong bối cảnh "tình hình
    # covid" (lý do không đi TP.HCM khám) -> vẫn gán DX theo quy ước "tên bệnh trong câu
    # văn chung vẫn gán, recall quan trọng hơn" (tiền lệ GT[30] "bệnh thoái hóa tinh bột"
    # trong bài giảng). KHÔNG isFamily/isNegated: không nói ai mắc, chỉ là bối cảnh dịch.
    # U07.1 "COVID-19, virus được xác định" là mã COVID-19 mặc định; U07.2 dành cho ca
    # chẩn đoán lâm sàng chưa xét nghiệm — ở đây không nói về một ca bệnh nào.
    # KHÔNG gán:
    # - "điều trị thuốc uống 5 tuần", "đã ngừng dùng thuốc": KHÔNG nêu tên thuốc
    #   -> không gán (GT[228]/GT[235]), do đó cũng không có nhãn NEG nào ở đây.
    # - "độ giãn không giảm": mức độ tiến triển của bệnh đã gán ở trên.
    # - "sợ ảnh hưởng tinh trùng ảnh hưởng sinh sản": LO NGẠI về hậu quả, không phải tên
    #   bệnh (khác GT[44] "vô sinh thứ phát" là tên chẩn đoán bác sĩ nêu).
    # - "Câu trả lời của bác sĩ:": tiêu đề -> không gán (GT[142]).
    # - "Tuyến Tỉnh", "chuyên khoa", "hcm": cơ sở/khoa/địa danh -> không gán.
]

# ------------------------------------
# Block 169 = block cuối của file 38.txt (96/107 đã xong) -> gán TRỌN file.
# Nội dung TRÙNG NGUYÊN VĂN mục "Các bệnh lý mạn tính" đã gán ở GT[87] (14.txt) và
# GT[88] (12.txt) — cùng một EHR (BN nam CML dùng gleevec, ảo giác sau ngừng thuốc)
# xuất hiện lại ở file này. -> DÙNG LẠI Y NGUYÊN 13 nhãn của GT[87], không xét lại
# (quy ước "block là bản sao thì quyết định của block nguồn thắng").
# Khác duy nhất: ở đây "Ngã" lần [1] là bề mặt rời (giống GT[87], không cần cú pháp
# [[...]] như GT[88] vì sau "Ngã" là dấu newline bình thường).
# ------------------------------------

GT[169] = [  # 422c ×1  38.txt — mục "1. Tiền sử bệnh nội khoa" / "Các bệnh lý mạn tính"
    ("Bệnh bạch cầu dòng tủy mãn tính", 0, DX, [HIST], ["C92.1"]),
    ("gleevec", 0, DRUG, [HIST], ["282386"]),  # "đang dùng gleevec" -> chỉ HIST
    ("Tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("tăng lipid máu, không đặc hiệu", 0, DX, [HIST], ["E78.5"]),
    ("Đái tháo đường típ 2", 0, DX, [HIST], ["E11"]),
    ("hẹp ống sống", 0, DX, [HIST], ["M48.0"]),
    ("Giả gout", 0, DX, [HIST], ["M11.2"]),  # pseudogout/CPPD = vôi hoá sụn khớp khác
    ("bệnh thận mạn, không đặc hiệu Giai đoạn 4", 0, DX, [HIST], ["N18.4"]),  # giữ
    # "Giai đoạn 4" vì nó key ra mã con N18.4
    ("tăng sản tuyến tiền liệt", 0, DX, [HIST], ["N40"]),
    ("Nhiều lần ngã gần đây", 0, SYM, [HIST], []),
    ("Ngã", 1, SYM, [HIST], []),  # [0] nằm trong "Nhiều lần ngã gần đây"
    ("ảo giác", 0, SYM, [HIST], []),
    ("gleevec", 1, DRUG, [HIST, NEG], ["282386"]),  # "(dừng theo chỉ dẫn sau xuất viện)"
]

# ------------------------------------
# 2 block còn lại của file 33.txt (127/73 đã xong) -> gán TRỌN file.
# 33.txt = 281 (mục "1. Tiền sử bệnh") -> 127 (QA mụn trứng cá của BN 18t, đã gán) ->
# 73 (đặc điểm triệu chứng + sự kiện trước nhập viện, đã gán) -> 189 (mục "3. Đánh giá
# tại bệnh viện"). Block 281 và 73/189 là CÙNG một EHR (BN nam suy tim/rung nhĩ, đau
# ngực, dùng lasix ở nhà không đỡ), mẩu QA mụn ở giữa là của nguồn khác.
# Quy ước chốt:
#  - 281 dưới "1. Tiền sử bệnh" + "Các bệnh lý mạn tính" -> isHistorical toàn block
#    (tiền lệ GT[21]/GT[14]/GT[20]/GT[87]/GT[98]).
#  - 189 dưới "3. Đánh giá tại bệnh viện" -> KHÔNG assertion (GT[143]/GT[154]/GT[94]).
# ------------------------------------

GT[281] = [  # 99c ×1  33.txt — mục "1. Tiền sử bệnh" / "Các bệnh lý mạn tính"
    # 2 dòng tiêu đề -> không gán (GT[142]). Cả 4 dòng gạch đầu dòng là bệnh mạn tính
    # -> isHistorical. Block này gần y hệt GT[21] (51/70.txt) nên dùng lại mã đã chốt.
    ("rung nhĩ", 0, DX, [HIST], ["I48.9"]),  # I48.9 "Rung nhĩ và/hoặc cuồng nhĩ, không
    # xác định" — y như GT[182]/GT[204] cùng bề mặt. Không dùng I48.2 "Rung nhĩ mạn tính"
    # dù đứng dưới nhãn "bệnh lý mạn tính": nhãn mục là của cả danh sách, không phải một
    # từ định danh trong tên bệnh (quy ước "tiêu đề mục không kéo vào bề mặt/không key mã").
    ("tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("suy tim, không đặc hiệu", 0, DX, [HIST], ["I50.9"]),  # giữ ", không đặc hiệu" vì
    # đó là phần định danh mã .9, y như GT[21] cùng bề mặt.
    ("béo phì", 0, DX, [HIST], ["E66.9"]),  # y GT[21]/GT[20]/GT[4]/GT[51]
]

GT[189] = [  # 352c ×1  33.txt — mục "3. Đánh giá tại bệnh viện" (thủ thuật + phát hiện)
    # Tiêu đề "3. Đánh giá tại bệnh viện" / "Các thủ thuật đã thực hiện" / "Các phát hiện
    # chẩn đoán khác" -> không gán (GT[132]/GT[94]/GT[154]/GT[22]).
    # 7 dòng "Nhận X" / "Được cho X" là THUỐC dùng trong lần nhập viện này -> gán DRUG,
    # KHÔNG assertion; liều/đường dùng ("2 sl", "80mg", "iv", "po", "8mg", "1mg", "10mg")
    # cắt khỏi bề mặt (quy ước liều thuốc chốt ở đợt 12).
    ("ntg", 0, DRUG, [], ["4917"]),  # viết tắt nitroglycerin; RxNorm KHÔNG có concept tên
    # "ntg" nên lấy mã hoạt chất IN 4917 y như GT[55]/GT[212] "nitroglycerin" (tiền lệ
    # GT[271] gán "ASA" -> 1191 của aspirin: viết tắt vẫn là bề mặt riêng nhưng mã trỏ về
    # hoạt chất). Chỉ gán lần [0] (dòng y lệnh); 2 lần sau ở dòng "Với ntg ..." xem dưới.
    ("asa", 0, DRUG, [], ["1191"]),  # aspirin IN 1191, y GT[271] "ASA" (matcher không
    # phân biệt hoa/thường; bề mặt xuất ra là chuỗi thật trong block = "asa").
    ("lasix", 0, DRUG, [], ["202991"]),  # y GT[73] cùng file / GT[98] / GT[165]
    ("morphine", 0, DRUG, [], ["7052"]),  # RxNorm IN 7052 (GT[196] "morphineoral" cùng mã)
    ("dilaudid", 0, DRUG, [], ["224913"]),  # biệt dược CÓ trong RxNorm -> dùng mã BN
    # 224913 (quy ước BN nếu có, tiền lệ GT[182] eliquis / GT[63] tylenol).
    ("metoprolol", 0, DRUG, [], ["6918"]),  # y GT[175]/GT[34]/GT[154]
    ("diltiazem", 0, DRUG, [], ["3443"]),  # RxNorm IN 3443
    # --- "Các phát hiện chẩn đoán khác": 2 dòng TRÙNG NGUYÊN VĂN nhau (lỗi lặp của
    # corpus) -> gán ĐỦ CẢ HAI LẦN (quy ước "cụm lặp do dịch thì gán mọi lần").
    # "ntg" ở đây là lần [1] và [2]; không dùng ALL được vì lần [0] là dòng y lệnh đã gán
    # riêng ở trên (ALL sẽ trùng span).
    ("ntg", 1, DRUG, [], ["4917"]),
    ("ntg", 2, DRUG, [], ["4917"]),
    ("khó thở", ALL, SYM, [], []),  # 2 lần; "cải thiện" là mức độ -> không vào bề mặt,
    # và KHÔNG isNegated vì chỉ đỡ chứ chưa hết (khác "hết X" -> NEG).
    ("đau ngực", ALL, SYM, [], []),  # 2 lần; "vẫn còn" -> triệu chứng đang có.
    ("nhịp tim", 0, LAB, [], []),  # "nhịp tim cải thiện thành" (câu bị cắt cụt ở cuối
    # file) -> đây là NHÃN phép đo nhịp tim -> TÊN_XÉT_NGHIỆM, y GT[143]/GT[154] ("hr").
    # Không có trị số theo sau (file cắt giữa câu) -> không có nhãn VAL.
]

GT[165] = [  # 430c ×1  58.txt — mục "3. Đánh giá tại bệnh viện" của EHR tăng kali máu
    ("kali", 0, LAB, [], []),
    ("6.3", 0, VAL, [], []),
    ("kali (k)", 0, LAB, [], []),
    (".8", 0, VAL, [], []),  # bản dịch mất chữ số đầu, giữ nguyên bề mặt
    ("ure (bun)", 0, LAB, [], []),
    ("83", 0, VAL, [], []),
    ("creatinine", 0, LAB, [], []),
    ("5.7", 0, VAL, [], []),
    ("hemoglobin", 0, LAB, [], []),
    ("7.8", 0, VAL, [], []),
    ("hba1c", 0, LAB, [], []),
    ("6.5", 0, VAL, [], []),
    ("bnp", 0, LAB, [], []),
    ("21,000", 0, VAL, [], []),
    ("tổng phân tích nước tiểu", 0, LAB, [], []),
    ("cúm", 0, LAB, [], []),  # "cúm âm tính" -> tiền lệ GT[58]
    ("âm tính", 0, VAL, [], []),
    ("chụp x-quang ngực", 0, LAB, [], []),
    ("Tăng gánh nhẹ tuần hoàn phổi", 0, DX, [], []),
    ("tràn dịch màng phổi hai bên nhẹ", 0, DX, [], ["J90"]),
    ("tim to", 0, DX, [], ["R93.1"]),
    ("insulin", 0, DRUG, [], []),  # RxNorm không có IN "insulin" chung
    ("dextrose", 0, DRUG, [], ["4850"]),  # = glucose
    ("tăng kali máu", 0, DX, [], ["E87.5"]),
    ("lasix", 0, DRUG, [], ["202991"]),
]
# 167 = 201 ký tự đầu của 165 (đến hết dòng "tổng phân tích nước tiểu"), rồi ghép
# một mẩu tư vấn dinh dưỡng, sau đó quay lại đúng 2 dòng "thủ thuật" của 165.
# Phần chung chỉ tới hết dòng nước tiểu nên 6 nhãn cuối phải khai lại tay.
SHARE[167] = (165, 201)
GT[167] = [  # 425c ×1  57.txt
    # --- mẩu tư vấn dinh dưỡng ghép vào (nói chung, không assertion) ---
    ("Folate", 0, DRUG, [], ["4511"]),  # folic acid
    ("Vitamin C", 0, DRUG, [], ["1151"]),
    # "các carotenoid", "các chất chống oxy hóa Flavonoid": nhóm chất chống oxy hóa
    # trong thực phẩm, RxNorm không có -> vẫn gán THUỐC theo tiền lệ nhóm thuốc,
    # candidates rỗng.
    ("carotenoid", 0, DRUG, [], []),
    ("Flavonoid", 0, DRUG, [], []),
    # --- trở lại 2 dòng thủ thuật của EHR ---
    ("insulin", 0, DRUG, [], []),
    ("dextrose", 0, DRUG, [], ["4850"]),
    ("tăng kali máu", 0, DX, [], ["E87.5"]),
    ("lasix", 0, DRUG, [], ["202991"]),
]

GT[157] = [  # 446c ×1  55.txt — câu trả lời của bác sĩ cho QA "đo HA tại phòng khám"
    # Đoạn giảng chung, không phải bệnh nhân cụ thể -> không gán assertion
    # (thống nhất với GT[76]/GT[81]/GT[118]).
    ("lo âu căng thẳng", 0, SYM, [], []),
    ("huyết áp", ALL, LAB, [], []),  # 3 lần, đều là tên phép đo
]
# 163 = 308 ký tự đầu của 157 rồi rẽ sang mục kết quả CĐHA của một EHR khác.
# Cả 3 lần "huyết áp" nằm trong 308 ký tự đầu và số lần ở con cũng đúng 3
# -> thừa hưởng được cả hai nhãn, chỉ cần gán tay phần đuôi.
SHARE[163] = (157, 308)
GT[163] = [  # 434c ×1  93.txt — đuôi 126c: mẩu kết quả CĐHA, cùng nguồn với GT[25]
    ("chụp ct", 0, LAB, [], []),  # "chụp ctchưa phát hiện" dính chữ
    # "chưa phát hiện bất thường trên phim chụp": kết quả mô tả bằng chữ, theo
    # tiền lệ GT[25] chỉ gán KẾT_QUẢ cho giá trị số -> bỏ.
    ("đại tràng giãn", 0, DX, [], ["K59.3"]),  # "Theo dõi đại tràng giãn"
]

GT[98] = [  # 810c ×1  58.txt — mục "Tiền sử bệnh" + XN máu của EHR đái tháo đường
    # "Tiền sử bệnh nội khoa" -> toàn bộ isHistorical (tiền lệ block 14/20/87/88)
    ("Tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("Đái tháo đường", 0, DX, [HIST], ["E11"]),
    ("bệnh lý thần kinh ngoại biên", 0, DX, [HIST], ["E11.4"]),
    ("Suy tim không do thiếu máu cơ tim", 0, DX, [HIST], ["I50.9"]),
    ("Bệnh thận mạn tính", 0, DX, [HIST], ["N18.9"]),
    # --- phần theo dõi hiện tại: không còn isHistorical ---
    ("người đỡ mệt", 0, SYM, [], []),
    ("Nhịp tim đều", 0, SYM, [], []),
    ("85 lần/phút", 0, VAL, [], []),
    ("HA", 0, LAB, [], []),
    ("130/75mmHg", 0, VAL, [], []),
    ("XN máu", 0, LAB, [], []),
    ("Glucose", 0, LAB, [], []),
    ("5,8 mmol/l", 0, VAL, [], []),
    ("Cholesterol", 0, LAB, [], []),
    ("4,7 mmol/l", 0, VAL, [], []),
    ("Triglycerid", 0, LAB, [], []),
    ("1,9mmol/l", 0, VAL, [], []),
    ("LDL - cholesterol", 0, LAB, [], []),
    ("2,2 mmol/l", 0, VAL, [], []),
    ("HDL - cholesterol", 0, LAB, [], []),
    ("2mmol/l", 0, VAL, [], []),
    ("HbA1c", 0, LAB, [], []),
    ("7,5 pP%", 0, VAL, [], []),  # lỗi dịch "pP%", giữ nguyên bề mặt
    # "Uống rượu 30 năm": hành vi, không phải chẩn đoán/thuốc -> không gán.
    ("tăng HA", 0, DX, [HIST], ["I10"]),  # "Phát hiện tăng HA từ năm 2009"
    ("dị ứng", 0, DX, [NEG], []),  # "Tiền sử dị ứng: Không có"
]
SHARE[224] = (98, 221)  # 224 = 221 ký tự đầu của 98, đuôi rỗng

GT[202] = [  # 304c ×1  58.txt — mục "4. Hướng điều trị": 4 dòng TRÙNG NGUYÊN VĂN GT[103]
    # 4 dòng này là bản sao y nguyên của 3 dòng cuối GT[103] (57.txt) -> DÙNG LẠI Y NGUYÊN
    # mã + assertion, không xét lại (quy ước "block là bản sao thì quyết định của block
    # NGUỒN thắng"). Cả 6 nhãn thuốc đều NEG vì thuốc đã hết.
    ("isosorbide", 0, DRUG, [NEG], ["6057"]),
    ("crestor", 0, DRUG, [NEG], ["320864"]),
    ("carvedilol", 0, DRUG, [NEG], ["20352"]),
    ("isosorbide", 1, DRUG, [NEG], ["6057"]),  # "Hết isosorbide, crestor, carvedilol"
    ("crestor", 1, DRUG, [NEG], ["320864"]),
    ("carvedilol", 1, DRUG, [NEG], ["20352"]),
    # "Các xét nghiệm xét nghiệm được kiểm tra bởi PCP": lỗi dịch lặp chữ, là nhãn mục
    # chung -> không gán (y như GT[103] không gán cụm này).
    ("kali", 0, LAB, [], []),  # index 0: TRONG BLOCK 202 chỉ có 1 lần (ở GT[103] là lần
    # [1] vì block đó có "tăng kali máu" đứng trước) — chỉ số đếm TRONG block.
    ("6.3", 0, VAL, [], []),
    # "mẫu không tan máu": nhận xét chất lượng mẫu, không phải kết quả XN -> không gán.
    # "bác sĩ nội trú trực", "khoa Cấp cứu": chức danh/khoa -> không gán (GT[142]).
]

GT[103] = [  # 778c ×1  57.txt — EHR tăng kali máu/hết thuốc (mục "Bệnh sử hiện tại")
    ("xét nghiệm bất thường", 0, LAB, [], []),
    ("tăng kali máu", 0, DX, [], ["E87.5"]),
    ("Creatinine", 0, LAB, [], []),
    ("Torsemide", 0, DRUG, [], ["38413"]),
    ("torsemide", 1, DRUG, [NEG], ["38413"]),  # "đề nghị ngừng sử dụng torsemide"
    ("đường huyết", 0, LAB, [], []),
    # "hết que thử đường máu": TÊN_XÉT_NGHIỆM không được mang assertion theo đề,
    # nên gán trần, không isNegated.
    ("que thử đường máu", 0, LAB, [], []),
    ("glucose", 0, LAB, [], []),
    ("glargine", 0, DRUG, [NEG], ["274783"]),  # "glucose là thấp, nên ngừng dùng glargine"
    ("ngã", 0, SYM, [], []),
    # SỬA ở đợt 26: 3 nhãn lần [0] trước đây THIẾU NEG. Câu "(isosorbide, crestor,
    # carvedilol) đã hết khi đi khám PCP" nói CÙNG MỘT sự việc với câu sau "Hết
    # isosorbide... khoảng 3 tuần trước" -> thuốc đã hết = isNegated (GT[16] "đã hết
    # thuốc", GT[60]/GT[79]). Để lệch giữa 2 lần trong cùng block là tự mâu thuẫn.
    ("isosorbide", 0, DRUG, [NEG], ["6057"]),
    ("crestor", 0, DRUG, [NEG], ["320864"]),
    ("carvedilol", 0, DRUG, [NEG], ["20352"]),
    ("isosorbide", 1, DRUG, [NEG], ["6057"]),  # "Hết isosorbide, crestor, carvedilol"
    ("crestor", 1, DRUG, [NEG], ["320864"]),
    ("carvedilol", 1, DRUG, [NEG], ["20352"]),
    ("kali", 1, LAB, [], []),
    ("6.3", 0, VAL, [], []),
    # "Dùng xe đẩy hàng làm dụng cụ hỗ trợ đi lại": dụng cụ, không gán.
]

# block 116 = 493 ký tự đầu của 103 rồi rẽ sang mục kế hoạch điều trị của EHR khác.
SHARE[116] = (103, 493)
GT[116] = [  # 658c ×1  53.txt — đuôi 165c: kế hoạch xét nghiệm/điều trị
    ("CTM", 0, LAB, [], []),
    ("SHM", 0, LAB, [], []),
    ("chụp XQ phổi", 0, LAB, [], []),
    ("đường máu", 1, LAB, [], []),  # [0] nằm trong "que thử đường máu"
    ("rối loạn lipid máu", 0, DX, [], ["E78.5"]),  # SỬA (rà mâu thuẫn sau khi phủ
    # 100%): trước dùng E78.9. Chốt E78.5 "Tăng lipid máu, không xác định" làm chuẩn
    # cho MỌI bề mặt "rối loạn lipid máu"/"tăng lipid máu" — y GT[233]/GT[169]/GT[193]/
    # GT[218]/GT[26]. E78.9 "Rối loạn chuyển hóa lipoprotein, không xác định" rộng hơn
    # một bậc, để dành cho bề mặt nói "rối loạn chuyển hóa lipoprotein".
    ("HA", 0, LAB, [], []),
]

GT[93] = [  # 861c ×1  93.txt — QA "tăng HA khi có người đo" (người hỏi tự kể)
    ("HA", 0, LAB, [], []),  # "đo HA là 160/70 mmHg"
    ("160/70 mmHg", 0, VAL, [], []),
    ("HA", 1, LAB, [], []),
    ("170/60 mmHg", 0, VAL, [], []),
    ("HA", 2, LAB, [], []),
    ("150/60 mmHg", 0, VAL, [], []),
    ("hồi hợp", 0, SYM, [], []),  # lỗi chính tả của người hỏi, giữ nguyên bề mặt
    ("cảm giác rợn người", 0, SYM, [], []),
    ("HA", 3, LAB, [], []),  # "máy đo HA điện tử"
    ("HA", 4, LAB, [], []),
    ("HA", 5, LAB, [], []),
    ("nhịp tim đều tăng", 0, SYM, [], []),
    ("cảm giác rợn người", 1, SYM, [], []),
    ("hồi hộp", 0, SYM, [], []),
    ("cảm nhận được tim đập rất mạnh", 0, SYM, [], []),
    ("tăng HA", 0, DX, [], ["I10"]),  # bao trọn "HA"[6] -> không gán riêng
    ("huyết áp", 0, LAB, [], []),
]
SHARE[95] = (93, 836)  # 95 = 836 ký tự đầu của 93, đuôi rỗng

GT[76] = [  # 1099c ×1  65.txt — bài giảng điều trị rụng tóc thể mảng + 1 câu ECG ghép vào
    # 5 dãy sao là 5 tên thuốc bị mask, độ dài khác nhau -> gán riêng theo bề mặt
    ("**************", ALL, DRUG, [], []),  # 14 sao ×2: "Liệu pháp ..." / "Tiêm ..."
    ("rụng tóc từng vùng", 0, DX, [], ["L63.9"]),
    ("Corticosteroid", 0, DRUG, [], []),
    ("***************************", 0, DRUG, [], []),  # 27 sao
    ("************************************", 0, DRUG, [], []),  # 36 sao
    ("corticoid", 0, DRUG, [], []),
    ("rụng tóc toàn bộ", 0, DX, [], ["L63.1"]),
    ("rụng tóc toàn thể", 0, DX, [], ["L63.0"]),
    ("********************", 0, DRUG, [], []),  # 20 sao, "2,5g ...e có bao phim"
    # --- 1 câu ECG của một EHR khác bị ghép vào giữa bài ---
    ("Nghiệm pháp gắng sức", 0, LAB, [], []),
    ("thiếu máu cơ tim cục bộ", 0, DX, [], ["I25.9"]),
    ("ST chênh xuống", 0, VAL, [], []),  # kết quả của nghiệm pháp gắng sức
    # --- trở lại bài rụng tóc ---
    ("diphenylcyclopropenone", 0, DRUG, [], []),  # RxNorm không có
    ("dinitrochlorobenzene", 0, DRUG, [], []),
    ("rụng tóc", 3, SYM, [], []),  # "quét lên vùng rụng tóc" — [0..2] trong nhãn dài
    ("viêm da tiếp xúc dị ứng", 0, DX, [], ["L23.9"]),
    ("rụng tóc", 4, SYM, [], []),
    ("viêm da tiếp xúc", 1, DX, [], ["L25.9"]),  # [0] nằm trong nhãn "dị ứng" ở trên
    ("mày đay", 0, DX, [], ["L50.9"]),
    ("bất thường sắc tố", 0, DX, [], ["L81.9"]),
    ("bạch biến", 0, DX, [], ["L80"]),
]
SHARE[122] = (76, 647)  # 122 = 647 ký tự đầu của 76, đuôi rỗng

# ------------------------------------------------------------------
# 4 block còn lại của file 49.txt (block 0/18/122/246 đã xong) -> gán TRỌN file.
# 49.txt = QA rụng tóc từng mảng (block 246 câu hỏi + block 122/180/18 bài giảng điều
# trị, cùng nguồn với 65.txt) bị CHÈN một bệnh án ung thư vú di căn vào giữa:
# block 318 (dòng chẩn đoán) -> 324 (mục 2) -> 219 (mục 3) rồi trở lại bài giảng.
# PHÁT HIỆN: block 180 là ĐOẠN THÂN của cùng câu đã gán trong GT[76] (65.txt) — ở
# 65.txt cả bài dồn vào 1 block 1099c, ở 49.txt bị cắt thành 122 + 180 + 18. Quan hệ
# tiền tố với 76 = 0 (block 180 mở đầu bằng dòng tiêu đề "2. Liệu phát miễn dịch
# tiếp xúc" mà block 76 không có) -> SHARE không dùng được, gán tay nhưng DÙNG LẠI
# Y NGUYÊN nhãn tương ứng của GT[76] để hai bản không lệch nhau.
# Lưu ý: block 237 (89.txt) chung 62 ký tự tiền tố với 180 (cùng dòng tiêu đề đó)
# nhưng đuôi là một câu ECG hoàn toàn khác -> không liên quan, gán riêng sau.
# ------------------------------------------------------------------

GT[180] = [  # 384c ×1  49.txt — thân mục "2. Liệu phát miễn dịch tiếp xúc" (= đoạn cuối GT[76])
    # Bài giảng phương pháp điều trị, không có bệnh nhân cụ thể -> KHÔNG assertion
    # (tiền lệ GT[76] cùng nguồn, GT[18] cùng file).
    # "Liệu phát miễn dịch tiếp xúc (contac immunotherapy)": tiêu đề mục. KHÔNG gán:
    # đây là tên PHƯƠNG PHÁP (miễn dịch trị liệu), thuốc thật là 2 chất gây mẫn cảm
    # kể ngay sau -> gán 2 chất đó thay vì gán tiêu đề. Khác GT[18] "PUVA" (PUVA là
    # psoralen + UVA, tức chính tên thuốc) và khác GT[76]:3544 nơi "Liệu pháp
    # **************" có tên thuốc bị mask nằm ngay trong tiêu đề. Bản dịch còn sai
    # chính tả "Liệu phát"/"contac" -> càng không phải tên khái niệm chuẩn.
    ("diphenylcyclopropenone", 0, DRUG, [], []),  # y như GT[76]:3558, RxNorm không có
    # "(diphencyprone)": tên gọi khác trong ngoặc ngay sau -> không gán riêng
    # (tiền lệ GT[299]:1600 "(Coronary Artery Disease – CAD)", GT[207]).
    ("dinitrochlorobenzene", 0, DRUG, [], []),  # y như GT[76]:3559
    ("rụng tóc", 0, SYM, [], []),  # "quét lên vùng rụng tóc" — ở GT[76] là lần [3]
    ("viêm da tiếp xúc dị ứng", 0, DX, [], ["L23.9"]),  # y như GT[76]:3561
    ("rụng tóc", 1, SYM, [], []),  # "trên vùng rụng tóc" — ở GT[76] là lần [4]
    # "01 lần/tuần", "trong 06 tháng": tần suất/thời gian -> không gán (GT[151]).
    # "Các tác dụng phụ bao gồm": tiêu đề nhóm -> không gán. Các tác dụng phụ vẫn gán
    # (đúng như GT[76]) vì đề chỉ hỏi khái niệm bệnh có mặt trong văn bản.
    ("viêm da tiếp xúc", 1, DX, [], ["L25.9"]),  # lần [0] nằm trong nhãn "dị ứng" ở trên
    ("mày đay", 0, DX, [], ["L50.9"]),  # y như GT[76]:3564
    ("bất thường sắc tố", 0, DX, [], ["L81.9"]),  # y như GT[76]:3565
    ("bạch biến", 0, DX, [], ["L80"]),  # y như GT[76]:3566
]

# --- 3 block của mẩu bệnh án ung thư vú di căn bị ghép vào giữa bài giảng ---
# Cả 3 block đều là bệnh án lần nhập viện HIỆN TẠI (dòng chẩn đoán -> mục 2 -> mục 3)
# -> KHÔNG assertion (tiền lệ GT[22]/GT[142]/GT[152]).

GT[318] = [  # 52c ×1  49.txt — dòng chẩn đoán của EHR ghép vào
    ("Ung thư vú di căn", 0, DX, [], ["C50.9"]),  # `names` KHÔNG có "ung thư vú"
    # (đã tra) -> quét `entries`: C50.9 "U ác tính ở vú, không xác định" là mã duy
    # nhất không đòi vị trí 1/4 cụ thể. GIỮ chữ "di căn" trong bề mặt (nó nằm liền
    # trong tên chẩn đoán, không phải hậu tố đo lường như "không thể cắt bỏ" ở
    # GT[208] hay "mức độ" ở GT[280]) nhưng mã vẫn là mã u NGUYÊN PHÁT: C79.9
    # ("U ác tính thứ phát, vị trí không xác định") là mã cho ổ di căn, còn bề mặt
    # này nêu bệnh gốc là ung thư vú -> chọn C50.9. Chỉ 1 mã, không thêm C79.9
    # (ghép khái niệm chấm bằng Jaccard trên tập mã, thêm mã sai làm giảm điểm).
    # SỬA (rà lại quyết định rủi ro): trước cắt cả "trái tái phát", giờ GIỮ LẠI "trái".
    # Đếm trong GT: 112 nhãn có chữ vị trí trong bề mặt ("căng cứng vai trái" ×8, "xuất
    # huyết dưới nhện vùng trán phải" ×4, "tụ máu ngoài màng cứng phải cấp tính" ×2...).
    # Tức quy ước thực tế của tôi là GIỮ vị trí — chỗ này cắt là ngoại lệ tự tạo. "Vị trí"
    # bị cắt theo GT[280] là loại "vị trí – mức độ" mô tả thêm, không phải bên trái/phải
    # của cơ quan. Còn "tái phát" thì VẪN CẮT, giữ lý lẽ cũ: câu là "Ung thư vú di căn,
    # tràn dịch màng phổi trái tái phát" — 2 chẩn đoán nối bằng dấu phẩy, "tái phát" bổ
    # nghĩa cả cụm nên không thuộc riêng bề mặt nào. Mã J90 không đổi (J90 không phân biệt
    # bên), theo tiền lệ GT[58]/GT[99]/GT[94]/GT[45]/GT[165].
    ("tràn dịch màng phổi trái", 0, DX, [], ["J90"]),
]

GT[324] = [  # 44c ×1  49.txt — mục "2. Bệnh sử hiện tại" (chỉ có lý do vào viện)
    # "2. Bệnh sử hiện tại", "Lý do vào việni" (lỗi dịch dính chữ "i"): tiêu đề mục
    # -> không gán (GT[142]:1941).
    ("khó thở", 0, SYM, [], []),  # tiền lệ GT[91]:3074 "lý do vào viện: khó thở"
]

GT[219] = [  # 254c ×1  49.txt — mục "3. Khám tại bệnh viện" của EHR ung thư vú
    # Tiêu đề mục + các tiêu đề nhóm ("Lâm sàng", "Kết quả chẩn đoán hình ảnh",
    # "Các thủ thuật đã thực hiện") -> không gán (GT[142]:1941/GT[186]:1113).
    ("tràn dịch màng ngoài tim", 0, DX, [], ["I31.3"]),  # I31.3 "Tràn dịch màng ngoài
    # tim (không do viêm)" — khớp chính xác qua `names` (đã tra). Cắt hậu tố "mức độ
    # trung bình": mức độ là thuộc tính, không phải tên bệnh (GT[280] cắt "mức độ").
    ("ung thư di căn theo đường bạch huyết ở hai phổi", 0, DX, [], ["C78.0"]),
    # C78.0 "U ác tính thứ phát ở phổi" — đây là kết quả CĐHA mô tả ổ DI CĂN (khác
    # block 318 nêu bệnh gốc ở vú) nên dùng mã thứ phát. Đã cân nhắc C77.1 ("thứ phát
    # ở hạch trong khoang ngực") vì bề mặt nói "theo đường bạch huyết", nhưng vị trí
    # tổn thương là HAI PHỔI, không phải hạch -> C78.0. Giữ TRỌN cụm làm bề mặt:
    # "theo đường bạch huyết ở hai phổi" là kiểu lan + vị trí gắn liền trong tên phát
    # hiện CĐHA, tiền lệ GT[94]:2985 "xẹp phổi thùy dưới phải do chèn ép" giữ cả
    # nguyên nhân, GT[141]:1927 "nhiễm trùng chi dưới bên phải do Enterococcus...".
    # "dẫn lưu dịch màng tim": thủ thuật -> không gán (GT[117]/GT[208]/GT[201]).
    # "Mình xin tư vấn một số phương pháp điều trị dưới đây": câu dẫn của bài giảng
    # rụng tóc (chỗ nối trở lại nguồn kia) -> không gán.
]

GT[118] = [  # 653c ×1  16.txt — QA "Bệnh dại có lây không?" (kiến thức chung, không BN)
    ("bệnh dại", 0, DX, [], ["A82.9"]),
    ("bệnh dại", 1, DX, [], ["A82.9"]),
    ("bệnh dại", 2, DX, [], ["A82.9"]),
    ("bệnh dại", 3, DX, [], ["A82.9"]),
    ("bệnh dại", 4, DX, [], ["A82.9"]),
    ("bệnh dại", 5, DX, [], ["A82.9"]),
    ("tử vong", 0, SYM, [], []),  # thống nhất với GT[30]
    # RxNorm không có ingredient chung cho vaccine dại (chỉ có 2 IN theo chủng
    # 830457/830464) -> để candidates rỗng.
    ("*****************", 0, DRUG, [], []),  # 17 sao = vaccine phòng dại bị mask
]

# block 120 = bản dịch khác của cùng bài, chỉ chung 235 ký tự đầu với 118 (sau đó
# lệch vì "điên dại ở" vs "điên dạiở") -> gán tay hết, không SHARE được.
GT[120] = [  # 649c ×1  13.txt
    ("bệnh dại", 0, DX, [], ["A82.9"]),
    ("bệnh dại", 1, DX, [], ["A82.9"]),
    ("bệnh dại", 2, DX, [], ["A82.9"]),
    ("bệnh dại", 3, DX, [], ["A82.9"]),  # "Bệnh dạithường" dính chữ -> lấy đúng phần tên
    ("bệnh dại", 4, DX, [], ["A82.9"]),
    ("bệnh dại", 5, DX, [], ["A82.9"]),
    ("tử vong", 0, SYM, [], []),
    ("vaccine phòng dại", 0, DRUG, [], []),  # bản không bị mask của nhãn 17 sao ở 118
]

# block 131 chỉ chung 236 ký tự đầu với 118 rồi bị CẮT NGANG, ghép vào một mẩu
# EHR khác hẳn (khám bụng + sinh hiệu + thuốc). Thừa hưởng 2 nhãn "bệnh dại" đầu.
SHARE[131] = (118, 236)
GT[131] = [  # 582c ×1  20.txt — đuôi 346c: mẩu EHR đau bụng/nôn
    ("Da niêm mạc hồngi", 0, SYM, [], []),  # lỗi dịch dính chữ "hồng" + "i"
    ("Đau bụng hạ sườn phải", 0, SYM, [], []),
    ("Buồn nôn", 0, SYM, [], []),
    ("nôn ra thức ăn và dịch dạ dày, không có máu", 0, SYM, [], []),
    ("Huyết áp", 0, LAB, [], []),
    ("130/76 mmHg", 0, VAL, [], []),
    ("Mạch", 0, LAB, [], []),
    ("93 l/p", 0, VAL, [], []),
    ("Nhiệt độ", 0, LAB, [], []),
    ("36.3 độ C", 0, VAL, [], []),
    ("Nhịp thở", 0, LAB, [], []),
    ("14 l/p", 0, VAL, [], []),
    ("SPO2", 0, LAB, [], []),
    ("99 %", 0, VAL, [], []),
    ("compazine", 0, DRUG, [], ["203546"]),
    ("alevenhưng", 0, DRUG, [], ["215101"]),  # "aleve" dính "nhưng" -> giữ nguyên bề mặt
    ("đau", 1, SYM, [], []),  # "vẫn còn đau"
    ("morphineoral", 0, DRUG, [], ["7052"]),  # "morphine oral" dính chữ
    ("lorazepam", 0, DRUG, [], ["6470"]),
    ("đau", 2, SYM, [], []),  # "đỡ đau"
]

GT[113] = [  # 682c ×1  60.txt — QA mụn trứng cá, người hỏi tự kể về mình -> không FAM
    ("mụn trứng cá", 0, DX, [], ["L70.9"]),
    ("da rất nhiều dầu", 0, SYM, [], []),
    # các lần "mụn" đứng riêng: [0][4][5] nằm trong nhãn dài hơn nên bỏ
    ("mụn", 1, SYM, [], []),  # "dường như không còn mụn"
    ("mụn", 2, SYM, [], []),
    ("mụn", 3, SYM, [], []),  # "mụn ở trán, má, 2 bên quai hàm và cằm"
    ("mụn cám", 0, SYM, [], []),
    ("mụn đầu trắng", 0, SYM, [], []),
    ("mụn", 6, SYM, [], []),
    ("mụn", 7, SYM, [], []),
    ("mụn", 8, SYM, [], []),
    ("Trứng cá", 1, DX, [], ["L70.9"]),  # "Trứng cá bắt nguồn từ bốn yếu tố chính"
]
SHARE[123] = (113, 640)  # đuôi rỗng, cắt ngay trước dòng "Trứng cá bắt nguồn..."
SHARE[127] = (113, 615)  # đuôi rỗng, cắt trước cả "Câu trả lời của bác sĩ:"

# ------------------------------------------------------------------
# 3 block còn lại của file 60.txt (block 0/2/113/123/127 đã xong) -> gán TRỌN file.
# 60.txt = QA mụn trứng cá (block 113 + block 2 lời khuyên cuối) bị CHÈN nguyên một
# bệnh án tim/thận vào giữa, ngay sau dòng "Trứng cá bắt nguồn từ bốn yếu tố chính:".
# Bệnh nhân EHR: thay van hai lá cơ học + ghép thận thất bại (chạy thận), dùng
# coumadin, vào viện vì INR dưới ngưỡng điều trị (1.7) và chảy máu mũi.
# Quy ước chốt cho 3 block này:
#  - Block 273 nằm dưới mục tiền sử + "Thuốc trước khi nhập viện" -> isHistorical
#    (tiền lệ GT[187] cùng dạng mục, GT[100] "Tiền sử bệnh: Bản thân").
#  - Block 151 = mục "2. Bệnh sử hiện tại" (HPI) -> KHÔNG isHistorical
#    (tiền lệ GT[225]/GT[129]/GT[161]).
#  - Block 250 = mục "3. Khám tại bệnh viện" -> lần này -> KHÔNG assertion
#    (tiền lệ GT[143]/GT[152]); dùng đúng khuôn sinh hiệu của GT[131].
# ------------------------------------------------------------------

GT[273] = [  # 113c ×1  60.txt — tiền sử phẫu thuật + thuốc trước nhập viện
    # "Phẫu thuật thay ...": thủ thuật -> chỉ lấy phần TÌNH TRẠNG còn lại là
    # "van hai lá cơ học" (tiền lệ GT[100]:2918 "Van động mạch chủ cơ học" -> DX
    # + HIST + Z95.2, cùng dạng "van tim nhân tạo cơ học"; và tiền lệ GT[187]/
    # GT[13] bỏ phần "phẫu thuật cắt bỏ ...").
    ("van hai lá cơ học", 0, DX, [HIST], ["Z95.2"]),  # Z95.2 "Sự có mặt của van tim
    # nhân tạo cơ học" — dùng lại đúng mã GT[100]:2918. Đã loại Z95.4 ("van tim thay
    # thế khác") vì bề mặt nói rõ CƠ HỌC. Không dùng I34.x (hở/hẹp van hai lá, tiền lệ
    # GT[91] "HoHL" -> I34.0) vì đây là van đã THAY, không phải bệnh van còn lại.
    ("ghép thận thất bại", 0, DX, [HIST], ["T86.1"]),  # T86.1 "Thất bại và/hoặc thải
    # ghép thận" — khớp gần như nguyên văn bề mặt (đã tra `entries`, chỉ có T86.1 và
    # Z94.0 "Tình trạng ghép thận"; chọn T86.1 vì bề mặt nhấn THẤT BẠI). `names` không
    # có mục tên "ghép thận thất bại" nên tra bằng cách quét `entries`.
    ("coumadin", 0, DRUG, [HIST], ["11289"]),  # dùng lại y nguyên GT[187]:2281:
    # Coumadin KHÔNG có trong RXNCONSO.RRF -> mã hoạt chất warfarin IN 11289.
    # "3.0 mg /ngày": liều + đường dùng -> không gán (tiền lệ GT[297]/GT[316]/GT[161]).
]

GT[151] = [  # 470c ×1  60.txt — mục "2. Bệnh sử hiện tại" (HPI -> không HIST)
    # "Lý do vào viện" và "Khám hiện tại": tiêu đề mục -> không gán (GT[142]:1941).
    ("INR", 0, LAB, [], []),  # "Lý do vào viện:, INR dưới ngưỡng điều trị"
    # KHÔNG gán cụm "INR dưới ngưỡng điều trị" / "chỉ số đông máu dưới ngưỡng điều
    # trị" làm CHẨN_ĐOÁN: "dưới ngưỡng điều trị" là NHẬN ĐỊNH bằng chữ về trị số, mà
    # tiền lệ chỉ gán KẾT_QUẢ_XÉT_NGHIỆM cho GIÁ TRỊ SỐ (+đơn vị) — GT[25]:4447 và
    # GT[163]:3449 bỏ "chưa phát hiện bất thường trên phim chụp" đúng vì lẽ đó.
    # Cũng KHÔNG gán "chỉ số đông máu" riêng làm LAB thứ hai: đây là cách gọi chung
    # của chính chỉ số INR trong cùng câu ("chỉ số đông máu ... ( kết quả là INR 1.7)")
    # -> chỉ giữ tên chỉ số thật (tiền lệ GT[136] bỏ tiêu đề nhóm panel xét nghiệm).
    ("chảy máu mũi", 0, SYM, [], []),  # "xuất hiện chảy máu mũi" — SYM theo GT[111]:2747
    # (cùng bề mặt) và GT[171]:2763 ("chảy máu cam"). "khoảng 01 lần/ tuần": tần suất
    # -> không gán (tiền lệ GT[226]:1290 cắt mốc thời gian, GT[240]:1658 "Thời gian").
    ("xét nghiệm", 0, LAB, [], []),  # "Khi làm xét nghiệm tại khoa chạy thận" — tên
    # phép đo nêu chung nhưng CÓ thực hiện và có kết quả ngay sau -> gán, theo tiền lệ
    # GT[103]:3487 "xét nghiệm bất thường" và GT[25]:4442/GT[136] "xét nghiệm máu".
    # Khác "các xét nghiệm này"/"một xét nghiệm nào" (GT[289]/GT[1]) là nêu giả định
    # nên không gán. "khoa chạy thận": tên khoa/nơi làm -> không gán (tiền lệ bỏ
    # chuyên khoa). Không gán "chạy thận" làm thủ thuật -> thủ thuật không gán.
    ("INR", 1, LAB, [], []),  # "( kết quả là INR 1.7)" — tiền lệ GT[100]:2914 cùng cặp
    ("1.7", 0, VAL, [], []),  # INR không đơn vị, tiền lệ GT[100]:2915 ("15" cho INR 15)
    # "không có biểu hiện bất thường khác": phủ định của BẤT THƯỜNG = kết quả bình
    # thường -> không gán (chốt ở GT[289]:1064 và GT[186]:1110, nhắc lại ở GT[25]:4448).
    # --- "Khám hiện tại" -> các phát hiện ÂM TÍNH -> SYM + isNegated ---
    ("chảy máu mũi", 1, SYM, [NEG], []),  # "Không chảy máu mũi"
    ("đau ngực", 0, SYM, [NEG], []),  # tiền lệ GT[129]:2335/GT[27]:4359/GT[78]:3228
    ("khó thở", 0, SYM, [NEG], []),  # tiền lệ GT[129]:2336/GT[27]:4360/GT[162]:1500
    ("đau bụng", 0, SYM, [NEG], []),
    ("buồn nôn", 0, SYM, [NEG], []),  # "Không có buồn nôn"
    ("nôn", 1, SYM, [NEG], []),  # "không nôn" — lần [0] nằm trong "buồn nôn" nên lấy
    # index 1. Tách thành 2 bề mặt vì bản dịch viết rời "buồn nôn, không nôn", mỗi
    # cụm có từ phủ định riêng (khác GT[131]:3603 nơi "nôn ra thức ăn..." là 1 cụm).
    # "Các cơ quan khác chưa phát hiện bất thường": kết quả BÌNH THƯỜNG -> không gán.
]

GT[250] = [  # 154c ×1  60.txt — mục "3. Khám tại bệnh viện" (sinh hiệu)
    # Tiêu đề mục + "Kết quả khám thực thể": tiêu đề -> không gán (GT[142]:1941).
    # Khuôn giống hệt GT[131]:3604-3613 (cùng kiểu đơn vị "l/p" và "độ C").
    ("dấu hiệu sinh tồn", 0, LAB, [], []),  # tiền lệ GT[94]:2967
    ("Nhiệt độ", 0, LAB, [], []),
    ("36.5 độ C", 0, VAL, [], []),
    ("Mạch", 0, LAB, [], []),
    ("88 l/p", 0, VAL, [], []),
    ("Huyết áp", 0, LAB, [], []),
    ("120/70 mmHg", 0, VAL, [], []),
    ("Nhịp thở", 0, LAB, [], []),
    ("20 l/p", 0, VAL, [], []),
    ("SPO2", 0, LAB, [], []),
    ("92 %", 0, VAL, [], []),
]

# ------------------------------------------
# 2 block còn lại của cặp file 51.txt + 70.txt -> gán TRỌN CẢ HAI FILE một lượt.
# 51.txt và 70.txt là HAI BẢN của cùng MỘT EHR (BN suy tim mất bù, khó thở, phù chi
# dưới), chia sẻ y nguyên block 21 (mục "1. Tiền sử bệnh") ở đầu:
#   70.txt = 21 (tiền sử) -> 74 (mục 2, đã gán) -> 199 (mục 3 + 4 dòng y lệnh)
#   51.txt = 21 (tiền sử) -> 83 (mục 2 cắt ngắn, SHARE 1028c của 74) -> 128 (đã gán)
# Chỗ khác nhau: 70.txt chèn 3 dòng bài giảng BỆNH DẠI vào đầu mục 3; 51.txt chèn
# câu trả lời của bác sĩ về dây chằng chéo. 4 dòng y lệnh cuối (aspirin /
# albuterolipratropium / methylprednisolone / lợi tiểu) GIỐNG HỆT ở cả hai file:
# ở 51.txt đã gán trong GT[128] -> DÙNG LẠI Y NGUYÊN mã cho block 199.
# Quy ước chốt:
#  - Block 21 nằm dưới "1. Tiền sử bệnh" + "Các bệnh lý mãn tính" -> isHistorical
#    toàn block (tiền lệ GT[14]/GT[20]/GT[87]/GT[98]).
#  - Block 199 dưới "3. Đánh giá tại bệnh viện" -> KHÔNG assertion (tiền lệ
#    GT[143]/GT[98]); mẩu bài giảng dại cũng không có BN cụ thể -> không assertion.
# ------------------------------------------

GT[21] = [  # 207c ×2  51.txt, 70.txt — mục "1. Tiền sử bệnh" / "Các bệnh lý mãn tính"
    # "1.  Tiền sử bệnh", "Các bệnh lý mãn tính": tiêu đề mục -> không gán (GT[142]).
    ("béo phì", 0, DX, [HIST], ["E66.9"]),  # y như GT[20]/GT[4]/GT[51] cùng mã
    ("đái tháo đường", 0, DX, [HIST], ["E14"]),  # KHÔNG rõ typ -> E14 (tiền lệ
    # GT[14]/GT[20]/GT[104]); "được kiểm soát bằng chế độ ăn" là CÁCH ĐIỀU TRỊ, cắt
    # khỏi bề mặt (quy ước cắt hậu tố mức độ/điều trị, tiền lệ GT[219]). Không NEG:
    # bệnh vẫn đang có, chỉ là kiểm soát được (khác "đã dừng thuốc").
    ("ngừng thở khi ngủ", 0, DX, [HIST], ["G47.3"]),  # G47.3 "Ngưng thở khi ngủ";
    # corpus viết "ngừng" còn bảng ICD viết "ngưng" -> giữ bề mặt literal của corpus
    # (WER chấm literal), mã vẫn G47.3 y như GT[20]/GT[9] "ngưng thở khi ngủ do
    # tắc nghẽn". Không dùng P28.3 (mã của TRẺ SƠ SINH).
    ("suy tim, không đặc hiệu", 0, DX, [HIST], ["I50.9"]),  # I50.9 "Suy tim, không
    # xác định" — y như GT[124]/GT[197]/GT[91]/GT[98]. Bề mặt GIỮ ", không đặc hiệu"
    # vì đó là phần định danh đúng mã .9 (cùng kiểu GT[87] "tăng lipid máu, không
    # đặc hiệu" -> E78.5, GT[168] "bệnh thận mạn, không đặc hiệu Giai đoạn 4").
    # "tiền sử lâm sàng" đứng trước: nhãn mục -> không lấy vào bề mặt.
    # "Dị ứng:" -> tiêu đề mục, không gán.
    ("Dị ứng furosemide", 0, DX, [HIST], ["Z88.8"]),  # dị ứng thuốc là một TRẠNG
    # THÁI BỆNH LÝ có mã ICD riêng -> CHẨN_ĐOÁN. Z88.8 "Tiền sử cá nhân dị ứng với
    # dược chất, thuốc điều trị và/hoặc sinh phẩm khác": furosemide là thuốc lợi
    # tiểu, không thuộc Z88.0–Z88.7 (penicillin/kháng sinh/gây mê/ma tuý/giảm đau/
    # huyết thanh) -> đúng con "khác". Không dùng T78.4 ("Dị ứng, không xác định")
    # như GT[7]/GT[113] "dị ứng do thời tiết": ở đó tác nhân KHÔNG phải thuốc nên
    # không có mã Z88 nào dùng được; ở đây tác nhân là thuốc và Z88.8 khớp chính xác
    # hơn. Bề mặt lấy trọn "Dị ứng furosemide" (lần [1] của "Dị ứng", sau dấu ":")
    # chứ không tách "furosemide" thành nhãn THUỐC riêng: đây KHÔNG phải thuốc bệnh
    # nhân đang dùng mà là tác nhân gây dị ứng, nằm liền trong tên chẩn đoán
    # (tiền lệ GT[94] "xẹp phổi thùy dưới phải do chèn ép" giữ cả nguyên nhân).
]

GT[199] = [  # 313c ×1  70.txt — mục "3. Đánh giá tại bệnh viện" + 3 dòng bài giảng dại
    # "3.  Đánh giá tại bệnh viện": tiêu đề mục -> không gán.
    # --- 3 dòng bài giảng bệnh dại ghép vào (cùng nguồn GT[66], không có BN) ---
    ("bệnh dại", 0, DX, [], ["A82.9"]),  # y như GT[66]/GT[11]/GT[108] cùng mã.
    # Ở GT[66] đây là lần [3] ("lây nhiễm bệnh dại bao gồm"); trong block 199 chỉ
    # có 1 lần -> index 0 (chỉ số đếm TRONG block, không cộng dồn).
    # "Loại hình tiếp xúc và loại động vật cắn", "Mức độ nghiêm trọng của vết cắn":
    # yếu tố nguy cơ/đường vào của bài giảng, không phải triệu chứng của BN nào
    # -> không gán, y như GT[66]/GT[11]/GT[139] đã bỏ "vết cắn"/"vết thương".
    # --- 4 dòng y lệnh: GIỐNG HỆT GT[128] (51.txt), dùng lại y nguyên ---
    ("aspirin", 0, DRUG, [], ["1191"]),  # bỏ hàm lượng "325mg" khỏi bề mặt
    # (quy ước liều thuốc chốt ở đợt 12).
    ("albuterolipratropium", 0, DRUG, [], []),  # lỗi dịch dính 2 tên thuốc, không
    # có concept RxNorm -> candidates rỗng, y như GT[128].
    # "nebulizer": dạng bào chế/đường dùng -> không gán (GT[297]/GT[316]).
    ("methylprednisolone", 0, DRUG, [], ["6902"]),  # RxNorm IN = 6902, y như GT[128].
    # "125mg iv": hàm lượng + đường dùng -> không gán.
    ("lợi tiểu", 0, DRUG, [], []),  # nhóm thuốc, không tên cụ thể -> candidates
    # rỗng (tiền lệ GT[52]/GT[128]/GT[99] "liệu pháp lợi tiểu"). "600cc": thể tích
    # -> không gán.
]

GT[74] = [  # 1121c ×1  70.txt — EHR khó thở/phù chi dưới (suy tim mất bù)
    # SỬA (chống span lồng nhau): trước dùng ALL -> 4 lần, nhưng lần [3] nằm BÊN TRONG
    # bề mặt dài "khó nằm vào ban đêm để ngủ vì khó thở" ở dưới. Span lồng nhau vừa trái
    # quy ước, vừa KHÔNG biểu diễn được bằng BIO token-classification (1 token 1 nhãn)
    # -> liệt kê index rõ, bỏ lần [3].
    ("khó thở", 0, SYM, [], []),
    ("khó thở", 1, SYM, [], []),
    ("khó thở", 2, SYM, [], []),
    ("căng cứng vai trái", ALL, SYM, [], []),
    ("ho có đờm trắng", ALL, SYM, [], []),
    ("chủ quan sốt", ALL, SYM, [], []),
    ("phù chi dưới", ALL, SYM, [], []),
    # bản dịch thiếu chữ ở lần đầu ("vì thở"), lần sau đủ ("vì khó thở") -> hai
    # bề mặt khác nhau, gán riêng từng cái theo đúng chữ trong văn bản.
    ("khó nằm vào ban đêm để ngủ vì thở", 0, SYM, [], []),
    ("khó nằm vào ban đêm để ngủ vì khó thở", 0, SYM, [], []),
    ("thiếu oxy", ALL, SYM, [], []),
    ("độ bão hòa oxy", ALL, LAB, [], []),
    ("86", ALL, VAL, [], []),  # đề không có đơn vị trong văn bản
    # "gọi EMS", "thở oxy qua mask không hồi phục (NRB)", "đưa đến khoa Cấp cứu":
    # thủ thuật/sự kiện, không phải thuốc -> không gán (như "Xông khí dung").
    # "bỏ lỡ 3 ngày dùng một số thuốc": không có tên thuốc -> không gán.
]
# block 83 = 1028 ký tự đầu của 74, không có đuôi riêng. Nhưng nó cắt TRƯỚC dòng
# "Tình trạng ngay trước khi nhập viện" nên 3 nhãn ALL của block 74 chỉ còn 1 lần
# xuất hiện ở đây -> expand_share từ chối (số lần không khớp), phải khai lại.
SHARE[83] = (74, 1028)
GT[83] = [  # 1028c ×1  51.txt
    ("thiếu oxy", ALL, SYM, [], []),
    ("độ bão hòa oxy", ALL, LAB, [], []),
    ("86", ALL, VAL, [], []),
]

GT[49] = [  # 1579c ×1  22.txt — EHR đau bụng/ngộ độc acetaminophen + câu hỏi mày đay (bản dịch lỗi)
    ("đau bụng ngày càng nặng", ALL, SYM, [], []),
    ("đau bụng liên tục", ALL, SYM, [], []),
    ("đau bụng", 4, SYM, [], []),  # "2 ngày trước khi nhập viện, đau bụng trở nên tồi tệ hơn"
    ("tăng men gan", 0, SYM, [], []),
    ("tổng bilirubin", 0, LAB, [], []),
    ("6.7", 0, VAL, [], []),
    ("mệt mỏi toàn thân", 0, SYM, [], []),
    ("yếu sức", 0, SYM, [], []),
    ("khó thở khi gắng sức", 0, SYM, [], []),
    ("ngứa toàn thân", 0, SYM, [], []),
    ("tiểu ra máu không đau", 0, SYM, [], []),
    ("Đau vùng gan phải (RUQ) và thượng vị lan ra sau lưng", 0, SYM, [], []),
    ("buồn nôn", 0, SYM, [NEG], []),
    ("nôn", 1, SYM, [NEG], []),
    ("thay đổi thói quen đại tiện", 0, SYM, [NEG], []),
    ("phân có máu, đen hoặc nhựa đường", 0, SYM, [NEG], []),
    ("acetaminophen", 0, DRUG, [], ["161"]),
    ("thuốc an thần", 0, DRUG, [HIST], []),  # "uống 2 chai thuốc an thần trong quá khứ"
    # --- sang câu hỏi của người dùng: nói về BẠN của người hỏi, không phải BN ---
    # Đề chỉ có isFamily cho "người khác" -> dùng FAM (tiền lệ block 26/45/47).
    ("thuốc giảm đau", 0, DRUG, [FAM], []),
    ("dị ứng thời tiết", 0, DX, [FAM, NEG], ["T78.4"]),
]

GT[48] = [  # 1582c ×1  76.txt — đuôi EHR cắt chi (lắp chân giả) + QA mày đay bản dịch lỗi nặng nhất
    # "lắp chân giả" là thủ thuật/dụng cụ, không thuộc 5 loại -> không gán.
    ("MÀY đay VÔ CĂN", 0, DX, [], ["L50.1"]),
    ("MÀY đay MẠN", 0, DX, [], ["L50.8"]),
    ("mày đay vô căn", 1, DX, [], ["L50.1"]),
    ("Bạn đay vô căn", 0, DX, [], ["L50.1"]),  # lỗi dịch máy của "mày đay vô căn"
    ("***************", ALL, DRUG, [], []),  # kháng histamin H1 thế hệ 2 rồi thế hệ 1
    ("*********", 0, DRUG, [], []),  # corticoid liều thấp
]

GT[47] = [  # 1582c ×1  68.txt — EHR bệnh 3 thân ĐM vành + QA liều Augmentin cho trẻ
    ("mệt mỏi", ALL, SYM, [], []),
    ("khó thở tăng", 0, SYM, [], []),
    ("Khó thở tăng khi vận động gắng sức", 0, SYM, [], []),
    ("Đi lại khó khăn", 0, SYM, [], []),
    ("Đau hai bàn chân", 0, SYM, [], []),
    ("bệnh lý thần kinh ngoại biên", 0, DX, [], ["G62.9"]),
    ("Đo sức bền cơ tim bằng đồng vị phóng xạ", 0, LAB, [], []),
    ("dị tật cố định vùng trước vách và vách dưới", 0, DX, [], []),
    ("giảm chức năng tâm thu thất trái nghiêm trọng", 0, DX, [], ["I50.1"]),
    ("rối loạn chức năng thất trái", 0, DX, [], ["I50.1"]),
    ("Chụp động mạch vành", ALL, LAB, [], []),
    ("bệnh ba thân động mạch vành nghiêm trọng", 0, DX, [], ["I25.1"]),
    # --- sang mẩu QA liều Augmentin cho bé (con người hỏi -> FAM) ---
    ("Augmentin", ALL, DRUG, [FAM], ["151392"]),
    ("amoxicillin", 0, DRUG, [FAM], ["723"]),
    ("acid clavulanic", 0, DRUG, [FAM], ["21216"]),
    ("kháng sinh", ALL, DRUG, [FAM], []),
    ("tiêu chảy", 0, SYM, [FAM], []),
    ("giảm hấp thu dinh dưỡng", 0, SYM, [FAM], []),
    ("men tiêu hóa", 0, DRUG, [FAM], []),
]

GT[46] = [  # 1620c ×1  43.txt — EHR ảo giác (ngừng gleevec/allopurinol) + chèn QA phân sống trẻ bú sữa
    ("ảo giác", 0, SYM, [], []),
    ("ảo giác", 1, SYM, [], []),
    ("nhiễm khuẩn đường tiết niệu, vị trí không xác định", 0, DX, [HIST], ["N39.0"]),
    ("Thuốc giảm đau", 0, DRUG, [NEG], []),  # "Thuốc giảm đau đã ngừng"
    ("nhiễm khuẩn đường tiết niệu, vị trí không xác định", 1, DX, [HIST], ["N39.0"]),
    ("thuốc giảm đau", 1, DRUG, [NEG], []),
    ("gleevec", 0, DRUG, [NEG], ["282386"]),  # đã ngừng 5 ngày trước nhập viện
    ("allopurinol", 0, DRUG, [NEG], ["519"]),
    ("ảo giác", 2, SYM, [], []),
    ("ảo giác", 3, SYM, [], []),
    ("nhìn/nghe thấy có nhiều người", 0, SYM, [], []),
    ("Ảo giác", 4, SYM, [], []),
    ("hoang tưởng", 0, SYM, [], []),
    ("lo sợ", 0, SYM, [], []),
    # --- hết 901 ký tự chia sẻ với block 65; sang mẩu QA phân sống ---
    # QA về con của người hỏi -> isFamily (tiền lệ block 26/45)
    ("đi cầu phân sống", ALL, SYM, [FAM], []),
    ("không hấp thu được một số protein", 0, DX, [FAM], ["K90.4"]),
    ("men Bacillus clausii 2 tỷ bào tử/5ml/ ống", 0, DRUG, [], []),  # không có trong RxNorm
    ("Enterogermina", 0, DRUG, [], []),  # biệt dược của Bacillus clausii
    ("Biogermin", 0, DRUG, [], []),
    ("gleevec", 1, DRUG, [NEG], ["282386"]),
    ("allopurinol", 1, DRUG, [NEG], ["519"]),
    ("ảo giác", 5, SYM, [], []),
]

# block 65 = 901 ký tự đầu của block 46 (EHR ảo giác) + mục "Diễn biên trước khi
# nhập viện" liệt kê lại 4 mục điều trị mà block 46 thay bằng mẩu QA phân sống.
SHARE[65] = (46, 901)
# block 126 = 525 ký tự đầu của block 46, đuôi chỉ là câu khuyên đi khám (không
# có khái niệm) -> khai SHARE là xong, không cần gán tay.
SHARE[126] = (46, 525)
# block 160 = 416 ký tự đầu của block 45, đuôi chỉ là "Câu trả lời của bác sĩ:".
SHARE[160] = (45, 416)

GT[65] = [  # 1201c — đuôi riêng (901c đầu thừa hưởng block 46)
    ("nhiễm khuẩn đường tiết niệu, vị trí không xác định", 2, DX, [HIST], ["N39.0"]),
    ("Thuốc giảm đau", 2, DRUG, [NEG], []),
    ("gleevec", 1, DRUG, [NEG], ["282386"]),
    ("allopurinol", 1, DRUG, [NEG], ["519"]),
    ("ảo giác", 5, SYM, [], []),
]

GT[45] = [  # 1634c ×1  39.txt — EHR tụt huyết áp/mệt mỏi hậu phẫu + chèn mẩu QA bàn chân bẹt
    ("tụt huyết áp không rõ nguyên nhân", 0, DX, [], ["I95.9"]),
    ("mệt mỏi", ALL, SYM, [], []),  # 5 lần, đều là của bệnh nhân
    ("Viêm phổi bệnh viện", 0, DX, [HIST], ["J18.9"]),  # biến chứng đợt nằm viện trước
    ("rung nhĩ và nhịp nhanh trên thất", 0, DX, [HIST], ["I48.9"]),
    # SỬA (chống span lồng nhau): trước gán THÊM ("[[nhịp nhanh trên thất]]", 0, I47.1)
    # nằm bên trong cụm trên, cố ý tách 2 khái niệm từ 1 chuỗi. Bỏ, vì (a) GT[94] cùng
    # bề mặt chỉ gán MỘT nhãn cụm đầy đủ -> đó là tiền lệ, (b) BIO token-classification
    # không biểu diễn được span lồng nhau.
    ("đau bụng gián đoạn", 0, SYM, [], []),
    ("hạ huyết áp, không đặc hiệu", 0, DX, [], ["I95.9"]),
    ("khó khăn khi ra khỏi giường", 0, SYM, [], []),
    # mẩu QA bàn chân bẹt ghép vào (con của người hỏi -> FAM, giống block 26)
    ("bệnh bàn chân bẹt", 0, DX, [FAM], ["Q66.5"]),
    ("không đau", 0, SYM, [FAM, NEG], []),
    ("khó thở khi gắng sức", 0, SYM, [], []),
    ("ho mạn tính có đờm vàng loãng", 0, SYM, [], []),
    ("ran", 0, SYM, [], []),
    ("phù phù", 0, SYM, [], []),  # lỗi dịch máy lặp từ, giữ nguyên mặt chữ
    ("dịch thanh dịch lẫn máu từ vết mổ", 0, SYM, [], []),
    ("phân nâu dương tính guaiac", 0, SYM, [], []),
    ("huyết khối", 0, LAB, [], []),  # dịch máy; trị số 26.3/28 đi kèm
    ("26.3", 0, VAL, [], []),
    ("28", 0, VAL, [], []),
    ("chụp x-quang ngực", 0, LAB, [], []),
    ("xẹp phổi thùy dưới phải do chèn ép", 0, DX, [], ["J98.1"]),
    ("tràn dịch màng phổi", 0, DX, [], ["J90"]),
    # "Truyền dịch tĩnh mạch 750cc", "Xông khí dung": thủ thuật điều trị, không
    # phải tên thuốc cũng không phải tên xét nghiệm -> không gán.
    ("Viêm phổi bệnh viện", 1, DX, [], ["J18.9"]),
    ("Rung nhĩ kèm nhịp nhanh trên thất", 0, DX, [], ["I48"]),  # SỬA (rà mâu thuẫn):
    # trước dùng I48.9. Bề mặt KHÔNG nói kịch phát/dai dẳng/mạn tính nên không key ra
    # mã con nào; I48 là mã nhóm "Rung nhĩ và/hoặc cuồng nhĩ" -> khớp đúng mức chi tiết
    # của bề mặt. Y GT[94] và GT[238] ("Rung nhĩ kèm đáp ứng thất nhanh" -> I48).
    # Lưu ý phân biệt với GT[281] "rung nhĩ" trơ -> I48.9: ở đó bề mặt không có phần
    # "kèm ...", đứng một mình như một chẩn đoán không xác định.
    # SỬA (chống span lồng nhau): bỏ ("[[nhịp nhanh trên thất]]", 1, I47.1) — y lý lẽ ở
    # nhãn "rung nhĩ và nhịp nhanh trên thất" phía trên.
]

GT[44] = [  # 1642c ×1  31.txt — QA giãn thừng tinh + EHR sỏi ống mật chủ/viêm dạ dày (ERCP)
    ("Giãn thừng tinh", ALL, DX, [], ["I86.1"]),  # = giãn tĩnh mạch bìu
    ("vô sinh thứ phát", 0, DX, [], ["N46"]),
    ("đau bụng vùng hạ sườn phải", 0, SYM, [], []),
    ("chướng bụng", ALL, SYM, [], []),
    ("buồn nôn thoáng qua", ALL, SYM, [], []),
    ("Nôn mửa", 0, SYM, [], []),
    ("đau lưng âm ỉ", 0, SYM, [], []),
    ("đau bụng hạ sườn phải", 0, SYM, [], []),
    ("đau lưng", 1, SYM, [], []),  # trong mục "Vị trí"
    ("đau bụng", 2, SYM, [], []),  # trong mục "Thời gian"
    ("[[nôn]], đau lưng kéo dài", 0, SYM, [], []),  # "buồn nôn thoáng qua, nôn, ..."
    ("đau lưng kéo dài", 0, SYM, [], []),
    ("nội soi thực quản - dạ dày - tá tràng", ALL, LAB, [], []),
    ("viêm dạ dày", ALL, DX, [], ["K29.7"]),
    ("thuốc NSAIDs", 0, DRUG, [NEG], []),  # "Đã ngừng sử dụng thuốc NSAIDs"
    ("omeprazole", 0, DRUG, [], ["7646"]),
    ("cộng hưởng từ mật tụy", ALL, LAB, [], []),
    ("sỏi đoạn cuối ống mật chủ", ALL, DX, [], ["K80.5"]),
    ("Xét nghiệm chức năng gan", ALL, LAB, [], []),
    ("men gan tăng", 0, SYM, [], []),
    ("tăng men gan", 0, SYM, [], []),
    ("Nội soi mật tụy ngược dòng (ERCP)", 0, LAB, [], []),
    ("ERCP", 1, LAB, [], []),
    ("viên sỏi tại đoạn cuối ống mật chủ", 0, DX, [], ["K80.5"]),
    ("sỏi ống dẫn mật chung đoạn cuối", 0, DX, [], ["K80.5"]),
]

GT[43] = [  # 1663c ×1  14.txt — EHR suy kiệt/ảo giác + QA mày đay (bản dịch sạch nhất, vào giữa bài)
    ("Toàn trạng suy kiệt", 0, SYM, [], []),
    ("ảo giác dai dẳng", 0, SYM, [], []),
    ("ảo giác", 1, SYM, [], []),  # "ảo giác được vợ nhận thấy" — vợ chỉ là người kể
    ("Lú lẫn ngày càng nặng", ALL, SYM, [], []),
    ("Cực kỳ yếu", 0, SYM, [], []),
    # Đoạn mô bệnh học là kiến thức chung, không phải xét nghiệm bệnh nhân làm
    # -> không gán LAB (giữ nhất quán với block 32 cùng nguồn).
    ("mày đay vô căn", ALL, DX, [], ["L50.1"]),  # 2 lần, hoa/thường khác nhau
    ("****************", ALL, DRUG, [], []),  # kháng histamin H1 thế hệ 2 rồi thế hệ 1
    ("corticoid", 0, DRUG, [], []),
]

GT[42] = [  # 1678c ×1  61.txt — QA cấy que tránh thai + EHR mệt mỏi/hạ huyết áp chèn giữa
    # "cấy que" là thủ thuật, không phải thuốc; que Implanon chứa etonogestrel.
    ("Implanon", 0, DRUG, [], ["14584"]),
    ("mệt mỏi kéo dài", 0, SYM, [], []),
    ("khó khăn khi ra khỏi giường", ALL, SYM, [], []),
    ("đau bụng gián đoạn", ALL, SYM, [], []),
    ("hạ huyết áp, không đặc hiệu", 0, DX, [], ["I95.9"]),
    ("mệt mỏi", 1, SYM, [], []),
    ("mệt mỏi", 2, SYM, [], []),
    ("khó thở khi gắng sức", 0, SYM, [], []),
    ("ho mạn tính có đờm vàng loãng", 0, SYM, [], []),
    ("chán ăn trong vài tháng", 0, SYM, [], []),
    # --- quay lại phần trả lời QA ---
    ("xét nghiệm bổ sung", 0, LAB, [], []),
    ("rỉ máu âm đạo", 0, SYM, [], []),
    ("kinh nguyệt thưa", 0, SYM, [], []),
]

GT[41] = [  # 1759c ×1  37.txt — QA teo ống tai bẩm sinh, bị chèn mẩu EHR block 35 vào giữa
    ("tai phải bé không có lỗ tai", 0, DX, [], ["Q16.1"]),
    ("đo âm tai còn lại", 0, LAB, [], []),
    ("vành tai không phát triển đều", 0, DX, [], ["Q17.2"]),
    ("nó nhỏ hơn tai còn lại", 0, SYM, [], []),
    # --- chèn nguyên mẩu EHR tổn thương âm hộ (giống đuôi block 35) ---
    ("cực kỳ đau đớn", 0, SYM, [], []),
    ("ban đỏ", 0, SYM, [], []),
    ("chảy mủ", 0, SYM, [], []),
    ("bactrim", 0, DRUG, [], ["151399"]),
    ("doxycycline", 0, DRUG, [], ["3640"]),
    ("Viêm mô tế bào", 0, DX, [], ["L03.3"]),
    ("ban đỏ", 1, SYM, [], []),
    ("dịch tiết có vẻ như mủ", 0, SYM, [], []),
    # --- quay lại phần trả lời QA ---
    ("chỉ nghe một bên", 0, DX, [], ["H90.1"]),
    ("lúng túng khi xác định hướng âm thanh", 0, SYM, [], []),
]

# ------------------------------------------------
# 2 block còn lại của file 25.txt (block 40 đã xong) -> gán TRỌN file.
# 25.txt = QA "uống nhiều thuốc tránh thai khẩn cấp có sao không" (146 câu hỏi + 40
# câu trả lời) bị CHÈN một EHR nhiễm trùng vết mổ vào giữa phần trả lời, đuôi file là
# 3 dòng "khám tại bệnh viện" của EHR đó (block 294).
# Block 294 = TIỀN TỐ 77 ký tự của block 111 (78.txt) -> dùng SHARE, không gán tay.
# ------------------------------------------------

GT[146] = [  # 497c ×1  25.txt — câu hỏi QA về thuốc tránh thai khẩn cấp
    # Người hỏi TỰ kể về mình -> KHÔNG isFamily (quy ước GT[105]).
    ("**********", ALL, DRUG, [], []),  # 3 lần, tên thuốc tránh thai khẩn cấp bị mask
    # -> gán DRUG như bề mặt, candidates rỗng (tiền lệ GT[40] cùng file với mask rộng
    # 25 dấu sao, GT[43], GT[148]). Mask 10 dấu sao ở đây là bề mặt riêng — needle
    # toàn dấu sao chỉ khớp đúng dải sao dài BẰNG nó.
    # "6 vien", "4 viên trong 4 tuần", "loại 12h": liều/thời gian/dạng thuốc
    # -> không gán (GT[297]/GT[316]).
    # "bcs invisible": bao cao su, là dụng cụ tránh thai -> không gán (tiền lệ
    # GT[107]/GT[42] bỏ "que cấy tránh thai"/"Que tránh thai" vì là dụng cụ).
    # "bị sì nước", "test": mô tả sự cố dụng cụ + thử thai tại nhà -> không gán
    # (tiền lệ GT[105] bỏ "que thử 2 vạch").
    ("đau bụng", 0, SYM, [], []),  # "sau mỗi lần uống thì em có đau bụng"
    ("chảy máu", 0, SYM, [NEG], []),  # "nhưng k chảy máu" (k = không) -> isNegated,
    # tiền lệ GT[213] "đánh răng không chảy máu" + GT[183] "không sốt".
    ("trễ kinh", 0, SYM, [NEG], []),  # cùng một chữ "k" phủ định phủ lên cả 2 triệu
    # chứng "chảy máu với trễ kinh" (tiền lệ GT[186] 1 phủ định phủ 4 triệu chứng).
    # "kinh tới rất đều": mô tả BÌNH THƯỜNG -> không gán (quy ước phát hiện bình
    # thường không gán). "tác dụng phụ": nói chung, chưa nêu tên -> không gán.
]

GT[40] = [  # 1820c ×1  25.txt — QA tác hại lạm dụng thuốc tránh thai + EHR nhiễm trùng vết mổ
    ("*************************", ALL, DRUG, [], []),  # thuốc tránh thai (bị che)
    ("tắc ống dẫn trứng", 0, DX, [], ["N83.9"]),
    ("teo niêm mạc tử cung", 0, DX, [], []),
    ("không rụng trứng", 0, DX, [], ["N97.0"]),
    ("vô sinh", 0, DX, [], ["N97.9"]),
    ("ung thư cổ tử cung", 0, DX, [], ["C53.9"]),
    ("mang thai ngoài tử cung", 0, DX, [], ["O00.9"]),
    # SỬA (rà mâu thuẫn sau khi phủ 100%): 4 dòng dưới trước đây gán SYM cả loạt vì
    # chúng nằm trong danh sách "tác dụng phụ". Nhưng LOẠI của khái niệm không phụ
    # thuộc vào việc nó là tác dụng phụ hay bệnh chính — 3 trong 4 là TÊN BỆNH da liễu
    # có mã ICD nên phải là DX, y các nhãn cùng bề mặt ở nơi khác.
    ("mụn trứng cá", 0, DX, [], ["L70.9"]),  # y GT[113]/GT[101]/GT[102]/GT[206] (5 lần)
    ("nám", 0, DX, [], ["L81.1"]),  # L81.1 "Rám má" = nám/melasma
    ("tàn nhang", 0, DX, [], ["L81.2"]),  # y GT[243] cùng bề mặt
    ("sạm da", 0, SYM, [], []),  # GIỮ SYM: mô tả tình trạng da, không phải tên bệnh
    # định danh (y GT[243] gán "da sạm" là SYM).
    ("bồn chồn", 0, SYM, [], []),
    ("lo lắng", 0, SYM, [], []),
    ("bứt rứt trong người", 0, SYM, [], []),
    ("giảm ham muốn", 0, SYM, [], []),
    ("lãnh cảm", 0, SYM, [], []),
    ("suy giảm hưng phấn", 0, SYM, [], []),
    # --- sang mẩu EHR nhiễm trùng vết mổ ---
    ("ban đỏ", 0, SYM, [], []),
    ("đau khi sờ nắn", 0, SYM, [], []),
    ("ống dẫn lưu JP", 0, LAB, [], []),
    ("sưng nề", 0, SYM, [], []),
    ("đau khi sờ nắn", 1, SYM, [], []),
    ("ban đỏ", 1, SYM, [], []),
    ("đau khi sờ nắn", 2, SYM, [], []),
    ("ban đỏ", 2, SYM, [], []),
    ("sưng nề", 1, SYM, [], []),
    ("chọc hút dịch", 0, LAB, [], []),
    ("cấy mẫu bệnh phẩm", 0, LAB, [], []),
    ("levafloxacin", 0, DRUG, [], ["82122"]),  # lỗi chính tả của levofloxacin
    ("cephalexin", 0, DRUG, [], ["2231"]),
    ("ban đỏ", 3, SYM, [], []),
    ("chóng mặt", 0, SYM, [], []),
    ("ban đỏ", 4, SYM, [], []),
    ("đau khi sờ nắn", 3, SYM, [], []),
    ("chóng mặt", 1, SYM, [], []),
    ("không sốt", 0, SYM, [NEG], []),
]

GT[39] = [  # 1886c ×1  24.txt — bệnh án viêm gan B cấp (bản gốc tiếng Việt, giàu KẾT_QUẢ_XÉT_NGHIỆM)
    ("mệt mỏi", 0, SYM, [], []),
    ("vàng da", 0, SYM, [], []),
    ("vàng mắt", 0, SYM, [], []),
    ("Hội chứng nhiễm trùng nhiễm độc", 0, DX, [], []),
    ("sốt nhẹ", 0, SYM, [], []),
    ("37^∘ 8", 0, VAL, [], []),
    ("sốt nóng liên tục", 0, SYM, [], []),
    ("gai rét", 0, SYM, [], []),
    ("cơn rét run", 0, SYM, [NEG], []),
    ("paracetamol", 0, DRUG, [], ["161"]),  # = acetaminophen trong RxNorm
    ("hết sốt", 0, SYM, [], []),
    ("vàng da", 1, SYM, [], []),
    ("vàng niêm mạc", 0, SYM, [], []),
    ("mệt mỏi", 1, SYM, [], []),
    ("hết sốt", 1, SYM, [], []),
    ("mệt mỏi", 2, SYM, [NEG], []),  # "hết mệt mỏi"
    ("BC", 0, LAB, [], []),
    ("5,38 G/l", 0, VAL, [], []),
    ("[[N]] 51,4%", 0, LAB, [], []),  # N = bạch cầu trung tính
    ("51,4%", 0, VAL, [], []),
    ("HBsAg", 0, LAB, [], []),
    ("Anti HBe", 0, LAB, [], []),
    ("Anti HBc IgG", 0, LAB, [], []),
    ("Anti HBc IgM", 0, LAB, [], []),
    ("Hội chứng viêm gan vàng da ứ mật", 0, DX, [], ["B16.9"]),
    ("hết sốt", 2, SYM, [], []),
    ("nước tiểu ít hơn so với bình thường", 0, SYM, [], []),
    ("vàng sậm như nước vối", 0, SYM, [], []),
    ("vàng da", 3, SYM, [], []),
    ("nước tiểu trong", 0, SYM, [], []),
    ("1000ml/24h", 0, VAL, [], []),
    ("Gan to dưới bờ sườn 3cm", 0, SYM, [], []),
    ("Bilirubin  toàn phần", 0, LAB, [], []),
    ("43 mmol/l", 0, VAL, [], []),
    ("27 mmol/l", 0, VAL, [], []),
    ("Ure", 0, LAB, [], []),
    ("5,9 mmol/l", 0, VAL, [], []),
    ("Creatinin", 0, LAB, [], []),
    ("89 micromol/l", 0, VAL, [], []),
    ("Hội chứng hủy hoại tế bào gan", 0, DX, [], ["K76.9"]),
    ("GOT", 0, LAB, [], []),
    ("542 U/l", 0, VAL, [], []),
    ("GPT", 0, LAB, [], []),
    ("628 U/l", 0, VAL, [], []),
    ("GGT", 0, LAB, [], []),
    ("234 U/l", 0, VAL, [], []),
    ("Chỉ số Deritis", 0, LAB, [], []),
    ("Tỷ lệ prothrombin", 0, LAB, [], []),
    ("55%", 0, VAL, [], []),
    ("vàng da", 4, SYM, [NEG, HIST], []),  # "chưa bị vàng da, vàng mắt trước đó"
    ("vàng mắt", 1, SYM, [NEG, HIST], []),
    ("nhiễm virus viêm gan B, C", 0, DX, [NEG, FAM], []),
    ("mang virus viêm gan B", 0, DX, [], ["Z22"]),  # người cùng đơn vị, không phải BN
    ("mệt mỏi", 3, SYM, [NEG], []),  # "mệt mỏi hết"
    ("vàng da", 5, SYM, [], []),
    ("đánh răng không chảy máu", 0, SYM, [NEG], []),
    ("1000ml/24h", 1, VAL, [], []),
    ("nước tiểu vàng nhẹ", 0, SYM, [], []),
]

GT[38] = [  # 1926c ×1  4.txt — EHR nôn ra máu / loét tá tràng, template lặp 3 mục (dùng ALL)
    ("Nôn ra máu", ALL, SYM, [], []),
    ("buồn nôn", ALL, SYM, [], []),
    ("tiêu chảy", ALL, SYM, [], []),
    ("viêm dạ dày ruột do virus", ALL, DX, [HIST], ["A08.4"]),
    ("khó khăn khi ăn uống qua đường miệng", ALL, SYM, [], []),
    ("đau bụng", ALL, SYM, [], []),
    ("omeprazole", ALL, DRUG, [], ["7646"]),
    ("hội chứng ruột kích thích", 0, DX, [HIST], ["K58"]),
    ("loét tá tràng", ALL, DX, [HIST], ["K26.9"]),
    ("nội soi", ALL, LAB, [], []),
    ("hồi tràng", ALL, DX, [HIST], ["K63.3"]),  # "nhiều loét tá tràng và hồi tràng"
    ("không thể giữ được bất cứ thứ gì", 0, SYM, [], []),
    ("xét nghiệm phân tìm cryptosporidium", ALL, LAB, [], []),
    ("test hơi thở h. pylori", ALL, LAB, [], []),
    ("Ăn uống kém", 0, SYM, [], []),
    # 3 khái niệm còn nguyên tiếng Anh (dịch máy bỏ sót) — vẫn là khái niệm
    ("nausea", 0, SYM, [], []),
    ("diarrhea", 0, SYM, [], []),
    ("abdominal pain", 0, SYM, [], []),
]

GT[37] = [  # 1933c ×1  44.txt — EHR tăng men gan/bilirubin + lại QA mày đay (bản dịch lỗi, mask khác block 32)
    ("tăng men gan", 0, SYM, [], []),
    ("tăng bilirubin máu", 0, DX, [], ["R17.9"]),
    ("ast", 0, LAB, [], []),
    ("421", 0, VAL, [], []),
    ("alt", 0, LAB, [], []),
    ("336", 0, VAL, [], []),
    ("alp", 0, LAB, [], []),
    ("185", 0, VAL, [], []),
    ("bilirubin toàn phần", 0, LAB, [], []),
    ("0.9", 0, VAL, [], []),
    ("siêu âm bụng có doppler", 0, LAB, [], []),
    ("chụp hida", 0, LAB, [], []),
    ("nồng độ acetaminophen", 0, LAB, [], []),
    ("nac", 0, DRUG, [NEG], ["197"]),  # N-acetylcystein, "Chưa từng dùng nac"
    ("ercp", ALL, LAB, [], []),
    ("túi mật giãn nở rõ rệt", 0, DX, [], []),
    ("sỏi mật", 0, DX, [HIST], ["K80.5"]),
    ("tăng bilirubin máu", 1, DX, [], ["R17.9"]),
    ("tăng men gan", 1, SYM, [], []),
    # --- sang mẩu QA mày đay, cùng nguồn với block 32/33 nhưng mask khác ---
    ("MÀY đay VÔ CĂN", ALL, DX, [], ["L50.1"]),
    ("MÀY đay MẠN", 0, DX, [], ["L50.8"]),
    ("Bạn đay vô căn", 0, DX, [], ["L50.1"]),  # lỗi dịch máy của "mày đay vô căn"
    ("***************", ALL, DRUG, [], []),  # kháng histamin H1 thế hệ 2 rồi thế hệ 1
    ("*********", 0, DRUG, [], []),  # corticoid liều thấp
]

GT[36] = [  # 1948c ×1  27.txt — QA giảng viêm phổi hoại tử/áp xe phổi + EHR đau đầu, phù gai thị
    ("viêm phổi hoại tử", 0, DX, [], ["J85.0"]),
    ("viêm phổi", 1, DX, [], ["J18.9"]),
    ("áp xe phổi", 0, DX, [], ["J85.2"]),
    ("VPHT", 0, DX, [], ["J85.0"]),  # viết tắt của "viêm phổi hoại tử"
    ("Viêm phổi", 2, DX, [], ["J18.9"]),
    ("viêm phế quản", 0, DX, [], ["J40"]),
    ("Viêm phổi", 3, DX, [], ["J18.9"]),
    ("thuốc kháng sinh", 0, DRUG, [], []),
    ("suy giảm miễn dịch", 0, DX, [], ["D84.9"]),
    ("hoại tử nhu mô phổi", 0, DX, [], ["J85.0"]),
    ("Viêm phổi hoại tử", 1, DX, [], ["J85.0"]),
    ("áp-xe nhỏ", 0, DX, [], ["J85.2"]),
    ("Áp xe phổi", 1, DX, [], ["J85.2"]),
    ("khạc ra mủ", 0, SYM, [], []),
    ("áp xe phổi", 2, DX, [], ["J85.2"]),
    # --- hết mẩu QA, sang mẩu EHR ---
    ("đau đầu gián đoạn", 0, SYM, [], []),
    ("đau đầu kéo dài", 0, SYM, [], []),
    ("nhìn mờ", 0, SYM, [], []),
    ("đau đầu nhiều hơn", 0, SYM, [], []),
    ("nhìn mờ", 1, SYM, [], []),
    ("đau đầu", 3, SYM, [], []),
    # "phù gai thị" gán TRIỆU_CHỨNG cho thống nhất với GT[62]/GT[71]/GT[179]
    # (dấu hiệu khám, xuất hiện dưới mục "Dấu hiệu lâm sàng").
    ("phù gai thị", 0, SYM, [], []),
]

GT[82] = [  # 1061c — đuôi riêng (782c đầu thừa hưởng block 35)
    ("tổn thương vùng âm hộ và mông bên phải", 1, SYM, [], []),
    ("Tổn thương cực kỳ đau đớn", 0, SYM, [], []),
    ("tổn thương dạng bóng nước ngày càng nặng", 0, SYM, [], []),
    ("Lan đến mông bên phải", 0, SYM, [], []),
    ("dịch giống mủ có màu vàng", 0, SYM, [], []),
]

GT[35] = [  # 1986c ×1  15.txt — EHR tổn thương âm hộ/mông (viêm mô bào) + chèn 2 mẩu tờ HDSD thuốc
    ("tổn thương vùng âm hộ và mông bên phải ngày càng nặng", 0, SYM, [], []),
    ("tổn thương vùng âm hộ phải lan rộng sang mông phải", 0, SYM, [], []),
    ("tổn thương đơn độc vùng âm hộ phải", 0, SYM, [], []),
    ("cotrimoxazol", 0, DRUG, [], ["10831"]),
    ("doxycyclin", 0, DRUG, [], ["3640"]),
    ("viêm mô tế bào", 0, DX, [], ["L03.3"]),
    ("ban đỏ", 0, SYM, [], []),
    ("bọng nước", 0, SYM, [], []),
    ("đau nhiều", 0, SYM, [], []),
    ("rỉ dịch vàng đục giống mủ", 0, SYM, [], []),
    # --- hết 782 ký tự chia sẻ với block 82 ---
    ("*******", 0, DRUG, [], []),  # tên sản phẩm bị che
    ("Pimperan", 0, DRUG, [], ["6915"]),  # biệt dược Việt của metoclopramide
    ("metoclopramide", 0, DRUG, [], ["6915"]),
    ("cực kỳ đau đớn", 0, SYM, [], []),
    ("ban đỏ", 1, SYM, [], []),
    ("chảy mủ", 0, SYM, [], []),
    ("bactrim", 0, DRUG, [], ["151399"]),
    ("doxycycline", 0, DRUG, [], ["3640"]),
    ("Viêm mô tế bào", 1, DX, [], ["L03.3"]),
    ("ban đỏ", 2, SYM, [], []),
    ("dịch tiết có vẻ như mủ", 0, SYM, [], []),
    ("doxycycline", 1, DRUG, [], ["3640"]),
    ("bactrim", 1, DRUG, [], ["151399"]),
    ("Viêm mô tế bào", 2, DX, [], ["L03.3"]),
]

GT[33] = [  # 2022c ×1  19.txt — EHR đau bụng/táo bón + QA mày đay (bản dịch SẠCH của block 32)
    ("tylenol", ALL, DRUG, [], ["202433"]),
    ("đau", 0, SYM, [], []),
    ("đau vẫn tiếp tục", 0, SYM, [], []),
    ("đau bụng", 0, SYM, [], []),
    ("táo bón", 0, SYM, [], []),
    ("buồn nôn", 0, SYM, [], []),
    ("đau hố chậu", 0, SYM, [], []),
    ("cơn đau vẫn tiếp diễn", 0, SYM, [], []),
    ("buồn nôn", 1, SYM, [], []),
    ("quả mận khô", 0, DRUG, [], []),  # dùng như thuốc nhuận tràng
    ("MÀY ĐAY VÔ CĂN", ALL, DX, [], ["L50.1"]),
    ("MÀY ĐAY MẠN TÍNH", 0, DX, [], ["L50.8"]),
    ("****************", ALL, DRUG, [], []),  # kháng histamin H1 thế hệ 2 và 1
    ("corticoid", 0, DRUG, [], []),
]

GT[34] = [  # 2016c ×1  10.txt — EHR đánh trống ngực / ngoại tâm thu
    ("đánh trống ngực", ALL, SYM, [], []),
    ("Khó thở nhẹ", 0, SYM, [], []),
    # SỬA (chống span lồng nhau): "khó thở" ALL bắt 7 lần, trong đó lần [0] chính là
    # phần đầu của "Khó thở nhẹ" ngay trên (văn bản: "- Khó thở nhẹ khó thở", dịch lặp).
    # Bỏ lần [0], giữ 6 lần còn lại.
    ("khó thở", 1, SYM, [], []),
    ("khó thở", 2, SYM, [], []),
    ("khó thở", 3, SYM, [], []),
    ("khó thở", 4, SYM, [], []),
    ("khó thở", 5, SYM, [], []),
    ("khó thở", 6, SYM, [], []),
    ("cảm giác thắt chặt ngực", ALL, SYM, [], []),
    ("mệt mỏi", ALL, SYM, [], []),
    ("giảm dung nạp gắng sức", 0, SYM, [], []),
    # "Không buồn nôn, hay nôn, đổ mồ hôi" -> 3 triệu chứng bị phủ định
    ("buồn nôn", 0, SYM, [NEG], []),
    ("[[nôn]], đổ mồ hôi", 0, SYM, [NEG], []),
    ("đổ mồ hôi", 0, SYM, [NEG], []),
    ("không có khó chịu vùng ngực", 0, SYM, [NEG], []),
    ("monitor holter", 0, LAB, [], []),
    ("Nhịp xoang chiếm ưu thế", 0, DX, [], []),
    ("ngoại tâm thu nhĩ", 0, DX, [], []),
    ("ngoại tâm thu thất", 0, DX, [], ["I49.3"]),
    ("metoprolol", 0, DRUG, [], ["6918"]),
    ("atenolol", 0, DRUG, [], ["1202"]),
    ("siêu âm tim qua thành ngực", 0, LAB, [], []),
    ("aspirin", 0, DRUG, [], ["1191"]),
    ("chụp x-quang ngực", 0, LAB, [], []),
    # liều thuốc (25mg, 325mg) KHÔNG phải KẾT_QUẢ_XÉT_NGHIỆM — theo định nghĩa đề
    # và tiền lệ: 8/8 KẾT_QUẢ_XÉT_NGHIỆM hiện có đều là trị số cận lâm sàng.
    ("phân tích nước tiểu", 0, LAB, [], []),
    ("ecg", 0, LAB, [], []),
]

GT[32] = [  # 2086c ×1  30.txt — EHR viêm mô tế bào chân + QA mày đay vô căn (bản dịch máy rất lỗi)
    ("phù", 0, SYM, [], []),
    ("chủ quan sốt", ALL, SYM, [], []),
    ("ớn lạnh", ALL, SYM, [], []),
    ("đau tăng dần", ALL, SYM, [], []),
    ("phù hai bên", ALL, SYM, [], []),
    ("ban đỏ, RL", ALL, SYM, [], []),
    ("[[phù]], ban đỏ", 0, SYM, [], []),
    ("[[ban đỏ]], chủ quan sốt", 0, SYM, [], []),
    ("lơ mơ khi đến tầng", 0, SYM, [], []),
    ("không thể tỉnh táo đủ lâu", 0, SYM, [], []),
    # QA mày đay: bệnh nhân (người hỏi) THẬT SỰ mắc -> assertions rỗng
    ("MÀY đay VÔ CĂN", 0, DX, [], ["L50.1"]),
    ("MÀY đay MẠN", 0, DX, [], ["L50.8"]),
    ("mày đay vô căn", 1, DX, [], ["L50.1"]),
    ("Bạn đay vô căn", 0, DX, [], ["L50.1"]),  # lỗi dịch máy của "mày đay vô căn"
    # 3 tên thuốc bị mask (kháng histamin H1 thế hệ 2/1 và corticoid)
    ("***************", ALL, DRUG, [], []),
    ("*********", 0, DRUG, [], []),
]

GT[59] = [  # 1312c — đuôi riêng (1048c đầu thừa hưởng block 30)
    ("đau bụng/khó chịu vùng bụng tăng dần", 0, SYM, [], []),
    # nhãn ALL của block 30 không tự thừa hưởng được (block này thêm lần xuất
    # hiện mới ở đuôi) -> khai lại tay cho các lần trong tiền tố + đuôi
    ("amyloidosis", ALL, DX, [], ["E85.9"]),
    ("bệnh thoái hóa tinh bột", ALL, DX, [], ["E85.9"]),
    # "hóa trị" là liệu pháp thuốc -> THUỐC (thống nhất với GT[57]); "ghép gan"
    # là thủ thuật -> không gán (như "cấy que", "lắp chân giả").
    ("hóa trị", 0, DRUG, [], []),
]

GT[88] = [  # 922c — đuôi riêng (551c đầu thừa hưởng block 30) — mục tiền sử bệnh mạn
    ("Bệnh bạch cầu dòng tủy mãn tính", 0, DX, [HIST], ["C92.1"]),
    ("gleevec", 0, DRUG, [HIST], ["282386"]),
    ("Tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("tăng lipid máu, không đặc hiệu", 0, DX, [HIST], ["E78.5"]),
    ("Đái tháo đường típ 2", 0, DX, [HIST], ["E11"]),
    ("hẹp ống sống", 0, DX, [HIST], ["M48.0"]),
    ("Giả gout", 0, DX, [HIST], ["M11.2"]),  # pseudogout/CPPD = vôi hoá sụn khớp khác
    ("bệnh thận mạn, không đặc hiệu Giai đoạn 4", 0, DX, [HIST], ["N18.4"]),
    ("tăng sản tuyến tiền liệt", 0, DX, [HIST], ["N40"]),
    ("Nhiều lần ngã gần đây", 0, SYM, [HIST], []),
    ("[[Ngã]]\n", 0, SYM, [HIST], []),
    ("ảo giác", 0, SYM, [HIST], []),
    ("gleevec", 1, DRUG, [HIST, NEG], ["282386"]),  # SỬA ở đợt 25: "(dừng theo chỉ dẫn
    # sau xuất viện)" -> thuốc đã dừng = isNegated. Trước đây thiếu NEG, lệch với
    # GT[87]/GT[168] gán cùng bề mặt trong cùng ngữ cảnh.
]

GT[30] = [  # 2288c ×1  21.txt — QA giải thích bệnh thoái hóa tinh bột + EHR sỏi ống mật chủ
    # Phần QA: bác sĩ giảng về bệnh, bệnh nhân KHÔNG mắc. Nhưng "bệnh thoái hóa
    # tinh bột" là tên chẩn đoán nên vẫn gán (xem quy ước "khái niệm trong bài
    # giảng" ở worklog/07) — recall quan trọng hơn.
    ("bệnh thoái hóa tinh bột", ALL, DX, [], ["E85.9"]),
    ("amyloidosis", ALL, DX, [], ["E85.9"]),
    ("lắng đọng protein", 0, SYM, [], []),
    ("suy các cơ quan", 0, SYM, [], []),
    ("tử vong", 0, SYM, [], []),
    ("ung thư máu", 0, DX, [], []),
    ("đa u tủy", 0, DX, [], ["C90.0"]),
    # ---- mẩu EHR: triệu chứng thật của bệnh nhân ----
    ("đau bụng vùng hạ sườn phải", 0, SYM, [], []),
    ("chướng bụng", ALL, SYM, [], []),
    ("buồn nôn thoáng qua", ALL, SYM, [], []),
    ("Nôn mửa", 0, SYM, [], []),
    ("đau lưng âm ỉ", 0, SYM, [], []),
    ("đau bụng hạ sườn phải", 0, SYM, [], []),
    ("đau lưng", 1, SYM, [], []),
    ("đau lưng kéo dài", 0, SYM, [], []),
    ("nội soi thực quản - dạ dày - tá tràng", 0, LAB, [], []),
    ("viêm dạ dày", 0, DX, [], ["K29.7"]),
    # "Đã ngừng sử dụng thuốc NSAIDs" -> isNegated, thống nhất với GT[44] (cùng câu
    # nguồn); trước đây ghi HIST là sai tiền lệ.
    ("thuốc NSAIDs", 0, DRUG, [NEG], []),
    ("omeprazole", 0, DRUG, [], ["7646"]),
    ("Chụp cộng hưởng từ mật tụy", 0, LAB, [], []),
    ("sỏi đoạn cuối ống mật chủ", 0, DX, [], ["K80.5"]),  # thống nhất 6/7 chỗ khác
    ("Xét nghiệm chức năng gan", ALL, LAB, [], []),
    ("men gan tăng", 0, SYM, [], []),
    ("tăng men gan", 0, SYM, [], []),
]

GT[29] = [  # 2324c ×1  3.txt — EHR đột quỵ, template "Tiền sử bệnh hiện tại" lặp nguyên khối
    # Cả block là bệnh sử của lần nhập viện NÀY -> không isHistorical (trừ chỗ
    # nói rõ "tiền sử"). Mọi triệu chứng lặp 2 lần (mục "Lý do nhập viện" và
    # "Triệu chứng khi nhập viện") -> dùng ALL.
    ("yếu sức nửa người bên phải", ALL, SYM, [], []),
    ("tình trạng tri giác giảm sút", ALL, SYM, [], []),
    ("nhìn song thị", ALL, SYM, [], []),
    ("nằm sải trên sàn", ALL, SYM, [], []),
    ("không thể tự đứng dậy", ALL, SYM, [], []),
    ("yếu sức chân phải", ALL, SYM, [], []),
    ("Không nhớ cách mình bị ngã", 0, SYM, [], []),
    ("không thể chịu lực ở chân phải", ALL, SYM, [], []),
    ("khuỵu chân", ALL, SYM, [], []),
    ("chụp ct sọ não", ALL, LAB, [], []),
    # "kết quả âm tính" — kết quả bằng chữ, không có giá trị số. Theo tiền lệ
    # (8/8 KẾT_QUẢ_XÉT_NGHIỆM hiện có đều là số + đơn vị) -> KHÔNG gán.
    ("chọc dò dịch não tủy", ALL, LAB, [], []),
    ("nhịp tim chậm nặng", ALL, SYM, [], []),
    ("hạ huyết áp", ALL, DX, [], ["I95.9"]),
    ("intravenous fluids", ALL, DRUG, [], []),
    ("Code tai biến mạch máu não", 0, DX, [], []),
    ("tỉnh chậm phản xạ kém", 0, SYM, [], []),
    ("Phủ nhận các bệnh nền lớn", 0, DX, [NEG, HIST], []),
    ("nhiễm trùng răng miệng", ALL, DX, [HIST], []),
    ("kháng sinh", ALL, DRUG, [HIST], []),
    # "Phủ nhận tiền sử bị tai biến mạch máu não hoặc co giật" -> NEG + HIST
    ("tai biến mạch máu não", 1, DX, [NEG, HIST], []),
    ("co giật", 0, SYM, [NEG, HIST], []),
    ("mệt mỏi", ALL, SYM, [], []),
    ("yếu chân phải", 0, SYM, [], []),
    ("tỉnh chậm, phản xạ kém", 0, SYM, [], []),
]

GT[28] = [  # 2430c ×1  17.txt — QA chảy máu chân răng (liệt kê nguyên nhân) + mẩu tiền sử EHR
    # Bệnh nhân thật sự có: chảy máu chân răng + hôi miệng (vấn đề đem đi hỏi).
    ("chảy máu chân răng", 0, SYM, [], []),
    ("hôi miệng", 0, SYM, [], []),
    # Phần "Nguyên nhân": bác sĩ liệt kê các bệnh CÓ THỂ gây ra, bệnh nhân chưa
    # được chẩn đoán bệnh nào. Vẫn gán CHẨN_ĐOÁN — xem worklog/07 mục "khái niệm
    # trong danh sách nguyên nhân". Lý do ngắn: đề không có assertion cho
    # "khả năng", và bỏ hẳn thì mất recall (recall = toàn bộ điểm).
    ("Vệ sinh răng miệng kém", 0, SYM, [], []),
    ("tổn thương nướu", 0, SYM, [], []),
    ("Viêm quanh răng", 0, DX, [], ["K05.2", "K05.3"]),
    ("viêm và sưng", 0, SYM, [], []),
    ("sang chấn răng", 0, SYM, [], []),
    ("Viêm nha chu", 0, DX, [], ["K05"]),
    ("nhiễm trùng lợi nặng", 0, SYM, [], []),
    ("đau khi nhai", 0, SYM, [], []),
    ("răng lung lay", 0, SYM, [], []),
    ("sưng nướu", 0, SYM, [], []),
    ("dễ chảy máu răng", 0, SYM, [], []),
    ("có mủ", 0, SYM, [], []),
    ("Viêm nha chu", 1, DX, [], ["K05"]),
    ("chân răng có thể bị hư hại", 0, SYM, [], []),
    ("mất răng", 0, DX, [], ["K08.1"]),
    ("viêm khớp dạng thấp", 0, DX, [], ["M06.9"]),
    ("các bệnh hô hấp", 0, DX, [], []),
    ("đột quỵ", 0, DX, [], ["I64"]),
    ("Thiếu canxi và vitamin", 0, DX, [], ["E56.9"]),
    ("Thiếu hụt canxi", 0, DX, [], []),
    ("loãng xương", 0, DX, [], ["M81.9"]),
    ("sâu răng", 0, DX, [], ["K02.9"]),
    ("viêm nha chu", 2, DX, [], ["K05"]),
    ("Hôi miệng", 1, SYM, [], []),
    ("chảy máu chân răng", 1, SYM, [], []),
    ("thiếu hụt vitamin K", 0, DX, [], ["E56.1"]),
    ("Tiểu đường", 0, DX, [], ["E14"]),
    ("Hôi miệng", 2, SYM, [], []),
    ("chảy máu chân răng", 2, SYM, [], []),
    ("bệnh tiểu đường", 0, DX, [], ["E14"]),
    ("giảm sản xuất insulin", 0, SYM, [], []),
    ("tiểu đường", 2, DX, [], ["E14"]),  # SỬA (chống span lồng nhau): trước ghi index 1,
    # nhưng lần [1] nằm BÊN TRONG "bệnh tiểu đường" ở dòng trên. Lần đứng riêng cần gán
    # ("người bị tiểu đường suy yếu hệ miễn dịch") là index 2.
    ("suy yếu hệ miễn dịch", 0, SYM, [], []),
    ("khó đông máu", 0, SYM, [], []),
    ("chân răng chảy máu kéo dài", 0, SYM, [], []),
    ("nồng độ đường trong máu cao", 0, SYM, [], []),
    # "Tác dụng phụ của thuốc": tên NHÓM thuốc, không phải tên thuốc cụ thể.
    # Đề nói THUỐC = "tên thuốc mà bệnh nhân điều trị". Đây không phải thuốc
    # bệnh nhân dùng, nhưng vẫn là tên thuốc -> gán, không có mã RxNorm nhóm.
    ("Kháng histamin H1", 0, DRUG, [], []),
    ("thuốc chống trầm cảm", 0, DRUG, [], []),
    ("thuốc lợi tiểu", 0, DRUG, [], []),
    ("thuốc kháng sinh", 0, DRUG, [], []),
    ("thuốc chống nôn", 0, DRUG, [], []),
    ("hôi miệng", 3, SYM, [], []),
    ("chảy máu chân răng", 3, SYM, [], []),
    ("Hút thuốc lá", 0, SYM, [], []),
    ("hỏng men răng", 0, SYM, [], []),
    ("gai lưỡi phát triển quá mức", 0, SYM, [], []),
    ("hôi miệng", 4, SYM, [], []),
    ("chảy máu chân răng", 4, SYM, [], []),
    ("mất răng", 1, DX, [], ["K08.1"]),
    # ---- mẩu tiền sử EHR ghép vào (bệnh nhân nam, ung thư dương vật) ----
    ("bệnh mạch máu ngoại biên", 0, DX, [HIST], ["I73.9"]),
    ("bệnh phổi tắc nghẽn mạn tính", 0, DX, [HIST], ["J44.9"]),
    ("Ngưng thở khi ngủ do tắc nghẽn", 0, DX, [HIST], ["G47.3"]),
    ("BiPAP", 0, DRUG, [HIST], []),  # thực chất là thiết bị thở, không phải thuốc
    ("Ung thư biểu mô tế bào vảy xâm nhập của dương vật", 0, DX, [HIST], ["C60.9"]),
    ("biệt hóa kém", 0, DX, [HIST], []),
    ("bờ diện cắt dương tính", 0, DX, [HIST], []),
    # ---- phần bác sĩ khuyên dùng (mẹo dân gian + thủ thuật) ----
    ("trà gừng", 0, DRUG, [], []),
    ("mật ong", 0, DRUG, [], []),
    ("viêm", 6, SYM, [], []),  # SỬA (chống span lồng nhau): trước ghi index 3, nhưng lần
    # [3] chính là "Viêm nha chu nếu để kéo dài" -> nằm trong nhãn "Viêm nha chu" index 1.
    # Lần cần gán ở đây là "khử mùi hôi do viêm," = index 6.
    ("giảm sưng đau", 0, SYM, [], []),
    ("Trà đinh hương", 0, DRUG, [], []),
    ("bào láng gốc răng", 0, LAB, [], []),
    ("cao răng", 0, SYM, [], []),
    ("Ghép mô mềm ở vòm họng", 0, LAB, [], []),
    ("nướu bị ảnh hưởng", 0, SYM, [], []),
    ("khám răng miệng", 0, LAB, [], []),
]

GT[27] = [  # 2639c ×1  5.txt — QA vô sinh + EHR đường mật (mục "trước nhập viện" lặp gần y nguyên)
    # QA: bác sĩ liệt kê xét nghiệm CẦN làm, chưa thực hiện. Vẫn gán TÊN_XÉT_NGHIỆM
    # vì loại này không có assertion phân biệt thời/thể (đề chỉ cho assertion với
    # DX/THUỐC/TRIỆU_CHỨNG) -> nhãn xét nghiệm đọc rộng theo tên, không theo thời.
    ("vô sinh", 0, DX, [], ["N97.9"]),
    ("chưa có thai", 0, SYM, [], []),
    ("xét nghiệm tinh dịch đồ", 0, LAB, [], []),
    ("xét nghiệm cận lâm sàng", 0, LAB, [], []),
    ("siêu âm", 0, LAB, [], []),
    ("chụp tử cung vòi trứng", 0, LAB, [], []),
    ("xét nghiệm nội tiết", 0, LAB, [], []),
    ("Kinh nguyệt của bạn thưa", 0, SYM, [], []),
    ("thuốc tránh thai", 0, DRUG, [], []),
    ("Hội chứng buồng trứng đa nang", 0, DX, [], ["E28.2"]),
    ("rậm lông", 0, SYM, [], []),
    # "béo phì" gán CHẨN_ĐOÁN cho thống nhất với 2 chỗ khác (E66.9 có mã riêng).
    ("béo phì", 0, DX, [], ["E66.9"]),
    ("siêu âm buồng trứng", 0, LAB, [], []),
    ("nhiều nang", 0, SYM, [], []),
    ("vô sinh", 1, DX, [], ["N97.9"]),
    # ---- mẩu EHR: bệnh nhân nữ, ống dẫn mật, nghi ung thư biểu mô tuyến ----
    # "phủ nhận bất kỳ buồn nôn, nôn, sốt, ớn lạnh, hoặc dịch rò rỉ" -> tất cả NEG.
    # Cả 3 lần liệt kê đều là phủ nhận nên dùng ALL.
    ("buồn nôn", ALL, SYM, [NEG], []),
    # SỬA (chống span lồng nhau): needle "[[nôn]]," định lấy chữ "nôn" ĐỨNG RIÊNG (lần
    # thứ hai trong "buồn nôn, nôn,"), nhưng "buồn nôn," cũng khớp mẫu đó -> nó bắt cả
    # 6 lần, 3 trong đó nằm bên trong "buồn nôn". Thêm ngữ cảnh "nôn, " phía trước để
    # chỉ khớp lần đứng riêng.
    ("nôn, [[nôn]],", ALL, SYM, [NEG], []),
    ("sốt", ALL, SYM, [NEG], []),
    ("ớn lạnh", ALL, SYM, [NEG], []),
    ("dịch rò rỉ quanh ống thông", ALL, SYM, [NEG], []),
    ("đau ngực", 0, SYM, [NEG], []),
    ("khó thở", 0, SYM, [NEG], []),
    ("cholangiogram", ALL, LAB, [], []),
    ("tắc nghẽn kéo dài gần chỗ nối mật tụy", ALL, DX, [], ["K83.1"]),
    ("sinh thiết", ALL, LAB, [], []),
    ("lấy mẫu bằng bàn chải", ALL, LAB, [], []),
    ("tế bào bất thường", ALL, DX, [], ["R85.6"]),
    ("ung thư biểu mô tuyến", ALL, DX, [], ["C24.0"]),
    ("đau khi sờ nắn xung quanh vị trí đặt ống dẫn", 0, SYM, [], []),
    ("cân nặng đã cải thiện", 0, SYM, [], []),
]

# ------------------------------------------------
# 2 block còn lại của file 5.txt (block 27 đã xong) -> gán TRỌN file.
# 5.txt = CÙNG bệnh nhân đường mật với 88.txt, bản dịch chi tiết hơn: mục 1 tiền sử
# phẫu thuật (block 201) -> mục 2 HPI bị chèn QA vô sinh (block 27, đã gán) -> mục 3
# đánh giá tại bệnh viện (block 152).
# Quy ước: DÙNG LẠI Y NGUYÊN nhãn của GT[27] (cùng file, cùng bệnh án) và của
# GT[208] (88.txt, cùng câu tiền sử phẫu thuật ở bản dịch khác).
# ------------------------------------------------

GT[201] = [  # 309c ×1  5.txt — mục "1. Tiền sử bệnh nội khoa" (bản dịch dài của block 208)
    # Cùng câu với block 208 (88.txt): chung 60 ký tự tiền tố rồi lệch
    # ("- cắt bỏ ống dẫn mật chủ" vs ": Đã thực hiện phẫu thuật cắt bỏ ống dẫn mật
    # chung") -> SHARE không dùng được, gán tay theo đúng quyết định của GT[208].
    # "phẫu thuật cắt bỏ ống dẫn mật chung", "cắt bỏ một phần thùy gan bên trái",
    # "nối mật tụy bằng ống dẫn hồi tràng (RNY hepaticojejunostomy)": thủ thuật
    # -> không gán (GT[208]/GT[13]/GT[117]).
    # "vào ngày [Ngày]": chỗ khuyết ngày tháng của corpus -> không gán.
    ("ung thư biểu mô tế bào mật", 0, DX, [HIST], ["C24.0"]),  # lý do mổ -> gán + HIST
    # (GT[208] cùng câu, GT[13]:892). Bề mặt ở đây là "ung thư biểu mô tế bào mật"
    # (bản dịch khác của "ung thư đường mật" ở 88.txt) -> lấy đúng nguyên văn.
    # C24.0 dùng lại của GT[27]:4366 (cùng bệnh nhân, "ung thư biểu mô tuyến") và
    # GT[208]. Đã cân nhắc C22.1 "Ung thư biểu mô ống mật TRONG gan" nhưng loại:
    # bệnh nhân mổ ống mật CHUNG (ngoài gan) -> C24.0 "U ác tính ở ống mật ngoài gan".
    # Cắt hậu tố "không thể cắt bỏ" khỏi bề mặt, y như GT[208].
    # "2. Tiền sử bệnh hiện tại": tiêu đề mục -> không gán.
]

GT[152] = [  # 468c ×1  5.txt — mục "3. Đánh giá tại bệnh viện" (tóm tắt lại mục 2)
    # Mục 3 = lần nhập viện HIỆN TẠI -> KHÔNG assertion (tiền lệ GT[22]/GT[132]/
    # GT[142]/GT[154]). Tiêu đề mục và các tiêu đề nhóm ("Dấu hiệu lâm sàng",
    # "Kết quả phòng thí nghiệm", "Kết quả chẩn đoán hình ảnh", "Thủ thuật thực
    # hiện") -> không gán (GT[142]:1941).
    # Cả 4 dòng đều là TÓM TẮT LẠI các phát hiện đã có ở block 27 -> dùng lại y
    # nguyên nhãn của GT[27] để 2 block cùng bệnh án không lệch nhau.
    ("đau khi sờ nắn xung quanh vị trí đặt ống dẫn", 0, SYM, [], []),  # GT[27]:4367
    # "đặc biệt là khi hít thở sâu": yếu tố làm tăng -> không gán (GT[27] cùng câu
    # cũng chỉ lấy phần tên triệu chứng).
    ("lấy mẫu bằng bàn chải", 0, LAB, [], []),  # GT[27]:4364
    ("tế bào bất thường", ALL, DX, [], ["R85.6"]),  # 2 lần vì lỗi dịch lặp cụm dính
    # nhau "tế bào bất thườngtế bào bất thường" -> gán CẢ HAI (tiền lệ GT[132]:2164
    # "âm tính âm tính" và "túi mật giãn" lặp). Mã R85.6 theo GT[27]:4365.
    ("ung thư biểu mô tuyến", 0, DX, [], ["C24.0"]),  # GT[27]:4366. "đáng ngại cho"
    # = nghi ngờ -> vẫn gán DX, không assertion (GT[205]/GT[22]).
    ("cholangiogram", 0, LAB, [], []),  # GT[27]:4361
    ("tắc nghẽn kéo dài gần chỗ nối mật tụy", 0, DX, [], ["K83.1"]),  # GT[27]:4362
    # "ảnh hưởng đến ống dẫn trước và sau bên phải": vị trí lan -> không gán, đúng
    # như GT[27] cùng câu.
    # "Đặt 3 stent thành vách vĩnh viễn": thủ thuật/thiết bị -> không gán
    # (GT[27] cùng câu, GT[117], GT[208]).
]

GT[31] = [  # 2275c — đuôi riêng (1843c đầu thừa hưởng block 26)
    # "không ghi nhận run giật tay chân, không cứng đờ, không cắn lưỡi và
    #  không tiểu tiện không tự chủ" -> 4 triệu chứng bị phủ định
    ("run giật tay chân", 0, SYM, [NEG], []),
    ("cứng đờ", 0, SYM, [NEG], []),
    ("cắn lưỡi", 0, SYM, [NEG], []),
    ("tiểu tiện không tự chủ", 0, SYM, [NEG], []),
    # mục "Triệu chứng khi nhập viện" — nhắc lại nên nth lấy lần thứ 2
    ("Đau đầu vùng thái dương phải", 1, SYM, [], []),
    ("Tê bì vùng trán phải", 0, SYM, [], []),
    ("Cơn rối loạn ý thức thoáng qua", 1, SYM, [], []),
    ("Mất định hướng", 1, SYM, [], []),
    ("Mất thăng bằng", 0, SYM, [], []),
    ("Gần ngất", 0, SYM, [], []),
]

GT[25] = [  # 3012c ×1  9.txt — phần đuôi riêng (2677c đầu thừa hưởng block 24)
    # mục "Lý do nhập viện: theo dõi đại tràng giãn"
    ("đại tràng giãn", 0, DX, [], ["K59.3"]),
    # "phát hiện xét nghiệm máu có tăng bạch cầu"
    ("xét nghiệm máu", 0, LAB, [], []),
    ("tăng bạch cầu", 0, SYM, [], []),
    # lỗi template của corpus: "tăng bạch cầuNgày nay" dính chữ, cụm vẫn đúng
    ("ý thúc chậm hơn", 0, SYM, [], []),
    ("chụp CT", 0, LAB, [], []),
    # "chưa phát hiện bất thường trên phim chụp" -> kết quả mô tả bằng chữ,
    # tiền lệ chỉ gán KẾT_QUẢ cho giá trị số -> bỏ. Nhưng "chưa phát hiện bất
    # thường" là phủ định của bất thường, không phải triệu chứng bệnh nhân có.
    ("Bệnh nhân lơ mơ", 0, SYM, [], []),
]

# Nhãn chuyển tự động từ data/gt/ (6 file gán tay đầu, worklog/05-06).
GT[6] = [  # 614c ×2  72.txt,98.txt
    ("ý định tự tử", 0, SYM, [], []),
    ("ý nghĩ tự bắn vào đầu", 0, SYM, [], []),
    ("trầm cảm", 0, DX, [], ["F32.9"]),
    ("hưng cảm", 0, DX, [], ["F30.9"]),
    ("tăng hoạt động", 0, SYM, [], []),
    ("giảm nhu cầu ngủ", 0, SYM, [], []),
    ("ý định tự tử", 1, SYM, [], []),
    ("suboxone", 0, DRUG, [HIST], ["352990"]),
    ("suboxone", 1, DRUG, [HIST], ["352990"]),
    ("ý nghĩ tự tử", 0, SYM, [], []),
    ("nghĩ tự bắn vào đầu", 1, SYM, [], []),
    ("lo âu", 0, SYM, [], []),
    ("hoảng sợ", 0, SYM, [], []),
    ("hoang tưởng", 0, SYM, [], []),
]
GT[14] = [  # 343c ×2  55.txt,97.txt
    ("Suy thận mạn giai đoạn V", 0, DX, [HIST], ["N18.5"]),
    ("đái tháo đường", 0, DX, [HIST], ["E14"]),
    ("tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("u ác của tuyến tiền liệt", 0, DX, [HIST], ["C61"]),
    ("Sinh thiết tuyến tiền liệt", 0, LAB, [], []),
]
GT[15] = [  # 327c ×2  80.txt,95.txt
    ("bệnh gút", 0, DX, [], ["M10"]),
    ("khỏi đau", 0, SYM, [HIST], []),
]
GT[20] = [  # 249c ×2  42.txt,95.txt
    ("đái tháo đường", 0, DX, [HIST], ["E14"]),
    ("tăng huyết áp", 0, DX, [HIST], ["I10"]),
    ("béo phì", 0, DX, [HIST], ["E66.9"]),
    ("ngưng thở khi ngủ do tắc nghẽn", 0, DX, [HIST], ["G47.3"]),
    ("tylenol", 0, DRUG, [HIST], ["202433"]),
    ("mucinex d", 0, DRUG, [HIST], ["352777"]),
    ("tiêu chảy", 0, SYM, [], []),
]
GT[68] = [  # 1187c ×1  99.txt
    ("biến đổi ý thức", 0, SYM, [], []),
    ("hạ thân nhiệt", 0, DX, [], ["T68"]),
    ("hạ huyết áp", 0, DX, [], ["I95.9"]),
    ("biến đổi ý thức", 1, SYM, [], []),
    ("hạ thân nhiệt", 1, DX, [], ["T68"]),
    ("hạ huyết áp", 1, DX, [], ["I95.9"]),
    ("90", 0, VAL, [], []),
    ("biến đổi ý thức", 2, SYM, [], []),
    ("hạ thân nhiệt", 2, DX, [], ["T68"]),
    ("Khó thở khi nằm đầu bằng", 0, SYM, [], []),
    ("SpO2", 0, LAB, [], []),
    ("99%", 0, VAL, [], []),
    ("Tim nhịp không đều", 0, SYM, [], []),
    ("tần số", 0, LAB, [], []),
    ("105 chu  kì/phút", 0, VAL, [], []),
    ("Huyết áp", 3, LAB, [], []),
    ("110/70  mmHg", 0, VAL, [], []),
    ("rì rào phế nang giảm", 0, SYM, [], []),
    ("không có tiếng rales bệnh lí", 0, SYM, [NEG], []),
    ("Không có điểm đau", 0, SYM, [NEG], []),
    ("Không phù", 0, SYM, [NEG], []),
    ("Đợt cấp COPD", 0, DX, [], ["J44.1"]),
    ("Tâm phế mạn", 0, DX, [], ["I27.9"]),
    ("Cơn tim nhanh nhĩ", 0, DX, [], ["I47.1"]),
    ("Nhiễm khuẩn đường tiêu hóa", 0, DX, [], ["A09.9"]),
    ("Tăng huyết áp", 0, DX, [], ["I10"]),
    ("chụp x-quang ngực", 0, LAB, [], []),
    ("không có hình ảnh tổn thương viêm cấp tính", 0, DX, [NEG], []),
    ("chụp x-quang ngực", 1, LAB, [], []),
    ("cấy nước tiểu", 0, LAB, [], []),
    ("điện tâm đồ", 0, LAB, [], []),
    ("nhịp chậm xoang", 0, DX, [], ["R00.1"]),
    ("đường huyết lúc đói", 0, LAB, [], []),
    ("đường huyết thấp", 0, DX, [], []),
]
GT[69] = [  # 1182c ×1  96.txt
    ("chụp cắt lớp vi tính (ct)", 0, LAB, [], []),
    ("tắc hẹp 80% động mạch thận trái", 0, DX, [], ["I70.1"]),
    ("Môi bong vẩy trắng", 0, SYM, [], []),
    ("môi khô", 0, SYM, [], []),
    ("vitamin C", 0, DRUG, [], ["1151"]),
]
GT[119] = [  # 650c ×1  100.txt
    ("************", 0, DRUG, [], []),
    ("nguy cơ tiền sản giật cao", 0, DX, [], ["O14"]),
    ("tiền sản giật", 1, DX, [], ["O14"]),
    ("tiền sản giật", 2, DX, [], ["O14"]),
    ("*******", 0, DRUG, [], []),
    ("chảy máu", 0, SYM, [], []),
    ("*******", 1, DRUG, [], []),
    ("lo lắng", 0, SYM, [], []),
    ("aspirin", 0, DRUG, [], ["1191"]),
]
GT[121] = [  # 648c ×1  95.txt
    ("bệnhgout", 0, DX, [], ["M10"]),
    ("hạt tophi", 0, DX, [], ["M10"]),
    ("hạt tophi", 1, DX, [], ["M10"]),
    ("hạt tophi", 2, DX, [], ["M10"]),
    ("hạt tophi", 3, DX, [], ["M10"]),
    ("sưng", 0, SYM, [], []),
    ("tấy đỏ", 0, SYM, [], []),
    ("hạt tophi", 4, DX, [], ["M10"]),
    ("hoại tử", 0, DX, [], []),
    ("biến dạng xương khớp", 0, DX, [], []),
    ("nhiễm trùng máu", 0, DX, [], ["A41.9"]),
]
GT[145] = [  # 504c ×1  97.txt
    ("bệnh trĩ", 0, DX, [], ["K64.9"]),
    ("Ure", 0, LAB, [], []),
    ("69", 0, VAL, [], []),
    ("91 mg/dl", 0, VAL, [], []),
    ("24.6 -32.5 mmol/l", 0, VAL, [], []),
    ("photpho", 0, LAB, [], []),
    ("8.4", 0, VAL, [], []),
    ("u ác của tuyến tiền liệt", 0, DX, [], ["C61"]),
]
GT[147] = [  # 497c ×1  98.txt
    ("Đã tử vong", 0, DX, [FAM], []),
    ("Rối loạn cảm xúc", 0, DX, [HIST], ["F39"]),
    ("Rối loạn lưỡng cực", 0, DX, [HIST], ["F31.9"]),
    ("rối loạn lo âu", 0, DX, [HIST], ["F41.9"]),
    ("klonopin", 0, DRUG, [HIST], ["202585"]),
    ("clonidine", 0, DRUG, [HIST], ["2599"]),
    ("clonidine", 1, DRUG, [HIST], ["2599"]),
    ("suboxone", 0, DRUG, [HIST], ["352990"]),
]
GT[148] = [  # 494c ×1  100.txt
    ("mang thai được 22 tuần", 0, SYM, [], []),
    ("nguy cơ tiền sản giật cao", 0, DX, [], ["O14"]),
    ("************", 0, DRUG, [], []),
    ("cục máu đông", 0, SYM, [], []),
    ("đi tiêu ra máu", 0, SYM, [], []),
]
GT[153] = [  # 467c ×1  97.txt
    ("mệt mỏi", 0, SYM, [], []),
    ("mất trí nhớ chi tiết", 0, SYM, [], []),
    ("khó chịu", 0, SYM, [], []),
    ("mệt mỏi", 1, SYM, [], []),
    ("ăn không ngon miệng", 0, SYM, [], []),
    ("ngứa da toàn thân", 0, SYM, [], []),
    ("mất trí nhớ chi tiết", 1, SYM, [], []),
    ("khó thở khi gắng sức", 0, SYM, [], []),
    ("buồn nôn", 0, SYM, [], []),
    ("nôn", 1, SYM, [], []),
    ("Mệt mỏi", 2, SYM, [], []),
    ("Ăn không ngon miệng", 1, SYM, [], []),
    ("Ngứa da toàn thân", 1, SYM, [], []),
    ("mất trí nhớ chi tiết", 2, SYM, [], []),
]
GT[243] = [  # 178c ×1  98.txt
    ("tàn nhang", 0, DX, [], ["L81.2"]),
    ("da sạm", 0, SYM, [], []),
]
GT[267] = [  # 122c ×1  99.txt
    ("viêm tủy xương", 0, DX, [HIST], ["M86.9"]),
    ("bàng quang thần kinh", 0, DX, [HIST], ["N31.9"]),
    ("liệt hai chi dưới", 0, DX, [HIST], ["G82.2"]),
]
GT[269] = [  # 117c ×1  100.txt
    ("đại tiện ra máu đỏ tươi", 0, SYM, [], []),
]
GT[274] = [  # 112c ×1  96.txt
    ("chụp cắt lớp vi tính (ct)", 0, LAB, [], []),
    ("tắc hẹp 80% động mạch thận trái", 0, DX, [], ["I70.1"]),
]
GT[278] = [  # 105c ×1  95.txt
    ("gout cấp", 0, DX, [], ["M10"]),
    ("đau các khớp", 0, SYM, [], []),
]


# --------------------------------------------------------------------------
# hạ tầng: tìm needle trong một đoạn văn


def _find_occurrences(norm_low: str, needle_nfc_low: str) -> list[int]:
    """Vị trí mọi lần xuất hiện của needle trong text đã NFC + lower."""
    if set(needle_nfc_low) == {"*"}:
        # tên thuốc bị mask: khớp trọn run dấu sao, không khớp substring bên
        # trong run dài hơn
        return [
            m.start()
            for m in re.finditer(r"\*+", norm_low)
            if m.end() - m.start() == len(needle_nfc_low)
        ]
    out: list[int] = []
    i = 0
    while True:
        j = norm_low.find(needle_nfc_low, i)
        if j < 0:
            return out
        out.append(j)
        i = j + 1


def _split_context(needle: str) -> tuple[str, int, int | None]:
    """Cắt cú pháp `ngữ cảnh [[phần cần lấy]] ngữ cảnh`.

    Trả về (needle đầy đủ để tìm, độ lệch đầu, độ dài phần cần lấy).
    Dùng khi cụm ngắn xuất hiện nhiều chỗ, cần ngữ cảnh để trỏ đúng.
    """
    m = re.search(r"\[\[(.+?)\]\]", needle)
    if not m:
        return needle, 0, None
    full = needle[: m.start()] + m.group(1) + needle[m.end() :]
    pre = normalize(needle[: m.start()])[0]
    core = normalize(m.group(1))[0]
    return full, len(pre), len(core)


def locate(raw: str, needle: str, nth: int, where: str) -> tuple[int, int]:
    """Toạ độ (start, end) của lần xuất hiện thứ `nth` của needle, trên raw.

    `raw` là nguyên văn (có thể ở dạng NFD). Tìm trên bản NFC rồi map về.
    """
    full, pre_len, core_len = _split_context(needle)
    norm, imap = normalize(raw)
    low = norm.lower()
    n = normalize(full)[0].lower()
    starts = _find_occurrences(low, n)
    if len(starts) <= nth:
        raise SystemExit(
            f"{where}: {needle!r} chỉ có {len(starts)} lần xuất hiện, cần index {nth}"
        )
    s0 = starts[nth] + pre_len
    s1 = s0 + (core_len if core_len is not None else len(n))
    a, b = to_raw_span(imap, len(raw), s0, s1)
    want = norm[s0:s1].lower()
    got = normalize(raw[a:b])[0].lower()
    if got != want:
        raise SystemExit(f"{where}: span [{a},{b}] ra {got!r}, cần {want!r}")
    return a, b


def _count_occurrences(block_text: str, needle: str) -> int:
    """Số lần `needle` xuất hiện trong block (đếm trên bản NFC, không phân biệt hoa/thường)."""
    norm = normalize(block_text)[0].lower()
    full = _split_context(needle)[0]
    return len(_find_occurrences(norm, normalize(full)[0].lower()))


def resolve(block_text: str, anns: list[Ann], where: str) -> list[dict]:
    """Nhãn -> entity, toạ độ tính trên block_text.

    `nth = ALL` nghĩa là gán cho mọi lần xuất hiện của needle — dùng khi một
    khái niệm được nhắc lại y nguyên nhiều lần trong cùng block với cùng nhãn.
    """
    out: list[dict] = []
    for needle, nth, typ, asserts, cands in anns:
        idxs = range(_count_occurrences(block_text, needle)) if nth is ALL else (nth,)
        for i in idxs:
            a, b = locate(block_text, needle, i, where)
            out.append(
                {
                    "text": block_text[a:b],
                    "position": [a, b],
                    "type": typ,
                    "assertions": list(asserts),
                    "candidates": list(cands),
                }
            )
    out.sort(key=lambda e: e["position"][0])
    return out


# --------------------------------------------------------------------------
# chiếu ngược ra file


def project(blocks: dict[int, dict], f2b: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """block -> file. Tìm lại needle trong đoạn văn của từng file.

    Không cộng offset vì hai lần xuất hiện của một block có thể lệch ký tự
    (xem docstring module).
    """
    per_file: dict[str, list[dict]] = {}
    for fname, segs in sorted(f2b.items(), key=lambda kv: int(kv[0].split(".")[0])):
        raw = (INPUT_DIR / fname).read_text(encoding="utf-8")
        ents: list[dict] = []
        for seg in sorted(segs, key=lambda s: s["start"]):
            bid = seg["block_id"]
            if bid not in GT:
                continue
            seg_text = raw[seg["start"] : seg["end"]]
            where = f"{fname}[block {bid}]"
            for e in resolve(seg_text, GT[bid], where):
                a = seg["start"] + e["position"][0]
                b = seg["start"] + e["position"][1]
                assert raw[a:b] == e["text"], (where, e, raw[a:b])
                ents.append({**e, "position": [a, b]})
        if ents:
            ents.sort(key=lambda e: e["position"][0])
            per_file[fname] = ents
    return per_file


# --------------------------------------------------------------------------
# kiểm tra


def check(blocks: dict[int, dict]) -> list[str]:
    errs: list[str] = []
    for bid, anns in GT.items():
        if bid not in blocks:
            errs.append(f"block {bid} không tồn tại")
            continue
        ents = resolve(blocks[bid]["text"], anns, f"block {bid}")
        spans = [tuple(e["position"]) for e in ents]
        dup = {s for s in spans if spans.count(s) > 1}
        if dup:
            errs.append(f"block {bid}: span trùng {dup}")
        for e in ents:
            if e["assertions"] and e["type"] not in {DX, DRUG, SYM}:
                errs.append(f"block {bid}: {e['text']!r} loại {e['type']} không được có assertions")
            if e["candidates"] and e["type"] not in {DX, DRUG}:
                errs.append(f"block {bid}: {e['text']!r} loại {e['type']} không được có candidates")
            bad = set(e["assertions"]) - {NEG, FAM, HIST}
            if bad:
                errs.append(f"block {bid}: assertion lạ {bad}")
    return errs


def coverage(blocks: dict[int, dict]) -> dict:
    done = set(GT) | DONE_EMPTY
    tot_c = sum(b["n_chars"] for b in blocks.values())
    done_c = sum(blocks[b]["n_chars"] for b in done if b in blocks)
    return {
        "block_da_gan": len(done),
        "block_tong": len(blocks),
        "ky_tu_da_gan": done_c,
        "ky_tu_tong": tot_c,
        "phu_ky_tu": round(done_c / max(1, tot_c), 4),
        "entity": sum(len(v) for v in GT.values()),
    }


def expand_share(blocks: dict[int, dict]) -> None:
    """Áp SHARE: nạp nhãn của block gốc vào block chia sẻ tiền tố. Sửa GT tại chỗ.

    Chỉ nhận nhãn nằm trọn trong `n` ký tự tiền tố. Nhãn của block chia sẻ đã
    khai tay (phần đuôi riêng) được giữ và cộng thêm.
    """
    for bid, (src, n) in sorted(SHARE.items()):
        if src not in GT:
            raise SystemExit(f"SHARE[{bid}]: block gốc {src} chưa có nhãn")
        a = unicodedata.normalize("NFC", blocks[src]["text"])[:n]
        b = unicodedata.normalize("NFC", blocks[bid]["text"])[:n]
        if a != b:
            i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
            raise SystemExit(
                f"SHARE[{bid}] = ({src}, {n}): tiền tố lệch ở ký tự {i}: "
                f"{a[max(0,i-25):i+15]!r} vs {b[max(0,i-25):i+15]!r}"
            )
        # `n` đo trên bản NFC, nên phải xét vị trí nhãn cũng trên bản NFC
        # (`locate` trả toạ độ bản thô — hai hệ lệch nhau ở 20 file NFD).
        norm_src = normalize(blocks[src]["text"])[0]
        low = norm_src.lower()
        inherited: list[Ann] = []
        for ann in GT[src]:
            needle, nth = ann[0], ann[1]
            full, pre_len, core_len = _split_context(needle)
            nn = normalize(full)[0].lower()
            occ = _find_occurrences(low, nn)
            span = core_len if core_len is not None else len(nn)
            if nth is ALL:
                # nhãn ALL: chỉ thừa hưởng nếu MỌI lần xuất hiện đều nằm trong
                # tiền tố; nếu không thì block chia sẻ có thêm lần xuất hiện
                # mới ở đuôi mà ta chưa xét ngữ cảnh -> để gán tay.
                if all(o + pre_len + span <= n for o in occ) and _count_occurrences(
                    blocks[bid]["text"], needle
                ) == len(occ):
                    inherited.append(ann)
                continue
            end = occ[nth] + pre_len + span
            if end <= n:
                inherited.append(ann)
        GT[bid] = inherited + GT.get(bid, [])


def load_blocks() -> tuple[dict[int, dict], dict[str, list[dict]]]:
    blocks = {b["block_id"]: b for b in json.loads(BLOCKS.read_text(encoding="utf-8"))}
    f2b = json.loads(F2B.read_text(encoding="utf-8"))
    return blocks, f2b


def show(bid: int) -> None:
    blocks, _ = load_blocks()
    b = blocks[bid]
    print(f"=== block {bid} | {b['n_chars']} ký tự | xuất hiện {b['n_occurrences']} lần ===")
    print(f"file: {', '.join(s['file'] for s in b['spans'])}")
    nfc = unicodedata.normalize("NFC", b["text"])
    print("-" * 70)
    print(nfc)
    print("-" * 70)


def main() -> None:
    blocks, f2b = load_blocks()
    expand_share(blocks)
    errs = check(blocks)
    if errs:
        for e in errs:
            print(" !", e)
        raise SystemExit(f"{len(errs)} lỗi nhãn")

    per_file = project(blocks, f2b)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for fname, ents in per_file.items():
        (OUT_DIR / f"{Path(fname).stem}.json").write_text(
            json.dumps(ents, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    cov = coverage(blocks)
    print("=== gán nhãn cấp block ===")
    for k, v in cov.items():
        print(f"  {k:14s} {v}")
    kinds: dict[str, int] = {}
    for ents in per_file.values():
        for e in ents:
            kinds[e["type"]] = kinds.get(e["type"], 0) + 1
    print(f"  chiếu ra       {len(per_file)} file, {sum(len(v) for v in per_file.values())} entity")
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"    {k:22s} {v}")


def occ_report(bid: int, needles: list[str]) -> None:
    """Đếm số lần xuất hiện của từng needle trong một block, kèm ngữ cảnh.

    Dùng TRƯỚC khi viết nhãn để chọn `nth` đúng, thay vì thử-sai qua lỗi.
    """
    blocks = load_blocks()[0]
    text = blocks[bid]["text"]
    norm = normalize(text)[0]
    low = norm.lower()
    for needle in needles:
        full, pre_len, core_len = _split_context(needle)
        nn = normalize(full)[0].lower()
        occ = _find_occurrences(low, nn)
        print(f"{needle!r}: {len(occ)} lần")
        for i, o in enumerate(occ):
            s = o + pre_len
            e = s + (core_len if core_len is not None else len(nn))
            print(f"    [{i}] …{norm[max(0, s - 45):s]}«{norm[s:e]}»{norm[e:e + 45]}…")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--show":
        show(int(sys.argv[2]))
    elif len(sys.argv) > 3 and sys.argv[1] == "--occ":
        occ_report(int(sys.argv[2]), sys.argv[3:])
    else:
        main()
