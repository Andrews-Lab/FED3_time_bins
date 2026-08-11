import os
import subprocess
import sys
import PySimpleGUI as sg


# Location containing this launcher.
ROOT = os.path.dirname(os.path.abspath(__file__))

TIMEBINS_FOLDER = os.path.join(
    ROOT,
    "FED3_time_bins",
)

TRIALBINS_FOLDER = os.path.join(
    ROOT,
    "FED3_trial_bins",
)


PROGRAMS = {
    "Timebins": {
        "script": os.path.join(
            TIMEBINS_FOLDER,
            "Codes",
            "Run_program.py",
        ),
        # Timebins expects to run from the FED3_time_bins folder.
        "working_directory": TIMEBINS_FOLDER,
    },

    "ClosedEcon PR1": {
        "script": os.path.join(
            TRIALBINS_FOLDER,
            "ClosedEconPR1.py",
        ),
        "working_directory": TRIALBINS_FOLDER,
    },

    "Stop Signal": {
        "script": os.path.join(
            TRIALBINS_FOLDER,
            "StopSig.py",
        ),
        "working_directory": TRIALBINS_FOLDER,
    },

    "Bandit": {
        "script": os.path.join(
            TRIALBINS_FOLDER,
            "Bandit.py",
        ),
        "working_directory": TRIALBINS_FOLDER,
    },
}


def run_program(program_name):
    program = PROGRAMS[program_name]
    script_path = program["script"]
    working_directory = program["working_directory"]

    if not os.path.isfile(script_path):
        sg.popup_error(
            "The selected program could not be found.",
            "",
            script_path,
            title="FED3 Analyzer Error",
        )
        return

    try:
        # sys.executable ensures that the child uses the same FTB Python environment as this launcher.
        completed = subprocess.run(
            [sys.executable, script_path],
            cwd=working_directory,
            check=False,
        )

        if completed.returncode != 0:
            sg.popup_error(
                f"{program_name} exited with an error.",
                "",
                f"Exit code: {completed.returncode}",
                "",
                "Check the terminal for further details.",
                title="FED3 Analyzer Error",
            )

    except Exception as error:
        sg.popup_error(
            f"Could not start {program_name}.",
            "",
            str(error),
            title="FED3 Analyzer Error",
        )


def choose_trialbins():
    layout = [
        [
            sg.Text(
                "Choose a Trialbins analysis",
                font=("Arial", 16),
                justification="center",
                expand_x=True,
            )
        ],
        [sg.Text("")],
        [
            sg.Button(
                "ClosedEcon PR1",
                size=(22, 2),
                expand_x=True,
            )
        ],
        [
            sg.Button(
                "Stop Signal",
                size=(22, 2),
                expand_x=True,
            )
        ],
        [
            sg.Button(
                "Bandit",
                size=(22, 2),
                expand_x=True,
            )
        ],
        [sg.Text("")],
        [
            sg.Push(),
            sg.Button("Back", size=(10, 1)),
        ],
    ]

    window = sg.Window(
        "FED3 Trialbins",
        layout,
        finalize=True,
        resizable=False,
    )

    event, _ = window.read()
    window.close()

    if event in [
        "ClosedEcon PR1",
        "Stop Signal",
        "Bandit",
    ]:
        return event

    return None


def create_welcome_window():
    layout = [
        [
            sg.Text(
                "Welcome to the FED3 Analyzer",
                font=("Arial", 18),
                justification="center",
                expand_x=True,
            )
        ],
        [
            sg.Text(
                "Choose an analysis method",
                justification="center",
                expand_x=True,
            )
        ],
        [sg.Text("")],
        [
            sg.Button(
                "Timebins",
                size=(18, 3),
                expand_x=True,
            ),
            sg.Button(
                "Trialbins",
                size=(18, 3),
                expand_x=True,
            ),
        ],
        [sg.Text("")],
        [
            sg.Push(),
            sg.Button("Exit", size=(10, 1)),
        ],
    ]

    return sg.Window(
        "FED3 Analyzer",
        layout,
        finalize=True,
        resizable=False,
    )


def main():
    sg.theme("DarkTeal2")

    while True:
        window = create_welcome_window()
        event, _ = window.read()
        window.close()

        if event in [sg.WIN_CLOSED, "Exit"]:
            break

        if event == "Timebins":
            run_program("Timebins")

        elif event == "Trialbins":
            trial_choice = choose_trialbins()

            if trial_choice is not None:
                run_program(trial_choice)


if __name__ == "__main__":
    main()