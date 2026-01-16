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
else:
    import serial

# xaosim library selection (for Cred3 camera)
# If in SANDBOX_MODE, use mock even if xaosim is available
# (because we're not on the lab PC and xaosim would return garbage)
if SANDBOX_MODE:
    from .sandbox import xaosim_mock as xaosim
    shm = xaosim.shm
else:
    try:
        from xaosim.shmlib import shm
    except ImportError:
        from .sandbox import xaosim_mock as xaosim
        shm = xaosim.shm
        if not _SPHINX_BUILD:
            print("⛱️ xaosim not available - Cred3 will run in mock mode")

# Import classes
# Import classes
from .classes import PupilMask, FilterWheel, DM, Segment, Chip, XPOW, PhaseShifter, Cred3, Arch6, Config

# Initialize Config Singleton
config = Config()

# Import modules
from .modules import atmosphere

# Import Scripts (functions)
from .scripts import setup, shutdown

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


from .classes import Arch6

# Make bmc, serial and classes available for other modules
__all__ = ['bmc', 'serial', 'shm', 'PupilMask', 'FilterWheel', 'DM', 'Segment', 'Chip', 'XPOW', 'PhaseShifter', 'Cred3', 'atmosphere', 'SANDBOX_MODE', '__version__', 'Arch6', 'Config', 'config', 'setup', 'shutdown']