import os
from tqdm import tqdm
from Create_GUI         import GUI
from Create_time_bins   import analyse_FED_file
from Create_master_file import (create_blank_master, add_columns_to_master, 
                                create_master_file)

# Run the GUI.
inputs = GUI()
    
# Create a master file template.
master = create_blank_master()

# Analyse the data in each CSV file.
import_files = [file for file in os.listdir(inputs['Import location']) if 
                (file.lower().endswith(".csv") and file.startswith("~$")==False)]
for inputs['Filename'] in tqdm(import_files, ncols=70):
    
    # Analyse the individual FED file.
    df_together, df_bins, df_counts = analyse_FED_file(inputs)
        
    # Add the columns to the master file.
    if inputs['Find individual columns'] == True:
        master = add_columns_to_master(master, df_bins, inputs)

# Create the master master file.
if inputs['Find individual columns'] == True:
    create_master_file(master, inputs)
