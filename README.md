# python-artemis

Repository for the Artemis project to implement "3D grid scans" using the BlueSky / Ophyd framework from BNL. 

https://nsls-ii.github.io/bluesky/


Development Installation
------------

1. Clone this project 
1. If on a DLS machine avoid the controls pypi server and get Python 3.7 by running:
    ```
    module unload controls_dev
    module load python/3.7
    ```
    If not at DLS, use your local version of Python 3.7
1. Gather the dependencies by running the following
    ```
    pipenv install --dev
    ```
1. Install the pre-commit hooks, as specified [here](https://pre-commit.com/#3-install-the-git-hook-scripts).
