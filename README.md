#   DATA SCIENCE
##  BASE PACKAGE REPOS STRUCTURE

This repository contains the Google Cloud Platform maintained by the data science team. It contains GCP specific functions used across different data science projects.

### PROJECT INIT

#### CI / CD
- CD example for GCP Artifact Registry is available in .github/workflows

####    Poetry installation
- Install Poetry: https://python-poetry.org/docs/
- Windows: 
    - Need to install scoop first: https://scoop.sh/

####    Poetry documentation
- You do not need to setp-up because this project backbone already exists. However, it is important to understand the below key concepts 
- Follow this documentation: https://python-poetry.org/docs/basic-usage/
- Important parts are:
    - Project setup
    - Setting a Python version
    - Operationg modes
    - Specifying dependencies
    - Using poetry run 
    - Installing dependencies
- Other parts can read later

####    Poetry install
- Run `poetry install` to create a dedicated virtual environment and install the base dependencies

### README
- Writing your README matters.

### TESTS
- Pytest is the library to be used for unit-testing: https://docs.pytest.org/en/stable/
- Testing matters, please write unit-tests frequently to detect bugs early

### LINT
- Flake8 is used for Linting: https://flake8.pycqa.org/en/latest/
- Please, do not change the .flake8 configuration so it's common to all of our projects

### FORMAT
- Black is used for formatting the codebase: https://black.readthedocs.io/en/stable/index.html
- That ensures a common coding style across projects
