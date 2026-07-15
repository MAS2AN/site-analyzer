"""
平面検討図 SVGジェネレーター（医療施設計画論準拠）
────────────────────────────────────────────────────────────────
Notes on Hospital Building（工学院大学 医療・福祉建築研究会）の
チェックリスト・評価軸を踏まえた設計チェックポイントを、
SVGのtitleタグ（ホバーヒント）として各室に付与する。

フロア構成:
  右端  : コアゾーン（EV・階段・PS等）― 全フロア同一位置
  中央横: 廊下帯（CORR_W m 幅）
  北/南 : 通常諸室（廊下両側に面積均等振り分け）

廊下幅:
  2.4 m — 建基法施行令第119条（病院の患者用廊下1.8m以上）を満たした上で、
           Notes on Hospital Building Vol.05 E.2「動線」CLの推奨値。
"""
import math
import re
from typing import Dict, List, Optional, Tuple

# ── 定数 ────────────────────────────────────────────────────────
SCALE      = 22      # px/m
CORR_W     = 2.4     # 廊下幅 (m) — 病院推奨値（施行令第119条：1.8m以上）
CORE_W     = 5.0     # コアゾーン標準幅 (m)
MIN_ROOM_W = 2.0     # 室の最小幅 (m)
FONT       = "Noto Sans JP, sans-serif"

# ── 部門分類キーワード ───────────────────────────────────────────
# Notes on Hospital Building のCL分類に対応
_DEPT_KEYWORDS: Dict[str, List[str]] = {
    "outpatient": [
        "外来", "待合", "受付", "診察", "処置", "化学療法", "救急", "外来事務",
        "採血", "問診", "相談室", "クリニック", "産科", "婦人科", "小児科",
        "整形", "泌尿器", "眼科", "耳鼻", "皮膚科", "精神科", "歯科",
    ],
    "nursing": [
        "病室", "病棟", "個室", "多床", "ナースステーション", "NS", "看護",
        "スタッフ", "準備室", "処置室", "汚物", "リネン庫", "デイルーム",
        "緩和", "ICU", "HCU", "CCU", "NICU", "GCU", "SCU", "MFICU",
    ],
    "clinical": [
        "手術", "検査", "放射線", "内視鏡", "透析", "リハビリ", "分娩", "X線",
        "CT", "MRI", "RI", "核医学", "心カテ", "血管造影", "生理検査",
        "検体", "病理", "解剖", "霊安", "健診",
    ],
    "management": [
        "薬剤", "調剤", "中材", "中央材料", "栄養", "厨房", "給食",
        "倉庫", "事務", "医局", "会議", "研修", "更衣", "廃棄", "清掃",
        "リネン", "ボイラー", "電気室", "機械室", "情報", "ME", "SPD",
    ],
}

_CORE_KEYWORDS = (
    "EV", "エレベーター", "昇降機", "階段", "EL", "PS",
    "DS", "CUP", "シャフト",
)

# ── カラーパレット ───────────────────────────────────────────────
C: Dict[str, str] = {
    "bg":         "#FFFFFF",
    "corr":       "#FBF8F0",   # 廊下：アイボリー
    "core":       "#C8D8F0",   # コア（EV・階段）：薄青
    "outpatient": "#E2F3E2",   # 外来：薄緑
    "nursing":    "#E2EEFF",   # 病棟：薄コバルト
    "clinical":   "#FFF0E0",   # 中央診療：薄橙
    "management": "#F5EFDF",   # 管理：薄茶
    "other":      "#EAF4E8",   # 未分類
    "wall":       "#3D5C3C",
    "dim":        "#8B7355",
    "text":       "#2C3E35",
    "sub":        "#5A7A5A",
}

# ── Notes CLヒント辞書 ────────────────────────────────────────────
# 室名キーワード → 設計チェックポイント（Notes Vol + CL番号）
_CL_HINTS: List[Tuple[str, str]] = [
    ("待合",           "A.2共通（待合）: 車椅子回転スペース確保（08身体）/ 死角のない見通し（03安全）"),
    ("受付",           "A.1外来事務: カウンター高さ1,050mmと700mm両高さ設置（08身体）"),
    ("診察",           "A.3共通: 患者の視線・プライバシーへの配慮（04プラ）/ 採光確保（06環境）"),
    ("処置",           "A.3共通: 感染管理—清潔/不潔ゾーン分離（03安全）/ 手洗い設備隣接（01医療）"),
    ("化学療法",       "A.4化学療法: 個別ブースのプライバシー確保（04プラ）/ 1床あたり自然採光（05快適）"),
    ("救急",           "A.5救急外来: 救急車動線と一般外来動線の分離（10業務）/ 初療室への直接搬入（01医療）"),
    ("手術",           "B.5手術部門: 清潔/準清潔/汚染ゾーン分離（03安全）/ 患者搬送動線と器材搬送動線の分離（10業務）"),
    ("内視鏡",         "B.3内視鏡: 洗浄・消毒室の専用スペース確保（01医療）/ 換気設備（06環境）"),
    ("放射線",         "B.8放射線治療: 遮蔽計画の専門家確認必須（03安全）/ 将来機器更新スペース（11成長）"),
    ("MRI",           "B.4画像診断: 搬入開口部の確保（11成長・B.4.4）/ 磁気シールド（03安全）"),
    ("CT",            "B.4画像診断: 造影剤使用時の処置スペース（01医療）/ 被ばく管理区域設定（03安全）"),
    ("リハビリ",       "B.6リハビリ: 天井高3m以上確保（09設備）/ PT/OT/ST訓練室分離（01医療）"),
    ("透析",           "B.7人工透析: 給排水2系統確保（09設備）/ 患者間プライバシー（04プラ）"),
    ("ナースステーション", "C.1病棟（一般）: 全病室への視認性確保（01医療）/ カウンター高さと見通し（10業務）"),
    ("NS",            "C.1病棟（一般）: 全病室への視認性確保（01医療）/ カウンター高さと見通し（10業務）"),
    ("病室",           "C.1病棟（一般）: 窓面積（採光）確保（06環境）/ ベッドサイドの手洗い（01医療）"),
    ("個室",          "C.1病棟（一般）: 感染症対応—前室設置検討（03安全）/ プライバシー確保（04プラ）"),
    ("多床",           "C.1病棟（一般）: ベッド間隔1.5m以上確保（01医療）/ カーテンによるプライバシー（04プラ）"),
    ("ICU",           "C.10集中治療病棟: ベッド1床あたり25～30㎡確保（01医療）/ 全床監視可能な配置（10業務）"),
    ("NICU",          "C.11集中治療病棟: 照度調整機能付き照明（06環境）/ 親の面会スペース確保（02生活）"),
    ("緩和ケア",       "C.8緩和ケア病棟: 個室化・浴室隣接（04プラ）/ 家族滞在スペース（02生活）"),
    ("分娩",          "B.5/C.5産科: 緊急帝王切開時の手術室への搬送動線（01医療）"),
    ("薬剤",          "D.1薬剤部: 調剤室の内部動線（調剤→監査→払出し）（10業務）/ 毒劇薬保管（03安全）"),
    ("中材",          "D.2中央材料部: 汚染側→洗浄→滅菌→清潔側の一方向動線（01医療）"),
    ("栄養",          "D.3栄養管理部: 食材搬入動線と配膳車動線の分離（10業務）/ 廃棄物動線（03安全）"),
    ("厨房",          "D.3栄養管理部: HACCPに対応した清潔・準清潔ゾーン分離（03安全）"),
    ("倉庫",          "D.5中央倉庫: 物流動線の一元化（10業務）/ SPD対応搬入口（11成長）"),
    ("霊安",          "B.1検体/霊安: 専用動線確保（外来患者との交差回避）（04プラ）"),
    ("待合",          "E.7共生デザイン: 多様な座席タイプ（固定・可動・ソファ）混在（08身体）"),
    ("EV",            "E.1成長と変化: ストレッチャー対応（1,400×2,400mm以上）（08身体）/ 非常時電源確保（E.6BCP）"),
    ("エレベーター",   "E.1成長と変化: ストレッチャー対応（1,400×2,400mm以上）（08身体）"),
    ("階段",          "E.4安全安心: 手すり両側設置（08身体）/ 避難経路確保（03安全）"),
]


def _get_dept(name: str) -> str:
    """室名から部門種別を返す。"""
    if any(kw in name for kw in _CORE_KEYWORDS):
        return "core"
    for dept, keywords in _DEPT_KEYWORDS.items():
        if any(kw in name for kw in keywords):
            return dept
    return "other"


def _get_cl_hint(name: str) -> Optional[str]:
    """室名に対応するNotes CLヒントを返す。"""
    for keyword, hint in _CL_HINTS:
        if keyword in name:
            return hint
    return None


# ── パース ──────────────────────────────────────────────────────

def parse_rooms(text: str) -> List[Dict]:
    """
    テキスト → 諸室リスト
    書式: 室名 面積㎡（1行1室、# 行はコメント）
    """
    rooms = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"(.+?)\s+([\d.]+)", line)
        if not m:
            continue
        name = m.group(1).strip()
        area = float(m.group(2))
        dept = _get_dept(name)
        rooms.append({
            "name":     name,
            "area":     area,
            "is_core":  dept == "core",
            "dept":     dept,
            "cl_hint":  _get_cl_hint(name),
        })
    return rooms


# ── フロア振り分け ───────────────────────────────────────────────

def _distribute(rooms: List[Dict], n_floors: int) -> Dict[int, List[Dict]]:
    """
    コア室: 全フロアに複製（縦動線は全階同一位置）
    通常室: 面積均等になるよう降順グリーディーで振り分け
    """
    cores   = [r for r in rooms if r["is_core"]]
    normals = sorted(
        [r for r in rooms if not r["is_core"]],
        key=lambda r: r["area"], reverse=True,
    )

    floor_rooms: Dict[int, List[Dict]] = {f: list(cores) for f in range(1, n_floors + 1)}
    floor_total: Dict[int, float]      = {f: 0.0       for f in range(1, n_floors + 1)}

    for r in normals:
        f = min(floor_total, key=floor_total.get)
        floor_rooms[f].append(r)
        floor_total[f] += r["area"]

    return floor_rooms


# ── 1フロア配置 ─────────────────────────────────────────────────

def _layout(
    rooms: List[Dict], W: float, D: float
) -> Tuple[List[Dict], float]:
    """
    ダブルロード廊下型で諸室を配置する。
    戻り値: (placed_list, corr_y)
      placed_list: [{"room": dict, "x", "y", "w", "h"}, ...]
      corr_y     : 廊下の y 座標 (m)
    """
    placed: List[Dict] = []
    cores   = [r for r in rooms if r["is_core"]]
    normals = [r for r in rooms if not r["is_core"]]

    # ── コアゾーン（右端・縦一列）──
    cw = min(CORE_W, W * 0.28) if cores else 0.0
    if cw > 0:
        total_h_raw = sum(max(r["area"] / cw, 1.5) for r in cores)
        scale_h     = min(1.0, D / total_h_raw) if total_h_raw > 0 else 1.0
        cy_cur      = 0.0
        for r in cores:
            h = max(r["area"] / cw, 1.5) * scale_h
            placed.append({"room": r, "x": W - cw, "y": cy_cur, "w": cw, "h": h})
            cy_cur += h

    # ── 廊下 y 座標 ──
    uw     = W - cw           # コアを除いた利用幅
    corr_y = D / 2 - CORR_W / 2

    # ── 通常室を南北に振り分け ──
    total  = sum(r["area"] for r in normals)
    target = total / 2

    north: List[Dict] = []
    south: List[Dict] = []
    acc = 0.0
    for r in sorted(normals, key=lambda r: r["area"], reverse=True):
        if acc < target:
            north.append(r)
            acc += r["area"]
        else:
            south.append(r)

    north_h = corr_y
    south_h = D - corr_y - CORR_W

    _strip(north, 0.0, 0.0,              uw, north_h, placed)
    _strip(south, 0.0, corr_y + CORR_W,  uw, south_h, placed)

    return placed, corr_y


def _strip(
    rooms: List[Dict],
    ox: float, oy: float, sw: float, sh: float,
    placed: List[Dict],
) -> None:
    """ゾーン内に室を配置（幅不足なら2行に折り返す）"""
    if not rooms or sw <= 0 or sh <= 0:
        return
    avg_w = sw / len(rooms)
    if avg_w < MIN_ROOM_W * 1.4 and len(rooms) > 2:
        sorted_r = sorted(rooms, key=lambda r: r["area"], reverse=True)
        row1 = sorted_r[0::2]
        row2 = sorted_r[1::2]
        _row(row1, ox, oy,          sw, sh / 2, placed)
        _row(row2, ox, oy + sh / 2, sw, sh / 2, placed)
    else:
        _row(rooms, ox, oy, sw, sh, placed)


def _row(
    rooms: List[Dict],
    ox: float, oy: float, rw: float, rh: float,
    placed: List[Dict],
) -> None:
    """1行に面積比で横並び配置"""
    if not rooms:
        return
    total = sum(r["area"] for r in rooms)
    x = ox
    for r in rooms:
        w = (r["area"] / total) * rw
        placed.append({"room": r, "x": x, "y": oy, "w": w, "h": rh})
        x += w


# ── SVGレンダリング ──────────────────────────────────────────────

def _t(
    x: float, y: float, text: str,
    sz: int = 10, bold: bool = False,
    anchor: str = "middle", col: str = None,
    italic: bool = False,
) -> str:
    col = col or C["text"]
    fw  = "bold"   if bold   else "normal"
    fs  = "italic" if italic else "normal"
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-size="{sz}" font-weight="{fw}" font-style="{fs}" '
        f'fill="{col}">{text}</text>'
    )


def _render(
    placed: List[Dict],
    corr_y: float,
    W: float, D: float,
    floor_num: int,
    address: str = "",
) -> str:
    S               = SCALE
    PAD_L, PAD_T    = 30, 52
    PAD_R, PAD_B    = 20, 50   # 下余白を増やして凡例スペース確保
    svg_w           = int(W * S) + PAD_L + PAD_R
    svg_h           = int(D * S) + PAD_T + PAD_B

    def px(v: float) -> float: return PAD_L + v * S
    def py(v: float) -> float: return PAD_T + v * S

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{svg_w}" height="{svg_h}" font-family="{FONT}">',
        f'<rect width="{svg_w}" height="{svg_h}" fill="{C["bg"]}"/>',
        _t(PAD_L, 18, f"{floor_num}F  平面検討図（医療施設計画論準拠）", sz=12, bold=True, anchor="start"),
        _t(PAD_L, 34, address, sz=9, anchor="start", col="#888888"),
        _t(PAD_L, 46, f"廊下幅 {CORR_W}m ｜ Notes on Hospital Building CL適用", sz=8, anchor="start", col="#AAAAAA"),
    ]

    # 廊下帯（2.4m）
    lines += [
        f'<rect x="{px(0):.1f}" y="{py(corr_y):.1f}" '
        f'width="{W * S:.1f}" height="{CORR_W * S:.1f}" '
        f'fill="{C["corr"]}" stroke="{C["wall"]}" stroke-width="0.5"/>',
        _t(px(W / 2), py(corr_y + CORR_W / 2) + 4,
           f"廊　下  {CORR_W}m", sz=8, col="#999999"),
    ]

    # 諸室
    for pr in placed:
        x, y, w, h = pr["x"], pr["y"], pr["w"], pr["h"]
        dept = pr["room"]["dept"]
        col  = C.get(dept, C["other"])
        cl_hint = pr["room"].get("cl_hint") or ""

        # title要素（ホバーでCLヒントを表示）
        title_tag = f"<title>{pr['room']['name']} {pr['room']['area']:.0f}㎡\n{cl_hint}</title>" if cl_hint else ""

        lines.append(
            f'<rect x="{px(x):.1f}" y="{py(y):.1f}" '
            f'width="{max(w * S - 1, 2):.1f}" '
            f'height="{max(h * S - 1, 2):.1f}" '
            f'fill="{col}" stroke="{C["wall"]}" stroke-width="1.2">'
            f'{title_tag}</rect>'
        )

        # ラベル（室名 + 面積）
        cx_r = px(x + w / 2)
        cy_r = py(y + h / 2)
        name = pr["room"]["name"]
        area = pr["room"]["area"]

        pix_w = w * S
        fs = max(6, min(10, int(pix_w / max(len(name) * 1.3, 1))))
        max_chars = max(int(pix_w / (fs * 0.62)), 2)
        if len(name) > max_chars:
            name = name[: max_chars - 1] + "…"

        lines += [
            _t(cx_r, cy_r - 3, name, sz=fs, bold=True),
            _t(cx_r, cy_r + fs + 2, f"{area:.0f}㎡", sz=max(fs - 1, 6), col=C["sub"]),
        ]

    # 建物外壁
    lines.append(
        f'<rect x="{px(0):.1f}" y="{py(0):.1f}" '
        f'width="{W * S:.1f}" height="{D * S:.1f}" '
        f'fill="none" stroke="{C["wall"]}" stroke-width="2.5"/>'
    )

    # 北矢印
    na_x = svg_w - 22
    na_y = PAD_T + 20
    lines += [
        f'<polygon points="{na_x},{na_y - 12} {na_x - 5},{na_y + 6} '
        f'{na_x},{na_y + 2} {na_x + 5},{na_y + 6}" fill="{C["text"]}"/>',
        _t(na_x, na_y - 16, "N", sz=8, bold=True),
    ]

    # スケールバー（5m）
    sb_x = PAD_L
    sb_y = svg_h - 32
    sb_p = int(5 * S)
    lines += [
        f'<line x1="{sb_x}" y1="{sb_y}" x2="{sb_x + sb_p}" y2="{sb_y}" '
        f'stroke="{C["dim"]}" stroke-width="1.5"/>',
        f'<line x1="{sb_x}" y1="{sb_y - 3}" x2="{sb_x}" y2="{sb_y + 3}" '
        f'stroke="{C["dim"]}" stroke-width="1.5"/>',
        f'<line x1="{sb_x + sb_p}" y1="{sb_y - 3}" '
        f'x2="{sb_x + sb_p}" y2="{sb_y + 3}" '
        f'stroke="{C["dim"]}" stroke-width="1.5"/>',
        _t(sb_x + sb_p / 2, sb_y - 5, "5m", sz=8, col=C["dim"]),
    ]

    # 部門凡例
    legend_items = [
        ("外来部門",   C["outpatient"]),
        ("病棟部門",   C["nursing"]),
        ("中央診療",   C["clinical"]),
        ("管理サービス", C["management"]),
        ("コア",       C["core"]),
    ]
    lx = PAD_L
    ly = svg_h - 16
    box_sz = 9
    for label, lc in legend_items:
        lines += [
            f'<rect x="{lx}" y="{ly - box_sz}" width="{box_sz}" height="{box_sz}" '
            f'fill="{lc}" stroke="{C["wall"]}" stroke-width="0.8"/>',
            _t(lx + box_sz + 3, ly - 1, label, sz=7, anchor="start", col="#666666"),
        ]
        lx += box_sz + len(label) * 7 + 8

    lines.append("</svg>")
    return "\n".join(lines)


# ── プリセット諸室リスト ─────────────────────────────────────────
PRESET_ROOMS: Dict[str, str] = {
    "外来クリニック（診療所）": """\
# 外来クリニック想定（延べ床 約600〜800㎡）
# Notes on Hospital Building Vol.01 外来部門 A.1〜A.3 参照
受付・外来事務 30
待合 60
診察室 15
診察室 15
診察室 15
処置室 25
検査室 20
相談室 12
化学療法室 40
スタッフルーム 20
倉庫 15
トイレ（患者） 12
トイレ（スタッフ） 8
EV 15
階段 20
""",
    "一般病棟（1ユニット）": """\
# 一般病棟 1看護単位 40床想定
# Notes on Hospital Building Vol.03 病棟部門 C.1 参照
4床室 120
4床室 120
4床室 120
4床室 120
個室 25
個室 25
個室 25
個室 25
ナースステーション 60
スタッフ準備室 20
処置室 25
汚物室 10
リネン庫 10
デイルーム 40
患者浴室・シャワー 20
EV 15
階段 20
""",
    "中央診療部門（検査・手術）": """\
# 中央診療部門想定
# Notes on Hospital Building Vol.02 診療部門 B.1〜B.5 参照
検体検査室 80
生理検査室 60
内視鏡検査室 40
内視鏡洗浄消毒室 20
X線撮影室 40
CT室 60
MRI室 80
手術室 60
手術室 60
手術準備室 30
回復室 50
スタッフ更衣室 25
倉庫 30
EV 15
階段 20
""",
    "管理・サービス部門": """\
# 管理・サービス部門想定
# Notes on Hospital Building Vol.04 D.1〜D.16 参照
薬剤部（調剤室） 60
中央材料部 80
栄養管理部（厨房） 100
ME機器センター 30
倉庫 40
リネン室 25
廃棄物処理室 20
電気室 40
機械室 40
事務管理室 60
医局 50
研修室 40
更衣室（男） 20
更衣室（女） 20
EV 15
階段 20
""",
}


# ── 公開インターフェース ─────────────────────────────────────────

def generate_plans(
    rooms_text: str,
    max_building_area: float,
    est_floors: int,
    site_w: float,
    site_d: float,
    address: str = "",
) -> List[str]:
    """
    メイン関数: 諸室テキスト + ボリューム検討結果 → フロア別SVGリスト

    Parameters
    ----------
    rooms_text        : ユーザー入力テキスト（1行1室: 室名 面積）
    max_building_area : 最大建築面積 (㎡) — site_analyzer の volume_study() から取得
    est_floors        : 概算最大階数
    site_w / site_d   : 敷地幅・奥行 (m) — 建物アスペクト比の算出に使用
    address           : 住所文字列（SVGタイトルに表示）
    """
    rooms = parse_rooms(rooms_text)
    if not rooms:
        return []

    ratio  = site_w / site_d if site_d > 0 else 1.0
    bldg_w = math.sqrt(max_building_area * ratio)
    bldg_d = math.sqrt(max_building_area / ratio)

    floor_map = _distribute(rooms, est_floors)

    svgs: List[str] = []
    for f in sorted(floor_map):
        placed, corr_y = _layout(floor_map[f], bldg_w, bldg_d)
        svgs.append(_render(placed, corr_y, bldg_w, bldg_d, f, address))

    return svgs
