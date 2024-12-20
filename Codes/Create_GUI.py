import pandas as pd
import os
import PySimpleGUI as sg
import sys
import yaml

def import_yaml_file():
    # Load the yaml file with the default values.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_file = os.path.join(script_dir, "GUI_default_values.yaml")
    with open(yaml_file, "r") as file:
        default = yaml.safe_load(file)
    return(default)

def str_to_bool(value):
    dict1 = {'True':True, 'False':False}
    return(dict1[value])

def basic_options(default):
    
    # Create a dictionary with the inputs from the GUI.
    inputs = {}
    
    # Create a GUI with the options for analysis.
    sg.theme("DarkTeal2")
    layout = [
        [sg.T("")], [sg.Text("Choose a folder for the import location"), 
                     sg.Input(default_text=default['Import location'],key="Import",
                              enable_events=True),sg.FolderBrowse(key="Import2")],
        [sg.T("")], [sg.Text("Choose a folder for the export location"),
                     sg.Input(default_text=default['Export location'],key="Export",
                              enable_events=True),sg.FolderBrowse(key="Export2")],
        [sg.T("")], [sg.Text("Start time",size=(8,1)), 
                     sg.Combo(["Use custom time","Use first timestamp","Use initiation poke"],
                              default_value=default['Start time type'], size=(17,1),
                              key="Start_Time_Type",enable_events=True),
                     sg.Input(default_text=default['Start time'],key="Start_Time",
                              enable_events=True, size=(25,1))],
        [sg.T("")], [sg.Text("End time",size=(8,1)), 
                     sg.Combo(["Use custom time","Use last timestamp"],
                              default_value=default['End time type'], size=(17,1),
                              key="End_Time_Type",enable_events=True),
                     sg.Input(default_text=default['End time'],key="End_Time",
                              enable_events=True, size=(25,1))],
        [sg.T("")], [sg.Text("Time bin interval (in mins)",size=(20,1)), 
                     sg.Input(default_text=default['Time bin (mins)'],key="Time_Bin",
                              enable_events=True,size=(10,1))],
        [sg.T("")], [sg.Text("Get individual column summaries and label " +
                             "genotypes/treatments",size=(48,1)), 
                     sg.Combo(["True", "False"],
                              default_value=str(default['Find individual columns']),
                              key="Find_Ind_Cols",enable_events=True)],
        [sg.T("")], [sg.Button("Submit")]
             ]
    window = sg.Window('Options for analysis', layout, finalize=True)
    
    # Intialise the prompt visibility.
    if default["Start time type"] in ["Use first timestamp","Use initiation poke"]:
        window.Element("Start_Time").Update(visible=False)
    if default["Start time type"] == 'Use custom time':
        window.Element("Start_Time").Update(visible=True)
    if default["End time type"] == "Use last timestamp":
        window.Element("End_Time").Update(visible=False)
    if default["End time type"] == 'Use custom time':
        window.Element("End_Time").Update(visible=True)
    
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event=="Exit":
            window.close()
            sys.exit()
        # Make the time entries invisible if needed.
        if values["Start_Time_Type"] in ["Use first timestamp","Use initiation poke"]:
            window.Element("Start_Time").Update(visible=False)
        if values["Start_Time_Type"] == 'Use custom time':
            window.Element("Start_Time").Update(visible=True)
        if values["End_Time_Type"] == "Use last timestamp":
            window.Element("End_Time").Update(visible=False)
        if values["End_Time_Type"] == 'Use custom time':
            window.Element("End_Time").Update(visible=True)
        # If submit is pressed, record the entries in the GUI.
        if event == "Submit":
            inputs['Import location']         = values["Import"]
            inputs['Export location']         = values["Export"]
            inputs['Start time type']         = values["Start_Time_Type"]
            inputs['Start time']              = values["Start_Time"]
            inputs['End time type']           = values["End_Time_Type"]
            inputs['End time']                = values["End_Time"]
            inputs['Time bin (mins)']         = float(values["Time_Bin"])
            inputs['Find individual columns'] = str_to_bool(values["Find_Ind_Cols"])
            window.close()
            break
        
    return(inputs)

def import_settings_file(inputs, default):
    
    sg.theme("DarkTeal2")
    layout = [
        [sg.T("")], [sg.Text(("Import an existing settings excel file with filenames, "+
                              "genotypes and treatments.")), 
                     sg.Combo(["True", "False"],default_value=str(default['Use settings file']),
                              key="Settings",enable_events=True)],
        [sg.T("")], [sg.Button("Submit")]
             ]
    window = sg.Window('Choose whether to import an excel file', layout)
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event=="Exit":
            window.close()
            sys.exit()
        elif event == "Submit":
            inputs['Use settings file'] = str_to_bool(values["Settings"])
            window.close()
            break
    
    return(inputs)    
    
def choose_settings_file_location(inputs, default):
    
    sg.theme("DarkTeal2")
    layout = [
        [sg.T("")], [sg.Text("Choose the location of the settings excel file."), 
                     sg.Input(default_text=default['Settings import location'],key="Import",
                              enable_events=True),sg.FileBrowse(key="Import2")],
        [sg.T("")], [sg.Button("Submit")]
             ]
    window = sg.Window('Choose the location of the excel file.', layout)
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event=="Exit":
            window.close()
            sys.exit()
        elif event == "Submit":
            file_path = values["Import"]
            window.close()
            break
    gt_table = pd.read_excel(file_path, index_col=0)
    gt_table = gt_table.fillna('')
    inputs['Settings import location'] = file_path
    inputs['Genotypes/treatments table'] = gt_table
    
    return(inputs)
    
def create_settings_file(inputs):
    
    # Based on the import location, list all the CSV files to import.
    import_files = [file for file in os.listdir(inputs['Import location']) if 
                    (file.lower().endswith(".csv") and file.startswith("~$")==False)]
    sg.theme("DarkTeal2")
    size1 = (30,1)
    size2 = (34,1)
    layout = [[sg.T("")], [sg.Text('Filename',size=size1), 
                           sg.Text('Genotype',size=size1),
                           sg.Text('Treatment',size=size1)]]
    for filename in import_files:
        layout += [[sg.Text(filename,size=size1), 
                    sg.Input(size=size2,key=filename+'_Genotype'),
                    sg.Input(size=size2,key=filename+'_Treatment')]]
    layout += [[sg.T("")], [sg.Button("Submit")]]
    window = sg.Window('Fill in the genotypes/treatments', layout)
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event=="Exit":
            window.close()
            sys.exit()
        elif event == "Submit":
            gt_table = pd.DataFrame(columns=['Genotype','Treatment'],
                                    index=import_files)
            gt_table.index.name = 'Filename'
            for filename in import_files:
                gt_table.at[filename,'Genotype']  = values[filename+'_Genotype']
                gt_table.at[filename,'Treatment'] = values[filename+'_Treatment']
            window.close()
            break    
    inputs['Genotypes/treatments table'] = gt_table
    
    return(inputs)

def export_settings_file(inputs):
    
    # Export the settings as an excel file.
    export_name = 'Settings_excel_file0.xlsx'
    i = 1
    while export_name in os.listdir(inputs['Export location']):
        export_name = export_name[:-6] + str(i) + '.xlsx'
        i += 1
    export_destination = os.path.join(inputs['Export location'], export_name)
    inputs['Genotypes/treatments table'].to_excel(export_destination)
    print('Saved ' + export_name + ' at ' + inputs['Export location'] + '\n')
    
def export_yaml_file(inputs, default):
    
    export = {}
    entries = ['Import location','Export location','Start time type','Start time',
               'End time type','End time','Time bin (mins)','Find individual columns',
               'Use settings file','Settings import location']
    for entry in entries:
        if entry in inputs.keys():
            export[entry] = inputs[entry]
        elif entry in default.keys():
            export[entry] = default[entry]
        else:
            export[entry] = ''
    
    # Export the default values and replace the old yaml file.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_file = os.path.join(script_dir, "GUI_default_values.yaml")
    with open(yaml_file, "w") as file:
        yaml.dump(export, file, sort_keys=False, default_flow_style=False)
    
def GUI():
    
    default = import_yaml_file()
    inputs = basic_options(default)
    
    # If find individual columns is true, ask whether to import an existing excle file.
    if inputs['Find individual columns'] == True:
        inputs = import_settings_file(inputs, default)
            
        # If the previous option is true, ask for the import location.
        if inputs['Use settings file'] == True:
            inputs = choose_settings_file_location(inputs, default)
        
        # If the previous option is false, type in the genotypes/treatments.
        if inputs['Use settings file'] == False:
            inputs = create_settings_file(inputs)
            export_settings_file(inputs)
    
    # Export the inputs into a yaml file containing the default GUI values for 
    # the next GUI run.
    export_yaml_file(inputs, default)
            
    return(inputs)
