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