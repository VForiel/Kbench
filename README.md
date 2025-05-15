# Kernel test bench controls

This repo aim to provide a full set of tools to control all the devices on the Kernel-Nuller test bench.

## 🚀 Quickstart

Requirements:
- [Python 3.8](https://www.python.org/) (or higher, but not tested)

0. (Recommended) Create a virtual environment
    ```bash
    python3.8 -m venv .venv
    ```
    and activate it
    ```bash
    source .venv/bin/activate # Linux
    .venv/Scripts/activate # Windows
    ```

1. Install the python module
    ```bash
    pip install Kbench-controls
    ```

2. Start a python instance
    ```bash
    python
    ```
    And import the kbench module
    ```python
    import kbench
    ```
    You can now play with all the devices on the Kbench according to the (upcoming) documentation!

## 📚 Documentation

The documentation should be available at the adress: [kbench.readthedocs.io](http://kbench.readthedocs.io).

If you want to build the doc locally, once the project is setup (according to the instructions above):

1. Go in the `docs` folder
    ```bash
    cd docs
    ```
2. Install the requirements (by preference, in a virtual environment)
    ```bash
    pip install -r requirements.txt
    ```
3. Build the doc
    ```bash
    make html # Linux
    .\make.bat html # Windows
    ```
Once the documentation is build, you can find it in the `docs/_build_` folder.