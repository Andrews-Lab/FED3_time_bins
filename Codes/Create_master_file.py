import pandas as pd
import sys
import os

def create_blank_master():
    
    sheet_names = ['Date','Time','Time bins (mins)','Session Type','FR','Left Poke Count',
                   'Right Poke Count','Pellet Count','Block Pellet Count','Retrieval Time',
                   'Interpellet Interval','Poke Time','>Left_Regular_trial',
                   '>Left_Stop_trial','LeftinTimeOut','NoPoke_Regular_(incorrect)',
                   'NoPoke_STOP_(correct)','Pellet','Right_no_left','Right_Regular_(correct)',
                   'RightDuringDispense','RightinTimeout']
                   
    master = {}
    
    for col in sheet_names:
        master[col] = pd.DataFrame()
        
    return(master)

def add_columns_to_master(master, df_bins, inputs):
    
    sheet_names = ['Date','Time','Time bins (mins)','Session Type','FR','Left Poke Count',
                   'Right Poke Count','Pellet Count','Block Pellet Count','Retrieval Time',
                   'Interpellet Interval','Poke Time','>Left_Regular_trial',
                   '>Left_Stop_trial','LeftinTimeOut','NoPoke_Regular_(incorrect)',
                   'NoPoke_STOP_(correct)','Pellet','Right_no_left','Right_Regular_(correct)',
                   'RightDuringDispense','RightinTimeout']
                   
    sheet_cols = [col for col in sheet_names if col in df_bins.columns]
    
    for col in sheet_cols:
        master[col][inputs['Filename']] = df_bins[col]
        
    return(master)

def add_genotypes_treatments_to_master(master, inputs):
    
    def labels(filename, info):
        return(gt_table.at[filename, info])
    gt_table = inputs['Genotypes/treatments table']

    # Add the genotypes and treatments to the columns and sort them by these headings.
    for sheet in master.keys():
        headers    = pd.Series(master[sheet].columns, index=master[sheet].columns)
        for name in gt_table.columns:
            table = headers.apply(labels, info=name).to_frame().T
            table.index = [name]
            master[sheet] = pd.concat([table, master[sheet]])
        master[sheet] = master[sheet].sort_values(by=list(gt_table.columns), axis=1)
        
    return(master)

def add_time_columns_to_master(master, inputs):
    
    # Add in date and time columns if the start times are all the same.
    if inputs['Start time type'] == 'Use custom time':
        different_start_times = False
    else:
        different_start_times = True

    # Add time column(s) to each sheet about left poke count, right poke count, ...
    # First, find the filename with the most rows.
    names = inputs['Genotypes/treatments table'].columns
    longest_file = master['Time bins (mins)'].apply(pd.isna).sum().idxmin()
    time = {}
    for col in ['Time bins (mins)', 'Time', 'Date']:
        time[col] = master[col][longest_file].copy()
        time[col].name = col
        if different_start_times == True: 
            for name in names:
                time[col].at[name] = name
        if different_start_times == False: 
            for name in names:
                time[col].at[name] = ''

    for sheet in master.keys():
        # If the first active poke is used as the start time, only add time bins to
        # each sheet.
        if different_start_times == True:
            master[sheet]['Time bins (mins)'] = time['Time bins (mins)']
            master[sheet] = master[sheet].set_index('Time bins (mins)')
        # Include the date and times if the start and end times are determined by a
        # fixed date and time.
        elif different_start_times == False:
            master[sheet]['Date'] = time['Date']
            master[sheet]['Time'] = time['Time']
            master[sheet]['Time bins (mins)'] = time['Time bins (mins)']
            master[sheet] = master[sheet].set_index(['Date','Time','Time bins (mins)'])
        
    # Remove the date, time and time bins sheets.
    # The date, time and time bins are already added to each data sheet.
    for sheet in ['Time','Date','Time bins (mins)']:
        master.pop(sheet)

    # Remove the blank sheets.
    sheet_names = list(master.keys())
    for sheet in sheet_names:
        if len(master[sheet].columns) == 0:
            master.pop(sheet)
        
    return(master)

def export_master_file(master, inputs):
    
    # Export the master file.
    with pd.ExcelWriter(os.path.join(inputs['Export location'], 'Master.xlsx')) as writer:
        for sheet in master.keys():
            master[sheet].to_excel(writer, sheet_name=sheet)

def create_master_file(master, inputs):
    
    master = add_genotypes_treatments_to_master(master, inputs)
    master = add_time_columns_to_master(master, inputs)
    export_master_file(master, inputs)
            
def create_blank_singletime_master():
    return([])

def add_to_singletime_master(stopsig_master, stopsig):
    stopsig_master += [stopsig]
    return(stopsig_master)
            
def create_stopsig_master_file(stopsig_master, inputs):
    
    # Convert the list of dicts to a dataframe.
    stopsig_master = pd.DataFrame(stopsig_master).T
    stopsig_master.columns = stopsig_master.iloc[0]
    stopsig_master = stopsig_master.drop("Filename")

    # Add the genotypes and treatments to the columns and sort them by these headings.
    def labels(filename, info):
        return(gt_table.at[filename, info])
    gt_table = inputs['Genotypes/treatments table']
    headers = pd.Series(stopsig_master.columns, index=stopsig_master.columns)
    for name in gt_table.columns:
        table = headers.apply(labels, info=name).to_frame().T
        table.index = [name]
        stopsig_master = pd.concat([table, stopsig_master])
    stopsig_master = stopsig_master.sort_values(by=list(gt_table.columns), axis=1)
    
    # Export the stopsig master file.
    with pd.ExcelWriter(os.path.join(inputs['Export location'], 'StopSig_Master.xlsx')) as writer:
        stopsig_master.to_excel(writer)

def create_blank_multitime_master():
    return({"Blocks":[], "Cycles":[], "Days":[], "Total":[]})

def add_to_multitime_master(closedecon_master, closedecon):
    for key in closedecon_master.keys():
        closedecon_master[key] += closedecon[key]
    return(closedecon_master)

def create_multitime_master_file(closedecon_master, inputs):
    
    gt_table = inputs['Genotypes/treatments table']
    def labels(filename, info):
        return(gt_table.at[filename, info])
    
    # Convert the list of dicts to a dataframe.
    for sheet in closedecon_master.keys():
        closedecon_master[sheet] = pd.DataFrame(closedecon_master[sheet]).T
        closedecon_master[sheet].columns = closedecon_master[sheet].iloc[0]
        closedecon_master[sheet] = closedecon_master[sheet].drop("Filename")

        # Add the genotypes and treatments to the columns and sort them by these headings.
        headers = pd.Series(closedecon_master[sheet].columns, index=closedecon_master[sheet].columns)
        for name in gt_table.columns:
            table = headers.apply(labels, info=name).to_frame().T
            table.index = [name]
            closedecon_master[sheet] = pd.concat([table, closedecon_master[sheet]])
        closedecon_master[sheet] = closedecon_master[sheet].sort_values(by=list(gt_table.columns), axis=1)
        
        # Rotate the table in contrast to previous master files.
        closedecon_master[sheet] = closedecon_master[sheet].T
        closedecon_master[sheet].insert(3,"Filename",closedecon_master[sheet].index)

    # Rename columns.
    renamed = {"Number of blocks":"Block numbers"}
    closedecon_master["Blocks"] = closedecon_master["Blocks"].rename(columns=renamed)

    # Drop columns.
    blocks_drop = ["Completed cycles", "Completed days"]
    cycles_drop = ["Completed days"]
    days_drop   = ["Completed cycles"]
    total_drop  = ["Completed cycles", "Completed days", "Light/dark"]
    closedecon_master["Blocks"] = closedecon_master["Blocks"].drop(columns=blocks_drop)
    closedecon_master["Cycles"] = closedecon_master["Cycles"].drop(columns=cycles_drop)
    closedecon_master["Days"]   = closedecon_master["Days"  ].drop(columns=days_drop)
    closedecon_master["Total"]  = closedecon_master["Total" ].drop(columns=total_drop)
    
    # Export the closedecon master file.
    export_name = f'{inputs["Session Type"]}_Master.xlsx'
    export_destination = os.path.join(inputs['Export location'], export_name)
    with pd.ExcelWriter(export_destination) as writer:
        for sheet in closedecon_master.keys():
            closedecon_master[sheet].to_excel(writer, sheet_name=sheet, index=False)

def create_blank_plot_data_master(inputs):
    
    # Export the settings as an excel file.
    folder_name = 'Plots0'
    i = 1
    while folder_name in os.listdir(inputs['Export location']):
        folder_name = folder_name[:-1] + str(i)
        i += 1
    export_destination = os.path.join(inputs['Export location'], folder_name)
    os.makedirs(export_destination)
    inputs["Plots location"] = export_destination
    plot_data_master = []
    
    return(plot_data_master, inputs)

def create_plot_data_master_file(plot_data_master, inputs):
    
    # Prepare data.
    plot_data_master = pd.concat([pd.DataFrame(dict1) for dict1 in plot_data_master], axis=1)
    plot_data_master = plot_data_master.sort_index(axis=1, level=[0, 1, 2, 3])
    
    # Export data.
    export_name = "Bandit_plot_data.csv"
    export_destination = os.path.join(inputs['Plots location'], export_name)
    plot_data_master.to_csv(export_destination, index=False)
