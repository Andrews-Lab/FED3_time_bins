
import os
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import tkinter as tk
from tkinter import colorchooser
from tkinter import filedialog, messagebox
from tkinter.simpledialog import askstring

sns.set_theme(style="white", font_scale=1.2)


# ------------------------------------------------------------
# PLOT CONSTANTS
# ------------------------------------------------------------

PLOT_LINEWIDTH = 2.5

PLOT_SEM_ALPHA = 0.18

DEMAND_MARKERSIZE = 3.5

STRIPPLOT_SIZE = 7

REQUIRED_COLUMNS = {
    "MM:DD:YYYY hh:mm:ss",
    "Event",
    "FR",
    "Left_Poke_Count",
    "Right_Poke_Count",
    "Pellet_Count",
    "Block_Pellet_Count",
}

# Runtime context used by legacy-compatible output and plotting helpers.
active_side_input = None
include_incomplete = False
use_phase = False
light_start = "07:00"
light_end = "19:00"
metadata_df = pd.DataFrame()
metadata_cols_left = []
mouse_col = None
sex_col = None
group_col = None
summary_df = pd.DataFrame()
trials_all_df = pd.DataFrame()
demand_df = pd.DataFrame()
ordered_mice = []
plots_folder = None
group_colors = {}
sex_colors = {}
show_plots = False
save_individual_timecourse_plots = False


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
            "All raw timestamps failed to parse. "
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

def resolve_active_side(df, active_side_input):

    if active_side_input in ["left", "right"]:
        return active_side_input.capitalize()

    if "Active_Poke" in df.columns:
        active_values = (
            df["Active_Poke"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.capitalize()
        )

        active_values = active_values[
            active_values.isin(["Left", "Right"])
        ]

        if active_values.nunique() == 1:
            return active_values.iloc[0]

    return None

def summarize_interval(
    trial_df,
    pellet_row,
    trial_num,
    completed,
    active_side,
    phase_start,
    phase_end,
    use_phase,
):

    start_time = trial_df["Timestamp"].iloc[0]
    end_time = trial_df["Timestamp"].iloc[-1]

    left_start = trial_df["Left_Poke_Count"].iloc[0]
    left_end = trial_df["Left_Poke_Count"].iloc[-1]
    right_start = trial_df["Right_Poke_Count"].iloc[0]
    right_end = trial_df["Right_Poke_Count"].iloc[-1]

    left_pokes = left_end - left_start
    right_pokes = right_end - right_start

    # If the first row in the interval is itself a poke, the cumulative count
    # already includes that poke. Add it back so pellet intervals count all work
    # from immediately after the previous pellet through the current pellet.
    first_side = trial_df["PokeSide"].iloc[0] if "PokeSide" in trial_df.columns else pd.NA

    if first_side == "Left":
        left_pokes = left_pokes + 1
    elif first_side == "Right":
        right_pokes = right_pokes + 1

    left_pokes = max(left_pokes, 0) if not pd.isna(left_pokes) else np.nan
    right_pokes = max(right_pokes, 0) if not pd.isna(right_pokes) else np.nan

    if active_side == "Left":
        active_pokes = left_pokes
        inactive_pokes = right_pokes
    else:
        active_pokes = right_pokes
        inactive_pokes = left_pokes

    total_pokes = active_pokes + inactive_pokes

    accuracy = (
        (active_pokes / total_pokes) * 100
        if total_pokes > 0 and not pd.isna(active_pokes)
        else np.nan
    )

    duration_s = (end_time - start_time).total_seconds()
    duration_min = duration_s / 60 if duration_s >= 0 else np.nan

    vigor = (
        active_pokes / duration_min
        if duration_min > 0 and not pd.isna(active_pokes)
        else np.nan
    )

    total_poke_rate = (
        total_pokes / duration_min
        if duration_min > 0 and not pd.isna(total_pokes)
        else np.nan
    )

    inactive_poke_rate = (
        inactive_pokes / duration_min
        if duration_min > 0 and not pd.isna(inactive_pokes)
        else np.nan
    )

    inactive_poke_percent = (
        (inactive_pokes / total_pokes) * 100
        if total_pokes > 0 and not pd.isna(inactive_pokes)
        else np.nan
    )

    if pellet_row is not None:
        fr = pellet_row.get("FR", np.nan)
        block = pellet_row.get("Block", np.nan)
        block_pellet_count = pellet_row.get("Block_Pellet_Count", np.nan)
        active_poke_side = pellet_row.get("Active_Poke", np.nan)
        retrieval_time = pellet_row.get("Retrieval_Time", np.nan)
        interpellet_interval = pellet_row.get("InterPelletInterval", np.nan)
        pellet_count = pellet_row.get("Pellet_Count", np.nan)
    else:
        fr = trial_df["FR"].dropna().iloc[-1] if trial_df["FR"].notna().any() else np.nan
        block = trial_df["Block"].iloc[-1]
        block_pellet_count = trial_df["Block_Pellet_Count"].iloc[-1]
        active_poke_side = (
            trial_df["Active_Poke"].dropna().iloc[-1]
            if "Active_Poke" in trial_df.columns and trial_df["Active_Poke"].notna().any()
            else np.nan
        )
        retrieval_time = np.nan
        interpellet_interval = np.nan
        pellet_count = trial_df["Pellet_Count"].iloc[-1]

    pokes_per_pellet = total_pokes if completed == 1 else np.nan
    active_pokes_per_pellet = active_pokes if completed == 1 else np.nan

    if use_phase:
        start_phase = identify_phase(start_time, phase_start, phase_end)
        end_phase = identify_phase(end_time, phase_start, phase_end)
        phase_crossing = start_phase != end_phase
        phase = end_phase
    else:
        start_phase = "All"
        end_phase = "All"
        phase_crossing = False
        phase = "All"

    return {
        "Trial": trial_num,
        "Block": block,
        "Completed": completed,
        "Phase": phase,
        "StartPhase": start_phase,
        "EndPhase": end_phase,
        "PhaseCrossing": phase_crossing,
        "StartTime": start_time,
        "EndTime": end_time,
        "Duration_s": duration_s,
        "Duration_min": duration_min,
        "FR": fr,
        "ActivePokeSide": active_side,
        "RawActivePokeSide": active_poke_side,
        "LeftPokes": left_pokes,
        "RightPokes": right_pokes,
        "ActivePokes": active_pokes,
        "InactivePokes": inactive_pokes,
        "TotalPokes": total_pokes,
        "Accuracy": accuracy,
        "InactivePokePercent": inactive_poke_percent,
        "Vigor": vigor,
        "TotalPokeRate": total_poke_rate,
        "InactivePokeRate": inactive_poke_rate,
        "PokesPerPellet": pokes_per_pellet,
        "ActivePokesPerPellet": active_pokes_per_pellet,
        "RetrievalTime": retrieval_time,
        "InterPelletInterval": interpellet_interval,
        "Pellet_Count": pellet_count,
        "Block_Pellet_Count": block_pellet_count
    }

def build_trials(
    df,
    active_side_input,
    include_incomplete,
    use_phase,
    light_start="07:00",
    light_end="19:00",
):

    df = df.copy()
    missing = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing:
        raise ValueError(
            "Missing required ClosedEcon PR1 columns: " + ", ".join(missing)
        )

    active_side = resolve_active_side(df, active_side_input)

    if active_side is None:
        raise ValueError(
            "Active side could not be determined. Enter Left or Right "
            "instead of Auto, or provide a consistent Active_Poke column."
        )

    # -------------------------
    # TIMESTAMP HANDLING
    # -------------------------
    raw_timestamps = df["MM:DD:YYYY hh:mm:ss"].copy()
    df["Timestamp"] = parse_timestamps(raw_timestamps)
    validate_parsed_timestamps(
        raw_timestamps,
        df["Timestamp"],
        require_valid=True,
    )

    df = df.dropna(subset=["Timestamp"]).copy()
    df = df.reset_index(drop=True)

    # -------------------------
    # CLEAN COLUMNS
    # -------------------------
    numeric_cols = [
        "FR",
        "Left_Poke_Count",
        "Right_Poke_Count",
        "Pellet_Count",
        "Block_Pellet_Count",
        "Retrieval_Time",
        "InterPelletInterval",
        "Poke_Time",
        "Correct_Poke",
        "Binary_Left_Pokes",
        "Binary_Right_Pokes",
        "Binary_Pellets"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Event_clean"] = (
        df["Event"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", "", regex=True)
    )

    # FED3 ClosedEcon files can appear in two common schemas:
    # 1) Event = Poke, with Correct_Poke/Binary_Left_Pokes/Binary_Right_Pokes.
    # 2) Event = Left/Right/LeftWithPellet/etc., without Correct_Poke.
    df["PokeSide"] = pd.Series(pd.NA, index=df.index, dtype="object")

    if "Binary_Left_Pokes" in df.columns:
        df.loc[df["Binary_Left_Pokes"].eq(1), "PokeSide"] = "Left"

    if "Binary_Right_Pokes" in df.columns:
        df.loc[df["Binary_Right_Pokes"].eq(1), "PokeSide"] = "Right"

    df.loc[
        df["Event_clean"].str.startswith("Left", na=False),
        "PokeSide"
    ] = "Left"

    df.loc[
        df["Event_clean"].str.startswith("Right", na=False),
        "PokeSide"
    ] = "Right"

    df["IsPoke"] = (
        df["Event_clean"].eq("Poke")
        | df["PokeSide"].isin(["Left", "Right"])
    )

    df["IsActivePoke"] = pd.Series(pd.NA, index=df.index, dtype="object")

    if "Correct_Poke" in df.columns:
        valid_correct = df["Correct_Poke"].isin([0, 1])
        df.loc[valid_correct, "IsActivePoke"] = df.loc[
            valid_correct,
            "Correct_Poke"
        ].eq(1)

    needs_side_fallback = df["IsActivePoke"].isna() & df["IsPoke"]

    if "Active_Poke" in df.columns:
        df.loc[needs_side_fallback, "IsActivePoke"] = (
            df.loc[needs_side_fallback, "PokeSide"].astype(str).str.lower()
            == df.loc[needs_side_fallback, "Active_Poke"].astype(str).str.lower()
        )

    # -------------------------
    # BLOCK DETECTION
    # -------------------------
    df["BlockReset"] = df["Block_Pellet_Count"].diff() < 0

    if "Concat_#" in df.columns:
        df["BlockReset"] = (
            df["BlockReset"]
            | (df["Concat_#"].ne(df["Concat_#"].shift()) & df.index.to_series().ne(0))
        )

    df["Block"] = df["BlockReset"].cumsum() + 1

    # -------------------------
    # PELLET EVENTS = COMPLETED TRIALS
    # -------------------------
    is_pellet = df["Event_clean"].eq("Pellet")

    if "Binary_Pellets" in df.columns:
        is_pellet = is_pellet | df["Binary_Pellets"].eq(1)

    pellet_idx = df[is_pellet].index.tolist()

    trials = []
    prev_idx = 0

    start = None
    end = None

    if use_phase:
        start = pd.to_datetime(light_start).time()
        end   = pd.to_datetime(light_end).time()

    for trial_num, idx in enumerate(pellet_idx, start=1):

        trial_df = df.loc[prev_idx:idx].copy()
        pellet_row = df.loc[idx]

        row = summarize_interval(
            trial_df=trial_df,
            pellet_row=pellet_row,
            trial_num=trial_num,
            completed=1,
            active_side=active_side,
            phase_start=start,
            phase_end=end,
            use_phase=use_phase,
        )

        trials.append(row)
        prev_idx = idx + 1

    # -------------------------
    # OPTIONAL CENSORED FINAL INTERVAL
    # -------------------------
    if include_incomplete and prev_idx < len(df):
        final_df = df.loc[prev_idx:].copy()
        final_pokes = final_df[final_df["IsPoke"].eq(True)]

        if len(final_pokes) > 0:
            trial_num = len(trials) + 1

            row = summarize_interval(
                trial_df=final_df,
                pellet_row=None,
                trial_num=trial_num,
                completed=0,
                active_side=active_side,
                phase_start=start,
                phase_end=end,
                use_phase=use_phase,
            )

            trials.append(row)

    trials_df = pd.DataFrame(trials)

    if trials_df.empty:
        return trials_df

    trials_df["CumulativePellets"] = trials_df["Completed"].cumsum()
    trials_df["CumulativeActivePokes"] = trials_df["ActivePokes"].cumsum()
    trials_df["CumulativeTotalPokes"] = trials_df["TotalPokes"].cumsum()

    if use_phase:
        trials_df["PhaseTrial"] = (
            trials_df
            .groupby("Phase")
            .cumcount()
            + 1
        )

        trials_df["ExclusivePhaseTrial"] = np.nan
        exclusive_mask = trials_df["PhaseCrossing"].eq(False)

        trials_df.loc[exclusive_mask, "ExclusivePhaseTrial"] = (
            trials_df.loc[exclusive_mask]
            .groupby("Phase")
            .cumcount()
            + 1
        )
    else:
        trials_df["PhaseTrial"] = trials_df["Trial"]
        trials_df["ExclusivePhaseTrial"] = trials_df["Trial"]

    return trials_df


# ------------------------------------------------------------
# SUMMARY AND DEMAND METRICS
# ------------------------------------------------------------

def summarize_trials(trials_df):

    completed = trials_df[trials_df["Completed"].eq(1)].copy()
    all_rows = trials_df.copy()

    total_session_time_h = (
        (all_rows["EndTime"].max() - all_rows["StartTime"].min()).total_seconds() / 3600
        if len(all_rows) > 0 else np.nan
    )

    total_pellets = completed["Completed"].sum()
    total_pokes = all_rows["TotalPokes"].sum()
    left_pokes = all_rows["LeftPokes"].sum()
    right_pokes = all_rows["RightPokes"].sum()
    active_pokes = all_rows["ActivePokes"].sum()
    inactive_pokes = all_rows["InactivePokes"].sum()

    final_completed = completed.tail(1)

    final_fr = (
        final_completed["FR"].iloc[0]
        if len(final_completed) > 0
        else np.nan
    )

    max_fr = completed["FR"].max() if len(completed) > 0 else np.nan

    return {
        "TotalPellets": total_pellets,
        "CompletedTrials": len(completed),
        "TotalPokes": total_pokes,
        "LeftPokes": left_pokes,
        "RightPokes": right_pokes,
        "ActivePokes": active_pokes,
        "InactivePokes": inactive_pokes,
        "Accuracy": (
            (active_pokes / total_pokes) * 100
            if total_pokes > 0 else np.nan
        ),
        "InactivePokePercent": (
            (inactive_pokes / total_pokes) * 100
            if total_pokes > 0 else np.nan
        ),
        "PokesPerPellet": (
            total_pokes / total_pellets
            if total_pellets > 0 else np.nan
        ),
        "ActivePokesPerPellet": (
            active_pokes / total_pellets
            if total_pellets > 0 else np.nan
        ),
        "InactivePokesPerPellet": (
            inactive_pokes / total_pellets
            if total_pellets > 0 else np.nan
        ),
        "PelletsPerHour": (
            total_pellets / total_session_time_h
            if total_session_time_h > 0 else np.nan
        ),
        "ActivePokesPerHour": (
            active_pokes / total_session_time_h
            if total_session_time_h > 0 else np.nan
        ),
        "TotalSessionTime_h": total_session_time_h,
        "FinalFR": final_fr,
        "MaxFR": max_fr,
        "MeanFR": completed["FR"].mean(),
        "MedianFR": completed["FR"].median(),
        "MeanTrialDuration_min": completed["Duration_min"].mean(),
        "MeanVigor": completed["Vigor"].mean(),
        "MeanTotalPokeRate": completed["TotalPokeRate"].mean(),
        "MeanInactivePokeRate": completed["InactivePokeRate"].mean(),
        "MeanInactivePokePercent": completed["InactivePokePercent"].mean(),
        "MeanRetrievalTime": completed["RetrievalTime"].mean(),
        "MeanInterPelletInterval": completed["InterPelletInterval"].mean(),
        "BlocksCompleted": completed["Block"].nunique(),
        "IncompleteFinalInterval": int(all_rows["Completed"].eq(0).any()),
        "IncompleteFinalPokes": all_rows.loc[
            all_rows["Completed"].eq(0),
            "TotalPokes"
        ].sum()
    }

def demand_by_fr(trials_df):

    completed = trials_df[trials_df["Completed"].eq(1)].copy()

    if completed.empty:
        return pd.DataFrame()

    demand = (
        completed
        .groupby("FR", dropna=False)
        .agg(
            Pellets=("Completed", "sum"),
            LeftPokes=("LeftPokes", "sum"),
            RightPokes=("RightPokes", "sum"),
            ActivePokes=("ActivePokes", "sum"),
            InactivePokes=("InactivePokes", "sum"),
            TotalPokes=("TotalPokes", "sum"),
            TotalDuration_min=("Duration_min", "sum"),
            MeanAccuracy=("Accuracy", "mean"),
            MeanVigor=("Vigor", "mean"),
            MeanTotalPokeRate=("TotalPokeRate", "mean"),
            MeanInactivePokeRate=("InactivePokeRate", "mean"),
            MeanInactivePokePercent=("InactivePokePercent", "mean"),
            MeanDuration_min=("Duration_min", "mean"),
            MeanRetrievalTime=("RetrievalTime", "mean"),
            MeanInterPelletInterval=("InterPelletInterval", "mean")
        )
        .reset_index()
    )

    demand["PokesPerPellet"] = demand["TotalPokes"] / demand["Pellets"]
    demand["ActivePokesPerPellet"] = demand["ActivePokes"] / demand["Pellets"]
    demand["InactivePokesPerPellet"] = demand["InactivePokes"] / demand["Pellets"]
    demand["PooledAccuracy"] = (
        demand["ActivePokes"] / demand["TotalPokes"].replace(0, np.nan)
    ) * 100
    demand["InactivePokePercent"] = (
        demand["InactivePokes"] / demand["TotalPokes"].replace(0, np.nan)
    ) * 100
    demand["PelletsPerMinute"] = (
        demand["Pellets"] / demand["TotalDuration_min"].replace(0, np.nan)
    )

    return demand

def demand_by_fr_phase(trials_df, use_phase, exclusive_only=False):

    if not use_phase or "Phase" not in trials_df.columns:
        return pd.DataFrame()

    completed = trials_df[trials_df["Completed"].eq(1)].copy()

    if exclusive_only and "PhaseCrossing" in completed.columns:
        completed = completed[completed["PhaseCrossing"].eq(False)].copy()

    if completed.empty:
        return pd.DataFrame()

    phase_demand = []

    for phase, d_phase in completed.groupby("Phase"):
        demand = demand_by_fr(d_phase)

        if demand.empty:
            continue

        demand["Phase"] = phase
        phase_demand.append(demand)

    if len(phase_demand) == 0:
        return pd.DataFrame()

    return pd.concat(phase_demand, ignore_index=True)


# ------------------------------------------------------------
# OUTPUT TABLE HELPERS
# ------------------------------------------------------------

def move_metadata_left(df):

    if df.empty:
        return df

    left_cols = [
        col for col in metadata_cols_left
        if col in df.columns
    ]

    other_cols = [
        col for col in df.columns
        if col not in left_cols
    ]

    return df[left_cols + other_cols]

def reorder_columns(df, front_cols):

    if df.empty:
        return df

    front = [
        col for col in front_cols
        if col in df.columns
    ]

    rest = [
        col for col in df.columns
        if col not in front
    ]

    return df[front + rest]

def metadata_rows(columns):

    mouse_row = [""] + list(columns)

    geno_row = [""] + [
        summary_df.loc[summary_df[mouse_col].astype(str).eq(str(m)), group_col].iloc[0]
        for m in columns
    ]

    sex_row = [""] + [
        summary_df.loc[summary_df[mouse_col].astype(str).eq(str(m)), sex_col].iloc[0]
        for m in columns
    ]

    return mouse_row, geno_row, sex_row

def make_summary_metric_table(metric, data=None):

    if data is None:
        data = summary_df

    if metric not in data.columns:
        return pd.DataFrame()

    rows = []

    for mouse in ordered_mice:

        d_mouse = data[data[mouse_col].astype(str).eq(str(mouse))]

        if d_mouse.empty:
            continue

        rows.append({
            "Filename": d_mouse["Filename"].iloc[0],
            mouse_col: d_mouse[mouse_col].iloc[0],
            sex_col: d_mouse[sex_col].iloc[0],
            group_col: d_mouse[group_col].iloc[0],
            metric: d_mouse[metric].iloc[0]
        })

    out = pd.DataFrame(rows)

    cols = [
        col for col in [
            "Filename",
            mouse_col,
            sex_col,
            group_col,
            metric
        ]
        if col in out.columns
    ]

    cols = list(dict.fromkeys(cols))

    return out[cols]

def make_trial_metric_table(metric, data=None, index_col="Trial"):

    if data is None:
        data = trials_all_df[trials_all_df["Completed"].eq(1)].copy()

    if data.empty or metric not in data.columns:
        return pd.DataFrame()
    
    if index_col not in data.columns:
        index_col = "Trial"

    pivot = data.pivot_table(
        index=index_col,
        columns=mouse_col,
        values=metric,
        aggfunc="mean"
    )

    pivot.columns = pivot.columns.astype(str)
    valid_mice = [m for m in ordered_mice if str(m) in pivot.columns]

    if len(valid_mice) == 0:
        return pd.DataFrame()

    pivot = pivot[valid_mice].reset_index()
    pivot.columns = [index_col] + valid_mice

    mouse_row, geno_row, sex_row = metadata_rows(valid_mice)

    meta = pd.DataFrame(
        [mouse_row, geno_row, sex_row],
        index=[mouse_col, group_col, sex_col],
        columns=pivot.columns
    )

    return pd.concat([meta, pivot])

def make_demand_metric_table(metric, data=None):

    if data is None:
        data = demand_df

    if data.empty or metric not in data.columns:
        return pd.DataFrame()

    pivot = data.pivot_table(
        index="FR",
        columns=mouse_col,
        values=metric,
        aggfunc="mean"
    )

    pivot.columns = pivot.columns.astype(str)
    valid_mice = [m for m in ordered_mice if str(m) in pivot.columns]

    if len(valid_mice) == 0:
        return pd.DataFrame()

    pivot = pivot[valid_mice].reset_index()
    pivot.columns = ["FR"] + valid_mice

    mouse_row, geno_row, sex_row = metadata_rows(valid_mice)

    meta = pd.DataFrame(
        [mouse_row, geno_row, sex_row],
        index=[mouse_col, group_col, sex_col],
        columns=pivot.columns
    )

    return pd.concat([meta, pivot])

def safe_sheet_name(name):
    bad_chars = ["\\", "/", "*", "[", "]", ":", "?"]

    for char in bad_chars:
        name = name.replace(char, "_")

    return name[:31]


# ------------------------------------------------------------
# PLOT FILE AND COLOUR HELPERS
# ------------------------------------------------------------

def get_plot_subfolder(filename):

    filename_lower = filename.lower()

    if filename.startswith("Stacked_"):
        return "Stacked"
    if "heatmap" in filename_lower:
        return "Heatmaps"
    if filename_lower.endswith("__dark_exclusive.png"):
        return "Dark_Exclusive"
    if filename_lower.endswith("__light_exclusive.png"):
        return "Light_Exclusive"
    if filename_lower.endswith("__dark.png"):
        return "Dark"
    if filename_lower.endswith("__light.png"):
        return "Light"

    return "All"

def get_plot_path(filename):

    subfolder = get_plot_subfolder(filename)
    folder = os.path.join(plots_folder, subfolder)

    if not os.path.exists(folder):
        os.makedirs(folder)

    return os.path.join(folder, filename)

def build_color_map(values):

    if len(values) == 0:
        return {}

    palette = sns.color_palette("tab10", n_colors=len(values)).as_hex()

    return {
        str(value): palette[i]
        for i, value in enumerate(values)
    }

def get_plot_color(grp, grouping_col):

    key = str(grp)

    if grouping_col == group_col:
        return group_colors.get(key, None)
    if grouping_col == sex_col:
        return sex_colors.get(key, None)

    return None

def get_plot_palette(grouping_col):

    if grouping_col == group_col:
        return group_colors if len(group_colors) > 0 else None
    if grouping_col == sex_col:
        return sex_colors if len(sex_colors) > 0 else None

    return None


# ------------------------------------------------------------
# CORE PLOTTING FUNCTIONS
# ------------------------------------------------------------

def plot_trial_trajectory(data, metric, group_col_plot, title, filename, ylabel=None, x_col="Trial"):

    if data.empty or metric not in data.columns:
        return

    plot_x_col = x_col if x_col in data.columns else "Trial"

    plt.figure(figsize=(9, 6))

    for grp, d in data.groupby(group_col_plot):
        color = get_plot_color(grp, group_col_plot)

        mean = d.groupby(plot_x_col)[metric].mean()
        sem = d.groupby(plot_x_col)[metric].sem().fillna(0)

        plt.plot(
            mean.index,
            mean.values,
            label=grp,
            linewidth=PLOT_LINEWIDTH,
            color=color
        )

        plt.fill_between(
            mean.index,
            mean - sem,
            mean + sem,
            alpha=PLOT_SEM_ALPHA,
            color=color
        )

    if plot_x_col == "PhaseTrial":
        x_label = "PhaseTrial (EndPhase-based)"
    elif plot_x_col == "ExclusivePhaseTrial":
        x_label = "ExclusivePhaseTrial (StartPhase = EndPhase)"
    else:
        x_label = plot_x_col

    plt.xlabel(x_label)
    plt.ylabel(ylabel if ylabel else metric)
    plt.title(title)
    plt.legend()

    plot_path = get_plot_path(filename)
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_demand(data, metric, group_col_plot, title, filename, ylabel=None):

    if data.empty or metric not in data.columns:
        return

    plt.figure(figsize=(9, 6))

    for grp, d in data.groupby(group_col_plot):
        color = get_plot_color(grp, group_col_plot)

        mean = d.groupby("FR")[metric].mean()
        sem = d.groupby("FR")[metric].sem().fillna(0)

        plt.plot(
            mean.index,
            mean.values,
            label=grp,
            marker="o",
            markersize=DEMAND_MARKERSIZE,
            markeredgewidth=0,
            linewidth=PLOT_LINEWIDTH,
            color=color
        )
        plt.fill_between(
            mean.index,
            mean - sem,
            mean + sem,
            alpha=PLOT_SEM_ALPHA,
            color=color
        )

    plt.xlabel("FR")
    plt.ylabel(ylabel if ylabel else metric)
    plt.title(title)
    plt.legend()

    plot_path = get_plot_path(filename)
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")

    if show_plots:
        plt.show()
    else:
        plt.close()

def plot_summary_stripplot(data, metric, x_col, title, filename, hue_col=None):

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
    plot_data = plot_data.dropna(subset=required_columns)

    if plot_data.empty or plot_data[x_col].nunique() == 0:
        print(f"Skipping {filename}: no valid data to plot.")
        return

    if hue_col and plot_data[hue_col].nunique() == 0:
        print(f"Skipping {filename}: no valid {hue_col} values to plot.")
        return

    plt.figure(figsize=(8, 6))

    palette_col = hue_col if hue_col else x_col
    palette = get_plot_palette(palette_col)
    hide_legend = False

    strip_kwargs = {
        "data": plot_data,
        "x": x_col,
        "y": metric,
        "dodge": True if hue_col else False,
        "size": STRIPPLOT_SIZE
    }

    if hue_col:
        strip_kwargs["hue"] = hue_col
        strip_kwargs["palette"] = palette
    elif palette is not None:
        strip_kwargs["hue"] = x_col
        strip_kwargs["palette"] = palette
        hide_legend = True

    axis = sns.stripplot(**strip_kwargs)

    if hide_legend:
        legend = axis.get_legend()
        if legend is not None:
            legend.remove()

    plt.title(title)
    plt.ylabel(metric)

    if x_col == "Combined_Group":
        plt.xticks(rotation=45)

    plot_path = get_plot_path(filename)
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")

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

def plot_group_sex_heatmap(data, title, filename):

    heatmap_metrics = [
        "TotalPellets",
        "TotalPokes",
        "ActivePokes",
        "InactivePokes",
        "Accuracy",
        "InactivePokePercent",
        "PokesPerPellet",
        "PelletsPerHour",
        "FinalFR",
        "MaxFR",
        "MeanTrialDuration_min",
        "MeanVigor",
        "MeanTotalPokeRate",
        "MeanInactivePokeRate",
        "MeanInactivePokePercent",
        "MeanRetrievalTime"
    ]

    heatmap_metrics = [
        m for m in heatmap_metrics
        if m in data.columns
    ]

    if len(heatmap_metrics) == 0:
        return

    grouped = (
        data
        .groupby([group_col, sex_col], dropna=False)[heatmap_metrics]
        .mean()
    )

    if grouped.empty:
        return

    grouped.index = [
        f"{group} | {sex}"
        for group, sex in grouped.index
    ]

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
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")

    if show_plots:
        plt.show()
    else:
        plt.close()

def add_dark_shading(ax, x_min, x_max):

    if not use_phase:
        return

    start_time = pd.to_datetime(light_start).time()
    end_time = pd.to_datetime(light_end).time()

    x_min = pd.to_datetime(x_min)
    x_max = pd.to_datetime(x_max)

    if pd.isna(x_min) or pd.isna(x_max):
        return

    first_day = x_min.normalize() - pd.Timedelta(days=1)
    last_day = x_max.normalize() + pd.Timedelta(days=1)

    for day in pd.date_range(first_day, last_day, freq="D"):

        midnight = day
        next_midnight = day + pd.Timedelta(days=1)
        light_start_dt = pd.Timestamp.combine(day.date(), start_time)
        light_end_dt = pd.Timestamp.combine(day.date(), end_time)

        if start_time < end_time:
            dark_intervals = [
                (midnight, light_start_dt),
                (light_end_dt, next_midnight)
            ]
        else:
            dark_intervals = [
                (light_end_dt, light_start_dt)
            ]

        for dark_start, dark_end in dark_intervals:

            if dark_end < x_min or dark_start > x_max:
                continue

            ax.axvspan(
                dark_start,
                dark_end,
                color="gray",
                alpha=0.18,
                zorder=0
            )

def plot_stacked_individual_timecourse(
    data,
    metric,
    ylabel,
    title,
    filename,
    color_by_value=False
):

    if data.empty or metric not in data.columns or "EndTime" not in data.columns:
        return

    plot_data = data.copy()
    plot_data["EndTime"] = pd.to_datetime(
        plot_data["EndTime"],
        errors="coerce"
    )

    plot_data = plot_data.dropna(subset=["EndTime", metric])

    if plot_data.empty:
        return

    if "StartTime" in plot_data.columns:
        plot_data["StartTime"] = pd.to_datetime(
            plot_data["StartTime"],
            errors="coerce"
        )
    else:
        plot_data["StartTime"] = pd.NaT

    def format_sex_label(value):

        if pd.isna(value):
            return ""

        label = str(value).strip()
        label_lower = label.lower()

        if label_lower.startswith("female"):
            return "F"
        if label_lower.startswith("male"):
            return "M"

        return label

    mouse_order = (
        plot_data[
            [mouse_col, sex_col, group_col]
        ]
        .drop_duplicates(subset=[mouse_col])
        .copy()
    )

    mouse_order["_Mouse_str"] = mouse_order[mouse_col].astype(str)
    mouse_order["_Mouse_num"] = pd.to_numeric(
        mouse_order["_Mouse_str"],
        errors="coerce"
    )

    mouse_order = mouse_order.sort_values(
        by=[sex_col, group_col, "_Mouse_num", "_Mouse_str"],
        na_position="last"
    )

    mice = mouse_order["_Mouse_str"].tolist()

    mouse_labels = {}

    for _, row in mouse_order.iterrows():

        mouse = row["_Mouse_str"]
        sex_label = format_sex_label(row[sex_col])
        group_label = "" if pd.isna(row[group_col]) else str(row[group_col]).strip()

        label_parts = [
            part for part in [mouse, sex_label, group_label]
            if part != ""
        ]

        mouse_labels[mouse] = " | ".join(label_parts)

    if len(mice) == 0:
        return

    def get_previous_light_anchor(timestamp):

        if not use_phase:
            return timestamp

        light_start_time = pd.to_datetime(light_start).time()
        anchor = pd.Timestamp.combine(timestamp.date(), light_start_time)

        if anchor > timestamp:
            anchor = anchor - pd.Timedelta(days=1)

        return anchor

    cycle_anchors = {}

    for mouse in mice:

        d_mouse = plot_data[
            plot_data[mouse_col].astype(str).eq(str(mouse))
        ]

        if d_mouse["StartTime"].notna().any():
            session_start = d_mouse["StartTime"].min()
        else:
            session_start = d_mouse["EndTime"].min()

        cycle_anchor = get_previous_light_anchor(session_start)
        cycle_anchors[str(mouse)] = cycle_anchor

        plot_data.loc[
            plot_data[mouse_col].astype(str).eq(str(mouse)),
            "SessionDay"
        ] = (
            plot_data.loc[
                plot_data[mouse_col].astype(str).eq(str(mouse)),
                "EndTime"
            ] - cycle_anchor
        ).dt.total_seconds() / 86400

    x_min = 0
    x_max = plot_data["SessionDay"].max()

    if pd.isna(x_max) or x_max <= 0:
        x_max = 1

    x_axis_label = (
        "Days from light-cycle anchor"
        if use_phase else
        "Days from session start"
    )

    y_max = plot_data[metric].max()

    if pd.isna(y_max) or y_max <= 0:
        y_max = 1

    def add_relative_dark_shading(ax, d_mouse):

        if not use_phase:
            return

        mouse = str(d_mouse[mouse_col].iloc[0])
        cycle_anchor = cycle_anchors.get(mouse)

        if cycle_anchor is None or pd.isna(cycle_anchor):
            return

        start_time = pd.to_datetime(light_start).time()
        end_time = pd.to_datetime(light_end).time()

        actual_min = d_mouse["EndTime"].min()
        actual_max = d_mouse["EndTime"].max()

        if pd.isna(actual_min) or pd.isna(actual_max):
            return

        first_day = actual_min.normalize() - pd.Timedelta(days=1)
        last_day = actual_max.normalize() + pd.Timedelta(days=1)

        for day in pd.date_range(first_day, last_day, freq="D"):

            midnight = day
            next_midnight = day + pd.Timedelta(days=1)
            light_start_dt = pd.Timestamp.combine(day.date(), start_time)
            light_end_dt = pd.Timestamp.combine(day.date(), end_time)

            if start_time < end_time:
                dark_intervals = [
                    (midnight, light_start_dt),
                    (light_end_dt, next_midnight)
                ]
            else:
                dark_intervals = [
                    (light_end_dt, light_start_dt)
                ]

            for dark_start, dark_end in dark_intervals:

                if dark_end < actual_min or dark_start > actual_max:
                    continue

                rel_start = (dark_start - cycle_anchor).total_seconds() / 86400
                rel_end = (dark_end - cycle_anchor).total_seconds() / 86400

                ax.axvspan(
                    max(rel_start, x_min),
                    min(rel_end, x_max),
                    color="gray",
                    alpha=0.18,
                    zorder=0
                )

    def draw_mouse_timecourse(ax, d_mouse):

        add_relative_dark_shading(ax, d_mouse)

        if color_by_value:
            ax.scatter(
                d_mouse["SessionDay"],
                d_mouse[metric],
                c=d_mouse[metric],
                cmap="spring",
                s=10,
                alpha=0.65,
                linewidths=0,
                zorder=2
            )
        else:
            group_value = d_mouse[group_col].iloc[0]
            color = get_plot_color(group_value, group_col)

            ax.plot(
                d_mouse["SessionDay"],
                d_mouse[metric],
                color=color,
                linewidth=1.0,
                alpha=0.85,
                zorder=2
            )

            ax.scatter(
                d_mouse["SessionDay"],
                d_mouse[metric],
                color=color,
                s=8,
                alpha=0.75,
                linewidths=0,
                zorder=3
            )

        ax.set_ylim(-0.05 * y_max, y_max * 1.05)
        ax.set_xlim(x_min, x_max)

    fig_height = max(5, len(mice) * 0.75)

    fig, axes = plt.subplots(
        len(mice),
        1,
        figsize=(14, fig_height),
        sharex=True
    )

    if len(mice) == 1:
        axes = [axes]

    previous_group_key = None

    for ax, mouse in zip(axes, mice):

        d_mouse = plot_data[
            plot_data[mouse_col].astype(str).eq(str(mouse))
        ].sort_values("EndTime")

        sex_value = d_mouse[sex_col].iloc[0]
        group_value = d_mouse[group_col].iloc[0]
        group_key = (str(sex_value), str(group_value))

        draw_mouse_timecourse(ax, d_mouse)

        ax.set_ylabel(
            mouse_labels.get(str(mouse), str(mouse)),
            rotation=0,
            ha="right",
            va="center",
            labelpad=56,
            fontsize=8
        )

        if previous_group_key is None:
            ax.spines["top"].set_visible(False)
        elif group_key != previous_group_key:
            ax.spines["top"].set_visible(True)
            ax.spines["top"].set_linewidth(1.4)
            ax.spines["top"].set_color("black")
        else:
            ax.spines["top"].set_visible(False)

        ax.spines["right"].set_visible(False)

        previous_group_key = group_key

        if ax is not axes[-1]:
            ax.tick_params(labelbottom=False)

    axes[-1].set_xlabel(x_axis_label)
    axes[-1].set_xticks(np.arange(np.floor(x_min), np.ceil(x_max) + 1, 1))

    fig.text(
        0.02,
        0.5,
        ylabel,
        rotation="vertical",
        va="center"
    )

    fig.suptitle(title, y=0.995)
    fig.tight_layout(rect=[0.04, 0, 1, 0.98])

    plot_path = get_plot_path(filename)
    fig.savefig(plot_path, dpi=300, bbox_inches="tight")

    if show_plots:
        plt.show()
    else:
        plt.close(fig)

    if save_individual_timecourse_plots:

        base_filename = os.path.splitext(filename)[0]

        for mouse in mice:

            d_mouse = plot_data[
                plot_data[mouse_col].astype(str).eq(str(mouse))
            ].sort_values("EndTime")

            if d_mouse.empty:
                continue

            fig_ind, ax_ind = plt.subplots(figsize=(10, 5))
            draw_mouse_timecourse(ax_ind, d_mouse)

            ax_ind.set_title(
                f"{title} - {mouse_labels.get(str(mouse), str(mouse))}"
            )
            ax_ind.set_xlabel(x_axis_label)
            ax_ind.set_ylabel(ylabel)
            ax_ind.spines["top"].set_visible(False)
            ax_ind.spines["right"].set_visible(False)
            ax_ind.set_xlim(x_min, x_max)
            ax_ind.set_xticks(np.arange(np.floor(x_min), np.ceil(x_max) + 1, 1))
            fig_ind.tight_layout()

            individual_path = get_plot_path(
                f"{base_filename}_{safe_filename_value(mouse)}.png"
            )

            fig_ind.savefig(individual_path, dpi=300, bbox_inches="tight")

            if show_plots:
                plt.show()
            else:
                plt.close(fig_ind)


# ------------------------------------------------------------
# REUSABLE PLOT VARIANT HELPERS
# ------------------------------------------------------------

def safe_filename_value(value):

    return (
        str(value)
        .strip()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
        .replace("[", "_")
        .replace("]", "_")
        .replace("\n", "")
        .replace("\r", "")
    )

def build_plot_filename(metric, group_col_plot=None, subset_col=None,
                        subset_value=None, phase=None, exclusive=False):

    parts = [safe_filename_value(metric)]

    if subset_col is not None and subset_value is not None:
        parts.append(
            f"{safe_filename_value(subset_col)}_{safe_filename_value(subset_value)}"
        )

    if group_col_plot is not None:
        parts.append(f"By_{safe_filename_value(group_col_plot)}")

    if phase is not None:
        phase_part = safe_filename_value(phase)

        if exclusive:
            phase_part = f"{phase_part}_Exclusive"

        parts.append(phase_part)

    return "__".join(parts) + ".png"

def plot_split_second_third(
    data,
    split_col,
    compare_col,
    plot_func,
    metric_name,
    title_prefix=None
):

    if data.empty:
        return

    display_prefix = title_prefix if title_prefix is not None else metric_name

    for val in sorted(data[split_col].dropna().unique()):

        subset = data[data[split_col] == val]

        if subset[compare_col].nunique() < 2:
            print(f"Skipping {val} - only one group in {compare_col}")
            continue

        plot_func(
            subset,
            group_col_plot=compare_col,
            title=f"{display_prefix} ({compare_col} within {split_col} = {val})",
            filename=build_plot_filename(
                metric_name,
                group_col_plot=compare_col,
                subset_col=split_col,
                subset_value=val
            )
        )

def plot_split_second_third_phase(
    data,
    split_col,
    compare_col,
    plot_func,
    metric_name,
    title_prefix=None,
    x_col="PhaseTrial",
    exclusive=False
):

    if data.empty or "Phase" not in data.columns:
        print(f"Skipping {metric_name}: no Phase column available.")
        return

    display_prefix = title_prefix if title_prefix is not None else metric_name

    for phase, d_phase in data.groupby("Phase"):

        for val in sorted(d_phase[split_col].dropna().unique()):

            subset = d_phase[d_phase[split_col] == val]

            if subset[compare_col].nunique() < 2:
                print(f"Skipping {val} ({phase}) - only one group in {compare_col}")
                continue

            plot_func(
                subset,
                group_col_plot=compare_col,
                title=f"{display_prefix} ({compare_col} within {split_col} = {val}, {phase})",
                filename=build_plot_filename(
                    metric_name,
                    group_col_plot=compare_col,
                    subset_col=split_col,
                    subset_value=val,
                    phase=phase,
                    exclusive=exclusive
                ),
                x_col=x_col
            )

def plot_split_second_third_demand_phase(
    data,
    split_col,
    compare_col,
    plot_func,
    metric_name,
    title_prefix=None,
    exclusive=False
):

    if data.empty or "Phase" not in data.columns:
        print(f"Skipping {metric_name}: no Phase column available.")
        return

    display_prefix = title_prefix if title_prefix is not None else metric_name

    for phase, d_phase in data.groupby("Phase"):

        for val in sorted(d_phase[split_col].dropna().unique()):

            subset = d_phase[d_phase[split_col] == val]

            if subset[compare_col].nunique() < 2:
                print(f"Skipping {val} ({phase}) - only one group in {compare_col}")
                continue

            plot_func(
                subset,
                group_col_plot=compare_col,
                title=f"{display_prefix} ({compare_col} within {split_col} = {val}, {phase})",
                filename=build_plot_filename(
                    metric_name,
                    group_col_plot=compare_col,
                    subset_col=split_col,
                    subset_value=val,
                    phase=phase,
                    exclusive=exclusive
                )
            )


# ------------------------------------------------------------
# MAIN GUI AND ANALYSIS WORKFLOW
# ------------------------------------------------------------
def run_gui():
    global active_side_input, include_incomplete, use_phase, light_start, light_end, metadata_df, metadata_cols_left, mouse_col
    global sex_col, group_col, summary_df, trials_all_df, demand_df, ordered_mice, plots_folder
    global group_colors, sex_colors, show_plots, save_individual_timecourse_plots

    # -------------------------
    # ROOT SETUP AND FILE SELECTION
    # -------------------------

    root = tk.Tk()

    root.withdraw()

    file_paths = filedialog.askopenfilenames(
        title="Select FED3 ClosedEcon PR1 CSV files",
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
    # ANALYSIS SETTINGS
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

        light_start = clean_time_input(light_start)
        light_end   = clean_time_input(light_end)

        if light_start is None or light_end is None:
            messagebox.showwarning("Cancelled", "Light/Dark not set. Exiting.")
            root.destroy()
            return

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

        frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=frame, anchor="nw")
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
                tk.Label(
                    frame,
                    text=header,
                    font=("Arial", 10, "bold")
                ).grid(row=0, column=col)
            else:
                e = tk.Entry(frame)
                e.insert(0, header)
                e.grid(row=0, column=col)
                header_entries[col] = e

        rows = []

        for i, fname in enumerate(file_map.keys()):
            tk.Label(frame, text=fname).grid(row=i + 1, column=0)

            m = tk.Entry(frame)
            s = tk.Entry(frame)
            g = tk.Entry(frame)

            m.grid(row=i + 1, column=1)
            s.grid(row=i + 1, column=2)
            g.grid(row=i + 1, column=3)

            rows.append({"file": fname, "mouse": m, "sex": s, "geno": g})

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

            metadata_df.to_excel(
                os.path.join(save_folder, "ClosedEconPR1_Metadata.xlsx"),
                index=False
            )

            meta_window.destroy()

        tk.Button(frame, text="Continue", command=collect).grid(
            row=len(rows) + 2,
            column=0,
            columnspan=4
        )

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

    # -------------------------
    # ACTIVE-SIDE AND INCOMPLETE-INTERVAL SETTINGS
    # -------------------------

    active_side_input = askstring(
        "Active Poke Side",
        "Which poke side is active?\n\n"
        "Enter Left, Right, or Auto.\n\n"
        "Auto uses the Active_Poke column when it is available and consistent.",
        initialvalue="Auto"
    )

    if active_side_input is None:
        messagebox.showwarning("Cancelled", "No active side selected. Exiting.")
        root.destroy()
        return

    active_side_input = active_side_input.strip().lower()

    if active_side_input not in ["left", "right", "auto"]:
        messagebox.showerror(
            "Invalid Active Side",
            "Please enter Left, Right, or Auto."
        )
        root.destroy()
        return

    include_incomplete = messagebox.askyesno(
        "Incomplete Final Interval",
        "Include final unfinished ratio interval if there are pokes after the last pellet?"
    )

    # -------------------------
    # PROCESS INDIVIDUAL FILES
    # -------------------------

    all_trials = []

    all_summary = []

    all_demand = []

    all_phase_demand = []

    all_phase_demand_exclusive = []

    processing_errors = []

    for i, (_, row) in enumerate(metadata_df.iterrows()):
        filename = str(row["Filename"]).strip()
        print(f"Processing {i+1}/{len(metadata_df)}", end="\r")

        if filename not in file_map:
            processing_errors.append(
                f"{filename}: not among the selected CSV files"
            )
            continue

        try:
            df = pd.read_csv(file_map[filename], low_memory=False)
            trials_df = build_trials(
                df,
                active_side_input=active_side_input,
                include_incomplete=include_incomplete,
                use_phase=use_phase,
                light_start=light_start,
                light_end=light_end,
            )
        except Exception as error:
            processing_errors.append(f"{filename}: {error}")
            continue

        if trials_df.empty:
            processing_errors.append(f"{filename}: no pellet trials reconstructed")
            continue

        trials_df["Filename"] = filename
        trials_df[mouse_col] = row[mouse_col]
        trials_df[sex_col] = row[sex_col]
        trials_df[group_col] = row[group_col]

        summary = summarize_trials(trials_df)
        summary["Filename"] = filename
        summary[mouse_col] = row[mouse_col]
        summary[sex_col] = row[sex_col]
        summary[group_col] = row[group_col]

        demand = demand_by_fr(trials_df)
        phase_demand = demand_by_fr_phase(trials_df, use_phase)
        phase_demand_exclusive = demand_by_fr_phase(
            trials_df,
            use_phase,
            exclusive_only=True,
        )

        if not demand.empty:
            demand["Filename"] = filename
            demand[mouse_col] = row[mouse_col]
            demand[sex_col] = row[sex_col]
            demand[group_col] = row[group_col]

        if not phase_demand.empty:
            phase_demand["Filename"] = filename
            phase_demand[mouse_col] = row[mouse_col]
            phase_demand[sex_col] = row[sex_col]
            phase_demand[group_col] = row[group_col]

        if not phase_demand_exclusive.empty:
            phase_demand_exclusive["Filename"] = filename
            phase_demand_exclusive[mouse_col] = row[mouse_col]
            phase_demand_exclusive[sex_col] = row[sex_col]
            phase_demand_exclusive[group_col] = row[group_col]

        all_trials.append(trials_df)
        all_summary.append(summary)
        all_demand.append(demand)
        all_phase_demand.append(phase_demand)
        all_phase_demand_exclusive.append(phase_demand_exclusive)

    if len(all_trials) == 0:
        details = "\n".join(processing_errors)
        messagebox.showwarning(
            "No Data",
            "No trials were reconstructed."
            + (f"\n\n{details}" if details else ""),
        )
        root.destroy()
        return

    trials_all_df = pd.concat(all_trials, ignore_index=True)

    summary_df = pd.DataFrame(all_summary)

    demand_df = pd.concat(all_demand, ignore_index=True) if all_demand else pd.DataFrame()

    phase_demand_df = (
        pd.concat(all_phase_demand, ignore_index=True)
        if all_phase_demand else pd.DataFrame()
    )

    phase_demand_exclusive_df = (
        pd.concat(all_phase_demand_exclusive, ignore_index=True)
        if all_phase_demand_exclusive else pd.DataFrame()
    )

    # -------------------------
    # COMBINE, SORT, AND FORMAT OUTPUTS
    # -------------------------

    for df in [trials_all_df, summary_df, demand_df, phase_demand_df, phase_demand_exclusive_df]:
        if not df.empty:
            df[mouse_col] = df[mouse_col].astype(str)
            df["_Mouse_numeric"] = pd.to_numeric(df[mouse_col], errors="coerce")
            sort_cols = [group_col, sex_col, "_Mouse_numeric", mouse_col]

            if "Trial" in df.columns:
                sort_cols.append("Trial")

            if "Phase" in df.columns:
                sort_cols.append("Phase")

            if "FR" in df.columns:
                sort_cols.append("FR")

            df.sort_values(sort_cols, inplace=True)
            df.drop(columns="_Mouse_numeric", inplace=True)

    metadata_cols_left = ["Filename", mouse_col]

    for col in [sex_col, group_col]:
        if col in summary_df.columns and col not in metadata_cols_left:
            metadata_cols_left.append(col)

    trials_all_df = move_metadata_left(trials_all_df)

    summary_df = move_metadata_left(summary_df)

    demand_df = move_metadata_left(demand_df)

    phase_demand_df = move_metadata_left(phase_demand_df)

    phase_demand_exclusive_df = move_metadata_left(phase_demand_exclusive_df)

    trial_front_cols = metadata_cols_left + [
        "Trial",
        "PhaseTrial",
        "ExclusivePhaseTrial",
        "Phase",
        "StartPhase",
        "EndPhase",
        "PhaseCrossing",
        "Block",
        "Completed",
        "StartTime",
        "EndTime"
    ]

    trials_all_df = reorder_columns(trials_all_df, trial_front_cols)

    phase_demand_front_cols = metadata_cols_left + [
        "Phase",
        "FR"
    ]

    phase_demand_df = reorder_columns(phase_demand_df, phase_demand_front_cols)

    phase_demand_exclusive_df = reorder_columns(
        phase_demand_exclusive_df,
        phase_demand_front_cols
    )

    ordered_mice = summary_df[mouse_col].astype(str).tolist()

    # -------------------------
    # EXPORT EXCEL WORKBOOK
    # -------------------------

    output_path = os.path.join(save_folder, "ClosedEconPR1_EXTRAS.xlsx")

    summary_metrics = [
        "TotalPellets",
        "CompletedTrials",
        "TotalPokes",
        "ActivePokes",
        "InactivePokes",
        "Accuracy",
        "InactivePokePercent",
        "PokesPerPellet",
        "ActivePokesPerPellet",
        "InactivePokesPerPellet",
        "PelletsPerHour",
        "ActivePokesPerHour",
        "TotalSessionTime_h",
        "FinalFR",
        "MaxFR",
        "MeanFR",
        "MedianFR",
        "MeanTrialDuration_min",
        "MeanVigor",
        "MeanTotalPokeRate",
        "MeanInactivePokeRate",
        "MeanInactivePokePercent",
        "MeanRetrievalTime",
        "MeanInterPelletInterval",
        "BlocksCompleted",
        "IncompleteFinalInterval",
        "IncompleteFinalPokes"
    ]

    trial_metrics = [
        "FR",
        "ActivePokes",
        "InactivePokes",
        "TotalPokes",
        "Accuracy",
        "InactivePokePercent",
        "Vigor",
        "TotalPokeRate",
        "InactivePokeRate",
        "PokesPerPellet",
        "ActivePokesPerPellet",
        "Duration_min",
        "RetrievalTime",
        "InterPelletInterval",
        "CumulativePellets",
        "CumulativeActivePokes",
        "CumulativeTotalPokes"
    ]

    demand_metrics = [
        "Pellets",
        "ActivePokes",
        "InactivePokes",
        "TotalPokes",
        "TotalDuration_min",
        "PokesPerPellet",
        "ActivePokesPerPellet",
        "InactivePokesPerPellet",
        "PooledAccuracy",
        "InactivePokePercent",
        "PelletsPerMinute",
        "MeanAccuracy",
        "MeanVigor",
        "MeanTotalPokeRate",
        "MeanInactivePokeRate",
        "MeanInactivePokePercent",
        "MeanDuration_min",
        "MeanRetrievalTime",
        "MeanInterPelletInterval"
    ]

    with pd.ExcelWriter(output_path) as writer:

        trials_all_df.to_excel(
            writer,
            sheet_name="Trials",
            index=False,
            float_format="%.5f"
        )

        if use_phase and "PhaseCrossing" in trials_all_df.columns:
            trials_exclusive_df = trials_all_df[
                trials_all_df["PhaseCrossing"].eq(False)
            ].copy()

            if not trials_exclusive_df.empty:
                trials_exclusive_df.to_excel(
                    writer,
                    sheet_name="Trials_ExclusivePhase",
                    index=False,
                    float_format="%.5f"
                )

        summary_df.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
            float_format="%.5f"
        )

        if not demand_df.empty:
            demand_df.to_excel(
                writer,
                sheet_name="Demand_By_FR",
                index=False,
                float_format="%.5f"
            )

        if use_phase and not phase_demand_df.empty:
            phase_demand_df.to_excel(
                writer,
                sheet_name="Demand_By_FR_Phase",
                index=False,
                float_format="%.5f"
            )

        if use_phase and not phase_demand_exclusive_df.empty:
            phase_demand_exclusive_df.to_excel(
                writer,
                sheet_name="Demand_By_FR_Phase_Excl",
                index=False,
                float_format="%.5f"
            )

        for metric in summary_metrics:
            table = make_summary_metric_table(metric)

            if not table.empty:
                table.to_excel(
                    writer,
                    sheet_name=safe_sheet_name(metric),
                    index=False,
                    float_format="%.5f"
                )

        for metric in trial_metrics:
            table = make_trial_metric_table(metric)

            if not table.empty:
                table.to_excel(
                    writer,
                    sheet_name=safe_sheet_name(f"{metric}_Trial"),
                    float_format="%.5f"
                )

        for metric in demand_metrics:
            table = make_demand_metric_table(metric)

            if not table.empty:
                table.to_excel(
                    writer,
                    sheet_name=safe_sheet_name(f"Demand_{metric}"),
                    float_format="%.5f"
                )

        if use_phase and not phase_demand_df.empty:
            for phase, d_phase in phase_demand_df.groupby("Phase"):

                for metric in demand_metrics:
                    table = make_demand_metric_table(
                        metric,
                        data=d_phase
                    )

                    if not table.empty:
                        table.to_excel(
                            writer,
                            sheet_name=safe_sheet_name(f"Demand_{metric}_{phase}"),
                            float_format="%.5f"
                        )

        if use_phase and not phase_demand_exclusive_df.empty:
            for phase, d_phase in phase_demand_exclusive_df.groupby("Phase"):

                for metric in demand_metrics:
                    table = make_demand_metric_table(
                        metric,
                        data=d_phase
                    )

                    if not table.empty:
                        table.to_excel(
                            writer,
                            sheet_name=safe_sheet_name(f"ExclDemand_{phase}_{metric}"),
                            float_format="%.5f"
                        )

        if use_phase:
            for phase, d_phase in trials_all_df.groupby("Phase"):
                d_phase_completed = d_phase[d_phase["Completed"].eq(1)].copy()
                d_phase_exclusive = d_phase_completed[
                    d_phase_completed["PhaseCrossing"].eq(False)
                ].copy()

                for metric in trial_metrics:
                    table = make_trial_metric_table(
                        metric,
                        data=d_phase_completed,
                        index_col="PhaseTrial"
                    )

                    if not table.empty:
                        table.to_excel(
                            writer,
                            sheet_name=safe_sheet_name(f"{metric}_{phase}"),
                            float_format="%.5f"
                        )

                    exclusive_table = make_trial_metric_table(
                        metric,
                        data=d_phase_exclusive,
                        index_col="ExclusivePhaseTrial"
                    )

                    if not exclusive_table.empty:
                        exclusive_table.to_excel(
                            writer,
                            sheet_name=safe_sheet_name(f"Excl_{phase}_{metric}"),
                            float_format="%.5f"
                        )

    # -------------------------
    # CONFIGURE PLOTS
    # -------------------------

    plots_folder = os.path.join(save_folder, "ClosedEconPR1_Plots")

    if not os.path.exists(plots_folder):
        os.makedirs(plots_folder)

    show_plots = messagebox.askyesno(
        "Plot Display",
        "Display plots?\n\nYes = show plots\nNo = save only"
    )

    save_individual_timecourse_plots = messagebox.askyesno(
        "Individual Timecourse Plots",
        "Save individual mouse versions of the stacked timecourse plots?"
    )

    use_custom_colors = messagebox.askyesno(
        "Plot Colours",
        "Would you like to choose custom colours for Sex and Genotype groups?"
    )

    unique_groups = sorted(metadata_df[group_col].dropna().astype(str).unique())

    unique_sexes = sorted(metadata_df[sex_col].dropna().astype(str).unique())

    group_colors = build_color_map(unique_groups)

    sex_colors = build_color_map(unique_sexes)

    if use_custom_colors:

        for grp in unique_groups:
            color = colorchooser.askcolor(title=f"Choose colour for {grp}")[1]

            if color is not None:
                group_colors[str(grp)] = color

        for sex in unique_sexes:
            color = colorchooser.askcolor(title=f"Choose colour for {sex}")[1]

            if color is not None:
                sex_colors[str(sex)] = color

    # -------------------------
    # GENERATE PLOTS
    # -------------------------

    summary_df = summary_df.copy()

    completed_trials = trials_all_df[trials_all_df["Completed"].eq(1)].copy()

    summary_df["Combined_Group"] = (
        summary_df[sex_col].astype(str)
        + "_"
        + summary_df[group_col].astype(str)
    )

    completed_trials["Combined_Group"] = (
        completed_trials[sex_col].astype(str)
        + "_"
        + completed_trials[group_col].astype(str)
    )

    if not demand_df.empty:
        demand_df = demand_df.copy()

        demand_df["Combined_Group"] = (
            demand_df[sex_col].astype(str)
            + "_"
            + demand_df[group_col].astype(str)
        )

    if not phase_demand_df.empty:
        phase_demand_df = phase_demand_df.copy()

        phase_demand_df["Combined_Group"] = (
            phase_demand_df[sex_col].astype(str)
            + "_"
            + phase_demand_df[group_col].astype(str)
        )

    if not phase_demand_exclusive_df.empty:
        phase_demand_exclusive_df = phase_demand_exclusive_df.copy()

        phase_demand_exclusive_df["Combined_Group"] = (
            phase_demand_exclusive_df[sex_col].astype(str)
            + "_"
            + phase_demand_exclusive_df[group_col].astype(str)
        )

    plot_stacked_individual_timecourse(
        completed_trials,
        metric="Block_Pellet_Count",
        ylabel="Pellet Count in Block",
        title="Individual Block Progression",
        filename="Stacked_BlockPelletCount_by_time.png",
        color_by_value=True
    )

    plot_stacked_individual_timecourse(
        completed_trials,
        metric="FR",
        ylabel="FR",
        title="Individual FR Progression",
        filename="Stacked_FR_by_time.png"
    )

    plot_stacked_individual_timecourse(
        completed_trials,
        metric="CumulativePellets",
        ylabel="Cumulative Pellets",
        title="Individual Cumulative Pellets",
        filename="Stacked_CumulativePellets_by_time.png"
    )

    summary_plot_metrics = [
        "TotalPellets",
        "CompletedTrials",
        "TotalPokes",
        "ActivePokes",
        "InactivePokes",
        "Accuracy",
        "InactivePokePercent",
        "PokesPerPellet",
        "ActivePokesPerPellet",
        "InactivePokesPerPellet",
        "PelletsPerHour",
        "ActivePokesPerHour",
        "TotalSessionTime_h",
        "FinalFR",
        "MaxFR",
        "MeanFR",
        "MedianFR",
        "MeanTrialDuration_min",
        "MeanVigor",
        "MeanTotalPokeRate",
        "MeanInactivePokeRate",
        "MeanInactivePokePercent",
        "MeanRetrievalTime",
        "MeanInterPelletInterval",
        "BlocksCompleted",
        "IncompleteFinalInterval",
        "IncompleteFinalPokes"
    ]

    for metric in summary_plot_metrics:

        plot_summary_stripplot(
            summary_df,
            metric=metric,
            x_col=group_col,
            hue_col=sex_col,
            title=f"{metric} (Individual Mice)",
            filename=build_plot_filename(metric, group_col_plot=group_col)
        )

        plot_summary_stripplot(
            summary_df,
            metric=metric,
            x_col=sex_col,
            hue_col=group_col,
            title=f"{metric} (by {sex_col})",
            filename=build_plot_filename(metric, group_col_plot=sex_col)
        )

        plot_summary_stripplot(
            summary_df,
            metric=metric,
            x_col="Combined_Group",
            title=f"{metric} ({sex_col} x {group_col})",
            filename=build_plot_filename(metric, group_col_plot=f"{sex_col}_{group_col}")
        )

        plot_split_second_third(
            summary_df,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=lambda data, group_col_plot, title, filename, metric=metric:
                plot_summary_stripplot(
                    data,
                    metric=metric,
                    x_col=group_col_plot,
                    title=title,
                    filename=filename
                ),
            metric_name=metric,
            title_prefix=metric
        )

        plot_split_second_third(
            summary_df,
            split_col=group_col,
            compare_col=sex_col,
            plot_func=lambda data, group_col_plot, title, filename, metric=metric:
                plot_summary_stripplot(
                    data,
                    metric=metric,
                    x_col=group_col_plot,
                    title=title,
                    filename=filename
                ),
            metric_name=metric,
            title_prefix=metric
        )

    trial_plot_metrics = {
        "CumulativePellets": "Cumulative Pellets",
        "FR": "FR",
        "Duration_min": "Duration (min)",
        "PokesPerPellet": "Pokes Per Pellet",
        "ActivePokesPerPellet": "Active Pokes Per Pellet",
        "ActivePokes": "Active Pokes",
        "InactivePokes": "Inactive Pokes",
        "TotalPokes": "Total Pokes",
        "Accuracy": "Accuracy (%)",
        "InactivePokePercent": "Inactive Pokes (%)",
        "Vigor": "Vigor (Active Pokes/min)",
        "TotalPokeRate": "Total Pokes/min",
        "InactivePokeRate": "Inactive Pokes/min",
        "RetrievalTime": "Retrieval Time",
        "InterPelletInterval": "Interpellet Interval",
        "CumulativeActivePokes": "Cumulative Active Pokes",
        "CumulativeTotalPokes": "Cumulative Total Pokes"
    }

    for metric, ylabel in trial_plot_metrics.items():

        trial_plot_func = (
            lambda data, group_col_plot, title, filename, metric=metric, ylabel=ylabel, x_col="Trial":
                plot_trial_trajectory(
                    data,
                    metric=metric,
                    group_col_plot=group_col_plot,
                    title=title,
                    filename=filename,
                    ylabel=ylabel,
                    x_col=x_col
                )
        )

        trial_plot_func(
            completed_trials,
            group_col_plot=group_col,
            title=f"{ylabel} (by {group_col})",
            filename=build_plot_filename(metric, group_col_plot=group_col)
        )

        trial_plot_func(
            completed_trials,
            group_col_plot=sex_col,
            title=f"{ylabel} (by {sex_col})",
            filename=build_plot_filename(metric, group_col_plot=sex_col)
        )

        plot_split_second_third(
            completed_trials,
            split_col=sex_col,
            compare_col=group_col,
            plot_func=trial_plot_func,
            metric_name=metric,
            title_prefix=ylabel
        )

        plot_split_second_third(
            completed_trials,
            split_col=group_col,
            compare_col=sex_col,
            plot_func=trial_plot_func,
            metric_name=metric,
            title_prefix=ylabel
        )

        if use_phase:

            for phase, d_phase in completed_trials.groupby("Phase"):
                d_phase_exclusive = d_phase[
                    d_phase["PhaseCrossing"].eq(False)
                ].copy()

                trial_plot_func(
                    d_phase,
                    group_col_plot=group_col,
                    title=f"{ylabel} (by {group_col}, {phase})",
                    filename=build_plot_filename(metric, group_col_plot=group_col, phase=phase),
                    x_col="PhaseTrial"
                )

                trial_plot_func(
                    d_phase,
                    group_col_plot=sex_col,
                    title=f"{ylabel} (by {sex_col}, {phase})",
                    filename=build_plot_filename(metric, group_col_plot=sex_col, phase=phase),
                    x_col="PhaseTrial"
                )

                trial_plot_func(
                    d_phase_exclusive,
                    group_col_plot=group_col,
                    title=f"{ylabel} (by {group_col}, {phase}, Exclusive)",
                    filename=build_plot_filename(metric, group_col_plot=group_col, phase=phase, exclusive=True),
                    x_col="ExclusivePhaseTrial"
                )

                trial_plot_func(
                    d_phase_exclusive,
                    group_col_plot=sex_col,
                    title=f"{ylabel} (by {sex_col}, {phase}, Exclusive)",
                    filename=build_plot_filename(metric, group_col_plot=sex_col, phase=phase, exclusive=True),
                    x_col="ExclusivePhaseTrial"
                )

            plot_split_second_third_phase(
                completed_trials,
                split_col=sex_col,
                compare_col=group_col,
                plot_func=trial_plot_func,
                metric_name=metric,
                title_prefix=ylabel
            )

            plot_split_second_third_phase(
                completed_trials,
                split_col=group_col,
                compare_col=sex_col,
                plot_func=trial_plot_func,
                metric_name=metric,
                title_prefix=ylabel
            )

            completed_trials_exclusive = completed_trials[
                completed_trials["PhaseCrossing"].eq(False)
            ].copy()

            plot_split_second_third_phase(
                completed_trials_exclusive,
                split_col=sex_col,
                compare_col=group_col,
                plot_func=trial_plot_func,
                metric_name=metric,
                title_prefix=f"{ylabel} Exclusive",
                x_col="ExclusivePhaseTrial",
                exclusive=True
            )

            plot_split_second_third_phase(
                completed_trials_exclusive,
                split_col=group_col,
                compare_col=sex_col,
                plot_func=trial_plot_func,
                metric_name=metric,
                title_prefix=f"{ylabel} Exclusive",
                x_col="ExclusivePhaseTrial",
                exclusive=True
            )

    demand_plot_metrics = {
        "Pellets": "Pellets",
        "ActivePokes": "Active Pokes",
        "InactivePokes": "Inactive Pokes",
        "TotalPokes": "Total Pokes",
        "TotalDuration_min": "Total Duration (min)",
        "PokesPerPellet": "Pokes Per Pellet",
        "ActivePokesPerPellet": "Active Pokes Per Pellet",
        "InactivePokesPerPellet": "Inactive Pokes Per Pellet",
        "PooledAccuracy": "Pooled Accuracy (%)",
        "MeanAccuracy": "Mean Accuracy (%)",
        "InactivePokePercent": "Pooled Inactive Pokes (%)",
        "PelletsPerMinute": "Pellets Per Minute",
        "MeanVigor": "Mean Vigor (Active Pokes/min)",
        "MeanTotalPokeRate": "Mean Total Pokes/min",
        "MeanInactivePokeRate": "Mean Inactive Pokes/min",
        "MeanInactivePokePercent": "Mean Inactive Pokes (%)",
        "MeanDuration_min": "Mean Duration (min)",
        "MeanRetrievalTime": "Mean Retrieval Time",
        "MeanInterPelletInterval": "Mean Interpellet Interval"
    }

    if not demand_df.empty:

        for metric, ylabel in demand_plot_metrics.items():

            demand_plot_func = (
                lambda data, group_col_plot, title, filename, metric=metric, ylabel=ylabel:
                    plot_demand(
                        data,
                        metric=metric,
                        group_col_plot=group_col_plot,
                        title=title,
                        filename=filename,
                        ylabel=ylabel
                    )
            )

            demand_plot_func(
                demand_df,
                group_col_plot=group_col,
                title=f"Demand: {ylabel} by FR ({group_col})",
                filename=build_plot_filename(f"Demand_{metric}", group_col_plot=group_col)
            )

            demand_plot_func(
                demand_df,
                group_col_plot=sex_col,
                title=f"Demand: {ylabel} by FR ({sex_col})",
                filename=build_plot_filename(f"Demand_{metric}", group_col_plot=sex_col)
            )

            plot_split_second_third(
                demand_df,
                split_col=sex_col,
                compare_col=group_col,
                plot_func=demand_plot_func,
                metric_name=f"Demand_{metric}",
                title_prefix=f"Demand: {ylabel} by FR"
            )

            plot_split_second_third(
                demand_df,
                split_col=group_col,
                compare_col=sex_col,
                plot_func=demand_plot_func,
                metric_name=f"Demand_{metric}",
                title_prefix=f"Demand: {ylabel} by FR"
            )

            if use_phase and not phase_demand_df.empty:

                for phase, d_phase in phase_demand_df.groupby("Phase"):

                    demand_plot_func(
                        d_phase,
                        group_col_plot=group_col,
                        title=f"Demand: {ylabel} by FR ({group_col}, {phase})",
                        filename=build_plot_filename(f"Demand_{metric}", group_col_plot=group_col, phase=phase)
                    )

                    demand_plot_func(
                        d_phase,
                        group_col_plot=sex_col,
                        title=f"Demand: {ylabel} by FR ({sex_col}, {phase})",
                        filename=build_plot_filename(f"Demand_{metric}", group_col_plot=sex_col, phase=phase)
                    )

                plot_split_second_third_demand_phase(
                    phase_demand_df,
                    split_col=sex_col,
                    compare_col=group_col,
                    plot_func=demand_plot_func,
                    metric_name=f"Demand_{metric}",
                    title_prefix=f"Demand: {ylabel} by FR"
                )

                plot_split_second_third_demand_phase(
                    phase_demand_df,
                    split_col=group_col,
                    compare_col=sex_col,
                    plot_func=demand_plot_func,
                    metric_name=f"Demand_{metric}",
                    title_prefix=f"Demand: {ylabel} by FR"
                )

            if use_phase and not phase_demand_exclusive_df.empty:

                for phase, d_phase in phase_demand_exclusive_df.groupby("Phase"):

                    demand_plot_func(
                        d_phase,
                        group_col_plot=group_col,
                        title=f"Demand: {ylabel} by FR ({group_col}, {phase}, Exclusive)",
                        filename=build_plot_filename(f"Demand_{metric}", group_col_plot=group_col, phase=phase, exclusive=True)
                    )

                    demand_plot_func(
                        d_phase,
                        group_col_plot=sex_col,
                        title=f"Demand: {ylabel} by FR ({sex_col}, {phase}, Exclusive)",
                        filename=build_plot_filename(f"Demand_{metric}", group_col_plot=sex_col, phase=phase, exclusive=True)
                    )

                plot_split_second_third_demand_phase(
                    phase_demand_exclusive_df,
                    split_col=sex_col,
                    compare_col=group_col,
                    plot_func=demand_plot_func,
                    metric_name=f"Demand_{metric}",
                    title_prefix=f"Demand: {ylabel} by FR Exclusive",
                    exclusive=True
                )

                plot_split_second_third_demand_phase(
                    phase_demand_exclusive_df,
                    split_col=group_col,
                    compare_col=sex_col,
                    plot_func=demand_plot_func,
                    metric_name=f"Demand_{metric}",
                    title_prefix=f"Demand: {ylabel} by FR Exclusive",
                    exclusive=True
                )

    plot_group_sex_heatmap(
        summary_df,
        title=f"ClosedEcon PR1 Summary ({group_col} x {sex_col})",
        filename=build_plot_filename("ClosedEconPR1_heatmap", group_col_plot=f"{group_col}_{sex_col}")
    )

    if processing_errors:
        error_path = os.path.join(
            save_folder,
            "ClosedEconPR1_processing_errors.txt",
        )
        with open(error_path, "w", encoding="utf-8") as error_file:
            error_file.write("\n".join(processing_errors))
        print(f"\nSome files were skipped. Details saved to:\n{error_path}")

    print(f"\nPrism-ready file saved:\n{output_path}")

    messagebox.showinfo(
        "Done",
        f"ClosedEcon PR1 analysis complete.\n\nSaved:\n{output_path}"
    )

    root.destroy()


def main():
    try:
        run_gui()
    except Exception as error:
        try:
            messagebox.showerror(
                "ClosedEcon PR1 Error",
                f"The analysis stopped because of an unexpected error:\n\n{error}",
            )
        except Exception:
            pass
        raise



if __name__ == "__main__":
    main()
