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

![image](https://user-images.githubusercontent.com/101311642/195033127-046fec78-24ae-4ab7-b059-f763a19e93b4.png)

__Input and output data__

![image](https://user-images.githubusercontent.com/101311642/194794376-e8ae77ac-dbc8-41dc-a1c8-bf0b7ace3f52.png)

### Installation

Install [Anaconda Navigator](https://www.anaconda.com/products/distribution). <br>
Open Anaconda Prompt (on Mac open terminal and install X-Code when prompted). <br>
Download this repository to your home directory by typing in the line below.
```
git clone https://github.com/Andrews-Lab/FED3_time_bins.git
```
If you receive an error about git, install git using the line below, type "Y" when prompted and then re-run the line above.
```
conda install -c anaconda git
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

Run the codes.
```
python FED.py
```

### Guide

View the guide about [how to analyse your FED data](How_to_use_FED_code.pdf).

<br>

### Acknowledgements

__Authors:__ <br>
[Harry Dempsey](https://github.com/H-Dempsey), Taaseen Rahman <br>

__Credits:__ <br>
Zane Andrews, Wang Lok So, Lex Kravitz, Taaseen Rahman <br>

__About the labs:__ <br>
The [Andrews lab](https://www.monash.edu/discovery-institute/andrews-lab) investigates how the brain senses and responds to hunger. <br>
The [Foldi lab](https://www.monash.edu/discovery-institute/foldi-lab) investigates the biological underpinnings of anorexia nervosa and feeding disorders. <br>
The [Kravitz lab](https://kravitzlab.com/) investigates the function of basal ganglia circuits and how they change in diseases such as obesity, addiction, and depression. <br>
