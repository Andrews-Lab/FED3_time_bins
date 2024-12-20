import os
from tqdm import tqdm
from Create_GUI         import GUI
from Preprocess_data    import preprocess_data
from Create_time_bins   import analyse_FED_file
from Create_master_file import (create_blank_master, add_columns_to_master, 
    create_master_file, create_blank_stopsig_master, add_to_stopsig_master,
    create_stopsig_master_file)

# Run the GUI.
inputs = GUI()
    
# Create a master file template.
master = create_blank_master()

# Create a StopSig master file template.
stopsig_master = create_blank_stopsig_master()

# Analyse the data in each CSV file.
import_files = [file for file in os.listdir(inputs['Import location']) if 
                (file.lower().endswith(".csv") and file.startswith("~$")==False)]
for inputs['Filename'] in tqdm(import_files, ncols=70):
    
    # Preprocess the CSV file.
    df = preprocess_data(inputs)
    
    # Analyse the individual FED file.
    sheets, stopsig_results = analyse_FED_file(df, inputs)
        
    # Add the columns to the master file.
    if inputs['Find individual columns'] == True:
        master = add_columns_to_master(master, sheets["Time bins"], inputs)
        
        if inputs["Session Type"] == "StopSig":
            stopsig_master = add_to_stopsig_master(stopsig_master, stopsig_results)

# Create the master master file.
if inputs['Find individual columns'] == True:
    create_master_file(master, inputs)
    
    if inputs["Session Type"] == "StopSig":
        create_stopsig_master_file(stopsig_master, inputs)
