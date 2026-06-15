"""
敷地法規調査ツール - Streamlit Web UI
起動: python -m streamlit run app.py
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Streamlit Cloud の Secrets を環境変数に反映（ローカル実行時はスキップ）
for _key in ("REINFOLIB_API_KEY", "GOOGLE_API_KEY"):
    if _key not in os.environ and _key in st.secrets:
        os.environ[_key] = st.secrets[_key]

# analyze_site.py と同じフォルダにある関数をインポート
sys.path.insert(0, str(Path(__file__).parent))
from analyze_site import build_report, geocode, research, volume_study


# ─────────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="敷地法規調査ツール",
    page_icon="🏢",
    layout="wide",
)

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
    submitted = st.form_submit_button("🔍 調査開始", use_container_width=True, type="primary")

# ─────────────────────────────────────────────
# 実行・結果表示
# ─────────────────────────────────────────────
if submitted and address.strip():
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
        # 都市計画 GIS マップ（folium）
        # ─────────────────────────────────────────────
        try:
            import folium
            from streamlit_folium import st_folium
            from analyze_site import ZONE_COLORS

            st.subheader("🗺️ 都市計画 GIS マップ")

            data_src = zone_info.get("_data_source", "A29")
            if data_src == "XKT002":
                st.caption("用途地域ポリゴン: reinfolib XKT002（令和6年度データ） / ベースマップ: 地理院タイル")
            else:
                st.caption("ベースマップ: 地理院タイル　※ reinfolib APIキー未設定のためポリゴン表示なし")

            m = folium.Map(
                location=[geo["lat"], geo["lon"]],
                zoom_start=16,
                tiles="https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png",
                attr='<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank">地理院タイル</a>',
            )

            # 用途地域ポリゴン（XKT002 から取得した GeoJSON features）
            map_features = zone_info.get("_map_features", [])
            if map_features:
                zone_group = folium.FeatureGroup(name="用途地域", show=True)
                for feat in map_features:
                    props = feat.get("properties", {})
                    zname = props.get("use_area_ja", "")
                    bcr   = props.get("u_building_coverage_ratio_ja", "")
                    far   = props.get("u_floor_area_ratio_ja", "")
                    color = ZONE_COLORS.get(zname, "#BBBBBB")
                    tip   = f"{zname}　建ぺい率 {bcr}　容積率 {far}" if zname else ""
                    try:
                        folium.GeoJson(
                            feat,
                            style_function=lambda x, c=color: {
                                "fillColor": c,
                                "color": "#444444",
                                "weight": 0.8,
                                "fillOpacity": 0.45,
                            },
                            tooltip=folium.Tooltip(tip, sticky=False),
                        ).add_to(zone_group)
                    except Exception:
                        pass
                zone_group.add_to(m)

            # 敷地マーカー
            folium.Marker(
                [geo["lat"], geo["lon"]],
                popup=folium.Popup(clean_address, max_width=250),
                icon=folium.Icon(color="red", icon="home", prefix="glyphicon"),
                tooltip="調査敷地",
            ).add_to(m)

            folium.LayerControl().add_to(m)
            st_folium(m, use_container_width=True, height=450, returned_objects=[])

        except ImportError:
            st.info(
                "地図表示には `folium` と `streamlit-folium` が必要です。"
                "`pip install folium streamlit-folium` を実行してください。",
                icon="ℹ️",
            )

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

**📡 データソース**
- 用途地域 → **XKT002（令和6年度）**
- 防火規制 → XKT014 / 地区計画 → XKT023
- 高度利用地区 → XKT024 ← NEW
- APIキー未設定時 → A29（2019年）フォールバック

---

**⚠️ 注意事項**
- 高度地区・日影規制数値は自動取得不可（✕）
- 確認申請・設計判断は必ず行政窓口で確認
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
