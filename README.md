# FED3 Time Bins 🐁

### Overview

__FED3__

FED3 or Feeding Experimentation Device Version 3 is a [home cage feeding device](https://github.com/KravitzLabDevices/FED3), developed by the [Kravitz Lab](https://kravitzlab.com/). <br>
It is open source and is used for the training of mice in operant tasks. <br>

__Purpose__

The CSV output from the FED3 devices show the timestamps of each event, like nose pokes or pellet retrievals. This repository :
* Converts this output into a time binned file. It also adds another sheet with the time stamps of all pellet count changes.
* Creates a master file that combines all the “Left poke count” columns from the raw FED files into one sheet. It does the same thing for the other column types as well. The columns are then sorted by genotype and treatment. <br>

__Preview of the graphical user interfaces__

![image](https://user-images.githubusercontent.com/101311642/194792955-85f67a03-a02d-47e2-9e02-c9aa5242e874.png)

__Input and output data__

![image](https://user-images.githubusercontent.com/101311642/194794376-e8ae77ac-dbc8-41dc-a1c8-bf0b7ace3f52.png)

### Installation

Install [Anaconda Navigator](https://www.anaconda.com/products/distribution). <br>
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

### Guide

View the [guide](How_to_use_FED_code.pdf) about how to analyse your FED data.
