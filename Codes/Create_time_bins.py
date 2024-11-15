import pandas as pd
import numpy as np
import os

def add(val,time):
    return(val+time)
    
def last_nonnan_item(list1):
    if list1 is None:
        return(np.nan)
    nonnan_list = [num for num in list1 if pd.isna(num)==False]
    if len(nonnan_list) == 0:
        return(np.nan)
    else:
        return(nonnan_list[-1])
    
def avg(list1):
    if len(list1) == 0:
        return(0)
    else:
        return(sum(list1)/len(list1))

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
                     'Retrieval Time','Interpellet Interval','Poke Time','>Left_Regular_trial',
                     '>Left_Stop_trial','LeftinTimeOut','NoPoke_Regular_(incorrect)',
                     'NoPoke_STOP_(correct)','Pellet','Right_no_left','Right_Regular_(correct)',
                     'RightDuringDispense','RightinTimeout']
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
                     'Retrieval Time','Interpellet Interval','Poke Time','>Left_Regular_trial',
                     '>Left_Stop_trial','LeftinTimeOut','NoPoke_Regular_(incorrect)',
                     'NoPoke_STOP_(correct)','Pellet','Right_no_left','Right_Regular_(correct)',
                     'RightDuringDispense','RightinTimeout']
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

def collect_paired_events_data(df):
    
    df["Latencies"] = np.nan

    # Paired events analysis
    PE = {} 
    PE["Regular LRP count"]      = 0
    PE["Regular LRP indices"]    = []
    PE["Regular LRP latency LR"] = []
    PE["Regular LRP latency RP"] = []
    PE["Regular LN count"]       = 0
    PE["Regular LN indices"]     = []
    PE["Stop LNP count"]         = 0
    PE["Stop LNP indices"]       = []
    PE["Stop LNP latency NP"]    = []
    PE["Stop LR count"]          = 0
    PE["Stop LR indices"]        = []
    PE["Stop LR latency LR"]     = []
    
    # Collect the paired events data.
    for i in range(1,len(df)):
        
        if df.at[i-1,"Event"] == ">Left_Regular_trial" and df.at[i,"Event"] == "Right_Regular_(correct)":
            for j in range(i,len(df)):
                if df.at[j,"Event"] == "Pellet":
                    latency_LR = (df.at[i,"Time"] - df.at[i-1,"Time"]).total_seconds()
                    latency_RP = (df.at[j,"Time"] - df.at[i,  "Time"]).total_seconds()
                    PE["Regular LRP count"]      += 1
                    PE["Regular LRP indices"]    += list(range(i-1,j+1))
                    PE["Regular LRP latency LR"] += [latency_LR]
                    PE["Regular LRP latency RP"] += [latency_RP]
                    df.at[i,"Latencies"] = latency_LR
                    df.at[j,"Latencies"] = latency_RP
                    break
            
        if df.at[i-1,"Event"] == ">Left_Regular_trial" and df.at[i,"Event"] == "NoPoke_Regular_(incorrect)":
            PE["Regular LN count"]   += 1
            PE["Regular LN indices"] += [i-1,i]
            
        if df.at[i-1,"Event"] == ">Left_Stop_trial" and df.at[i,"Event"] == "NoPoke_STOP_(correct)":
            for j in range(i,len(df)):
                if df.at[j,"Event"] == "Pellet":
                    latency_NP = (df.at[j,"Time"] - df.at[i,"Time"]).total_seconds()
                    PE["Stop LNP count"]      += 1
                    PE["Stop LNP indices"]    += list(range(i-1,j+1))
                    PE["Stop LNP latency NP"] += [latency_NP]
                    df.at[j,"Latencies"] = latency_NP
                    break
            
        if df.at[i-1,"Event"] == ">Left_Stop_trial" and df.at[i,"Event"] == "Right_STOP_(incorrect)":
            latency_LR = (df.at[i,"Time"] - df.at[i-1,"Time"]).total_seconds()
            PE["Stop LR count"]      += 1
            PE["Stop LR indices"]    += [i-1,i]
            PE["Stop LR latency LR"] += [latency_LR]
            df.at[i,"Latencies"]      = latency_LR
    
    return(df, PE)

# def collect_paired_events_data(df):
    
#     df["Latencies"] = df["Time"].diff().dt.total_seconds()
#     keep_latencies = []

#     # Paired events analysis
#     PE = {} 
#     PE["Regular LRP count"]      = 0
#     PE["Regular LRP indices"]    = []
#     PE["Regular LRP latency LR"] = []
#     PE["Regular LRP latency RP"] = []
#     PE["Regular LN count"]       = 0
#     PE["Regular LN indices"]     = []
#     PE["Stop LNP count"]         = 0
#     PE["Stop LNP indices"]       = []
#     PE["Stop LNP latency NP"]    = []
#     PE["Stop LR count"]          = 0
#     PE["Stop LR indices"]        = []
#     PE["Stop LR latency LR"]     = []
    
#     # Collect the paired events data.
#     for i in range(1,len(df)):
        
#         if df.at[i-1,"Event"] == ">Left_Regular_trial" and df.at[i,"Event"] == "Right_Regular_(correct)":
#             if i+1 < len(df) and df.at[i+1,"Event"] == "Pellet":
#                 keep_latencies += [i]
#                 keep_latencies += [i+1]
#                 PE["Regular LRP count"]      += 1
#                 PE["Regular LRP indices"]    += [i-1,i,i+1]
#                 PE["Regular LRP latency LR"] += [df.at[i,  "Latencies"]]
#                 PE["Regular LRP latency RP"] += [df.at[i+1,"Latencies"]]
            
#         if df.at[i-1,"Event"] == ">Left_Regular_trial" and df.at[i,"Event"] == "NoPoke_Regular_(incorrect)":
#             PE["Regular LN count"]   += 1
#             PE["Regular LN indices"] += [i-1,i]
            
#         if df.at[i-1,"Event"] == ">Left_Stop_trial" and df.at[i,"Event"] == "NoPoke_STOP_(correct)":
#             if i+1 < len(df) and df.at[i+1,"Event"] == "Pellet":
#                 keep_latencies += [i+1]
#                 PE["Stop LNP count"]      += 1
#                 PE["Stop LNP indices"]    += [i-1,i,i+1]
#                 PE["Stop LNP latency NP"] += [df.at[i+1,"Latencies"]]
            
#         if df.at[i-1,"Event"] == ">Left_Stop_trial" and df.at[i,"Event"] == "Right_STOP_(incorrect)":
#             keep_latencies += [i]
#             PE["Stop LR count"]      += 1
#             PE["Stop LR indices"]    += [i-1,i]
#             PE["Stop LR latency LR"] += [df.at[i,"Latencies"]]
            
#     # Remove uninteresting latency data.
#     vals_to_remove = [i for i in df.index if i not in keep_latencies]
#     df.loc[vals_to_remove, "Latencies"] = np.nan
    
#     return(df, PE)

def organise_paired_events_results(df, PE):
    
    results = {}
    
    # Regular LRP
    results["Regular LRP count"]                 = PE["Regular LRP count"]
    results["Regular LRP latency LR sum (secs)"] = sum(PE["Regular LRP latency LR"])
    results["Regular LRP latency LR avg (secs)"] = avg(PE["Regular LRP latency LR"])
    results["Regular LRP latency RP sum (secs)"] = sum(PE["Regular LRP latency RP"])
    results["Regular LRP latency RP avg (secs)"] = avg(PE["Regular LRP latency RP"])
    results[" "*1] = np.nan
        
    # Regular LN
    results["Regular LN count"]                  = PE["Regular LN count"]
    results[" "*2] = np.nan
    
    # Stop LNP
    results["Stop LNP count"]                    = PE["Stop LNP count"]
    results["Stop LNP latency NP sum (secs)"]    = sum(PE["Stop LNP latency NP"])
    results["Stop LNP latency NP avg (secs)"]    = avg(PE["Stop LNP latency NP"])
    results[" "*3] = np.nan
    
    # Stop LR
    results["Stop LR count"]                     = PE["Stop LR count"]
    results["Stop LR latency LR sum (secs)"]     = sum(PE["Stop LR latency LR"])
    results["Stop LR latency LR avg (secs)"]     = avg(PE["Stop LR latency LR"])
    results[" "*4] = np.nan
    
    return(results)

def color(col, PE):
    
    colors = []
    
    for idx in col.index:
        
        if idx in PE["Regular LRP indices"]:
            tcolor = '#FFFFFF' # White
            bcolor = '#00B050' # Green

        elif idx in PE["Regular LN indices"]:
            tcolor = '#FFFFFF' # White
            bcolor = '#FF3F3F' # Red
            
        elif idx in PE["Stop LNP indices"]:
            tcolor = '#4E7C3E' # Dark green
            bcolor = '#C3EFCC' # Light green
            
        elif idx in PE["Stop LR indices"]:
            tcolor = '#9C1B14' # Dark red
            bcolor = '#FBC4CD' # Light red
            
        else:
            tcolor = 'black'
            bcolor = 'none'
            
        colors += [f'background-color: {bcolor}; color: {tcolor}']
        
    return(colors)

def combine_results_and_raw_data(df, results, PE):

    # Prepare paired events analysis for concatenation.
    results = pd.DataFrame(results.items(), columns=['Time', 'Event'])
    results['Latencies'] = np.nan
    results.index   = ["num"+str(i) for i in results.index]
    
    # Concatenate the paired events overall analysis and raw data.
    sheet = pd.concat([results, df[["Time","Event","Latencies"]]])
    
    # Color code the sheet.
    sheet = sheet.style.apply(color, PE=PE, subset=["Event"], axis=0)

    return(sheet)

def analyse_FED_file(df, inputs):
    
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
    
    # Add a sheet for latency data if the session type is StopSig.
    if df.at[0,"Session Type"] == "StopSig": 
        # Collected paired events data and add latency information to df.
        df, PE = collect_paired_events_data(df)
        # Calculate sums and averages of latencies.
        results = organise_paired_events_results(df, PE)
        # Combine the overall results with the raw data and color code the sheet.
        latency_sheet = combine_results_and_raw_data(df, results, PE)
    else:
        latency_sheet = pd.DataFrame()
    
    # Export the data.
    export_name = 'Time bins for '+inputs['Filename'][:-4]+'.xlsx'
    export_destination = os.path.join(inputs['Export location'], export_name)
    with pd.ExcelWriter(export_destination) as writer:
        df_together.to_excel(writer, sheet_name='All data', index=False)
        df_bins.to_excel(writer, sheet_name='Time bins', index=False)
        df_counts.to_excel(writer, sheet_name='Pellet count changes', index=False)
        if df.at[0,"Session Type"] == "StopSig":
            latency_sheet.to_excel(writer, sheet_name='Paired events', index=False, header=False)
        
    return(df_together, df_bins, df_counts, latency_sheet)
