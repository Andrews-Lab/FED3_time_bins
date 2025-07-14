import pandas as pd
import os
from tkinter import Tk, filedialog, messagebox
from datetime import datetime

def read_fed_csv(file_path):
    df = pd.read_csv(file_path)
    df['Source_File'] = os.path.basename(file_path)
    return df

def concatenate_csvs(file_paths):
    dfs = []

    # Track running totals for key count columns
    pellet_offset = 0
    left_poke_offset = 0
    right_poke_offset = 0
    block_pellet_offset = 0  # optional

    for i, path in enumerate(file_paths):
        df = read_fed_csv(path)

        # Adjust count columns to continue across sessions
        if 'Pellet_Count' in df.columns:
            df['Pellet_Count'] += pellet_offset
            pellet_offset = df['Pellet_Count'].max()

        if 'Left_Poke_Count' in df.columns:
            df['Left_Poke_Count'] += left_poke_offset
            left_poke_offset = df['Left_Poke_Count'].max()

        if 'Right_Poke_Count' in df.columns:
            df['Right_Poke_Count'] += right_poke_offset
            right_poke_offset = df['Right_Poke_Count'].max()

        df['Session'] = i + 1
        dfs.append(df)

    merged = pd.concat(dfs, ignore_index=True)

    for time_col in ['MM:DD:YYYY hh:mm:ss', 'Timestamp']:
        if time_col in merged.columns:
            merged[time_col] = pd.to_datetime(merged[time_col], errors='coerce')
            merged['Elapsed_Time_s'] = (merged[time_col] - merged[time_col].min()).dt.total_seconds()
            break

    return merged

def run_concatenator_gui():
    root = Tk()
    root.withdraw()
    messagebox.showinfo("FED3 Concatenator", "Select the FED3 CSV files to concatenate")
    file_paths = filedialog.askopenfilenames(title="Select FED3 CSVs", filetypes=[("CSV Files", "*.csv")])

    if not file_paths:
        messagebox.showwarning("Cancelled", "No files were selected.")
        return
   
    # Print selected file names to terminal
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
