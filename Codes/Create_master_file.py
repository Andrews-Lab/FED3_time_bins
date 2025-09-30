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
    return({})

def add_to_multitime_master(closedecon_master, closedecon):
    for key in closedecon.keys():
        if key not in closedecon_master.keys():
            closedecon_master[key] = []
        closedecon_master[key] += closedecon[key]
    return(closedecon_master)

def labels(filename, info, gt_table):
    return(gt_table.at[filename, info])

def organise_table1(df_sheet, sheet, inputs):
    
    # Convert the list of dicts to a dataframe.
    df_sheet = pd.DataFrame(df_sheet).T
    df_sheet.columns = df_sheet.iloc[0]
    df_sheet = df_sheet.drop("Filename")

    # Add the genotypes and treatments to the columns and sort them by these headings.
    headers = pd.Series(df_sheet.columns, index=df_sheet.columns)
    gt_table = inputs['Genotypes/treatments table']
    for name in gt_table.columns:
        table = headers.apply(labels, info=name, gt_table=gt_table).to_frame().T
        table.index = [name]
        df_sheet = pd.concat([table, df_sheet])
    df_sheet = df_sheet.sort_values(by=list(gt_table.columns), axis=1)
    
    # Rotate the table in contrast to previous master files.
    df_sheet = df_sheet.T
    df_sheet.insert(3,"Filename",df_sheet.index)
    
    # List the columns to drop and rename.
    drop_cols = {
        "BLOCKS": ["Completed cycles", "Completed days", "Cycles"],
        "CYCLES": ["Completed days"],
        "DAYS":   ["Completed cycles", "Cycles"],
        "TOTAL":  ["Completed cycles", "Completed days", "Light/Dark", "Cycles"],
    }
    rename_cols = {
        "BLOCKS": {"Number of blocks":"Block numbers"},
        "CYCLES": {},
        "DAYS":   {},
        "TOTAL":  {},
    }
    # Rename and drop columns according to the data type.
    data_type = [type1 for type1 in drop_cols.keys() if type1 in sheet][0]
    df_sheet  = df_sheet.drop(columns=drop_cols[data_type])
    df_sheet  = df_sheet.rename(columns=rename_cols[data_type])
    
    return(df_sheet)

def organise_table2(df_sheet, sheet, inputs):
    
    # Define the row indices.
    index_cols = {
        "BLOCKS": "Block numbers",
        "CYCLES": ["Cycles", "Light/Dark"],
        "DAYS":   "Days",
        "TOTAL":  "Total",
    }
    # Reset the counting so that blocks, cycles and days go like 0,1,1,2,...
    df_sheet    = df_sheet.copy()
    data_type   = [type1 for type1 in index_cols.keys() if type1 in sheet][0]
    heading     = index_cols[data_type]
    num_heading = heading[0] if type(heading)==list else heading
    df_sheet[num_heading] = pd.factorize(df_sheet[num_heading])[0] + 1

    # Make a new excel sheet for each data column.
    col_ind      = df_sheet.columns.get_loc("Left poke count")
    list_heading = [heading] if type(heading)==str else heading
    data_cols    = df_sheet.columns[col_ind:].tolist() + list_heading
    gt_table     = inputs['Genotypes/treatments table']
    id_info      = [gt_table.index.name] + gt_table.columns.tolist()
    
    # Define row index name.
    if "Light" in sheet:
        extra_word = "Light "
    elif "Dark" in sheet:
        extra_word = "Dark "
    else:
        extra_word = ""
    if type(heading)==list:
        index_name = heading
    else:
        index_name = [extra_word + heading]
    
    # Create a new excel sheet for every data column.
    excel = {}
    for col in data_cols:
        excel[col] = df_sheet.pivot(index=heading, columns=id_info, values=col)
        excel[col].index.names = index_name

    # If no color coding is needed, skip this step.
    days_or_total = "DAYS" in sheet or "TOTAL" in sheet
    light_or_dark = "Light" in sheet or "Dark" in sheet
    if days_or_total or light_or_dark:
        return(excel)

    # Deine a color map.
    color_map = {
        "Light": "",
        "Light-Dark": "background-color: #FCE5CD",
        "Dark-Light": "background-color: #FCE5CD",
        "Dark": "background-color: #D3D3D3",
    }
    # For every sheet in the excel file, apply coloring rules.
    color_code = df_sheet.pivot(index=heading, columns=id_info, values="Light/Dark")
    styles = color_code.applymap(lambda x: color_map[x])
    for col in excel.keys():
        excel[col] = excel[col].style.apply(lambda x: styles, axis=None)

    return(excel)

def export_multitime(master, inputs, name):
    
    # Define export destination for excel file.
    if type(name)==list:
        export_name = f'{inputs["Session Type"]}_Master.xlsx'
        keep_index = False
        keep_sheets = name
    else:
        export_name = f'{inputs["Session Type"]}_Master_{name}.xlsx'
        keep_index = True
        keep_sheets = master.keys()
    export_destination = os.path.join(inputs['Export location'], export_name)
    
    # Export excel file.
    with pd.ExcelWriter(export_destination) as writer:
        for sheet in keep_sheets:
            safe_name = sheet.replace("/","÷")
            master[sheet].to_excel(writer, sheet_name=safe_name, index=keep_index)
      
def create_multitime_master_file(master1, inputs):
    
    for sheet in master1.keys():
        master1[sheet] = organise_table1(master1[sheet], sheet, inputs)
    
    # Sheets to appear in the Master_Bandit.xlsx or Master_ClosedEcon.xlsx file.
    keep_sheets = [
        "Comp_Blocks_BLOCKS",              
        "Comp_Blocks_CYCLES",              
        "Comp_Blocks_DAYS",                       
        "Comp_Blocks_Days_TOTAL",     
        "Comp_Blocks_Days_Light_TOTAL",
        "Comp_Blocks_Days_Dark_TOTAL",
        "Comp_Blocks_Cycles_Light_TOTAL",
        "Comp_Blocks_Cycles_Dark_TOTAL",
    ]
    export_multitime(master1, inputs, keep_sheets)
    
    # File to export as Master_Bandit_{file}.xlsx or Master_ClosedEcon_{file}.xlsx.
    keep_files = [              
        "Comp_Blocks_Days_DAYS",
        "Comp_Blocks_Days_BLOCKS",
        "Comp_Blocks_Days_Light_BLOCKS",
        "Comp_Blocks_Days_Dark_BLOCKS",
        "Comp_Blocks_Cycles_CYCLES",
        "Comp_Blocks_Cycles_Light_CYCLES",
        "Comp_Blocks_Cycles_Dark_CYCLES",
    ]
    for file in keep_files:
        master2 = organise_table2(master1[file], file, inputs)
        export_multitime(master2, inputs, file)

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
    plot_data_master = plot_data_master.sort_index(axis=1, level=[0,1,2,3])
    
    # Export data.
    export_name = "Bandit_plot_data.csv"
    export_destination = os.path.join(inputs['Plots location'], export_name)
    plot_data_master.to_csv(export_destination, index=False)
