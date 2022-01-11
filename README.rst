python-artemis
===========================

|code_ci| |docs_ci| |coverage| |pypi_version| |license|

Repository for the Artemis project to implement "3D grid scans" using the BlueSky / Ophyd framework from BNL.

https://nsls-ii.github.io/bluesky/

============== ==============================================================
Source code    https://github.com/DiamondLightSourcepython-artemis
Documentation  https://DiamondLightSource.github.io/python-artemis
Releases       https://github.com/DiamondLightSource/python-artemis/releases
============== ==============================================================

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

.. |code_ci| image:: https://github.com/DiamondLightSource/python-artemis/workflows/Code%20CI/badge.svg?branch=master
    :target: https://github.com/DiamondLightSource/python-artemis/actions?query=workflow%3A%22Code+CI%22
    :alt: Code CI

.. |docs_ci| image:: https://github.com/DiamondLightSource/python-artemis/workflows/Docs%20CI/badge.svg?branch=master
    :target: https://github.com/DiamondLightSource/python-artemis/actions?query=workflow%3A%22Docs+CI%22
    :alt: Docs CI

.. |coverage| image:: https://codecov.io/gh/DiamondLightSource/python-artemis/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/DiamondLightSource/python-artemis
    :alt: Test Coverage

.. |pypi_version| image:: https://img.shields.io/pypi/v/python_artemis.svg
    :target: https://pypi.org/project/python_artemis
    :alt: Latest PyPI version

.. |license| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
    :target: https://opensource.org/licenses/Apache-2.0
    :alt: Apache License

..
    Anything below this line is used when viewing README.rst and will be replaced
    when included in index.rst

See https://DiamondLightSource.github.io/python-artemis for more detailed documentation.
