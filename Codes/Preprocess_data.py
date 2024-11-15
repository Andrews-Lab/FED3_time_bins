import pandas as pd
import sys
import os

def replace_values(val,new_val):
    return(new_val)

def remove_prefix(val):
    return(int(val[2:]))

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
    
    # Find the start and end times, if use initiation poke or use first/last 
    # timestamps is selected.          
    for time in ['Start time', 'End time']:
        
        if inputs[time+' type'] == 'Use custom time':
            # Find a way to identify when there is only a time listed and no date.
            # This is tricky and I may update this in the future.
            # If a date isn't included, use the most common date from the FED file.
            date_time_components = str(inputs[time]).split(' ')
            date_time_components = [val for val in date_time_components if val!='']
            if len(date_time_components) == 1:
                def find_date(time):
                    return(time.date())
                most_common_date = df["Time"].apply(find_date).mode()[0]
                inputs[time] = str(most_common_date)+' '+inputs[time]
            
            # Convert the string to a datetime object.
            inputs[time] = pd.to_datetime(inputs[time])
        
        if time == 'Start time':
            if inputs[time+' type'] == 'Use first timestamp':
                inputs[time] = df.at[0,"Time"]
        
            if inputs[time+' type'] == 'Use initiation poke':
                for i in range(len(df)):
                    active_poke_col = df.at[i,"Active Poke"] + " Poke Count"
                    if df.at[i,active_poke_col] >= 1:
                        inputs[time] = df.at[i,"Time"]
                        break
                    
        if time == 'End time':
            if inputs[time+' type'] == 'Use last timestamp':
                inputs[time] = df.at[len(df)-1,"Time"]
        
    # If the end time is before the first data point or the start time is after 
    # the last data point, throw an error.
    if inputs['End time'] < df.at[0,"Time"]:
        print('\nThe end time is before the first data point in file '+inputs['Filename']+'.')
        print('Change the custom end time or select "Use last end time".')
        sys.exit()
    elif inputs['Start time'] > df.at[len(df)-1,"Time"]:
        print('\nThe start time is after the last data point in file '+inputs['Filename']+'.')
        print('Change the custom start time, select "Use first timestamp" or '+
              'select "Use initiation poke".')
        sys.exit()
        
    return(inputs)

def add_additional_columns_stopsig(df):
    
    # There are some events that would be useful to summarise as separate 
    # cumulative columns for the stopsig task.
    if df.at[0,"Session Type"] == "StopSig":
        
        list_events = [">Left_Regular_trial",">Left_Stop_trial","LeftinTimeOut",
                       "NoPoke_Regular_(incorrect)","NoPoke_STOP_(correct)","Pellet",
                       "Right_no_left","Right_Regular_(correct)","RightDuringDispense",
                       "RightinTimeout"]

        for event in list_events:
            df[event] = (df['Event'] == event).cumsum()
            
    return(df)

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

def preprocess_data(inputs):
    
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
    
    # Add additional columns based on the events column for the stopsig task.
    df = add_additional_columns_stopsig(df)
    
    return(df)
