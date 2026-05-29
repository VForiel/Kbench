# Lab PC Setup Guide

This guide provides installation and setup instructions for the PHOTONICS bench laboratory computer.

## Camera (C-Red 3)

### Driver for the EDT PCI Board

The C-Red 3 camera communicates through an EDT PCI board that must be properly configured.

### Dependencies

Install the required libraries:

- **EDT PDV SDK**: Available from `/opt/EDTpdv/`
- **libImageStreamIO**: For shared memory image streaming
- **commander**: Camera control interface

### Starting the C-Red 1 Server

After a reboot, the PCI board must be reconfigured to recognize the camera type:

```bash
cd ~/Progs/repos/dcs/asgard-cred1-server
/opt/EDTpdv/initcam -f cred3_edt_config.cfg
```

Start the C-Red 1 server:

```bash
cd ~/Progs/repos/dcs/asgard-cred1-server
./asgard_cam_server
```

### Camera Control Commands

#### Grab Frames

In the C-Red 1 server prompt:

```bash
fetch
```

#### View Images with shmview

In the "photonic" Python environment:

```bash
shmview
```

- Navigate to **File > Open SHM**
- Select `cred1.im.shm`
- The camera image should appear

#### Stop Grabbing

```bash
stop
```

#### Get Camera Status

```bash
status
```

Returns `idle` if not running, `running` otherwise.

#### Get Framerate

```bash
cli "fps"
```

Returns the frame rate in Hz.

#### Set Framerate

```bash
cli "set fps XXX"
```

Replace `XXX` with the desired frame rate in Hz.

#### Other Commands

Check the C-Red 3 documentation for available commands, then use:

```bash
cli "your_command"
```

### Troubleshooting Camera Issues

#### Camera Information Shows Zeros

If the server displays frame size, timeout, or FPS as 0, restart the PCI board:

```bash
cd ~/Progs/repos/dcs/asgard-cred1-server
/opt/EDTpdv/initcam -f cred3_edt_config.cfg
```

#### Segmentation Fault on "fetch" Command

Restart the PCI board using the same command as above.

#### Segmentation Fault on Server Start

Swap the cables behind the camera, then reinitialize:

```bash
cd ~/Progs/repos/dcs/asgard-cred1-server
/opt/EDTpdv/initcam -f cred3_edt_config.cfg
./asgard_cam_server
```

## USB Device Assignment

To ensure USB devices are assigned to consistent ttyUSB ports for phobos:

Create the udev rules file:

```bash
sudo nano /etc/udev/rules.d/99-usbserial.rules
```

Add the following rules:

```bash
ACTION=="add",ENV{ID_BUS}=="usb",ENV{ID_SERIAL_SHORT}=="AC01ZP6W",SYMLINK+="ttyUSBzaber"
ACTION=="add",ENV{ID_BUS}=="usb",ENV{ID_SERIAL_SHORT}=="TP02052235-13923",SYMLINK+="ttyUSBthorlabs"
ACTION=="add",ENV{ID_BUS}=="usb",ENV{ID_SERIAL_SHORT}=="37001886",SYMLINK+="ttyUSBFlipMount"
ACTION=="add",ENV{ID_BUS}=="usb",ENV{ID_SERIAL_SHORT}=="A64MV77S",SYMLINK+="ttyUSBnewport"
ACTION=="add",ENV{ID_BUS}=="usb",ENV{ID_SERIAL_SHORT}=="c6db877177fded11906c6919f9a91825",SYMLINK+="ttyUSBNkt"
```

Apply the rules:

```bash
sudo udevadm control --reload-rules
```

Or reboot the computer.

**Device mappings:**
- `ttyUSBzaber`: Zaber linear stages
- `ttyUSBthorlabs`: Thorlabs filter wheel
- `ttyUSBFlipMount`: Thorlabs MFF101 flip mount
- `ttyUSBnewport`: Newport mask wheel
- `ttyUSBNkt`: NKT photonics supercontinuum source

phobos reads these device IDs from the `config.yml` file.

### Flip Mount Troubleshooting (MFF101)

If `FlipMount()` fails with a timeout-like traceback similar to:

```
ThorlabsBackendError: read returned less than expected: 0 instead of 1
```

try a full power cycle of the flip mount power supply (turn it off, wait a few seconds, then turn it back on).

This has been observed to recover communication immediately in cases where USB enumeration succeeds but the device does not respond to APT commands.

## Deformable Mirror (BMC)

### Software Download

The BMC SDK can be downloaded directly from the Boston Micromachines website:

[https://bostonmicromachines.com/DMSDK/BMC-DMSDK.zip](https://bostonmicromachines.com/DMSDK/BMC-DMSDK.zip)

:::{note}
The SDK requirements tie us to a specific version of Ubuntu Linux.
:::

After successful installation, files will be added to the `/opt/Boston Micromachines/` directory.

**Verify installation** by checking that the Linux kernel module is loaded:

```bash
lsmod | grep bmc
```

Expected output:
```
bmc_mdrv         16384  0
```

### Configuration Files

Each BMC DM is identified by an 11-digit serial number.

**PHOTONICS bench DM serial number:** `27BW007#051`

Two configuration files must be copied to the appropriate locations:

```bash
sudo cp 27BW007#051.dm /opt/Boston\ Micromachines/Profiles/
sudo cp LUT_27BW007#051.mat /opt/Boston\ Micromachines/Calibration/
```

:::{note}
The `.dm` profile file is mandatory. The `.mat` calibration file may only be used by MATLAB-based tools.
:::

These files are located in the `config/calibration/` directory of this repository.

### Testing the Installation

BMC provides command-line test tools in `/opt/Boston Micromachines/bin/`.

**Test DM communication:**

```bash
/opt/Boston\ Micromachines/bin/BmcExampleC -s 27BW007#051
```

This runs through a sequence of actuator activations to verify proper operation.

## Python Environment Setup

### Lab PC (Linux)

Install all dependencies including hardware-specific libraries:

```bash
# Install base package with lab dependencies
pip install -r requirements-lab.txt
pip install -e .
```

This installs:
- Core dependencies (numpy, scipy, etc.)
- xaosim (for camera shared memory interface)
- Development tools (pytest, jupyter, etc.)

### Development/Sandbox Mode (Windows/Linux without hardware)

For development without hardware access:

```bash
pip install -e .
```

This installs only the base dependencies. The package will automatically run in **sandbox mode** with mock hardware interfaces.

## Verifying Installation

Test the installation in Python:

```python
import phobos

# Check mode
print(f"Sandbox mode: {phobos.SANDBOX_MODE}")

# Try initializing hardware (uses mocks if in sandbox mode)
dm = phobos.DM()
fw = phobos.FilterWheel()
chip = phobos.Chip(6)
camera = phobos.Cred3()
```

If BMC SDK is not installed, you'll see:
```
❌ BMC lib not found. Install it via the BMC SDK.
⛱️ Running in sandbox mode.
```

## Additional Resources

- {doc}`deformable_mirror` - DM control API documentation
- {doc}`cred3` - Camera interface documentation
- {doc}`configuration_file` - Configuration file format
