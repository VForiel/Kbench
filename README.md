# Test-bench-controls
---------------------

This repo aim to provide a full set of tools to control all the devices on the Kernel-Nuller test bench.

## 🚀 Quickstart

Requirements:
- [Git](https://git-scm.com/)
- [Python 3.11](https://www.python.org/)

1. Clone the repo:
    ```bash
    git clone https://github.com/Kernel-Nulling/Test-bench-controls
    ```
    And move inside
    ```
    cd Test-bench-controls
    ```

2. (Recommanded) Create a virtual environment
    ```bash
    python3.11 -m venv .kvenv
    ```
    and activate it
    ```bash
    source .kvenv/bin/activate # Linux
    .kvenv/Scripts/activate # Windows
    ```

3. Install requirements
    ```bash
    pip install -r requirements.txt
    ```

4. Start a python instance
    ```bash
    python
    ```
    And import the kbench module
    ```python
    from kbench import *
    ```
    You can now play with all the devices on the Kbench according to the (upcoming) documentation!

## 📚 Documentation

The documentation should be available at the adress: [kbench.docs.foriel.xyz](http://kbench.docs.foriel.xyz).

If you want to build the doc locally, once the project is setup (according to the instructions above):

1. Go in the `docs` folder
    ```bash
    cd docs
    ```
1. Build the doc
    ```bash
    make html # Linux
    .\make.bat html # Windows
    ```
Once the documentation is build, you can find it in the `docs/_build_` folder.