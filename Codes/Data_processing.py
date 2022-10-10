import pandas as pd
import numpy as np
import sys
import os

def replace_values(val,new_val):
    return(new_val)
def remove_prefix(val):
    return(int(val[2:]))
def last_nonnan_item(list1):
    if list1 is None:
        return(np.nan)
    nonnan_list = [num for num in list1 if pd.isna(num)==False]
    if len(nonnan_list) == 0:
        return(np.nan)
    else:
        return(nonnan_list[-1])
def add(val,time):
    return(val+time)

def clean_data(df):
    # Clean the dataframe.  
    df = df.dropna(how='all')
    df.index = list(range(len(df)))
    df.columns = df.columns.str.replace(' ', '')
    df.columns = df.columns.str.replace('FR_Ratio', 'Session_Type')
    df.columns = df.columns.str.replace('Session_type', 'Session_Type')
    df.columns = df.columns.str.replace('InterPelletInterval', 'Interpellet_Interval')
    df['Retrieval_Time'] = df['Retrieval_Time'].replace('Timed_out', 60).apply(pd.to_numeric)
    df = df.drop(columns=['FED_Version', 'Device_Number', 'Battery_Voltage'],errors="ignore")
    df.columns = df.columns.str.replace('_', ' ')
    if 'Poke Time' in df.columns:
        df['Poke Time'] = df['Poke Time'].fillna(method="ffill")
    return(df)

def correct_session_type_columns(df):
    
    # Correct the session type columns.
    # Numbers that form part of the Progressive Ratio.
    # https://pubmed.ncbi.nlm.nih.gov/8794935/
    PR_nums = [0,1,2,4,6,9,12,15,20,25,32,40,50,62,77,95,118,145,178,219,
               268,328,402,492,603,737,901,1102,1347,1646,2012,2459,3004]
    
    # If there is a 'Session Type' and an 'FR' column.
    if 'Session Type' in df.columns and 'FR' in df.columns:
        
        if df['Session Type'].iloc[0][:2] == 'FR':
            df['Session Type'] = df['Session Type'].apply(replace_values, new_val='Fixed ratio')
        elif df['Session Type'].iloc[0][:2] == 'PR':
            df['Session Type'] = df['Session Type'].apply(replace_values, new_val='Progressive ratio')
        elif df['Session Type'].iloc[0] == 'Menu':
            unique_values = list(df['FR'].unique())
            if len(unique_values) == 1:
                name = 'Fixed ratio'
            elif all([val in PR_nums for val in unique_values]):
                name = 'Progressive ratio'
            else:
                name = 'Unnamed ratio'
            df['Session Type'] = df['Session Type'].apply(replace_values, new_val=name)

    # If there is only a 'Session Type' column.
    if 'Session Type' in df.columns and 'FR' not in df.columns:

        if str(df['Session Type'].iloc[0])[:2] == 'FR':
            df['FR']           = df['Session Type'].apply(remove_prefix)
            df['Session Type'] = df['Session Type'].apply(replace_values, new_val='Fixed ratio')
        elif str(df['Session Type'].iloc[0])[:2] == 'PR':
            df['FR']           = df['Session Type'].apply(remove_prefix)
            df['Session Type'] = df['Session Type'].apply(replace_values, new_val='Progressive ratio')
        elif str(df['Session Type'].iloc[0]).isdigit():
            unique_values = list(df['Session Type'].unique())
            if len(unique_values) == 1:
                name = 'Fixed ratio'
            elif all([val in PR_nums for val in unique_values]):
                name = 'Progressive ratio'
            else:
                name = 'Unnamed ratio'
            df['FR']           = df['Session Type'].copy()
            df['Session Type'] = df['Session Type'].apply(replace_values, new_val=name)
            
    return(df)

def combine_time_columns(df):
    # Combine time columns if there are 2.
    if "MM:DD:YYYYhh:mm:ss" not in df.columns:
        df["MM:DD:YYYY"] = df["MM:DD:YYYY"] + " " + df["hh:mm:ss"]
        df = df.rename(columns={"MM:DD:YYYY": "Time"})
        df = df.drop(columns=['hh:mm:ss'])
    else:
        df = df.rename(columns={"MM:DD:YYYYhh:mm:ss": "Time"})
    df["Time"] = pd.to_datetime(df["Time"])
    
    return(df)

def edit_start_and_end_times(df, inputs):
    
    # Find the start and end times if there is an ACTIVE initiation poke.                    
    if inputs['Use initiation poke'] == True:
        for i in range(len(df)):
            active_poke_col = df.at[i,"Active Poke"] + " Poke Count"
            if df.at[i,active_poke_col] >= 1:
                inputs['Start time'] = df.at[i,"Time"]
                inputs['End time']   = df.at[len(df)-1,"Time"]
                break             
    elif inputs['Use initiation poke'] == False:
        inputs['Start time'] = pd.to_datetime(inputs['Start time'])
        inputs['End time']   = pd.to_datetime(inputs['End time'])
        
    # If the end time is before the first data point or the start time is after 
    # the last data point, throw an error.
    if inputs['End time'] < df.at[0,"Time"]:
        print('\nThe end time is before the first data point in file '+inputs['Filename']+'.')
        print('Change the end time or set "use an active initiation poke" to '+
              'true in the GUI.')
        sys.exit()
    elif inputs['Start time'] > df.at[len(df)-1,"Time"]:
        print('\nThe start time is after the last data point in file '+inputs['Filename']+'.')
        print('Change the start time or set "use an active initiation poke" to '+
              'true in the GUI.')
        sys.exit()
        
    return(inputs)

def remove_data_outside_window(df, inputs):
    
    # Remove the data before the start time and after the end time.
    del_indices = []
    for i in range(len(df)):
        if df.at[i,"Time"] < inputs['Start time']:
            del_indices.append(i)
        if df.at[i,"Time"] > inputs['End time']:
            del_indices.append(i)
    df = df.drop(del_indices)
    df.index = list(range(len(df)))
    
    return(df)
    
def find_time_bins(df, inputs):
    
    # Find the time bins.
        
    # Add a time column with the minutes since the start time.
    for i in range(len(df)):
        df.at[i,"Time (mins)"] = (df.at[i,"Time"]-inputs['Start time']).total_seconds() / 60
        
    # Create a list of the time bins.
    duration_mins = (inputs['End time'] - inputs['Start time']).total_seconds() / 60
    time_bins_labels = list(np.arange(0, duration_mins + inputs['Time bin (mins)'], inputs['Time bin (mins)']))
    time_bins_mins = [-inputs['Time bin (mins)']] + time_bins_labels
    
    # Add the bins to the dataframe.
    df['Time bins (mins)'] = pd.cut(df['Time (mins)'], time_bins_mins, 
                                    labels=time_bins_labels, right=True)
    
    # Group the data into time bins. At each bin, list all the values for pellet count for example.
    possible_cols = ['Time bins (mins)','Library Version','Session Type','Motor Turns','FR',
                     'Left Poke Count','Right Poke Count','Pellet Count','Block Pellet Count',
                     'Retrieval Time','Interpellet Interval','Poke Time']
    output_cols = [col for col in possible_cols if col in df.columns]
    df_bins = df[output_cols].groupby("Time bins (mins)").agg(list)
    
    # For each bin, display the last non-nan value in each list.
    data_cols = output_cols.copy()
    data_cols.remove("Time bins (mins)")
    for col in data_cols:
        df_bins[col] = df_bins[col].apply(last_nonnan_item)
    
    # Fill in the nan values for empty lists.
    possible_nans = ['Retrieval Time', 'Interpellet Interval', 'Poke Time', 'Motor Turns']
    no_ffil_of_nans = [col for col in possible_nans if col in df_bins.columns]
    df_bins[no_ffil_of_nans] = df_bins[no_ffil_of_nans].fillna(0)
    df_bins = df_bins.fillna(method="ffill")
    df_bins["Session Type"] = df_bins["Session Type"].fillna(method="bfill")
    df_bins = df_bins.fillna(0)
    
    return(df_bins)

def find_retrieval_time_changes(df):

    # Create another dataframe with every non-zero change in retrieval time.
    # If there is a change in the pellet count and not in the retrieval time, include that time point.
    possible_cols = ['Time bins (mins)','Library Version','Session Type','Motor Turns','FR',
                     'Left Poke Count','Right Poke Count','Pellet Count','Block Pellet Count',
                     'Retrieval Time','Interpellet Interval','Poke Time']
    output_cols = [col for col in possible_cols if col in df.columns]
    count_cols = output_cols.copy()
    count_cols.remove("Time bins (mins)")
    count_cols = ['Time (mins)'] + count_cols
    df_counts = df[count_cols].fillna(0)
    
    keep_indices = []
    for i in range(len(df_counts)):
        if i == 0 or df_counts.at[i,"Retrieval Time"] != df_counts.at[i-1,"Retrieval Time"]:
            if df_counts.at[i,"Retrieval Time"] != 0:
                keep_indices.append(i)
                continue
        elif i == 0 or df_counts.at[i,"Pellet Count"] != df_counts.at[i-1,"Pellet Count"]:
            keep_indices.append(i)
    df_counts = df_counts.loc[keep_indices]
    df_counts.index = df_counts["Time (mins)"]
    df_counts = df_counts.drop(columns=["Time (mins)"])
    
    return(df_counts)

def combine_TB_plus_RTC(df_counts, df_bins):

    # Create a dataframe with the time bins and retrieval time changes together.
    df_together = df_counts.copy()
    df_together.index.names = ['Time bins (mins)']
    df_together = pd.concat([df_together,df_bins])
    df_together = df_together.sort_index()
    df_together["Time bins (mins)"] = df_together.index
    df_together = df_together.drop_duplicates(keep='first')
    df_together = df_together.drop(columns=["Time bins (mins)"])
    
    return(df_together)

def add_additional_columns(df_ind, inputs):
    
    # Add in the columns for the time bins in minutes.  
    df_ind.insert(0, 'Time bins (mins)', df_ind.index)
    
    # Add in the corresponding columns for the dates and times.
    # If the number of rows in the dataframe is 0, return empty date and time
    # columns.
    float_index = df_ind.index
    if len(float_index) == 0:
        date_time_col = pd.DataFrame(columns=['Date','Time'])
    else:
        date_time_col = pd.Series(list(float_index))
        date_time_col = date_time_col.apply(pd.to_timedelta, unit='m')
        date_time_col = date_time_col.apply(add, time=inputs['Start time'])
        date_time_col = date_time_col.apply(pd.to_datetime).dt.round('1s')
        date = pd.Series(date_time_col.dt.date, name='Date')
        time = pd.Series(date_time_col.dt.time, name='Time')
        date_time_col = pd.concat([date,time], axis=1)
        date_time_col.index = list(float_index)
    df_ind = pd.concat([date_time_col, df_ind], axis=1)
    
    # Add the pellet count changes column.
    ind = df_ind.columns.get_loc('Pellet Count') + 1
    pellet_count = df_ind['Pellet Count']
    count_change = pellet_count.copy()
    for i in range(1,len(pellet_count)):
        count_change.iat[i] = pellet_count.iat[i] - pellet_count.iat[i-1]
    df_ind.insert(ind, 'Pellet Count Change', count_change)
    
    return(df_ind)

def analyse_FED_file(inputs):
    
    # Import the raw data.
    import_destination = os.path.join(inputs['Import location'], inputs['Filename'])
    df = pd.read_csv(import_destination)
    
    # Clean the data.
    df = clean_data(df)
    
    # Correct session type columns.
    df = correct_session_type_columns(df)
    
    # Combine time columns if there are 2.
    df = combine_time_columns(df)
    
    # Edit the start and end times.
    inputs = edit_start_and_end_times(df, inputs)
    
    # Remove the data before the start time and after the end time.
    df = remove_data_outside_window(df, inputs)
    
    # Find the time bins.
    df_bins = find_time_bins(df, inputs)
    
    # Create another dataframe with every non-zero change in retrieval time.
    # If there is a change in the pellet count and not in the retrieval time, include that time point.
    df_counts = find_retrieval_time_changes(df)
    
    # Create a dataframe with the time bins and retrieval time changes together.
    df_together = combine_TB_plus_RTC(df_counts, df_bins)
    
    # Add more columns to each dataframe.
    # These are time bins, date, time and pellet count changes.
    df_together = add_additional_columns(df_together, inputs)
    df_bins     = add_additional_columns(df_bins, inputs)
    df_counts   = add_additional_columns(df_counts, inputs)
    
    # Export the data.
    export_name = 'Time bins for '+inputs['Filename'][:-4]+'.xlsx'
    export_destination = os.path.join(inputs['Export location'], export_name)
    with pd.ExcelWriter(export_destination) as writer:
        df_together.to_excel(writer, sheet_name='All data', index=False)
        df_bins.to_excel(writer, sheet_name='Time bins', index=False)
        df_counts.to_excel(writer, sheet_name='Pellet count changes', index=False)
        
    return(df_together, df_bins, df_counts)
