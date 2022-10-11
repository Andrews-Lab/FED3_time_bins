import pandas as pd
import os

def create_blank_master():
    
    sheet_names = ['Date','Time','Time bins (mins)','Session Type','FR','Left Poke Count',
                   'Right Poke Count','Pellet Count','Block Pellet Count','Retrieval Time',
                   'Interpellet Interval','Poke Time']
    master = {}
    for col in sheet_names:
        master[col] = pd.DataFrame()
    return(master)

def add_columns_to_master(master, df_bins, inputs):
    
    sheet_names = ['Date','Time','Time bins (mins)','Session Type','FR','Left Poke Count',
                   'Right Poke Count','Pellet Count','Block Pellet Count','Retrieval Time',
                   'Interpellet Interval','Poke Time']
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
        genotypes  = headers.apply(labels, info='Genotype').to_frame().T
        treatments = headers.apply(labels, info='Treatment').to_frame().T
        genotypes.index  = ['Genotype']
        treatments.index = ['Treatment']
        master[sheet] = pd.concat([treatments, master[sheet]])
        master[sheet] = pd.concat([genotypes,  master[sheet]])
        master[sheet] = master[sheet].sort_values(by=['Genotype','Treatment'], axis=1)
        
    return(master)

def add_time_columns_to_master(master, inputs):
    
    # Add in date and time columns if the start times are all the same.
    if inputs['Start time type'] == 'Use custom time':
        different_start_times = False
    else:
        different_start_times = True

    # Add time column(s) to each sheet about left poke count, right poke count, ...
    # First, find the filename with the most rows.
    longest_file = master['Time bins (mins)'].apply(pd.isna).sum().idxmin()
    time = {}
    for col in ['Time bins (mins)', 'Time', 'Date']:
        time[col] = master[col][longest_file].copy()
        time[col].name = col
        if different_start_times == True: 
            time[col].at['Genotype']  = 'Genotype'
            time[col].at['Treatment'] = 'Treatment'
        if different_start_times == False: 
            time[col].at['Genotype']  = ''
            time[col].at['Treatment'] = ''

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
        
    return(master)

def create_master_file(master, inputs):
    
    master = add_genotypes_treatments_to_master(master, inputs)
    master = add_time_columns_to_master(master, inputs)
    # Export the master file.
    with pd.ExcelWriter(os.path.join(inputs['Export location'], 'Master.xlsx')) as writer:
        for sheet in master.keys():
            master[sheet].to_excel(writer, sheet_name=sheet)
