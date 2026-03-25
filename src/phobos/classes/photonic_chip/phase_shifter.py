# External imports
import numpy as np
import time
import re
import warnings
from datetime import datetime
import os
from itertools import combinations

# Internal imports
from ... import SANDBOX_MODE
from ... import serial
from ..config import Config
from .xpow import XPOW

MAX_VOLTAGE = 30  # V
MAX_CURRENT = 300  # mA

# Conversion factors (fixed, hardware-dependent)
# To convert user values (mA, V) to 16-bit DAC values
CUR_CONVERSION = 65535 / 300  # DAC units per mA
VOLT_CONVERSION = 65535 / 40  # DAC units per V

class PhaseShifter:
    """
    Represents a single channel on the photonic chip.
    
    Provides an intuitive interface for controlling individual channels.
    PhaseShifter instances are independent and access the XPOW controller directly.
    
    Parameters
    ----------
    channel: int
        Absolute channel number (1-40) on the XPOW controller.
        
    Attributes
    ----------
    channel : int
        The absolute channel number.
    power_dac_factor: float, optional
        Digital to Analog Conversion factor for power. Auto-calibrated on first use.
    phase_factor: float, optional
        Power-to-phase conversion factor in W/rad. Auto-calibrated on first use.
        
    Examples
    --------
    >>> ch17 = PhaseShifter(17)
    >>> ch17.set_voltage(2.5)
    >>> current = ch17.get_current()
    """
    
    _instances = {}

    # Constructors ------------------------------------------------------------

    def __new__(cls, channel: int, *args, **kwargs):

        # Check if channel is valid
        if not (1 <= channel <= XPOW().N_CHANNELS):
             raise ValueError(f"❌ Invalid channel number {channel}. Must be between 1 and {XPOW().N_CHANNELS}.")
             
        # Return cached instance if it exists
        if channel not in cls._instances:
            cls._instances[channel] = super(PhaseShifter, cls).__new__(cls)

        return cls._instances[channel]

    def __init__(self, channel: int):

        # If already initialized (from cache), skip
        if hasattr(self, 'channel'):
            return

        self.channel = channel
        self.power_dac_factor = None # Digital to Analog Conversion factor (for calibration)
        self.phase_factor = None # W/rad (initial guess: 0.6 / (2 * np.pi), can be calibrated)

    # Setter methods ----------------------------------------------------------
        
    def set_current(self, current: float, verbose: bool = False) -> None:
        """
        Set current for this channel.
        
        Parameters
        ----------
        current : float
            Target current in mA.
        verbose : bool, optional
            If True, print command details. Default is False.
        """
        current = max(0, min(MAX_CURRENT, current))
        current_value = current * CUR_CONVERSION
        XPOW().send_command(f"CH:{self.channel}:CUR:{int(current_value)}", verbose=verbose, output=False)
        time.sleep(Config().get('photonic_chip.stabilization_time', 0.001))
        
    def set_voltage(self, voltage: float, verbose: bool = False) -> None:
        """
        Set voltage for this channel.
        
        Parameters
        ----------
        voltage : float
            Target voltage in V.
        verbose : bool, optional
            If True, print command details. Default is False.
        """ 
        voltage = max(0, min(MAX_VOLTAGE, voltage))
        voltage_value = voltage * VOLT_CONVERSION
        XPOW().send_command(f"CH:{self.channel}:VOLT:{int(voltage_value)}", verbose=verbose, output=False)
        time.sleep(Config().get('photonic_chip.stabilization_time', 0.001))
    
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
        a 2-point measurement (1V and 30V at 300mA). 
        See PhaseShifter.power_dac_calibration() documentation for more details.
        
        Examples
        --------
        >>> ch = PhaseShifter(17)
        >>> ch.set_power(0.6)  # Set to 0.6 W (auto-calibrates if needed)
        """
        
        # Auto-calibrate if not done yet
        if self.power_dac_factor is None:
            if verbose:
                print(f"🔧 Auto-calibrating channel {self.channel}...")
            self.power_dac_factor = self.power_dac_calibration(verbose=verbose)
        
        # Set fixed current at 300 mA
        self.set_current(300.0, verbose=verbose)
        
        # Compute voltage from power using the calibrated slope
        # P = slope * V * I  =>  V = sqrt(P / (slope))
        # I = 0.3 A (300 mA converted to amperes)
        voltage = np.sqrt(power / self.power_dac_factor)
        
        # Apply voltage
        self.set_voltage(voltage, verbose=verbose)
        time.sleep(Config().get('photonic_chip.stabilization_time', 0.001))
        
        if verbose:
            print(f"🔧 Channel {self.channel}: power={power:.3f} W → voltage={voltage:.3f} V @ 300 mA")

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

        Returns
        -------
        tuple of (float, float)
            A tuple containing:
            - power : float
                The computed optical power in watts (W) needed to achieve the target phase.
            - read_power : float
                The actual measured optical power applied to the channel in watts (W).
            
        Notes
        -----
        The power is computed as: phase * self.phase_factor
        where self.phase_factor is the phase-to-power coefficient in W/rad.
        This coefficient can be calibrated using Arch.phase_calibration().
        """
        # Compute power needed for the desired phase

        phase_factor = self.phase_factor
        if phase_factor is None:
            warnings.warn(
                f"Phase factor not set for channel {self.channel}. Using default phase_factor=1.0. "
                "Please calibrate using Arch.phase_calibration().",
                UserWarning,
                stacklevel=2
            )
            phase_factor = 1.0  # Default guess if not calibrated

        power = (phase % (2*np.pi)) * phase_factor

        # Apply the power
        self.set_power(power, verbose=verbose)

        # Read the applied power
        read_power = self.get_power(verbose=verbose)
        
        if verbose:
            print(f"🔧 Channel {self.channel}: phase={phase:.3f} rad → power={power:.3f} W")

        return power, read_power

    # Getter methods ----------------------------------------------------------
        
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
        res = XPOW().send_command(f"CH:{self.channel}:VAL?", verbose=verbose)
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
        res = XPOW().send_command(f"CH:{self.channel}:VAL?", verbose=verbose)
        match = re.search(r'=\s*([\d\.]+)V,\s*([\d\.]+)mA', res)
        if match:
            return float(match.group(1))
        else:
            raise ValueError(f"❌ Unable to parse voltage from response: {res}")
    
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
        The phase is computed as: power / self.phase_factor
        This assumes the power-to-phase relationship is linear.
        """
        power = self.get_power(verbose=verbose)

        phase_factor = self.phase_factor
        if phase_factor is None:
            warnings.warn(
                f"Phase factor not set for channel {self.channel}. Using default phase_factor=1.0. "
                "Please calibrate using Arch.phase_calibration().",
                UserWarning,
                stacklevel=2
            )
            phase_factor = 1.0  # Default guess if not calibrated

        phase = power / phase_factor

        if verbose:
            print(f"📊 Channel {self.channel}: power={power:.3f} W → phase={phase:.3f} rad")
        
        return phase

    # Calbiration -------------------------------------------------------------
    
    def power_dac_calibration(self, verbose: bool = False, plot: bool = False) -> float:
        """
        Calibrate power correction coefficient for this channel using 2-point measurement.
        
        The TOPA electric cricuit can be simplified as a simple R circuit.
        The coefficient to measure is the invert of the resistance R and
        the internal conversions of the driver between the requested voltage
        and the actual output voltage.

        All in all, the relationship between the requested power and the applied voltage is:
            - P = $\alpha \cdot V²$
            - $\alpha = coeff_{XPOW} / R$, as there is a linear relationship between the requested and the applied voltages.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print calibration details. Default is False.
        plot : bool, optional
            If True, display before/after calibration comparison plots. Default is False.

        Returns
        -------
        float
            The calibrated slope coefficient for power correction.

        Notes
        -----
        The calibration process:
        1. Set current to 300 mA
        2. Measure intensity at V = 1V
        3. Measure intensity at V = 30V
        4. Compute $\alpha$ from: $\alpha$ = (I2 - I1) / (V2 - V1)
        5. Store $\alpha$ in POWER_CORRECTION[channel]
        
        Thus, requested power is converted into applied voltage with: $V_{applied} = \sqrt{P_{requested} / \alpha}$.
        
       
        Examples
        --------
        >>> ch = PhaseShifter(17)
        >>> ch.power_dac_calibration(verbose=True)
        >>> ch.set_power(0.6)  # Now uses calibrated coefficient
        """

        if verbose:
            print(f"🔧 Calibrating channel {self.channel} using 2-point measurement...")

        # Reset power correction before calibration
        self.power_dac_factor = 1.0
        
        # ========== BEFORE CALIBRATION SCANS ==========

        if plot:
            import matplotlib.pyplot as plt
            
            # Current scan (before)
            self.set_voltage(1.0, verbose=verbose)
            i_ramp = np.linspace(0, 30, 20)  # mA
            i_meas_i_before = []
            v_meas_i_before = []
            p_meas_i_before = []
            for i in i_ramp:
                self.set_current(i, verbose=False)
                i_meas_i_before.append(self.get_current(verbose=False))
                v_meas_i_before.append(self.get_voltage(verbose=False))
                p_meas_i_before.append(self.get_power(verbose=False))

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
        self.power_dac_factor = slope
        
        if verbose:
            print(f"✅ Channel {self.channel} calibrated: slope={slope:.6f}")
        
        # ========== AFTER CALIBRATION SCANS ==========

        if plot:
            # Current scan (after)
            self.set_voltage(1.0, verbose=verbose)
            i_meas_i_after = []
            v_meas_i_after = []
            p_meas_i_after = []
            for i in i_ramp:
                self.set_current(i, verbose=False)
                i_meas_i_after.append(self.get_current(verbose=False))
                v_meas_i_after.append(self.get_voltage(verbose=False))
                p_meas_i_after.append(self.get_power(verbose=False))
            
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
            axs[0, 0].plot(i_ramp, i_meas_i_before, 'o-', label='Before', alpha=0.7)
            axs[0, 0].plot(i_ramp, i_meas_i_after, 's-', label='After', alpha=0.7)
            axs[0, 0].set_xlabel('Set Current (mA)')
            axs[0, 0].set_ylabel('Measured Current (mA)')
            axs[0, 0].set_title('Current Scan - Current')
            axs[0, 0].grid(True)
            axs[0, 0].legend()
            
            axs[0, 1].plot(i_ramp, v_meas_i_before, 'o-', label='Before', alpha=0.7)
            axs[0, 1].plot(i_ramp, v_meas_i_after, 's-', label='After', alpha=0.7)
            axs[0, 1].set_xlabel('Set Current (mA)')
            axs[0, 1].set_ylabel('Measured Voltage (V)')
            axs[0, 1].set_title('Current Scan - Voltage')
            axs[0, 1].grid(True)
            axs[0, 1].legend()
            
            axs[0, 2].plot(i_ramp, p_meas_i_before, 'o-', label='Before', alpha=0.7)
            axs[0, 2].plot(i_ramp, p_meas_i_after, 's-', label='After', alpha=0.7)
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

        return slope
    
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