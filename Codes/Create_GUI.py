from Preprocess_data import import_data, clean_data, correct_session_type_columns
from Create_concatenator import run_concatenator_gui
from Create_classic_metrics import supports_classic_enhancements
import pandas as pd
import os
import PySimpleGUI as sg
import sys
import yaml
from tkinter import colorchooser

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

def clean_metadata_value(value):
    if pd.isna(value):
        return ''
    return ' '.join(str(value).split())

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
        [sg.T("")], [sg.Button("Submit"), sg.Push(), sg.Button("Concatenate files")]
             ]
    # Resizable window (handy for long paths)
    window = sg.Window('Options for analysis', layout, finalize=True, resizable=True)
    
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
        if event == "Concatenate files":
            run_concatenator_gui()
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

def check_session_type(inputs):
    
    # Find the first file in the folder.
    import_files = [file for file in os.listdir(inputs['Import location']) if 
                    (file.lower().endswith(".csv") and file.startswith("~$")==False)]
    inputs["Filename"] = import_files[0]
    
    # Process the file to find the session type.
    df = import_data(inputs)
    df = clean_data(df, inputs, print_message=False)
    df, inputs = correct_session_type_columns(df, inputs)
    
    return(inputs["Session Type"])

def choose_classic_metrics(inputs, default):

    sg.theme("DarkTeal2")

    # Translate values saved by the earlier three-choice version of this option so existing YAML settings remain compatible.
    saved_active_mode = default.get(
        "Classic active poke fallback",
        "Auto",
    )
    active_mode = {
        "Left": "Left fallback",
        "Right": "Right fallback",
    }.get(saved_active_mode, saved_active_mode)

    layout = [
        [sg.T("")],
        [
            sg.Text("Create additional ClassicFED metric sheets?"),
            sg.Combo(
                ["True", "False"],
                default_value=str(
                    default.get(
                        "Create Classic metric sheets",
                        False,
                    )
                ),
                key="Create Classic metric sheets",
                readonly=True,
            ),
        ],
        [sg.T("")],
        [
            sg.Text(
                "Target duration in minutes "
                "(leave blank to keep original duration)"
            ),
            sg.Input(
                default_text=default.get(
                    "Classic duration (mins)",
                    "",
                ),
                key="Classic duration (mins)",
                size=(10, 1),
            ),
        ],
        [sg.T("")],
        [
            sg.Text("Active poke handling"),
            sg.Combo(
                [
                    "Auto",
                    "Left fallback",
                    "Right fallback",
                    "Skip active-side metrics",
                ],
                default_value=active_mode,
                key="Classic active poke fallback",
                readonly=True,
            ),
        ],
        [sg.T("")],
        [sg.Button("Submit")],
    ]

    window = sg.Window(
        "ClassicFED options",
        layout,
    )

    while True:
        event, values = window.read()

        if event == sg.WIN_CLOSED or event == "Exit":
            window.close()
            sys.exit()

        if event == "Submit":
            create_metrics = str_to_bool(
                values["Create Classic metric sheets"]
            )

            duration_text = str(
                values["Classic duration (mins)"]
            ).strip()

            if duration_text == "":
                duration = ""
            else:
                try:
                    duration = float(duration_text)

                    if duration <= 0:
                        raise ValueError

                except ValueError:
                    sg.popup_error(
                        "Target duration must be a positive "
                        "number or left blank."
                    )
                    continue

            inputs["Create Classic metric sheets"] = (
                create_metrics
            )

            inputs["Classic duration (mins)"] = duration

            inputs["Classic active poke fallback"] = values[
                "Classic active poke fallback"
            ]

            window.close()
            break

    return inputs


def choose_to_create_sum_masters(inputs, default):

    sg.theme("DarkTeal2")
    layout = [
        [sg.T("")],
        [
            sg.Text("Create summed master Excel files?"),
            sg.Combo(
                ["True", "False"],
                default_value=str(
                    default.get("Create sum masters", False)
                ),
                key="Create sum masters",
                readonly=True,
                enable_events=True,
            ),
        ],
        [sg.T("")],
        [sg.Button("Submit")],
    ]

    window = sg.Window(
        "Choose summed master outputs",
        layout,
    )

    while True:
        event, values = window.read()

        if event == sg.WIN_CLOSED or event == "Exit":
            window.close()
            sys.exit()

        elif event == "Submit":
            inputs["Create sum masters"] = str_to_bool(
                values["Create sum masters"]
            )
            window.close()
            break

    return inputs


def choose_light_dark_cycle(inputs, default):
    
    sg.theme("DarkTeal2")
    layout = [
        [sg.T("")], [sg.Text("Light cycle times", size=(14,1)), 
                     sg.Input(default_text=default['Light cycle start'],key="Light cycle start",
                              enable_events=True, size=(10,1)),
                     sg.Input(default_text=default['Light cycle end'],key="Light cycle end",
                              enable_events=True, size=(10,1))],
        [sg.T("")], [sg.Text("The dark cycle times will be filled in automatically")], 
        [sg.T("")], [sg.Button("Submit")]
             ]
    window = sg.Window('Choose the start and end times of the light cycle', layout)
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event=="Exit":
            window.close()
            sys.exit()
        elif event == "Submit":
            inputs['Light cycle start'] = values['Light cycle start']
            inputs['Light cycle end']   = values['Light cycle end']
            window.close()
            break
    
    return(inputs)    

def choose_plot_options(inputs, default):
    metadata_columns = list(inputs["Genotypes/treatments table"].columns)
    if not metadata_columns:
        inputs["Create plots"] = False
        return inputs

    default_primary = default.get("Plot primary group", metadata_columns[0])
    if default_primary not in metadata_columns:
        default_primary = metadata_columns[0]

    secondary_choices = ["None"] + metadata_columns
    default_secondary = default.get("Plot secondary group", "None")
    if default_secondary not in secondary_choices:
        default_secondary = "None"

    sg.theme("DarkTeal2")
    layout = [
        [sg.T("")],
        [sg.Text("Create plots?"),
         sg.Combo(["True", "False"],
                  default_value=str(default.get("Create plots", False)),
                  key="Create plots", readonly=True)],
        [sg.Text("Plot preset"),
         sg.Combo(["Basic", "Full"],
                  default_value=default.get("Plot preset", "Basic"),
                  key="Plot preset", readonly=True)],
        [sg.Text("Plot source"),
         sg.Combo(["Normal", "Summed", "Both"],
                  default_value=default.get("Plot source", "Normal"),
                  key="Plot source", readonly=True)],
        [sg.T("")],
        [sg.Text("Primary grouping"),
         sg.Combo(metadata_columns, default_value=default_primary,
                  key="Plot primary group", readonly=True)],
        [sg.Text("Secondary grouping"),
         sg.Combo(secondary_choices, default_value=default_secondary,
                  key="Plot secondary group", readonly=True)],
        [sg.T("")],
        [sg.Text("Show individual animal lines?"),
         sg.Combo(["True", "False"],
                  default_value=str(default.get("Plot individual lines", False)),
                  key="Plot individual lines", readonly=True)],
        [sg.Text("Shade Dark phases?"),
         sg.Combo(["True", "False"],
                  default_value=str(default.get("Shade dark phases", True)),
                  key="Shade dark phases", readonly=True)],
        [sg.Text("Use custom plot colours?"),
         sg.Combo(["True", "False"],
                  default_value=str(default.get("Use custom plot colors", False)),
                  key="Use custom plot colors", readonly=True)],
        [sg.T("")],
        [sg.Button("Submit")],
    ]

    window = sg.Window("Plot options", layout)
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == "Exit":
            window.close()
            sys.exit()
        if event == "Submit":
            inputs["Create plots"] = str_to_bool(values["Create plots"])
            inputs["Plot preset"] = values["Plot preset"]
            inputs["Plot source"] = values["Plot source"]
            inputs["Plot primary group"] = values["Plot primary group"]
            inputs["Plot secondary group"] = values["Plot secondary group"]
            inputs["Plot individual lines"] = str_to_bool(
                values["Plot individual lines"]
            )
            inputs["Shade dark phases"] = str_to_bool(
                values["Shade dark phases"]
            )
            inputs["Use custom plot colors"] = str_to_bool(
                values["Use custom plot colors"]
            )
            window.close()
            break

    inputs["Plot color maps"] = {}
    if inputs["Create plots"] and inputs["Use custom plot colors"]:
        metadata = inputs["Genotypes/treatments table"]
        color_columns = [inputs["Plot primary group"]]
        secondary = inputs["Plot secondary group"]
        if secondary != "None" and secondary not in color_columns:
            color_columns.append(secondary)

        for column in color_columns:
            color_map = {}
            unique_values = sorted({
                clean_metadata_value(value)
                for value in metadata[column].dropna()
                if clean_metadata_value(value) != ''
            })
            for value in unique_values:
                color = colorchooser.askcolor(
                    title=f"Choose colour for {column}: {value}"
                )[1]
                if color is not None:
                    color_map[str(value)] = color
            inputs["Plot color maps"][column] = color_map

    return inputs


def choose_to_import_settings_file(inputs, default):
    
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
    inputs['Settings import location'] = file_path
    
    return(inputs)

def import_settings_file(inputs):
    
    gt_table = pd.read_excel(inputs['Settings import location'], index_col=0)
    gt_table = gt_table.applymap(clean_metadata_value)
    gt_table.columns = [clean_metadata_value(column) for column in gt_table.columns]
    gt_table.index = gt_table.index.map(clean_metadata_value)
    gt_table.index.name = 'Filename'
    inputs['Genotypes/treatments table'] = gt_table
    
    return(inputs)
    
def create_settings_file(inputs):
    
    # Based on the import location, list all the CSV files to import.
    import_files = [file for file in os.listdir(inputs['Import location']) if 
                    (file.lower().endswith(".csv") and file.startswith("~$")==False)]
    sg.theme("DarkTeal2")
    size1 = (30,1)
    size2 = (20,1)

    # Header row with EDITABLE titles (as before)
    rows = [[sg.T("")],
            [sg.Text('Filename', size=size1),
             sg.Input(default_text="Genotype",  key="Name1", size=size2, expand_x=True),
             sg.Input(default_text="Treatment", key="Name2", size=size2, expand_x=True),
             sg.Input(default_text="Mouse ID",  key="Name3", size=size2, expand_x=True)]]

    # One row per file
    for filename in import_files:
        rows += [[sg.Text(filename, size=size1, tooltip=filename),
                  sg.Input(size=size2, key=filename+'_Name1', expand_x=True),
                  sg.Input(size=size2, key=filename+'_Name2', expand_x=True),
                  sg.Input(size=size2, key=filename+'_Name3', expand_x=True)]]

    # Scrollable column so huge file lists are usable
    scrollable_col = sg.Column(rows, scrollable=True, vertical_scroll_only=True,
                               size=(900, 600), expand_x=True, expand_y=True)
    layout = [[scrollable_col], [sg.Push(), sg.Button("Submit", bind_return_key=True)]]

    # Resizable + draggable window
    window = sg.Window('Fill in the genotypes/treatments', layout,resizable=True,
                       finalize=True, grab_anywhere=True)

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event=="Exit":
            window.close()
            sys.exit()
        elif event == "Submit":
            # READ the customizable column titles from the header inputs
            name1 = values["Name1"]
            name2 = values["Name2"]
            name3 = values["Name3"]

            gt_table = pd.DataFrame(columns=[name1,name2,name3],
                                    index=import_files)
            gt_table.index.name = 'Filename'

            for filename in import_files:
                gt_table.at[filename,name1] = values.get(filename+'_Name1', '')
                gt_table.at[filename,name2] = values.get(filename+'_Name2', '')
                gt_table.at[filename,name3] = values.get(filename+'_Name3', '')
            window.close()
            break    

    gt_table = gt_table.applymap(clean_metadata_value)
    gt_table.columns = [clean_metadata_value(column) for column in gt_table.columns]
    gt_table.index = gt_table.index.map(clean_metadata_value)
    gt_table.index.name = 'Filename'
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
    entries = [
        'Import location',
        'Export location',
        'Start time type',
        'Start time',
        'End time type',
        'End time',
        'Time bin (mins)',
        'Find individual columns',
        'Create sum masters',
        'Create Classic metric sheets',
        'Classic duration (mins)',
        'Classic active poke fallback',
        'Create plots',
        'Plot preset',
        'Plot source',
        'Plot primary group',
        'Plot secondary group',
        'Plot individual lines',
        'Shade dark phases',
        'Use custom plot colors',
        'Use settings file',
        'Settings import location',
        'Light cycle start',
        'Light cycle end',
    ]
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
    
def GUI(skip=False):

    # Import the default settings from the GUI_default_values.yaml file.
    default = import_yaml_file()
    
    # Allow the user to run the codes with the default settings.
    if skip and default["Use settings file"]:
        inputs = import_settings_file(default)
        return(inputs)

    # Choose the basic information for FED analysis.
    inputs = basic_options(default)

    # Inspect the first file to determine the analysis pathway.
    session_type = check_session_type(inputs)

    # Ordinary ClassicFED-style sessions can receive the optional
    # Classic metrics.
    if supports_classic_enhancements(session_type):
        inputs = choose_classic_metrics(
            inputs,
            default,
        )

        # The summed specialised masters are not relevant here.
        inputs["Create sum masters"] = False

    # Specialised long-session types keep their existing options.
    else:
        inputs["Create Classic metric sheets"] = False
        inputs["Classic duration (mins)"] = ""
        inputs["Classic active poke fallback"] = "Auto"

        if session_type in [
            "ClosedEcon_PR1",
            "Bandit",
            "StopSig",
            "LeftRight",
        ]:
            inputs = choose_to_create_sum_masters(
                inputs,
                default,
            )

            inputs = choose_light_dark_cycle(
                inputs,
                default,
            )
        else:
            inputs["Create sum masters"] = False
    
    # If find individual columns is true, ask whether to import an existing excle file.
    if inputs['Find individual columns']:
        inputs = choose_to_import_settings_file(inputs, default)
            
        # If the previous option is true, ask for the import location.
        if inputs['Use settings file']:
            inputs = choose_settings_file_location(inputs, default)
            inputs = import_settings_file(inputs)
        
        # If the previous option is false, type in the genotypes/treatments.
        if inputs['Use settings file'] == False:
            inputs = create_settings_file(inputs)
            export_settings_file(inputs)

        # Plot grouping choices depend on the metadata headers, so ask only after the settings table has been imported or created.
        inputs = choose_plot_options(inputs, default)
    else:
        inputs["Create plots"] = False
    
    # Export the inputs into a yaml file containing the default GUI values for the next GUI run.
    export_yaml_file(inputs, default)
            
    return(inputs)

