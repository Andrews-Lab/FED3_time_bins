import pandas as pd
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

    # Remove the blank sheets.
    sheet_names = list(master.keys())
    for sheet in sheet_names:
        if len(master[sheet]) == 0:
            master.pop(sheet)
        
    return(master)

def create_master_file(master, inputs):
    
    master = add_genotypes_treatments_to_master(master, inputs)
    master = add_time_columns_to_master(master, inputs)
    # Export the master file.
    with pd.ExcelWriter(os.path.join(inputs['Export location'], 'Master.xlsx')) as writer:
        for sheet in master.keys():
            master[sheet].to_excel(writer, sheet_name=sheet)
            
def create_blank_stopsig_master():
    return([])

def add_to_stopsig_master(stopsig_master, stopsig_results):
    stopsig_master += [stopsig_results]
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
    headers    = pd.Series(stopsig_master.columns, index=stopsig_master.columns)
    genotypes  = headers.apply(labels, info='Genotype').to_frame().T
    treatments = headers.apply(labels, info='Treatment').to_frame().T
    genotypes.index  = ['Genotype']
    treatments.index = ['Treatment']
    stopsig_master = pd.concat([treatments, stopsig_master])
    stopsig_master = pd.concat([genotypes,  stopsig_master])
    stopsig_master = stopsig_master.sort_values(by=['Genotype','Treatment'], axis=1)
    
    # Export the stopsig master file.
    with pd.ExcelWriter(os.path.join(inputs['Export location'], 'StopSig_Master.xlsx')) as writer:
        stopsig_master.to_excel(writer)
