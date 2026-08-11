from tqdm import tqdm
from Create_GUI         import GUI
from Preprocess_data    import find_import_files, preprocess_data
from Create_time_bins   import analyse_FED_file
from Create_plots       import create_requested_plots
from Create_master_file import (create_blank_master, add_columns_to_master, 
    create_master_file, add_to_singletime_master, create_blank_multitime_master, 
    add_to_multitime_master, create_multitime_master_file, create_blank_plot_data_master,
    create_plot_data_master_file)

# Run the GUI.
inputs = GUI()
    
# Create master file templates.
master            = create_blank_master()
stopsig_master    = create_blank_multitime_master()
leftright_master  = create_blank_multitime_master()
closedecon_master = create_blank_multitime_master()
bandit_master     = create_blank_multitime_master()
plot_data_master, inputs = create_blank_plot_data_master(inputs)

# Analyse the data in each CSV file.
import_files = find_import_files(inputs)

for inputs["Filename"] in tqdm(import_files, ncols=70):
    
    # Preprocess the CSV file.
    df, inputs = preprocess_data(inputs)
    
    # Analyse the individual FED file.
    sheets, stopsig, leftright, closedecon, bandit, plot_data = analyse_FED_file(df, inputs)
        
    # Add the columns to the master file.
    if inputs['Find individual columns']:
        master = add_columns_to_master(master, sheets["Master time bins"], inputs)
        
        if inputs["Session Type"] == "StopSig":
            stopsig_master = add_to_multitime_master(stopsig_master, stopsig)
        
        elif inputs["Session Type"] == "LeftRight":
            leftright_master = add_to_multitime_master(leftright_master, leftright)
        
        elif inputs["Session Type"] == "ClosedEcon_PR1":
            closedecon_master = add_to_multitime_master(closedecon_master, closedecon)

        elif inputs["Session Type"] == "Bandit":
            bandit_master    = add_to_multitime_master(bandit_master, bandit)
            plot_data_master = add_to_singletime_master(plot_data_master, plot_data)

# ClassicFED plots use the classic master directly.  Long-session plots are
# created later from the exact finalized tables used for Excel export.
if (
    inputs['Find individual columns']
    and inputs.get("Create plots", False)
    and inputs["Session Type"] not in [
        "StopSig", "LeftRight", "ClosedEcon_PR1", "Bandit"
    ]
):
    create_requested_plots(
        master,
        stopsig_master,
        leftright_master,
        closedecon_master,
        bandit_master,
        inputs,
    )

# Create the master master file.
if inputs['Find individual columns']:
    create_master_file(master, inputs)
    
    if inputs["Session Type"] == "StopSig":
        plot_tables = create_multitime_master_file(stopsig_master, inputs)

    elif inputs["Session Type"] == "LeftRight":
        plot_tables = create_multitime_master_file(leftright_master, inputs)
    
    elif inputs["Session Type"] == "ClosedEcon_PR1":
        plot_tables = create_multitime_master_file(closedecon_master, inputs)

    elif inputs["Session Type"] == "Bandit":
        plot_tables = create_multitime_master_file(bandit_master, inputs)
        create_plot_data_master_file(plot_data_master, inputs)

    if (
        inputs.get("Create plots", False)
        and inputs["Session Type"] in [
            "StopSig", "LeftRight", "ClosedEcon_PR1", "Bandit"
        ]
    ):
        create_requested_plots(
            master,
            stopsig_master,
            leftright_master,
            closedecon_master,
            bandit_master,
            inputs,
            finalized_long_tables=plot_tables,
        )
