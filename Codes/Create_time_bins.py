import pandas as pd
import numpy as np
import os

def last_nonnan_item(list1):
    if list1 is None:
        return(np.nan)
    nonnan_list = [num for num in list1 if pd.isna(num)==False]
    if len(nonnan_list) == 0:
        return(np.nan)
    else:
        return(nonnan_list[-1])
    
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

def combine_tables(df_counts, df_bins):
    
    # Create a dataframe with the time bins and retrieval time changes together.
    df_together = df_counts.copy()
    df_together.index.names = ['Time bins (mins)']
    df_together = pd.concat([df_together,df_bins])
    df_together = df_together.sort_index()
    df_together["Time bins (mins)"] = df_together.index
    df_together = df_together.drop_duplicates(keep='first')
    df_together = df_together.drop(columns=["Time bins (mins)"])
    
    return(df_together)

def add(val,time):
    return(val+time)

def add_additional_columns_to_sheet(df_ind, inputs):
    
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

def add_additional_columns(sheets, inputs):
    # Add the same columns to each sheet.
    reordered = {}
    new_order = ["All data", "Time bins", "Pellet count changes"]
    for name in new_order:
        reordered[name] = add_additional_columns_to_sheet(sheets[name], inputs)
    return(reordered)

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

def avg(list1):
    if len(list1) == 0:
        return(0)
    else:
        return(sum(list1)/len(list1))

def organise_paired_events_results(PE, inputs):
    
    results = {}
    results["Filename"] = inputs["Filename"]
    
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
    
    # Total events variables
    regular_LRP   = PE["Regular LRP count"]
    regular_LN    = PE["Regular LN count"]
    total_regular = regular_LRP + regular_LN
    stop_LNP      = PE["Stop LNP count"]
    stop_LR       = PE["Stop LR count"]
    total_stop    = stop_LNP + stop_LR
    total_events  = total_regular + total_stop
    
    # Events within regular or stop trials.
    results["Regular LRP/total regular (%)"]   = (regular_LRP/total_regular)*100
    results["Regular LN/total regular (%)"]    = (regular_LN/total_regular)*100
    results["Total regular events"]            = total_regular
    results["Stop LNP/total stop (%)"]         = (stop_LNP/total_stop)*100
    results["Stop LR/total stop (%)"]          = (stop_LR/total_stop)*100
    results["Total stop events"]               = total_stop
    results[" "*5] = np.nan
    
    # Events within total trials.
    results["Regular LRP/total events (%)"]    = (regular_LRP/total_events)*100
    results["Regular LN/total events (%)"]     = (regular_LN/total_events)*100
    results["Regular events/total events (%)"] = (total_regular/total_events)*100
    results["Stop LNP/total events (%)"]       = (stop_LNP/total_events)*100
    results["Stop LR/total events (%)"]        = (stop_LR/total_events)*100
    results["Stop events/total events (%)"]    = (total_stop/total_events)*100
    results["Total events"]                    = total_events
    results[" "*6] = np.nan
    
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
    sheet = sheet.iloc[1:] # Remove the row saying "Filename: ..."
    
    # Color code the sheet.
    sheet = sheet.style.apply(color, PE=PE, subset=["Event"], axis=0)

    return(sheet)

def export_data(inputs, sheets):
    # Export excel file with many sheets.
    export_name = 'Time bins for '+inputs['Filename'][:-4]+'.xlsx'
    export_destination = os.path.join(inputs['Export location'], export_name)
    sheets_with_headers = ["Time bins", "Pellet count changes", "All data"]
    with pd.ExcelWriter(export_destination) as writer:
        for name in sheets.keys():
            if name in sheets_with_headers:
                sheets[name].to_excel(writer, sheet_name=name, index=False)
            else:
                sheets[name].to_excel(writer, sheet_name=name, index=False, header=False)

def analyse_FED_file(df, inputs):
    
    sheets = {}
    
    # Find the time bins.
    sheets["Time bins"] = find_time_bins(df, inputs)
    
    # Create another dataframe with every non-zero change in retrieval time.
    # If there is a change in the pellet count and not in the retrieval time, include that time point.
    sheets["Pellet count changes"] = find_retrieval_time_changes(df)
    
    # Create a dataframe with the time bins and retrieval time changes together.
    sheets["All data"] = combine_tables(sheets["Pellet count changes"], sheets["Time bins"])
    
    # Add more columns to the dataframes above.
    # These are time bins, date, time and pellet count changes.
    sheets = add_additional_columns(sheets, inputs)
    
    # Initialise the StopSig summary results.
    results = {}
    
    if inputs["Session Type"] == "StopSig": 
        # Collected paired events data and add latency information to df.
        df, PE = collect_paired_events_data(df)
        
        # Calculate sums and averages of latencies.
        results = organise_paired_events_results(PE, inputs)
        
        # Combine the overall results with the raw data and color code the sheet.
        sheets["Paired events"] = combine_results_and_raw_data(df, results, PE)
    
    # Export the data.
    export_data(inputs, sheets)
        
    return(sheets, results)
