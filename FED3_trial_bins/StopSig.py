
import os
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import seaborn as sns
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
from tkinter.simpledialog import askinteger, askstring
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


sns.set_theme(style="white", font_scale=1.2)

# ------------------------------------------------------------
# STOPSIG EVENT DEFINITIONS AND CONSTANTS
# ------------------------------------------------------------
START_EVENTS = {
    ">Left_Regular_trial": "Regular",
    ">Left_Stop_trial": "Stop",
}

TERMINAL_EVENTS = {
    "Right_Regular_(correct)": {
        "TrialType": "Regular",
        "ResponseType": "RightPoke",
        "Outcome": "RegularCorrect",
        "Correct": 1,
    },
    "NoPoke_Regular_(incorrect)": {
        "TrialType": "Regular",
        "ResponseType": "Withhold",
        "Outcome": "RegularIncorrect",
        "Correct": 0,
    },
    "NoPoke_STOP_(correct)": {
        "TrialType": "Stop",
        "ResponseType": "Withhold",
        "Outcome": "StopCorrect",
        "Correct": 1,
    },
    "Right_STOP_(incorrect)": {
        "TrialType": "Stop",
        "ResponseType": "RightPoke",
        "Outcome": "StopIncorrect",
        "Correct": 0,
    },
}

REQUIRED_COLUMNS = {
    "MM:DD:YYYY hh:mm:ss",
    "Event",
    "Left_Poke_Count",
    "Right_Poke_Count",
    "Pellet_Count",
}

DEFAULT_REGULAR_OMISSION_TIMEOUT_S = 30
DEFAULT_STOP_ERROR_NOISE_S = 2
DEFAULT_STOP_ERROR_TIMEOUT_S = 90
DEFAULT_STOP_SIGNAL_DELAY_MS = 300
DEFAULT_RESPONSE_WINDOW_S = 4

SUMMARY_METRICS = [
    "CompletedTrials",
    "IncompleteTrials",
    "RegularTrials",
    "StopTrials",
    "OverallAccuracy",
    "RegularAccuracy",
    "StopAccuracy",
    "BalancedAccuracy",
    "PelletsConfirmed",
    "RewardMismatches",
    "MeanRegularCorrectRT_s",
    "MeanStopFailureRT_s",
    "MeanCorrectWithhold_s",
    "MeanInterTrialInterval_s",
    "MeanAvailableInitiationLatency_s",
    "PostErrorSlowing_s",
    "PostStopRegularAccuracyChange",
    "PostStopRegularRTChange_s",
    "PostStopErrorAccuracyChange",
    "PostStopErrorRTChange_s",
    "Regular LRP count",
    "Regular LN count",
    "Stop LNP count",
    "Stop LR count",
    "Regular LRP latency RP avg (secs)",
    "Stop LNP latency NP avg (secs)",
    "Regular LRP/total trials (%)",
    "Regular LN/total trials (%)",
    "Regular trials/total trials (%)",
    "Stop LNP/total trials (%)",
    "Stop LR/total trials (%)",
    "Stop trials/total trials (%)",
    "LRP/total pellets (%)",
    "LNP/total pellets (%)",
    "RightNoLeftEvents",
    "LeftTimeoutEvents",
    "RightTimeoutEvents",
    "SessionDuration_h",
]

PCA_FEATURES = [
    "RegularAccuracy",
    "StopAccuracy",
    "MeanRegularCorrectRT_s",
    "MeanStopFailureRT_s",
    "MeanAvailableInitiationLatency_s",
    "PostErrorSlowing_s",
    "PostStopRegularAccuracyChange",
    "PostStopRegularRTChange_s",
    "PostStopErrorAccuracyChange",
    "PostStopErrorRTChange_s",
]

SUMMARY_DISPLAY_NAMES = {
    "TotalTrials": "Trial Starts",
    "CompletedTrials": "Total Trials",
    "IncompleteTrials": "Incomplete Trials",
    "RegularTrials": "Regular Trials",
    "StopTrials": "Stop Trials",
    "StopTrialPercent": "Stop trials/total trials (%)",
    "OverallAccuracy": "Overall Accuracy (%)",
    "RegularAccuracy": "Regular LRP/total regular (%)",
    "RegularOmissionRate": "Regular LN/total regular (%)",
    "StopAccuracy": "Stop LNP/total stop (%)",
    "StopFailureRate": "Stop LR/total stop (%)",
    "BalancedAccuracy": "Balanced Accuracy (%)",
    "PelletsConfirmed": "Pellet count",
    "RewardMismatches": "Reward Mismatches",
    "TrialTypeMismatches": "Trial Type Mismatches",
    "MultipleTerminalTrials": "Multiple Terminal Trials",
    "MeanRegularCorrectRT_s": "Regular LRP L to R latency avg (secs)",
    "MedianRegularCorrectRT_s": "Regular LRP L to R latency median (secs)",
    "MeanStopFailureRT_s": "Stop LR L to R latency avg (secs)",
    "MedianStopFailureRT_s": "Stop LR L to R latency median (secs)",
    "MeanCorrectWithhold_s": "Stop LNP L to N latency avg (secs)",
    "Regular LRP latency LR sum (secs)": "Regular LRP L to R latency sum (secs)",
    "Regular LRP latency LR avg (secs)": "Regular LRP L to R latency avg (secs)",
    "Regular LRP latency RP sum (secs)": "Regular LRP R to P latency sum (secs)",
    "Regular LRP latency RP avg (secs)": "Regular LRP R to P latency avg (secs)",
    "Stop LNP latency NP sum (secs)": "Stop LNP N to P latency sum (secs)",
    "Stop LNP latency NP avg (secs)": "Stop LNP N to P latency avg (secs)",
    "Stop LR latency LR sum (secs)": "Stop LR L to R latency sum (secs)",
    "Stop LR latency LR avg (secs)": "Stop LR L to R latency avg (secs)",
    "MeanInterTrialInterval_s": "Intertrial interval avg (secs)",
    "MedianInterTrialInterval_s": "Intertrial interval median (secs)",
    "MeanAvailableInitiationLatency_s": "Next-Trial Initiation Latency avg (secs)",
    "MedianAvailableInitiationLatency_s": "Next-Trial Initiation Latency median (secs)",
    "PostErrorSlowing_s": "Post-error Regular LRP L to R slowing (secs)",
    "PostStopRegularAccuracyChange": "Post-Stop Regular accuracy change (%)",
    "PostStopRegularRTChange_s": "Post-Stop Regular LRP L to R latency change (secs)",
    "PostStopErrorAccuracyChange": "Post-Stop-error accuracy change (%)",
    "PostStopErrorRTChange_s": "Post-Stop-error Regular LRP L to R latency change (secs)",
    "PostStopInitiationChange_s": "Post-Stop Next-Trial Initiation Latency change (secs)",
    "PostStopErrorInitiationChange_s": "Post-Stop-error Next-Trial Initiation Latency change (secs)",
    "RightNoLeftEvents": "Right_no_left count",
    "LeftTimeoutEvents": "LeftinTimeOut count",
    "RightTimeoutEvents": "RightinTimeout count",
    "SessionDuration_h": "Session duration (hours)",
}


# ------------------------------------------------------------
# GENERAL INPUT AND TIME HELPERS
# ------------------------------------------------------------
def clean_time_input(value):
    if value is None:
        return None

    value = str(value).strip()
    if value.isdigit():
        return f"{int(value):02d}:00"

    try:
        hour, minute = value.split(":")
        return f"{int(hour):02d}:{int(minute):02d}"
    except (TypeError, ValueError):
        return value


def validate_time(value):
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except (TypeError, ValueError):
        return False


def parse_timestamps(series):
    cleaned = (
        series
        .astype(str)
        .str.strip()
        .replace({
            "": pd.NA,
            "nan": pd.NA,
            "NaN": pd.NA,
            "None": pd.NA,
        })
    )

    parsed = pd.Series(
        pd.NaT,
        index=cleaned.index,
        dtype="datetime64[ns]",
    )

    known_formats = [
        "%m/%d/%Y %H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m:%d:%Y %H:%M:%S.%f",
        "%m:%d:%Y %H:%M:%S",
        "%m:%d:%Y %H:%M",
    ]

    for timestamp_format in known_formats:
        missing = parsed.isna() & cleaned.notna()
        if not missing.any():
            break

        parsed.loc[missing] = pd.to_datetime(
            cleaned.loc[missing],
            format=timestamp_format,
            errors="coerce",
        )

    missing = parsed.isna() & cleaned.notna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(
            cleaned.loc[missing],
            errors="coerce",
            infer_datetime_format=True,
            dayfirst=False,
        )

    return parsed

def validate_parsed_timestamps(raw_series, parsed_series, require_valid=False):
    failed = parsed_series.isna()
    n_failed = int(failed.sum())

    if n_failed == 0:
        return

    print(
        f"WARNING: {n_failed} of {len(parsed_series)} timestamps "
        "failed to parse."
    )

    examples = (
        raw_series.loc[failed]
        .dropna()
        .astype(str)
        .str.strip()
    )
    examples = [value for value in examples.unique() if value][:3]

    if examples:
        print("Unparsed timestamp examples:")
        for value in examples:
            print(f"  {value}")

    if require_valid and n_failed == len(parsed_series):
        raise ValueError(
            "All raw timestamps failed to parse. "
            "Check the 'MM:DD:YYYY hh:mm:ss' column."
        )


def identify_phase(timestamp, light_start_time, light_end_time):
    if pd.isna(timestamp):
        return np.nan

    current = timestamp.time()
    if light_start_time < light_end_time:
        return (
            "Light"
            if light_start_time <= current < light_end_time
            else "Dark"
        )

    return (
        "Light"
        if current >= light_start_time or current < light_end_time
        else "Dark"
    )


def safe_percent(numerator, denominator):
    if denominator is None or pd.isna(denominator) or denominator <= 0:
        return np.nan
    return (numerator / denominator) * 100


# ------------------------------------------------------------
# METADATA INPUT GUI
# ------------------------------------------------------------
def collect_metadata(root, file_map, save_folder):
    use_existing = messagebox.askyesno(
        "Metadata", "Do you have an existing metadata file?"
    )

    if use_existing:
        metadata_path = filedialog.askopenfilename(
            title="Select Metadata File",
            filetypes=[("Excel files", "*.xlsx")],
        )
        if not metadata_path:
            return None
        metadata_df = pd.read_excel(metadata_path)
        return metadata_df.apply(
            lambda column: column.map(
                lambda value: value.strip()
                if isinstance(value, str)
                else value
            )
        )

    window = tk.Toplevel(root)
    window.title("Enter StopSig Metadata")
    window.geometry("760x520")

    canvas = tk.Canvas(window)
    scrollbar = tk.Scrollbar(window, orient="vertical", command=canvas.yview)
    frame = tk.Frame(canvas)
    frame.bind(
        "<Configure>",
        lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
    )
    canvas.create_window((0, 0), window=frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    headers = ["Filename", "Mouse ID", "Sex", "Genotype"]
    header_entries = {}
    for column_number, header in enumerate(headers):
        if header == "Filename":
            tk.Label(
                frame, text=header, font=("Arial", 10, "bold")
            ).grid(row=0, column=column_number)
        else:
            entry = tk.Entry(frame)
            entry.insert(0, header)
            entry.grid(row=0, column=column_number)
            header_entries[column_number] = entry

    rows = []
    for row_number, filename in enumerate(file_map, start=1):
        tk.Label(frame, text=filename).grid(row=row_number, column=0)
        entries = [tk.Entry(frame) for _ in range(3)]
        for column_number, entry in enumerate(entries, start=1):
            entry.grid(row=row_number, column=column_number)
        rows.append((filename, entries))

    result = {"data": None}

    def collect():
        column_names = [header_entries[index].get() for index in [1, 2, 3]]
        data = []
        for filename, entries in rows:
            data.append({
                "Filename": filename,
                column_names[0]: entries[0].get(),
                column_names[1]: entries[1].get(),
                column_names[2]: entries[2].get(),
            })
        result["data"] = pd.DataFrame(data)
        result["data"].to_excel(
            os.path.join(save_folder, "StopSig_Metadata.xlsx"),
            index=False,
        )
        window.destroy()

    tk.Button(frame, text="Continue", command=collect).grid(
        row=len(rows) + 2, column=0, columnspan=4
    )
    root.wait_window(window)
    return result["data"]




# ------------------------------------------------------------
# RAW FED3 DATA CLEANING
# ------------------------------------------------------------
def clean_raw_data(raw_df):
    missing = sorted(REQUIRED_COLUMNS.difference(raw_df.columns))
    if missing:
        raise ValueError(
            "Missing required StopSig columns: " + ", ".join(missing)
        )

    df = raw_df.copy()
    df["RawCSVRow"] = np.arange(2, len(df) + 2)
    raw_timestamps = df["MM:DD:YYYY hh:mm:ss"].copy()
    df["Timestamp"] = parse_timestamps(raw_timestamps)
    validate_parsed_timestamps(
        raw_timestamps,
        df["Timestamp"],
        require_valid=True,
    )
    df["Event_clean"] = df["Event"].astype(str).str.strip()

    numeric_columns = [
        "Left_Poke_Count",
        "Right_Poke_Count",
        "Pellet_Count",
        "Block_Pellet_Count",
        "Retrieval_Time",
        "InterPelletInterval",
        "Poke_Time",
        "FR",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


# ------------------------------------------------------------
# TRIAL TIMING AND ROLLING-ACCURACY HELPERS
# ------------------------------------------------------------
def event_millis_latency(start_row, terminal_row):
    if "Block_Pellet_Count" not in start_row.index:
        return np.nan

    start_value = start_row.get("Block_Pellet_Count", np.nan)
    end_value = terminal_row.get("Block_Pellet_Count", np.nan)

    if pd.isna(start_value) or pd.isna(end_value):
        return np.nan

    latency = (end_value - start_value) / 1000
    if 0 <= latency <= 60:
        return latency

    return np.nan


def rolling_binary(series, window):
    numeric = pd.to_numeric(series, errors="coerce")
    denominator = numeric.rolling(window=window, min_periods=1).count()
    numerator = numeric.rolling(window=window, min_periods=1).sum()
    percentage = (numerator / denominator.replace(0, np.nan)) * 100
    return numerator, denominator, percentage


def add_trial_indices_and_rolling(trials_df, rolling_window, use_phase):
    if trials_df.empty:
        return trials_df

    trials_df = trials_df.sort_values("Trial").reset_index(drop=True)
    trials_df["TypeTrial"] = (
        trials_df.groupby("TrialType", dropna=False).cumcount() + 1
    )

    numerator, denominator, accuracy = rolling_binary(
        trials_df["Correct"], rolling_window
    )
    trials_df["RollingCorrectCount"] = numerator
    trials_df["RollingTrialCount"] = denominator
    trials_df["RollingAccuracy"] = accuracy

    trials_df["TypeRollingCorrectCount"] = np.nan
    trials_df["TypeRollingTrialCount"] = np.nan
    trials_df["TypeRollingAccuracy"] = np.nan

    for _, trial_type_df in trials_df.groupby("TrialType", dropna=False):
        numerator, denominator, accuracy = rolling_binary(
            trial_type_df["Correct"], rolling_window
        )
        trials_df.loc[
            trial_type_df.index, "TypeRollingCorrectCount"
        ] = numerator.to_numpy()
        trials_df.loc[
            trial_type_df.index, "TypeRollingTrialCount"
        ] = denominator.to_numpy()
        trials_df.loc[
            trial_type_df.index, "TypeRollingAccuracy"
        ] = accuracy.to_numpy()

    completed_correct = trials_df["Correct"].fillna(0).cumsum()
    completed_count = trials_df["Correct"].notna().cumsum()
    trials_df["CumulativeCorrect"] = completed_correct
    trials_df["CumulativeCompletedTrials"] = completed_count
    trials_df["CumulativeAccuracy"] = (
        completed_correct / completed_count.replace(0, np.nan)
    ) * 100
    trials_df["CumulativePellets"] = trials_df["PelletConfirmed"].cumsum()

    if use_phase:
        trials_df["PhaseTrial"] = (
            trials_df.groupby("Phase", dropna=False).cumcount() + 1
        )
        trials_df["PhaseTypeTrial"] = (
            trials_df.groupby(["Phase", "TrialType"], dropna=False).cumcount()
            + 1
        )

        phase_rolling_specs = [
            (
                trials_df.index,
                ["Phase"],
                "PhaseRollingCorrectCount",
                "PhaseRollingTrialCount",
                "PhaseRollingAccuracy",
            ),
            (
                trials_df.index,
                ["Phase", "TrialType"],
                "PhaseTypeRollingCorrectCount",
                "PhaseTypeRollingTrialCount",
                "PhaseTypeRollingAccuracy",
            ),
        ]

        for indices, group_columns, count_col, n_col, accuracy_col in phase_rolling_specs:
            trials_df[count_col] = np.nan
            trials_df[n_col] = np.nan
            trials_df[accuracy_col] = np.nan

            selected = trials_df.loc[indices]
            for _, group_data in selected.groupby(
                group_columns, dropna=False, sort=False
            ):
                numerator, denominator, accuracy = rolling_binary(
                    group_data["Correct"], rolling_window
                )
                trials_df.loc[group_data.index, count_col] = numerator.to_numpy()
                trials_df.loc[group_data.index, n_col] = denominator.to_numpy()
                trials_df.loc[group_data.index, accuracy_col] = accuracy.to_numpy()
    else:
        trials_df["PhaseTrial"] = trials_df["Trial"]
        trials_df["PhaseTypeTrial"] = trials_df["TypeTrial"]
        trials_df["PhaseRollingCorrectCount"] = trials_df[
            "RollingCorrectCount"
        ]
        trials_df["PhaseRollingTrialCount"] = trials_df[
            "RollingTrialCount"
        ]
        trials_df["PhaseRollingAccuracy"] = trials_df["RollingAccuracy"]
        trials_df["PhaseTypeRollingCorrectCount"] = trials_df[
            "TypeRollingCorrectCount"
        ]
        trials_df["PhaseTypeRollingTrialCount"] = trials_df[
            "TypeRollingTrialCount"
        ]
        trials_df["PhaseTypeRollingAccuracy"] = trials_df[
            "TypeRollingAccuracy"
        ]

    return trials_df


def add_sequential_context(
    trials_df,
    regular_omission_timeout_s=DEFAULT_REGULAR_OMISSION_TIMEOUT_S,
    stop_error_noise_s=DEFAULT_STOP_ERROR_NOISE_S,
    stop_error_timeout_s=DEFAULT_STOP_ERROR_TIMEOUT_S,
):
    if trials_df.empty:
        return trials_df

    trials_df = trials_df.sort_values("Trial").reset_index(drop=True).copy()
    stop_error_lockout_s = stop_error_noise_s + stop_error_timeout_s
    trials_df["PreviousTrialType"] = trials_df["TrialType"].shift()
    trials_df["PreviousOutcome"] = trials_df["Outcome"].shift()
    trials_df["PreviousSequence"] = trials_df["Sequence"].shift()
    trials_df["PreviousCorrect"] = trials_df["Correct"].shift()
    trials_df["AvailabilityTime"] = pd.NaT
    trials_df["AvailabilityBasis"] = pd.NA
    trials_df["RawAvailableInitiationLatency_s"] = np.nan
    trials_df["AvailableInitiationLatency_s"] = np.nan
    trials_df["PrecedingRegularRunLength"] = np.nan
    trials_df["OutcomeStreakLength"] = 0

    regular_run = 0
    previous_correct = None
    streak_length = 0

    for index in trials_df.index:
        current_correct = trials_df.at[index, "Correct"]

        if pd.isna(current_correct):
            streak_length = 0
            previous_correct = None
        elif previous_correct is not None and current_correct == previous_correct:
            streak_length += 1
        else:
            streak_length = 1
            previous_correct = current_correct

        trials_df.at[index, "OutcomeStreakLength"] = streak_length

        if trials_df.at[index, "TrialType"] == "Stop":
            trials_df.at[index, "PrecedingRegularRunLength"] = regular_run
            regular_run = 0
        elif trials_df.at[index, "TrialType"] == "Regular":
            regular_run += 1

        if index == 0:
            continue

        previous = trials_df.loc[index - 1]
        previous_sequence = previous["Sequence"]

        if previous_sequence in ["Regular LRP", "Stop LNP"]:
            availability_time = previous["PelletTime"]
            basis = "Pellet delivery"
            if pd.isna(availability_time):
                availability_time = previous["EndTime"]
                basis = "Terminal event fallback"
        elif previous_sequence == "Regular LN":
            availability_time = previous["EndTime"] + pd.Timedelta(
                seconds=regular_omission_timeout_s
            )
            basis = (
                f"End of {regular_omission_timeout_s}-second regular omission timeout"
            )
        elif previous_sequence == "Stop LR":
            availability_time = previous["EndTime"] + pd.Timedelta(
                seconds=stop_error_lockout_s
            )
            basis = (
                f"End of {stop_error_noise_s}-second noise and "
                f"{stop_error_timeout_s}-second stop-error timeout"
            )
        else:
            availability_time = previous["EndTime"]
            basis = "Previous terminal event"

        trials_df.at[index, "AvailabilityTime"] = availability_time
        trials_df.at[index, "AvailabilityBasis"] = basis

        if pd.notna(availability_time) and pd.notna(trials_df.at[index, "StartTime"]):
            raw_latency = (
                trials_df.at[index, "StartTime"] - availability_time
            ).total_seconds()
            trials_df.at[index, "RawAvailableInitiationLatency_s"] = raw_latency
            trials_df.at[index, "AvailableInitiationLatency_s"] = max(raw_latency, 0)

    valid_latency = trials_df["AvailableInitiationLatency_s"].notna()
    trials_df["CumulativeAvailableInitiationLatency_s"] = (
        trials_df["AvailableInitiationLatency_s"].fillna(0).cumsum()
    )
    cumulative_count = valid_latency.cumsum()
    trials_df["CumulativeMeanAvailableInitiationLatency_s"] = (
        trials_df["CumulativeAvailableInitiationLatency_s"]
        / cumulative_count.replace(0, np.nan)
    )

    trials_df["PhaseCumulativeAvailableInitiationLatency_s"] = (
        trials_df["AvailableInitiationLatency_s"]
        .fillna(0)
        .groupby(trials_df["Phase"])
        .cumsum()
    )
    phase_count = (
        valid_latency.astype(int)
        .groupby(trials_df["Phase"])
        .cumsum()
    )
    trials_df["PhaseCumulativeMeanAvailableInitiationLatency_s"] = (
        trials_df["PhaseCumulativeAvailableInitiationLatency_s"]
        / phase_count.replace(0, np.nan)
    )

    return trials_df


# ------------------------------------------------------------
# EVENT-BASED TRIAL RECONSTRUCTION
# ------------------------------------------------------------
def reconstruct_trials(
    raw_df,
    rolling_window=20,
    use_phase=False,
    light_start="07:00",
    light_end="19:00",
    regular_omission_timeout_s=DEFAULT_REGULAR_OMISSION_TIMEOUT_S,
    stop_error_noise_s=DEFAULT_STOP_ERROR_NOISE_S,
    stop_error_timeout_s=DEFAULT_STOP_ERROR_TIMEOUT_S,
    stop_signal_delay_ms=DEFAULT_STOP_SIGNAL_DELAY_MS,
    response_window_s=DEFAULT_RESPONSE_WINDOW_S,
):
    df = clean_raw_data(raw_df)
    start_indices = df.index[df["Event_clean"].isin(START_EVENTS)].tolist()
    trials = []

    phase_start = datetime.strptime(light_start, "%H:%M").time()
    phase_end = datetime.strptime(light_end, "%H:%M").time()

    for trial_number, start_index in enumerate(start_indices, start=1):
        next_start = (
            start_indices[trial_number]
            if trial_number < len(start_indices)
            else len(df)
        )
        interval = df.loc[start_index:next_start - 1].copy()
        start_row = df.loc[start_index]
        trial_type = START_EVENTS[start_row["Event_clean"]]

        terminal_rows = interval[
            interval["Event_clean"].isin(TERMINAL_EVENTS)
        ]
        terminal_count = len(terminal_rows)
        terminal_row = terminal_rows.iloc[0] if terminal_count else None

        if terminal_row is None:
            terminal_event = np.nan
            terminal_time = interval["Timestamp"].dropna().iloc[-1]
            terminal_raw_row = np.nan
            response_type = "Incomplete"
            outcome = "Incomplete"
            correct = np.nan
            terminal_trial_type = np.nan
            completed = 0
            pellet_search = interval.iloc[0:0]
        else:
            terminal_event = terminal_row["Event_clean"]
            terminal_info = TERMINAL_EVENTS[terminal_event]
            terminal_time = terminal_row["Timestamp"]
            terminal_raw_row = terminal_row["RawCSVRow"]
            response_type = terminal_info["ResponseType"]
            outcome = terminal_info["Outcome"]
            correct = terminal_info["Correct"]
            terminal_trial_type = terminal_info["TrialType"]
            completed = 1
            pellet_search = interval.loc[terminal_row.name:]

        pellet_rows = pellet_search[
            pellet_search["Event_clean"].eq("Pellet")
        ]
        pellet_confirmed = int(not pellet_rows.empty)
        pellet_row = pellet_rows.iloc[0] if pellet_confirmed else None
        pellet_time = (
            pellet_row.get("Timestamp", pd.NaT)
            if pellet_row is not None
            else pd.NaT
        )

        timestamp_latency = (
            (terminal_time - start_row["Timestamp"]).total_seconds()
            if pd.notna(terminal_time) and pd.notna(start_row["Timestamp"])
            else np.nan
        )
        millis_latency = (
            event_millis_latency(start_row, terminal_row)
            if terminal_row is not None
            else np.nan
        )
        terminal_latency = (
            millis_latency if pd.notna(millis_latency) else timestamp_latency
        )
        latency_source = (
            "Block_Pellet_Count"
            if pd.notna(millis_latency)
            else "Timestamp"
        )

        if use_phase:
            start_phase = identify_phase(
                start_row["Timestamp"], phase_start, phase_end
            )
            end_phase = identify_phase(terminal_time, phase_start, phase_end)
            phase_crossing = start_phase != end_phase
            phase = end_phase
        else:
            start_phase = "All"
            end_phase = "All"
            phase_crossing = False
            phase = "All"

        expected_reward = correct if completed else np.nan
        reward_mismatch = (
            int(pellet_confirmed != expected_reward)
            if completed
            else np.nan
        )

        right_response_latency = (
            terminal_latency if response_type == "RightPoke" else np.nan
        )
        withhold_duration = (
            terminal_latency if response_type == "Withhold" else np.nan
        )
        pellet_delivery_latency = (
            (pellet_time - terminal_time).total_seconds()
            if pd.notna(pellet_time) and pd.notna(terminal_time)
            else np.nan
        )

        sequence = {
            "RegularCorrect": "Regular LRP",
            "RegularIncorrect": "Regular LN",
            "StopCorrect": "Stop LNP",
            "StopIncorrect": "Stop LR",
            "Incomplete": "Incomplete",
        }[outcome]

        trials.append({
            "Trial": trial_number,
            "TrialType": trial_type,
            "Completed": completed,
            "Outcome": outcome,
            "Sequence": sequence,
            "Correct": correct,
            "ResponseType": response_type,
            "StartEvent": start_row["Event_clean"],
            "TerminalEvent": terminal_event,
            "TerminalEventCount": terminal_count,
            "TrialTypeMismatch": (
                int(trial_type != terminal_trial_type)
                if completed
                else np.nan
            ),
            "PelletExpected": expected_reward,
            "PelletConfirmed": pellet_confirmed,
            "RewardMismatch": reward_mismatch,
            "Phase": phase,
            "StartPhase": start_phase,
            "EndPhase": end_phase,
            "PhaseCrossing": phase_crossing,
            "StartTime": start_row["Timestamp"],
            "EndTime": terminal_time,
            "PelletTime": pellet_time,
            "TerminalLatency_s": terminal_latency,
            "TimestampLatency_s": timestamp_latency,
            "EventMillisLatency_s": millis_latency,
            "LatencySource": latency_source,
            "RightResponseLatency_s": right_response_latency,
            "WithholdDuration_s": withhold_duration,
            "PelletDeliveryLatency_s": pellet_delivery_latency,
            "InterTrialInterval_s": np.nan,
            "StopSignalDelay_ms": stop_signal_delay_ms,
            "ResponseWindow_s": response_window_s,
            "RegularOmissionTimeout_s": regular_omission_timeout_s,
            "StopErrorNoise_s": stop_error_noise_s,
            "StopErrorTimeout_s": stop_error_timeout_s,
            "StopErrorLockout_s": stop_error_noise_s + stop_error_timeout_s,
            "PelletCountAtStart": start_row.get("Pellet_Count", np.nan),
            "PelletCountAfterTrial": (
                pellet_row.get("Pellet_Count", np.nan)
                if pellet_row is not None
                else interval["Pellet_Count"].dropna().iloc[-1]
            ),
            "PelletRetrievalTime": (
                pellet_row.get("Retrieval_Time", np.nan)
                if pellet_row is not None
                else np.nan
            ),
            "InterPelletInterval": (
                pellet_row.get("InterPelletInterval", np.nan)
                if pellet_row is not None
                else np.nan
            ),
            "LeftPokeCountAtStart": start_row.get(
                "Left_Poke_Count", np.nan
            ),
            "RightPokeCountAtStart": start_row.get(
                "Right_Poke_Count", np.nan
            ),
            "LeftPokeCountAtEnd": (
                terminal_row.get("Left_Poke_Count", np.nan)
                if terminal_row is not None
                else interval["Left_Poke_Count"].dropna().iloc[-1]
            ),
            "RightPokeCountAtEnd": (
                terminal_row.get("Right_Poke_Count", np.nan)
                if terminal_row is not None
                else interval["Right_Poke_Count"].dropna().iloc[-1]
            ),
            "StartRawCSVRow": start_row["RawCSVRow"],
            "TerminalRawCSVRow": terminal_raw_row,
            "RollingWindow": rolling_window,
        })

    trials_df = pd.DataFrame(trials)
    if trials_df.empty:
        return trials_df, df

    trials_df["InterTrialInterval_s"] = (
        trials_df["StartTime"] - trials_df["EndTime"].shift()
    ).dt.total_seconds()

    trials_df = add_trial_indices_and_rolling(
        trials_df,
        rolling_window=rolling_window,
        use_phase=use_phase,
    )
    trials_df = add_sequential_context(
        trials_df,
        regular_omission_timeout_s=regular_omission_timeout_s,
        stop_error_noise_s=stop_error_noise_s,
        stop_error_timeout_s=stop_error_timeout_s,
    )
    return trials_df, df


# ------------------------------------------------------------
# MOUSE, TRIAL-TYPE, AND PHASE SUMMARIES
# ------------------------------------------------------------
def calculate_sequence_metrics(trials_df):
    completed = trials_df[trials_df["Completed"].eq(1)].copy()
    regular_lrp = completed[completed["Sequence"].eq("Regular LRP")]
    regular_ln = completed[completed["Sequence"].eq("Regular LN")]
    stop_lnp = completed[completed["Sequence"].eq("Stop LNP")]
    stop_lr = completed[completed["Sequence"].eq("Stop LR")]

    regular_lrp_count = len(regular_lrp)
    regular_ln_count = len(regular_ln)
    stop_lnp_count = len(stop_lnp)
    stop_lr_count = len(stop_lr)
    regular_trials = regular_lrp_count + regular_ln_count
    stop_trials = stop_lnp_count + stop_lr_count
    total_trials = regular_trials + stop_trials
    pellet_count = int(completed["PelletConfirmed"].sum())

    return {
        "Regular LRP count": regular_lrp_count,
        "Regular LRP latency LR sum (secs)": regular_lrp[
            "RightResponseLatency_s"
        ].sum(),
        "Regular LRP latency LR avg (secs)": regular_lrp[
            "RightResponseLatency_s"
        ].mean(),
        "Regular LRP latency RP sum (secs)": regular_lrp[
            "PelletDeliveryLatency_s"
        ].sum(),
        "Regular LRP latency RP avg (secs)": regular_lrp[
            "PelletDeliveryLatency_s"
        ].mean(),
        "Regular LN count": regular_ln_count,
        "Stop LNP count": stop_lnp_count,
        "Stop LNP latency NP sum (secs)": stop_lnp[
            "PelletDeliveryLatency_s"
        ].sum(),
        "Stop LNP latency NP avg (secs)": stop_lnp[
            "PelletDeliveryLatency_s"
        ].mean(),
        "Stop LR count": stop_lr_count,
        "Stop LR latency LR sum (secs)": stop_lr[
            "RightResponseLatency_s"
        ].sum(),
        "Stop LR latency LR avg (secs)": stop_lr[
            "RightResponseLatency_s"
        ].mean(),
        "Regular LRP/total regular (%)": safe_percent(
            regular_lrp_count, regular_trials
        ),
        "Regular LN/total regular (%)": safe_percent(
            regular_ln_count, regular_trials
        ),
        "Regular Trials": regular_trials,
        "Stop LNP/total stop (%)": safe_percent(stop_lnp_count, stop_trials),
        "Stop LR/total stop (%)": safe_percent(stop_lr_count, stop_trials),
        "Stop Trials": stop_trials,
        "Regular LRP/total trials (%)": safe_percent(
            regular_lrp_count, total_trials
        ),
        "Regular LN/total trials (%)": safe_percent(
            regular_ln_count, total_trials
        ),
        "Regular trials/total trials (%)": safe_percent(
            regular_trials, total_trials
        ),
        "Stop LNP/total trials (%)": safe_percent(
            stop_lnp_count, total_trials
        ),
        "Stop LR/total trials (%)": safe_percent(stop_lr_count, total_trials),
        "Stop trials/total trials (%)": safe_percent(stop_trials, total_trials),
        "Total Trials": total_trials,
        "Pellet count": pellet_count,
        "LRP/total pellets (%)": safe_percent(
            regular_lrp_count, pellet_count
        ),
        "LNP/total pellets (%)": safe_percent(stop_lnp_count, pellet_count),
    }


def calculate_adjustment_metrics(trials_df):
    regular = trials_df[
        trials_df["TrialType"].eq("Regular")
        & trials_df["Completed"].eq(1)
    ].copy()

    after_regular = regular[regular["PreviousTrialType"].eq("Regular")]
    after_stop = regular[regular["PreviousTrialType"].eq("Stop")]
    after_stop_success = regular[regular["PreviousSequence"].eq("Stop LNP")]
    after_stop_error = regular[regular["PreviousSequence"].eq("Stop LR")]
    after_correct = regular[regular["PreviousCorrect"].eq(1)]
    after_error = regular[regular["PreviousCorrect"].eq(0)]

    def accuracy(data):
        return data["Correct"].mean() * 100 if not data.empty else np.nan

    def correct_rt(data):
        return data.loc[
            data["Outcome"].eq("RegularCorrect"),
            "RightResponseLatency_s",
        ].mean()

    def initiation(data):
        return data["AvailableInitiationLatency_s"].mean()

    return {
        "MeanAvailableInitiationLatency_s": trials_df[
            "AvailableInitiationLatency_s"
        ].mean(),
        "MedianAvailableInitiationLatency_s": trials_df[
            "AvailableInitiationLatency_s"
        ].median(),
        "PostErrorSlowing_s": correct_rt(after_error) - correct_rt(after_correct),
        "PostStopRegularAccuracyChange": (
            accuracy(after_stop) - accuracy(after_regular)
        ),
        "PostStopRegularRTChange_s": (
            correct_rt(after_stop) - correct_rt(after_regular)
        ),
        "PostStopInitiationChange_s": (
            initiation(after_stop) - initiation(after_regular)
        ),
        "PostStopErrorAccuracyChange": (
            accuracy(after_stop_error) - accuracy(after_stop_success)
        ),
        "PostStopErrorRTChange_s": (
            correct_rt(after_stop_error) - correct_rt(after_stop_success)
        ),
        "PostStopErrorInitiationChange_s": (
            initiation(after_stop_error) - initiation(after_stop_success)
        ),
        "RegularTrialsAfterRegular": len(after_regular),
        "RegularTrialsAfterStop": len(after_stop),
        "RegularTrialsAfterStopSuccess": len(after_stop_success),
        "RegularTrialsAfterStopError": len(after_stop_error),
    }


def summarize_trials(trials_df, event_counts):
    completed = trials_df[trials_df["Completed"].eq(1)].copy()
    regular = completed[completed["TrialType"].eq("Regular")]
    stop = completed[completed["TrialType"].eq("Stop")]
    regular_correct = regular[regular["Correct"].eq(1)]
    stop_incorrect = stop[stop["Correct"].eq(0)]
    correct_withhold = stop[stop["Correct"].eq(1)]

    session_duration_h = (
        (trials_df["EndTime"].max() - trials_df["StartTime"].min())
        .total_seconds()
        / 3600
        if not trials_df.empty
        else np.nan
    )
    regular_accuracy = safe_percent(regular["Correct"].sum(), len(regular))
    stop_accuracy = safe_percent(stop["Correct"].sum(), len(stop))

    summary = {
        "TotalTrials": len(trials_df),
        "CompletedTrials": len(completed),
        "IncompleteTrials": int(trials_df["Completed"].eq(0).sum()),
        "RegularTrials": len(regular),
        "StopTrials": len(stop),
        "StopTrialPercent": safe_percent(len(stop), len(completed)),
        "OverallAccuracy": safe_percent(
            completed["Correct"].sum(), len(completed)
        ),
        "RegularAccuracy": regular_accuracy,
        "StopAccuracy": stop_accuracy,
        "BalancedAccuracy": np.nanmean(
            [regular_accuracy, stop_accuracy]
        ),
        "RegularOmissionRate": (
            100 - regular_accuracy if pd.notna(regular_accuracy) else np.nan
        ),
        "StopFailureRate": (
            100 - stop_accuracy if pd.notna(stop_accuracy) else np.nan
        ),
        "PelletsConfirmed": int(trials_df["PelletConfirmed"].sum()),
        "RewardMismatches": int(
            pd.to_numeric(
                trials_df["RewardMismatch"], errors="coerce"
            ).fillna(0).sum()
        ),
        "TrialTypeMismatches": int(
            pd.to_numeric(
                trials_df["TrialTypeMismatch"], errors="coerce"
            ).fillna(0).sum()
        ),
        "MultipleTerminalTrials": int(
            trials_df["TerminalEventCount"].gt(1).sum()
        ),
        "MeanRegularCorrectRT_s": regular_correct[
            "RightResponseLatency_s"
        ].mean(),
        "MedianRegularCorrectRT_s": regular_correct[
            "RightResponseLatency_s"
        ].median(),
        "MeanStopFailureRT_s": stop_incorrect[
            "RightResponseLatency_s"
        ].mean(),
        "MedianStopFailureRT_s": stop_incorrect[
            "RightResponseLatency_s"
        ].median(),
        "MeanCorrectWithhold_s": correct_withhold[
            "WithholdDuration_s"
        ].mean(),
        "MeanInterTrialInterval_s": trials_df[
            "InterTrialInterval_s"
        ].mean(),
        "MedianInterTrialInterval_s": trials_df[
            "InterTrialInterval_s"
        ].median(),
        "RightNoLeftEvents": int(event_counts.get("Right_no_left", 0)),
        "LeftTimeoutEvents": int(event_counts.get("LeftinTimeOut", 0)),
        "RightTimeoutEvents": int(event_counts.get("RightinTimeout", 0)),
        "SessionDuration_h": session_duration_h,
    }
    summary.update(calculate_sequence_metrics(trials_df))
    summary.update(calculate_adjustment_metrics(trials_df))
    return summary


def summarize_trial_types(trials_df):
    rows = []
    for trial_type, data in trials_df.groupby("TrialType", dropna=False):
        completed = data[data["Completed"].eq(1)]
        rows.append({
            "TrialType": trial_type,
            "Trials": len(data),
            "CompletedTrials": len(completed),
            "CorrectTrials": completed["Correct"].sum(),
            "Accuracy": safe_percent(
                completed["Correct"].sum(), len(completed)
            ),
            "RightPokeTrials": int(
                completed["ResponseType"].eq("RightPoke").sum()
            ),
            "WithholdTrials": int(
                completed["ResponseType"].eq("Withhold").sum()
            ),
            "MeanTerminalLatency_s": completed[
                "TerminalLatency_s"
            ].mean(),
            "MedianTerminalLatency_s": completed[
                "TerminalLatency_s"
            ].median(),
        })
    return pd.DataFrame(rows)


def summarize_phases(trials_df):
    if "Phase" not in trials_df.columns:
        return pd.DataFrame()

    rows = []
    for phase, phase_data in trials_df.groupby("Phase"):
        phase_summary = summarize_trials(
            phase_data,
            pd.Series(dtype="int64"),
        )
        phase_summary["Phase"] = phase
        rows.append(phase_summary)
    return pd.DataFrame(rows)


# ------------------------------------------------------------
# PERI-STOP ALIGNMENT AND PCA PREPARATION
# ------------------------------------------------------------
def build_peri_stop_data(
    trials_df,
    peri_window,
    mouse_col,
    sex_col,
    group_col,
):
    if trials_df.empty:
        return pd.DataFrame()

    data = trials_df.sort_values("Trial").reset_index(drop=True)
    anchors = data.index[data["TrialType"].eq("Stop")].tolist()
    rows = []

    for anchor_index in anchors:
        anchor = data.loc[anchor_index]
        anchor_category = (
            "Stop Success"
            if anchor["Sequence"] == "Stop LNP"
            else "Stop Error"
        )

        for relative_trial in range(-peri_window, peri_window + 1):
            surrounding_index = anchor_index + relative_trial
            if surrounding_index < 0 or surrounding_index >= len(data):
                continue

            surrounding = data.loc[surrounding_index]
            is_regular = surrounding["TrialType"] == "Regular"
            is_regular_correct = surrounding["Outcome"] == "RegularCorrect"

            rows.append({
                "Filename": anchor.get("Filename", np.nan),
                mouse_col: anchor.get(mouse_col, np.nan),
                sex_col: anchor.get(sex_col, np.nan),
                group_col: anchor.get(group_col, np.nan),
                "Phase": anchor["Phase"],
                "AnchorTrial": anchor["Trial"],
                "AnchorSequence": anchor["Sequence"],
                "AnchorCategory": anchor_category,
                "RelativeTrial": relative_trial,
                "SurroundingTrial": surrounding["Trial"],
                "SurroundingTrialType": surrounding["TrialType"],
                "SurroundingSequence": surrounding["Sequence"],
                "SurroundingCorrect": surrounding["Correct"],
                "RegularAccuracy": (
                    surrounding["Correct"] * 100 if is_regular else np.nan
                ),
                "RegularCorrectRT_s": (
                    surrounding["RightResponseLatency_s"]
                    if is_regular_correct
                    else np.nan
                ),
                "AvailableInitiationLatency_s": surrounding[
                    "AvailableInitiationLatency_s"
                ],
                "PeriWindow": peri_window,
            })

    return pd.DataFrame(rows)


def run_mouse_pca(summary_df, mouse_col, sex_col, group_col):
    empty_result = {
        "performed": False,
        "scores": pd.DataFrame(),
        "loadings": pd.DataFrame(),
        "variance": pd.DataFrame(),
        "input": pd.DataFrame(),
        "diagnostics": pd.DataFrame(),
        "features": [],
        "pca_model": None,
        "scaler": None,
        "imputation_means": pd.Series(dtype=float),
    }

    available_features = [
        feature for feature in PCA_FEATURES if feature in summary_df.columns
    ]
    if len(available_features) < 2:
        return empty_result

    aggregations = {
        sex_col: "first",
        group_col: "first",
        **{feature: "mean" for feature in available_features},
    }
    mouse_data = (
        summary_df.groupby(mouse_col, as_index=False)
        .agg(aggregations)
        .copy()
    )

    numeric = mouse_data[available_features].apply(
        pd.to_numeric, errors="coerce"
    )
    usable_features = [
        feature
        for feature in available_features
        if numeric[feature].notna().sum() >= 2
        and numeric[feature].nunique(dropna=True) > 1
    ]

    if len(mouse_data) < 3 or len(usable_features) < 2:
        return empty_result

    numeric = numeric[usable_features]
    imputation_means = numeric.mean()
    imputed = numeric.fillna(imputation_means)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(imputed)
    pca = PCA(n_components=2)
    components = pca.fit_transform(scaled)

    scores = mouse_data[[mouse_col, sex_col, group_col]].copy()
    scores["PC1"] = components[:, 0]
    scores["PC2"] = components[:, 1]

    pca_input = mouse_data[[mouse_col, sex_col, group_col]].copy()
    for feature in usable_features:
        pca_input[feature] = imputed[feature].to_numpy()

    loadings = pd.DataFrame({
        "Feature": usable_features,
        "PC1": pca.components_[0],
        "PC2": pca.components_[1],
    })
    variance = pd.DataFrame({
        "Component": ["PC1", "PC2"],
        "ExplainedVarianceRatio": pca.explained_variance_ratio_,
        "ExplainedVariancePercent": pca.explained_variance_ratio_ * 100,
    })
    diagnostics = pd.DataFrame({
        "Feature": usable_features,
        "ImputationMean": [imputation_means[feature] for feature in usable_features],
        "ScalingMean": scaler.mean_,
        "ScalingSD": scaler.scale_,
        "MissingValuesImputed": [
            int(numeric[feature].isna().sum()) for feature in usable_features
        ],
    })

    return {
        "performed": True,
        "scores": scores,
        "loadings": loadings,
        "variance": variance,
        "input": pca_input,
        "diagnostics": diagnostics,
        "features": usable_features,
        "pca_model": pca,
        "scaler": scaler,
        "imputation_means": imputation_means,
    }


def project_phase_pca(
    phase_summary_df,
    pca_results,
    mouse_col,
    sex_col,
    group_col,
):
    if phase_summary_df.empty or not pca_results["performed"]:
        return pd.DataFrame(), pd.DataFrame()

    features = pca_results["features"]
    score_rows = []
    input_rows = []

    for phase, phase_data in phase_summary_df.groupby("Phase"):
        aggregations = {
            sex_col: "first",
            group_col: "first",
            **{feature: "mean" for feature in features},
        }
        mouse_data = (
            phase_data.groupby(mouse_col, as_index=False)
            .agg(aggregations)
            .copy()
        )
        if mouse_data.empty:
            continue

        numeric = mouse_data[features].apply(pd.to_numeric, errors="coerce")
        imputed = numeric.fillna(pca_results["imputation_means"])
        scaled = pca_results["scaler"].transform(imputed)
        components = pca_results["pca_model"].transform(scaled)

        scores = mouse_data[[mouse_col, sex_col, group_col]].copy()
        scores.insert(3, "Phase", phase)
        scores["PC1"] = components[:, 0]
        scores["PC2"] = components[:, 1]
        score_rows.append(scores)

        pca_input = mouse_data[[mouse_col, sex_col, group_col]].copy()
        pca_input.insert(3, "Phase", phase)
        for feature in features:
            pca_input[feature] = imputed[feature].to_numpy()
        input_rows.append(pca_input)

    phase_scores = (
        pd.concat(score_rows, ignore_index=True)
        if score_rows
        else pd.DataFrame()
    )
    phase_input = (
        pd.concat(input_rows, ignore_index=True)
        if input_rows
        else pd.DataFrame()
    )
    return phase_scores, phase_input


# ------------------------------------------------------------
# PRISM TABLE AND EXCEL-NAME HELPERS
# ------------------------------------------------------------
def move_metadata_left(data, metadata_columns):
    if data.empty:
        return data
    front = [column for column in metadata_columns if column in data.columns]
    remaining = [column for column in data.columns if column not in front]
    return data[front + remaining]


def safe_sheet_name(name):
    invalid = "[]:*?/\\"
    cleaned = "".join("_" if character in invalid else character for character in name)
    return cleaned[:31]


def prism_summary_table(summary_df, metric, mouse_col, sex_col, group_col):
    columns = [mouse_col, sex_col, group_col, metric]
    table = summary_df[columns].copy()
    return table.rename(columns=SUMMARY_DISPLAY_NAMES)


def format_summary_for_export(summary_df):
    display_df = summary_df.rename(columns=SUMMARY_DISPLAY_NAMES).copy()
    return display_df.loc[:, ~display_df.columns.duplicated()]


def prism_trial_table(
    trials_df,
    metric,
    index_col,
    mouse_col,
    sex_col,
    group_col,
):
    data = trials_df.dropna(subset=[index_col, metric]).copy()
    if data.empty:
        return pd.DataFrame()

    wide = data.pivot_table(
        index=index_col,
        columns=mouse_col,
        values=metric,
        aggfunc="mean",
    ).sort_index()

    metadata = (
        data[[mouse_col, sex_col, group_col]]
        .drop_duplicates(subset=[mouse_col])
        .set_index(mouse_col)
    )
    ordered_mice = list(wide.columns)
    header = pd.DataFrame(
        [
            [metadata.at[mouse, group_col] for mouse in ordered_mice],
            [metadata.at[mouse, sex_col] for mouse in ordered_mice],
        ],
        index=[group_col, sex_col],
        columns=ordered_mice,
    )
    body = wide.copy()
    body.index = body.index.map(str)
    return pd.concat([header, body], axis=0)


# ------------------------------------------------------------
# EXCEL WORKBOOK EXPORT
# ------------------------------------------------------------
def write_outputs(
    output_path,
    trials_df,
    summary_df,
    type_summary_df,
    event_counts_df,
    phase_summary_df,
    peri_stop_df,
    pca_results,
    phase_pca_scores_df,
    phase_pca_input_df,
    analysis_settings_df,
    mouse_col,
    sex_col,
    group_col,
    use_phase,
):
    metadata_columns = ["Filename", mouse_col, sex_col, group_col]
    trials_df = move_metadata_left(trials_df, metadata_columns)
    summary_df = move_metadata_left(summary_df, metadata_columns)
    type_summary_df = move_metadata_left(type_summary_df, metadata_columns)
    event_counts_df = move_metadata_left(event_counts_df, metadata_columns)
    phase_summary_df = move_metadata_left(
        phase_summary_df, metadata_columns
    )

    validation_columns = metadata_columns + [
        "Trial",
        "Completed",
        "TrialTypeMismatch",
        "TerminalEventCount",
        "PelletExpected",
        "PelletConfirmed",
        "RewardMismatch",
        "StartRawCSVRow",
        "TerminalRawCSVRow",
    ]
    validation = trials_df[
        [column for column in validation_columns if column in trials_df.columns]
    ].copy()

    with pd.ExcelWriter(output_path) as writer:
        trials_df.to_excel(writer, sheet_name="Trials", index=False)
        format_summary_for_export(summary_df).to_excel(
            writer, sheet_name="Summary", index=False
        )
        type_summary_df.to_excel(
            writer, sheet_name="TrialType_Summary", index=False
        )
        event_counts_df.to_excel(
            writer, sheet_name="Event_Counts", index=False
        )
        validation.to_excel(writer, sheet_name="Validation", index=False)
        if analysis_settings_df is not None and not analysis_settings_df.empty:
            analysis_settings_df.to_excel(
                writer,
                sheet_name="Analysis_Settings",
                index=False,
            )

        if not peri_stop_df.empty:
            excel_row_limit = 1_000_000
            for start_row in range(0, len(peri_stop_df), excel_row_limit):
                stop_row = start_row + excel_row_limit
                sheet_number = (start_row // excel_row_limit) + 1
                sheet_name = (
                    "PeriStop_Trials"
                    if len(peri_stop_df) <= excel_row_limit
                    else f"PeriStop_Trials_{sheet_number}"
                )
                peri_stop_df.iloc[start_row:stop_row].to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False,
                )

        if pca_results["performed"]:
            pca_results["scores"].to_excel(
                writer, sheet_name="PCA_Scores", index=False
            )
            pca_results["loadings"].to_excel(
                writer, sheet_name="PCA_Loadings", index=False
            )
            pca_results["variance"].to_excel(
                writer, sheet_name="PCA_Variance", index=False
            )
            pca_results["input"].to_excel(
                writer, sheet_name="PCA_Input", index=False
            )
            pca_results["diagnostics"].to_excel(
                writer, sheet_name="PCA_Diagnostics", index=False
            )

            if not phase_pca_scores_df.empty:
                phase_pca_scores_df.to_excel(
                    writer, sheet_name="PCA_Phase_Scores", index=False
                )
                phase_pca_input_df.to_excel(
                    writer, sheet_name="PCA_Phase_Input", index=False
                )

                for phase, phase_scores in phase_pca_scores_df.groupby("Phase"):
                    phase_scores.to_excel(
                        writer,
                        sheet_name=safe_sheet_name(f"PCA_Scores_{phase}"),
                        index=False,
                    )
                    phase_pca_input_df[
                        phase_pca_input_df["Phase"].eq(phase)
                    ].to_excel(
                        writer,
                        sheet_name=safe_sheet_name(f"PCA_Input_{phase}"),
                        index=False,
                    )

        if use_phase:
            format_summary_for_export(phase_summary_df).to_excel(
                writer, sheet_name="Phase_Summary", index=False
            )

            for phase in ["Dark", "Light"]:
                phase_data = trials_df[trials_df["Phase"].eq(phase)]
                phase_data.to_excel(
                    writer,
                    sheet_name=safe_sheet_name(f"Trials_{phase}"),
                    index=False,
                )

        for metric in SUMMARY_METRICS:
            if metric not in summary_df.columns:
                continue
            prism_summary_table(
                summary_df, metric, mouse_col, sex_col, group_col
            ).to_excel(
                writer,
                sheet_name=safe_sheet_name(f"S_{metric}"),
                index=False,
            )

        trial_exports = [
            ("OverallRolling", trials_df, "RollingAccuracy", "Trial"),
            (
                "RegularRolling",
                trials_df[trials_df["TrialType"].eq("Regular")],
                "TypeRollingAccuracy",
                "TypeTrial",
            ),
            (
                "StopRolling",
                trials_df[trials_df["TrialType"].eq("Stop")],
                "TypeRollingAccuracy",
                "TypeTrial",
            ),
            (
                "Regular_L_to_R",
                trials_df[trials_df["Outcome"].eq("RegularCorrect")],
                "RightResponseLatency_s",
                "TypeTrial",
            ),
            (
                "Regular_R_to_P",
                trials_df[trials_df["Outcome"].eq("RegularCorrect")],
                "PelletDeliveryLatency_s",
                "TypeTrial",
            ),
            (
                "Stop_N_to_P",
                trials_df[trials_df["Outcome"].eq("StopCorrect")],
                "PelletDeliveryLatency_s",
                "TypeTrial",
            ),
            (
                "Stop_L_to_R",
                trials_df[trials_df["Outcome"].eq("StopIncorrect")],
                "RightResponseLatency_s",
                "TypeTrial",
            ),
            (
                "CumNextTrialInit",
                trials_df,
                "CumulativeAvailableInitiationLatency_s",
                "Trial",
            ),
            (
                "CumMeanNextTrialInit",
                trials_df,
                "CumulativeMeanAvailableInitiationLatency_s",
                "Trial",
            ),
        ]

        for name, data, metric, index_col in trial_exports:
            table = prism_trial_table(
                data,
                metric,
                index_col,
                mouse_col,
                sex_col,
                group_col,
            )
            if not table.empty:
                table.to_excel(
                    writer,
                    sheet_name=safe_sheet_name(f"T_{name}"),
                    index=True,
                )

        if use_phase:
            phase_initiation_exports = [
                (
                    "CumNextInit",
                    "PhaseCumulativeAvailableInitiationLatency_s",
                ),
                (
                    "CumMeanNextInit",
                    "PhaseCumulativeMeanAvailableInitiationLatency_s",
                ),
            ]
            for phase in ["Dark", "Light"]:
                phase_trials = trials_df[trials_df["Phase"].eq(phase)]
                for short_name, metric in phase_initiation_exports:
                    table = prism_trial_table(
                        phase_trials,
                        metric,
                        "PhaseTrial",
                        mouse_col,
                        sex_col,
                        group_col,
                    )
                    if table.empty:
                        continue
                    table.to_excel(
                        writer,
                        sheet_name=safe_sheet_name(
                            f"T_{short_name}_{phase}"
                        ),
                        index=True,
                    )

        if not peri_stop_df.empty:
            peri_metrics = [
                ("RegularAccuracy", "Accuracy"),
                ("RegularCorrectRT_s", "Regular_L_to_R"),
                ("AvailableInitiationLatency_s", "NextTrialInit"),
            ]
            anchor_groups = [
                ("AllStop", peri_stop_df),
                (
                    "StopSuccess",
                    peri_stop_df[
                        peri_stop_df["AnchorCategory"].eq("Stop Success")
                    ],
                ),
                (
                    "StopError",
                    peri_stop_df[
                        peri_stop_df["AnchorCategory"].eq("Stop Error")
                    ],
                ),
            ]

            for anchor_name, anchor_data in anchor_groups:
                for metric, metric_name in peri_metrics:
                    table = prism_trial_table(
                        anchor_data,
                        metric,
                        "RelativeTrial",
                        mouse_col,
                        sex_col,
                        group_col,
                    )
                    if table.empty:
                        continue
                    table.to_excel(
                        writer,
                        sheet_name=safe_sheet_name(
                            f"Peri_{anchor_name}_{metric_name}"
                        ),
                        index=True,
                    )


# ------------------------------------------------------------
# PLOT FILE, COLOUR, AND DISPLAY HELPERS
# ------------------------------------------------------------
PLOT_LINEWIDTH = 2.5
PLOT_SEM_ALPHA = 0.18
STRIPPLOT_SIZE = 7


def safe_filename_value(value):
    safe = str(value).strip()
    for character in '<>:"/\\|?*[]':
        safe = safe.replace(character, "_")
    return safe.replace(" ", "_").replace("\n", "").replace("\r", "")


def build_plot_filename(
    metric,
    grouping_col=None,
    subset_col=None,
    subset_value=None,
    phase=None,
):
    parts = [safe_filename_value(metric)]

    if subset_col is not None and subset_value is not None:
        parts.append(
            f"{safe_filename_value(subset_col)}_"
            f"{safe_filename_value(subset_value)}"
        )

    if grouping_col is not None:
        parts.append(f"By_{safe_filename_value(grouping_col)}")

    if phase is not None:
        parts.append(safe_filename_value(phase))

    return "__".join(parts) + ".png"


def get_plot_path(plot_folder, filename):
    filename_lower = filename.lower()

    if filename_lower.startswith("pca_") or "correlation" in filename_lower:
        subfolder = "PCA"
    elif filename_lower.startswith("stacked_"):
        subfolder = "Stacked"
    elif filename_lower.startswith("peristop_"):
        subfolder = "PeriStop"
    elif filename_lower.endswith("__dark.png"):
        subfolder = "Dark"
    elif filename_lower.endswith("__light.png"):
        subfolder = "Light"
    else:
        subfolder = "All"

    destination = os.path.join(plot_folder, subfolder)
    os.makedirs(destination, exist_ok=True)
    return os.path.join(destination, filename)


def build_color_map(values):
    values = sorted({str(value) for value in values if pd.notna(value)})
    if not values:
        return {}

    colors = sns.color_palette("tab10", n_colors=len(values)).as_hex()
    return {value: colors[index] for index, value in enumerate(values)}


def configure_plot_colors(metadata_df, group_col, sex_col, use_custom_colors):
    group_values = metadata_df[group_col].dropna().astype(str).unique()
    sex_values = metadata_df[sex_col].dropna().astype(str).unique()
    combined_values = (
        metadata_df[sex_col].astype(str)
        + " x "
        + metadata_df[group_col].astype(str)
    ).unique()

    color_maps = {
        group_col: build_color_map(group_values),
        sex_col: build_color_map(sex_values),
        "Combined_Group": build_color_map(combined_values),
    }

    if use_custom_colors:
        for value in sorted(group_values):
            color = colorchooser.askcolor(
                title=f"Choose colour for {value}"
            )[1]
            if color is not None:
                color_maps[group_col][str(value)] = color

        for value in sorted(sex_values):
            color = colorchooser.askcolor(
                title=f"Choose colour for {value}"
            )[1]
            if color is not None:
                color_maps[sex_col][str(value)] = color

    return color_maps


def get_plot_color(value, grouping_col, color_maps):
    return color_maps.get(grouping_col, {}).get(str(value))


def finish_plot(figure, plot_path, show_plots):
    figure.savefig(plot_path, dpi=300, bbox_inches="tight")
    if show_plots:
        plt.show()
    else:
        plt.close(figure)


# ------------------------------------------------------------
# CORE PLOTTING FUNCTIONS
# ------------------------------------------------------------
def plot_group_trajectory(
    data,
    x_col,
    y_col,
    grouping_col,
    title,
    ylabel,
    filename,
    plot_folder,
    color_maps,
    show_plots,
    y_limits=None,
    vertical_line=None,
):
    required = [x_col, y_col, grouping_col, "_Mouse"]
    if data.empty or any(column not in data.columns for column in required):
        return

    plot_data = data.dropna(subset=required).copy()
    if plot_data.empty:
        return

    figure, axis = plt.subplots(figsize=(9, 6))

    for group, group_data in plot_data.groupby(grouping_col, sort=True):
        per_mouse = (
            group_data.groupby(["_Mouse", x_col], as_index=False)[y_col]
            .mean()
        )
        grouped = per_mouse.groupby(x_col)[y_col]
        mean = grouped.mean()
        sem = grouped.sem().fillna(0)
        color = get_plot_color(group, grouping_col, color_maps)

        axis.plot(
            mean.index,
            mean.values,
            color=color,
            linewidth=PLOT_LINEWIDTH,
            label=group,
        )
        axis.fill_between(
            mean.index,
            mean - sem,
            mean + sem,
            color=color,
            alpha=PLOT_SEM_ALPHA,
        )

    x_labels = {
        "Trial": "Trial",
        "TypeTrial": "Trial within Trial Type",
        "PhaseTrial": "Phase Trial",
        "PhaseTypeTrial": "Phase Trial within Trial Type",
        "RelativeTrial": "Trials around Stop",
    }
    axis.set_xlabel(x_labels.get(x_col, x_col))
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    if y_limits is not None:
        axis.set_ylim(*y_limits)
    if vertical_line is not None:
        axis.axvline(vertical_line, color="black", linestyle="--", linewidth=1.5)
    axis.legend(frameon=True)
    sns.despine(ax=axis)
    figure.tight_layout()
    finish_plot(
        figure,
        get_plot_path(plot_folder, filename),
        show_plots,
    )


def plot_summary_metric(
    data,
    metric,
    x_col,
    title,
    filename,
    plot_folder,
    color_maps,
    show_plots,
    hue_col=None,
):
    required = [metric, x_col]
    if hue_col is not None:
        required.append(hue_col)

    if data.empty or any(column not in data.columns for column in required):
        return

    plot_data = data.dropna(subset=required).copy()
    if plot_data.empty:
        return

    palette_col = hue_col if hue_col is not None else x_col
    palette = color_maps.get(palette_col)
    plot_hue = hue_col if hue_col is not None else x_col
    figure, axis = plt.subplots(figsize=(8, 6))
    sns.stripplot(
        data=plot_data,
        x=x_col,
        y=metric,
        hue=plot_hue,
        dodge=hue_col is not None,
        jitter=0.16,
        size=STRIPPLOT_SIZE,
        palette=palette,
        ax=axis,
    )

    if hue_col is None:
        legend = axis.get_legend()
        if legend is not None:
            legend.remove()
    axis.set_title(title)
    sns.despine(ax=axis)
    figure.tight_layout()
    finish_plot(
        figure,
        get_plot_path(plot_folder, filename),
        show_plots,
    )


# ------------------------------------------------------------
# REUSABLE GRAPH-VARIANT GENERATORS
# ------------------------------------------------------------
def add_combined_group(data, sex_col, group_col):
    combined = data.copy()
    valid = combined[sex_col].notna() & combined[group_col].notna()
    combined["Combined_Group"] = pd.Series(
        pd.NA,
        index=combined.index,
        dtype="object",
    )
    combined.loc[valid, "Combined_Group"] = (
        combined.loc[valid, sex_col].astype(str)
        + " x "
        + combined.loc[valid, group_col].astype(str)
    )
    combined[sex_col] = combined[sex_col].map(
        lambda value: str(value) if pd.notna(value) else np.nan
    )
    combined[group_col] = combined[group_col].map(
        lambda value: str(value) if pd.notna(value) else np.nan
    )
    return combined


def generate_trajectory_variants(
    data,
    metric_name,
    title_prefix,
    x_col,
    y_col,
    ylabel,
    mouse_col,
    sex_col,
    group_col,
    phase,
    plot_folder,
    color_maps,
    show_plots,
    y_limits=None,
    vertical_line=None,
):
    if data.empty:
        return

    plot_data = add_combined_group(data, sex_col, group_col)
    plot_data["_Mouse"] = plot_data[mouse_col].astype(str)
    phase_title = f", {phase}" if phase is not None else ""

    for grouping_col in [group_col, sex_col, "Combined_Group"]:
        plot_group_trajectory(
            plot_data,
            x_col,
            y_col,
            grouping_col,
            f"{title_prefix} (by {grouping_col}{phase_title})",
            ylabel,
            build_plot_filename(
                metric_name,
                grouping_col=grouping_col,
                phase=phase,
            ),
            plot_folder,
            color_maps,
            show_plots,
            y_limits,
            vertical_line,
        )

    for split_col, compare_col in [
        (sex_col, group_col),
        (group_col, sex_col),
    ]:
        for value in sorted(plot_data[split_col].dropna().unique()):
            subset = plot_data[plot_data[split_col].eq(value)]
            plot_group_trajectory(
                subset,
                x_col,
                y_col,
                compare_col,
                (
                    f"{title_prefix} ({compare_col} within "
                    f"{split_col} = {value}{phase_title})"
                ),
                ylabel,
                build_plot_filename(
                    metric_name,
                    grouping_col=compare_col,
                    subset_col=split_col,
                    subset_value=value,
                    phase=phase,
                ),
                plot_folder,
                color_maps,
                show_plots,
                y_limits,
                vertical_line,
            )


def generate_summary_variants(
    data,
    metric,
    title_prefix,
    sex_col,
    group_col,
    phase,
    plot_folder,
    color_maps,
    show_plots,
):
    if data.empty or metric not in data.columns:
        return

    plot_data = add_combined_group(data, sex_col, group_col)
    phase_title = f", {phase}" if phase is not None else ""

    direct_specs = [
        (group_col, sex_col, f"{group_col}_{sex_col}"),
        (sex_col, group_col, f"{sex_col}_{group_col}"),
        ("Combined_Group", None, "Combined_Group"),
    ]

    for x_col, hue_col, grouping_name in direct_specs:
        plot_summary_metric(
            plot_data,
            metric,
            x_col,
            f"{title_prefix} (by {grouping_name}{phase_title})",
            build_plot_filename(
                f"Summary_{metric}",
                grouping_col=grouping_name,
                phase=phase,
            ),
            plot_folder,
            color_maps,
            show_plots,
            hue_col=hue_col,
        )

    for split_col, compare_col in [
        (sex_col, group_col),
        (group_col, sex_col),
    ]:
        for value in sorted(plot_data[split_col].dropna().unique()):
            subset = plot_data[plot_data[split_col].eq(value)]
            plot_summary_metric(
                subset,
                metric,
                compare_col,
                (
                    f"{title_prefix} ({compare_col} within "
                    f"{split_col} = {value}{phase_title})"
                ),
                build_plot_filename(
                    f"Summary_{metric}",
                    grouping_col=compare_col,
                    subset_col=split_col,
                    subset_value=value,
                    phase=phase,
                ),
                plot_folder,
                color_maps,
                show_plots,
            )


# ------------------------------------------------------------
# TRIAL RASTER AND PCA PLOTS
# ------------------------------------------------------------
def format_sex_label(value):
    text = str(value).strip()
    return text[:1].upper() if text else ""


def plot_stacked_trial_raster(
    data,
    x_col,
    title,
    filename,
    plot_folder,
    mouse_col,
    sex_col,
    group_col,
    show_plots,
    raster_mode="sequence",
):
    if raster_mode == "accuracy":
        value_col = "Correct"
        code_map = {0: 0, 1: 1}
        colors = ["#FF0000", "#9ACD32"]
        image_alpha = 1.0
        legend_handles = [
            Patch(color="#9ACD32", alpha=0.88, label="Correct"),
            Patch(color="#FF0000", alpha=0.88, label="Incorrect"),
        ]
    else:
        value_col = "Sequence"
        code_map = {
            "Regular LRP": 0,
            "Regular LN": 1,
            "Stop LNP": 2,
            "Stop LR": 3,
        }
        colors = ["#14823B", "#A9DDB8", "#B3212D", "#F2AFB5"]
        image_alpha = 1.0
        legend_handles = [
            Patch(color="#14823B", label="Regular LRP"),
            Patch(color="#A9DDB8", label="Regular LN"),
            Patch(color="#B3212D", label="Stop LNP"),
            Patch(color="#F2AFB5", label="Stop LR"),
        ]

    required = [mouse_col, sex_col, group_col, x_col, value_col]
    if data.empty or any(column not in data.columns for column in required):
        return

    plot_data = data.dropna(subset=[mouse_col, x_col, value_col]).copy()
    if plot_data.empty:
        return

    mouse_order = (
        plot_data[[mouse_col, sex_col, group_col]]
        .drop_duplicates(subset=[mouse_col])
        .sort_values([sex_col, group_col, mouse_col], kind="stable")
    )
    mice = mouse_order[mouse_col].tolist()
    maximum_trial = int(plot_data[x_col].max())
    matrix = np.full((len(mice), maximum_trial), np.nan)
    for row_index, mouse in enumerate(mice):
        mouse_data = plot_data[plot_data[mouse_col].eq(mouse)]
        for _, trial in mouse_data.iterrows():
            column_index = int(trial[x_col]) - 1
            code = code_map.get(trial[value_col])
            if 0 <= column_index < maximum_trial and code is not None:
                matrix[row_index, column_index] = code

    cmap = ListedColormap(colors)
    cmap.set_bad("white")
    figure_height = max(5, len(mice) * 0.35)
    figure, axis = plt.subplots(figsize=(14, figure_height))
    axis.imshow(
        matrix,
        aspect="auto",
        interpolation="nearest",
        cmap=cmap,
        vmin=0,
        vmax=len(colors) - 1,
        alpha=image_alpha,
    )

    for row_boundary in np.arange(0.5, len(mice), 1):
        axis.axhline(
            row_boundary,
            color="white",
            linewidth=0.35,
            alpha=0.65,
        )

    labels = []
    metadata = mouse_order.set_index(mouse_col)
    for mouse in mice:
        labels.append(
            f"{mouse} | {format_sex_label(metadata.at[mouse, sex_col])} | "
            f"{metadata.at[mouse, group_col]}"
        )

    axis.set_yticks(np.arange(len(mice)))
    axis.set_yticklabels(labels, fontsize=8)
    axis.set_xlabel(x_col)
    axis.set_ylabel("Mouse")
    axis.set_title(title)
    axis.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=len(legend_handles),
        frameon=True,
    )
    figure.tight_layout(rect=[0, 0.10, 1, 1])
    finish_plot(
        figure,
        get_plot_path(plot_folder, filename),
        show_plots,
    )


def plot_pca_joint(
    data,
    grouping_col,
    title,
    filename,
    plot_folder,
    color_maps,
    variance,
    show_plots,
):
    plot_data = data.dropna(subset=["PC1", "PC2", grouping_col]).copy()
    if plot_data.empty:
        return

    grid = sns.JointGrid(
        data=plot_data,
        x="PC1",
        y="PC2",
        height=7,
        ratio=4,
        space=0.08,
    )

    for group, group_data in plot_data.groupby(grouping_col, sort=True):
        color = get_plot_color(group, grouping_col, color_maps)
        grid.ax_joint.scatter(
            group_data["PC1"],
            group_data["PC2"],
            label=group,
            s=75,
            alpha=0.70,
            color=color,
        )

        if len(group_data) >= 3 and group_data["PC1"].nunique() > 1:
            sns.kdeplot(
                data=group_data,
                x="PC1",
                ax=grid.ax_marg_x,
                color=color,
                fill=True,
                alpha=0.22,
                linewidth=1.5,
            )

        if len(group_data) >= 3 and group_data["PC2"].nunique() > 1:
            sns.kdeplot(
                data=group_data,
                y="PC2",
                ax=grid.ax_marg_y,
                color=color,
                fill=True,
                alpha=0.22,
                linewidth=1.5,
            )

    grid.ax_joint.axhline(0, color="#9BB7DD", linestyle="--", alpha=0.8)
    grid.ax_joint.axvline(0, color="#9BB7DD", linestyle="--", alpha=0.8)
    grid.ax_joint.set_xlabel(f"PC1 ({variance[0]:.1f}%)")
    grid.ax_joint.set_ylabel(f"PC2 ({variance[1]:.1f}%)")
    grid.ax_joint.legend(title=grouping_col, frameon=True)

    figure = grid.figure
    figure.suptitle(title, y=1.02)
    figure.tight_layout(rect=[0, 0, 1, 0.98])
    finish_plot(
        figure,
        get_plot_path(plot_folder, filename),
        show_plots,
    )


def plot_pca_score_variants(
    scores,
    variance,
    phase,
    plot_folder,
    sex_col,
    group_col,
    color_maps,
    show_plots,
):
    if scores.empty:
        return

    scores = add_combined_group(scores, sex_col, group_col)
    phase_title = f", {phase}" if phase is not None else ""

    for grouping_col in [sex_col, group_col, "Combined_Group"]:
        plot_pca_joint(
            scores,
            grouping_col,
            f"PCA (by {grouping_col}{phase_title})",
            build_plot_filename(
                "PCA_Scores",
                grouping_col=grouping_col,
                phase=phase,
            ),
            plot_folder,
            color_maps,
            variance,
            show_plots,
        )

    for split_col, compare_col in [
        (sex_col, group_col),
        (group_col, sex_col),
    ]:
        for value in sorted(scores[split_col].dropna().unique()):
            subset = scores[scores[split_col].eq(value)]
            plot_pca_joint(
                subset,
                compare_col,
                (
                    f"PCA ({compare_col} within {split_col} = "
                    f"{value}{phase_title})"
                ),
                build_plot_filename(
                    "PCA_Scores",
                    grouping_col=compare_col,
                    subset_col=split_col,
                    subset_value=value,
                    phase=phase,
                ),
                plot_folder,
                color_maps,
                variance,
                show_plots,
            )


def create_pca_plots(
    pca_results,
    phase_pca_scores_df,
    plot_folder,
    sex_col,
    group_col,
    color_maps,
    show_plots,
):
    if not pca_results["performed"]:
        return

    variance = pca_results["variance"][
        "ExplainedVariancePercent"
    ].to_numpy()
    plot_pca_score_variants(
        pca_results["scores"],
        variance,
        None,
        plot_folder,
        sex_col,
        group_col,
        color_maps,
        show_plots,
    )

    if not phase_pca_scores_df.empty:
        for phase, phase_scores in phase_pca_scores_df.groupby("Phase"):
            plot_pca_score_variants(
                phase_scores,
                variance,
                phase,
                plot_folder,
                sex_col,
                group_col,
                color_maps,
                show_plots,
            )

    loadings = pca_results["loadings"].copy()
    loadings["Feature"] = loadings["Feature"].map(
        lambda feature: SUMMARY_DISPLAY_NAMES.get(feature, feature)
    )
    loadings = loadings.set_index("Feature")
    for component in ["PC1", "PC2"]:
        figure, axis = plt.subplots(
            figsize=(8, max(5, len(loadings) * 0.45))
        )
        sns.barplot(
            x=loadings[component],
            y=loadings.index,
            color="#4C78A8",
            ax=axis,
        )
        axis.axvline(0, color="black", linestyle="--")
        axis.set_title(f"PCA Loadings ({component})")
        axis.set_xlabel("Loading")
        axis.set_ylabel("Feature")
        figure.tight_layout()
        finish_plot(
            figure,
            get_plot_path(
                plot_folder,
                f"PCA_Loadings_{component}.png",
            ),
            show_plots,
        )

    figure, axis = plt.subplots(figsize=(10, 8))
    correlation = pca_results["input"][pca_results["features"]].corr()
    sns.heatmap(
        correlation,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        center=0,
        ax=axis,
    )
    axis.set_title("PCA Feature Correlation Matrix")
    figure.tight_layout()
    finish_plot(
        figure,
        get_plot_path(plot_folder, "PCA_Feature_Correlation.png"),
        show_plots,
    )


# ------------------------------------------------------------
# GRAPH GENERATION
# ------------------------------------------------------------
def create_plots(
    trials_df,
    summary_df,
    phase_summary_df,
    peri_stop_df,
    pca_results,
    phase_pca_scores_df,
    plot_folder,
    mouse_col,
    sex_col,
    group_col,
    use_phase,
    color_maps,
    show_plots,
):
    os.makedirs(plot_folder, exist_ok=True)

    trajectory_specs = [
        (
            "OverallAccuracy",
            trials_df,
            "Trial",
            "RollingAccuracy",
            "Rolling Overall Accuracy",
        ),
        (
            "RegularAccuracy",
            trials_df[trials_df["TrialType"].eq("Regular")],
            "TypeTrial",
            "TypeRollingAccuracy",
            "Rolling Regular-Trial Accuracy",
        ),
        (
            "StopAccuracy",
            trials_df[trials_df["TrialType"].eq("Stop")],
            "TypeTrial",
            "TypeRollingAccuracy",
            "Rolling Stop-Trial Accuracy",
        ),
    ]

    for name, data, x_col, y_col, title in trajectory_specs:
        generate_trajectory_variants(
            data,
            name,
            title,
            x_col,
            y_col,
            "Accuracy (%)",
            mouse_col,
            sex_col,
            group_col,
            None,
            plot_folder,
            color_maps,
            show_plots,
            y_limits=(0, 100),
        )

    initiation_specs = [
        (
            "CumulativeNextTrialInitiationLatency",
            "Cumulative Next-Trial Initiation Latency",
            "CumulativeAvailableInitiationLatency_s",
            "Cumulative latency (seconds)",
        ),
        (
            "CumulativeMeanNextTrialInitiationLatency",
            "Cumulative Mean Next-Trial Initiation Latency",
            "CumulativeMeanAvailableInitiationLatency_s",
            "Mean latency (seconds)",
        ),
    ]

    for metric_name, title, metric, ylabel in initiation_specs:
        generate_trajectory_variants(
            trials_df,
            metric_name,
            title,
            "Trial",
            metric,
            ylabel,
            mouse_col,
            sex_col,
            group_col,
            None,
            plot_folder,
            color_maps,
            show_plots,
        )

    if use_phase:
        for phase in ["Dark", "Light"]:
            phase_data = trials_df[trials_df["Phase"].eq(phase)]
            phase_specs = [
                (
                    "OverallAccuracy",
                    phase_data,
                    "PhaseTrial",
                    "PhaseRollingAccuracy",
                    "Rolling Overall Accuracy",
                ),
                (
                    "RegularAccuracy",
                    phase_data[phase_data["TrialType"].eq("Regular")],
                    "PhaseTypeTrial",
                    "PhaseTypeRollingAccuracy",
                    "Rolling Regular-Trial Accuracy",
                ),
                (
                    "StopAccuracy",
                    phase_data[phase_data["TrialType"].eq("Stop")],
                    "PhaseTypeTrial",
                    "PhaseTypeRollingAccuracy",
                    "Rolling Stop-Trial Accuracy",
                ),
            ]

            for name, subset, x_col, y_col, title in phase_specs:
                generate_trajectory_variants(
                    subset,
                    name,
                    title,
                    x_col,
                    y_col,
                    "Accuracy (%)",
                    mouse_col,
                    sex_col,
                    group_col,
                    phase,
                    plot_folder,
                    color_maps,
                    show_plots,
                    y_limits=(0, 100),
                )

            phase_initiation_specs = [
                (
                    "CumulativeNextTrialInitiationLatency",
                    "Cumulative Next-Trial Initiation Latency",
                    "PhaseCumulativeAvailableInitiationLatency_s",
                    "Cumulative latency (seconds)",
                ),
                (
                    "CumulativeMeanNextTrialInitiationLatency",
                    "Cumulative Mean Next-Trial Initiation Latency",
                    "PhaseCumulativeMeanAvailableInitiationLatency_s",
                    "Mean latency (seconds)",
                ),
            ]

            for metric_name, title, metric, ylabel in phase_initiation_specs:
                generate_trajectory_variants(
                    phase_data,
                    metric_name,
                    title,
                    "PhaseTrial",
                    metric,
                    ylabel,
                    mouse_col,
                    sex_col,
                    group_col,
                    phase,
                    plot_folder,
                    color_maps,
                    show_plots,
                )

    summary_metrics = [
        "OverallAccuracy",
        "RegularAccuracy",
        "StopAccuracy",
        "BalancedAccuracy",
        "MeanRegularCorrectRT_s",
        "Regular LRP latency RP avg (secs)",
        "Stop LNP latency NP avg (secs)",
        "MeanStopFailureRT_s",
        "MeanAvailableInitiationLatency_s",
        "PostErrorSlowing_s",
        "PostStopRegularAccuracyChange",
        "PostStopRegularRTChange_s",
        "PostStopErrorAccuracyChange",
        "PostStopErrorRTChange_s",
    ]

    for metric in summary_metrics:
        if metric in summary_df.columns:
            generate_summary_variants(
                summary_df,
                metric,
                SUMMARY_DISPLAY_NAMES.get(metric, metric),
                sex_col,
                group_col,
                None,
                plot_folder,
                color_maps,
                show_plots,
            )

    if use_phase and not phase_summary_df.empty:
        for phase, phase_data in phase_summary_df.groupby("Phase"):
            for metric in summary_metrics:
                if metric not in phase_data.columns:
                    continue
                generate_summary_variants(
                    phase_data,
                    metric,
                    SUMMARY_DISPLAY_NAMES.get(metric, metric),
                    sex_col,
                    group_col,
                    phase,
                    plot_folder,
                    color_maps,
                    show_plots,
                )

    # -------------------------
    # PERI-STOP TRAJECTORIES
    # -------------------------
    if not peri_stop_df.empty:
        peri_metrics = [
            (
                "RegularAccuracy",
                "Regular-Trial Accuracy",
                "Regular-Trial Accuracy (%)",
                (0, 100),
            ),
            (
                "RegularCorrectRT_s",
                "Regular LRP L to R Latency",
                "Regular LRP L to R Latency (seconds)",
                None,
            ),
            (
                "AvailableInitiationLatency_s",
                "Next-Trial Initiation Latency",
                "Next-Trial Initiation Latency (seconds)",
                None,
            ),
        ]
        anchor_groups = [
            ("AllStop", "All Stop Trials", peri_stop_df),
            (
                "StopSuccess",
                "Successful Stop LNP Trials",
                peri_stop_df[
                    peri_stop_df["AnchorCategory"].eq("Stop Success")
                ],
            ),
            (
                "StopError",
                "Failed Stop LR Trials",
                peri_stop_df[
                    peri_stop_df["AnchorCategory"].eq("Stop Error")
                ],
            ),
        ]

        for anchor_name, anchor_label, anchor_data in anchor_groups:
            for metric, title, ylabel, y_limits in peri_metrics:
                generate_trajectory_variants(
                    anchor_data,
                    f"PeriStop_{anchor_name}_{metric}",
                    f"{title} Around {anchor_label}",
                    "RelativeTrial",
                    metric,
                    ylabel,
                    mouse_col,
                    sex_col,
                    group_col,
                    None,
                    plot_folder,
                    color_maps,
                    show_plots,
                    y_limits=y_limits,
                    vertical_line=0,
                )

                if use_phase:
                    for phase in ["Dark", "Light"]:
                        phase_anchor_data = anchor_data[
                            anchor_data["Phase"].eq(phase)
                        ]
                        generate_trajectory_variants(
                            phase_anchor_data,
                            f"PeriStop_{anchor_name}_{metric}",
                            f"{title} Around {anchor_label}",
                            "RelativeTrial",
                            metric,
                            ylabel,
                            mouse_col,
                            sex_col,
                            group_col,
                            phase,
                            plot_folder,
                            color_maps,
                            show_plots,
                            y_limits=y_limits,
                            vertical_line=0,
                        )

    # -------------------------
    # STACKED TRIAL RASTERS
    # -------------------------
    plot_stacked_trial_raster(
        trials_df,
        "Trial",
        "StopSig Trial Sequences",
        "Stacked_TrialRaster.png",
        plot_folder,
        mouse_col,
        sex_col,
        group_col,
        show_plots,
    )

    plot_stacked_trial_raster(
        trials_df,
        "Trial",
        "StopSig Trial Accuracy",
        "Stacked_AccuracyRaster.png",
        plot_folder,
        mouse_col,
        sex_col,
        group_col,
        show_plots,
        raster_mode="accuracy",
    )

    if use_phase:
        for phase in ["Dark", "Light"]:
            plot_stacked_trial_raster(
                trials_df[trials_df["Phase"].eq(phase)],
                "PhaseTrial",
                f"StopSig Trial Sequences ({phase})",
                f"Stacked_TrialRaster__{phase}.png",
                plot_folder,
                mouse_col,
                sex_col,
                group_col,
                show_plots,
            )

            plot_stacked_trial_raster(
                trials_df[trials_df["Phase"].eq(phase)],
                "PhaseTrial",
                f"StopSig Trial Accuracy ({phase})",
                f"Stacked_AccuracyRaster__{phase}.png",
                plot_folder,
                mouse_col,
                sex_col,
                group_col,
                show_plots,
                raster_mode="accuracy",
            )

    # -------------------------
    # PCA AND CORRELATION PLOTS
    # -------------------------
    create_pca_plots(
        pca_results,
        phase_pca_scores_df,
        plot_folder,
        sex_col,
        group_col,
        color_maps,
        show_plots,
    )


# ------------------------------------------------------------
# MAIN GUI AND ANALYSIS WORKFLOW
# ------------------------------------------------------------
def run_gui():
    # -------------------------
    # STEP 1A: ROOT SETUP
    # -------------------------
    root = tk.Tk()
    root.withdraw()

    # -------------------------
    # STEP 1B: FILE SELECTION AND OUTPUT LOCATION
    # -------------------------
    file_paths = filedialog.askopenfilenames(
        title="Select FED3 StopSig CSV files",
        filetypes=[("CSV files", "*.csv")],
    )
    if not file_paths:
        return

    file_map = {os.path.basename(path): path for path in file_paths}
    save_folder = os.path.dirname(file_paths[0])

    # -------------------------
    # STEP 2A: LIGHT/DARK SETTINGS
    # -------------------------
    use_phase = messagebox.askyesno(
        "Light/Dark Analysis",
        "Do you want to split trials by Light/Dark cycle?",
    )
    light_start = "07:00"
    light_end = "19:00"

    if use_phase:
        light_start = clean_time_input(
            askstring(
                "Light Cycle",
                "Enter LIGHT START time (24h HH:MM)",
                initialvalue="07:00",
            )
        )
        light_end = clean_time_input(
            askstring(
                "Light Cycle",
                "Enter LIGHT END time (24h HH:MM)",
                initialvalue="19:00",
            )
        )
        if not validate_time(light_start) or not validate_time(light_end):
            messagebox.showerror(
                "Invalid Time",
                "Light start and end must use HH:MM format.",
            )
            return

    # -------------------------
    # STEP 2B: ROLLING WINDOW SETTING
    # -------------------------
    rolling_window = askinteger(
        "Rolling Accuracy Window",
        "Enter the number of trials used for rolling accuracy.",
        initialvalue=20,
        minvalue=1,
    )
    if rolling_window is None:
        return

    # -------------------------
    # STEP 2C: PERI-STOP WINDOW SETTING
    # -------------------------
    peri_window = askinteger(
        "Peri-Stop Window",
        "Enter the number of trials before and after each Stop trial.",
        initialvalue=10,
        minvalue=1,
    )
    if peri_window is None:
        return

    # -------------------------
    # STEP 2D: TASK TIMING SETTINGS
    # -------------------------
    regular_omission_timeout_s = askinteger(
        "Task Timing",
        (
            "Regular no-poke/omission timeout in seconds.\n\n"
            "Used after Regular LN trials to calculate next-trial initiation latency."
        ),
        initialvalue=DEFAULT_REGULAR_OMISSION_TIMEOUT_S,
        minvalue=0,
    )
    if regular_omission_timeout_s is None:
        return

    stop_error_noise_s = askinteger(
        "Task Timing",
        (
            "Stop-error noise duration in seconds.\n\n"
            "Used after Stop LR trials before the timeout period."
        ),
        initialvalue=DEFAULT_STOP_ERROR_NOISE_S,
        minvalue=0,
    )
    if stop_error_noise_s is None:
        return

    stop_error_timeout_s = askinteger(
        "Task Timing",
        (
            "Stop-error timeout duration in seconds.\n\n"
            "Total Stop LR lockout = noise duration + timeout duration."
        ),
        initialvalue=DEFAULT_STOP_ERROR_TIMEOUT_S,
        minvalue=0,
    )
    if stop_error_timeout_s is None:
        return

    stop_signal_delay_ms = askinteger(
        "Task Timing",
        (
            "Stop-signal delay in milliseconds.\n\n"
            "This is saved with each trial for documentation."
        ),
        initialvalue=DEFAULT_STOP_SIGNAL_DELAY_MS,
        minvalue=0,
    )
    if stop_signal_delay_ms is None:
        return

    response_window_s = askinteger(
        "Task Timing",
        (
            "Response window in seconds.\n\n"
            "This is saved with each trial for documentation."
        ),
        initialvalue=DEFAULT_RESPONSE_WINDOW_S,
        minvalue=1,
    )
    if response_window_s is None:
        return

    # -------------------------
    # STEP 3: METADATA INPUT
    # -------------------------
    metadata_df = collect_metadata(root, file_map, save_folder)
    if metadata_df is None or metadata_df.empty:
        return

    metadata_columns = [
        column for column in metadata_df.columns if column != "Filename"
    ]
    if len(metadata_columns) < 3:
        messagebox.showerror(
            "Metadata Error",
            "Metadata needs Mouse ID, Sex, and Group/Genotype columns.",
        )
        return

    mouse_col, sex_col, group_col = metadata_columns[:3]

    # -------------------------
    # STEP 4: PLOT DISPLAY AND COLOURS
    # -------------------------
    show_plots = messagebox.askyesno(
        "Plot Display",
        "Display plots?\n\nYes = show plots\nNo = save only",
    )
    use_custom_colors = messagebox.askyesno(
        "Plot Colours",
        "Would you like to choose custom colours for Sex and Genotype groups?",
    )
    color_maps = configure_plot_colors(
        metadata_df,
        group_col,
        sex_col,
        use_custom_colors,
    )

    # -------------------------
    # STEP 5: READ, CLEAN, AND PROCESS INDIVIDUAL FILES
    # -------------------------
    all_trials = []
    all_summaries = []
    all_type_summaries = []
    all_event_counts = []
    all_phase_summaries = []
    all_peri_stop = []
    errors = []

    for _, metadata_row in metadata_df.iterrows():
        filename = metadata_row["Filename"]

        if filename not in file_map:
            errors.append(f"{filename}: not among selected CSV files")
            continue

        try:
            raw_df = pd.read_csv(file_map[filename], low_memory=False)
            trials_df, clean_df = reconstruct_trials(
                raw_df,
                rolling_window=rolling_window,
                use_phase=use_phase,
                light_start=light_start,
                light_end=light_end,
                regular_omission_timeout_s=regular_omission_timeout_s,
                stop_error_noise_s=stop_error_noise_s,
                stop_error_timeout_s=stop_error_timeout_s,
                stop_signal_delay_ms=stop_signal_delay_ms,
                response_window_s=response_window_s,
            )
        except Exception as error:
            errors.append(f"{filename}: {error}")
            continue

        if trials_df.empty:
            errors.append(f"{filename}: no StopSig trial-start events found")
            continue

        metadata_values = {
            "Filename": filename,
            mouse_col: metadata_row[mouse_col],
            sex_col: metadata_row[sex_col],
            group_col: metadata_row[group_col],
        }
        timing_values = {
            "RegularOmissionTimeout_s": regular_omission_timeout_s,
            "StopErrorNoise_s": stop_error_noise_s,
            "StopErrorTimeout_s": stop_error_timeout_s,
            "StopErrorLockout_s": stop_error_noise_s + stop_error_timeout_s,
            "StopSignalDelay_ms": stop_signal_delay_ms,
            "ResponseWindow_s": response_window_s,
        }
        for column, value in metadata_values.items():
            trials_df[column] = value

        event_counts = clean_df["Event_clean"].value_counts()
        summary = summarize_trials(trials_df, event_counts)
        summary.update(metadata_values)
        summary.update(timing_values)
        all_summaries.append(summary)
        all_trials.append(trials_df)

        peri_stop = build_peri_stop_data(
            trials_df,
            peri_window,
            mouse_col,
            sex_col,
            group_col,
        )
        if not peri_stop.empty:
            all_peri_stop.append(peri_stop)

        type_summary = summarize_trial_types(trials_df)
        for column, value in metadata_values.items():
            type_summary[column] = value
        all_type_summaries.append(type_summary)

        event_count_df = event_counts.rename_axis("Event").reset_index(
            name="Count"
        )
        for column, value in metadata_values.items():
            event_count_df[column] = value
        all_event_counts.append(event_count_df)

        if use_phase:
            phase_summary = summarize_phases(trials_df)
            for column, value in metadata_values.items():
                phase_summary[column] = value
            all_phase_summaries.append(phase_summary)

    if not all_trials:
        messagebox.showerror(
            "No Output",
            "No files could be reconstructed.\n\n" + "\n".join(errors),
        )
        return

    # -------------------------
    # STEP 6: COMBINE OUTPUTS AND RUN PCA
    # -------------------------
    trials_all_df = pd.concat(all_trials, ignore_index=True)
    summary_df = pd.DataFrame(all_summaries)
    type_summary_df = pd.concat(all_type_summaries, ignore_index=True)
    event_counts_df = pd.concat(all_event_counts, ignore_index=True)
    phase_summary_df = (
        pd.concat(all_phase_summaries, ignore_index=True)
        if all_phase_summaries
        else pd.DataFrame()
    )
    peri_stop_df = (
        pd.concat(all_peri_stop, ignore_index=True)
        if all_peri_stop
        else pd.DataFrame()
    )
    pca_results = run_mouse_pca(
        summary_df,
        mouse_col,
        sex_col,
        group_col,
    )
    phase_pca_scores_df, phase_pca_input_df = project_phase_pca(
        phase_summary_df,
        pca_results,
        mouse_col,
        sex_col,
        group_col,
    )

    analysis_settings_df = pd.DataFrame([
        {
            "Setting": "Rolling accuracy window",
            "Value": rolling_window,
            "Units": "trials",
            "Notes": "Number of trials used for rolling accuracy calculations.",
        },
        {
            "Setting": "Peri-stop window",
            "Value": peri_window,
            "Units": "trials before/after anchor",
            "Notes": "Number of reconstructed trials extracted before and after each Stop anchor.",
        },
        {
            "Setting": "Light/dark analysis enabled",
            "Value": use_phase,
            "Units": "",
            "Notes": "If TRUE, phase-specific summaries, exports, and plots are generated.",
        },
        {
            "Setting": "Light cycle start",
            "Value": light_start if use_phase else "Not used",
            "Units": "HH:MM",
            "Notes": "User-entered light-cycle start time.",
        },
        {
            "Setting": "Light cycle end",
            "Value": light_end if use_phase else "Not used",
            "Units": "HH:MM",
            "Notes": "User-entered light-cycle end time.",
        },
        {
            "Setting": "Regular omission timeout",
            "Value": regular_omission_timeout_s,
            "Units": "seconds",
            "Notes": "Added after Regular LN terminal events when calculating AvailabilityTime.",
        },
        {
            "Setting": "Stop-error noise duration",
            "Value": stop_error_noise_s,
            "Units": "seconds",
            "Notes": "Noise duration added after Stop LR terminal events.",
        },
        {
            "Setting": "Stop-error timeout duration",
            "Value": stop_error_timeout_s,
            "Units": "seconds",
            "Notes": "Timeout duration added after the Stop LR noise period.",
        },
        {
            "Setting": "Stop-error total lockout",
            "Value": stop_error_noise_s + stop_error_timeout_s,
            "Units": "seconds",
            "Notes": "StopErrorNoise_s + StopErrorTimeout_s; used after Stop LR.",
        },
        {
            "Setting": "Stop-signal delay",
            "Value": stop_signal_delay_ms,
            "Units": "milliseconds",
            "Notes": "Saved with each trial for documentation.",
        },
        {
            "Setting": "Response window",
            "Value": response_window_s,
            "Units": "seconds",
            "Notes": "Saved with each trial for documentation.",
        },
        {
            "Setting": "Mouse ID metadata column",
            "Value": mouse_col,
            "Units": "",
            "Notes": "Metadata column used as the mouse identifier.",
        },
        {
            "Setting": "Sex metadata column",
            "Value": sex_col,
            "Units": "",
            "Notes": "Metadata column used for sex grouping.",
        },
        {
            "Setting": "Group metadata column",
            "Value": group_col,
            "Units": "",
            "Notes": "Metadata column used for genotype/group plotting.",
        },
    ])

    # -------------------------
    # STEP 7: EXCEL EXPORT
    # -------------------------
    output_path = os.path.join(save_folder, "StopSig_EXTRAS.xlsx")
    write_outputs(
        output_path,
        trials_all_df,
        summary_df,
        type_summary_df,
        event_counts_df,
        phase_summary_df,
        peri_stop_df,
        pca_results,
        phase_pca_scores_df,
        phase_pca_input_df,
        analysis_settings_df,
        mouse_col,
        sex_col,
        group_col,
        use_phase,
    )

    # -------------------------
    # STEP 8: GRAPH GENERATION
    # -------------------------
    plot_folder = os.path.join(save_folder, "StopSig_Plots")
    create_plots(
        trials_all_df,
        summary_df,
        phase_summary_df,
        peri_stop_df,
        pca_results,
        phase_pca_scores_df,
        plot_folder,
        mouse_col,
        sex_col,
        group_col,
        use_phase,
        color_maps,
        show_plots,
    )

    print(f"\nStopSig workbook saved:\n{output_path}")
    print(f"StopSig plots saved:\n{plot_folder}")

    if errors:
        error_path = os.path.join(save_folder, "StopSig_processing_errors.txt")
        with open(error_path, "w", encoding="utf-8") as error_file:
            error_file.write("\n".join(errors))
        print(f"Some files were skipped. Details saved to:\n{error_path}")


if __name__ == "__main__":
    run_gui()
