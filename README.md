# PHOBos - Photonics Bench Operating System

This repo aim to provide a full set of tools to control all the devices on the Kernel-Nuller test bench.

> **⚠️ Important:** This package is designed to run on the PHOTONICS lab PC with specific hardware (BMC deformable mirror, Thorlabs filter wheel, Newport/Zaber motors, C-RED3 camera). Outside this environment, the library will automatically enter **sandbox mode** and simulate missing components with mock interfaces. See the [installation guide](https://phob.readthedocs.io/en/latest/installation.html) for proper lab PC setup.

## 🚀 Quickstart

Requirements:
- [Python 3.12](https://www.python.org/)

### Lab PC Installation (with hardware)

For the lab PC with all hardware connected, follow the complete [installation guide](https://phob.readthedocs.io/en/latest/installation.html).

Quick version:
```bash
pip install -r requirements-lab.txt
pip install -e .
```

### Development/Sandbox Installation (without hardware)

For development or testing without hardware access:

```bash
pip install -e .
```

The package will automatically detect missing hardware and run in **sandbox mode** with mock interfaces.

## 📚 Documentation

The documentation should be available at the adress: [phob.readthedocs.io](http://phob.readthedocs.io).

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