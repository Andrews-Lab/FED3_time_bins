import numpy as np
import pandas as pd


# These session types already have their own specialised processing.
# Other session types use the ordinary time-bin pathway and may receive the optional ClassicFED enhancements.
SPECIALISED_SESSION_TYPES = {
    "ClosedEcon_PR1",
    "Incomplete_ClosedEcon",
    "Bandit",
    "StopSig",
    "LeftRight",
}


CLASSIC_TIME_SERIES_METRICS = [
    "Poke Accuracy (%)",
    "Active Poke Efficiency (%)",
    "Total Poke Efficiency (%)",
    "Sum Retrieval Time (secs)",
    "Sum IPI (secs)",
    "Sum Poke Time (secs)",
]


CLASSIC_AVERAGE_METRICS = [
    "Average Retrieval Time (secs)",
    "Average IPI (secs)",
    "Average Poke Time (secs)",
]


COUNT_COLUMNS = [
    "Left Poke Count",
    "Right Poke Count",
    "Pellet Count",
    "Block Pellet Count",
]


SUM_COLUMNS = [
    "Sum Retrieval Time (secs)",
    "Sum IPI (secs)",
    "Sum Poke Time (secs)",
]


def supports_classic_enhancements(session_type):
    """
    Return True for session types using the ordinary time-bin
    pathway rather than specialised long-session analysis.
    """
    return (
        pd.notna(session_type)
        and str(session_type) not in SPECIALISED_SESSION_TYPES
    )


def normalise_active_poke(value):
    """
    Convert L, Left, R or Right into Left or Right.
    """
    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    if value.startswith("l"):
        return "Left"

    if value.startswith("r"):
        return "Right"

    return None


def find_active_poke(df, inputs):
    """
    Determine the active poke using the selected GUI mode.

    Auto uses the CSV's Active Poke column and skips active-side
    metrics if it is unavailable or ambiguous. Left/Right fallback
    still prefer a usable CSV value, then use the selected side.
    Skip always disables active-side metrics.
    """
    mode = inputs.get(
        "Classic active poke fallback",
        "Auto",
    )

    # Remain compatible with settings saved by the earlier version.
    mode = {
        "Left": "Left fallback",
        "Right": "Right fallback",
    }.get(mode, mode)

    if mode == "Skip active-side metrics":
        return None

    if "Active Poke" in df.columns:
        active_values = (
            df["Active Poke"]
            .apply(normalise_active_poke)
            .dropna()
            .unique()
            .tolist()
        )

        if len(active_values) == 1:
            return active_values[0]

    if mode == "Left fallback":
        return "Left"

    if mode == "Right fallback":
        return "Right"

    return None


def safe_percentage(numerator, denominator):
    """
    Match Classicfix by returning zero when the denominator is zero.
    """
    numerator = pd.to_numeric(
        numerator,
        errors="coerce",
    ).fillna(0)

    denominator = pd.to_numeric(
        denominator,
        errors="coerce",
    ).fillna(0)

    result = pd.Series(0.0, index=denominator.index)
    valid = denominator != 0

    result.loc[valid] = (
        numerator.loc[valid] / denominator.loc[valid]
    ) * 100

    return result


def standardise_classic_duration(df_bins, inputs):
    """
    Crop or extend time bins to the optional target duration.

    Cumulative count columns are carried forward into extended
    rows. Event-value columns remain blank because no additional
    event occurred in those artificial rows.
    """
    target_duration = inputs.get("Classic duration (mins)")

    if target_duration in [None, ""]:
        return df_bins

    target_duration = float(target_duration)
    time_bin = float(inputs["Time bin (mins)"])

    output = df_bins.copy()

    # Reduce floating-point mismatch when reindexing.
    output.index = pd.Index(
        np.round(
            np.asarray(
                pd.to_numeric(output.index),
                dtype=float,
            ),
            10,
        ),
        name=output.index.name,
    )

    new_index = np.arange(
        0,
        target_duration + (time_bin / 2),
        time_bin,
    )

    new_index = pd.Index(
        np.round(new_index, 10),
        name=output.index.name,
    )

    output = output.reindex(new_index)

    carry_forward_columns = [
        column
        for column in COUNT_COLUMNS + SUM_COLUMNS
        if column in output.columns
    ]

    if carry_forward_columns:
        output[carry_forward_columns] = (
            output[carry_forward_columns]
            .ffill()
            .fillna(0)
        )

    descriptive_columns = [
        "Library Version",
        "Session Type",
        "Motor Turns",
        "FR",
    ]

    available_descriptive = [
        column
        for column in descriptive_columns
        if column in output.columns
    ]

    if available_descriptive:
        output[available_descriptive] = (
            output[available_descriptive]
            .ffill()
            .bfill()
        )

    return output


def add_poke_metrics(df_bins, raw_df, inputs):
    """
    Add the poke-related metrics when the required columns exist.
    """
    output = df_bins.copy()

    required_columns = {
        "Left Poke Count",
        "Right Poke Count",
        "Pellet Count",
    }

    if not required_columns.issubset(output.columns):
        return output

    left_pokes = pd.to_numeric(
        output["Left Poke Count"],
        errors="coerce",
    )

    right_pokes = pd.to_numeric(
        output["Right Poke Count"],
        errors="coerce",
    )

    pellets = pd.to_numeric(
        output["Pellet Count"],
        errors="coerce",
    )

    total_pokes = left_pokes + right_pokes

    # This metric does not require identification of an active side.
    output["Total Poke Efficiency (%)"] = safe_percentage(
        pellets,
        total_pokes,
    )

    active_side = find_active_poke(
        raw_df,
        inputs,
    )

    # Accuracy and active efficiency cannot be calculated without a meaningful active side.
    if active_side is None:
        return output

    if active_side == "Left":
        active_pokes = left_pokes
    else:
        active_pokes = right_pokes

    output["Poke Accuracy (%)"] = safe_percentage(
        active_pokes,
        total_pokes,
    )

    output["Active Poke Efficiency (%)"] = safe_percentage(
        pellets,
        active_pokes,
    )

    return output


def add_event_timing_metrics(df_bins, inputs):
    """
    Match Classicfix's event-sheet calculations.

    Running sums and averages both use the genuine time-bin rows that
    exist before duration extension. Zero-event bins are included in
    the average, as in the original master sheet. A shorter target
    duration crops the source rows used by the average; a longer target
    never adds artificial rows to the average.
    """
    output = df_bins.copy()
    target_duration = inputs.get("Classic duration (mins)")
    average_source = output

    if target_duration not in [None, ""]:
        numeric_index = pd.to_numeric(
            average_source.index,
            errors="coerce",
        )
        average_source = average_source[
            numeric_index <= float(target_duration)
        ]

    sum_names = {
        "Retrieval Time": "Sum Retrieval Time (secs)",
        "Interpellet Interval": "Sum IPI (secs)",
        "Poke Time": "Sum Poke Time (secs)",
    }

    average_names = {
        "Retrieval Time": "Average Retrieval Time (secs)",
        "Interpellet Interval": "Average IPI (secs)",
        "Poke Time": "Average Poke Time (secs)",
    }

    for source_column, sum_column in sum_names.items():
        if source_column not in output.columns:
            continue

        values = pd.to_numeric(
            output[source_column],
            errors="coerce",
        )

        output[sum_column] = values.cumsum()

    for source_column, average_column in average_names.items():
        if source_column not in average_source.columns:
            continue

        values = pd.to_numeric(
            average_source[source_column],
            errors="coerce",
        ).dropna()

        output[average_column] = np.nan

        if len(values) > 0 and len(output) > 0:
            column_number = output.columns.get_loc(
                average_column
            )

            output.iloc[0, column_number] = values.mean()

    return output


def add_classic_metrics(df_bins, raw_df, inputs):
    """
    Apply the optional ClassicFED enhancements to one file.
    """
    if not inputs.get("Create Classic metric sheets", False):
        return df_bins

    if not supports_classic_enhancements(
        inputs.get("Session Type")
    ):
        return df_bins

    # Calculate event sums and averages before duration extension so artificial rows cannot affect the averages.
    output = add_event_timing_metrics(
        df_bins.copy(),
        inputs,
    )

    # Crop or extend after event calculations. Cumulative sum columns are carried forward through padded rows by this function.
    output = standardise_classic_duration(
        output,
        inputs,
    )

    output = add_poke_metrics(
        output,
        raw_df,
        inputs,
    )

    return output
