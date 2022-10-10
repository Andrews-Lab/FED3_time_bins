# FED3 Time Bin Analysis

The CSV output from the FED3 devices show the timestamps of each event, like nose pokes or pellet retrievals. This repository :
* Converts this output into a time binned file. It also adds another sheet with the time stamps of all pellet count changes.
* Creates a master file that combines all the “Left poke count” columns from the raw FED files into one sheet. It does the same thing for the other column types as well. The columns are then sorted by genotype and treatment. <br>

![image](https://user-images.githubusercontent.com/101311642/194792955-85f67a03-a02d-47e2-9e02-c9aa5242e874.png)

![image](https://user-images.githubusercontent.com/101311642/194794376-e8ae77ac-dbc8-41dc-a1c8-bf0b7ace3f52.png)

### Installation

Install Anaconda Navigator (https://www.anaconda.com/products/distribution). <br>
Open Anaconda Prompt (on Mac open terminal and install X-Code when prompted). <br>
Download this repository to your home directory by typing in the line below.
```
git clone https://github.com/H-Dempsey/FED3_time_bins.git
```
Change the directory to the place where the downloaded folder is. <br>
```
cd FED3_time_bins
```

Create a conda environment and install the dependencies.
```
conda env create -n FTB -f Dependencies.yaml
```

### Usage
Open Anaconda Prompt (on Mac open terminal). <br>
Change the directory to the place where the git clone was made.
```
cd FED3_time_bins
```

Activate the conda environment.
```
conda activate FTB
```

Choose the code to run by entering one of these lines.
```
python FED.py
```

Alternatively, you can run these codes using a python IDE called "Spyder".
Follow the instructions in the "Guide to these codes" folder.

### Guide

1.	Select all the options for time bins analysis and click “submit”. Here is an explanation of all the options:

![image](https://user-images.githubusercontent.com/101311642/194795486-d17b9044-1810-40e2-996f-ded874208182.png)

* __Import location__: the import location is a folder that contains the raw FEDs data. The code will analyse each CSV file in the folder.
* __Export location__: the export location is a folder for the time binned files.

* __Use active initiation poke__: there is an option to use an active initiation poke for the start time and the last time point for the end time. If this option is set to true, the times will be found using the method below:

![image](https://user-images.githubusercontent.com/101311642/194795613-005ecf9a-4f8e-4ba7-a407-53762669f6cd.png)

* __Start and end times__: if the above option is set to ‘False’, the start and end times can be entered manually. The time points from the raw data CSV file above can be copied directly.
* __Time bin interval (mins)__: the time bin length can be any whole number or decimal in minutes.
* __Get individual column summaries__: make a master excel file that combines the data for each column across many files. The sheets are “left poke count”, “right poke count”, … See step 9 onwards for an explanation of this option.

2.	Go to the export location to find the time binned file.

![image](https://user-images.githubusercontent.com/101311642/194795699-cb983216-67f7-43d7-932c-d549663d3555.png)

3.	Here is the exported data.
* The time bins 0, 1, 2, … refer to t = 0 mins, 0 < t ≤ 1 mins, 1 < t ≤ 2 mins, … These are the rows in yellow. The sheet __Time bins__ only contains these rows.
* Whenever a pellet count changes, the exact time point is shown as a decimal. The time points 4.28, 4.3, 4.33, … refer to t = 4.28 mins, t = 4.3 mins, t = 4.33 mins, … These rows are shown in red and the sheet __Pellet count changes__ only contains these rows.
* The sheet __All data__ contains the rows from both these sheets together.

__All data sheet__

![image](https://user-images.githubusercontent.com/101311642/194795971-fe919b66-9b58-4fbb-ab91-815a45ae8c12.png)

__Time bins sheet__

![image](https://user-images.githubusercontent.com/101311642/194795998-f98295eb-4bad-430c-80cf-5870b52dd613.png)

__Pellet count changes sheet__

![image](https://user-images.githubusercontent.com/101311642/194796013-dce0ef1d-0952-43f3-ba82-4202388931ea.png)

4. The option “get individual columns summaries” at the start of the GUI can also be used to create a master excel file, that combines the columns from all excel files. Note that the raw FED files should still be imported, not the time binned files.

![image](https://user-images.githubusercontent.com/101311642/194796276-162dd303-556c-4e43-bef8-c42922bc4e45.png)

