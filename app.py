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


# =========================================================
# CSV関連
# =========================================================

def get_csv_files():
    return sorted(glob.glob(os.path.join(DATA_DIR, "*_operation.csv")))


def load_data(file_path):
    df = pd.read_csv(file_path, encoding="utf-8-sig")

    df["実行日時"] = pd.to_datetime(df["実行日時"])
    df["対象開始日時"] = pd.to_datetime(df["対象開始日時"])
    df["対象終了日時"] = pd.to_datetime(df["対象終了日時"])
    df["日付"] = pd.to_datetime(df["日付"])

    return df


def get_year_month_from_file(file_path):
    file_name = os.path.basename(file_path)
    year = int(file_name[0:4])
    month = int(file_name[5:7])
    return year, month


def get_previous_month_csv_path(selected_file):
    year, month = get_year_month_from_file(selected_file)

    if month == 1:
        previous_year = year - 1
        previous_month = 12
    else:
        previous_year = year
        previous_month = month - 1

    previous_file_name = f"{previous_year}_{previous_month:02d}_operation.csv"
    return os.path.join(DATA_DIR, previous_file_name)


def load_current_and_previous_month_data(selected_file):
    file_paths = [selected_file]

    previous_file = get_previous_month_csv_path(selected_file)

    if os.path.exists(previous_file):
        file_paths.append(previous_file)

    df_list = []

    for file_path in file_paths:
        df_list.append(load_data(file_path))

    base_df = pd.concat(df_list, ignore_index=True)
    base_df = calculate_metrics(base_df)

    return base_df


# =========================================================
# 計算処理
# =========================================================

def calculate_metrics(df):
    df["停止時間_分"] = df["計画時間_分"] - df["稼働時間_分"]

    df["稼働率_%"] = (
        df["稼働時間_分"] / df["計画時間_分"] * 100
    )

    df["想定との差_%"] = (
        df["稼働率_%"] - df["想定稼働率_%"]
    )

    return df


def calculate_rate_summary(df, group_cols):
    summary_df = df.groupby(group_cols).agg(
        計画時間_分=("計画時間_分", "sum"),
        稼働時間_分=("稼働時間_分", "sum"),
        想定稼働時間_分=("想定稼働時間_分", "sum"),
        停止時間_分=("停止時間_分", "sum"),
    ).reset_index()

    summary_df["稼働率_%"] = (
        summary_df["稼働時間_分"] / summary_df["計画時間_分"] * 100
    )

    summary_df["想定稼働率_%"] = (
        summary_df["想定稼働時間_分"] / summary_df["計画時間_分"] * 100
    )

    summary_df["想定との差_%"] = (
        summary_df["稼働率_%"] - summary_df["想定稼働率_%"]
    )

    return summary_df


def create_graph_data(summary_df, id_vars):
    graph_df = summary_df.rename(
        columns={"稼働率_%": "実績稼働率_%"}
    )

    return graph_df.melt(
        id_vars=id_vars,
        value_vars=["実績稼働率_%", "想定稼働率_%"],
        var_name="区分",
        value_name="稼働率_%"
    )


def create_rate_line_chart(graph_df, x_col, color_col, title, x_title):
    fig = px.line(
        graph_df,
        x=x_col,
        y="稼働率_%",
        color=color_col,
        line_dash="区分",
        markers=True,
        title=title
    )

    fig.update_yaxes(
        range=[0, 100],
        title="稼働率_%"
    )

    fig.update_xaxes(
        title=x_title
    )

    return fig


# =========================================================
# CSV選択
# =========================================================

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

weekly_base_df = load_current_and_previous_month_data(selected_file)

selected_year, selected_month = get_year_month_from_file(selected_file)

selected_month_start = pd.Timestamp(
    year=selected_year,
    month=selected_month,
    day=1
)

next_month_start = selected_month_start + pd.DateOffset(months=1)
previous_month_start = selected_month_start - pd.DateOffset(months=1)

# 日別は選択月だけに限定
df = df[
    (df["日付"] >= selected_month_start)
    & (df["日付"] < next_month_start)
]

st.sidebar.write("選択中ファイル")
st.sidebar.code(selected_file)


# =========================================================
# フィルター
# =========================================================

lines = ["すべて"] + sorted(df["ライン"].unique().tolist())
selected_line = st.sidebar.selectbox("ライン選択", lines)

if selected_line != "すべて":
    df = df[df["ライン"] == selected_line]
    weekly_base_df = weekly_base_df[weekly_base_df["ライン"] == selected_line]

machines = ["すべて"] + sorted(df["設備名"].unique().tolist())
selected_machine = st.sidebar.selectbox("設備選択", machines)

if selected_machine != "すべて":
    df = df[df["設備名"] == selected_machine]
    weekly_base_df = weekly_base_df[weekly_base_df["設備名"] == selected_machine]


if df.empty:
    st.warning("選択条件に一致するデータがありません。")
    st.stop()


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
# 設備別 日別稼働率推移
# =========================================================

st.subheader("設備別 日別稼働率推移：実績 vs 想定")

machine_daily_summary = calculate_rate_summary(
    df,
    ["日付", "設備ID", "設備名"]
)

machine_daily_graph_df = create_graph_data(
    machine_daily_summary,
    ["日付", "設備ID", "設備名"]
)

machine_daily_fig = create_rate_line_chart(
    machine_daily_graph_df,
    x_col="日付",
    color_col="設備名",
    title="設備別 日別稼働率推移",
    x_title="日付"
)

machine_daily_fig.update_xaxes(
    dtick="D1",
    tickformat="%m/%d",
    title="日付"
)

st.plotly_chart(machine_daily_fig, width="stretch")


# =========================================================
# ライン別 日別稼働率推移
# =========================================================

st.subheader("ライン別 日別稼働率推移：実績 vs 想定")

line_daily_summary = calculate_rate_summary(
    df,
    ["日付", "ライン"]
)

line_daily_graph_df = create_graph_data(
    line_daily_summary,
    ["日付", "ライン"]
)

line_daily_fig = create_rate_line_chart(
    line_daily_graph_df,
    x_col="日付",
    color_col="ライン",
    title="ライン別 日別稼働率推移",
    x_title="日付"
)

line_daily_fig.update_xaxes(
    dtick="D1",
    tickformat="%m/%d",
    title="日付"
)

st.plotly_chart(line_daily_fig, width="stretch")


# =========================================================
# 週別稼働率推移
# =========================================================

st.subheader("週別 稼働率推移：実績 vs 想定")

weekly_df = weekly_base_df.copy()

# 週別は先月分 + 今月分のみ対象
weekly_df = weekly_df[
    (weekly_df["日付"] >= previous_month_start)
    & (weekly_df["日付"] < next_month_start)
]

weekly_df["週開始日"] = weekly_df["日付"] - pd.to_timedelta(
    weekly_df["日付"].dt.weekday,
    unit="D"
)

weekly_df["週終了日"] = weekly_df["週開始日"] + pd.Timedelta(days=6)

# 完了した週だけ表示
latest_date = weekly_df["日付"].max()
weekly_df = weekly_df[weekly_df["週終了日"] < latest_date]

if weekly_df.empty:
    st.info("週次稼働率を表示するには、完了した1週間分のデータが必要です。")
else:
    st.markdown("#### 設備別 週別稼働率推移")

    machine_weekly_summary = calculate_rate_summary(
        weekly_df,
        ["週開始日", "設備ID", "設備名"]
    )

    machine_weekly_graph_df = create_graph_data(
        machine_weekly_summary,
        ["週開始日", "設備ID", "設備名"]
    )

    machine_weekly_fig = create_rate_line_chart(
        machine_weekly_graph_df,
        x_col="週開始日",
        color_col="設備名",
        title="設備別 週別稼働率推移",
        x_title="週開始日"
    )

    machine_weekly_fig.update_xaxes(
        tickformat="%m/%d",
        title="週開始日"
    )

    st.plotly_chart(machine_weekly_fig, width="stretch")

    st.markdown("#### ライン別 週別稼働率推移")

    line_weekly_summary = calculate_rate_summary(
        weekly_df,
        ["週開始日", "ライン"]
    )

    line_weekly_graph_df = create_graph_data(
        line_weekly_summary,
        ["週開始日", "ライン"]
    )

    line_weekly_fig = create_rate_line_chart(
        line_weekly_graph_df,
        x_col="週開始日",
        color_col="ライン",
        title="ライン別 週別稼働率推移",
        x_title="週開始日"
    )

    line_weekly_fig.update_xaxes(
        tickformat="%m/%d",
        title="週開始日"
    )

    st.plotly_chart(line_weekly_fig, width="stretch")


# =========================================================
# ライン別集計
# =========================================================

st.subheader("ライン別 稼働率")

line_summary = calculate_rate_summary(
    df,
    ["ライン"]
)

st.dataframe(line_summary, width="stretch")


# =========================================================
# 設備別集計
# =========================================================

st.subheader("設備別 稼働率")

machine_summary = calculate_rate_summary(
    df,
    ["設備ID", "設備名"]
)

st.dataframe(machine_summary, width="stretch")


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

st.dataframe(reason_summary, width="stretch")

reason_fig = px.line(
    reason_summary,
    x="停止理由",
    y="停止時間_分",
    markers=True,
    title="停止理由別 停止時間"
)

st.plotly_chart(reason_fig, width="stretch")


# =========================================================
# アラート表示
# =========================================================

st.subheader("稼働率アラート")

alert_df = machine_summary[machine_summary["想定との差_%"] < 0]

if alert_df.empty:
    st.success("想定稼働率を下回っている設備はありません。")
else:
    st.warning("想定稼働率を下回っている設備があります。")
    st.dataframe(alert_df, width="stretch")


# =========================================================
# 元データ表示
# =========================================================

with st.expander("元データを確認する"):
    st.dataframe(df, width="stretch")