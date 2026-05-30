import os
import random
from datetime import datetime, time, timedelta

import jpholiday
import pandas as pd


DATA_DIR = "data"

TOTAL_TIME_MINUTES = 360
BREAK_TIME_MINUTES = 45
FIRST_WORKDAY_START_TIME = time(8, 30)

COLUMNS = [
    "実行日時",
    "対象開始日時",
    "対象終了日時",
    "日付",
    "シフト",
    "ライン",
    "設備ID",
    "設備名",
    "サイクルタイム_分",
    "計画時間_分",
    "想定停止時間_分",
    "想定稼働時間_分",
    "想定稼働率_%",
    "実停止時間_分",
    "稼働時間_分",
    "実績稼働率_%",
    "停止理由",
    "生産数",
    "不良数",
]

MACHINES = [
    {"ライン": "Line-A", "設備ID": "MC-001", "設備名": "切断機", "サイクルタイム_分": 25, "想定停止率_%": 8},
    {"ライン": "Line-A", "設備ID": "MC-002", "設備名": "加工機", "サイクルタイム_分": 36, "想定停止率_%": 10},
    {"ライン": "Line-B", "設備ID": "MC-003", "設備名": "検査機", "サイクルタイム_分": 20, "想定停止率_%": 5},
    {"ライン": "Line-B", "設備ID": "MC-004", "設備名": "包装機", "サイクルタイム_分": 15, "想定停止率_%": 7},
    {"ライン": "Line-C", "設備ID": "MC-005", "設備名": "組立機", "サイクルタイム_分": 20, "想定停止率_%": 12},
    {"ライン": "Line-C", "設備ID": "MC-006", "設備名": "圧着機", "サイクルタイム_分": 22, "想定停止率_%": 9},
]

DOWNTIME_RULES = {
    "なし": (0, 10),
    "チョコ停": (5, 20),
    "段取り替え": (20, 50),
    "材料待ち": (30, 80),
    "設備異常": (60, 120),
    "品質確認": (15, 40),
    "清掃": (10, 30),
}


def get_monthly_csv_path(now: datetime) -> str:
    return os.path.join(DATA_DIR, now.strftime("%Y_%m_operation.csv"))


def prepare_csv_file(file_path: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(file_path):
        pd.DataFrame(columns=COLUMNS).to_csv(
            file_path,
            index=False,
            encoding="utf-8-sig"
        )
        print(f"新規CSVを作成しました: {file_path}")
    else:
        print(f"既存CSVに追記します: {file_path}")


def round_down_to_schedule_time(now: datetime) -> datetime:
    """
    GitHub Actionsの実行遅延対策。
    現在時刻を 0:00 / 6:00 / 12:00 / 18:00 の直近過去時刻に丸める。
    例：
      12:03 → 12:00
      18:08 → 18:00
      00:02 → 00:00
    """
    schedule_hours = [0, 6, 12, 18]

    rounded_hour = max(
        hour for hour in schedule_hours
        if hour <= now.hour
    )

    return now.replace(
        hour=rounded_hour,
        minute=0,
        second=0,
        microsecond=0
    )


def get_target_period(now: datetime) -> tuple[datetime, datetime]:
    target_end = round_down_to_schedule_time(now)
    target_start = target_end - timedelta(hours=6)
    return target_start, target_end


def is_non_workday(target_date) -> bool:
    return (
        target_date.weekday() == 6
        or jpholiday.is_holiday(target_date)
    )


def should_skip_non_workday(
    target_start: datetime,
    target_end: datetime
) -> bool:
    return (
        is_non_workday(target_start.date())
        or is_non_workday(target_end.date())
    )


def is_first_workday_morning(
    target_start: datetime,
    target_end: datetime
) -> bool:
    if not (
        target_start.time() == time(6, 0)
        and target_end.time() == time(12, 0)
    ):
        return False

    previous_day = target_end.date() - timedelta(days=1)

    return is_non_workday(previous_day)


def get_shift(target_end: datetime) -> str:
    if 6 <= target_end.hour < 18:
        return "昼勤"
    return "夜勤"


def calculate_planned_time(
    target_start: datetime,
    target_end: datetime
) -> int:
    if is_first_workday_morning(target_start, target_end):
        first_start = datetime.combine(
            target_end.date(),
            FIRST_WORKDAY_START_TIME
        )

        total_minutes = int(
            (target_end - first_start).total_seconds() // 60
        )

        break_minutes = 15
        return total_minutes - break_minutes

    return TOTAL_TIME_MINUTES - BREAK_TIME_MINUTES


def calculate_expected_values(
    planned_time: int,
    machine: dict
) -> tuple[int, int, float]:
    expected_downtime = int(planned_time * machine["想定停止率_%"] / 100)
    expected_operating_time = planned_time - expected_downtime
    expected_operation_rate = expected_operating_time / planned_time * 100

    return expected_downtime, expected_operating_time, expected_operation_rate


def create_machine_record(
    now: datetime,
    target_start: datetime,
    target_end: datetime,
    machine: dict,
    planned_time: int
) -> dict:
    reason = random.choice(list(DOWNTIME_RULES.keys()))

    min_down, max_down = DOWNTIME_RULES[reason]
    actual_downtime = random.randint(min_down, max_down)
    actual_downtime = min(actual_downtime, planned_time)

    operating_time = planned_time - actual_downtime
    actual_operation_rate = operating_time / planned_time * 100

    expected_downtime, expected_operating_time, expected_operation_rate = calculate_expected_values(
        planned_time,
        machine
    )

    cycle_time = machine["サイクルタイム_分"]
    production_count = operating_time // cycle_time

    defect_rate = random.uniform(0, 0.03)
    defect_count = int(production_count * defect_rate)

    return {
        "実行日時": now.strftime("%Y-%m-%d %H:%M:%S"),
        "対象開始日時": target_start.strftime("%Y-%m-%d %H:%M:%S"),
        "対象終了日時": target_end.strftime("%Y-%m-%d %H:%M:%S"),
        "日付": target_end.strftime("%Y-%m-%d"),
        "シフト": get_shift(target_end),
        "ライン": machine["ライン"],
        "設備ID": machine["設備ID"],
        "設備名": machine["設備名"],
        "サイクルタイム_分": cycle_time,
        "計画時間_分": planned_time,
        "想定停止時間_分": expected_downtime,
        "想定稼働時間_分": expected_operating_time,
        "想定稼働率_%": round(expected_operation_rate, 1),
        "実停止時間_分": actual_downtime,
        "稼働時間_分": operating_time,
        "実績稼働率_%": round(actual_operation_rate, 1),
        "停止理由": reason,
        "生産数": production_count,
        "不良数": defect_count,
    }


def create_dummy_records(
    now: datetime,
    target_start: datetime,
    target_end: datetime,
    planned_time: int
) -> pd.DataFrame:
    records = []

    for machine in MACHINES:
        records.append(
            create_machine_record(
                now,
                target_start,
                target_end,
                machine,
                planned_time
            )
        )

    return pd.DataFrame(records)


def append_records_to_csv(file_path: str, df_new: pd.DataFrame) -> None:
    df_new.to_csv(
        file_path,
        mode="a",
        header=False,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"{len(df_new)}件のデータを追記しました。")


def main() -> None:
    now = datetime.now()

    target_start, target_end = get_target_period(now)

    print(f"実行日時: {now}")
    print(f"対象区間: {target_start} 〜 {target_end}")

    if should_skip_non_workday(target_start, target_end):
        print("対象区間に日曜日または祝日が含まれるため、データ作成をスキップします。")
        return

    planned_time = calculate_planned_time(target_start, target_end)

    file_path = get_monthly_csv_path(target_end)

    prepare_csv_file(file_path)

    df_new = create_dummy_records(
        now,
        target_start,
        target_end,
        planned_time
    )

    append_records_to_csv(file_path, df_new)

    print(f"計画時間: {planned_time}分")
    print("ダミーデータ作成が完了しました。")


if __name__ == "__main__":
    main()