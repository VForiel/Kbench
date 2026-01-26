import numpy as np
from .. import serial
import time
# import matplotlib.pyplot as plt  # Lazy loaded
# from scipy.optimize import minimize # Lazy loaded
from .. import SANDBOX_MODE
import re
import warnings
from datetime import datetime
import os
from itertools import combinations

from ...utils.singleton import Singleton

class XPOW(metaclass=Singleton):
    """
    Singleton class managing the serial connection to the XPOW controller. You can simply use `phobos.xpow` to access it.
    
    This class ensures a single shared connection is used by all Chip and Channel instances.
    It is automatically instantiated on first access and handles all low-level communication.
    
    Attributes
    ----------
    N_CHANNELS : int
        Total number of channels available (40).
    MAX_VOLTAGE : float
        Maximum voltage in V (5V).
    MAX_CURRENT : float
        Maximum current in mA (300mA).
    CUR_CONVERSION : float
        Conversion factor from mA to DAC units (65535/300).
    VOLT_CONVERSION : float
        Conversion factor from V to DAC units (65535/40).
    CUR_CORRECTION : np.ndarray
        Per-channel calibration multipliers for current (initialized to 1.0).
    VOLT_CORRECTION : np.ndarray
        Per-channel calibration multipliers for voltage (initialized to 1.0).

    Access
    ------
    The singleton instance is available as `phobos.XPOW()`.
    """
    
    _instance = None
    _serial = None
    
    # Hardware specifications
    N_CHANNELS = 40
    
    def __init__(self):
        """Initialize XPOW controller."""

        # Prevent re-initialization in singleton pattern
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.connect()

    def __getattr__(self, name):
        """Handle deprecated method calls with warnings."""
        if name == 'update_all_coeffs':
            warnings.warn(
                "update_all_coeffs() is deprecated and no longer needed. DAC calibration is handled by dac_calibration().",
                DeprecationWarning,
                stacklevel=2
            )
            return lambda plot=False, verbose=False: print(f"⚠️  update_all_coeffs() is deprecated and does nothing.") if verbose else None
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    def connect(self):
        """
        Establish serial connection to the XPOW controller.
        
        Returns
        -------
        serial.Serial
            Active serial connection object.
            
        Raises
        ------
        ConnectionError
            If the XPOW controller does not respond correctly.
            
        Notes
        -----
        - In sandbox mode, uses '/dev/ttyACM0' as default port
        - In normal mode, auto-detects XPOW via USB VID:PID (2341:8036)
        - Baudrate: 115200 baud
        - Timeout: 1.0 second
        """
        if self._serial is None:
            # Setup serial connection
            if SANDBOX_MODE:
                port = '/dev/ttyACM0'
            else:
                from serial.tools import list_ports
                port = list(list_ports.grep("2341:8036"))[0][0]   
            self._serial = serial.Serial(port, baudrate=115200, timeout=1.0)
            
            # Check connection
            res = self.send_command("*IDN?")
            if "XPOW" not in res:
                raise ConnectionError(f"❌ No response from the XPOW controller on port {port} at 115200 bauds. Response was: {res}")
        return self._serial
    
    def disconnect(self):
        """
        Close the serial connection to the XPOW controller.
        
        Notes
        -----
        This method is automatically called when the program exits, but can be
        called manually to release the serial port.
        """
        if self._serial is not None:
            self._serial.close()
            self._serial = None
    
    def send_command(self, cmd: str, verbose: bool = False, output: bool = True) -> str:
        """
        Send a command to the XPOW controller and return the response.
        
        Parameters
        ----------
        cmd : str
            Command string to send (without newline terminator).
        verbose : bool, optional
            If True, print transmitted and received messages. Default is False.
        output : bool, optional
            If True, wait for and return response. Default is True.
            
        Returns
        -------
        str or None
            Response from XPOW controller if output=True, None otherwise.
            
        Notes
        -----
        Common XPOW commands:
        
        - ``*IDN?`` : Query device identification
        - ``CH:X:CUR:Y`` : Set current Y on channel X
        - ``CH:X:VOLT:Y`` : Set voltage Y on channel X
        - ``CH:X:VAL?`` : Query voltage and current on channel X
        """
        cmd_line = cmd + "\n"
        self.connect()
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        if verbose:
            print(f"📤 XPOW TX: '{cmd}'")
        self._serial.write(cmd_line.encode())
        time.sleep(0.01)  # Wait a bit for the command to be processed
        if output:
            response = self._serial.readline().decode().strip()
            if verbose:
                print(f"📥 XPOW RX: '{response}'")
            return response
        else:
            if verbose:
                print(f"📥 Output disabled")
            return None
    
    @staticmethod
    def dac_calibration(plot: bool = False, verbose: bool = False):
        """
        Calibrate DAC power correction coefficients for all 40 XPOW channels.
        
        This method performs 2-point power measurements on every channel to compute
        the slope coefficients used for accurate power control. Each channel is
        calibrated independently.
        
        Parameters
        ----------
        plot : bool, optional
            If True, display calibration comparison plots for each channel. Default is False.
        verbose : bool, optional
            If True, print calibration details for each channel. Default is False.
            
        Notes
        -----
        This method calibrates all 40 channels. For calibrating only specific chip
        channels, use :meth:`Arch.dac_calibration` instead. For a single channel, use
        :meth:`PhaseShifter.dac_calibration`.
        
        The calibration process for each channel:
        1. Set current to 300 mA
        2. Measure power at V = 1V
        3. Measure power at V = 30V
        4. Compute slope coefficient
        5. Store slope in POWER_CORRECTION[channel]
        
        Examples
        --------
        >>> XPOW.dac_calibration(verbose=True)  # Calibrate all channels with details
        >>> XPOW.dac_calibration(plot=True)     # Calibrate and show comparison plots
        """
        if verbose:
            print(f"🔧 Calibrating DAC for all {XPOW.N_CHANNELS} XPOW channels...")
        
        for ch in range(1, XPOW.N_CHANNELS + 1):
            channel = PhaseShifter(ch, calibrate=False)
            channel.dac_calibration(plot=plot, verbose=verbose)
        
        if verbose:
            print("✅ All XPOW DAC calibrations completed.")
    
    @staticmethod
    def turn_off(verbose: bool = False):
        """
        Set voltage and current to zero on ALL 40 XPOW channels.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print shutdown commands. Default is False.
            
        Notes
        -----
        This is a global safety method affecting all 40 channels simultaneously,
        regardless of which chip architectures are in use.
        
        Examples
        --------
        >>> XPOW.turn_off()  # Turn off all channels
        """
        # Get singleton instance
        xpow = XPOW()
        
        if verbose:
            print(f"🔌 Turning off all {XPOW.N_CHANNELS} XPOW channels...")
            
        for ch in range(1, XPOW.N_CHANNELS + 1):
            # Send raw commands to avoid overhead or circular dependency issues
            # Turn voltage to 0 first (safety) then current
            xpow.send_command(f"CH:{ch}:VOLT:0", verbose=False, output=False)
            xpow.send_command(f"CH:{ch}:CUR:0", verbose=False, output=False)
            
        if verbose:
            print(f"✅ All {XPOW.N_CHANNELS} XPOW channels turned off.")
