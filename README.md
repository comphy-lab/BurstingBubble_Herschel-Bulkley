# Herschel-Bulkley Worthington Jets & Droplets Produced by Bursting Bubbles

This repository contains the simulation code and analysis for studying the dynamics of Herschel-Bulkley Worthington jets and droplets produced by bursting bubbles. The code uses the Basilisk framework to simulate bubble cavity collapse in non-Newtonian media, examining how power-law index, yield stress, and viscosity affect jet and droplet formation.

The article can be found at: 

<!-- [![](https://img.shields.io/badge/arXiv-4b4b4b?style=flat&logo=arxiv&link=https://arxiv.org/pdf/22408.05089.pdf)](https://arxiv.org/pdf/2408.05089.pdf) -->
<!-- [![](https://img.shields.io/badge/Journal%20of%20Fluid%20Mechanics-ADD-DOI-HERE-WHEN-PUBLISHED-blue)](https://doi.org/ADD-DOI-HERE-WHEN-PUBLISHED) -->


## Overview

The project investigates how non-Newtonian behavior influences bubble bursting dynamics by exploring the phase space of effective Ohnesorge number, power-law index, and plasto-capillary number using volume of fluid-based finite volume simulations. The results demonstrate how shear-thinning/thickening behavior and yield stress significantly influence the overall dynamics through the interplay of viscous and plastic effects.

## Installation and Setup

To ensure you have the necessary tools and a fresh Basilisk installation, use the provided script:

```bash
./reset_install_requirements.sh
```

### Function
This script checks for Basilisk installation and compiles it if not present.

### OS Compatibility
Designed for macOS. If you encounter issues on Linux, please open a GitHub issue.

### Dependencies
- Basilisk C is fetched and built automatically.
- Xcode Command Line Tools (macOS) or equivalent compiler toolchain (Linux) are required.

### Environment Setup
After running the script, a `.project_config` file is created, setting `BASILISK` and `PATH` automatically.

If you have previously installed Basilisk or changed dependencies, re-run the script with `--hard`:

```bash
./reset_install_requirements.sh --hard
```

## Running the Code

### Recommended Method: Using Makefile

The easiest way to compile and run the code is using the Makefile approach:

1. Navigate to the `testCases` directory:
```bash
cd testCases
```

2. Compile and run using make (this runs the code interactively using the browser):
```bash
CFLAGS=-DDISPLAY=-1 make burstingBubbleVE.tst
```

To run the code non-interactively, use the following command:
```bash
make burstingBubbleVE.tst
```

### Alternative Method: Direct Compilation

You can compile the code directly using `qcc` in two ways:

1. Using include paths (recommended):
```bash
qcc -O2 -Wall -disable-dimensions -I$(PWD)/src-local -I$(PWD)/../src-local burstingBubbleVE.c -o burstingBubbleVE -lm
```

2. Without include paths:
```bash
qcc -O2 -Wall -disable-dimensions burstingBubbleVE.c -o burstingBubbleVE -lm
```
**Note**: If using method 2, you must first manually copy the `src-local` folder to your running directory.

### Local Execution

MacOS:

```bash
# First source the configuration
source .project_config

# Compile using include paths (recommended)
qcc -O2 -Wall -disable-dimensions -I$(PWD)/src-local -I$(PWD)/../src-local burstingBubbleVE.c -o burstingBubbleVE -lm

# Or compile without include paths (requires manually copying src-local folder)
qcc -O2 -Wall -disable-dimensions burstingBubbleVE.c -o burstingBubbleVE -lm

# Run the executable, only supports serial execution
./burstingBubbleVE
```

Linux:

```bash
# First source the configuration
source .project_config

# Compile using include paths (recommended)
qcc -O2 -Wall -disable-dimensions -fopenmp -I$(PWD)/src-local -I$(PWD)/../src-local burstingBubbleVE.c -o burstingBubbleVE -lm

# Or compile without include paths (requires manually copying src-local folder)
qcc -O2 -Wall -disable-dimensions -fopenmp burstingBubbleVE.c -o burstingBubbleVE -lm

# Set the number of OpenMP threads
export OMP_NUM_THREADS=4

# Run the executable
./burstingBubbleVE
```

### HPC Cluster Execution (e.g., Snellius)

For cluster environments, it is strongly recommended to manually copy the `src-local` folder to your working directory to ensure reliable compilation across different cluster configurations:

1. First, copy the required files:
```bash
cp -r /path/to/original/src-local .
```

2. Compile the code for MPI:
```bash
CC99='mpicc -std=c99' qcc -Wall -O2 -D_MPI=1 -disable-dimensions burstingBubbleVE.c -o burstingBubbleVE -lm
```

3. Create a SLURM job script (e.g., `run_simulation.sh`):
```bash
#!/bin/bash

#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --time=1:00:00
#SBATCH --partition=genoa
#SBATCH --mail-type=ALL
#SBATCH --mail-user=v.sanjay@utwente.nl

srun --mpi=pmi2 -n 32 --gres=cpu:32 --mem-per-cpu=1750mb burstingBubbleVE
```

4. Submit the job:
```bash
sbatch run_simulation.sh
```

### Additional Running Scripts

The `z_extras/running` directory contains supplementary materials and post-processing tools used in the analysis. This includes C-based data extraction utilities, Python visualization scripts, and analysis notebooks. These tools were used to process simulation outputs and generate figures for the study. For detailed documentation of these tools, see the [README](z_extras/README.md) in the `z_extras` directory.

## Reset Install Requirements Script

The `reset_install_requirements.sh` script is designed to reset the installation requirements for the project. This can be useful when you want to ensure that all dependencies are fresh and up-to-date.

### Purpose

The script re-installs all required packages as specified in the requirements file, ensuring that the project's dependencies are up-to-date and consistent.

### Usage

To run the script, use the following command in your terminal:

```bash
bash reset_install_requirements.sh
```

Make sure to have the necessary permissions to execute the script.

## Citation

If you use this code in your research, please cite:

### Software
<!-- Add software citation when available -->

## Authors

- Vatsal Sanjay (University of Twente), [vatsalsanjay@gmail.com](mailto:vatsalsanjay@gmail.com)

## License

This project is licensed under standard academic terms. Please cite the paper and software if you use this code in your research. 
