# External imports
import os
import sys
import toml

# Detect if running in Sphinx documentation build
_SPHINX_BUILD = 'sphinx' in sys.modules or os.environ.get('SPHINX_BUILD') == '1'

# Automatic mode detection (control or sandbox)
try:
    import bmc
    if not _SPHINX_BUILD:
        print("✅ BMC lib found. Running in control mode.")
    SANDBOX_MODE = False
except ImportError:
    from .sandbox import bmc_mock as bmc
    if not _SPHINX_BUILD:
        print("❌ BMC lib not found. Install it via the BMC SDK.")
        print("⛱️ Running in sandbox mode.")
    SANDBOX_MODE = True

# Serial library selection
if SANDBOX_MODE:
    from .sandbox import serial_mock as serial
    from .sandbox import xaosim_mock as xaosim
    shm = xaosim.shm
else:
    import serial
    try:
        from xaosim.shmlib import shm
    except ImportError:
        from .sandbox import xaosim_mock as xaosim
        shm = xaosim.shm
        if not _SPHINX_BUILD:
            print("⛱️ xaosim not available - Cred3 will run in mock mode")

# Shortcuts
from .classes import *
from .modules import *
from .utils import *
from .scripts import *

# Initialize Config Singleton
config = classes.config.Config()

# Get version from pyproject.toml
try:
    import toml
    pyproject_file = os.path.join(os.path.dirname(__file__), '../..', 'pyproject.toml')
    with open(pyproject_file, 'r') as f:
        pyproject = toml.load(f)
    __version__ = pyproject['project']['version']
except Exception as e:
    if not _SPHINX_BUILD:
        print("❌ Error: Could not retrieve version information.")
        print(f"ℹ️ {e}")

# Try to get current commit (if in a git repo)
try:
    import subprocess
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    __version__ += f"+{commit[:7]}"
except Exception:
    pass