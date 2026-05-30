import glob
import os

import pandas as pd
import plotly.express as px
import streamlit as st


DATA_DIR = "data"

st.set_page_config(
    page_title="設備稼働率ダッシュボード",
    layout="wide"
)

st.title("🏭 設備稼働率ダッシュボード")


def get_csv_files():
    return sorted(glob.glob(os.path.join(DATA_DIR, "*_operation.csv")))


def load_data(file_path):
    df = pd.read_csv(file_path, encoding="utf-8-sig")

    df["実行日時"] = pd.to_datetime(df["実行日時"])
    df["対象開始日時"] = pd.to_datetime(df["対象開始日時"])
    df["対象終了日時"] = pd.to_datetime(df["対象終了日時"])
    df["日付"] = pd.to_datetime(df["日付"])

    return df


def calculate_metrics(df):
    # CSV作成側ですでに作っているが、念のため再計算
    df["停止時間_分"] = df["計画時間_分"] - df["稼働時間_分"]

    df["稼働率_%"] = (
        df["稼働時間_分"] / df["計画時間_分"] * 100
    )

    df["想定との差_%"] = (
        df["稼働率_%"] - df["想定稼働率_%"]
    )

    return df


csv_files = get_csv_files()

if not csv_files:
    st.warning("dataフォルダにCSVファイルがありません。")
    st.stop()

selected_file = st.sidebar.selectbox(
    "表示する月のCSVを選択",
    csv_files,
    index=len(csv_files) - 1
)

df = load_data(selected_file)
df = calculate_metrics(df)

st.sidebar.write("選択中ファイル")
st.sidebar.code(selected_file)


# =========================================================
# フィルター
# =========================================================

lines = ["すべて"] + sorted(df["ライン"].unique().tolist())
selected_line = st.sidebar.selectbox("ライン選択", lines)

if selected_line != "すべて":
    df = df[df["ライン"] == selected_line]

machines = ["すべて"] + sorted(df["設備名"].unique().tolist())
selected_machine = st.sidebar.selectbox("設備選択", machines)

if selected_machine != "すべて":
    df = df[df["設備名"] == selected_machine]


# =========================================================
# 全体サマリー
# =========================================================

total_planned_time = df["計画時間_分"].sum()
total_operating_time = df["稼働時間_分"].sum()
total_downtime = df["停止時間_分"].sum()

overall_operation_rate = total_operating_time / total_planned_time * 100

expected_operating_time = df["想定稼働時間_分"].sum()
overall_expected_rate = expected_operating_time / total_planned_time * 100

operation_gap = overall_operation_rate - overall_expected_rate

col1, col2, col3, col4 = st.columns(4)

col1.metric("全体稼働率", f"{overall_operation_rate:.1f}%")
col2.metric("想定稼働率", f"{overall_expected_rate:.1f}%")
col3.metric("想定との差", f"{operation_gap:.1f}%")
col4.metric("総停止時間", f"{int(total_downtime)}分")


# =========================================================
# 日別 稼働率推移グラフ
# =========================================================

st.subheader("日別 稼働率推移：実績 vs 想定")

trend_df = df.groupby(
    ["日付", "設備ID", "設備名"]
).agg(
    計画時間_分=("計画時間_分", "sum"),
    稼働時間_分=("稼働時間_分", "sum"),
    想定稼働時間_分=("想定稼働時間_分", "sum"),
).reset_index()

trend_df["実績稼働率_%"] = (
    trend_df["稼働時間_分"] / trend_df["計画時間_分"] * 100
)

trend_df["想定稼働率_%"] = (
    trend_df["想定稼働時間_分"] / trend_df["計画時間_分"] * 100
)

graph_df = trend_df.melt(
    id_vars=["日付", "設備ID", "設備名"],
    value_vars=["実績稼働率_%", "想定稼働率_%"],
    var_name="区分",
    value_name="稼働率_%"
)

fig = px.line(
    graph_df,
    x="日付",
    y="稼働率_%",
    color="設備名",       # 設備ごとに色分け
    line_dash="区分",    # 実績/想定で線種分け
    markers=True,
    title="設備別 日別稼働率推移"
)

# Y軸を0〜100%で固定
fig.update_yaxes(
    range=[0, 100],
    title="稼働率_%"
)

# X軸は日付単位だけ表示
fig.update_xaxes(
    dtick="D1",
    tickformat="%m/%d",
    title="日付"
)

st.plotly_chart(fig, use_container_width=True)


# =========================================================
# ライン別集計
# =========================================================

st.subheader("ライン別 稼働率")

line_summary = df.groupby("ライン").agg(
    計画時間_分=("計画時間_分", "sum"),
    稼働時間_分=("稼働時間_分", "sum"),
    想定稼働時間_分=("想定稼働時間_分", "sum"),
    停止時間_分=("停止時間_分", "sum"),
).reset_index()

line_summary["稼働率_%"] = (
    line_summary["稼働時間_分"] / line_summary["計画時間_分"] * 100
)

line_summary["想定稼働率_%"] = (
    line_summary["想定稼働時間_分"] / line_summary["計画時間_分"] * 100
)

line_summary["想定との差_%"] = (
    line_summary["稼働率_%"] - line_summary["想定稼働率_%"]
)

st.dataframe(line_summary, use_container_width=True)


# =========================================================
# 設備別集計
# =========================================================

st.subheader("設備別 稼働率")

machine_summary = df.groupby(["設備ID", "設備名"]).agg(
    計画時間_分=("計画時間_分", "sum"),
    稼働時間_分=("稼働時間_分", "sum"),
    想定稼働時間_分=("想定稼働時間_分", "sum"),
    停止時間_分=("停止時間_分", "sum"),
).reset_index()

machine_summary["稼働率_%"] = (
    machine_summary["稼働時間_分"] / machine_summary["計画時間_分"] * 100
)

machine_summary["想定稼働率_%"] = (
    machine_summary["想定稼働時間_分"] / machine_summary["計画時間_分"] * 100
)

machine_summary["想定との差_%"] = (
    machine_summary["稼働率_%"] - machine_summary["想定稼働率_%"]
)

st.dataframe(machine_summary, use_container_width=True)


# =========================================================
# 停止理由ランキング
# =========================================================

st.subheader("停止理由ランキング")

reason_summary = df.groupby("停止理由").agg(
    件数=("停止理由", "count"),
    停止時間_分=("停止時間_分", "sum"),
).reset_index()

reason_summary = reason_summary.sort_values(
    "停止時間_分",
    ascending=False
)

st.dataframe(reason_summary, use_container_width=True)

reason_fig = px.bar(
    reason_summary,
    x="停止理由",
    y="停止時間_分",
    title="停止理由別 停止時間"
)

st.plotly_chart(reason_fig, use_container_width=True)


# =========================================================
# アラート表示
# =========================================================

st.subheader("稼働率アラート")

alert_df = machine_summary[machine_summary["想定との差_%"] < 0]

if alert_df.empty:
    st.success("想定稼働率を下回っている設備はありません。")
else:
    st.warning("想定稼働率を下回っている設備があります。")
    st.dataframe(alert_df, use_container_width=True)


# =========================================================
# 元データ表示
# =========================================================

with st.expander("元データを確認する"):
    st.dataframe(df, use_container_width=True)