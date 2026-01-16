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


from .utils import Singleton

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
    The singleton instance is available as `phobos.xpow`, `Arch.xpow`, or `PhaseShifter.xpow`.
    """
    
    _instance = None
    _serial = None
    
    # Hardware specifications
    N_CHANNELS = 40

    # Conversion factors (fixed, hardware-dependent)
    # To convert user values (mA, V) to 16-bit DAC values
    CUR_CONVERSION = 65535 / 300  # DAC units per mA
    VOLT_CONVERSION = 65535 / 40  # DAC units per V

    # Securities
    MAX_VOLTAGE = 30  # V
    MAX_CURRENT = 300  # mA
    
    # Correction coefficients (calibrable, initialized to 1.0)
    # Refined by update_coeffs() to compensate for channel variations
    CUR_CORRECTION = np.ones(N_CHANNELS)
    VOLT_CORRECTION = np.ones(N_CHANNELS)
    
    # Power correction coefficients (calibrable, initialized to None)
    # Stores the slope coefficient from P = slope * V² calibration
    # Computed from 2-point measurement (1V and 30V at 300mA)
    # Will be calibrated on first use of set_power() for each channel
    POWER_CORRECTION = np.array([None] * N_CHANNELS)
    
    # Phase-to-power conversion coefficients (radians to W)
    # PHASE_CONVERSION[ch] gives the power needed per radian of phase shift
    # Default: 2π phase shift at 0.6W → 0.6/(2π) ≈ 0.095 W/rad
    PHASE_CONVERSION = np.ones(N_CHANNELS) * (0.6 / (2 * np.pi))
    
    
    def __init__(self):
        """Initialize XPOW controller."""
        if hasattr(self, '_initialized'): return
        self._initialized = True

    
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

    def __init__(self):
        """Initialize XPOW controller."""
        if hasattr(self, '_initialized'): return
        self._initialized = True
        self.connect()

        # Hardware verification (requested by user)
        # Check Channel 1 response (Assuming "Channel 0" in request meant first channel)
        if not SANDBOX_MODE:
            try:
                # 1. Set 300mA, 10V
                self.send_command("CH:1:CUR:300", verbose=False)
                self.send_command("CH:1:VOLT:10", verbose=False)
                
                # 2. Check V > 5
                res = self.send_command("CH:1:VAL?", verbose=False)
                # Parse response explicitly
                match = re.search(r'=\s*([\d\.]+)V', res)
                if not match:
                     raise ValueError(f"Invalid response format: {res}")
                v_meas = float(match.group(1))
                
                if v_meas <= 5.0:
                     raise ConnectionError(f"Voltage check failed. Expected > 5V, got {v_meas}V.")
                     
                # 3. Set 0V
                self.send_command("CH:1:VOLT:0", verbose=False)
                
                # 4. Check V < 5
                res = self.send_command("CH:1:VAL?", verbose=False)
                match = re.search(r'=\s*([\d\.]+)V', res)
                v_meas = float(match.group(1))
                
                if v_meas >= 5.0:
                     raise ConnectionError(f"Voltage reset failed. Expected < 5V, got {v_meas}V.")
                     
                print("✅ XPOW power supply verification passed.")
                
            except Exception as e:
                # Cleanup before raising
                self.send_command("CH:1:CUR:0", verbose=False)
                self.send_command("CH:1:VOLT:0", verbose=False)
                
                err_msg = (
                    f"\n❌ XPOW Verification Failed: {e}\n"
                    "👉 PLEASE FOLLOW THESE STEPS:\n"
                    "   1. Turn OFF the XPOW unit.\n"
                    "   2. Ensure the GENERATOR is turned ON.\n"
                    "   3. Turn ON the XPOW unit.\n"
                    "   4. RESTART the Python kernel."
                )
                raise ConnectionError(err_msg) from e
            finally:
                # Always reset to 0 current/voltage after test
                self.send_command("CH:1:CUR:0", verbose=False)
                self.send_command("CH:1:VOLT:0", verbose=False)




class PhaseShifter:
    """
    Represents a single channel on the photonic chip.
    
    Provides an intuitive interface for controlling individual channels.
    PhaseShifter instances are independent and access the XPOW controller directly.
    
    Parameters
    ----------
    channel_number : int
        Absolute channel number (1-40) on the XPOW controller.
        
    Attributes
    ----------
    channel : int
        The absolute channel number.
    xpow : XPOW
        Reference to the singleton XPOW controller.
        
    Examples
    --------
    >>> ch17 = PhaseShifter(17)
    >>> ch17.set_voltage(2.5)
    >>> current = ch17.get_current()
    """
    
    _instances = {}
    xpow = None

    def __new__(cls, channel_number: int, *args, **kwargs):
        """Multiton pattern: return existing instance for this channel or create new one."""
        if not (1 <= channel_number <= XPOW.N_CHANNELS):
             raise ValueError(f"❌ Invalid channel number {channel_number}. Must be between 1 and {XPOW.N_CHANNELS}.")
             
        if channel_number not in cls._instances:
            cls._instances[channel_number] = super(PhaseShifter, cls).__new__(cls)
        return cls._instances[channel_number]

    def __init__(self, channel_number: int, calibrate: bool = True):
        """
        Initialize a PhaseShifter instance.
        
        Parameters
        ----------
        channel_number : int
            Absolute channel number (1-40).
        """
        # If already initialized (from cache), skip
        if hasattr(self, 'channel'):
            return

        self.channel = channel_number
        self.xpow = XPOW()
        
        # Calibration relies on XPOW connection. 
        # Since we just created it, we might want to calibrate.
        # But if we pull from cache, we skip this block, so we don't re-calibrate.
        if calibrate:
            self.dac_calibration()
        
    def set_current(self, current: float, verbose: bool = False):
        """
        Set current for this channel.
        
        Parameters
        ----------
        current : float
            Target current in mA.
        verbose : bool, optional
            If True, print command details. Default is False.
        
        Notes
        -----
        The DAC value is computed as: current * CUR_CONVERSION * CUR_CORRECTION[channel]
        where CUR_CONVERSION is a fixed hardware constant and CUR_CORRECTION is calibrable.
        """
        current = max(0, min(self.xpow.MAX_CURRENT, current))
        current_value = current * self.xpow.CUR_CONVERSION * self.xpow.CUR_CORRECTION[self.channel - 1]
        self.xpow.send_command(f"CH:{self.channel}:CUR:{int(current_value)}", verbose=verbose, output=False)
        
    def set_voltage(self, voltage: float, verbose: bool = False):
        """
        Set voltage for this channel.
        
        Parameters
        ----------
        voltage : float
            Target voltage in V.
        verbose : bool, optional
            If True, print command details. Default is False.
        
        Notes
        -----
        The DAC value is computed as: voltage * VOLT_CONVERSION * VOLT_CORRECTION[channel]
        where VOLT_CONVERSION is a fixed hardware constant and VOLT_CORRECTION is calibrable.
        """ 
        voltage = max(0, min(self.xpow.MAX_VOLTAGE, voltage))
        voltage_value = voltage * self.xpow.VOLT_CONVERSION * self.xpow.VOLT_CORRECTION[self.channel - 1]
        self.xpow.send_command(f"CH:{self.channel}:VOLT:{int(voltage_value)}", verbose=verbose, output=False)
        
    def get_current(self, verbose: bool = False) -> float:
        """
        Query measured current for this channel.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print query details. Default is False.
            
        Returns
        -------
        float
            Measured current in mA.
        """
        res = self.xpow.send_command(f"CH:{self.channel}:VAL?", verbose=verbose)
        match = re.search(r'=\s*([\d\.]+)V,\s*([\d\.]+)mA', res)
        if match:
            return float(match.group(2))
        else:
            raise ValueError(f"❌ Unable to parse current from response: {res}")
        
    def get_voltage(self, verbose: bool = False) -> float:
        """
        Query measured voltage for this channel.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print query details. Default is False.
            
        Returns
        -------
        float
            Measured voltage in V.
        """
        res = self.xpow.send_command(f"CH:{self.channel}:VAL?", verbose=verbose)
        match = re.search(r'=\s*([\d\.]+)V,\s*([\d\.]+)mA', res)
        if match:
            return float(match.group(1))
        else:
            raise ValueError(f"❌ Unable to parse voltage from response: {res}")
    
    def set_power(self, power: float, verbose: bool = False):
        """
        Set optical power for this channel.
        
        This method sets a fixed current of 300 mA and adjusts the voltage
        to achieve the desired optical power. The power is proportional to V²,
        so the voltage is computed as sqrt(power / slope).
        
        Parameters
        ----------
        power : float
            Target optical power in watts (W).
        verbose : bool, optional
            If True, print command details. Default is False.
        
        Notes
        -----
        The slope coefficient is calibrated automatically on first use using
        a 2-point measurement (1V and 30V at 300mA). The relationship is:
        
            P = slope * V * I
            
        thus, we have:
        
            V = sqrt(P / slope)
        
        Examples
        --------
        >>> ch = PhaseShifter(17)
        >>> ch.set_power(0.6)  # Set to 0.6 W (auto-calibrates if needed)
        """
        # Auto-calibrate if not done yet
        if self.xpow.POWER_CORRECTION[self.channel - 1] is None:
            if verbose:
                print(f"🔧 Auto-calibrating channel {self.channel}...")
            self.dac_calibration(verbose=verbose)
        
        # Set fixed current at 300 mA
        self.set_current(300.0, verbose=verbose)
        
        # Compute voltage from power using the calibrated slope
        # P = slope * V * I  =>  V = sqrt(P / (slope * I))
        # I = 0.3 A (300 mA converted to amperes)
        slope = self.xpow.POWER_CORRECTION[self.channel - 1]
        voltage = np.sqrt(power / slope)
        
        # Apply voltage
        self.set_voltage(voltage, verbose=verbose)
        
        if verbose:
            print(f"🔧 Channel {self.channel}: power={power:.3f} W → voltage={voltage:.3f} V @ 300 mA")
    
    def get_power(self, verbose: bool = False) -> float:
        """
        Query the current optical power based on measured voltage and current.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print query details. Default is False.
            
        Returns
        -------
        float
            Measured optical power in watts (W), computed as P = V × I / 1000.
            
        Notes
        -----
        This method queries both voltage (V) and current (mA) from the XPOW
        controller and computes electrical power: P = V × I / 1000 (converting mA to A).
        
        Examples
        --------
        >>> ch = PhaseShifter(17)
        >>> ch.set_power(0.6)
        >>> power = ch.get_power()
        >>> print(f"Measured power: {power:.3f} W")
        """
        voltage = self.get_voltage(verbose=verbose)
        current = self.get_current(verbose=verbose)
        power = voltage * current / 1000.0  # Convert mA to A: P = V × I
        
        if verbose:
            print(f"📊 Channel {self.channel}: V={voltage:.3f} V, I={current:.1f} mA → P={power:.3f} W")
        
        return power
    
    def dac_calibration(self, verbose: bool = False, plot: bool = False):
        """
        Calibrate power correction coefficient for this channel using 2-point measurement.
        
        This method measures the power at 1V and 30V with a fixed current of 300mA,
        then computes the slope coefficient from these two points. The relationship
        used is P = slope * V * I, where I is in amperes.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print calibration details. Default is False.
        plot : bool, optional
            If True, display before/after calibration comparison plots. Default is False.
            
        Notes
        -----
        The calibration process:
        1. Set current to 300 mA
        2. Measure power at V = 1V
        3. Measure power at V = 30V
        4. Compute slope from: slope = (P2 - P1) / ((V2² - V1²) * I)
        5. Store slope in POWER_CORRECTION[channel]
        
        The slope represents the proportionality constant in P = slope * V² * I.
        
        Examples
        --------
        >>> ch = PhaseShifter(17)
        >>> ch.dac_calibration(verbose=True)
        >>> ch.set_power(0.6)  # Now uses calibrated coefficient
        """
        if verbose:
            print(f"🔧 Calibrating channel {self.channel} using 2-point measurement...")

        # Reset power correction before calibration
        self.xpow.POWER_CORRECTION[self.channel - 1] = None
        
        # ========== BEFORE CALIBRATION SCANS ==========
        if plot:
            import matplotlib.pyplot as plt
            
            # Current scan (before)
            self.set_voltage(1.0, verbose=verbose)
            i_ramp = np.linspace(0, 30, 20)  # mA
            i_meas_before = []
            v_meas_before = []
            p_meas_before = []
            for i in i_ramp:
                self.set_current(i, verbose=False)
                i_meas_before.append(self.get_current(verbose=False))
                v_meas_before.append(self.get_voltage(verbose=False))
                p_meas_before.append(self.get_power(verbose=False))
            
            # Voltage scan (before)
            self.set_current(300.0, verbose=verbose)
            v_ramp = np.linspace(0, 30, 20)  # V
            i_meas_v_before = []
            v_meas_v_before = []
            p_meas_v_before = []
            for v in v_ramp:
                self.set_voltage(v, verbose=False)
                i_meas_v_before.append(self.get_current(verbose=False))
                v_meas_v_before.append(self.get_voltage(verbose=False))
                p_meas_v_before.append(self.get_power(verbose=False))
            
            # Power scan (before)
            p_ramp = np.linspace(0, 1, 20)  # W
            i_meas_p_before = []
            v_meas_p_before = []
            p_meas_p_before = []
            for p in p_ramp:
                self.set_power(p, verbose=False)
                i_meas_p_before.append(self.get_current(verbose=False))
                v_meas_p_before.append(self.get_voltage(verbose=False))
                p_meas_p_before.append(self.get_power(verbose=False))
        
        # ========== CALIBRATION ==========
        # Set fixed current at 300 mA
        self.set_current(300.0, verbose=verbose)
        
        # Measure at 1V
        self.set_voltage(1.0, verbose=verbose)
        v1 = self.get_voltage(verbose=verbose)
        i1 = self.get_current(verbose=verbose) / 1000.0 # Convert mA to A
        
        # Measure at 30V
        self.set_voltage(30.0, verbose=verbose)
        v2 = self.get_voltage(verbose=verbose)
        i2 = self.get_current(verbose=verbose) / 1000.0  # Convert mA to A
        
        # Compute slope coefficient
        # (the slope is coming from a potential difference between what is set and what is measured)
        # P = slope * V * I  (with I in amperes)
        if abs(v2 - v1) < 0.01:  # Voltage difference too small
            if verbose:
                print(f"⚠️  Channel {self.channel}: voltage unchanged (v1={v1:.2f}V, v2={v2:.2f}V). Using default slope=1.0. Please ensure the XPOW is correctly powered. If so, try to restart it.")
            slope = 1.0
        else:
            slope = (i2 - i1) / (v2 - v1)
        
        # Store the slope coefficient
        self.xpow.POWER_CORRECTION[self.channel - 1] = slope
        
        if verbose:
            print(f"✅ Channel {self.channel} calibrated: slope={slope:.6f}")
        
        # ========== AFTER CALIBRATION SCANS ==========
        if plot:
            # Current scan (after)
            self.set_voltage(1.0, verbose=verbose)
            i_meas_after = []
            v_meas_after = []
            p_meas_after = []
            for i in i_ramp:
                self.set_current(i, verbose=False)
                i_meas_after.append(self.get_current(verbose=False))
                v_meas_after.append(self.get_voltage(verbose=False))
                p_meas_after.append(self.get_power(verbose=False))
            
            # Voltage scan (after)
            self.set_current(300.0, verbose=verbose)
            i_meas_v_after = []
            v_meas_v_after = []
            p_meas_v_after = []
            for v in v_ramp:
                self.set_voltage(v, verbose=False)
                i_meas_v_after.append(self.get_current(verbose=False))
                v_meas_v_after.append(self.get_voltage(verbose=False))
                p_meas_v_after.append(self.get_power(verbose=False))
            
            # Power scan (after)
            i_meas_p_after = []
            v_meas_p_after = []
            p_meas_p_after = []
            for p in p_ramp:
                self.set_power(p, verbose=False)
                i_meas_p_after.append(self.get_current(verbose=False))
                v_meas_p_after.append(self.get_voltage(verbose=False))
                p_meas_p_after.append(self.get_power(verbose=False))
            
            # ========== PLOTTING ==========
            fig, axs = plt.subplots(3, 3, figsize=(15, 12))
            
            # Row 0: Current scan
            axs[0, 0].plot(i_ramp, i_meas_before, 'o-', label='Before', alpha=0.7)
            axs[0, 0].plot(i_ramp, i_meas_after, 's-', label='After', alpha=0.7)
            axs[0, 0].set_xlabel('Set Current (mA)')
            axs[0, 0].set_ylabel('Measured Current (mA)')
            axs[0, 0].set_title('Current Scan - Current')
            axs[0, 0].grid(True)
            axs[0, 0].legend()
            
            axs[0, 1].plot(i_ramp, v_meas_before, 'o-', label='Before', alpha=0.7)
            axs[0, 1].plot(i_ramp, v_meas_after, 's-', label='After', alpha=0.7)
            axs[0, 1].set_xlabel('Set Current (mA)')
            axs[0, 1].set_ylabel('Measured Voltage (V)')
            axs[0, 1].set_title('Current Scan - Voltage')
            axs[0, 1].grid(True)
            axs[0, 1].legend()
            
            axs[0, 2].plot(i_ramp, p_meas_before, 'o-', label='Before', alpha=0.7)
            axs[0, 2].plot(i_ramp, p_meas_after, 's-', label='After', alpha=0.7)
            axs[0, 2].set_xlabel('Set Current (mA)')
            axs[0, 2].set_ylabel('Measured Power (W)')
            axs[0, 2].set_title('Current Scan - Power')
            axs[0, 2].grid(True)
            axs[0, 2].legend()
            
            # Row 1: Voltage scan
            axs[1, 0].plot(v_ramp, i_meas_v_before, 'o-', label='Before', alpha=0.7)
            axs[1, 0].plot(v_ramp, i_meas_v_after, 's-', label='After', alpha=0.7)
            axs[1, 0].set_xlabel('Set Voltage (V)')
            axs[1, 0].set_ylabel('Measured Current (mA)')
            axs[1, 0].set_title('Voltage Scan - Current')
            axs[1, 0].grid(True)
            axs[1, 0].legend()
            
            axs[1, 1].plot(v_ramp, v_meas_v_before, 'o-', label='Before', alpha=0.7)
            axs[1, 1].plot(v_ramp, v_meas_v_after, 's-', label='After', alpha=0.7)
            axs[1, 1].set_xlabel('Set Voltage (V)')
            axs[1, 1].set_ylabel('Measured Voltage (V)')
            axs[1, 1].set_title('Voltage Scan - Voltage')
            axs[1, 1].grid(True)
            axs[1, 1].legend()
            
            axs[1, 2].plot(v_ramp, p_meas_v_before, 'o-', label='Before', alpha=0.7)
            axs[1, 2].plot(v_ramp, p_meas_v_after, 's-', label='After', alpha=0.7)
            axs[1, 2].set_xlabel('Set Voltage (V)')
            axs[1, 2].set_ylabel('Measured Power (W)')
            axs[1, 2].set_title('Voltage Scan - Power')
            axs[1, 2].grid(True)
            axs[1, 2].legend()
            
            # Row 2: Power scan
            axs[2, 0].plot(p_ramp, i_meas_p_before, 'o-', label='Before', alpha=0.7)
            axs[2, 0].plot(p_ramp, i_meas_p_after, 's-', label='After', alpha=0.7)
            axs[2, 0].set_xlabel('Set Power (W)')
            axs[2, 0].set_ylabel('Measured Current (mA)')
            axs[2, 0].set_title('Power Scan - Current')
            axs[2, 0].grid(True)
            axs[2, 0].legend()
            
            axs[2, 1].plot(p_ramp, v_meas_p_before, 'o-', label='Before', alpha=0.7)
            axs[2, 1].plot(p_ramp, v_meas_p_after, 's-', label='After', alpha=0.7)
            axs[2, 1].set_xlabel('Set Power (W)')
            axs[2, 1].set_ylabel('Measured Voltage (V)')
            axs[2, 1].set_title('Power Scan - Voltage')
            axs[2, 1].grid(True)
            axs[2, 1].legend()
            
            axs[2, 2].plot(p_ramp, p_meas_p_before, 'o-', label='Before', alpha=0.7)
            axs[2, 2].plot(p_ramp, p_meas_p_after, 's-', label='After', alpha=0.7)
            axs[2, 2].set_xlabel('Set Power (W)')
            axs[2, 2].set_ylabel('Measured Power (W)')
            axs[2, 2].set_title('Power Scan - Power')
            axs[2, 2].grid(True)
            axs[2, 2].legend()
            
            plt.suptitle(f'Channel {self.channel} Calibration Comparison', fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.show()
        
        # Turn off channel after calibration
        self.turn_off(verbose=verbose)
    
    def turn_off(self, verbose: bool = False):
        """
        Set voltage and current to zero on this channel.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print shutdown commands. Default is False.
            
        Examples
        --------
        >>> ch = Channel(17)
        >>> ch.turn_off()  # Turn off channel 17
        """
        self.set_current(0, verbose=verbose)
        self.set_voltage(0, verbose=verbose)
        if verbose:
            print(f"✅ Channel {self.channel} turned off.")
        
    def ensure_current(self, current: float, tolerance: float = 0.1, max_attempts: int = 100, verbose: bool = False):
        """
        Iteratively adjust current until target is reached.
        
        Parameters
        ----------
        current : float
            Target current in mA.
        tolerance : float, optional
            Acceptable error in mA. Default is 0.1 mA.
        max_attempts : int, optional
            Maximum adjustment iterations. Default is 100.
        verbose : bool, optional
            If True, print adjustment details. Default is False.
            
        Returns
        -------
        float
            Correction factor applied.
        """
        attempts = 0
        step_current = current
        while attempts < max_attempts:
            measured_current = self.get_current(verbose=verbose)
            error = current - measured_current
            if abs(error) <= tolerance:
                return step_current / current
            step = 0.5 * error
            step_current = measured_current + step
            self.set_current(step_current, verbose=verbose)
            attempts += 1
        if abs(error) > tolerance:
            raise RuntimeError(f"❌ Unable to reach target current {current} mA on channel {self.channel} within {tolerance} mA after {max_attempts} attempts.")
        
    def ensure_voltage(self, voltage: float, tolerance: float = 0.01, max_attempts: int = 100, verbose: bool = False):
        """
        Iteratively adjust voltage until target is reached.
        
        Parameters
        ----------
        voltage : float
            Target voltage in V.
        tolerance : float, optional
            Acceptable error in V. Default is 0.01 V.
        max_attempts : int, optional
            Maximum adjustment iterations. Default is 100.
        verbose : bool, optional
            If True, print adjustment details. Default is False.
            
        Returns
        -------
        float
            Correction factor applied.
        """
        attempts = 0
        step_voltage = voltage
        while attempts < max_attempts:
            measured_voltage = self.get_voltage(verbose=verbose)
            error = voltage - measured_voltage
            if abs(error) <= tolerance:
                return step_voltage / voltage
            step = 0.5 * error
            step_voltage = measured_voltage + step
            self.set_voltage(step_voltage, verbose=verbose)
            attempts += 1
        if abs(error) > tolerance:
            raise RuntimeError(f"❌ Unable to reach target voltage {voltage} V on channel {self.channel} within {tolerance} V after {max_attempts} attempts.")
    
    def set_phase(self, phase: float, verbose: bool = False):
        """
        Set phase shift for this channel by varying power.
        
        The phase is assumed to be a linear function of the injected power.
        
        Parameters
        ----------
        phase : float
            Target phase shift in radians.
        verbose : bool, optional
            If True, print command details. Default is False.
            
        Notes
        -----
        The power is computed as: phase * PHASE_CONVERSION[channel]
        where PHASE_CONVERSION is the phase-to-power coefficient in W/rad.
        This coefficient can be calibrated using Arch.phase_calibration().
        """
        # Compute power needed for the desired phase
        power = phase * self.xpow.PHASE_CONVERSION[self.channel - 1]
        
        # Apply the power
        self.set_power(power, verbose=verbose)
        
        if verbose:
            print(f"🔧 Channel {self.channel}: phase={phase:.3f} rad → power={power:.3f} W")
    
    def get_phase(self, verbose: bool = False) -> float:
        """
        Query the current phase shift based on set power.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print query details. Default is False.
            
        Returns
        -------
        float
            Estimated phase shift in radians, computed from measured power.
            
        Notes
        -----
        The phase is computed as: power / PHASE_CONVERSION[channel]
        This assumes the power-to-phase relationship is linear.
        """
        power = self.get_power(verbose=verbose)
        phase = power / self.xpow.PHASE_CONVERSION[self.channel - 1]
        
        if verbose:
            print(f"📊 Channel {self.channel}: power={power:.3f} W → phase={phase:.3f} rad")
        
        return phase
    
    def __getattr__(self, name):
        """Handle deprecated method calls with warnings."""
        if name == 'calibrate':
            warnings.warn(
                "calibrate() is deprecated, use dac_calibration() instead",
                DeprecationWarning,
                stacklevel=2
            )
            return self.dac_calibration
        elif name == 'update_coeff':
            warnings.warn(
                "update_coeff() is deprecated and no longer needed. DAC calibration is handled by dac_calibration().",
                DeprecationWarning,
                stacklevel=2
            )
            return lambda plot=False, verbose=False: print(f"⚠️  update_coeff() is deprecated and does nothing.") if verbose else None
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

class _Arch:
    """
    Base class to handle a photonic chip architecture via the XPOW controller.
    
    This class should be subclassed for specific architectures (e.g. Arch1, Arch6).
    It manages a list of PhaseShifter objects corresponding to the TOPAs in that architecture.
    All chip instances share the same XPOW controller connection.
    
    Parameters
    ----------
    name : str
        Human-readable name of the architecture.
    id : str
        Architecture identifier code.
    n_inputs : int
        Number of input ports.
    n_outputs : int
        Number of output ports.
    topas : tuple
        Absolute channel numbers for TOPAs in this architecture.
    number : int, optional
        Architecture number.
        
    Attributes
    ----------
    name : str
        Human-readable name of the architecture.
    id : str
        Architecture identifier code.
    number : int
        Architecture number.
    n_inputs : int
        Number of input ports.
    n_outputs : int
        Number of output ports.
    topas : tuple
        Absolute channel numbers for TOPAs in this architecture.
    channels : list[PhaseShifter]
        List of PhaseShifter instances (indexed from 0).
    xpow : XPOW
        Reference to the singleton XPOW controller.
    """

    xpow = None

    def __init__(self, name: str, id: str, n_inputs: int, n_outputs: int, topas: tuple, number: int = None):
        """
        Initialize a Arch instance.
        """
        self.name = name
        self.id = id
        self.number = number
        self.n_inputs = n_inputs
        self.n_outputs = n_outputs
        self.topas = topas
        
        # Get Singleton XPOW instance (triggers connection if not already connected)
        self.xpow = XPOW()
        
        # Create channel objects (list indexed from 0)
        self.channels = [PhaseShifter(channel_num) for channel_num in self.topas]
        
        # Ensure XPOW connection is established
        # _xpow.connect() # Lazy loading, removed eager connect

    def __getattr__(self, name):
        """Handle deprecated method calls with warnings."""
        if name == 'update_coeffs':
            warnings.warn(
                "update_coeffs() is deprecated and no longer needed. DAC calibration is handled by dac_calibration().",
                DeprecationWarning,
                stacklevel=2
            )
            return lambda plot=False, verbose=False: print(f"⚠️  update_coeffs() is deprecated and does nothing.") if verbose else None
        elif name == 'calibrate_phase':
            warnings.warn(
                "calibrate_phase() is deprecated, use phase_calibration() instead",
                DeprecationWarning,
                stacklevel=2
            )
            return self.phase_calibration
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __getitem__(self, topa_index: int) -> PhaseShifter:
        """
        Access channel by TOPA index (1-indexed): chip[1] returns first TOPA channel.
        
        Parameters
        ----------
        topa_index : int
            TOPA index starting from 1.
            
        Returns
        -------
        Channel
            The corresponding Channel instance.
            
        Raises
        ------
        IndexError
            If topa_index is out of range for this architecture.
        """
        if not (1 <= topa_index <= len(self.channels)):
            raise IndexError(f"❌ TOPA index {topa_index} not available for architecture {self.number}. Available indices: 1-{len(self.channels)}")
        return self.channels[topa_index - 1]
    
    def set_currents(self, currents, verbose: bool = False):
        """
        Set currents for all TOPAs in this chip.
        
        Parameters
        ----------
        currents : array-like
            Array of target currents in mA (one per TOPA).
            Length must match number of TOPAs in architecture.
        verbose : bool, optional
            If True, print command details. Default is False.
            
        Raises
        ------
        ValueError
            If length of currents doesn't match number of TOPAs.
            
        Examples
        --------
        >>> chip = Chip(6)  # 4 TOPAs
        >>> chip.set_currents([10.0, 15.0, 20.0, 25.0])
        """
        currents = np.asarray(currents)
        if len(currents) != len(self.channels):
            raise ValueError(f"❌ Expected {len(self.channels)} current values, got {len(currents)}")
        
        for channel, current in zip(self.channels, currents):
            channel.set_current(current, verbose=verbose)
    
    def set_voltages(self, voltages, verbose: bool = False):
        """
        Set voltages for all TOPAs in this chip.
        
        Parameters
        ----------
        voltages : array-like
            Array of target voltages in V (one per TOPA).
            Length must match number of TOPAs in architecture.
        verbose : bool, optional
            If True, print command details. Default is False.
            
        Raises
        ------
        ValueError
            If length of voltages doesn't match number of TOPAs.
            
        Examples
        --------
        >>> chip = Chip(6)  # 4 TOPAs
        >>> chip.set_voltages([1.5, 2.0, 2.5, 3.0])
        """
        voltages = np.asarray(voltages)
        if len(voltages) != len(self.channels):
            raise ValueError(f"❌ Expected {len(self.channels)} voltage values, got {len(voltages)}")
        
        for channel, voltage in zip(self.channels, voltages):
            channel.set_voltage(voltage, verbose=verbose)
    
    def get_currents(self, verbose: bool = False) -> np.ndarray:
        """
        Query measured currents for all TOPAs in this chip.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print query details. Default is False.
            
        Returns
        -------
        np.ndarray
            Array of measured currents in mA (one per TOPA).
            
        Examples
        --------
        >>> chip = Chip(6)
        >>> currents = chip.get_currents()
        >>> print(currents)  # [10.2, 15.1, 19.8, 24.9]
        """
        return np.array([ch.get_current(verbose=verbose) for ch in self.channels])
    
    def get_voltages(self, verbose: bool = False) -> np.ndarray:
        """
        Query measured voltages for all TOPAs in this chip.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print query details. Default is False.
            
        Returns
        -------
        np.ndarray
            Array of measured voltages in V (one per TOPA).
            
        Examples
        --------
        >>> chip = Chip(6)
        >>> voltages = chip.get_voltages()
        >>> print(voltages)  # [1.52, 2.01, 2.48, 2.99]
        """
        return np.array([ch.get_voltage(verbose=verbose) for ch in self.channels])
    
    def set_powers(self, powers, verbose: bool = False):
        """
        Set optical powers for all TOPAs in this chip.
        
        Parameters
        ----------
        powers : array-like
            Array of target powers in W (one per TOPA).
            Length must match number of TOPAs in architecture.
        verbose : bool, optional
            If True, print command details. Default is False.
            
        Raises
        ------
        ValueError
            If length of powers doesn't match number of TOPAs.
            
        Examples
        --------
        >>> chip = Arch(6)  # 4 TOPAs
        >>> chip.set_powers([0.3, 0.4, 0.5, 0.6])
        
        Notes
        -----
        Each channel will auto-calibrate on first use if not already calibrated.
        """
        powers = np.asarray(powers)
        if len(powers) != len(self.channels):
            raise ValueError(f"❌ Expected {len(self.channels)} power values, got {len(powers)}")
        
        for channel, power in zip(self.channels, powers):
            channel.set_power(power, verbose=verbose)
    
    def get_powers(self, verbose: bool = False) -> np.ndarray:
        """
        Query measured optical powers for all TOPAs in this chip.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print query details. Default is False.
            
        Returns
        -------
        np.ndarray
            Array of measured powers in W (one per TOPA).
            
        Examples
        --------
        >>> chip = Arch(6)
        >>> powers = chip.get_powers()
        >>> print(powers)  # [0.31, 0.42, 0.51, 0.59]
        """
        return np.array([ch.get_power(verbose=verbose) for ch in self.channels])
    
    def turn_off(self, verbose: bool = False):
        """
        Set voltage and current to zero on all TOPAs in this chip only.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print shutdown commands. Default is False.
            
        Notes
        -----
        This method only affects the channels used by this chip architecture.
        To turn off all 40 XPOW channels, use XPOWController.turn_off().
        
        Examples
        --------
        >>> chip = Chip(6)  # 4 channels: 17, 18, 19, 20
        >>> chip.turn_off()  # Only turns off channels 17-20
        """
        for channel in self.channels:
            channel.set_current(0, verbose=verbose)
            channel.set_voltage(0, verbose=verbose)
        if verbose:
            print(f"✅ Chip {self.name} turned off (channels {list(self.topas)}).")
        if verbose:
            print(f"✅ Chip {self.name} turned off (channels {list(self.topas)}).")

    def set_phases(self, phases, verbose: bool = False):
        """
        Set phase shifts for all TOPAs in this chip.
        
        Parameters
        ----------
        phases : array-like
            Array of target phase shifts in radians (one per TOPA).
            Length must match number of TOPAs in architecture.
        verbose : bool, optional
            If True, print command details. Default is False.
            
        Raises
        ------
        ValueError
            If length of phases doesn't match number of TOPAs.
            
        Examples
        --------
        >>> chip = Chip(6)  # 4 TOPAs
        >>> chip.set_phases([0.0, np.pi/4, np.pi/2, np.pi])
        """
        phases = np.asarray(phases)
        if len(phases) != len(self.channels):
            raise ValueError(f"❌ Expected {len(self.channels)} phase values, got {len(phases)}")
        
        for channel, phase in zip(self.channels, phases):
            channel.set_phase(phase, verbose=verbose)
    
    def get_phases(self, verbose: bool = False) -> np.ndarray:
        """
        Query estimated phase shifts for all TOPAs in this chip.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print query details. Default is False.
            
        Returns
        -------
        np.ndarray
            Array of estimated phase shifts in radians (one per TOPA).
            
        Examples
        --------
        >>> chip = Chip(6)
        >>> phases = chip.get_phases()
        >>> print(phases)  # [0.0, 0.785, 1.571, 3.142]
        """
        return np.array([ch.get_phase(verbose=verbose) for ch in self.channels])
    
    def dac_calibration(self, plot: bool = False, verbose: bool = False):
        """
        Calibrate DAC power correction coefficients for all channels in this architecture.
        
        This method performs 2-point power measurements on each TOPA channel to compute
        the slope coefficients used for accurate power control. Only channels used by
        this specific architecture are calibrated, leaving other XPOW channels unchanged.
        
        Parameters
        ----------
        plot : bool, optional
            If True, display calibration comparison plots for each channel. Default is False.
        verbose : bool, optional
            If True, print calibration details for each channel. Default is False.
            
        Notes
        -----
        Only calibrates TOPA channels in self.topas (the channels used by this architecture).
        For calibrating all 40 XPOW channels, use :meth:`XPOW.dac_calibration`.
        For a single channel, use :meth:`PhaseShifter.dac_calibration`.
        
        Examples
        --------
        >>> arch = Arch6()
        >>> arch.dac_calibration(verbose=True)  # Calibrate only Arch6's 4 TOPAs
        """
        if verbose:
            print(f"🔧 Calibrating DAC for {len(self.channels)} channels in {self.name}...")
        
        for channel in self.channels:
            channel.dac_calibration(plot=plot, verbose=verbose)
        
        if verbose:
            print(f"✅ DAC calibration completed for {self.name} (channels {list(self.topas)}).")
    
    def phase_calibration(self, samples: int, cred3_object, crop_centers, crop_sizes=10, plot: bool = False, verbose: bool = False):
        """
        Calibrate phase-to-power conversion coefficients for all channels in this chip.
        
        This method scans each channel individually from 0 to 1.2W, measures the output flux
        using the provided Cred3 camera object, fits a sinusoid to the response, and
        updates the PHASE_CONVERSION coefficient based on the measured period.
        
        Parameters
        ----------
        samples : int
            Number of power steps for the scan.
        cred3_object : Cred3
            Instance of the Cred3 camera class.
        crop_centers : list or ndarray
            List of (x, y) coordinates for the output spots to monitor.
        crop_sizes : int or tuple, optional
            Size of the crop window. Default is 10.
        plot : bool, optional
            If True, plot the fitted curves. Default is False.
        verbose : bool, optional
            If True, print calibration details. Default is False.
        """
        
        power_range = np.linspace(0, 1, samples)
        
        # Define the fitting function: (A + F*P) * sin(B * P + C) + D * P + E
        # def sine_func(x, A, B, C, D, E, F):
        #     return (A + F * x) * np.sin(B * x + C) + D * x + E

        def sine_func(x, A, B, C, D, E):
            return A * np.sin(2*np.pi/B * x + C) + D * x + E
            
        if verbose:
            print(f"🔧 Calibrating phase for {len(self.channels)} channels...")
            
        if plot:
            # Calculate grid size for subplots based on number of channels
            n_channels = len(self.channels)
            cols = int(np.ceil(np.sqrt(n_channels)))
            rows = int(np.ceil(n_channels / cols))
            import matplotlib.pyplot as plt
            fig, axs = plt.subplots(rows, cols, figsize=(4*cols, 3*rows), constrained_layout=True)
            fig.suptitle(f"Phase Calibration - {self.name}")
            if n_channels > 1:
                axs = np.atleast_1d(axs).flatten()
            else:
                axs = [axs]

        out_fluxes = []
        for idx, channel in enumerate(self.channels):

            # Turn off all channels first
            self.turn_off(verbose=verbose)

            if verbose:
                print(f"  - Scanning channel {channel.channel}...")
                
            fluxes = []
            
            # Scan power
            for p in power_range:
                channel.set_power(p)
                
                # Get outputs
                outs = cred3_object.get_outputs(crop_centers=crop_centers, crop_sizes=crop_sizes)
                fluxes.append(outs)
            
            fluxes = np.array(fluxes) # Shape (n_samples, n_outputs)
            out_fluxes.append(fluxes)
            
            # Calculate amplitudes to filter out unaffected outputs
            amplitudes = np.ptp(fluxes, axis=0)
            max_amp = np.max(amplitudes) if len(amplitudes) > 0 else 0
            threshold = max_amp / 10.0
            
            # Fit each output
            periods = []
            
            n_outputs = fluxes.shape[1]
            
            if plot:
                ax = axs[idx]
                ax.set_title(f"Channel {channel.channel}")
                ax.set_xlabel("Power (W)")
                ax.set_ylabel("Flux")
                ax.grid(True)
            
            for i in range(n_outputs):
                if amplitudes[i] < threshold:
                    # Skip outputs that are not affected by this shifter
                    continue

                y_data = fluxes[:, i]
                
                # Initial guess
                # A: (max-min)/2
                # B: 2*pi / 0.6 (assuming ~0.6W period) -> ~10
                # C: 0
                # D: 0
                # E: mean
                # F: 0
                p0 = [(np.max(y_data)-np.min(y_data))/2, 11, 0, 0, np.mean(y_data), 0]

                p0 = [(np.max(y_data)-np.min(y_data))/2, 0.6, 0, 0, np.mean(y_data)]

                bounds_min = [0,      0,  0,      -np.inf, 0,     -np.inf]
                bounds_max = [np.inf, 20, 2*np.pi, np.inf, np.inf, np.inf]

                bounds_min = [0,      0.5,-np.pi,-np.inf,-np.inf]
                bounds_max = [np.inf, 1  , np.pi, np.inf, np.inf]
                
                try:

                    method = 'curve_fit'

                    if method == 'minimize':
                        from scipy.optimize import minimize
                        
                        # Define residual function for minimize
                        def residual(params):
                            return np.sum((y_data - sine_func(power_range, *params))**2)
                        
                        # Use minimize with robust method
                        result = minimize(residual, p0, bounds=np.array((bounds_min, bounds_max)).T, options={'maxiter':10000})
                        popt = result.x

                    elif method == 'curve_fit':
                        from scipy.optimize import curve_fit
                        popt, _ = curve_fit(sine_func, power_range, y_data, p0=p0, bounds=(bounds_min, bounds_max), maxfev = 10000)
                    
                    # A, B, C, D, E, F = popt
                    A, B, C, D, E = popt

                    #period = 2 * np.pi / np.abs(B)
                    period = B
                    periods.append(period)

                    if verbose:
                        print("Coeffs:")
                        print(popt)
                    
                    if plot:
                        # Plot data points and fit
                        line, = ax.plot(power_range, sine_func(power_range, *popt), '-', label=f'Out {i} (T={period:.3f}W)')
                        ax.plot(power_range, y_data, 'o', color=line.get_color(), alpha=0.3)
                        
                except Exception as e:
                    if verbose:
                        print(f"    ⚠️ Fit failed for output {i}: {e}")
            
            if plot:
                ax.legend(fontsize='small')
            
            if periods:
                # Filter outliers? Or just mean.
                avg_period = np.mean(periods)
                
                # Update coefficient
                # Period T corresponds to 2pi phase shift
                # So Power = Phase * Coeff => T = 2pi * Coeff => Coeff = T / 2pi
                new_coeff = avg_period / (2 * np.pi)
                
                _xpow.PHASE_CONVERSION[channel.channel - 1] = new_coeff
                
                if verbose:
                    print(f"  ✅ Channel {channel.channel} calibrated: Period={avg_period:.4f} W -> Coeff={new_coeff:.4f} W/rad")
            else:
                if verbose:
                    print(f"  ❌ Channel {channel.channel} calibration failed: no valid fits.")
            
            # Turn off channel before next
            channel.turn_off()
            
        if plot:
            # Hide unused subplots
            for j in range(len(self.channels), len(axs)):
                axs[j].axis('off')
            
            # ========== SECOND FIGURE: PHASE SCAN (0 to 2π) ==========
            if verbose:
                print("📊 Performing phase scan (0 to 2π) for verification...")
            
            phase_range = np.linspace(0, 2*np.pi, samples)
            
            fig2, axs2 = plt.subplots(rows, cols, figsize=(4*cols, 3*rows), constrained_layout=True)
            fig2.suptitle(f"Phase Scan Verification (0 to 2π) - {self.name}")
            if n_channels > 1:
                axs2 = np.atleast_1d(axs2).flatten()
            else:
                axs2 = [axs2]
            
            for idx, channel in enumerate(self.channels):
                # Turn off all channels first
                self.turn_off(verbose=False)
                
                if verbose:
                    print(f"  - Scanning phase for channel {channel.channel}...")
                
                fluxes_phase = []
                
                # Scan phase from 0 to 2π
                for phase in phase_range:
                    channel.set_phase(phase)
                    
                    # Get outputs
                    outs = cred3_object.get_outputs(crop_centers=crop_centers, crop_sizes=crop_sizes)
                    fluxes_phase.append(outs)
                
                fluxes_phase = np.array(fluxes_phase)  # Shape (n_samples, n_outputs)
                
                # Calculate amplitudes to filter out unaffected outputs
                amplitudes_phase = np.ptp(fluxes_phase, axis=0)
                max_amp_phase = np.max(amplitudes_phase) if len(amplitudes_phase) > 0 else 0
                threshold_phase = max_amp_phase / 10.0
                
                # Plot phase scan
                ax2 = axs2[idx]
                ax2.set_title(f"Channel {channel.channel}")
                ax2.set_xlabel("Phase (rad)")
                ax2.set_ylabel("Flux")
                ax2.grid(True)
                
                # Add vertical lines at 0, π, 2π for reference
                ax2.axvline(0, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)
                ax2.axvline(np.pi, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)
                ax2.axvline(2*np.pi, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)
                
                for i in range(fluxes_phase.shape[1]):
                    if amplitudes_phase[i] < threshold_phase:
                        # Skip outputs that are not affected by this shifter
                        continue
                    
                    y_data_phase = fluxes_phase[:, i]
                    ax2.plot(phase_range, y_data_phase, 'o-', label=f'Out {i}', alpha=0.7)
                
                ax2.legend(fontsize='small')
                
                # Turn off channel before next
                channel.turn_off()
            
            # Hide unused subplots in second figure
            for j in range(len(self.channels), len(axs2)):
                axs2[j].axis('off')
            
            plt.show()
            
        if verbose:
            print("✅ Phase calibration completed.")

        return np.array(out_fluxes)

    def characterize(self, dm_object, cred3_object, crop_centers, crop_sizes=10, 
                    phase_samples=51, n_averages=10, plot=True, verbose=True):
        """
        Comprehensive characterization of the architecture with all input/shifter combinations.
        
        This method systematically scans phase responses for:
        - Each single input (1-4)
        - Each pair of inputs (1-2, 1-3, 1-4, 2-3, 2-4, 3-4)
        - Each trio of inputs
        - All 4 inputs simultaneously
        
        For each input configuration, all shifters are scanned from 0 to 2π.
        
        Parameters
        ----------
        dm_object : DM
            Deformable mirror instance to control input blocking/unblocking.
        cred3_object : Cred3
            Camera instance for flux measurements.
        crop_centers : array-like
            Output spot centers for flux extraction.
        crop_sizes : int, optional
            Crop window size. Default is 10.
        phase_samples : int, optional
            Number of phase steps (0 to 2π). Default is 51.
        n_averages : int, optional
            Number of frames to average per phase point. Default is 10.
        plot : bool, optional
            If True, automatically generate plots after characterization. Default is True.
        verbose : bool, optional
            Print progress information. Default is True.
            
        Returns
        -------
        str
            Path to the consolidated characterization_data.npz archive file.
            
        Notes
        -----
        Results are saved to:
        generated/architecture_characterization/<arch_name>/<datetime>/characterization_data.npz
        
        The archive is a single .npz file containing all scans with structured keys:
        - metadata_*: global parameters (arch_name, timestamp, etc.)
        - n{n}_inputs_{i1}_{i2}_shifter{ch}_*: scan data for each configuration
          - phases: array of phase values
          - fluxes: measured output fluxes
          - active_inputs: which inputs were active
          - shifter_channel: which shifter was scanned
        """
        if verbose:
            print(f"🔬 Starting full characterization of {self.name}...")
            print(f"   Inputs: {self.n_inputs}, Outputs: {self.n_outputs}, Shifters: {len(self.channels)}")
        
        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = os.path.join("generated", "architecture_characterization", 
                               self.name.replace(" ", "_"), timestamp)
        os.makedirs(base_dir, exist_ok=True)
        
        if verbose:
            print(f"   Save directory: {base_dir}")
        
        # Phase scan range
        phase_range = np.linspace(0, 2*np.pi, phase_samples)
        
        # Generate all input combinations
        all_inputs = list(range(1, self.n_inputs + 1))
        input_combinations = []
        
        # 1-input: [1], [2], [3], [4]
        for i in all_inputs:
            input_combinations.append(([i], f"input_{i}"))
        
        # 2-inputs: [1,2], [1,3], etc.
        for combo in combinations(all_inputs, 2):
            input_combinations.append((list(combo), f"inputs_{'_'.join(map(str, combo))}"))
        
        # 3-inputs
        for combo in combinations(all_inputs, 3):
            input_combinations.append((list(combo), f"inputs_{'_'.join(map(str, combo))}"))
        
        # 4-inputs (all)
        input_combinations.append((all_inputs, "inputs_all"))
        
        total_scans = len(input_combinations) * len(self.channels)
        scan_count = 0
        
        # Dictionary to store all scan data
        all_scans = {}
        
        # Scan each input combination
        for active_inputs, combo_label in input_combinations:
            n_active = len(active_inputs)
            
            if verbose:
                print(f"\n📊 Scanning with {n_active} input(s) active: {active_inputs}")
            
            # Set DM: turn off all, then turn on selected inputs
            dm_object.off()  # Turn off all inputs
            dm_object.max(active_inputs)  # Turn on selected inputs
            
            # Scan each shifter
            for shifter_idx, shifter in enumerate(self.channels):
                scan_count += 1
                
                if verbose:
                    print(f"  [{scan_count}/{total_scans}] Shifter {shifter.channel} " +
                          f"(TOPA {shifter_idx+1}/{len(self.channels)})")
                
                # Turn off all shifters, prepare to scan this one
                self.turn_off(verbose=False)
                
                fluxes = []
                
                # Scan phase
                for phase in phase_range:
                    shifter.set_phase(phase)
                    
                    # Average multiple frames
                    temp_fluxes = []
                    for _ in range(n_averages):
                        outs = cred3_object.get_outputs(crop_centers=crop_centers, 
                                                       crop_sizes=crop_sizes)
                        temp_fluxes.append(outs)
                    
                    fluxes.append(np.mean(temp_fluxes, axis=0))
                
                fluxes = np.array(fluxes)  # Shape: (phase_samples, n_outputs)
                
                # Fit each output with the sinusoidal model
                # Model: (A + F*x) * sin(B * x + C) + D * x + E
                def sine_func(x, A, B, C, D, E, F):
                    return (A + F * x) * np.sin(B * x + C) + D * x + E
                
                n_outputs = fluxes.shape[1]
                fit_params = np.zeros((n_outputs, 6))  # 6 parameters per output
                fit_success = np.zeros(n_outputs, dtype=bool)
                
                for out_idx in range(n_outputs):
                    try:
                        # Initial guess for parameters
                        flux_mean = np.mean(fluxes[:, out_idx])
                        flux_amp = (np.max(fluxes[:, out_idx]) - np.min(fluxes[:, out_idx])) / 2
                        
                        p0 = [flux_amp, 1.0, 0.0, 0.0, flux_mean, 0.0]  # [A, B, C, D, E, F]
                        
                        # Fit using minimize for better robustness
                        from scipy.optimize import minimize
                        
                        # Define residual function for minimize
                        def residual(params):
                            return np.sum((fluxes[:, out_idx] - sine_func(phase_range, *params))**2)
                        
                        # Use minimize with robust method
                        result = minimize(residual, p0, method='L-BFGS-B', 
                                        options={'maxiter': 10000, 'ftol': 1e-9})
                        
                        if result.success:
                            fit_params[out_idx] = result.x
                            fit_success[out_idx] = True
                        else:
                            fit_params[out_idx] = np.zeros(6)
                            fit_success[out_idx] = False
                    except:
                        # If fit fails, store zeros
                        fit_params[out_idx] = np.zeros(6)
                        fit_success[out_idx] = False
                
                # Store scan in dictionary with unique key
                scan_key = f"n{n_active:d}_inputs_{'_'.join(map(str, active_inputs))}_shifter{shifter.channel:02d}"
                all_scans[scan_key] = {
                    'phases': phase_range,
                    'fluxes': fluxes,
                    'active_inputs': np.array(active_inputs),
                    'shifter_channel': shifter.channel,
                    'shifter_index': shifter_idx,
                    'n_inputs_active': n_active,
                    'fit_params': fit_params,
                    'fit_success': fit_success
                }
                
                if verbose:
                    n_successful = np.sum(fit_success)
                    print(f"     ✅ Scan stored: {scan_key} (fits: {n_successful}/{n_outputs})")
        
        # Turn everything off at the end
        self.turn_off(verbose=False)
        dm_object.max()  # Restore all inputs
        
        # Save consolidated archive
        archive_file = os.path.join(base_dir, "characterization_data.npz")
        
        # Prepare data for saving: flatten nested dict structure
        save_dict = {
            # Global metadata
            'metadata_n_outputs': self.n_outputs,
            'metadata_crop_centers': crop_centers,
            'metadata_crop_sizes': crop_sizes,
            'metadata_n_averages': n_averages,
            'metadata_timestamp': timestamp,
            'metadata_arch_name': self.name,
            'metadata_arch_number': self.number,
            'metadata_scan_keys': list(all_scans.keys())  # Index of all scans
        }
        
        # Add each scan's data with prefixed keys
        for scan_key, scan_data in all_scans.items():
            for data_key, data_value in scan_data.items():
                save_dict[f"{scan_key}_{data_key}"] = data_value
        
        np.savez(archive_file, **save_dict)
        
        if verbose:
            print(f"\n✅ Characterization complete!")
            print(f"   Total scans: {scan_count}")
            print(f"   Consolidated archive: {archive_file}")
        
        # Automatically plot results if requested
        if plot:
            if verbose:
                print(f"\n📊 Generating plots...")
            self.plot_characterization(archive_file)
        
        return archive_file

    @staticmethod
    def plot_characterization(archive_path, output_dir=None):
        """
        Load and plot characterization results from a consolidated archive.
        
        Creates separate plots for each number of inputs (1, 2, 3, 4), with:
        - Rows: different shifters
        - Columns: different input combinations for that input count
        - Each subplot shows fitted sinusoidal responses for all outputs
        
        Parameters
        ----------
        archive_path : str
            Path to the consolidated characterization_data.npz file.
        output_dir : str, optional
            Directory to save plots. If None, uses the parent directory of archive_path.
            
        Returns
        -------
        dict
            Dictionary mapping n_inputs -> figure object.
            
        Examples
        --------
        >>> arch = Arch(6)
        >>> # ... run characterization ...
        >>> Arch.plot_characterization("generated/.../characterization_data.npz")
        """
        if output_dir is None:
            output_dir = os.path.dirname(archive_path)
        
        # Load consolidated archive
        if not os.path.exists(archive_path):
            print(f"❌ Archive not found: {archive_path}")
            return {}
        
        data = np.load(archive_path)
        
        # Extract metadata
        scan_keys = data['metadata_scan_keys']
        arch_name = str(data['metadata_arch_name'])
        timestamp = str(data['metadata_timestamp'])
        
        # Fitting function
        def sine_func(x, A, B, C, D, E, F):
            return (A + F * x) * np.sin(B * x + C) + D * x + E
        
        # Organize scans by: n_inputs -> shifter_ch -> [list of scans with different input combos]
        # First, collect all data
        scan_structure = {}
        shifter_channels = set()
        
        for scan_key in scan_keys:
            shifter_ch = int(data[f"{scan_key}_shifter_channel"])
            n_inputs = int(data[f"{scan_key}_n_inputs_active"])
            active_inputs = tuple(data[f"{scan_key}_active_inputs"])
            
            shifter_channels.add(shifter_ch)
            
            if n_inputs not in scan_structure:
                scan_structure[n_inputs] = {}
            
            if shifter_ch not in scan_structure[n_inputs]:
                scan_structure[n_inputs][shifter_ch] = []
            
            scan_data = {
                'key': scan_key,
                'phases': data[f"{scan_key}_phases"],
                'fluxes': data[f"{scan_key}_fluxes"],
                'active_inputs': active_inputs,
                'shifter_channel': shifter_ch,
                'fit_params': data[f"{scan_key}_fit_params"],
                'fit_success': data[f"{scan_key}_fit_success"]
            }
            
            scan_structure[n_inputs][shifter_ch].append(scan_data)
        
        shifter_channels = sorted(list(shifter_channels))
        figures = {}
        
        # Create one figure per number of inputs
        for n_inputs in sorted(scan_structure.keys()):
            print(f"📊 Plotting {n_inputs}-input configuration(s)...")
            
            # Get all input combinations for this n_inputs
            # (number of columns = number of different combinations)
            input_combos = set()
            for shifter_ch in shifter_channels:
                if shifter_ch in scan_structure[n_inputs]:
                    for scan in scan_structure[n_inputs][shifter_ch]:
                        input_combos.add(scan['active_inputs'])
            
            input_combos = sorted(list(input_combos))
            n_cols = len(input_combos)
            n_rows = len(shifter_channels)
            
            # Find global Y limits for synchronization
            y_min_global, y_max_global = np.inf, -np.inf
            for shifter_ch in shifter_channels:
                if shifter_ch in scan_structure[n_inputs]:
                    for scan in scan_structure[n_inputs][shifter_ch]:
                        fluxes = scan['fluxes']
                        y_min_global = min(y_min_global, np.min(fluxes))
                        y_max_global = max(y_max_global, np.max(fluxes))
            
            # Create figure
            import matplotlib.pyplot as plt
            fig, axs = plt.subplots(n_rows, n_cols, figsize=(5*n_cols, 4*n_rows), 
                                   constrained_layout=True)
            
            fig.suptitle(f"{arch_name} - {n_inputs} Input(s) Active\n{timestamp}", 
                        fontsize=14, fontweight='bold')
            
            # Ensure axs is 2D array
            if n_rows == 1 and n_cols == 1:
                axs = np.array([[axs]])
            elif n_rows == 1:
                axs = axs.reshape(1, -1)
            elif n_cols == 1:
                axs = axs.reshape(-1, 1)
            
            # Plot each cell: row = shifter, col = input combination
            for row_idx, shifter_ch in enumerate(shifter_channels):
                for col_idx, input_combo in enumerate(input_combos):
                    ax = axs[row_idx, col_idx]
                    
                    # Find the scan for this shifter and input combination
                    scan_data = None
                    if shifter_ch in scan_structure[n_inputs]:
                        for scan in scan_structure[n_inputs][shifter_ch]:
                            if scan['active_inputs'] == input_combo:
                                scan_data = scan
                                break
                    
                    if scan_data is None:
                        ax.text(0.5, 0.5, 'No data', ha='center', va='center', 
                               transform=ax.transAxes)
                        ax.set_title(f"Shifter {shifter_ch}\nInputs: {list(input_combo)}")
                        ax.axis('off')
                        continue
                    
                    # Extract data
                    phases = scan_data['phases']
                    fluxes = scan_data['fluxes']
                    active_inputs = scan_data['active_inputs']
                    fit_params = scan_data['fit_params']
                    fit_success = scan_data['fit_success']
                    n_outputs = fluxes.shape[1]
                    
                    # Dense phase array for smooth fit curves
                    phase_dense = np.linspace(0, 2*np.pi, 200)
                    
                    # Plot each output, using fit curve color for the data points when available
                    for out_idx in range(n_outputs):
                        # Plot fit first if successful so we can reuse its color for the points
                        if fit_success[out_idx]:
                            fit_curve = sine_func(phase_dense, *fit_params[out_idx])
                            line, = ax.plot(phase_dense / np.pi, fit_curve, '-', 
                                            linewidth=1.5, alpha=0.8)
                            color = line.get_color()
                            # Plot data points with the same color as the fit
                            ax.plot(phases / np.pi, fluxes[:, out_idx], 'o', 
                                   markersize=3, label=f'Out {out_idx+1}', alpha=0.6, color=color)
                        else:
                            # No fit: plot points with default color
                            ax.plot(phases / np.pi, fluxes[:, out_idx], 'o', 
                                   markersize=3, label=f'Out {out_idx+1}', alpha=0.6)
                    
                    # Labels and title
                    ax.set_xlabel("Phase (π rad)", fontsize=9)
                    if col_idx == 0:
                        ax.set_ylabel("Flux (ADU)", fontsize=9)
                    
                    # Title with shifter and inputs info
                    inputs_str = ','.join(map(str, active_inputs))
                    ax.set_title(f"Shifter {shifter_ch}\nInputs: [{inputs_str}]", 
                                fontsize=10)
                    
                    ax.grid(True, alpha=0.3)
                    if n_outputs <= 4:  # Only show legend if not too many outputs
                        ax.legend(fontsize='x-small', ncol=2, loc='best')
                    
                    # Synchronize Y-axis across all subplots
                    ax.set_ylim(y_min_global, y_max_global)
            
            # Save figure
            fig_filename = f"characterization_{n_inputs}inputs.png"
            fig_path = os.path.join(output_dir, fig_filename)
            fig.savefig(fig_path, dpi=150, bbox_inches='tight')
            print(f"   ✅ Saved: {fig_filename}")
            
            figures[n_inputs] = fig
            
            # ========== CREATE CENTERED VERSION (mean-subtracted) ==========
            print(f"📊 Plotting {n_inputs}-input configuration(s) (mean-subtracted)...")
            
            # Find global maximum amplitude for normalization
            max_amplitude = 0.0
            for shifter_ch in shifter_channels:
                if shifter_ch in scan_structure[n_inputs]:
                    for scan in scan_structure[n_inputs][shifter_ch]:
                        fluxes = scan['fluxes']
                        for out_idx in range(fluxes.shape[1]):
                            centered = fluxes[:, out_idx] - np.mean(fluxes[:, out_idx])
                            amplitude = np.max(np.abs(centered))
                            max_amplitude = max(max_amplitude, amplitude)
            
            # Create centered figure
# Create centered figure
            import matplotlib.pyplot as plt
            fig_centered, axs_centered = plt.subplots(n_rows, n_cols, figsize=(5*n_cols, 4*n_rows), 
                                                      constrained_layout=True)
            
            fig_centered.suptitle(f"{arch_name} - {n_inputs} Input(s) Active (Mean-Subtracted)\n{timestamp}", 
                                 fontsize=14, fontweight='bold')
            
            # Ensure axs_centered is 2D array
            if n_rows == 1 and n_cols == 1:
                axs_centered = np.array([[axs_centered]])
            elif n_rows == 1:
                axs_centered = axs_centered.reshape(1, -1)
            elif n_cols == 1:
                axs_centered = axs_centered.reshape(-1, 1)
            
            # Plot each cell with centered data
            for row_idx, shifter_ch in enumerate(shifter_channels):
                for col_idx, input_combo in enumerate(input_combos):
                    ax = axs_centered[row_idx, col_idx]
                    
                    # Find the scan for this shifter and input combination
                    scan_data = None
                    if shifter_ch in scan_structure[n_inputs]:
                        for scan in scan_structure[n_inputs][shifter_ch]:
                            if scan['active_inputs'] == input_combo:
                                scan_data = scan
                                break
                    
                    if scan_data is None:
                        ax.text(0.5, 0.5, 'No data', ha='center', va='center', 
                               transform=ax.transAxes)
                        ax.set_title(f"Shifter {shifter_ch}\nInputs: {list(input_combo)}")
                        ax.axis('off')
                        continue
                    
                    # Extract data
                    phases = scan_data['phases']
                    fluxes = scan_data['fluxes']
                    active_inputs = scan_data['active_inputs']
                    fit_params = scan_data['fit_params']
                    fit_success = scan_data['fit_success']
                    n_outputs = fluxes.shape[1]
                    
                    # Dense phase array for smooth fit curves
                    phase_dense = np.linspace(0, 2*np.pi, 200)
                    
                    # Plot each output (centered and normalized), matching point color to fit when available
                    for out_idx in range(n_outputs):
                        # Subtract mean and normalize by max amplitude
                        flux_centered = fluxes[:, out_idx] - np.mean(fluxes[:, out_idx])
                        flux_normalized = flux_centered / max_amplitude if max_amplitude > 0 else flux_centered

                        # If fit succeeded, plot fit first to capture its color, then plot points with that color
                        if fit_success[out_idx]:
                            fit_curve = sine_func(phase_dense, *fit_params[out_idx])
                            fit_curve_centered = fit_curve - np.mean(sine_func(phases, *fit_params[out_idx]))
                            fit_curve_normalized = fit_curve_centered / max_amplitude if max_amplitude > 0 else fit_curve_centered
                            line, = ax.plot(phase_dense / np.pi, fit_curve_normalized, '-', 
                                            linewidth=1.5, alpha=0.8)
                            color = line.get_color()
                            ax.plot(phases / np.pi, flux_normalized, 'o', 
                                   markersize=3, label=f'Out {out_idx+1}', alpha=0.6, color=color)
                        else:
                            # No fit: plot normalized points with default color
                            ax.plot(phases / np.pi, flux_normalized, 'o', 
                                   markersize=3, label=f'Out {out_idx+1}', alpha=0.6)
                    
                    # Labels and title
                    ax.set_xlabel("Phase (π rad)", fontsize=9)
                    if col_idx == 0:
                        ax.set_ylabel("Normalized Flux", fontsize=9)
                    
                    # Title with shifter and inputs info
                    inputs_str = ','.join(map(str, active_inputs))
                    ax.set_title(f"Shifter {shifter_ch}\nInputs: [{inputs_str}]", 
                                fontsize=10)
                    
                    ax.grid(True, alpha=0.3)
                    if n_outputs <= 4:  # Only show legend if not too many outputs
                        ax.legend(fontsize='x-small', ncol=2, loc='best')
                    
                    # Set Y-axis limits to [-1, 1]
                    ax.set_ylim(-1.1, 1.1)
                    
                    # Add horizontal line at y=0
                    ax.axhline(0, color='k', linestyle='--', linewidth=0.5, alpha=0.3)
            
            # Save centered figure
            fig_centered_filename = f"characterization_{n_inputs}inputs_centered.png"
            fig_centered_path = os.path.join(output_dir, fig_centered_filename)
            fig_centered.savefig(fig_centered_path, dpi=150, bbox_inches='tight')
            print(f"   ✅ Saved: {fig_centered_filename}")
            
            figures[f"{n_inputs}_centered"] = fig_centered
        
        print(f"✅ Plotting complete. Figures saved to: {output_dir}")
        return figures

class Chip:
    """
    Factory class to return the active Architecture based on configuration.
    This acts as a proxy to the Singleton instance of the active Arch.
    """
    def __new__(cls):
        return get_chip()

def get_chip() -> _Arch:
    """
    Factory function to return the active Architecture instance based on configuration.
    
    Returns
    -------
    ArchN
        Singleton instance of the active architecture.
    """
    import phobos
    import importlib
    
    arch_num = phobos.config.hardware.photonic_chip.arch
    
    # Import the specific architecture module
    # Assumes file naming convention: phobos.classes.archs.arch_N
    module_name = f"phobos.classes.archs.arch_{arch_num}"
    class_name = f"Arch{arch_num}"
    
    try:
        module = importlib.import_module(module_name)
        ArchClass = getattr(module, class_name)
        return ArchClass()
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Could not load architecture {arch_num} ({module_name}.{class_name}): {e}")