import os
import re
import hashlib
import matplotlib
matplotlib.use("agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from Create_classic_metrics import (
    CLASSIC_AVERAGE_METRICS,
    supports_classic_enhancements,
)
from Create_cumulative_master import get_sum_metrics, normalise_name

sns.set_theme(style="white", font_scale=1.2)


CLASSIC_TRAJECTORY_METRICS = [
    "Left Poke Count",
    "Right Poke Count",
    "Pellet Count",
    "Block Pellet Count",
    "Poke Accuracy (%)",
    "Active Poke Efficiency (%)",
    "Total Poke Efficiency (%)",
    "Sum Retrieval Time (secs)",
    "Sum IPI (secs)",
    "Sum Poke Time (secs)",
]


LONG_IDENTIFIER_COLUMNS = {
    "Filename",
    "Number of blocks",
    "Block numbers",
    "Cycles",
    "Days",
    "Total",
    "Light/Dark",
    "Completed cycles",
    "Completed days",
    "Start time",
    "End time",
}


def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*]+', "_", str(value).strip())
    value = re.sub(r"\s+", "_", value)
    return value.strip("._")


def clean_metadata_label(value):
    if pd.isna(value):
        return value
    return " ".join(str(value).split())


def metadata_to_table(metadata):
    output = metadata.copy().reset_index()
    first_column = output.columns[0]
    if first_column != "Filename":
        output = output.rename(columns={first_column: "Filename"})
    for column in output.columns:
        output[column] = output[column].map(clean_metadata_label)
    output["Filename"] = output["Filename"].astype(str).str.strip()
    return output


def build_color_map(values):
    values = sorted({str(value) for value in values if pd.notna(value)})
    if not values:
        return {}
    palette = sns.color_palette("tab10", n_colors=len(values)).as_hex()
    return dict(zip(values, palette))


def resolve_color_map(data, grouping_column, inputs):
    values = data[grouping_column].dropna().astype(str).unique()
    defaults = build_color_map(values)
    saved_maps = inputs.get("Plot color maps", {})
    chosen = saved_maps.get(grouping_column, {})
    defaults.update({str(key): value for key, value in chosen.items() if value})
    return defaults


def add_combined_group(data, primary_group, secondary_group):
    output = data.copy()
    output["Combined group"] = (
        output[primary_group].map(clean_metadata_label).astype(str)
        + " x "
        + output[secondary_group].map(clean_metadata_label).astype(str)
    )
    return output


def build_grouping_specs(data, inputs):
    primary = inputs.get("Plot primary group")
    secondary = inputs.get("Plot secondary group")
    preset = inputs.get("Plot preset", "Basic")
    specs = []

    if primary and primary in data.columns:
        specs.append((primary, f"By_{safe_filename(primary)}", None, None))

    if secondary and secondary != "None" and secondary in data.columns:
        if preset == "Full":
            specs.append((secondary, f"By_{safe_filename(secondary)}", None, None))

        if primary and primary in data.columns:
            split_values = sorted({
                clean_metadata_label(value)
                for value in data[secondary].dropna()
            })
            for split_value in split_values:
                specs.append(
                    (
                        primary,
                        f"{safe_filename(primary)}_x_{safe_filename(secondary)}",
                        secondary,
                        split_value,
                    )
                )

    return data, specs


def metric_table_to_long(metric_table, metric, metadata):
    if metric_table.empty:
        return pd.DataFrame()

    data = metric_table.copy()
    data.index = pd.to_numeric(data.index, errors="coerce")
    data.index.name = "Index"
    data = data.reset_index().melt(
        id_vars="Index",
        var_name="Filename",
        value_name="Value",
    )
    data["Filename"] = data["Filename"].astype(str).str.strip()
    data["Value"] = pd.to_numeric(data["Value"], errors="coerce")
    data = data.dropna(subset=["Index", "Value"])
    data = data.merge(
        metadata_to_table(metadata),
        on="Filename",
        how="left",
        validate="many_to_one",
    )
    data["Metric"] = metric
    data["Level"] = "Time bin"
    data["Route Level"] = "Time bin"
    data["Phase"] = "All"
    data["Route Phase"] = "All"
    data["Subset"] = "All data"
    data["Source"] = "Normal"
    data["Cumulative"] = False
    data["Order"] = data["Index"]
    return data


def classic_average_to_long(metric_table, metric, metadata):
    if metric_table.empty:
        return pd.DataFrame()

    data = metric_table.copy()
    if "Mean" in data.index:
        values = data.loc["Mean"]
    else:
        values = data.apply(pd.to_numeric, errors="coerce").iloc[0]

    output = values.rename("Value").rename_axis("Filename").reset_index()
    output["Filename"] = output["Filename"].astype(str).str.strip()
    output["Value"] = pd.to_numeric(output["Value"], errors="coerce")
    output = output.dropna(subset=["Value"])
    output = output.merge(
        metadata_to_table(metadata),
        on="Filename",
        how="left",
        validate="many_to_one",
    )
    output["Metric"] = metric
    output["Index"] = 1.0
    output["Order"] = 1
    output["Level"] = "Total"
    output["Route Level"] = "Time bin"
    output["Phase"] = "All"
    output["Route Phase"] = "All"
    output["Subset"] = "Classic averages"
    output["Source"] = "Normal"
    output["Cumulative"] = False
    return output


def collect_classic_plot_data(master, metadata):
    collected = []
    for metric in CLASSIC_TRAJECTORY_METRICS:
        if metric not in master:
            continue
        metric_data = metric_table_to_long(master[metric], metric, metadata)
        if not metric_data.empty:
            collected.append(metric_data)

    for metric in CLASSIC_AVERAGE_METRICS:
        if metric not in master:
            continue
        metric_data = classic_average_to_long(master[metric], metric, metadata)
        if not metric_data.empty:
            collected.append(metric_data)
    if not collected:
        return pd.DataFrame()
    return pd.concat(collected, ignore_index=True)


def identify_level(subset_name):
    upper = str(subset_name).upper()
    if upper.endswith("_BLOCKS"):
        return "Block"
    if upper.endswith("_CYCLES"):
        return "Cycle"
    if upper.endswith("_DAYS"):
        return "Day"
    if upper.endswith("_TOTAL") or upper == "TOTAL":
        return "Total"
    return None


def identify_route_phase(subset_name):
    name = str(subset_name)
    if "_Light_" in name:
        return "Light"
    if "_Dark_" in name:
        return "Dark"
    return "All"


def identify_route_level(subset_name, level):
    if level != "Total":
        return level

    name = str(subset_name)
    # TOTAL subsets describe the completed unit used to construct them.
    # Route cycle totals into Cycles and day totals into Days.
    if "Cycles" in name:
        return "Cycle"
    if "Days" in name:
        return "Day"
    if "Blocks" in name:
        return "Block"
    return "Total"


def identify_index_column(level, columns):
    candidates = {
        "Block": ["Number of blocks", "Block numbers"],
        "Cycle": ["Cycles"],
        "Day": ["Days"],
    }.get(level, [])
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def collect_long_session_plot_data(session_master, session_type, metadata):
    collected = []
    metadata_table = metadata_to_table(metadata)

    for subset_name, records in session_master.items():
        level = identify_level(subset_name)
        if level is None or not records:
            continue

        table = pd.DataFrame(records)
        if table.empty or "Filename" not in table.columns:
            continue

        table["Filename"] = table["Filename"].astype(str).str.strip()
        table["Order"] = table.groupby("Filename", sort=False).cumcount() + 1
        index_column = identify_index_column(level, table.columns)

        if level == "Total":
            table["Index"] = 1.0
        elif index_column is not None:
            table["Index"] = pd.to_numeric(table[index_column], errors="coerce")
            table["Index"] = table["Index"].fillna(table["Order"])
        else:
            table["Index"] = table["Order"].astype(float)

        route_phase = identify_route_phase(subset_name)
        if route_phase != "All":
            table["Phase"] = route_phase
        elif "Light/Dark" in table.columns:
            phase = table["Light/Dark"].astype(str)
            table["Phase"] = phase.where(phase.isin(["Light", "Dark"]), "All")
        else:
            table["Phase"] = "All"

        metric_columns = []
        for column in table.columns:
            if column in LONG_IDENTIFIER_COLUMNS or column in {
                "Index", "Order", "Phase"
            }:
                continue
            numeric = pd.to_numeric(table[column], errors="coerce")
            if numeric.notna().any():
                table[column] = numeric
                metric_columns.append(column)

        if not metric_columns:
            continue

        long_data = table.melt(
            id_vars=["Filename", "Index", "Order", "Phase"],
            value_vars=metric_columns,
            var_name="Metric",
            value_name="Value",
        ).dropna(subset=["Value"])

        long_data["Session Type"] = session_type
        long_data["Level"] = level
        long_data["Route Level"] = identify_route_level(subset_name, level)
        long_data["Route Phase"] = route_phase
        long_data["Subset"] = str(subset_name)
        long_data["Source"] = "Normal"
        long_data["Cumulative"] = False
        collected.append(long_data)

    if not collected:
        return pd.DataFrame()

    data = pd.concat(collected, ignore_index=True)
    data = data.merge(
        metadata_table,
        on="Filename",
        how="left",
        validate="many_to_one",
    )
    return data


def final_metric_table_to_long(metric_table, subset_name, metric, metadata):
    """Convert one finalized Excel metric sheet into plotting records."""
    table = getattr(metric_table, "data", metric_table).copy()
    if table.empty:
        return pd.DataFrame()

    level = identify_level(subset_name)
    if level is None:
        return pd.DataFrame()

    rows = []
    route_phase = identify_route_phase(subset_name)
    for column in table.columns:
        filename = column[0] if isinstance(column, tuple) else column
        values = pd.to_numeric(table[column], errors="coerce")
        for index_value, value in values.items():
            if pd.isna(value):
                continue

            if isinstance(index_value, tuple):
                plot_index = index_value[0]
                index_phase = index_value[1] if len(index_value) > 1 else "All"
            else:
                plot_index = index_value
                index_phase = "All"

            phase = route_phase
            if phase == "All" and str(index_phase) in ["Light", "Dark"]:
                phase = str(index_phase)

            rows.append({
                "Filename": str(filename).strip(),
                "Index": pd.to_numeric(plot_index, errors="coerce"),
                "Order": len(rows) + 1,
                "Phase": phase,
                "Metric": metric,
                "Value": value,
                "Session Type": None,
                "Level": level,
                "Route Level": identify_route_level(subset_name, level),
                "Route Phase": route_phase,
                "Subset": str(subset_name),
                "Source": "Normal",
                "Cumulative": False,
            })

    if not rows:
        return pd.DataFrame()
    output = pd.DataFrame(rows).dropna(subset=["Index", "Value"])
    return output.merge(
        metadata_to_table(metadata),
        on="Filename",
        how="left",
        validate="many_to_one",
    )


def final_total_table_to_long(table, subset_name, session_type, metadata):
    """Convert one finalized combined-master TOTAL tab into plot records."""
    table = table.copy()
    if table.empty or "Filename" not in table.columns:
        return pd.DataFrame()

    metadata_columns = set(metadata.columns)
    identifiers = LONG_IDENTIFIER_COLUMNS | metadata_columns
    metric_columns = []
    for column in table.columns:
        if column in identifiers:
            continue
        numeric = pd.to_numeric(table[column], errors="coerce")
        if numeric.notna().any():
            table[column] = numeric
            metric_columns.append(column)
    if not metric_columns:
        return pd.DataFrame()

    output = table.melt(
        id_vars=["Filename"],
        value_vars=metric_columns,
        var_name="Metric",
        value_name="Value",
    ).dropna(subset=["Value"])
    output["Filename"] = output["Filename"].astype(str).str.strip()
    output["Index"] = 1.0
    output["Order"] = 1
    output["Phase"] = identify_route_phase(subset_name)
    output["Session Type"] = session_type
    output["Level"] = "Total"
    output["Route Level"] = identify_route_level(subset_name, "Total")
    output["Route Phase"] = identify_route_phase(subset_name)
    output["Subset"] = str(subset_name)
    output["Source"] = "Normal"
    output["Cumulative"] = False
    return output.merge(
        metadata_to_table(metadata),
        on="Filename",
        how="left",
        validate="many_to_one",
    )


def collect_finalized_long_plot_data(plot_tables, session_type, metadata):
    """Collect the exact tables passed to the Excel writers."""
    collected = []
    for subset_name, metric_tables in plot_tables.get("Metric files", {}).items():
        for metric, metric_table in metric_tables.items():
            long_data = final_metric_table_to_long(
                metric_table, subset_name, metric, metadata
            )
            if not long_data.empty:
                long_data["Session Type"] = session_type
                collected.append(long_data)

    for subset_name, table in plot_tables.get("Totals", {}).items():
        long_data = final_total_table_to_long(
            table, subset_name, session_type, metadata
        )
        if not long_data.empty:
            collected.append(long_data)

    if not collected:
        return pd.DataFrame()
    return pd.concat(collected, ignore_index=True)


def create_cumulative_plot_data(data, session_type):
    if data.empty:
        return data.copy()

    approved = get_sum_metrics(session_type)
    # A TOTAL row already contains one final value per animal.
    # Applying a cumulative sum to that single value produces an identical duplicate plot.
    # So summed output is only meaningful for ordered trajectories.
    cumulative = data[
        (data["Level"] != "Total")
        & data["Metric"].map(normalise_name).isin(approved)
    ].copy()
    if cumulative.empty:
        return cumulative

    cumulative = cumulative.sort_values(
        ["Filename", "Metric", "Subset", "Order"],
        kind="stable",
    )
    cumulative["Value"] = cumulative.groupby(
        ["Filename", "Metric", "Subset"],
        sort=False,
    )["Value"].cumsum()
    cumulative["Source"] = "Summed"
    cumulative["Cumulative"] = True
    return cumulative


def add_dark_shading(axis, data):
    phase_table = data[["Index", "Phase"]].dropna().copy()
    if phase_table.empty or "Dark" not in set(phase_table["Phase"]):
        return

    phase_by_index = (
        phase_table.groupby("Index")["Phase"]
        .agg(lambda values: values.mode().iloc[0] if not values.mode().empty else "All")
        .sort_index()
    )
    indices = phase_by_index.index.to_numpy(dtype=float)
    if len(indices) > 1:
        typical_step = np.nanmedian(np.diff(np.unique(indices)))
        if not np.isfinite(typical_step) or typical_step <= 0:
            typical_step = 1.0
    else:
        typical_step = 1.0

    for index_value, phase in phase_by_index.items():
        if phase == "Dark":
            axis.axvspan(
                float(index_value) - typical_step / 2,
                float(index_value) + typical_step / 2,
                color="#D9D9D9",
                alpha=0.45,
                zorder=0,
            )


def plot_group_trajectory(
    data,
    metric,
    grouping_column,
    output_path,
    inputs,
):
    required = {"Filename", "Index", "Value", grouping_column}
    if not required.issubset(data.columns):
        return False

    plot_data = data.dropna(
        subset=["Filename", "Index", "Value", grouping_column]
    ).copy()
    if plot_data.empty:
        return False

    plot_data[grouping_column] = (
        plot_data[grouping_column]
        .map(clean_metadata_label)
        .astype(str)
    )
    colors = resolve_color_map(plot_data, grouping_column, inputs)
    figure, axis = plt.subplots(figsize=(9, 6))

    if inputs.get("Plot individual lines", False):
        for (group, _), animal in plot_data.groupby(
            [grouping_column, "Filename"], sort=False
        ):
            animal = animal.sort_values("Index")
            axis.plot(
                animal["Index"],
                animal["Value"],
                color=colors.get(str(group)),
                alpha=0.18,
                linewidth=1,
            )

    summary = (
        plot_data.groupby([grouping_column, "Index"], observed=True)["Value"]
        .agg(["mean", "sem", "count"])
        .reset_index()
    )

    for group, group_data in summary.groupby(grouping_column, observed=True):
        group_data = group_data.sort_values("Index")
        color = colors.get(str(group))
        x = group_data["Index"].to_numpy(dtype=float)
        mean = group_data["mean"].to_numpy(dtype=float)
        sem = group_data["sem"].fillna(0).to_numpy(dtype=float)
        count = group_data["count"].to_numpy(dtype=float)
        axis.plot(x, mean, label=str(group), color=color, linewidth=2)
        lower = np.where(count > 1, mean - sem, mean)
        upper = np.where(count > 1, mean + sem, mean)
        axis.fill_between(x, lower, upper, color=color, alpha=0.2)

    level = str(plot_data["Level"].iloc[0])
    route_phase = str(plot_data["Route Phase"].iloc[0])
    if (
        inputs.get("Shade dark phases", True)
        and level in ["Time bin", "Block", "Cycle"]
        and route_phase == "All"
    ):
        add_dark_shading(axis, plot_data)

    axis.set_xlabel("Time (mins)" if level == "Time bin" else level)
    axis.set_ylabel(metric)
    axis.set_title(f"{metric} by {grouping_column}")
    axis.legend(title=grouping_column, frameon=False)
    sns.despine(ax=axis)
    figure.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    figure.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(figure)
    return True


def plot_distribution(data, metric, grouping_column, output_path, inputs):
    plot_data = data.dropna(subset=["Value", grouping_column]).copy()
    if plot_data.empty:
        return False

    plot_data[grouping_column] = (
        plot_data[grouping_column]
        .map(clean_metadata_label)
        .astype(str)
    )
    order = sorted(plot_data[grouping_column].unique())
    colors = resolve_color_map(plot_data, grouping_column, inputs)
    figure_width = max(6, len(order) * 1.1)
    figure, axis = plt.subplots(figsize=(figure_width, 6))

    summary = (
        plot_data.groupby(grouping_column, observed=True)["Value"]
        .agg(["mean", "sem", "count"])
        .reindex(order)
    )
    positions = np.arange(len(order), dtype=float)
    means = summary["mean"].to_numpy(dtype=float)
    errors = summary["sem"].fillna(0).to_numpy(dtype=float)
    bar_colors = [colors.get(str(group)) for group in order]

    axis.bar(
        positions,
        means,
        width=0.55,
        color=bar_colors,
        alpha=0.45,
        edgecolor="black",
        linewidth=1.2,
        yerr=errors,
        capsize=6,
        error_kw={
            "elinewidth": 1.5,
            "capthick": 1.5,
            "ecolor": "black",
        },
    )

    random = np.random.RandomState(0)
    for position, group in zip(positions, order):
        values = plot_data.loc[
            plot_data[grouping_column] == group,
            "Value",
        ].to_numpy(dtype=float)
        jitter = random.uniform(-0.11, 0.11, size=len(values))
        axis.scatter(
            position + jitter,
            values,
            s=38,
            color=colors.get(str(group)),
            edgecolor="black",
            linewidth=0.4,
            alpha=0.95,
            zorder=3,
        )

    axis.set_xticks(positions)
    axis.set_xticklabels(order)
    axis.set_xlabel(grouping_column)
    axis.set_ylabel(metric)
    axis.set_title(f"{metric} by {grouping_column}")
    axis.tick_params(axis="x", rotation=45)
    sns.despine(ax=axis)
    figure.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    figure.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(figure)
    return True


def shorten_token(value, max_length=40):
    token = safe_filename(value)
    if len(token) <= max_length:
        return token
    digest = hashlib.sha1(token.encode("utf-8")).hexdigest()[:8]
    return f"{token[:max_length - 9]}_{digest}"


def compact_subset_name(subset):
    replacements = {
        "Comp": "C",
        "Blocks": "Blk",
        "Cycles": "Cyc",
        "Days": "Day",
    }
    ignored = {"BLOCKS", "CYCLES", "DAYS", "TOTAL", "Light", "Dark"}
    parts = []
    for part in str(subset).split("_"):
        if part in ignored:
            continue
        parts.append(replacements.get(part, part))
    return "_".join(parts) if parts else "All"


def get_plot_folder(root, route_level, grouping_name):
    level_folders = {
        "Time bin": "Time_Bins",
        "Block": "Blocks",
        "Cycle": "Cycles",
        "Day": "Days",
        "Total": "Totals",
    }
    return os.path.join(
        root,
        level_folders.get(str(route_level), safe_filename(route_level)),
        shorten_token(grouping_name, 40),
    )


def build_plot_path(
    folder,
    level,
    phase,
    source,
    subset,
    metric,
    split_value=None,
):
    level_codes = {
        "Time bin": "Time",
        "Block": "Block",
        "Cycle": "Cycle",
        "Day": "Day",
        "Total": "Total",
    }
    phase_codes = {"All": "All", "Light": "Light", "Dark": "Dark"}
    source_code = "S" if source == "Summed" else "N"
    plot_code = "SUM" if level == "Total" else "TRJ"
    components = []
    if split_value is not None:
        components.append(str(split_value))
    components.extend(
        [
            plot_code,
            source_code,
            phase_codes.get(str(phase), str(phase)),
            compact_subset_name(subset),
            str(metric),
        ]
    )
    stem = safe_filename("_".join(components))

    # Leave margin below the traditional Windows MAX_PATH boundary.
    absolute_folder = os.path.abspath(folder)
    max_stem_length = max(24, 235 - len(absolute_folder) - 5)
    if len(stem) > max_stem_length:
        digest = hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8]
        stem = f"{stem[:max_stem_length - 9]}_{digest}"

    return os.path.join(folder, f"{stem}.png")


def create_plot_collection(data, session_type, inputs):
    if data.empty:
        return

    source_choice = inputs.get("Plot source", "Normal")
    allowed_sources = {
        "Normal": {"Normal"},
        "Summed": {"Summed"},
        "Both": {"Normal", "Summed"},
    }.get(source_choice, {"Normal"})
    data = data[data["Source"].isin(allowed_sources)].copy()
    if data.empty:
        return

    data, grouping_specs = build_grouping_specs(data, inputs)
    if not grouping_specs:
        return

    plot_root = inputs["Plots location"]
    group_columns = [
        "Level", "Route Level", "Route Phase", "Source", "Subset", "Metric"
    ]
    for keys, metric_data in data.groupby(group_columns, sort=False):
        level, route_level, route_phase, source, subset, metric = keys
        for (
            grouping_column,
            grouping_name,
            split_column,
            split_value,
        ) in grouping_specs:
            selected_data = metric_data
            if split_column is not None:
                cleaned_split = selected_data[split_column].map(clean_metadata_label)
                selected_data = selected_data[cleaned_split == split_value]
                if selected_data.empty:
                    continue

            folder = get_plot_folder(plot_root, route_level, grouping_name)
            output_path = build_plot_path(
                folder,
                level,
                route_phase,
                source,
                subset,
                metric,
                split_value=split_value,
            )
            if level == "Total":
                plot_distribution(
                    selected_data,
                    metric,
                    grouping_column,
                    output_path,
                    inputs,
                )
            else:
                plot_group_trajectory(
                    selected_data,
                    metric,
                    grouping_column,
                    output_path,
                    inputs,
                )


def create_requested_plots(
    classic_master,
    stopsig_master,
    leftright_master,
    closedecon_master,
    bandit_master,
    inputs,
    finalized_long_tables=None,
):
    if not inputs.get("Create plots", False):
        return
    if "Genotypes/treatments table" not in inputs:
        return

    metadata = inputs["Genotypes/treatments table"]
    session_type = inputs.get("Session Type")

    if supports_classic_enhancements(session_type):
        data = collect_classic_plot_data(classic_master, metadata)
        # Classic master metrics already contain their intended cumulative count and timing columns.
        # So the Normal/Summed selector applies only to the specialised long-session outputs.
        classic_inputs = inputs.copy()
        classic_inputs["Plot source"] = "Normal"
        create_plot_collection(data, "ClassicFED", classic_inputs)
        return

    session_masters = {
        "StopSig": stopsig_master,
        "LeftRight": leftright_master,
        "ClosedEcon_PR1": closedecon_master,
        "Bandit": bandit_master,
    }
    session_master = session_masters.get(session_type)
    if not session_master:
        return

    if finalized_long_tables is not None:
        normal = collect_finalized_long_plot_data(
            finalized_long_tables,
            session_type,
            metadata,
        )
    else:
        normal = collect_long_session_plot_data(
            session_master,
            session_type,
            metadata,
        )
    if normal.empty:
        return

    source_choice = inputs.get("Plot source", "Normal")
    if source_choice in ["Summed", "Both"]:
        summed = create_cumulative_plot_data(normal, session_type)
        if not summed.empty:
            normal = pd.concat([normal, summed], ignore_index=True)

    create_plot_collection(normal, session_type, inputs)


# Backwards-compatible entry point used by the first plotting prototype.
def create_classic_plots(master, inputs):
    return create_requested_plots(master, {}, {}, {}, {}, inputs)
