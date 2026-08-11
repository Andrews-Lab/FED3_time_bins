import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import colorchooser
from tkinter import filedialog, messagebox
import os
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import seaborn as sns
from tkinter.simpledialog import askstring
from tkinter.simpledialog import askinteger
from datetime import datetime

sns.set_theme(style="white", font_scale=1.2)

# ------------------------------------------------------------
# RUNTIME CONTEXT DEFAULTS
# ------------------------------------------------------------
# Populated by run_gui(); defaults keep imports safe and function definitions valid.
use_phase = False
light_start = "07:00"
light_end = "19:00"
window = 100
peak_window = 11
mouse_col = None
sex_col = None
group_col = None
metadata_df = pd.DataFrame()
metadata_sorted = pd.DataFrame()
ordered_mice = []
plots_folder = None
show_plots = False
use_custom_colors = False
group_colors = {}
sex_colors = {}
display_metric_names = {}
percent_metrics = []
behavior_metrics = []
selected_groups = []
pc1_var = 0.0
pc2_var = 0.0

REQUIRED_COLUMNS = {
    "MM:DD:YYYY hh:mm:ss",
    "Event",
    "Pellet_Count",
    "High_prob_poke",
}

# ------------------------------------------------------------
# GENERAL INPUT AND TIME HELPERS
# ------------------------------------------------------------

def clean_time_input(t):
    if t is None:
        return None

    t = str(t).strip()

    # Handle lazy inputs like "9" or "21"
    if t.isdigit():
        return f"{int(t):02d}:00"

    # Handle "9:0" to "09:00"
    try:
        parts = t.split(":")
        if len(parts) == 2:
            h = int(parts[0])
            m = int(parts[1])
            return f"{h:02d}:{m:02d}"
    except:
        pass

    return t

def validate_time(t):
    try:
        datetime.strptime(t, "%H:%M")
        return True
    except:
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
            "All reconstructed trial timestamps failed to parse. "
            "Check the 'MM:DD:YYYY hh:mm:ss' column."
        )

def identify_phase(timestamp, start, end):
    t = timestamp.time()

    if start < end:
        return "Light" if (t >= start and t < end) else "Dark"
    else:
        return "Light" if (t >= start or t < end) else "Dark"

# ------------------------------------------------------------
# TRIAL RECONSTRUCTION
# ------------------------------------------------------------

def build_trials(
    df,
    use_phase=False,
    light_start="07:00",
    light_end="19:00",
):

    missing = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing:
        raise ValueError(
            "Missing required Bandit columns: " + ", ".join(missing)
        )

    df = df.copy()

    # -------------------------
    # DEFINE TRUE CHOICE EVENTS 
    # -------------------------
    df["Event_clean"] = (
        df["Event"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", "", regex=True)
    )

    # ONLY valid decision events
    is_choice = df["Event_clean"].isin(["Left", "Right"])
    choice_idx = df[is_choice].index.tolist()

    trials = []

    for i, idx in enumerate(choice_idx):

        # -------------------------
        # GET CHOICE
        # -------------------------
        choice = df.loc[idx, "Event_clean"].lower()

        # -------------------------
        # DETERMINE REWARD 
        # -------------------------
        if i < len(choice_idx) - 1:
            next_idx = choice_idx[i + 1]
        else:
            next_idx = len(df)

        # window from this choice up to (but not including) next choice
        window = df.loc[idx:next_idx - 1]

        # use starting pellet count at the moment of choice
        start_count = df.loc[idx, "Pellet_Count"]

        # reward = any increase after the choice within the window
        reward = int((window["Pellet_Count"] > start_count).any())

        # -------------------------
        # OTHER FIELDS
        # -------------------------
        hpp = str(df.loc[idx, "High_prob_poke"]).strip().lower()
        timestamp = str(df.loc[idx, "MM:DD:YYYY hh:mm:ss"]).strip()

        trials.append({
            "Choice": choice,
            "Reward": reward,
            "HighProbSide": hpp,
            "Timestamp": timestamp
        })

    trials_df = pd.DataFrame(trials)

    if trials_df.empty:
        return pd.DataFrame(columns=[
            "Choice","Reward","HighProbSide","Timestamp",
            "Trial","HighProb","Switch","SwitchNumber","Phase"
        ])

    # -------------------------
    # ADD TRIAL NUMBER
    # -------------------------
    trials_df["Trial"] = np.arange(1, len(trials_df) + 1)

    # -------------------------
    # DEFINE HIGH vs LOW PROB
    # -------------------------
    trials_df["HighProb"] = (
        trials_df["Choice"] == trials_df["HighProbSide"]
    )

    # -------------------------
    # SWITCH / REVERSAL DETECTION
    # -------------------------
    trials_df["Switch"] = (
        trials_df["HighProbSide"] != trials_df["HighProbSide"].shift()
    )

    trials_df.loc[0, "Switch"] = False
    trials_df["SwitchNumber"] = trials_df["Switch"].cumsum()

    # -------------------------
    # TIMESTAMP HANDLING
    # -------------------------
    raw_timestamps = trials_df["Timestamp"].copy()
    trials_df["Timestamp"] = parse_timestamps(raw_timestamps)
    validate_parsed_timestamps(
        raw_timestamps,
        trials_df["Timestamp"],
        require_valid=use_phase,
    )

    # -------------------------
    # PHASE ASSIGNMENT
    # -------------------------
    if use_phase:
        start = pd.to_datetime(light_start).time()
        end   = pd.to_datetime(light_end).time()

        valid_timestamp = trials_df["Timestamp"].notna()
        trials_df["Phase"] = pd.Series(pd.NA, index=trials_df.index, dtype="object")
        trials_df.loc[valid_timestamp, "Phase"] = trials_df.loc[valid_timestamp, "Timestamp"].apply(
            identify_phase, start=start, end=end
        )
    else:
        trials_df["Phase"] = "All"

    return trials_df

# ------------------------------------------------------------
# BEHAVIOR, LEARNING, ODDS-RATIO, AND SWITCH METRICS
# ------------------------------------------------------------

def compute_behavior_metrics(df_trials):

    df = df_trials.copy()

    # -------------------------
    # PREVIOUS TRIAL INFO
    # -------------------------
    df["PrevChoice"] = df["Choice"].shift(1)
    df["PrevReward"] = df["Reward"].shift(1)
    df["PrevHighProb"] = df["HighProb"].shift(1)
    df = df.dropna(
        subset=["PrevChoice", "PrevReward", "PrevHighProb"]
    ).copy()
    df["PrevReward"] = df["PrevReward"].astype(bool)


    df["Stay"] = df["Choice"] == df["PrevChoice"]
    df["Shift"] = ~df["Stay"]

    # -------------------------
    # COUNT EVENTS
    # -------------------------
    win_stay  = ((df["Stay"]) & (df["PrevReward"])).sum()
    win_shift = ((df["Shift"]) & (df["PrevReward"])).sum()
    lose_stay  = ((df["Stay"]) & (df["PrevReward"] == False)).sum()
    lose_shift = ((df["Shift"]) & (df["PrevReward"] == False)).sum()

# -------------------------
# STANDARD METRICS
# -------------------------
    winstay  = win_stay / (win_stay + win_shift) if (win_stay + win_shift) > 0 else np.nan
    winshift = win_shift / (win_stay + win_shift) if (win_stay + win_shift) > 0 else np.nan
    losestay = lose_stay / (lose_stay + lose_shift) if (lose_stay + lose_shift) > 0 else np.nan
    loseshift = lose_shift / (lose_stay + lose_shift) if (lose_stay + lose_shift) > 0 else np.nan

    metrics = {
        "WinStay": winstay,
        "WinShift": winshift,
        "LoseStay": losestay,
        "LoseShift": loseshift,
        "TotalTrials": len(df_trials),
        "TotalRewards": df_trials["Reward"].sum(),
        "RewardAcquisition": df_trials["Reward"].mean(),
        "SwitchRate": df["Shift"].mean(),
        "LeftBias": (df_trials["Choice"] == "left").mean(),
        "OutcomeSensitivity": (
            loseshift - winshift
            if not (np.isnan(loseshift) or np.isnan(winshift))
            else np.nan
        ),
        "LearningIndex": (
            ((winstay + loseshift) / 2) * 100
            if not (np.isnan(winstay) or np.isnan(loseshift))
            else np.nan
        )
    }

    # -------------------------
    # HIGH PROB METRICS
    # -------------------------
    hp = df[df["PrevHighProb"] == True]

    if len(hp) > 0:
        hp_ws  = ((hp["Stay"]) & (hp["PrevReward"])).sum()
        hp_wsh = ((hp["Shift"]) & (hp["PrevReward"])).sum()
        hp_ls  = ((hp["Stay"]) & (hp["PrevReward"] == False)).sum()
        hp_lsh = ((hp["Shift"]) & (hp["PrevReward"] == False)).sum()

        hp_winstay = hp_ws / (hp_ws + hp_wsh) if (hp_ws + hp_wsh) > 0 else np.nan
        hp_loseshift = hp_lsh / (hp_ls + hp_lsh) if (hp_ls + hp_lsh) > 0 else np.nan

        metrics["HighProbWinStay"] = hp_winstay
        metrics["HighProbLoseShift"] = hp_loseshift

        metrics["HighProbOutcomeSensitivity"] = (
            hp_loseshift + hp_winstay - 1
            if not (np.isnan(hp_loseshift) or np.isnan(hp_winstay))
            else np.nan
        )

    else:
        metrics["HighProbWinStay"] = np.nan
        metrics["HighProbLoseShift"] = np.nan
        metrics["HighProbOutcomeSensitivity"] = np.nan

    # -------------------------
    # LOW PROB METRICS
    # -------------------------
    lp = df[df["PrevHighProb"] == False]

    if len(lp) > 0:
        lp_ws  = ((lp["Stay"]) & (lp["PrevReward"])).sum()
        lp_wsh = ((lp["Shift"]) & (lp["PrevReward"])).sum()
        lp_ls  = ((lp["Stay"]) & (lp["PrevReward"] == False)).sum()
        lp_lsh = ((lp["Shift"]) & (lp["PrevReward"] == False)).sum()

        lp_winstay = lp_ws / (lp_ws + lp_wsh) if (lp_ws + lp_wsh) > 0 else np.nan
        lp_loseshift = lp_lsh / (lp_ls + lp_lsh) if (lp_ls + lp_lsh) > 0 else np.nan

        metrics["LowProbWinStay"] = lp_winstay
        metrics["LowProbLoseShift"] = lp_loseshift

        metrics["LowProbOutcomeSensitivity"] = (
            lp_loseshift + lp_winstay - 1
            if not (np.isnan(lp_loseshift) or np.isnan(lp_winstay))
            else np.nan
        )

    else:
        metrics["LowProbWinStay"] = np.nan
        metrics["LowProbLoseShift"] = np.nan
        metrics["LowProbOutcomeSensitivity"] = np.nan

    return metrics

def compute_trials_back_OR(df_trials, max_k=5):

    results = []

    for k in range(1, max_k+1):

        temp = df_trials.copy()

        # -------------------------
        # PREVIOUS TRIAL INFO
        # -------------------------
        temp["PrevChoice"] = temp["Choice"].shift(k)
        temp["PrevReward"] = temp["Reward"].shift(k)
        temp = temp.dropna(
            subset=["PrevChoice", "PrevReward"]
        ).copy()
        temp["PrevReward"] = temp["PrevReward"].astype(bool)

        # -------------------------
        # STAY / SHIFT
        # -------------------------
        temp["Stay"] = temp["Choice"] == temp["PrevChoice"]

        # -------------------------
        # COUNT EVENTS 
        # -------------------------
        A = ((temp["Stay"]) & (temp["PrevReward"])).sum()                      # WinStay
        B = ((~temp["Stay"]) & (temp["PrevReward"])).sum()                     # WinShift
        C = ((temp["Stay"]) & (temp["PrevReward"] == False)).sum()             # LoseStay
        D = ((~temp["Stay"]) & (temp["PrevReward"] == False)).sum()            # LoseShift

        # -------------------------
        # ODDS RATIO
        # -------------------------
        if (A + B) == 0 or (C + D) == 0:
            OR = np.nan
        else:
            OR = ((A + 0.5) * (D + 0.5)) / ((B + 0.5) * (C + 0.5))

        results.append({
            "TrialsBack": -k,
            "OddsRatio": OR
        })

    return pd.DataFrame(results)

def run_analysis(
    trials_subset,
    label,
    row,
    mouse_col,
    sex_col,
    group_col,
):

    if len(trials_subset) < 5:
        return None

    or_df = compute_trials_back_OR(trials_subset)
    metrics = compute_behavior_metrics(trials_subset)

    for k, v in metrics.items():
        or_df[k] = v

    or_df["Phase"] = label
    or_df["MouseID"] = row[mouse_col]
    or_df[sex_col] = row[sex_col]
    or_df[group_col] = row[group_col]

    return or_df

def run_learning(
    trials_subset,
    label,
    row,
    window,
    mouse_col,
    sex_col,
    group_col,
):

    if len(trials_subset) < 5:
        return None

    t = trials_subset.copy()

    # -------------------------
    # REWARD EMA (Exponential Moving Average) (performance)
    # -------------------------
    t["RewardEMA"] = t["Reward"].ewm(
        span=window,
        adjust=False
    ).mean()

    # -------------------------
    # PREVIOUS TRIAL VARIABLES
    # -------------------------
    t["PrevChoice"] = t["Choice"].shift(1)
    t["PrevReward"] = t["Reward"].shift(1)

    # Remove first invalid row from shift
    t = t.iloc[1:].copy()
    t["PrevReward"] = t["PrevReward"].astype(bool)

    # -------------------------
    # CUMULATIVE REWARDS
    # -------------------------
    t["CumRewards"] = t["Reward"].cumsum()

    # -------------------------
    # STAY / SHIFT CLASSIFICATION
    # -------------------------
    t["Stay"] = t["Choice"] == t["PrevChoice"]
    t["Shift"] = ~t["Stay"]

    # -------------------------
    # TRIAL-LEVEL STRATEGY EVENTS
    # -------------------------
    t["WinStayTrial"]  = (t["Stay"])  & (t["PrevReward"])
    t["LoseShiftTrial"] = (t["Shift"]) & (~t["PrevReward"])
    t["WinShiftTrial"] = (t["Shift"]) & (t["PrevReward"])   # needed for outcome sensitivity
    t["PrevWinTrial"] = t["PrevReward"]
    t["PrevLossTrial"] = ~t["PrevReward"]

    # -------------------------
    # LEARNING INDEX EMA (Exponential Moving Average) (strategy quality)
    # -------------------------
    win_stay_num = t["WinStayTrial"].ewm(
        span=window,
        adjust=False
    ).mean()

    lose_shift_num = t["LoseShiftTrial"].ewm(
        span=window,
        adjust=False
    ).mean()

    prev_win_den = t["PrevWinTrial"].ewm(
        span=window,
        adjust=False
    ).mean()

    prev_loss_den = t["PrevLossTrial"].ewm(
        span=window,
        adjust=False
    ).mean()

    t["WinStayEMA"] = win_stay_num / prev_win_den.replace(0, np.nan)
    t["LoseShiftEMA"] = lose_shift_num / prev_loss_den.replace(0, np.nan)

    t["LearningIndexEMA"] = (
        (t["WinStayEMA"] + t["LoseShiftEMA"]) / 2
    ) * 100

    # -------------------------
    # OUTCOME SENSITIVITY EMA (Exponential Moving Average)
    # -------------------------
    win_shift_num = t["WinShiftTrial"].ewm(
        span=window,
        adjust=False
    ).mean()

    t["WinShiftEMA"] = win_shift_num / prev_win_den.replace(0, np.nan)

    t["OutcomeSensitivityEMA"] = (
        t["LoseShiftEMA"] - t["WinShiftEMA"]
    )

    # -------------------------
    # OUTPUT
    # -------------------------
    df_out = t[[
        "Trial",
        "CumRewards",
        "RewardEMA",
        "LearningIndexEMA",
        "OutcomeSensitivityEMA"
    ]].copy()

    df_out["Trial"] = np.arange(1, len(df_out) + 1)
    df_out["Phase"] = label
    df_out["MouseID"] = row[mouse_col]
    df_out[sex_col] = row[sex_col]
    df_out[group_col] = row[group_col]

    return df_out

def run_peak_accuracy(
    trials_subset,
    label,
    row,
    switch_window,
    mouse_col,
    sex_col,
    group_col,
    switch_phase=None,
):

    if trials_subset.empty or "Switch" not in trials_subset.columns:
        return None

    t = trials_subset.sort_values("Trial").reset_index(drop=True)

    switch_mask = t["Switch"].fillna(False)

    if switch_phase is not None and "Phase" in t.columns:
        switch_mask = switch_mask & (t["Phase"] == switch_phase)

    switch_positions = np.flatnonzero(switch_mask.to_numpy())

    if len(switch_positions) == 0:
        return None

    rows = []

    for switch_count, switch_pos in enumerate(switch_positions, start=1):

        switch_number = t.loc[switch_pos, "SwitchNumber"]

        for rel_trial in range(-switch_window, switch_window + 1):

            pos = switch_pos + rel_trial

            if pos < 0 or pos >= len(t):
                continue

            trial = t.loc[pos]

            rows.append({
                "RelativeTrial": rel_trial,
                "PeakAccuracy": int(trial["HighProb"]),
                "SwitchNumber": switch_number,
                "SwitchCount": switch_count,
                "Phase": label,
                "MouseID": row[mouse_col],
                sex_col: row[sex_col],
                group_col: row[group_col]
            })

    if len(rows) == 0:
        return None

    return pd.DataFrame(rows)

# ------------------------------------------------------------
# OUTPUT AND SCALING HELPERS
# ------------------------------------------------------------

def scale_metric_columns(df, metrics, factor=100):
    out = df.copy()

    for metric in metrics:
        if metric in out.columns:
            out[metric] = out[metric] * factor

    return out

def scale_metric_rows(df, metrics, factor=100):
    out = df.copy()

    for metric in metrics:
        if metric in out.index:
            value_cols = out.columns[1:]
            out.loc[metric, value_cols] = out.loc[metric, value_cols] * factor

    return out

def scale_prism_value_columns(df, factor=100):
    out = df.copy()

    for col in out.columns[1:]:
        out[col] = out[col].map(
            lambda x: x * factor
            if isinstance(x, (int, float, np.integer, np.floating))
            and not pd.isna(x)
            else x
        )

    return out

def make_peak_accuracy_table(peak_df):

    if peak_df.empty:
        return pd.DataFrame()

    pivot_peak = peak_df.pivot_table(
        index="RelativeTrial",
        columns="MouseID",
        values="PeakAccuracy",
        aggfunc="mean"
    )

    if pivot_peak.empty:
        return pd.DataFrame()

    pivot_peak.columns = pivot_peak.columns.astype(str)

    valid_mice_peak = [
        m for m in ordered_mice
        if m in pivot_peak.columns
    ]

    if len(valid_mice_peak) == 0:
        return pd.DataFrame()

    pivot_peak = pivot_peak[valid_mice_peak]

    pivot_peak = pivot_peak.reset_index()
    pivot_peak.columns = ["Trials around switch"] + list(pivot_peak.columns[1:])

    mouse_row_peak = [""] + valid_mice_peak

    geno_row_peak = [""] + [
        metadata_sorted.loc[
            metadata_sorted[mouse_col] == m,
            group_col
        ].values[0]
        for m in valid_mice_peak
    ]

    sex_row_peak = [""] + [
        metadata_sorted.loc[
            metadata_sorted[mouse_col] == m,
            sex_col
        ].values[0]
        for m in valid_mice_peak
    ]

    meta_peak = pd.DataFrame(
        [mouse_row_peak, geno_row_peak, sex_row_peak],
        index=["Mouse ID", group_col, sex_col],
        columns=pivot_peak.columns
    )

    window_row_peak = ["Window"] + [peak_window] * len(valid_mice_peak)

    meta_peak = pd.concat([
        pd.DataFrame([window_row_peak], columns=pivot_peak.columns),
        meta_peak
    ])

    return pd.concat([
        meta_peak,
        pivot_peak
    ])

# ------------------------------------------------------------
# PLOT COLOUR AND FILE HELPERS
# ------------------------------------------------------------

def get_plot_color(grp, grouping_col):

    if not use_custom_colors:
        return None

    if grouping_col == group_col:
        return group_colors.get(grp, None)

    if grouping_col == sex_col:
        return sex_colors.get(grp, None)

    return None

def get_plot_subfolder(filename):

    filename_lower = filename.lower()

    if filename_lower.startswith("pca_"):
        return "PCA"
    if "heatmap" in filename_lower or "correlation" in filename_lower:
        return "Heatmaps"
    if (
        filename_lower.startswith("peakaccuracy")
        or filename_lower.startswith("peak_accuracy")
        or filename_lower.startswith("peritrial")
    ):
        return "PeriTrial"
    if filename_lower.startswith("stacked_"):
        return "Stacked"
    if filename_lower.endswith("_dark.png"):
        return "Dark"
    if filename_lower.endswith("_light.png"):
        return "Light"

    return "All"

def get_plot_path(filename):

    subfolder = get_plot_subfolder(filename)
    destination = os.path.join(plots_folder, subfolder)
    os.makedirs(destination, exist_ok=True)
    return os.path.join(destination, filename)

# ------------------------------------------------------------
# CORE PLOTTING FUNCTIONS
# ------------------------------------------------------------

def plot_or(data, group_col, title, filename):

    plt.figure()

    for grp, d in data.groupby(group_col):

        color = get_plot_color(grp, group_col)

        mean = d.groupby("TrialsBack")["OddsRatio"].mean()
        sem  = d.groupby("TrialsBack")["OddsRatio"].sem()

        plt.plot(
            mean.index,
            mean.values,
            label=grp,
            color=color
        )

        plt.fill_between(
            mean.index,
            mean-sem,
            mean+sem,
            alpha=0.2,
            color=color
        )

    plt.axhline(1, linestyle="--")
    plt.xlabel("Trials Back")
    plt.ylabel("Odds Ratio")
    plt.title(title)
    plt.legend()

    plot_path = get_plot_path(filename)
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_or_by_phase(data, group_col, base_title, base_filename):

    for phase, d_phase in data.groupby("Phase"):

        plt.figure()

        for grp, d in d_phase.groupby(group_col):

            color = get_plot_color(grp, group_col)

            mean = d.groupby("TrialsBack")["OddsRatio"].mean()
            sem  = d.groupby("TrialsBack")["OddsRatio"].sem()

            plt.plot(
                mean.index,
                mean.values,
                label=grp,
                color=color
            )

            plt.fill_between(
                mean.index,
                mean-sem,
                mean+sem,
                alpha=0.2,
                color=color
            )

        plt.axhline(1, linestyle="--")
        plt.xlabel("Trials Back")
        plt.ylabel("Odds Ratio")
        plt.title(f"{base_title} ({phase})")
        plt.legend()

        plot_path = get_plot_path(f"{base_filename}_{phase}.png")
        plt.savefig(plot_path, dpi=300, bbox_inches="tight")

        if show_plots:
            plt.show()
        else:
            plt.close()

def plot_peak_accuracy(data, group_col, title, filename):

    plt.figure()

    for grp, d in data.groupby(group_col):

        color = get_plot_color(grp, group_col)

        mean = d.groupby("RelativeTrial")["PeakAccuracy"].mean()
        sem  = d.groupby("RelativeTrial")["PeakAccuracy"].sem().fillna(0)

        plt.plot(
            mean.index,
            mean.values,
            label=grp,
            color=color
        )

        plt.fill_between(
            mean.index,
            mean-sem,
            mean+sem,
            alpha=0.2,
            color=color
        )

    plt.axvline(0, linestyle="--", color="black")
    plt.ylim(0, 1)
    plt.xlabel("Trials around switch")
    plt.ylabel("Peak Accuracy")
    plt.title(title)
    plt.legend()

    plot_path = get_plot_path(filename)
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_cum_rewards(data, group_col, title, filename):

    plt.figure()

    for grp, d in data.groupby(group_col):

        color = get_plot_color(grp, group_col)

        mean = d.groupby("Trial")["CumRewards"].mean()
        sem  = d.groupby("Trial")["CumRewards"].sem().fillna(0)

        plt.plot(
            mean.index,
            mean.values,
            label=grp,
            color=color
        )

        plt.fill_between(
            mean.index,
            mean-sem,
            mean+sem,
            alpha=0.2,
            color=color
        )

    plt.xlabel("Trial")
    plt.ylabel("Cumulative Wins")
    plt.title(title)
    plt.legend()

    plot_path = get_plot_path(filename)

    plt.savefig(
        plot_path,
        dpi=300,
        bbox_inches="tight"
    )

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_reward_acquisition(data, group_col, title, filename):

    plt.figure()

    for grp, d in data.groupby(group_col):

        color = get_plot_color(grp, group_col)

        mean = d.groupby("Trial")["RewardEMA"].mean() * 100
        sem  = d.groupby("Trial")["RewardEMA"].sem().fillna(0) * 100

        plt.plot(
            mean.index,
            mean.values,
            label=grp,
            color=color
        )

        plt.fill_between(
            mean.index,
            mean-sem,
            mean+sem,
            alpha=0.2,
            color=color
        )

    plt.xlabel("Trial")
    plt.ylabel("Win Rate EMA (%)")
    plt.title(title)
    plt.legend()

    plot_path = get_plot_path(filename)
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_learning_index(data, group_col, title, filename):

    plt.figure()

    for grp, d in data.groupby(group_col):

        color = get_plot_color(grp, group_col)

        mean = d.groupby("Trial")["LearningIndexEMA"].mean()
        sem  = d.groupby("Trial")["LearningIndexEMA"].sem().fillna(0)

        plt.plot(
            mean.index,
            mean.values,
            label=grp,
            color=color
        )

        plt.fill_between(
            mean.index,
            mean-sem,
            mean+sem,
            alpha=0.2,
            color=color
        )

    plt.xlabel("Trial")
    plt.ylabel("Learning Index (%)")
    plt.title(title)
    plt.legend()

    plot_path = get_plot_path(filename)
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_outcome_sensitivity(data, group_col, title, filename):

    plt.figure()

    for grp, d in data.groupby(group_col):

        color = get_plot_color(grp, group_col)

        mean = d.groupby("Trial")["OutcomeSensitivityEMA"].mean()
        sem  = d.groupby("Trial")["OutcomeSensitivityEMA"].sem().fillna(0)

        plt.plot(
            mean.index,
            mean.values,
            label=grp,
            color=color
        )

        plt.fill_between(
            mean.index,
            mean-sem,
            mean+sem,
            alpha=0.2,
            color=color
        )


    plt.axhline(0, linestyle="--", color="black")

    plt.xlabel("Trial")
    plt.ylabel("Outcome Sensitivity (EMA)")
    plt.title(title)
    plt.legend()

    plot_path = get_plot_path(filename)
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_stacked_behavior(
    data,
    group_col,
    metric,
    metric_ylabel,
    title,
    filename
):

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(8,8),
        sharex=True
    )

    # =================================================
    # TOP PANEL - CUMULATIVE REWARDS
    # =================================================
    ax1 = axes[0]

    for grp, d in data.groupby(group_col):

        color = get_plot_color(grp, group_col)

        mean = d.groupby("Trial")["CumRewards"].mean()
        sem  = d.groupby("Trial")["CumRewards"].sem().fillna(0)

        ax1.plot(
            mean.index,
            mean.values,
            label=grp,
            color=color
        )

        ax1.fill_between(
            mean.index,
            mean-sem,
            mean+sem,
            alpha=0.2,
            color=color
        )

    ax1.set_ylabel("Cumulative Wins")
    ax1.set_title(title)
    ax1.legend()

    # =================================================
    # BOTTOM PANEL - SELECTED METRIC
    # =================================================
    ax2 = axes[1]

    for grp, d in data.groupby(group_col):

        color = get_plot_color(grp, group_col)

        mean = d.groupby("Trial")[metric].mean()
        sem  = d.groupby("Trial")[metric].sem().fillna(0)

        ax2.plot(
            mean.index,
            mean.values,
            label=grp,
            color=color
        )

        ax2.fill_between(
            mean.index,
            mean-sem,
            mean+sem,
            alpha=0.2,
            color=color
        )

    if metric == "OutcomeSensitivityEMA":
        ax2.axhline(0, linestyle="--", color="black")

    ax2.set_xlabel("Trial")
    ax2.set_ylabel(metric_ylabel)

    plt.tight_layout()

    plot_path = get_plot_path(filename)

    plt.savefig(
        plot_path,
        dpi=300,
        bbox_inches="tight"
    )

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_stacked_learning(data, group_col, title, filename):

    plot_stacked_behavior(
        data=data,
        group_col=group_col,
        metric="LearningIndexEMA",
        metric_ylabel="Learning Index (%)",
        title=title,
        filename=filename
    )

def plot_stacked_outcome(data, group_col, title, filename):

    plot_stacked_behavior(
        data=data,
        group_col=group_col,
        metric="OutcomeSensitivityEMA",
        metric_ylabel="Outcome Sensitivity",
        title=title,
        filename=filename
    )

def display_metric_label(metric):
    return display_metric_names.get(metric, metric)

def build_behavior_wide_table(results, id_columns, metric_columns):

    available_metrics = [
        column for column in metric_columns
        if column in results.columns
    ]

    if results.empty:
        empty = pd.DataFrame(columns=id_columns + available_metrics)
        return empty.copy(), empty

    metrics = (
        results
        .groupby(id_columns, dropna=False)
        .first()[available_metrics]
        .reset_index()
    )

    metrics["MouseID"] = metrics["MouseID"].astype(str)

    if not {"TrialsBack", "OddsRatio"}.issubset(results.columns):
        return metrics.copy(), metrics

    odds_ratios = results.pivot_table(
        index=id_columns,
        columns="TrialsBack",
        values="OddsRatio"
    ).reset_index()

    if odds_ratios.empty:
        return metrics.copy(), metrics

    odds_ratios["MouseID"] = odds_ratios["MouseID"].astype(str)
    odds_ratios.columns = [
        f"OR_{int(column)}" if isinstance(column, (int, float))
        else column
        for column in odds_ratios.columns
    ]

    wide = pd.merge(
        metrics,
        odds_ratios,
        on=id_columns,
        how="left"
    )

    return wide, metrics

def plot_behavior_metric_stripplot(
    data,
    metric,
    x_col,
    title,
    filename,
    hue_col=None
):

    required_columns = [metric, x_col]

    if hue_col:
        required_columns.append(hue_col)

    missing_columns = [
        column for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        print(
            f"Skipping {filename}: missing columns "
            f"{', '.join(missing_columns)}."
        )
        return

    plot_data = data.copy()
    plot_data[metric] = pd.to_numeric(plot_data[metric], errors="coerce")

    if metric in percent_metrics:
        plot_data[metric] = plot_data[metric] * 100

    plot_data = plot_data.dropna(subset=required_columns)

    if plot_data.empty or plot_data[x_col].nunique() == 0:
        print(f"Skipping {filename}: no valid data to plot.")
        return

    if hue_col and plot_data[hue_col].nunique() == 0:
        print(f"Skipping {filename}: no valid {hue_col} values to plot.")
        return

    plt.figure(figsize=(8,6))

    sns.stripplot(
        data=plot_data,
        x=x_col,
        y=metric,
        hue=hue_col,
        dodge=True if hue_col else False,
        size=8,
        palette=sex_colors if (
            use_custom_colors and hue_col == sex_col
        ) else None
    )

    plt.title(title)
    plt.ylabel(display_metric_label(metric))

    if x_col == "Combined_Group":
        plt.xticks(rotation=45)

    plot_path = get_plot_path(filename)

    plt.savefig(
        plot_path,
        dpi=300,
        bbox_inches="tight"
    )

    if show_plots:
        plt.show()
    else:
        plt.close()

def format_heatmap_cell(x):

    if pd.isna(x):
        return ""

    ax = abs(float(x))

    if ax >= 100:
        return f"{x:.0f}"
    elif ax >= 10:
        return f"{x:.1f}"
    else:
        return f"{x:.2f}"

def plot_group_sex_behavior_heatmap(data, title, filename):

    heatmap_metrics = [
        metric for metric in behavior_metrics
        if metric in data.columns
    ]

    if len(heatmap_metrics) == 0:
        print(f"Skipping {filename}: no behavior metrics available.")
        return

    plot_data = data.copy()

    for metric in heatmap_metrics:
        plot_data[metric] = pd.to_numeric(
            plot_data[metric],
            errors="coerce"
        )

        if metric in percent_metrics:
            plot_data[metric] = plot_data[metric] * 100

    grouped = (
        plot_data
        .groupby([group_col, sex_col], dropna=False)[heatmap_metrics]
        .mean()
    )

    if grouped.empty:
        print(f"Skipping {filename}: no group/sex data available.")
        return

    grouped.index = [
        f"{group} | {sex}"
        for group, sex in grouped.index
    ]

    grouped = grouped.rename(columns=display_metric_names)

    annot_data = grouped.applymap(format_heatmap_cell)
    heatmap_scaled = grouped.copy()

    for col in heatmap_scaled.columns:

        col_min = heatmap_scaled[col].min()
        col_max = heatmap_scaled[col].max()

        if pd.isna(col_min) or pd.isna(col_max):
            heatmap_scaled[col] = 0
        elif col_max == col_min:
            heatmap_scaled[col] = 0.5
        else:
            heatmap_scaled[col] = (
                (heatmap_scaled[col] - col_min)
                / (col_max - col_min)
            )

    fig_width = max(12, len(heatmap_scaled.columns) * 0.9)
    fig_height = max(4, len(heatmap_scaled.index) * 0.7)

    plt.figure(figsize=(fig_width, fig_height))

    sns.heatmap(
        heatmap_scaled,
        annot=annot_data,
        fmt="",
        cmap="Blues",
        linewidths=0.5,
        linecolor="gray",
        cbar=True
    )

    plt.title(title)
    plt.xlabel("")
    plt.ylabel("")
    plt.xticks(rotation=60, ha="right")
    plt.yticks(rotation=0)

    plot_path = get_plot_path(filename)

    plt.savefig(
        plot_path,
        dpi=300,
        bbox_inches="tight"
    )

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_pca_joint(data, group_col, title, filename):

    # --------------------------------------------------------
    # Match KDE colours to selected plot colours
    # --------------------------------------------------------

    palette = None

    if use_custom_colors:
        groups = data[group_col].dropna().unique()
        candidate_palette = {
            group: get_plot_color(group, group_col)
            for group in groups
        }

        if candidate_palette and all(candidate_palette.values()):
            palette = candidate_palette

    # --------------------------------------------------------
    # Create JointGrid
    # --------------------------------------------------------

    g = sns.JointGrid(
        data=data,
        x="PC1",
        y="PC2",
        height=6
    )

    # --------------------------------------------------------
    # Scatter
    # --------------------------------------------------------

    for grp, d in data.groupby(group_col):

        color = get_plot_color(grp, group_col)

        g.ax_joint.scatter(
            d["PC1"],
            d["PC2"],
            label=grp,
            s=70,
            alpha=0.7,
            color=color
        )

    # --------------------------------------------------------
    # Top KDE
    # --------------------------------------------------------

    sns.kdeplot(
        data=data,
        x="PC1",
        hue=group_col,
        palette=palette,
        ax=g.ax_marg_x,
        fill=True,
        alpha=0.2,
        common_norm=False
    )

    # --------------------------------------------------------
    # Side KDE
    # --------------------------------------------------------

    sns.kdeplot(
        data=data,
        y="PC2",
        hue=group_col,
        palette=palette,
        ax=g.ax_marg_y,
        fill=True,
        alpha=0.2,
        common_norm=False
    )

    # --------------------------------------------------------
    # Axes lines
    # --------------------------------------------------------

    g.ax_joint.axhline(
        0,
        linestyle="--",
        alpha=0.5
    )

    g.ax_joint.axvline(
        0,
        linestyle="--",
        alpha=0.5
    )

    # --------------------------------------------------------
    # Labels
    # --------------------------------------------------------

    g.ax_joint.set_xlabel(
        f"PC1 ({pc1_var:.1f}%)"
    )

    g.ax_joint.set_ylabel(
        f"PC2 ({pc2_var:.1f}%)"
    )

    # --------------------------------------------------------
    # Legend
    # --------------------------------------------------------

    g.ax_joint.legend(
        title=group_col
    )

    fig = g.figure

    fig.suptitle(
        title,
        y=1.02
    )

    fig.tight_layout(
        rect=[0, 0, 1, 0.97]
    )

    save_path = get_plot_path(filename)

    fig.savefig(
        save_path,
        dpi=300,
        bbox_inches="tight"
    )

    if show_plots:
        plt.show()
    else:
        plt.close(fig)

# ------------------------------------------------------------
# REUSABLE PLOT VARIANT HELPERS
# ------------------------------------------------------------

def plot_split_second_third(data, split_col, compare_col, plot_func, prefix):

    for val in sorted(data[split_col].dropna().unique()):

        subset = data[data[split_col] == val]

        if subset[compare_col].nunique() < 2:
            print(f"Skipping {val} - only one group in {compare_col}")
            continue

        safe_val = str(val).strip().replace(" ", "_").replace("/", "_").replace("\n", "").replace("\r", "")

        plot_func(
            subset,
            group_col=compare_col,
            title=f"{prefix} ({compare_col} within {split_col} = {val})",
            filename=f"{prefix}_{split_col}_{safe_val}.png"
        )

def plot_split_second_third_phase(data, split_col, compare_col, plot_func, prefix):

    if "Phase" not in data.columns:
        print(f"Skipping {prefix}: no Phase column available.")
        return

    for phase, d_phase in data.groupby("Phase"):

        for val in sorted(d_phase[split_col].dropna().unique()):

            subset = d_phase[d_phase[split_col] == val]

            if subset[compare_col].nunique() < 2:
                print(f"Skipping {val} ({phase}) - only one group in {compare_col}")
                continue

            safe_val = str(val).strip().replace(" ", "_").replace("/", "_")

            plot_func(
                subset,
                group_col=compare_col,
                title=f"{prefix} ({compare_col} within {split_col} = {val}, {phase})",
                filename=f"{prefix}_{split_col}_{safe_val}_{phase}.png"
            )

# ------------------------------------------------------------
# MAIN GUI AND ANALYSIS WORKFLOW
# ------------------------------------------------------------
def run_gui():
    global use_phase, light_start, light_end, window, peak_window, mouse_col, sex_col, group_col
    global metadata_df, metadata_sorted, ordered_mice, plots_folder, show_plots, use_custom_colors, group_colors
    global sex_colors, display_metric_names, percent_metrics, behavior_metrics, selected_groups, pc1_var, pc2_var

    # -------------------------
    # ROOT SETUP AND FILE SELECTION
    # -------------------------

    root = tk.Tk()

    root.withdraw()

    file_paths = filedialog.askopenfilenames(
        title="Select FED3 Bandit CSV files",
        filetypes=[("CSV files", "*.csv")]
    )

    if not file_paths:
        root.destroy()
        return

    selected_names = [os.path.basename(path) for path in file_paths]
    if len(selected_names) != len(set(selected_names)):
        messagebox.showerror(
            "Duplicate Filenames",
            "Two selected files have the same basename. Rename one file or "
            "process the folders separately so metadata matching is unambiguous.",
        )
        root.destroy()
        return

    file_map = {os.path.basename(f): f for f in file_paths}

    save_folder = os.path.dirname(file_paths[0])

    # -------------------------
    # PHASE SETTINGS
    # -------------------------

    use_phase = messagebox.askyesno(
        "Light/Dark Analysis",
        "Do you want to split data by Light/Dark cycle?"
    )

    light_start = "07:00"
    light_end = "19:00"

    if use_phase:
        light_start = askstring(
            "Light Cycle",
            "Enter LIGHT START time (24h HH:MM)\nExample: 07:00",
            initialvalue="07:00"
        )

        light_end = askstring(
            "Light Cycle",
            "Enter LIGHT END time (24h HH:MM)\nExample: 19:00",
            initialvalue="19:00"
        )

        # Clean inputs
        light_start = clean_time_input(light_start)
        light_end   = clean_time_input(light_end)

        # Check cancel
        if light_start is None or light_end is None:
            messagebox.showwarning("Cancelled", "Light/Dark not set. Exiting.")
            root.destroy()
            return

        # Validate format
        if not validate_time(light_start) or not validate_time(light_end):
            messagebox.showerror(
                "Invalid Time Format",
                "Please enter time in HH:MM format (e.g. 07:00 or 19:00)"
            )
            root.destroy()
            return

    # -------------------------
    # METADATA INPUT
    # -------------------------

    use_existing = messagebox.askyesno(
        "Metadata",
        "Do you have an existing metadata file?"
    )

    metadata_df = None

    if use_existing:
        meta_file = filedialog.askopenfilename(
            title="Select Metadata File",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not meta_file:
            root.destroy()
            return
        try:
            metadata_df = pd.read_excel(meta_file)
        except Exception as error:
            messagebox.showerror("Metadata Error", str(error))
            root.destroy()
            return

        metadata_df = metadata_df.apply(
            lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x)
        )

    else:
        meta_window = tk.Toplevel()
        meta_window.title("Enter Metadata")
        meta_window.geometry("700x500")

        canvas = tk.Canvas(meta_window)
        scrollbar = tk.Scrollbar(meta_window, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):

            if event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")

            elif event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

        headers = ["Filename", "Mouse ID", "Sex", "Genotype"]
        header_entries = {}

        for col, header in enumerate(headers):
            if header == "Filename":
                tk.Label(frame, text=header, font=("Arial",10,"bold")).grid(row=0,column=col)
            else:
                e = tk.Entry(frame)
                e.insert(0, header)
                e.grid(row=0,column=col)
                header_entries[col] = e

        rows = []

        for i, fname in enumerate(file_map.keys()):
            tk.Label(frame, text=fname).grid(row=i+1, column=0)

            m = tk.Entry(frame); m.grid(row=i+1,column=1)
            s = tk.Entry(frame); s.grid(row=i+1,column=2)
            g = tk.Entry(frame); g.grid(row=i+1,column=3)

            rows.append({"file":fname,"mouse":m,"sex":s,"geno":g})

        def collect():
            data = []

            mouse_h = header_entries[1].get()
            sex_h   = header_entries[2].get()
            geno_h  = header_entries[3].get()

            for r in rows:
                data.append({
                    "Filename": r["file"],
                    mouse_h: r["mouse"].get(),
                    sex_h: r["sex"].get(),
                    geno_h: r["geno"].get()
                })

            global metadata_df
            metadata_df = pd.DataFrame(data)

            metadata_df = metadata_df.apply(
                lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x)
            )

            metadata_df.to_excel(os.path.join(save_folder, "Bandit_Metadata.xlsx"), index=False)

            meta_window.destroy()

        tk.Button(frame, text="Continue", command=collect)\
            .grid(row=len(rows)+2, column=0, columnspan=4)

        root.wait_window(meta_window)

    if metadata_df is None or metadata_df.empty:
        messagebox.showwarning("No Metadata", "No metadata was supplied.")
        root.destroy()
        return

    if "Filename" not in metadata_df.columns:
        messagebox.showerror(
            "Metadata Error",
            "The metadata file must contain a Filename column.",
        )
        root.destroy()
        return

    meta_cols = [c for c in metadata_df.columns if c != "Filename"]

    if len(meta_cols) < 3:
        messagebox.showerror(
            "Metadata Error",
            "Metadata needs mouse ID, sex, and group/genotype columns.",
        )
        root.destroy()
        return

    if any(not str(column).strip() for column in meta_cols[:3]):
        messagebox.showerror(
            "Metadata Error",
            "The first three metadata headers after Filename cannot be blank.",
        )
        root.destroy()
        return

    mouse_col = meta_cols[0]

    sex_col   = meta_cols[1]

    group_col = meta_cols[2]

    window = askinteger(
        "EMA Smoothing Window",
        "Enter smoothing window (number of trials):\n\n(Applies to Win Rate + Learning Index + Outcome Sensitivity)",
        initialvalue=100,
        minvalue=1
    )

    # -------------------------
    # ANALYSIS AND PLOT SETTINGS
    # -------------------------

    if window is None:
        messagebox.showwarning("Cancelled", "No smoothing window selected. Exiting.")
        root.destroy()
        return

    peak_window = askinteger(
        "Peak Accuracy Window",
        "Enter peak accuracy window (number of trials on each side of a switch):\n\n"
        "Example: 11 gives -11 to +11 trials around each switch.",
        initialvalue=11,
        minvalue=1
    )

    if peak_window is None:
        messagebox.showwarning("Cancelled", "No peak accuracy window selected. Exiting.")
        root.destroy()
        return

    create_stacked = messagebox.askyesno(
        "Stacked Behavioral Plots",
        "Create stacked behavioral trajectory plots?\n\n"
        "This will generate:\n"
        "- Cumulative Wins + Learning Index\n"
        "- Cumulative Wins + Outcome Sensitivity"
    )

    # -------------------------
    # PROCESS INDIVIDUAL FILES
    # -------------------------

    all_learning = []              # Light + Dark

    all_results = []               # Light + Dark

    all_peak_accuracy = []         # Light + Dark

    all_learning_combined = []     # All session

    all_results_combined = []      # All session

    all_peak_accuracy_combined = [] # All session

    processing_errors = []

    for _, row in metadata_df.iterrows():
        filename = str(row["Filename"]).strip()
        if filename not in file_map:
            processing_errors.append(
                f"{filename}: not among the selected CSV files"
            )
            continue

        try:

            df = pd.read_csv(file_map[filename], low_memory=False)

            trials = build_trials(
                df,
                use_phase=use_phase,
                light_start=light_start,
                light_end=light_end,
            )

            # --------------------------------------------------------
            # CREATE LIGHT / DARK SUBSETS
            # --------------------------------------------------------

            if use_phase:

                trials_light = trials[
                    trials["Phase"] == "Light"
                ].copy()

                trials_dark = trials[
                    trials["Phase"] == "Dark"
                ].copy()

            # --------------------------------------------------------
            # LEARNING ANALYSIS
            # --------------------------------------------------------

            if use_phase:

                # ALL SESSION
                l_all = run_learning(
                    trials, "All", row, window, mouse_col, sex_col, group_col
                )

                if l_all is not None:
                    all_learning_combined.append(l_all)

                # LIGHT
                l_light = run_learning(
                    trials_light,
                    "Light",
                    row,
                    window,
                    mouse_col,
                    sex_col,
                    group_col,
                )

                if l_light is not None:
                    all_learning.append(l_light)

                # DARK
                l_dark = run_learning(
                    trials_dark,
                    "Dark",
                    row,
                    window,
                    mouse_col,
                    sex_col,
                    group_col,
                )

                if l_dark is not None:
                    all_learning.append(l_dark)

            else:

                l = run_learning(
                    trials, "All", row, window, mouse_col, sex_col, group_col
                )

                if l is not None:
                    all_learning.append(l)

            # --------------------------------------------------------
            # BEHAVIOR METRICS + ODDS RATIO
            # --------------------------------------------------------

            if use_phase:

                # ALL SESSION
                res_all = run_analysis(
                    trials,
                    "All",
                    row,
                    mouse_col,
                    sex_col,
                    group_col,
                )

                if res_all is not None:
                    all_results_combined.append(res_all)

                # LIGHT
                res_light = run_analysis(
                    trials_light,
                    "Light",
                    row,
                    mouse_col,
                    sex_col,
                    group_col,
                )

                if res_light is not None:
                    all_results.append(res_light)

                # DARK
                res_dark = run_analysis(
                    trials_dark,
                    "Dark",
                    row,
                    mouse_col,
                    sex_col,
                    group_col,
                )

                if res_dark is not None:
                    all_results.append(res_dark)

            else:

                res = run_analysis(
                    trials,
                    "All",
                    row,
                    mouse_col,
                    sex_col,
                    group_col,
                )

                if res is not None:
                    all_results.append(res)

            # --------------------------------------------------------
            # PEAK / PERI-SWITCH ACCURACY
            # --------------------------------------------------------

            if use_phase:

                pa_all = run_peak_accuracy(
                    trials,
                    "All",
                    row,
                    switch_window=peak_window,
                    mouse_col=mouse_col,
                    sex_col=sex_col,
                    group_col=group_col,
                )

                if pa_all is not None:
                    all_peak_accuracy_combined.append(pa_all)

                pa_light = run_peak_accuracy(
                    trials,
                    "Light",
                    row,
                    switch_window=peak_window,
                    mouse_col=mouse_col,
                    sex_col=sex_col,
                    group_col=group_col,
                    switch_phase="Light"
                )

                if pa_light is not None:
                    all_peak_accuracy.append(pa_light)

                pa_dark = run_peak_accuracy(
                    trials,
                    "Dark",
                    row,
                    switch_window=peak_window,
                    mouse_col=mouse_col,
                    sex_col=sex_col,
                    group_col=group_col,
                    switch_phase="Dark"
                )

                if pa_dark is not None:
                    all_peak_accuracy.append(pa_dark)

            else:

                pa = run_peak_accuracy(
                    trials,
                    "All",
                    row,
                    switch_window=peak_window,
                    mouse_col=mouse_col,
                    sex_col=sex_col,
                    group_col=group_col,
                )

                if pa is not None:
                    all_peak_accuracy.append(pa)
        except Exception as error:
            processing_errors.append(f"{filename}: {error}")
            continue

    required_outputs_available = bool(all_results and all_learning)
    if use_phase:
        required_outputs_available = (
            required_outputs_available
            and bool(all_results_combined)
            and bool(all_learning_combined)
        )

    if not required_outputs_available:
        processing_errors.append(
            "No analyzable output: at least five valid trials are required "
            "for each requested analysis scope."
        )
        error_path = os.path.join(save_folder, "Bandit_processing_errors.txt")
        with open(error_path, "w", encoding="utf-8") as error_file:
            error_file.write("\n".join(processing_errors))
        messagebox.showwarning(
            "No Data",
            "Bandit analysis could not produce the required outputs.\n\n"
            f"Details were saved to:\n{error_path}",
        )
        root.destroy()
        return

    # -------------------------
    # COMBINE ANALYSIS OUTPUTS
    # -------------------------

    results_df = pd.concat(
        all_results,
        ignore_index=True
    )

    learning_all_df = pd.concat(
        all_learning,
        ignore_index=True
    )

    if use_phase:

        results_combined_df = pd.concat(
            all_results_combined,
            ignore_index=True
        )

        learning_combined_df = pd.concat(
            all_learning_combined,
            ignore_index=True
        )

        peak_accuracy_df = pd.concat(
            all_peak_accuracy,
            ignore_index=True
        ) if all_peak_accuracy else pd.DataFrame()

        peak_accuracy_combined_df = pd.concat(
            all_peak_accuracy_combined,
            ignore_index=True
        ) if all_peak_accuracy_combined else pd.DataFrame()

    else:

        results_combined_df = results_df.copy()
        learning_combined_df = learning_all_df.copy()
        peak_accuracy_df = pd.concat(
            all_peak_accuracy,
            ignore_index=True
        ) if all_peak_accuracy else pd.DataFrame()
        peak_accuracy_combined_df = peak_accuracy_df.copy()

    behavior_metric_columns = [
        "WinStay","LoseShift","LoseStay","WinShift",
        "TotalTrials","TotalRewards","RewardAcquisition","SwitchRate","LeftBias",
        "HighProbWinStay","HighProbLoseShift",
        "LowProbWinStay","LowProbLoseShift",
        "OutcomeSensitivity",
        "HighProbOutcomeSensitivity",
        "LowProbOutcomeSensitivity",
        "LearningIndex"
    ]

    wide_df, metrics_per_mouse = build_behavior_wide_table(
        results_combined_df,
        ["MouseID", sex_col, group_col],
        behavior_metric_columns
    )

    # -------------------------
    # PREPARE PCA AND EXPORT TABLES
    # -------------------------

    phase_wide_df, phase_metrics = build_behavior_wide_table(
        results_df,
        ["MouseID", sex_col, group_col, "Phase"],
        behavior_metric_columns
    )

    or_cols = [c for c in wide_df.columns if c.startswith("OR_")]

    feature_groups = {
        "OR": or_cols,

        "Basic": [
            "WinStay","LoseShift","LoseStay","WinShift"
        ],

        "Extended": [
            "TotalTrials","TotalRewards","RewardAcquisition","SwitchRate","LeftBias",
            "OutcomeSensitivity","LearningIndex"
        ],

        "HighLow": [
            "HighProbWinStay","HighProbLoseShift",
            "LowProbWinStay","LowProbLoseShift",
            "HighProbOutcomeSensitivity",
            "LowProbOutcomeSensitivity"
        ]
    }

    selected_groups = []

    pca_mouse_count = wide_df["MouseID"].nunique()

    if pca_mouse_count >= 2:
        pca_window = tk.Toplevel()
        pca_window.title("Select PCA Feature Groups")
        pca_window.geometry("400x300")

        tk.Label(
            pca_window,
            text="Select feature groups for PCA:",
            font=("Arial", 11, "bold")
        ).pack(pady=10)

        # Checkbox variables
        pca_vars = {
            "OR": tk.BooleanVar(value=True),
            "Basic": tk.BooleanVar(value=True),
            "Extended": tk.BooleanVar(value=True),
            "HighLow": tk.BooleanVar(value=False)
        }

        # Create checkboxes
        for group, var in pca_vars.items():
            tk.Checkbutton(
                pca_window,
                text=group,
                variable=var,
                font=("Arial", 10)
            ).pack(anchor="w", padx=20)

        def confirm_pca_selection():
            global selected_groups
            selected_groups = [
                g for g, v in pca_vars.items() if v.get()
            ]
            pca_window.destroy()

        tk.Button(
            pca_window,
            text="Continue",
            command=confirm_pca_selection
        ).pack(pady=15)

        root.wait_window(pca_window)
    else:
        print(
            f"\nWARNING: Not enough mice for PCA ({pca_mouse_count}). "
            "Skipping PCA."
        )

    feature_cols = []

    for group in selected_groups:
        feature_cols.extend(feature_groups[group])

    feature_cols = list(dict.fromkeys(feature_cols))

    print("\nPCA input features:")

    print(feature_cols)

    if len(feature_cols) == 0:
        print("\nNo PCA features selected - skipping PCA.")

        wide_df["PC1"] = np.nan
        wide_df["PC2"] = np.nan

        loadings = pd.DataFrame(columns=["PC1", "PC2"])
        pca = None
        pc1_var = np.nan
        pc2_var = np.nan
        pca_feature_means = pd.Series(dtype=float)

    else:
        X = wide_df[feature_cols].copy()

        # Handle NaNs (IMPORTANT; PCA DOESN'T WORK WITH NaNs)
        X = X.apply(
            lambda col: col.fillna(col.mean() if not np.isnan(col.mean()) else 0),
            axis=0
        )
        pca_feature_means = X.mean()

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        n_samples = X_scaled.shape[0]

        if n_samples < 2:
            print("\nWARNING: Not enough mice for PCA. Skipping PCA.")

            wide_df["PC1"] = np.nan
            wide_df["PC2"] = np.nan

            loadings = pd.DataFrame(columns=["PC1", "PC2"])
            pca = None
            pc1_var = np.nan
            pc2_var = np.nan
            pca_feature_means = pd.Series(dtype=float)

        else:
            pca = PCA(n_components=2)
            pcs = pca.fit_transform(X_scaled)
            pc1_var = pca.explained_variance_ratio_[0] * 100
            pc2_var = pca.explained_variance_ratio_[1] * 100
            wide_df["PC1"] = pcs[:, 0]
            wide_df["PC2"] = pcs[:, 1]

            loadings = pd.DataFrame(
                pca.components_.T,
                columns=["PC1", "PC2"],
                index=feature_cols
            )

    if pca is not None:
        print("\nExplained variance ratio:")
        print(pca.explained_variance_ratio_)

        print("\nPCA Loadings:")
        print(loadings)
    else:
        print("PCA not performed (no features selected or insufficient data)")

    metadata_sorted = metadata_df.copy()

    metadata_sorted[mouse_col] = metadata_sorted[mouse_col].astype(str)

    metadata_sorted["Mouse_ID_numeric"] = pd.to_numeric(metadata_sorted[mouse_col], errors="coerce")

    metadata_sorted = metadata_sorted.sort_values(
        by=[group_col, sex_col, "Mouse_ID_numeric", mouse_col]
    ).drop(columns=["Mouse_ID_numeric"]).reset_index(drop=True)

    ordered_mice = metadata_sorted[mouse_col].tolist()

    metrics_cols = [
        "WinStay","LoseShift","LoseStay","WinShift",
        "HighProbWinStay","HighProbLoseShift",
        "LowProbWinStay","LowProbLoseShift","TotalTrials",
        "TotalRewards","RewardAcquisition","SwitchRate","LeftBias",
        "OutcomeSensitivity",
        "HighProbOutcomeSensitivity",
        "LowProbOutcomeSensitivity",
        "LearningIndex"
    ]

    metrics_df = metrics_per_mouse[
        ["MouseID", sex_col, group_col] + metrics_cols
    ].copy()

    metrics_df["MouseID"] = metrics_df["MouseID"].astype(str)

    valid_mice = [
        m for m in ordered_mice
        if m in metrics_df["MouseID"].values
    ]

    metrics_df = (
        metrics_df
        .set_index("MouseID")
        .loc[valid_mice]
        .reset_index()
    )

    output_path = os.path.join(save_folder, "Bandit_EXTRAS.xlsx")

    display_metric_names = {
        "TotalRewards": "Total wins",
        "RewardAcquisition": "Win rate (%)",
        "RewardEMA": "Win rate EMA (%)",
        "CumRewards": "Cumulative wins"
    }

    percent_metrics = [
        "RewardAcquisition"
    ]

    pivot_or = results_combined_df.pivot_table(
        index="TrialsBack",
        columns="MouseID",
        values="OddsRatio"
    )

    pivot_or.columns = pivot_or.columns.astype(str)

    pivot_or = pivot_or.sort_index(ascending=False)

    valid_mice = [m for m in ordered_mice if m in pivot_or.columns]

    missing_mice = set(ordered_mice) - set(valid_mice)

    if missing_mice:
        print("\nWARNING: Missing mice in OR results:")
        print(missing_mice)

    pivot_or = pivot_or[valid_mice]

    pivot_or = pivot_or.reset_index()

    pivot_or.columns = ["Trials Back"] + list(pivot_or.columns[1:])

    mouse_row = [""] + valid_mice

    geno_row  = [""] + [metadata_sorted.loc[metadata_sorted[mouse_col]==m, group_col].values[0] for m in valid_mice]

    sex_row   = [""] + [metadata_sorted.loc[metadata_sorted[mouse_col]==m, sex_col].values[0] for m in valid_mice]

    meta_or = pd.DataFrame(
        [mouse_row, geno_row, sex_row],
        index=["Mouse ID", group_col, sex_col],
        columns=pivot_or.columns
    )

    final_or = pd.concat([meta_or, pivot_or])

    pca_features = ["PC1", "PC2"] + feature_cols

    pca_df = wide_df.copy()

    pca_df = pca_df[
        ["MouseID", sex_col, group_col] + pca_features
    ]

    pca_df["MouseID"] = pca_df["MouseID"].astype(str)

    valid_mice = [
        m for m in ordered_mice
        if m in pca_df["MouseID"].values
    ]

    pca_df = (
        pca_df
        .set_index("MouseID")
        .loc[valid_mice]
        .reset_index()
    )

    pca_values = pca_df.set_index("MouseID")[pca_features].T

    pca_values.insert(0, "Metric", pca_values.index)

    mouse_row = [""] + valid_mice

    geno_row = [""] + [
        metadata_sorted.loc[
            metadata_sorted[mouse_col] == m,
            group_col
        ].values[0]
        for m in valid_mice
    ]

    sex_row = [""] + [
        metadata_sorted.loc[
            metadata_sorted[mouse_col] == m,
            sex_col
        ].values[0]
        for m in valid_mice
    ]

    meta_pca = pd.DataFrame(
        [mouse_row, geno_row, sex_row],
        index=["Mouse ID", group_col, sex_col],
        columns=pca_values.columns
    )

    final_pca = pd.concat([meta_pca, pca_values])

    phase_pca_df = pd.DataFrame()

    if use_phase and pca is not None:
        phase_pca_rows = []

        for phase in phase_wide_df["Phase"].dropna().unique():
            df_phase = phase_wide_df[
                phase_wide_df["Phase"] == phase
            ].copy()

            if df_phase.empty:
                continue

            df_phase["MouseID"] = df_phase["MouseID"].astype(str)

            valid_mice_phase = [
                m for m in ordered_mice
                if m in df_phase["MouseID"].values
            ]

            if not valid_mice_phase:
                continue

            df_phase = (
                df_phase
                .set_index("MouseID")
                .loc[valid_mice_phase]
                .reset_index()
            )

            phase_X = df_phase[feature_cols].copy()
            phase_X = phase_X.fillna(pca_feature_means)
            phase_X = phase_X.fillna(0)

            phase_scaled = scaler.transform(phase_X)
            phase_pcs = pca.transform(phase_scaled)

            df_phase = df_phase[
                ["MouseID", sex_col, group_col, "Phase"] + feature_cols
            ].copy()

            df_phase["PC1"] = phase_pcs[:, 0]
            df_phase["PC2"] = phase_pcs[:, 1]

            phase_pca_rows.append(df_phase)

        if phase_pca_rows:
            phase_pca_df = pd.concat(phase_pca_rows, ignore_index=True)

    pivot_learning = learning_combined_df.pivot_table(
        index="Trial",
        columns="MouseID",
        values="RewardEMA"
    )

    pivot_learning.columns = pivot_learning.columns.astype(str)

    valid_mice_learning = [m for m in ordered_mice if m in pivot_learning.columns]

    pivot_learning = pivot_learning[valid_mice_learning]

    pivot_learning = pivot_learning.reset_index()

    pivot_learning.columns = ["Trial"] + list(pivot_learning.columns[1:])

    mouse_row = [""] + valid_mice_learning

    geno_row  = [""] + [
        metadata_sorted.loc[metadata_sorted[mouse_col] == m, group_col].values[0]
        for m in valid_mice_learning
    ]

    sex_row   = [""] + [
        metadata_sorted.loc[metadata_sorted[mouse_col] == m, sex_col].values[0]
        for m in valid_mice_learning
    ]

    meta_learning = pd.DataFrame(
        [mouse_row, geno_row, sex_row],
        index=["Mouse ID", group_col, sex_col],
        columns=pivot_learning.columns
    )

    window_row = ["Window"] + [window]*len(valid_mice_learning)

    meta_learning = pd.concat([
        pd.DataFrame([window_row], columns=pivot_learning.columns),
        meta_learning
    ])

    final_learning = pd.concat([meta_learning, pivot_learning])

    pivot_learning_LI = learning_combined_df.pivot_table(
        index="Trial",
        columns="MouseID",
        values="LearningIndexEMA"
    )

    pivot_learning_LI.columns = pivot_learning_LI.columns.astype(str)

    valid_mice_learning_LI = [m for m in ordered_mice if m in pivot_learning_LI.columns]

    pivot_learning_LI = pivot_learning_LI[valid_mice_learning_LI]

    pivot_learning_LI = pivot_learning_LI.reset_index()

    pivot_learning_LI.columns = ["Trial"] + list(pivot_learning_LI.columns[1:])

    mouse_row_LI = [""] + valid_mice_learning_LI

    geno_row_LI  = [""] + [
        metadata_sorted.loc[metadata_sorted[mouse_col] == m, group_col].values[0]
        for m in valid_mice_learning_LI
    ]

    sex_row_LI   = [""] + [
        metadata_sorted.loc[metadata_sorted[mouse_col] == m, sex_col].values[0]
        for m in valid_mice_learning_LI
    ]

    meta_learning_LI = pd.DataFrame(
        [mouse_row_LI, geno_row_LI, sex_row_LI],
        index=["Mouse ID", group_col, sex_col],
        columns=pivot_learning_LI.columns
    )

    window_row_LI = ["Window"] + [window]*len(valid_mice_learning_LI)

    meta_learning_LI = pd.concat([
        pd.DataFrame([window_row_LI], columns=pivot_learning_LI.columns),
        meta_learning_LI
    ])

    final_learning_LI = pd.concat([meta_learning_LI, pivot_learning_LI])

    pivot_learning_OS = learning_combined_df.pivot_table(
        index="Trial",
        columns="MouseID",
        values="OutcomeSensitivityEMA"
    )

    pivot_learning_OS.columns = pivot_learning_OS.columns.astype(str)

    valid_mice_learning_OS = [m for m in ordered_mice if m in pivot_learning_OS.columns]

    pivot_learning_OS = pivot_learning_OS[valid_mice_learning_OS]

    pivot_learning_OS = pivot_learning_OS.reset_index()

    pivot_learning_OS.columns = ["Trial"] + list(pivot_learning_OS.columns[1:])

    mouse_row_OS = [""] + valid_mice_learning_OS

    geno_row_OS  = [""] + [
        metadata_sorted.loc[metadata_sorted[mouse_col] == m, group_col].values[0]
        for m in valid_mice_learning_OS
    ]

    sex_row_OS   = [""] + [
        metadata_sorted.loc[metadata_sorted[mouse_col] == m, sex_col].values[0]
        for m in valid_mice_learning_OS
    ]

    meta_learning_OS = pd.DataFrame(
        [mouse_row_OS, geno_row_OS, sex_row_OS],
        index=["Mouse ID", group_col, sex_col],
        columns=pivot_learning_OS.columns
    )

    window_row_OS = ["Window"] + [window]*len(valid_mice_learning_OS)

    meta_learning_OS = pd.concat([
        pd.DataFrame([window_row_OS], columns=pivot_learning_OS.columns),
        meta_learning_OS
    ])

    final_learning_OS = pd.concat([meta_learning_OS, pivot_learning_OS])

    pivot_learning_CR = learning_combined_df.pivot_table(
        index="Trial",
        columns="MouseID",
        values="CumRewards"
    )

    pivot_learning_CR.columns = pivot_learning_CR.columns.astype(str)

    valid_mice_learning_CR = [
        m for m in ordered_mice
        if m in pivot_learning_CR.columns
    ]

    pivot_learning_CR = pivot_learning_CR[valid_mice_learning_CR]

    pivot_learning_CR = pivot_learning_CR.reset_index()

    pivot_learning_CR.columns = ["Trial"] + list(pivot_learning_CR.columns[1:])

    mouse_row_CR = [""] + valid_mice_learning_CR

    geno_row_CR = [""] + [
        metadata_sorted.loc[
            metadata_sorted[mouse_col] == m,
            group_col
        ].values[0]
        for m in valid_mice_learning_CR
    ]

    sex_row_CR = [""] + [
        metadata_sorted.loc[
            metadata_sorted[mouse_col] == m,
            sex_col
        ].values[0]
        for m in valid_mice_learning_CR
    ]

    meta_learning_CR = pd.DataFrame(
        [mouse_row_CR, geno_row_CR, sex_row_CR],
        index=["Mouse ID", group_col, sex_col],
        columns=pivot_learning_CR.columns
    )

    final_learning_CR = pd.concat([
        meta_learning_CR,
        pivot_learning_CR
    ])

    final_peak = make_peak_accuracy_table(peak_accuracy_combined_df)

    # -------------------------
    # EXPORT EXCEL WORKBOOK
    # -------------------------

    with pd.ExcelWriter(output_path) as writer:

        # =========================
        # COMBINED (ALL DATA)
        # =========================
        final_or.to_excel(writer, sheet_name="OddsRatio", float_format="%.5f")

        if pca is not None:
            scale_metric_rows(
                final_pca,
                percent_metrics
            ).rename(index=display_metric_names).to_excel(
                writer,
                sheet_name="PCA",
                float_format="%.5f"
            )

        scale_metric_columns(
            metrics_df,
            percent_metrics
        ).rename(columns=display_metric_names).to_excel(
            writer,
            sheet_name="BehaviorMetrics",
            index=False,
            float_format="%.5f"
        )

        if pca is not None:
            loadings.rename(index=display_metric_names).to_excel(
                writer,
                sheet_name="PCA_Loadings",
                float_format="%.5f"
            )

        scale_prism_value_columns(final_learning).to_excel(
            writer,
            sheet_name="WinRateEMA (%)",
            float_format="%.5f"
        )

        final_learning_LI.to_excel(
            writer,
            sheet_name="LearningIndexEMA (%)",
            float_format="%.5f"
        )

        final_learning_OS.to_excel(
            writer,
            sheet_name="OutcomeSensitivityEMA",
            float_format="%.5f"
        )

        final_learning_CR.to_excel(
            writer,
            sheet_name="CumulativeWins",
            float_format="%.5f"
        )

        if not final_peak.empty:
            final_peak.to_excel(
                writer,
                sheet_name="PeakAccuracy",
                float_format="%.5f"
            )

        # =========================
        # PHASE-SPLIT OUTPUTS
        # =========================
        if use_phase:

            # -------------------------
            # ODDS RATIO (PHASE)
            # -------------------------
            for phase in results_df["Phase"].unique():

                df_phase = results_df[results_df["Phase"] == phase]

                pivot = df_phase.pivot_table(
                    index="TrialsBack",
                    columns="MouseID",
                    values="OddsRatio"
                )

                if pivot.empty:
                    continue

                pivot.columns = pivot.columns.astype(str)

                valid_mice_phase = [m for m in ordered_mice if m in pivot.columns]
                pivot = pivot[valid_mice_phase]

                pivot = pivot.reset_index()
                pivot.columns = ["Trials Back"] + list(pivot.columns[1:])

                mouse_row = [""] + valid_mice_phase
                geno_row  = [""] + [
                    metadata_sorted.loc[metadata_sorted[mouse_col] == m, group_col].values[0]
                    for m in valid_mice_phase
                ]
                sex_row   = [""] + [
                    metadata_sorted.loc[metadata_sorted[mouse_col] == m, sex_col].values[0]
                    for m in valid_mice_phase
                ]

                meta = pd.DataFrame(
                    [mouse_row, geno_row, sex_row],
                    index=["Mouse ID", group_col, sex_col],
                    columns=pivot.columns
                )

                final_or_phase = pd.concat([meta, pivot])

                final_or_phase.to_excel(writer, sheet_name=f"OddsRatio_{phase}")


            # -------------------------
            # REWARD ACQUISITION (PHASE)
            # -------------------------
            for phase in learning_all_df["Phase"].unique():

                df_phase = learning_all_df[learning_all_df["Phase"] == phase]

                if df_phase.empty:
                    continue

                pivot = df_phase.pivot_table(
                    index="Trial",
                    columns="MouseID",
                    values="RewardEMA"
                )

                pivot = pivot.sort_index()
                pivot.columns = pivot.columns.astype(str)

                valid_mice_phase = [m for m in ordered_mice if m in pivot.columns]
                pivot = pivot[valid_mice_phase]

                pivot = pivot.reset_index()
                pivot.columns = ["Trial"] + list(pivot.columns[1:])

                mouse_row = [""] + valid_mice_phase
                geno_row = [""] + [
                    metadata_sorted.loc[metadata_sorted[mouse_col] == m, group_col].values[0]
                    for m in valid_mice_phase
                ]
                sex_row = [""] + [
                    metadata_sorted.loc[metadata_sorted[mouse_col] == m, sex_col].values[0]
                    for m in valid_mice_phase
                ]

                meta_learning = pd.DataFrame(
                    [mouse_row, geno_row, sex_row],
                    index=["Mouse ID", group_col, sex_col],
                    columns=pivot.columns
                )

                window_row = ["Window"] + [window] * len(valid_mice_phase)

                meta_learning = pd.concat([
                    pd.DataFrame([window_row], columns=pivot.columns),
                    meta_learning
                ])

                final_phase_learning = pd.concat([meta_learning, pivot])

                scale_prism_value_columns(final_phase_learning).to_excel(
                    writer,
                    sheet_name=f"WinRateEMA (%)_{phase}",
                    float_format="%.5f"
                )

            # -------------------------
            # LEARNING INDEX CURVE (PHASE)
            # -------------------------
            for phase in learning_all_df["Phase"].unique():

                df_phase = learning_all_df[learning_all_df["Phase"] == phase]

                if df_phase.empty:
                    continue

                pivot = df_phase.pivot_table(
                    index="Trial",
                    columns="MouseID",
                    values="LearningIndexEMA"
                )

                pivot = pivot.sort_index()
                pivot.columns = pivot.columns.astype(str)

                valid_mice_phase = [m for m in ordered_mice if m in pivot.columns]
                pivot = pivot[valid_mice_phase]

                pivot = pivot.reset_index()
                pivot.columns = ["Trial"] + list(pivot.columns[1:])

                # -------------------------
                # METADATA
                # -------------------------
                mouse_row = [""] + valid_mice_phase

                geno_row = [""] + [
                    metadata_sorted.loc[metadata_sorted[mouse_col] == m, group_col].values[0]
                    for m in valid_mice_phase
                ]

                sex_row = [""] + [
                    metadata_sorted.loc[metadata_sorted[mouse_col] == m, sex_col].values[0]
                    for m in valid_mice_phase
                ]

                meta_learning = pd.DataFrame(
                    [mouse_row, geno_row, sex_row],
                    index=["Mouse ID", group_col, sex_col],
                    columns=pivot.columns
                )

                # -------------------------
                # WINDOW ROW
                # -------------------------
                window_row = ["Window"] + [window] * len(valid_mice_phase)

                meta_learning = pd.concat([
                    pd.DataFrame([window_row], columns=pivot.columns),
                    meta_learning
                ])

                final_phase_learning = pd.concat([meta_learning, pivot])

                final_phase_learning.to_excel(
                    writer,
                    sheet_name=f"LearningIndex (%)_{phase}"
                )

            # -------------------------
            # OUTCOME SENSITIVITY CURVE (PHASE)
            # -------------------------
            for phase in learning_all_df["Phase"].unique():

                df_phase = learning_all_df[learning_all_df["Phase"] == phase]

                if df_phase.empty:
                    continue

                pivot = df_phase.pivot_table(
                    index="Trial",
                    columns="MouseID",
                    values="OutcomeSensitivityEMA"
                )

                pivot = pivot.sort_index()
                pivot.columns = pivot.columns.astype(str)

                valid_mice_phase = [m for m in ordered_mice if m in pivot.columns]
                pivot = pivot[valid_mice_phase]

                pivot = pivot.reset_index()
                pivot.columns = ["Trial"] + list(pivot.columns[1:])

                # -------------------------
                # METADATA
                # -------------------------
                mouse_row = [""] + valid_mice_phase

                geno_row = [""] + [
                    metadata_sorted.loc[metadata_sorted[mouse_col] == m, group_col].values[0]
                    for m in valid_mice_phase
                ]

                sex_row = [""] + [
                    metadata_sorted.loc[metadata_sorted[mouse_col] == m, sex_col].values[0]
                    for m in valid_mice_phase
                ]

                meta_learning = pd.DataFrame(
                    [mouse_row, geno_row, sex_row],
                    index=["Mouse ID", group_col, sex_col],
                    columns=pivot.columns
                )

                # -------------------------
                # WINDOW ROW
                # -------------------------
                window_row = ["Window"] + [window] * len(valid_mice_phase)

                meta_learning = pd.concat([
                    pd.DataFrame([window_row], columns=pivot.columns),
                    meta_learning
                ])

                final_phase_learning = pd.concat([meta_learning, pivot])

                final_phase_learning.to_excel(
                    writer,
                    sheet_name=f"OutcomeSensitivity_{phase}"
                )

            # -------------------------
            # CUMULATIVE REWARDS CURVE (PHASE)
            # -------------------------

            for phase in learning_all_df["Phase"].unique():

                df_phase = learning_all_df[
                    learning_all_df["Phase"] == phase
                ]

                if df_phase.empty:
                    continue

                pivot = df_phase.pivot_table(
                    index="Trial",
                    columns="MouseID",
                    values="CumRewards"
                )

                pivot = pivot.sort_index()
                pivot.columns = pivot.columns.astype(str)

                valid_mice_phase = [
                    m for m in ordered_mice
                    if m in pivot.columns
                ]

                pivot = pivot[valid_mice_phase]

                pivot = pivot.reset_index()
                pivot.columns = ["Trial"] + list(pivot.columns[1:])

                # -------------------------
                # METADATA
                # -------------------------
                mouse_row = [""] + valid_mice_phase

                geno_row = [""] + [
                    metadata_sorted.loc[
                        metadata_sorted[mouse_col] == m,
                        group_col
                    ].values[0]
                    for m in valid_mice_phase
                ]

                sex_row = [""] + [
                    metadata_sorted.loc[
                        metadata_sorted[mouse_col] == m,
                        sex_col
                    ].values[0]
                    for m in valid_mice_phase
                ]

                meta_learning = pd.DataFrame(
                    [mouse_row, geno_row, sex_row],
                    index=["Mouse ID", group_col, sex_col],
                    columns=pivot.columns
                )

                final_phase_learning = pd.concat([
                    meta_learning,
                    pivot
                ])

                final_phase_learning.to_excel(
                    writer,
                    sheet_name=f"CumulativeWins_{phase}"
                )

            # -------------------------
            # PEAK ACCURACY (PHASE)
            # -------------------------

            if not peak_accuracy_df.empty:

                for phase in peak_accuracy_df["Phase"].unique():

                    df_phase = peak_accuracy_df[
                        peak_accuracy_df["Phase"] == phase
                    ].copy()

                    final_phase_peak = make_peak_accuracy_table(df_phase)

                    if final_phase_peak.empty:
                        continue

                    final_phase_peak.to_excel(
                        writer,
                        sheet_name=f"PeakAccuracy_{phase}",
                        float_format="%.5f"
                    )

            # -------------------------
            # BEHAVIOR METRICS (PHASE)
            # -------------------------

            for phase in phase_wide_df["Phase"].unique():

                df_phase = phase_wide_df[
                    phase_wide_df["Phase"] == phase
                ].copy()

                if df_phase.empty:
                    continue

                df_phase["MouseID"] = df_phase["MouseID"].astype(str)

                valid_mice_phase = [
                    m for m in ordered_mice
                    if m in df_phase["MouseID"].values
                ]

                df_phase = (
                    df_phase
                    .set_index("MouseID")
                    .loc[valid_mice_phase]
                    .reset_index()
                )

                df_phase = df_phase[
                    ["MouseID", sex_col, group_col] + metrics_cols
                ]

                scale_metric_columns(
                    df_phase,
                    percent_metrics
                ).rename(columns=display_metric_names).to_excel(
                    writer,
                    sheet_name=f"Behavior_{phase}",
                    index=False
                )


            # =========================
            # PCA (PHASE)
            # =========================

            if pca is not None and not phase_pca_df.empty:

                for phase in phase_pca_df["Phase"].dropna().unique():

                    df_phase = phase_pca_df[
                        phase_pca_df["Phase"] == phase
                    ].copy()

                    if df_phase.empty:
                        continue

                    df_phase["MouseID"] = df_phase["MouseID"].astype(str)

                    valid_mice_phase = [
                        m for m in ordered_mice
                        if m in df_phase["MouseID"].values
                    ]

                    df_phase = (
                        df_phase
                        .set_index("MouseID")
                        .loc[valid_mice_phase]
                        .reset_index()
                    )

                    df_phase = df_phase[
                        ["MouseID", sex_col, group_col] + pca_features
                    ]

                    pca_values = (
                        df_phase
                        .set_index("MouseID")[pca_features]
                        .T
                    )

                    pca_values.insert(
                        0,
                        "Metric",
                        pca_values.index
                    )

                    mouse_row = [""] + valid_mice_phase

                    geno_row = [""] + [
                        metadata_sorted.loc[
                            metadata_sorted[mouse_col] == m,
                            group_col
                        ].values[0]
                        for m in valid_mice_phase
                    ]

                    sex_row = [""] + [
                        metadata_sorted.loc[
                            metadata_sorted[mouse_col] == m,
                            sex_col
                        ].values[0]
                        for m in valid_mice_phase
                    ]

                    meta = pd.DataFrame(
                        [mouse_row, geno_row, sex_row],
                        index=["Mouse ID", group_col, sex_col],
                        columns=pca_values.columns
                    )

                    final_phase_pca = pd.concat(
                        [meta, pca_values]
                    )

                    scale_metric_rows(
                        final_phase_pca,
                        percent_metrics
                    ).rename(index=display_metric_names).to_excel(
                        writer,
                        sheet_name=f"PCA_{phase}"
                    )

            else:

                print(
                    "\nSkipping phase PCA exports "
                    "(PCA not computed)."
                )

            print(f"\nPrism-ready file saved:\n{output_path}")

    # -------------------------
    # CONFIGURE PLOTS
    # -------------------------

    plots_folder = os.path.join(save_folder, "Bandit_Plots")

    if not os.path.exists(plots_folder):
        os.makedirs(plots_folder)

    show_plots = messagebox.askyesno(
        "Plot Display",
        "Display plots?\n\nYes = show plots\nNo = save only"
    )

    use_custom_colors = messagebox.askyesno(
        "Plot Colours",
        "Would you like to choose custom colours for Sex and Genotype groups?"
    )

    group_colors = {}

    sex_colors = {}

    if use_custom_colors:

        # -------------------------
        # GENOTYPE COLOURS
        # -------------------------
        unique_groups = sorted(
            metadata_df[group_col]
            .dropna()
            .astype(str)
            .unique()
        )

        for grp in unique_groups:

            color = colorchooser.askcolor(
                title=f"Choose colour for {grp}"
            )[1]

            if color is not None:
                group_colors[grp] = color

        # -------------------------
        # SEX COLOURS
        # -------------------------
        unique_sexes = sorted(
            metadata_df[sex_col]
            .dropna()
            .astype(str)
            .unique()
        )

        for sex in unique_sexes:

            color = colorchooser.askcolor(
                title=f"Choose colour for {sex}"
            )[1]

            if color is not None:
                sex_colors[sex] = color

    # -------------------------
    # GENERATE PLOTS
    # -------------------------

    results_combined_df["Combined_Group"] = (
        results_combined_df[sex_col].astype(str)
        + "_"
        + results_combined_df[group_col].astype(str)
    )

    results_df["Combined_Group"] = (
        results_df[sex_col].astype(str)
        + "_"
        + results_df[group_col].astype(str)
    )

    plot_or(
        results_combined_df,
        group_col=sex_col,
        title=f"Odds Ratio (by {sex_col})",
        filename=f"OR_by_{sex_col}.png"
    )

    plot_or(
        results_combined_df,
        group_col=group_col,
        title=f"Odds Ratio (by {group_col})",
        filename=f"OR_by_{group_col}.png"
    )

    plot_or(
        results_combined_df,
        group_col="Combined_Group",
        title=f"Odds Ratio ({sex_col} x {group_col})",
        filename=f"OR_by_{sex_col}_{group_col}.png"
    )

    if use_phase:

        plot_or_by_phase(
            results_df,
            group_col=sex_col,
            base_title=f"Odds Ratio (by {sex_col})",
            base_filename=f"OR_by_{sex_col}"
        )

        plot_or_by_phase(
            results_df,
            group_col=group_col,
            base_title=f"Odds Ratio (by {group_col})",
            base_filename=f"OR_by_{group_col}"
        )

        plot_or_by_phase(
            results_df,
            group_col="Combined_Group",
            base_title=f"Odds Ratio ({sex_col} x {group_col})",
            base_filename=f"OR_by_{sex_col}_{group_col}"
        )

    plot_split_second_third(
        results_combined_df,
        split_col=sex_col,
        compare_col=group_col,
        plot_func=plot_or,
        prefix="OR_split"
    )

    if use_phase:
        plot_split_second_third_phase(
            results_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_or,
            prefix="OR_split_phase"
        )

    if not peak_accuracy_combined_df.empty:

        plot_peak_accuracy(
            peak_accuracy_combined_df,
            group_col=group_col,
            title=f"Peak Accuracy (by {group_col})",
            filename="PeakAccuracy_by_group.png"
        )

        plot_peak_accuracy(
            peak_accuracy_combined_df,
            group_col=sex_col,
            title=f"Peak Accuracy (by {sex_col})",
            filename="PeakAccuracy_by_sex.png"
        )

    if use_phase and not peak_accuracy_df.empty:

        for phase, d_phase in peak_accuracy_df.groupby("Phase"):

            plot_peak_accuracy(
                d_phase,
                group_col=group_col,
                title=f"Peak Accuracy (by {group_col}, {phase})",
                filename=f"PeakAccuracy_by_{group_col}_{phase}.png"
            )

        for phase, d_phase in peak_accuracy_df.groupby("Phase"):

            plot_peak_accuracy(
                d_phase,
                group_col=sex_col,
                title=f"Peak Accuracy (by {sex_col}, {phase})",
                filename=f"PeakAccuracy_by_{sex_col}_{phase}.png"
            )

    if not peak_accuracy_combined_df.empty:

        plot_split_second_third(
            peak_accuracy_combined_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_peak_accuracy,
            prefix="PeakAccuracy_split"
        )

    if use_phase and not peak_accuracy_df.empty:

        plot_split_second_third_phase(
            peak_accuracy_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_peak_accuracy,
            prefix="PeakAccuracy_split_phase"
        )

    plot_cum_rewards(
        learning_combined_df,
        group_col=group_col,
        title=f"Cumulative Wins (by {group_col})",
        filename="CumulativeWins_by_group.png"
    )

    plot_cum_rewards(
        learning_combined_df,
        group_col=sex_col,
        title=f"Cumulative Wins (by {sex_col})",
        filename="CumulativeWins_by_sex.png"
    )

    if use_phase:

        for phase, d_phase in learning_all_df.groupby("Phase"):

            plot_cum_rewards(
                d_phase,
                group_col=group_col,
                title=f"Cumulative Wins (by {group_col}, {phase})",
                filename=f"CumulativeWins_by_{group_col}_{phase}.png"
            )

        for phase, d_phase in learning_all_df.groupby("Phase"):

            plot_cum_rewards(
                d_phase,
                group_col=sex_col,
                title=f"Cumulative Wins (by {sex_col}, {phase})",
                filename=f"CumulativeWins_by_{sex_col}_{phase}.png"
            )

    plot_split_second_third(
        learning_combined_df,
        split_col=sex_col,
        compare_col=group_col,
        plot_func=plot_cum_rewards,
        prefix="CumulativeWins_split"
    )

    if use_phase:

        plot_split_second_third_phase(
            learning_all_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_cum_rewards,
            prefix="CumulativeWins_split_phase"
        )

    plot_reward_acquisition(
        learning_combined_df,
        group_col=group_col,
        title=f"Win Rate (by {group_col})",
        filename="WinRate_by_group.png"
    )

    plot_reward_acquisition(
        learning_combined_df,
        group_col=sex_col,
        title=f"Win Rate (by {sex_col})",
        filename="WinRate_by_sex.png"
    )

    if use_phase:

        for phase, d_phase in learning_all_df.groupby("Phase"):

            plot_reward_acquisition(
                d_phase,
                group_col=group_col,
                title=f"Win Rate (by {group_col}, {phase})",
                filename=f"WinRate_by_{group_col}_{phase}.png"
            )

        for phase, d_phase in learning_all_df.groupby("Phase"):

            plot_reward_acquisition(
                d_phase,
                group_col=sex_col,
                title=f"Win Rate (by {sex_col}, {phase})",
                filename=f"WinRate_by_{sex_col}_{phase}.png"
            )

    plot_split_second_third(
        learning_combined_df,
        split_col=sex_col,
        compare_col=group_col,
        plot_func=plot_reward_acquisition,
        prefix="Win Rate"
    )

    if use_phase:
        plot_split_second_third_phase(
            learning_all_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_reward_acquisition,
            prefix="Win Rate"
        )

    plot_learning_index(
        learning_combined_df,
        group_col=group_col,
        title=f"Learning Index (by {group_col})",
        filename="LearningIndex_by_group.png"
    )

    plot_learning_index(
        learning_combined_df,
        group_col=sex_col,
        title=f"Learning Index (by {sex_col})",
        filename="LearningIndex_by_sex.png"
    )

    if use_phase:

        for phase, d_phase in learning_all_df.groupby("Phase"):

            plot_learning_index(
                d_phase,
                group_col=group_col,
                title=f"Learning Index (by {group_col}, {phase})",
                filename=f"LearningIndex_by_{group_col}_{phase}.png"
            )

        for phase, d_phase in learning_all_df.groupby("Phase"):

            plot_learning_index(
                d_phase,
                group_col=sex_col,
                title=f"Learning Index (by {sex_col}, {phase})",
                filename=f"LearningIndex_by_{sex_col}_{phase}.png"
            )

    plot_split_second_third(
        learning_combined_df,
        split_col=sex_col,
        compare_col=group_col,
        plot_func=plot_learning_index,
        prefix="LearningIndex_split"
    )

    if use_phase:
        plot_split_second_third_phase(
            learning_all_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_learning_index,
            prefix="LearningIndex_split_phase"
        )

    plot_outcome_sensitivity(
        learning_combined_df,
        group_col=group_col,
        title=f"Outcome Sensitivity (by {group_col})",
        filename="OutcomeSensitivity_by_group.png"
    )

    plot_outcome_sensitivity(
        learning_combined_df,
        group_col=sex_col,
        title=f"Outcome Sensitivity (by {sex_col})",
        filename="OutcomeSensitivity_by_sex.png"
    )

    if use_phase:

        for phase, d_phase in learning_all_df.groupby("Phase"):

            plot_outcome_sensitivity(
                d_phase,
                group_col=group_col,
                title=f"Outcome Sensitivity (by {group_col}, {phase})",
                filename=f"OutcomeSensitivity_by_{group_col}_{phase}.png"
            )

        for phase, d_phase in learning_all_df.groupby("Phase"):

            plot_outcome_sensitivity(
                d_phase,
                group_col=sex_col,
                title=f"Outcome Sensitivity (by {sex_col}, {phase})",
                filename=f"OutcomeSensitivity_by_{sex_col}_{phase}.png"
            )

    plot_split_second_third(
        learning_combined_df,
        split_col=sex_col,
        compare_col=group_col,
        plot_func=plot_outcome_sensitivity,
        prefix="OutcomeSensitivity_split"
    )

    if use_phase:
        plot_split_second_third_phase(
            learning_all_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_outcome_sensitivity,
            prefix="OutcomeSensitivity_split_phase"
        )

    if create_stacked:

        # --------------------------------------------------------
        # COMBINED - BY GENOTYPE
        # --------------------------------------------------------

        plot_stacked_behavior(
            learning_combined_df,
            group_col=group_col,
            metric="LearningIndexEMA",
            metric_ylabel="Learning Index (%)",
            title=f"Cumulative Wins + Learning Index ({group_col})",
            filename="Stacked_LearningIndex_by_group.png"
        )

        plot_stacked_behavior(
            learning_combined_df,
            group_col=group_col,
            metric="OutcomeSensitivityEMA",
            metric_ylabel="Outcome Sensitivity",
            title=f"Cumulative Wins + Outcome Sensitivity ({group_col})",
            filename="Stacked_OutcomeSensitivity_by_group.png"
        )

        # --------------------------------------------------------
        # COMBINED - BY SEX
        # --------------------------------------------------------

        plot_stacked_behavior(
            learning_combined_df,
            group_col=sex_col,
            metric="LearningIndexEMA",
            metric_ylabel="Learning Index (%)",
            title=f"Cumulative Wins + Learning Index ({sex_col})",
            filename="Stacked_LearningIndex_by_sex.png"
        )

        plot_stacked_behavior(
            learning_combined_df,
            group_col=sex_col,
            metric="OutcomeSensitivityEMA",
            metric_ylabel="Outcome Sensitivity",
            title=f"Cumulative Wins + Outcome Sensitivity ({sex_col})",
            filename="Stacked_OutcomeSensitivity_by_sex.png"
        )

        # --------------------------------------------------------
        # SPLIT ANALYSIS (SEX to GENOTYPE)
        # COMBINED
        # --------------------------------------------------------

        plot_split_second_third(
            learning_all_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_stacked_learning,
            prefix="Stacked_LearningIndex_split"
        )

        plot_split_second_third(
            learning_all_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_stacked_outcome,
            prefix="Stacked_OutcomeSensitivity_split"
        )

        # --------------------------------------------------------
        # PHASE SPLIT
        # --------------------------------------------------------

        if use_phase:

            # ----------------------------------------------------
            # PHASE SPLIT - BY GENOTYPE
            # ----------------------------------------------------

            for phase, d_phase in learning_all_df.groupby("Phase"):

                plot_stacked_behavior(
                    d_phase,
                    group_col=group_col,
                    metric="LearningIndexEMA",
                    metric_ylabel="Learning Index (%)",
                    title=f"Cumulative Wins + Learning Index ({group_col}, {phase})",
                    filename=f"Stacked_LearningIndex_by_group_{phase}.png"
                )

                plot_stacked_behavior(
                    d_phase,
                    group_col=group_col,
                    metric="OutcomeSensitivityEMA",
                    metric_ylabel="Outcome Sensitivity",
                    title=f"Cumulative Wins + Outcome Sensitivity ({group_col}, {phase})",
                    filename=f"Stacked_OutcomeSensitivity_by_group_{phase}.png"
                )

            # ----------------------------------------------------
            # PHASE SPLIT - BY SEX
            # ----------------------------------------------------

            for phase, d_phase in learning_all_df.groupby("Phase"):

                plot_stacked_behavior(
                    d_phase,
                    group_col=sex_col,
                    metric="LearningIndexEMA",
                    metric_ylabel="Learning Index (%)",
                    title=f"Cumulative Wins + Learning Index ({sex_col}, {phase})",
                    filename=f"Stacked_LearningIndex_by_sex_{phase}.png"
                )

                plot_stacked_behavior(
                    d_phase,
                    group_col=sex_col,
                    metric="OutcomeSensitivityEMA",
                    metric_ylabel="Outcome Sensitivity",
                    title=f"Cumulative Wins + Outcome Sensitivity ({sex_col}, {phase})",
                    filename=f"Stacked_OutcomeSensitivity_by_sex_{phase}.png"
                )

            # ----------------------------------------------------
            # SPLIT ANALYSIS (SEX to GENOTYPE)
            # PHASE-SPECIFIC
            # ----------------------------------------------------

            plot_split_second_third_phase(
                learning_all_df,
                split_col=sex_col,
                compare_col=group_col,
                plot_func=plot_stacked_learning,
                prefix="Stacked_LearningIndex_split_phase"
            )

            plot_split_second_third_phase(
                learning_all_df,
                split_col=sex_col,
                compare_col=group_col,
                plot_func=plot_stacked_outcome,
                prefix="Stacked_OutcomeSensitivity_split_phase"
            )

    behavior_metrics = [
        "WinStay",
        "LoseShift",
        "RewardAcquisition",
        "SwitchRate",
        "TotalTrials",
        "TotalRewards",
        "HighProbWinStay",
        "HighProbLoseShift",
        "LowProbWinStay",
        "LowProbLoseShift",
        "OutcomeSensitivity",
        "HighProbOutcomeSensitivity",
        "LowProbOutcomeSensitivity",
        "LearningIndex"
    ]

    for metric in behavior_metrics:
        metric_label = display_metric_label(metric)

        plot_behavior_metric_stripplot(
            wide_df,
            metric=metric,
            x_col=group_col,
            hue_col=sex_col,
            title=f"{metric_label} (Individual Mice)",
            filename=f"{metric}_stripplot.png"
        )

    if use_phase:

        for phase, d_phase in phase_wide_df.groupby("Phase"):

            for metric in behavior_metrics:
                metric_label = display_metric_label(metric)

                plot_behavior_metric_stripplot(
                    d_phase,
                    metric=metric,
                    x_col=group_col,
                    hue_col=sex_col,
                    title=f"{metric_label} ({phase})",
                    filename=f"{metric}_stripplot_{phase}.png"
                )

    wide_df["Combined_Group"] = (
        wide_df[sex_col].astype(str)
        + "_"
        + wide_df[group_col].astype(str)
    )

    for metric in behavior_metrics:

        plot_behavior_metric_stripplot(
            wide_df,
            metric=metric,
            x_col="Combined_Group",
            title=f"{metric} ({sex_col} x {group_col})",
            filename=f"{metric}_by_{sex_col}_{group_col}.png"
        )

    plot_group_sex_behavior_heatmap(
        wide_df,
        title=f"Behavior Metrics ({group_col} x {sex_col})",
        filename=f"BehaviorMetrics_heatmap_{group_col}_{sex_col}.png"
    )

    if use_phase:

        for phase, d_phase in phase_wide_df.groupby("Phase"):

            plot_group_sex_behavior_heatmap(
                d_phase,
                title=f"Behavior Metrics ({group_col} x {sex_col}, {phase})",
                filename=f"BehaviorMetrics_heatmap_{group_col}_{sex_col}_{phase}.png"
            )

    if len(feature_cols) > 0:

        plt.figure(figsize=(10, 8))

        sns.heatmap(
            wide_df[feature_cols].corr(),
            annot=True,
            cmap="coolwarm"
        )

        plt.title("Behavior Correlation Matrix")

        plot_path = get_plot_path("Correlation_Heatmap.png")
        plt.savefig(plot_path, dpi=300, bbox_inches="tight")

        if show_plots:
            plt.show()
        else:
            plt.close()

    else:
        print("Skipping correlation heatmap (no PCA features selected)")

    if pca is not None and not loadings.empty:

        loadings_plot = loadings.rename(index=display_metric_names)

        # -------------------------
        # PC1
        # -------------------------
        plt.figure()

        sns.barplot(
            x=loadings_plot["PC1"],
            y=loadings_plot.index
        )

        plt.axvline(0, linestyle="--", color="black")

        plt.title("PCA Loadings (PC1)")
        plt.xlabel("Loading")
        plt.ylabel("Features")

        plot_path = get_plot_path("PCA_Loadings_PC1.png")
        plt.savefig(plot_path, dpi=300, bbox_inches="tight")

        if show_plots:
            plt.show()
        else:
            plt.close()

        # -------------------------
        # PC2
        # -------------------------
        plt.figure()

        sns.barplot(
            x=loadings_plot["PC2"],
            y=loadings_plot.index
        )

        plt.axvline(0, linestyle="--", color="black")

        plt.title("PCA Loadings (PC2)")
        plt.xlabel("Loading")
        plt.ylabel("Features")

        plot_path = get_plot_path("PCA_Loadings_PC2.png")
        plt.savefig(plot_path, dpi=300, bbox_inches="tight")

        if show_plots:
            plt.show()
        else:
            plt.close()

    else:
        print("Skipping PCA loadings plots (not enough mice)")

    if pca is not None:
        plot_pca_joint(
            wide_df,
            group_col=sex_col,
            title=f"PCA (by {sex_col})",
            filename=f"PCA_by_{sex_col}_joint.png"
        )

    if pca is not None:
        plot_pca_joint(
            wide_df,
            group_col=group_col,
            title=f"PCA (by {group_col})",
            filename=f"PCA_by_{group_col}_joint.png"
        )

    if use_phase and pca is not None and not phase_pca_df.empty:

        for phase, d_phase in phase_pca_df.groupby("Phase"):
            plot_pca_joint(
                d_phase,
                group_col=group_col,
                title=f"PCA (by {group_col}, {phase})",
                filename=f"PCA_by_{group_col}_{phase}.png"
            )

        for phase, d_phase in phase_pca_df.groupby("Phase"):

            plot_pca_joint(
                d_phase,
                group_col=sex_col,
                title=f"PCA (by {sex_col}, {phase})",
                filename=f"PCA_by_{sex_col}_{phase}.png"
            )

    if pca is not None:
        plot_pca_joint(
            wide_df,
            group_col="Combined_Group",
            title=f"PCA ({sex_col} x {group_col})",
            filename=f"PCA_by_{sex_col}_{group_col}_joint.png"
        )

    if pca is not None:
        plot_split_second_third(
            wide_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=plot_pca_joint,
            prefix="PCA_split"
        )

    if use_phase:
        if pca is not None and not phase_pca_df.empty:
            plot_split_second_third_phase(
                phase_pca_df,
                split_col=sex_col,
                compare_col=group_col,
                plot_func=plot_pca_joint,
                prefix="PCA_split_phase"
            )

    if processing_errors:
        error_path = os.path.join(save_folder, "Bandit_processing_errors.txt")
        with open(error_path, "w", encoding="utf-8") as error_file:
            error_file.write("\n".join(processing_errors))
        print(f"Some files were skipped. Details saved to:\n{error_path}")

    completion_message = "Analysis complete!"
    if processing_errors:
        completion_message += (
            "\n\nSome files were skipped. See Bandit_processing_errors.txt."
        )
    messagebox.showinfo("Done", completion_message)

    root.destroy()


def main():
    try:
        run_gui()
    except Exception as error:
        try:
            messagebox.showerror(
                "Bandit Error",
                f"The analysis stopped because of an unexpected error:\n\n{error}",
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
