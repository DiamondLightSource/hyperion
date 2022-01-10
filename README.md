# python-artemis

Repository for the Artemis project to implement "3D grid scans" using the BlueSky / Ophyd framework from BNL. 

https://nsls-ii.github.io/bluesky/


Development Installation
------------

1. Clone this project 
1. If on a DLS machine get Python 3.9 by running:
    ```
    module load python/3.9
    ```
    If not at DLS, use your local version of Python (>3.7)
2. Gather the dependencies by running the following (note that the `--pypi-mirror` command is required at DLS to get the latest dependencies by avoiding the internal mirror, this is not required outside DLS)
    ```
    pipenv install --pypi-mirror="https://pypi.org/simple/" --dev
    ```
3. Install the pre-commit hooks, as specified [here](https://pre-commit.com/#3-install-the-git-hook-scripts).
