import pandas as pd
import numpy as np
import os
from tkinter import Tk, filedialog, messagebox
from datetime import datetime

# -----------------------------
# Bandit cleaner helpers
# -----------------------------
def _norm_hpp(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip().lower()
    if s.startswith("l"): return "left"
    if s.startswith("r"): return "right"
    return s

def _first_flip_index(g):
    vals = g["_hpp_norm"].tolist()
    idxs = g.index.to_list()
    last = None
    for j, val in enumerate(vals):
        if pd.isna(val):
            continue
        if last is None:
            last = val
            continue
        if val != last:
            return idxs[j]
    return None

def clean_bandit_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean Bandit-style concatenated CSVs in-memory:
      - Build robust block IDs using Block_Pellet_Count resets to 0
      - Detect first within-block flip of High_prob_poke
      - Drop rows from that flip onward
    Safe no-op if required columns are missing.
    """
    required = {"Block_Pellet_Count", "High_prob_poke"}
    if not required.issubset(df.columns):
        return df  # not Bandit-looking; do nothing

    out = df.copy()

    # Normalize High_prob_poke
    out["_hpp_norm"] = out["High_prob_poke"].apply(_norm_hpp)

    # Robust block IDs: reset when pellet count drops and equals 0
    bpc = pd.to_numeric(out["Block_Pellet_Count"], errors="coerce")
    reset_to_zero = ((bpc.diff() < 0) & (bpc == 0)).fillna(False)
    out["_BlockID_robust"] = reset_to_zero.cumsum().astype(int)

    # Find first flip per block; drop from flip onward
    rows_to_drop = []
    for blk, g in out.groupby("_BlockID_robust", sort=True):
        flip_at = _first_flip_index(g)
        if flip_at is not None:
            rows_to_drop.extend(range(flip_at, g.index.max() + 1))
            print(f"Block {blk}: dropped rows {flip_at}–{g.index.max()}")

    if rows_to_drop:
        print(f"Dropped {len(rows_to_drop)} rows. New shape: {out.shape[0] - len(rows_to_drop)} rows left.")
        out = out.drop(index=rows_to_drop)
    else:
        print("No conflicting blocks detected — nothing dropped.")

    return out.drop(columns=["_hpp_norm", "_BlockID_robust"], errors="ignore")

# -----------------------------
# Concatenator
# -----------------------------
def read_fed_csv(file_path):
    df = pd.read_csv(file_path)
    df["Source_File"] = os.path.basename(file_path)
    return df

def concatenate_csvs(file_paths):
    dfs = []

    # Track running totals for key count columns
    pellet_offset = 0
    left_poke_offset = 0
    right_poke_offset = 0

    for i, path in enumerate(file_paths):
        df = read_fed_csv(path)

        # Adjust count columns to continue across sessions
        if "Pellet_Count" in df.columns:
            df["Pellet_Count"] += pellet_offset
            pellet_offset = df["Pellet_Count"].max()

        if "Left_Poke_Count" in df.columns:
            df["Left_Poke_Count"] += left_poke_offset
            left_poke_offset = df["Left_Poke_Count"].max()

        if "Right_Poke_Count" in df.columns:
            df["Right_Poke_Count"] += right_poke_offset
            right_poke_offset = df["Right_Poke_Count"].max()

        df["Session"] = i + 1
        dfs.append(df)

    merged = pd.concat(dfs, ignore_index=True)

    # Run Bandit cleanup if applicable
    merged = clean_bandit_df(merged)

    # Compute elapsed time if available
    for time_col in ["MM:DD:YYYY hh:mm:ss", "Timestamp"]:
        if time_col in merged.columns:
            merged[time_col] = pd.to_datetime(merged[time_col], errors="coerce")
            merged["Elapsed_Time_s"] = (merged[time_col] - merged[time_col].min()).dt.total_seconds()
            break

    return merged

# -----------------------------
# GUI
# -----------------------------
def run_concatenator_gui():
    root = Tk()
    root.withdraw()
    messagebox.showinfo("FED3 Concatenator", "Select the FED3 CSV files to concatenate")
    file_paths = filedialog.askopenfilenames(
        title="Select FED3 CSVs",
        filetypes=[("CSV Files", "*.csv")]
    )

    if not file_paths:
        messagebox.showwarning("Cancelled", "No files were selected.")
        return

    print("\nSelected files for concatenation:")
    for file in file_paths:
        print(f" - {os.path.basename(file)}")

    df = concatenate_csvs(file_paths)

    save_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv")],
        initialfile=f"FED_concatenated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    if save_path:
        df.to_csv(save_path, index=False)
        messagebox.showinfo("Done", f"Concatenated file saved to:\n{save_path}")
    else:
        messagebox.showwarning("Cancelled", "Save location was not selected.")

if __name__ == "__main__":
    run_concatenator_gui()
