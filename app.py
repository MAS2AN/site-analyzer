"""
敷地法規調査ツール - Streamlit Web UI
起動: python -m streamlit run app.py
"""

import math
import os
import sys
import uuid
from pathlib import Path

import plotly.graph_objects as go
import requests as _req
import streamlit as st

# Streamlit Cloud の Secrets を環境変数に反映（ローカル実行時はスキップ）
for _key in ("REINFOLIB_API_KEY", "GOOGLE_API_KEY"):
    if _key not in os.environ and _key in st.secrets:
        os.environ[_key] = st.secrets[_key]

# analyze_site.py と同じフォルダにある関数をインポート
sys.path.insert(0, str(Path(__file__).parent))
from analyze_site import build_report, geocode, research, volume_study
from shadow_calc import (
    calc_shadows, suggest_height_solar, calc_height_limits,
    road_setback_traces, north_setback_traces,
)
from svg_plan import generate_plans, PRESET_ROOMS

_ROAD_BEARINGS = {
    "南（道路が南側・建物が南向き）": 180,
    "北（道路が北側）": 0,
    "東（道路が東側）": 90,
    "西（道路が西側）": 270,
    "南東": 135, "南西": 225, "北東": 45, "北西": 315,
}

# 3×3 コンパスグリッド定義 [表示ラベル, 度数]、None=中央（敷地）
_COMPASS_GRID = [
    [("↖ 北西", 315), ("↑ 北",  0),   ("↗ 北東",  45)],
    [("← 西",   270), None,            ("→ 東",    90)],
    [("↙ 南西", 225), ("↓ 南",  180),  ("↘ 南東", 135)],
]


def _create_volume_3d(vol: dict, site_w: float, site_d: float) -> go.Figure:
    """ボリューム検討結果を3Dボックスで可視化する。"""
    max_building_area = vol["max_building_area"]
    est_height = vol["est_height"]
    est_floors = vol["est_floors"]

    # 建物の縦横寸法：敷地と同じアスペクト比を維持
    ratio = site_w / site_d if site_d > 0 else 1.0
    bldg_w = math.sqrt(max_building_area * ratio)
    bldg_d = math.sqrt(max_building_area / ratio)
    pad_x = max((site_w - bldg_w) / 2, 0)
    pad_y = max((site_d - bldg_d) / 2, 0)

    x0, x1 = pad_x, pad_x + bldg_w
    y0, y1 = pad_y, pad_y + bldg_d
    h = est_height

    # 8頂点（底面4 + 上面4）
    vx = [x0, x1, x1, x0, x0, x1, x1, x0]
    vy = [y0, y0, y1, y1, y0, y0, y1, y1]
    vz = [0,  0,  0,  0,  h,  h,  h,  h ]

    # 12三角形（面インデックス）
    fi = [0, 0, 4, 4, 0, 0, 2, 3, 1, 1, 0, 0]
    fj = [1, 2, 5, 6, 5, 4, 6, 6, 5, 6, 3, 7]
    fk = [2, 3, 6, 7, 1, 5, 3, 7, 6, 2, 7, 4]

    # ワイヤーフレーム用エッジ（None区切り）
    edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    wx, wy, wz = [], [], []
    for p1, p2 in edges:
        wx += [vx[p1], vx[p2], None]
        wy += [vy[p1], vy[p2], None]
        wz += [vz[p1], vz[p2], None]

    # 寸法表示用オフセット
    dim_off = max(site_w * 0.12, 1.0)
    h_off   = max(site_w * 0.10, 0.8)

    traces = [
        # 敷地（グランドプレーン）
        go.Mesh3d(
            x=[0, site_w, site_w, 0], y=[0, 0, site_d, site_d], z=[0, 0, 0, 0],
            color="#C8B99A", opacity=0.55, name="敷地", showlegend=True, hoverinfo="none",
        ),
        # 敷地境界線
        go.Scatter3d(
            x=[0, site_w, site_w, 0, 0], y=[0, 0, site_d, site_d, 0], z=[0.05]*5,
            mode="lines", line=dict(color="#8B7355", width=4), name="敷地境界",
        ),
        # 建物エンベロープ（半透明）
        go.Mesh3d(
            x=vx, y=vy, z=vz, i=fi, j=fj, k=fk,
            color="#5B8C5A", opacity=0.30, name="建物エンベロープ", showlegend=True, hoverinfo="none",
        ),
        # ワイヤーフレーム
        go.Scatter3d(
            x=wx, y=wy, z=wz,
            mode="lines", line=dict(color="#2C3E35", width=2),
            name="建物輪郭", showlegend=False, hoverinfo="none",
        ),
        # ── 寸法線：敷地幅（手前辺の外側）──
        go.Scatter3d(
            x=[0, site_w], y=[-dim_off, -dim_off], z=[0, 0],
            mode="lines", line=dict(color="#8B7355", width=2, dash="dot"),
            showlegend=False, hoverinfo="none",
        ),
        # 寸法線：高さ（右外側）
        go.Scatter3d(
            x=[x1 + h_off, x1 + h_off], y=[y0, y0], z=[0, h],
            mode="lines", line=dict(color="#3D5C3C", width=2, dash="dot"),
            showlegend=False, hoverinfo="none",
        ),
        # 寸法線：建物幅（手前辺の内側）
        go.Scatter3d(
            x=[x0, x1], y=[y0 - dim_off * 0.5, y0 - dim_off * 0.5], z=[0, 0],
            mode="lines", line=dict(color="#5B8C5A", width=2, dash="dot"),
            showlegend=False, hoverinfo="none",
        ),
        # ── 寸法テキスト ──
        go.Scatter3d(
            x=[site_w / 2,          x1 + h_off * 1.6,  x0 + bldg_w / 2],
            y=[-dim_off * 1.3,      y0,                 y0 - dim_off * 0.6],
            z=[0,                   h / 2,              0],
            mode="text",
            text=[
                f"<b>敷地 {site_w:.1f}×{site_d:.1f} m</b>",
                f"<b>H={h:.1f}m ({est_floors}F)</b>",
                f"建物 {bldg_w:.1f}×{bldg_d:.1f} m",
            ],
            textfont=dict(color="#2C3E35", size=12),
            showlegend=False, hoverinfo="none",
        ),
    ]

    # 各階の水平ライン
    floor_h = h / est_floors if est_floors > 0 else h
    for f in range(1, min(est_floors, 30)):
        fz = f * floor_h
        traces.append(go.Scatter3d(
            x=[x0, x1, x1, x0, x0], y=[y0, y0, y1, y1, y0], z=[fz]*5,
            mode="lines", line=dict(color="#7FAF7E", width=1),
            showlegend=False, hoverinfo="none",
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            xaxis=dict(showticklabels=False, title="", showgrid=False, zeroline=False),
            yaxis=dict(showticklabels=False, title="", showgrid=False, zeroline=False),
            zaxis=dict(title="高さ (m)", ticksuffix="m", tickfont=dict(color="#2C3E35")),
            aspectmode="data",
            bgcolor="#F8F5EE",
            camera=dict(eye=dict(x=1.6, y=-1.6, z=0.9)),
        ),
        paper_bgcolor="#F5F2EB",
        margin=dict(l=0, r=0, t=10, b=0),
        height=450,
        legend=dict(
            x=0.01, y=0.98,
            bgcolor="rgba(245,242,235,0.85)",
            bordercolor="#D4CFC4",
            borderwidth=1,
            font=dict(color="#2C3E35", size=12),
        ),
    )
    return fig

# ─────────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="敷地法規調査ツール",
    page_icon="🏢",
    layout="wide",
)

# ── Google Analytics 4 サーバーサイド（Measurement Protocol）──
def _ga4_event(event_name: str, params: dict | None = None) -> None:
    """GA4 Measurement Protocol でイベントを送信する。失敗しても無視。"""
    ga_id = st.secrets.get("GA_MEASUREMENT_ID", "")
    ga_secret = st.secrets.get("GA_API_SECRET", "")
    if not ga_id or not ga_secret:
        return
    if "ga_client_id" not in st.session_state:
        st.session_state.ga_client_id = str(uuid.uuid4())
    try:
        _req.post(
            "https://www.google-analytics.com/mp/collect",
            params={"measurement_id": ga_id, "api_secret": ga_secret},
            json={
                "client_id": st.session_state.ga_client_id,
                "events": [{"name": event_name, "params": params or {}}],
            },
            timeout=2,
        )
    except Exception:
        pass

# セッション開始時に1回だけ page_view を送信
if "ga_page_viewed" not in st.session_state:
    st.session_state.ga_page_viewed = True
    _ga4_event("page_view")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

/* ── ベース ── */
html, body, .stApp {
    background-color: #F5F2EB !important;
    font-family: 'Noto Sans JP', sans-serif !important;
    color: #2C3E35 !important;
}

/* ── 全テキスト要素に深いグリーンを強制 ── */
p, span, div, label, li, td, th, caption,
.stMarkdown, .stText, .stCaption,
[data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"],
[data-testid="stText"] {
    color: #2C3E35 !important;
}

/* ── サイドバー内テキスト ── */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] li {
    color: #2C3E35 !important;
}

/* ── ステータス・スピナーテキスト ── */
[data-testid="stStatusWidget"] span,
[data-testid="stStatusWidget"] p,
[data-testid="stStatusWidget"] div {
    color: #2C3E35 !important;
}

/* ── サイドバー ── */
section[data-testid="stSidebar"] {
    background-color: #EAE6DC !important;
    border-right: 1px solid #D4CFC4 !important;
}
section[data-testid="stSidebar"] h2 {
    color: #3D5C3C !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    margin-top: 1rem !important;
}

/* ── 見出し ── */
h1 { color: #2C3E35 !important; font-weight: 700 !important; letter-spacing: -0.5px !important; }
h2, h3 { color: #3D5C3C !important; font-weight: 600 !important; }

/* ── フォーム枠 ── */
[data-testid="stForm"] {
    background-color: #FFFFFF !important;
    border: 1px solid #D4CFC4 !important;
    border-radius: 14px !important;
    padding: 1.5rem 1.5rem 1rem !important;
    box-shadow: 0 2px 10px rgba(91,140,90,0.08) !important;
}

/* ── テキスト入力 ── */
.stTextInput > div > div > input {
    background-color: #FAFAF7 !important;
    border: 1.5px solid #C8C3B8 !important;
    border-radius: 8px !important;
    color: #2C3E35 !important;
    font-family: 'Noto Sans JP', sans-serif !important;
}
.stTextInput > div > div > input:focus {
    border-color: #5B8C5A !important;
    box-shadow: 0 0 0 3px rgba(91,140,90,0.15) !important;
}

/* ── 調査開始ボタン ── */
.stFormSubmitButton > button {
    background-color: #5B8C5A !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    letter-spacing: 0.5px !important;
    padding: 0.6rem 2rem !important;
    transition: background-color 0.2s ease !important;
}
.stFormSubmitButton > button:hover {
    background-color: #4A7349 !important;
}

/* ── ダウンロードボタン ── */
.stDownloadButton > button {
    background-color: #F5F2EB !important;
    color: #3D5C3C !important;
    border: 2px solid #5B8C5A !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: background-color 0.2s ease !important;
}
.stDownloadButton > button:hover {
    background-color: #DFF0DE !important;
}

/* ── メトリクスカード ── */
[data-testid="stMetric"] {
    background-color: #FFFFFF !important;
    border: 1px solid #D4CFC4 !important;
    border-radius: 12px !important;
    padding: 1rem 1.2rem !important;
    box-shadow: 0 2px 8px rgba(91,140,90,0.08) !important;
}
[data-testid="stMetricLabel"] {
    color: #7A9E79 !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
}
[data-testid="stMetricValue"] {
    color: #2C3E35 !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
}

/* ── 区切り線 ── */
hr { border-color: #D4CFC4 !important; }

/* ── アラート・info ── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    background-color: #F0EDE5 !important;
    border-left-color: #5B8C5A !important;
}

/* ── ステータスボックス ── */
[data-testid="stStatusWidget"] {
    border-radius: 10px !important;
    border: 1px solid #D4CFC4 !important;
    background-color: #FAFAF7 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🏢 敷地法規調査ツール")
st.caption("住所を入力するだけで、都市計画情報・建築基準法の主要制限をまとめたレポートを自動生成します。")

# ─────────────────────────────────────────────
# 前面道路の方角コンパス（フォーム外・session_state で保持）
# ─────────────────────────────────────────────
if "road_bearing_deg" not in st.session_state:
    st.session_state.road_bearing_deg   = 180
    st.session_state.road_bearing_label = "南"

with st.container():
    st.markdown("**🧭 前面道路の方角**（クリックで選択）")
    st.caption("道路が敷地のどの方角にあるか選択してください")
    _comp_cols_rows = [st.columns([1, 1, 1, 0.05, 2]) for _ in range(3)]
    for ri, row in enumerate(_COMPASS_GRID):
        for ci, cell in enumerate(row):
            with _comp_cols_rows[ri][ci]:
                if cell is None:
                    st.markdown(
                        "<div style='text-align:center;line-height:2.4rem;font-size:1.3rem'>🏢</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    label, deg = cell
                    is_sel = st.session_state.road_bearing_deg == deg
                    if st.button(
                        label,
                        key=f"brg_{deg}",
                        use_container_width=True,
                        type="primary" if is_sel else "secondary",
                    ):
                        st.session_state.road_bearing_deg   = deg
                        st.session_state.road_bearing_label = label.split()[-1]
                        st.rerun()
        # 右側に説明を中央行のみ表示
        if ri == 1:
            with _comp_cols_rows[1][4]:
                sel_lbl = st.session_state.road_bearing_label
                sel_deg = st.session_state.road_bearing_deg
                st.markdown(
                    f"<div style='padding:4px 8px;background:#DFF0DE;border-radius:8px;"
                    f"border:1px solid #5B8C5A;font-size:0.9rem'>"
                    f"✅ <b>{sel_lbl}側</b> に前面道路<br>"
                    f"<span style='color:#666;font-size:0.8rem'>({sel_deg}°)</span></div>",
                    unsafe_allow_html=True,
                )

st.markdown("")  # spacing

# ─────────────────────────────────────────────
# 入力フォーム
# ─────────────────────────────────────────────
with st.form("search_form"):
    address = st.text_input(
        "調査したい住所を入力してください",
        placeholder="例）東京都目黒区目黒2-1-1　または　〒292-0007 千葉県木更津市中島2627-1",
        help="番地まで入力するほど精度が上がります。郵便番号は無視されます。",
    )
    col_sw, col_sd, col_road = st.columns(3)
    with col_sw:
        site_w_input = st.number_input(
            "敷地 幅（m）— 間口 ※任意",
            min_value=0.0, value=0.0, step=0.5, format="%.1f",
            help="前面道路側の寸法。入力するとボリューム検討が表示されます。",
        )
    with col_sd:
        site_d_input = st.number_input(
            "敷地 奥行（m）※任意",
            min_value=0.0, value=0.0, step=0.5, format="%.1f",
        )
    with col_road:
        road_width_input = st.number_input(
            "前面道路幅員（m）※任意",
            min_value=0.0, value=0.0, step=0.5, format="%.1f",
        )
    col_meas_h, col_shadow_t = st.columns(2)
    with col_meas_h:
        meas_h_input = st.selectbox(
            "日影測定面高さ",
            options=["1.5 m（低層住専等）", "4.0 m（その他住居系）", "6.5 m（商業系）"],
            index=0,
        )
    with col_shadow_t:
        shadow_thresh_input = st.selectbox(
            "日影規制 時間数",
            options=["3 時間", "4 時間", "5 時間"],
            index=1,
        )
    submitted = st.form_submit_button("🔍 調査開始", use_container_width=True, type="primary")

# ─────────────────────────────────────────────
# 実行・結果表示
# ─────────────────────────────────────────────
if submitted and address.strip():
    _ga4_event("search")
    # 郵便番号部分（〒xxx-xxxx）を除去
    import re
    clean_address = re.sub(r"[〒\s]*\d{3}-\d{4}\s*", "", address).strip()

    st.divider()

    # ステータス表示（処理中）
    status = st.status("調査中です。しばらくお待ちください...", expanded=True)

    try:
        with status:
            # Step 1: ジオコーディング
            st.write("📍 住所を座標に変換中...")
            geo = geocode(clean_address)
            st.write(f"　緯度 {geo['lat']:.6f} / 経度 {geo['lon']:.6f}　（市区町村コード: {geo['muniCode'] or '未取得'}）")

            # Step 2-3: 都市計画情報の調査
            st.write("🗺️ 国土数値情報（用途地域・容積率・建ぺい率）を照合中...")
            if os.environ.get("GOOGLE_API_KEY"):
                st.write("🤖 Gemini で Web参考情報を収集中...")
            else:
                st.write("🔎 DuckDuckGo で Web参考情報を補完中...")
            zone_info, search_results, gemini_raw = research(clean_address, geo["normalized"], geo)

            # Step 4: レポート生成
            st.write("📄 レポートを生成中...")
            report_md = build_report(clean_address, geo, zone_info, search_results, gemini_raw)

        status.update(label="✅ 調査完了！", state="complete", expanded=False)

        # ─────────────────────────────────────────────
        # 取得サマリー（一番目立つ場所に表示）
        # ─────────────────────────────────────────────
        st.subheader("📊 取得結果サマリー")

        na = "⚠️ 要確認"
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            v = zone_info.get("用途地域", na)
            color = "normal" if zone_info.get("用途地域") else "off"
            st.metric("用途地域", v)
        with col2:
            v = zone_info.get("容積率", na)
            st.metric("指定容積率", v)
        with col3:
            v = zone_info.get("建蔽率", na)
            st.metric("指定建ぺい率", v)
        with col4:
            v = zone_info.get("防火規制", na)
            st.metric("防火規制", v)

        st.divider()

        # ─────────────────────────────────────────────
        # レポート本文（Markdown 表示）
        # ─────────────────────────────────────────────
        st.subheader("📋 詳細レポート")
        st.markdown(report_md)

        st.divider()

        # ─────────────────────────────────────────────
        # ボリューム検討
        # ─────────────────────────────────────────────
        site_w = site_w_input if site_w_input > 0 else None
        site_d = site_d_input if site_d_input > 0 else None
        road_width = road_width_input if road_width_input > 0 else None
        site_area = (site_w * site_d) if (site_w and site_d) else None

        if site_area is not None:
            st.subheader("🏗️ ボリューム検討")
            st.caption("※敷地を正方形で近似した概算値です。前面道路容積率は建基法第52条第2項による。")

            vol = volume_study(zone_info, site_area, road_width)

            if "error" in vol:
                st.warning(vol["error"])
            else:
                # ── メトリクス ──
                vc1, vc2, vc3, vc4 = st.columns(4)
                with vc1:
                    st.metric("最大建築面積", f"{vol['max_building_area']:,.1f} ㎡")
                with vc2:
                    far_label = f"{vol['effective_far_pct']:.0f}%"
                    if vol.get("far_limited_by_road"):
                        far_label += "（道路制限）"
                    st.metric("有効容積率", far_label)
                with vc3:
                    st.metric("最大延べ床面積", f"{vol['max_total_area']:,.1f} ㎡")
                with vc4:
                    st.metric("概算最大階数", f"{vol['est_floors']} 階")

                # ── 計算内訳テーブル ──
                rows = [
                    ("敷地寸法", f"{site_w:.1f} × {site_d:.1f} m", "入力値"),
                    ("敷地面積", f"{site_area:,.1f} ㎡", f"{site_w:.1f} × {site_d:.1f}"),
                    ("建ぺい率", f"{vol['bcr_pct']:.0f}%", "取得値"),
                    ("最大建築面積", f"{vol['max_building_area']:,.1f} ㎡", "敷地面積 × 建ぺい率"),
                    ("指定容積率", f"{vol['far_pct']:.0f}%", "取得値"),
                ]
                if vol.get("road_far_pct") is not None:
                    rows.append((
                        "前面道路容積率",
                        f"{vol['road_far_pct']:.0f}%",
                        f"道路幅員 {road_width}m × {vol['road_multiplier']}",
                    ))
                rows += [
                    ("有効容積率", f"{vol['effective_far_pct']:.0f}%",
                     "指定容積率・前面道路容積率の小さい方"),
                    ("最大延べ床面積", f"{vol['max_total_area']:,.1f} ㎡", "敷地面積 × 有効容積率"),
                    ("概算最大高さ", f"{vol['est_height']} m", f"階数 × {vol['floor_height']}m/階"),
                    ("概算最大階数", f"{vol['est_floors']} 階", "最大延べ床 ÷ 最大建築面積（切り上げ）"),
                ]
                if "abs_height_limit" in vol:
                    rows.append(("絶対高さ制限 ⚠️", vol["abs_height_limit"], vol["abs_height_limited_floors"]))

                import pandas as pd
                df = pd.DataFrame(rows, columns=["項目", "値", "計算根拠"])
                st.dataframe(df, use_container_width=True, hide_index=True)

                if vol.get("far_limited_by_road"):
                    st.warning(
                        f"前面道路幅員 {road_width}m による容積率制限（{vol['road_far_pct']:.0f}%）が"
                        f"指定容積率（{vol['far_pct']:.0f}%）より厳しいため、有効容積率は "
                        f"**{vol['effective_far_pct']:.0f}%** になります。"
                    )
                if "abs_height_limit" in vol:
                    st.warning(
                        f"この用途地域（{vol['zone_name']}）には絶対高さ制限があります。"
                        f"最大 {vol['abs_height_limit']} — 概算階数は {vol['abs_height_limited_floors']} 程度になります。"
                    )

                # ── 3D可視化（ボリューム＋日影＋斜線）──
                st.markdown("**📐 建物エンベロープ・日影・斜線制限（3D）**")
                fig = _create_volume_3d(vol, site_w, site_d)

                bearing_deg = st.session_state.get("road_bearing_deg", 180)
                meas_h_m    = float(meas_h_input.split()[0])
                thresh_h    = int(shadow_thresh_input.split()[0])
                zone_name_v = zone_info.get("用途地域", "")
                road_w      = road_width or 6.0

                ratio    = site_w / site_d if site_d > 0 else 1.0
                bldg_w_c = math.sqrt(vol["max_building_area"] * ratio)
                bldg_d_c = math.sqrt(vol["max_building_area"] / ratio)
                px0      = max((site_w - bldg_w_c) / 2, 0)
                py0      = max((site_d - bldg_d_c) / 2, 0)
                bldg_fp  = [
                    (px0, py0), (px0 + bldg_w_c, py0),
                    (px0 + bldg_w_c, py0 + bldg_d_c), (px0, py0 + bldg_d_c),
                ]

                for t in road_setback_traces(road_w, site_w, site_d, zone_name_v):
                    fig.add_trace(t)
                for t in north_setback_traces(bearing_deg, site_w, site_d, zone_name_v):
                    fig.add_trace(t)
                shadow_res = calc_shadows(
                    bldg_fp, vol["est_height"], meas_h_m,
                    geo["lat"], geo["lon"], bearing_deg, thresh_h, site_w, site_d,
                )
                for t in shadow_res["traces"]:
                    fig.add_trace(t)

                st.caption(
                    f"冬至日 / 測定高 {meas_h_m}m / {thresh_h}時間日影 "
                    "│ 🟠 敷地内日影  🔴 敷地外逸脱  🟡 道路斜線エンベロープ  🟢 北側斜線エンベロープ"
                )
                st.plotly_chart(fig, use_container_width=True)

                # ── 日影判定 ──
                if shadow_res["violation"]:
                    st.error(
                        f"⚠️ **日影規制オーバー**: H={vol['est_height']:.0f}m では "
                        f"{thresh_h}時間日影が敷地外へ **{shadow_res['violation_area_m2']:.0f}㎡** 逸脱します。"
                    )
                    sug_h = suggest_height_solar(
                        bldg_fp, vol["est_height"], meas_h_m,
                        geo["lat"], geo["lon"], bearing_deg, thresh_h, site_w, site_d,
                    )
                    if sug_h > 0:
                        st.info(f"💡 **縮小案: H ≤ {sug_h:.1f}m** なら敷地内に収まります（バイナリサーチ概算）")
                    else:
                        st.warning("H=1m でも日影が逸脱するため、用途地域・建物位置の再検討が必要です。")
                else:
                    st.success(
                        f"✅ **日影OK**: {thresh_h}時間日影は敷地内に収まります "
                        f"（等時間日影面積 {shadow_res['iso_area_m2']:.0f}㎡）"
                    )

                # ── 斜線制限チェック ──
                limits = calc_height_limits(
                    zone_name_v, road_w, site_w, site_d, bldg_w_c, bldg_d_c, bearing_deg,
                )
                if limits:
                    lim_rows = []
                    if limits.get("road_limit_h") is not None:
                        ok = vol["est_height"] <= limits["road_limit_h"]
                        lim_rows.append((
                            "道路斜線", f"勾配 {limits['road_slope']}",
                            f"{limits['road_setback_m']:.1f}m 後退",
                            f"{limits['road_limit_h']:.1f}m",
                            "✅ 適合" if ok else "⚠️ 超過",
                        ))
                    if limits.get("north_limit_h") is not None:
                        ok = vol["est_height"] <= limits["north_limit_h"]
                        lim_rows.append((
                            "北側斜線", f"A={limits['north_rise']}m",
                            f"北端まで {limits['dist_to_north_m']:.1f}m",
                            f"{limits['north_limit_h']:.1f}m",
                            "✅ 適合" if ok else "⚠️ 超過",
                        ))
                    if lim_rows:
                        st.markdown("**📏 斜線制限チェック**")
                        df_lim = pd.DataFrame(
                            lim_rows,
                            columns=["制限種別", "勾配・A値", "距離", "制限高さ", "適合判定"],
                        )
                        st.dataframe(df_lim, use_container_width=True, hide_index=True)

                # ── 平面検討図（医療施設計画論準拠）──
                st.markdown("---")
                st.markdown("**🏥 平面検討図（医療施設計画論準拠）**")
                st.caption(
                    "Notes on Hospital Building（工学院大学 医療・福祉建築研究会）のCLに基づく"
                    "ダブルロード廊下型の概略平面図。各室にカーソルを合わせるとCL設計チェックポイントが表示されます。"
                )

                preset_choice = st.selectbox(
                    "プリセット諸室を選択",
                    ["（空欄 / 手入力）"] + list(PRESET_ROOMS.keys()),
                    key=f"preset_{floor_num if False else 'vol'}",
                )
                default_text = PRESET_ROOMS.get(preset_choice, "")
                rooms_input = st.text_area(
                    "諸室リスト（1行1室：室名 面積㎡）",
                    value=default_text,
                    height=180,
                    help="# から始まる行はコメントとして無視されます。",
                    key="rooms_input_vol",
                )

                if st.button("📐 平面検討図を生成", key="gen_plan_vol"):
                    if rooms_input.strip():
                        svgs = generate_plans(
                            rooms_input,
                            vol["max_building_area"],
                            vol["est_floors"],
                            site_w,
                            site_d,
                            clean_address,
                        )
                        if svgs:
                            for i, svg in enumerate(svgs, 1):
                                st.markdown(f"**{i}F**")
                                import streamlit.components.v1 as components
                                components.html(svg, height=500, scrolling=True)
                        else:
                            st.warning("諸室リストを正しい形式で入力してください（例: 診察室 15）")
                    else:
                        st.info("諸室リストを入力するか、プリセットを選択してください。")

            st.divider()

        # ─────────────────────────────────────────────
        # ダウンロードボタン
        # ─────────────────────────────────────────────
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', clean_address)
        st.download_button(
            label="📥 レポートをダウンロード（Markdown）",
            data=report_md.encode("utf-8"),
            file_name=f"敷地調査_{safe_name}.md",
            mime="text/markdown",
            use_container_width=True,
        )

        # ─────────────────────────────────────────────
        # 注意書き
        # ─────────────────────────────────────────────
        st.info(
            "**免責事項**: このレポートは国土数値情報・Web自動収集による参考情報です。"
            "確認申請・設計判断に使用する際は必ず所管行政庁の窓口で最新情報を確認してください。",
            icon="ℹ️",
        )

    except ValueError as e:
        status.update(label="❌ エラー", state="error")
        st.error(f"住所が見つかりませんでした: {e}\n\n番地まで含めた正確な住所を入力してください。")
    except Exception as e:
        status.update(label="❌ エラー", state="error")
        st.error(f"調査中にエラーが発生しました: {e}")

elif submitted:
    st.warning("住所を入力してください。")

# ─────────────────────────────────────────────
# サイドバー（使い方）
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("📖 使い方")
    st.markdown("""
1. 調査したい敷地の住所を入力
2. **調査開始** ボタンを押す
3. 30秒〜1分程度で結果が表示されます
4. 必要に応じてレポートをダウンロード

---

**取得できる情報**
- 用途地域
- 指定容積率・建ぺい率
- 防火規制（防火・準防火地域）
- 斜線制限・日影規制の適用有無
- 確認申請前チェックリスト
- 窓口確認が必要な条例一覧

---

**⚠️ 注意事項**
- 用途地域・容積率・建ぺい率は **国土数値情報（国土交通省）** から取得した公式データです
- 防火規制・高度地区・条例は Web 検索からの補完情報のため、必ず行政窓口で確認してください
""")

    st.header("🔑 Gemini AI")
    if os.environ.get("GOOGLE_API_KEY"):
        st.success("✅ Gemini API 設定済み\nWeb参考情報の精度が向上しています。")
    else:
        st.markdown("""
`GOOGLE_API_KEY` を設定すると、防火規制・高度地区の
取得精度が向上します。

[Google AI Studio でキー取得](https://aistudio.google.com/apikey)
""")
