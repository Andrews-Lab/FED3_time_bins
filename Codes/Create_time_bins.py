import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('agg')
import pandas as pd
import numpy as np
import sys
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
        return(np.nan)
    else:
        return(sum(list1)/len(list1))

def per(val1, val2):
    if val2 == 0:
        return(np.nan)
    else:
        return((val1/val2)*100)

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
    results["Regular LRP/total regular (%)"]   = per(regular_LRP, total_regular)
    results["Regular LN/total regular (%)"]    = per(regular_LN, total_regular)
    results["Total regular events"]            = total_regular
    results["Stop LNP/total stop (%)"]         = per(stop_LNP, total_stop)
    results["Stop LR/total stop (%)"]          = per(stop_LR, total_stop)
    results["Total stop events"]               = total_stop
    results[" "*5] = np.nan
    
    # Events within total trials.
    results["Regular LRP/total events (%)"]    = per(regular_LRP, total_events)
    results["Regular LN/total events (%)"]     = per(regular_LN, total_events)
    results["Regular events/total events (%)"] = per(total_regular, total_events)
    results["Stop LNP/total events (%)"]       = per(stop_LNP, total_events)
    results["Stop LR/total events (%)"]        = per(stop_LR, total_events)
    results["Stop events/total events (%)"]    = per(total_stop, total_events)
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

def identify_cycle(val, start, end):
    
    # Check for the light and dark cycles with only times and no dates.
    time = val.time()
    if start < end:
        if time >= start and time < end:
            return("Light")
        else:
            return("Dark")
    else:
        if time >= start or time < end:
            return("Light")
        else:
            return("Dark")

def return_y_or_n(val, list1):
    
    # Check whether a value is not in a list.
    if val not in list1:
        return("Y")
    else:
        return("N")

def counts_to_events(counts):
    
    # Convert cumulative data to event data, for example:
    # (1,1,2,2,3,3,...) to (1,0,1,0,1,0,...) and
    # (0,0,1,1,2,2,...) to (0,0,1,0,1,0,...).
    events = counts.diff()
    events.iloc[0] = counts.iloc[0] # diff makes nan the first value by default.
    
    return(events)

def add_time_info(df, inputs):
    
    # Find the block numbers using the moments that the block pellet count goes
    # down such as 0,1,2,3,0,...
    df["Blocks"] = (df["Block Pellet Count"].diff() < 0).cumsum() + 1

    # Find the cycle names.
    start = pd.to_datetime(inputs["Light cycle start"]).time()
    end   = pd.to_datetime(inputs["Light cycle end"]).time()
    df["Light/Dark"] = df["Time"].apply(identify_cycle, start=start, end=end)
    df["Cycles"] = (df["Light/Dark"] != df["Light/Dark"].shift()).cumsum()
    if df.at[0,"Light/Dark"] == "Dark":
        df["Cycles"] = df["Cycles"] - 1
    
    # Find the day numbers.
    # Subtract the time of the light cycle start from the Time column, so that
    # the light cycle starts at midnight. 
    light_cycle_start = pd.to_timedelta(inputs["Light cycle start"])
    df["Days"] = (df["Time"] - light_cycle_start)
    df["Days"] =  df["Days"].apply(lambda x: x.date())
    df["Days"] = (df["Days"] != df["Days"].shift()).cumsum()
    if df.at[0,"Light/Dark"] == "Dark":
        df["Days"] = df["Days"] - 1
    
    # Find the animal number, which is just 1 to indicate analysis of whole file.
    df["Total"] = 1

    # Indicate whether the blocks, cycles and days are complete or not.
    # By defintion, the last block and the first and last cycles and days are 
    # incomplete.
    last_block             = [df["Blocks"].iloc[-1]]
    first_and_last_cycles  = [df["Cycles"].iloc[0], df["Cycles"].iloc[-1]]
    first_and_last_days    = [df["Days"  ].iloc[0], df["Days"  ].iloc[-1]]
    df["Completed blocks"] =  df["Blocks"].apply(return_y_or_n, list1=last_block)
    df["Completed cycles"] =  df["Cycles"].apply(return_y_or_n, list1=first_and_last_cycles)
    df["Completed days"]   =  df["Days"  ].apply(return_y_or_n, list1=first_and_last_days)
    
    # Add left poke, right poke and pellet event data, as this is currently
    # cumulative.
    df["Left Poke Events"]  = counts_to_events(df["Left Poke Count"])
    df["Right Poke Events"] = counts_to_events(df["Right Poke Count"])
    df["Pellet Events"]     = counts_to_events(df["Pellet Count"])
    
    return(df)

def add_bandit_info(df):
    
    # Check that there is only 1 high prob poke within a block.
    one_high_prob_poke_per_block = df.groupby("Blocks")["High prob poke"].nunique().eq(1).all()
    if one_high_prob_poke_per_block == False:
        print("There is more than 1 high prob poke within a block")
        sys.exit()
    
    # Add statistics for the plotting.
    df["Low prob poke"] = df["High prob poke"].map({"Left":"Right","Right":"Left"})
    df["Is left"]       = df["Event"] == "Left"
    df["Is right"]      = df["Event"] == "Right"
    df["Cumul left"]    = df["Is left"].groupby(df["Blocks"]).cumsum()
    df["Cumul right"]   = df["Is right"].groupby(df["Blocks"]).cumsum()
    df["Cumul prop"]    = df["Cumul left"] / (df["Cumul left"] + df["Cumul right"])
    df["Ideal prop"]    = df["High prob poke"].map({"Left":1,"Right":0})
    
    return(df)

def plot_pokes_and_blocks(df, inputs):
    
    # Write the title.
    full_name = [inputs['Filename'][:-4]]
    if inputs['Find individual columns']:        
        gt_table = inputs['Genotypes/treatments table']
        genotype, treatment, mouse_ID = gt_table.loc[inputs["Filename"]]
        full_name += [genotype, treatment, mouse_ID]

    # Plot the data.
    title = " ".join(full_name)
    num_blocks = df["Blocks"].max()
    plt.figure(figsize=(num_blocks*(12/29), 4))
    plt.plot(range(len(df)), df["Ideal prop"], color="grey", label="Ideal proportion")
    plt.plot(range(len(df)), df["Cumul prop"], color="blue", label="Proportion")
    plt.title(title)
    plt.xlabel("Number of left, right or pellet trials")
    plt.ylabel("Left / (left + right) within each block")
    plt.legend(loc='lower right', bbox_to_anchor=(1, 1), ncol=2)

    # Export the plot.
    safe_characters = [char if char.isalnum() else "_" for char in title]
    export_name = f'{"".join(safe_characters)}.png'
    export_destination = os.path.join(inputs['Plots location'], export_name)
    plt.savefig(export_destination, bbox_inches="tight")
    plt.close()

    # Record the plotting data.
    plot_data = {
        (*full_name, "Proportion"):       df["Cumul prop"].tolist(),
        (*full_name, "Ideal proportion"): df["Ideal prop"].tolist()
    }
    return(plot_data)
        
def get_block_stats(series, name):
    
    # This is for block stats.
    first_value = series.iloc[0]
    if name == "Blocks":
        return(first_value)
    else:
        return(len(series.unique()))

def generate_results_closedecon(df_short, results, name):
    
    # Initialise the variables.
    blocks            = get_block_stats(df_short["Blocks"], name)
    lightdark         = "-".join(df_short["Light/Dark"      ].astype(str).unique())
    cycles            = "-".join(df_short["Cycles"          ].astype(str).unique())
    days              = "-".join(df_short["Days"            ].astype(str).unique())
    completed_cycles  = "-".join(df_short["Completed cycles"].astype(str).unique())
    completed_days    = "-".join(df_short["Completed days"  ].astype(str).unique())
    start_time        = df_short["Time"].iloc[0]
    end_time          = df_short["Time"].iloc[-1]
    length_mins       = (end_time - start_time).total_seconds()*(1/60)
    num_left_pokes    = df_short["Left Poke Events"].sum()
    num_right_pokes   = df_short["Right Poke Events"].sum()
    pellet_count      = df_short["Pellet Events"].sum()
    total_pokes       = num_left_pokes + num_right_pokes
    retrieval_times   = df_short["Retrieval Time"]
    IPIs              = df_short["Interpellet Interval"]
    poke_times        = df_short["Poke Time"]
    sum_retrievals    = retrieval_times.sum()
    sum_IPIs          = IPIs.sum()
    sum_poke_times    = poke_times.sum()
    avg_retrievals    = retrieval_times.mean()
    avg_IPIs          = IPIs.mean()
    avg_poke_times    = poke_times.mean()
    
    # Add these variables to the results dictionary.
    results["Number of blocks"]               = blocks
    results["Light/Dark"]                     = lightdark
    results["Cycles"]                         = cycles
    results["Days"]                           = days
    results["Completed cycles"]               = completed_cycles
    results["Completed days"]                 = completed_days
    results["Start time"]                     = start_time
    results["End time"]                       = end_time
    results["Length (mins)"]                  = length_mins
    results["Left poke count"]                = num_left_pokes
    results["Right poke count"]               = num_right_pokes
    results["Total pokes"]                    = total_pokes
    results["Pellet count"]                   = pellet_count
    results["Sum of retrieval times (secs)"]  = sum_retrievals
    results["Sum of IPIs (secs)"]             = sum_IPIs
    results["Sum of poke times (secs)"]       = sum_poke_times
    results["Average retrieval times (secs)"] = avg_retrievals
    results["Average IPIs (secs)"]            = avg_IPIs
    results["Average poke times (secs)"]      = avg_poke_times
    
    return(results)

def generate_results_bandit1(df_short, results):
    
    # Collect statistics.
    # Notice that "LeftinTimeOut" and "RightinTimeout" have slightly different capitals.
    pellets_to_switch = "-".join(df_short["PelletsToSwitch"].astype(str).unique())
    num_reversals     = df_short["Blocks"].unique().size - 1
    pokes_dispense    = df_short["Event"].isin(["LeftDuringDispense", "RightDuringDispense"]).sum()
    pokes_timeout     = df_short["Event"].isin(["LeftinTimeOut", "RightinTimeout"]).sum()
    pokes_pellet      = df_short["Event"].isin(["LeftWithPellet", "RightWithPellet"]).sum()
    
    # Add these variables to the results dictionary.
    results["Pellets to switch"]     = pellets_to_switch
    results["Num reversals"]         = num_reversals
    results["Pokes during dispense"] = pokes_dispense
    results["Poke in timeout"]       = pokes_timeout
    results["Pokes with pellet"]     = pokes_pellet
    
    return(results)

def generate_results_bandit2(df_short, results):
    
    # Record times when there are jumps between events.
    df_main = df_short.copy()
    df_main["Event no jump"]    = df_main.index.to_series().diff() == 1
    df_main["Event no jump x1"] = df_main["Event no jump"].shift(-1)
    df_main["Event no jump x2"] = df_main["Event no jump"].shift(-2)
    
    # Only keep the rows for events "Left", "Right" and "Pellet".
    df_main = df_main[df_main["Event"].isin(["Left", "Right", "Pellet"])].copy()
    
    # Record events that happen in later rows.
    df_main["Event after x1"] = df_main["Event"].shift(-1)
    df_main["Event after x2"] = df_main["Event"].shift(-2)
    
    # Define helpful variables with df_main.
    poke             = df_main["Event"].isin(["Left","Right"])
    poke_afterx1     = df_main["Event after x1"].isin(["Left","Right"])
    poke_afterx2     = df_main["Event after x2"].isin(["Left","Right"])
    high_prob_poke   = df_main["Event"] == df_main["High prob poke"]
    low_prob_poke    = df_main["Event"] == df_main["Low prob poke"]
    pell_afterx1     = df_main["Event after x1"] == "Pellet"
    same_event_x0_x1 = df_main["Event"] == df_main["Event after x1"]
    same_event_x0_x2 = df_main["Event"] == df_main["Event after x2"]
    no_jump_x0_x1    = df_main["Event no jump x1"]
    no_jump_x1_x2    = df_main["Event no jump x2"]
    no_jump_x0tx2    = no_jump_x0_x1 & no_jump_x1_x2
    
    # Find the indices where specific events occur.
    win                  = (poke           & pell_afterx1 & no_jump_x0_x1).sum()
    high_prob_win        = (high_prob_poke & pell_afterx1 & no_jump_x0_x1).sum()
    low_prob_win         = (low_prob_poke  & pell_afterx1 & no_jump_x0_x1).sum()
    high_prob_win_stay   = (high_prob_poke & pell_afterx1 & poke_afterx2 &  same_event_x0_x2 & no_jump_x0tx2).sum()
    high_prob_win_shift  = (high_prob_poke & pell_afterx1 & poke_afterx2 & ~same_event_x0_x2 & no_jump_x0tx2).sum()
    low_prob_win_stay    = (low_prob_poke  & pell_afterx1 & poke_afterx2 &  same_event_x0_x2 & no_jump_x0tx2).sum()
    low_prob_win_shift   = (low_prob_poke  & pell_afterx1 & poke_afterx2 & ~same_event_x0_x2 & no_jump_x0tx2).sum()
    loss                 = (poke           & poke_afterx1 & no_jump_x0_x1).sum()
    high_prob_loss       = (high_prob_poke & poke_afterx1 & no_jump_x0_x1).sum()
    low_prob_loss        = (low_prob_poke  & poke_afterx1 & no_jump_x0_x1).sum()
    high_prob_lose_stay  = (high_prob_poke & poke_afterx1 &  same_event_x0_x1 & no_jump_x0_x1).sum()
    high_prob_lose_shift = (high_prob_poke & poke_afterx1 & ~same_event_x0_x1 & no_jump_x0_x1).sum()
    low_prob_lose_stay   = (low_prob_poke  & poke_afterx1 &  same_event_x0_x1 & no_jump_x0_x1).sum()
    low_prob_lose_shift  = (low_prob_poke  & poke_afterx1 & ~same_event_x0_x1 & no_jump_x0_x1).sum()
    
    # Add these results to the dataframe.
    results["Win"]                  = win
    results["High prob win"]        = high_prob_win
    results["Low prob win"]         = low_prob_win
    results["High prob win-stay"]   = high_prob_win_stay
    results["High prob win-shift"]  = high_prob_win_shift
    results["Low prob win-stay"]    = low_prob_win_stay
    results["Low prob win-shift"]   = low_prob_win_shift
    results["Loss"]                 = loss
    results["High prob loss"]       = high_prob_loss
    results["Low prob loss"]        = low_prob_loss
    results["High prob lose-stay"]  = high_prob_lose_stay
    results["High prob lose-shift"] = high_prob_lose_shift
    results["Low prob lose-stay"]   = low_prob_lose_stay
    results["Low prob lose-shift"]  = low_prob_lose_shift
    
    # Calculate percentages.
    percentage1 = per(win,  win + loss)
    percentage2 = per(loss, win + loss)
    percentage3 = per(high_prob_win,  high_prob_win + high_prob_loss)
    percentage4 = per(high_prob_loss, high_prob_win + high_prob_loss)
    percentage5 = per(low_prob_win,   low_prob_win  + low_prob_loss)
    percentage6 = per(low_prob_loss,  low_prob_win  + low_prob_loss)

    # Add these percentages to the results.
    results["Win/(win+loss) (%)"]             = percentage1
    results["Loss/(win+loss) (%)"]            = percentage2
    results["HP win/(HP win + HP loss) (%)"]  = percentage3
    results["HP loss/(HP win + HP loss) (%)"] = percentage4
    results["LP win/(LP win + LP loss) (%)"]  = percentage5
    results["LP loss/(LP win + LP loss) (%)"] = percentage6
    
    return(results)

def generate_results_bandit(df_short, results, name):
    
    results = generate_results_closedecon(df_short, results, name)
    results = generate_results_bandit1(df_short, results)
    results = generate_results_bandit2(df_short, results)
    
    return(results)

def analyse_data(df, inputs, name, generate_results):

    collated = []
    
    for num in df[name].unique():
        
        df_short = df[df[name] == num].copy()
        results = {}
        results["Filename"] = inputs["Filename"]
        results = generate_results(df_short, results, name)
        collated += [results]
    
    return(collated)

def collect_data_subsets(df, inputs, generate_results):
    
    dict1 = {}
    
    # Define ways to subset the data.
    complete_blocks = df["Completed blocks"] == "Y"
    complete_cycles = df["Completed cycles"] == "Y"
    complete_days   = df["Completed days"]   == "Y"
    light_cycles    = df["Light/Dark"]       == "Light"
    dark_cycles     = df["Light/Dark"]       == "Dark"
    
    # Create data subsets.
    df_compblocks            = df[complete_blocks]
    df_compblocksdays        = df[complete_blocks & complete_days]
    df_compblocksdayslight   = df[complete_blocks & complete_days   & light_cycles]
    df_compblocksdaysdark    = df[complete_blocks & complete_days   & dark_cycles]
    df_compblockscycles      = df[complete_blocks & complete_cycles]
    df_compblockscycleslight = df[complete_blocks & complete_cycles & light_cycles]
    df_compblockscyclesdark  = df[complete_blocks & complete_cycles & dark_cycles]
    
    # Create info for analysing data subsets.
    info = [
        ("Comp_Blocks_BLOCKS",              df_compblocks,            "Blocks"),
        ("Comp_Blocks_CYCLES",              df_compblocks,            "Cycles"),
        ("Comp_Blocks_DAYS",                df_compblocks,            "Days"),
        ("Comp_Blocks_Days_BLOCKS",         df_compblocksdays,        "Blocks"),
        ("Comp_Blocks_Days_CYCLES",         df_compblocksdays,        "Cycles"),
        ("Comp_Blocks_Days_DAYS",           df_compblocksdays,        "Days"),
        ("Comp_Blocks_Days_TOTAL",          df_compblocksdays,        "Total"),
        ("Comp_Blocks_Days_Light_BLOCKS",   df_compblocksdayslight,   "Blocks"),
        ("Comp_Blocks_Days_Dark_BLOCKS",    df_compblocksdaysdark,    "Blocks"),
        ("Comp_Blocks_Cycles_CYCLES",       df_compblockscycles,      "Cycles"),
        ("Comp_Blocks_Cycles_Light_CYCLES", df_compblockscycleslight, "Cycles"),
        ("Comp_Blocks_Cycles_Dark_CYCLES",  df_compblockscyclesdark,  "Cycles"),
        ("Comp_Blocks_Days_Light_TOTAL",    df_compblocksdayslight,   "Total"),
        ("Comp_Blocks_Days_Dark_TOTAL",     df_compblocksdaysdark,    "Total"),
        ("Comp_Blocks_Cycles_Light_TOTAL",  df_compblockscycleslight, "Total"),
        ("Comp_Blocks_Cycles_Dark_TOTAL",   df_compblockscyclesdark,  "Total"),
    ]
    dict1 = {val[0]: analyse_data(val[1], inputs, val[2], generate_results) for val in info}
    
    return(dict1)

def analyse_FED_file(df, inputs):
    
    sheets     = {}
    stopsig    = {}
    closedecon = {}
    bandit     = {}
    plot_data  = {}
    
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

    if inputs["Session Type"] == "StopSig": 
        # Collected paired events data and add latency information to df.
        df, PE = collect_paired_events_data(df)
        
        # Calculate sums and averages of latencies.
        stopsig = organise_paired_events_results(PE, inputs)
        
        # Combine the overall results with the raw data and color code the sheet.
        sheets["Paired events"] = combine_results_and_raw_data(df, stopsig, PE)

    if inputs["Session Type"] == "ClosedEcon_PR1":
        # Add block, light/dark cycle and day information as columns.
        df = add_time_info(df, inputs)
        
        # Collect statistics grouped by blocks, cycles and days.
        closedecon = collect_data_subsets(df, inputs, generate_results_closedecon)
    
    if inputs["Session Type"] == "Bandit":
        # Add block, light/dark cycle and day information as columns.
        df = add_time_info(df, inputs)
        df = add_bandit_info(df)
        plot_data = plot_pokes_and_blocks(df, inputs)
        
        # Collect statistics grouped by blocks, cycles and days.
        bandit = collect_data_subsets(df, inputs, generate_results_bandit)
    
    # Export the data.
    export_data(inputs, sheets)
        
    return(sheets, stopsig, closedecon, bandit, plot_data)
