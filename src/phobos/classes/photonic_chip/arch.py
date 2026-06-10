# External imports
import numpy as np
import time
import re
import warnings
from datetime import datetime
import os
from itertools import combinations
from scipy.optimize import curve_fit, minimize
import matplotlib.pyplot as plt

from ...utils.singleton import Singleton
from .phase_shifter import PhaseShifter
from .xpow import XPOW
from ..deformable_mirror import DM
from ..cred3 import Cred3
from ..config import Config

class Chip:
    """
    Factory class to return the active Architecture based on configuration.
    This acts as a proxy to the Singleton instance of the active Arch.
    """
    def __new__(cls):
        return get_chip()

def get_chip() -> '_Arch':
    """
    Factory function to return the active Architecture instance based on configuration.
    
    Returns
    -------
    ArchN
        Singleton instance of the active architecture.
    """
    import phobos
    import importlib
    
    arch_num = phobos.config.get('photonic_chip.arch')
    
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
    shifters : list[PhaseShifter]
        List of PhaseShifter instances (indexed from 0).
    """

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
        
        # Create channel objects (list indexed from 0)
        self.shifters = [PhaseShifter(channel_num) for channel_num in self.topas]

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
        if not (1 <= topa_index <= len(self.shifters)):
            raise IndexError(f"❌ TOPA index {topa_index} not available for architecture {self.number}. Available indices: 1-{len(self.shifters)}")
        return self.shifters[topa_index - 1]
    
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
        if len(currents) != len(self.shifters):
            raise ValueError(f"❌ Expected {len(self.shifters)} current values, got {len(currents)}")
        
        for shifter, current in zip(self.shifters, currents):
            shifter.set_current(current, verbose=verbose)
    
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
        if len(voltages) != len(self.shifters):
            raise ValueError(f"❌ Expected {len(self.shifters)} voltage values, got {len(voltages)}")
        
        for shifter, voltage in zip(self.shifters, voltages):
            shifter.set_voltage(voltage, verbose=verbose)
    
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
        return np.array([shifter.get_current(verbose=verbose) for shifter in self.shifters])
    
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
        return np.array([shifter.get_voltage(verbose=verbose) for shifter in self.shifters])
    
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
        if len(powers) != len(self.shifters):
            raise ValueError(f"❌ Expected {len(self.shifters)} power values, got {len(powers)}")
        
        for shifter, power in zip(self.shifters, powers):
            shifter.set_power(power, verbose=verbose)
    
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
        return np.array([shifter.get_power(verbose=verbose) for shifter in self.shifters])
    
    def turn_off(self, verbose: bool = False):
        """
        Set voltage and current to zero on all TOPAs in this chip only.
        
        Parameters
        ----------
        verbose : bool, optional
            If True, print shutdown commands. Default is False.
            
        Notes
        -----
        This method only affects the shifters used by this chip architecture.
        To turn off all 40 XPOW shifters, use XPOWController.turn_off().
        
        Examples
        --------
        >>> arch = Arch6()  # 4 shifters: 17, 18, 19, 20
        >>> arch.turn_off()  # Only turns off shifters 17-20
        """
        for shifter in self.shifters:
            shifter.turn_off(verbose=verbose)

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

        Returns
        -------
        np.ndarray
            Array of shape (n_shifters, 2) containing theoretical and applied powers 
            for each shifter. Each row is [power_theoretical, power_applied] in watts (W).            
            
        Raises
        ------
        ValueError
            If length of phases doesn't match number of TOPAs.
            
        Examples
        --------
        >>> arch = Arch6()  # 4 TOPAs
        >>> arch.set_phases([0.0, np.pi/4, np.pi/2, np.pi])
        """
        phases = np.asarray(phases)
        if len(phases) != len(self.shifters):
            raise ValueError(f"❌ Expected {len(self.shifters)} phase values, got {len(phases)}")

        powers = []
        for shifter, phase in zip(self.shifters, phases):
            p_th, p_appl = shifter.set_phase(phase, verbose=verbose)
            powers.append([p_th, p_appl])

        powers = np.array(powers)
        return powers

    def set_phases2(self, phases, zero_points, verbose: bool = False):
        """
        Set phase shifts for all TOPAs in this chip.
        
        Parameters
        ----------
        phases : array-like
            Array of target phase shifts in radians (one per TOPA).
            Length must match number of TOPAs in architecture.
        zero_points : array-like
            Power (in W) corresponding to the reference phase.
            Shape must be (N,2), where N is the number of TOPAs in architecture.
            First column is the ID of the channel, 2nd column is the zero-point in W.
        verbose : bool, optional
            If True, print command details. Default is False.

        Returns
        -------
        np.ndarray
            Array of shape (n_shifters, 2) containing theoretical and applied powers 
            for each shifter. Each row is [power_theoretical, power_applied] in watts (W).            
            
        Raises
        ------
        ValueError
            If length of phases doesn't match number of TOPAs.
        """
        phases = np.asarray(phases)
        if len(phases) != len(self.shifters):
            raise ValueError(f"❌ Expected {len(self.shifters)} phase values, got {len(phases)}")

        powers = []
        for shifter, phase in zip(self.shifters, phases):
            zp = zero_points[:,1][zero_points[:,0] == shifter.channel]
            p_th, p_appl = shifter.set_phase2(phase, zp[0], verbose=verbose)
            powers.append([p_th, p_appl])

        powers = np.array(powers)
        return powers
    
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
        >>> arch = Arch6()
        >>> phases = arch.get_phases()
        >>> print(phases)  # [0.0, 0.785, 1.571, 3.142]
        """
        return np.array([shifter.get_phase(verbose=verbose) for shifter in self.shifters])
    
    def dac_calibration(self, plot: bool = False, verbose: bool = False):
        """
        Calibrate DAC power correction coefficients for all shifters in this architecture.
        
        This method performs 2-point power measurements on each TOPA shifter to compute
        the slope coefficients used for accurate power control. Only shifters used by
        this specific architecture are calibrated, leaving other XPOW shifters unchanged.
        
        Parameters
        ----------
        plot : bool, optional
            If True, display calibration comparison plots for each shifter. Default is False.
        verbose : bool, optional
            If True, print calibration details for each shifter. Default is False.
            
        Notes
        -----
        Only calibrates TOPA shifters in self.topas (the shifters used by this architecture).
        For calibrating all 40 XPOW shifters, use :meth:`XPOW.dac_calibration`.
        For a single shifter, use :meth:`PhaseShifter.dac_calibration`.
        
        Examples
        --------
        >>> arch = Arch6()
        >>> arch.dac_calibration(verbose=True)  # Calibrate only Arch6's 4 TOPAs
        """
        if verbose:
            print(f"🔧 Calibrating DAC for {len(self.shifters)} shifters in {self.name}...")
        
        for shifter in self.shifters:
            shifter.power_dac_calibration(plot=plot, verbose=verbose)
        
        if verbose:
            print(f"✅ DAC calibration completed for {self.name} (shifters {list(self.topas)}).")
    
    def phase_calibration(self, samples: int = 100, plot: bool = False, verbose: bool = False, return_metadata: bool = False, path = None, crop_mode = 'centers', nroi = 10):
        """
        Calibrate phase-to-power conversion coefficients for all shifters in this chip.
        
        This method scans each shifter individually from 0 to 1W, measures the output flux
        using Cred3 camera, fits a sinusoid to the response, and
        updates the PHASE_CONVERSION coefficient based on the measured period.
        
        Parameters
        ----------
        samples : int
            Number of power steps for the scan. Default is 100.
        plot : bool, optional
            If True, plot the fitted curves. Default is False.
        verbose : bool, optional
            If True, print calibration details. Default is False.
        path : Pathlib object, optional
            If not None, save the figure in 'path'
        crop_mode : str, optional
            The crop mode to use for the Cred3 outputs: 'centers' or 'rectangles_integrated'. Default is 'centers'.
        nroi : int, optional
            The number of regions of interest (ROIs) to use for the Cred3 outputs. Default is 10.

        Returns
        -------
        np.ndarray
            Array of measured output fluxes for each shifter during the scan.
        dict, optional
            If return_metadata is True, also returns a dict with metadata including the following keys:
            - "figure1": The calibration plot figure (if plot=True)
            - "figure2": The phase scan verification plot figure (if plot=True)
        """

        power_range = np.linspace(0, 1, samples) # Power from 0 to 1W
    
        def sine_func(x, A, B, C, D, E):
            return A * np.sin(2*np.pi/B * x + C) + D * x + E
            
        if verbose:
            print(f"🔧 Calibrating phase for {len(self.shifters)} shifters...")
            
        if plot:
            # Calculate grid size for subplots based on number of shifters
            n_shifters = len(self.shifters)
            cols = int(np.ceil(np.sqrt(n_shifters)))
            rows = int(np.ceil(n_shifters / cols))
            import matplotlib.pyplot as plt
            fig, axs = plt.subplots(rows, cols, figsize=(4*cols, 3*rows), constrained_layout=True)
            fig.suptitle(f"Phase Calibration - {self.name}")
            if n_shifters > 1:
                axs = np.atleast_1d(axs).flatten()
            else:
                axs = [axs]

        shifter_diag_fluxes = []
        calib_coeffs = []

        for idx, shifter in enumerate(self.shifters):
            # Turn off all shifters first
            self.turn_off(verbose=verbose)

            # if verbose:
            print(f"  - Scanning shifter {shifter.channel}...")
            fluxes = []
            
            # Scan power
            for p in power_range:
                shifter.set_power(p)
                
                # Get outputs
                outs = Cred3().get_outputs(crop_mode=crop_mode)[:nroi]
                fluxes.append(outs)
            
            fluxes = np.array(fluxes) # Shape (n_samples, n_outputs)
            shifter_diag_fluxes.append(fluxes)
            
            # Calculate amplitudes to filter out unaffected outputs
            amplitudes = np.ptp(fluxes, axis=0)
            max_amp = np.max(amplitudes) if len(amplitudes) > 0 else 0
            threshold = max_amp / 10.0
            
            # Fit each output
            periods = []
            
            n_outputs = fluxes.shape[1]
            
            if plot:
                ax = axs[idx]
                ax.set_title(f"Shifter {shifter.channel}")
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

                p0 = [(np.max(y_data)-np.min(y_data))/2, 0.6, 0, 0, np.mean(y_data)]

                bounds_min = [0,      0.5,-np.pi,-(np.max(y_data)-np.min(y_data))/(power_range.max()-power_range.min()),-np.inf]
                bounds_max = [np.inf, 1.2  , np.pi, (np.max(y_data)-np.min(y_data))/(power_range.max()-power_range.min()), np.inf]
                
                try:

                    method = 'minimize'

                    if method == 'minimize':
                        from scipy.optimize import minimize
                        
                        # Define residual function for minimize
                        def residual(params):
                            return np.sum((y_data - sine_func(power_range, *params))**2)
                        
                        # Use minimize with robust method
                        result = minimize(residual, p0, bounds=np.array((bounds_min, bounds_max)).T, options={'maxiter':50000})
                        popt = result.x

                    elif method == 'curve_fit':
                        from scipy.optimize import curve_fit
                        popt, _ = curve_fit(sine_func, power_range, y_data, p0=p0, bounds=(bounds_min, bounds_max), maxfev = 50000)
                    
                    # A, B, C, D, E, F = popt
                    A, B, C, D, E = popt

                    #period = 2 * np.pi / np.abs(B)
                    period = B
                    periods.append(period)
                    
                    if plot:
                        # Plot data points and fit
                        line, = ax.plot(power_range, sine_func(power_range, *popt), '-', label=f'Out {i} (T={period:.3f}W)')
                        ax.plot(power_range, y_data, 'o', color=line.get_color(), alpha=0.3)
                        
                except Exception as e:
                    # if verbose:
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
                
                shifter.phase_factor = new_coeff
                
                # if verbose:
                print(f"  ✅ Shifter {shifter.channel} calibrated: Period={avg_period:.4f} W -> Coeff={new_coeff:.4f} W/rad")

                new_coeff = avg_period / (2 * np.pi)
                calib_coeffs.append([shifter.channel, avg_period, new_coeff])
            else:
                # if verbose:
                print(f"  ❌ Shifter {shifter.channel} calibration failed: no valid fits.")

            # Turn off channel before next
            shifter.turn_off()

        if  plot and (path is not None):
            fig.savefig(path / f"chip_scans_plot_{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}.png", dpi=150)

        calib_coeffs = np.array(calib_coeffs)
        shifter_diag_fluxes = np.array(shifter_diag_fluxes)

        if plot:
            # Hide unused subplots
            for j in range(len(self.shifters), len(axs)):
                axs[j].axis('off')
            
            # ========== SECOND FIGURE: PHASE SCAN (0 to 2π) ==========
            # if verbose:
            #     print("📊 Performing phase scan (0 to 2π) for verification...")
            
            # phase_range = np.linspace(-2*np.pi, 2*np.pi, samples)
            
            # fig2, axs2 = plt.subplots(rows, cols, figsize=(4*cols, 3*rows), constrained_layout=True)
            # fig2.suptitle(f"Phase Scan Verification (0 to 2π) - {self.name}")
            # if n_shifters > 1:
            #     axs2 = np.atleast_1d(axs2).flatten()
            # else:
            #     axs2 = [axs2]
            
            # for idx, shifter in enumerate(self.shifters):
            #     # Turn off all shifters first
            #     self.turn_off(verbose=False)
                
            #     if verbose:
            #         print(f"  - Scanning phase for shifter {shifter.channel}...")
                
            #     fluxes_phase = []
                
            #     # Scan phase from 0 to 2π
            #     for phase in phase_range:
            #         shifter.set_phase(phase)
                    
            #         # Get outputs
            #         outs = Cred3().get_outputs()
            #         fluxes_phase.append(outs)
                
            #     fluxes_phase = np.array(fluxes_phase)  # Shape (n_samples, n_outputs)

            #     # Calculate amplitudes to filter out unaffected outputs
            #     amplitudes_phase = np.ptp(fluxes_phase, axis=0)
            #     max_amp_phase = np.max(amplitudes_phase) if len(amplitudes_phase) > 0 else 0
            #     threshold_phase = max_amp_phase / 10.0
                
            #     # Plot phase scan
            #     ax2 = axs2[idx]
            #     ax2.set_title(f"Shifter {shifter.channel}")
            #     ax2.set_xlabel("Phase (rad)")
            #     ax2.set_ylabel("Flux")
            #     ax2.grid(True)
                
            #     # Add vertical lines at 0, π, 2π for reference
            #     ax2.axvline(0, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)
            #     ax2.axvline(np.pi, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)
            #     ax2.axvline(2*np.pi, color='gray', linestyle='--', alpha=0.3, linewidth=0.8)
                
            #     for i in range(fluxes_phase.shape[1]):
            #         if amplitudes_phase[i] < threshold_phase:
            #             # Skip outputs that are not affected by this shifter
            #             continue
                    
            #         y_data_phase = fluxes_phase[:, i]
            #         ax2.plot(phase_range, y_data_phase, 'o-', label=f'Out {i}', alpha=0.7)
                
            #     ax2.legend(fontsize='small')
                
            #     # Turn off shifter before next
            #     shifter.turn_off()
            
            # # Hide unused subplots in second figure
            # for j in range(len(self.shifters), len(axs2)):
            #     axs2[j].axis('off')
            
            plt.show()
            
        if verbose:
            print("✅ Phase calibration completed.")

        if not return_metadata:
            return calib_coeffs, np.array(shifter_diag_fluxes), power_range
        else:
            return calib_coeffs, np.array(shifter_diag_fluxes), power_range, {
                'figure1' : fig if plot else None,
                'figure2' : fig2 if plot else None,
            }

    def phase_calibration2(self, 
                           samples: int = 100, 
                           niter: int = 3,
                           avg_frames: int = 1,
                           plot: bool = False, 
                           verbose: bool = False, 
                           return_metadata: bool = False):
        """
        Calibrate phase-to-power conversion coefficients for all shifters in this chip.
        
        This method scans each shifter individually from 0 to 1W, measures the output flux
        using Cred3 camera, several times.
        For each shifter, it fits a sinusoid to the average response, and
        updates the PHASE_CONVERSION coefficient based on the measured period.
        
        Parameters
        ----------
        samples : int
            Number of power steps for the scan. Default is 100.
        niter : int
            Number of iterations for the scan of one shifter. Default is 3.
        avg_frames : int
            Number of frames to average for each measurement. Default is 1.
        plot : bool, optional
            If True, plot the fitted curves. Default is False.
        verbose : bool, optional
            If True, print calibration details. Default is False.
        
        Returns
        -------
        np.ndarray
            Array of calibrated phase-to-power conversion coefficients of colums (shifter ID, power period (W), coeff (W/rad))
            Array of measured output fluxes for each shifter during the scan.
        dict, optional
            If return_metadata is True, also returns a dict with metadata including the following keys:
            - "figure1": The calibration plot figure (if plot=True)
            - "figure2": The phase scan verification plot figure (if plot=True)
        """

        power_range = np.linspace(0, 1, samples) # Power from 0 to 1W
    
        def sine(x, A, T, phi):
            return A * np.sin(2*np.pi/T * x + phi)

        def ramp(x, slope, offset):
            return slope * x + offset

        def sine_ramp(x, A, T, phi, slope, offset):
            return sine(x, A, T, phi) + ramp(x, slope, offset)

        if verbose:
            print(f"🔧 Calibrating phase for {len(self.shifters)} shifters...")
        
        if plot:
            n_shifters = len(self.shifters)
            cols = int(np.ceil(np.sqrt(n_shifters)))
            rows = int(np.ceil(n_shifters / cols))
            fig, axs = plt.subplots(rows, cols, figsize=(4*cols, 3*rows), constrained_layout=True)
            fig.suptitle(f"Phase Calibration - {self.name}")
            if n_shifters > 1:
                axs = np.atleast_1d(axs).flatten()
            else:
                axs = [axs]            

        shifter_diag_fluxes = []
        # Iterate over the shifters
        calib_coeffs = []
        for idx, shifter in enumerate(self.shifters):

            # 1. Scan each shifter multiple times
            # For each shifter, we do the scan several times. Each iteration is corrected for the drift.
            no_drift_flux = []
            scan_flux = []
            for iter in range(niter):
                # Turn off all shifters first
                self.turn_off(verbose=False)

                if verbose:
                    print(f"  - Scanning shifter {shifter.channel} {iter+1}/{niter}")
                
                
                # Scan power
                fluxes = []
                for p in power_range:
                    shifter.set_power(p)
                    
                    # Get outputs
                    outs = Cred3().get_outputs(stack=avg_frames)
                    fluxes.append(outs[:self.n_outputs])
                
                shifter.set_power(0)
                fluxes = np.array(fluxes) # Shape (n_samples, n_outputs)

                # Calculate amplitudes to filter out unaffected outputs
                amplitudes = np.ptp(fluxes, axis=0)
                max_amp = np.max(amplitudes) if len(amplitudes) > 0 else 0
                threshold = max_amp / 10.0

                # Correct ramp drift on each output
                if verbose:
                    print('Correcting drift...')

                no_drift_outputs = []
                periods = [] # For each output
                params = []
                model = sine_ramp
                for i in range(self.n_outputs):
                    if amplitudes[i] < threshold:
                        # Skip outputs that are not affected by this shifter
                        mock = np.nan * np.zeros_like(fluxes[:, i])
                        no_drift_outputs.append(mock)
                        continue

                    y_data = fluxes[:, i]
                    p0 = [(np.max(y_data)-np.min(y_data))/2, 0.6, 0, 0, np.mean(y_data)]

                    bounds_min = [0,      0.5,-np.pi,-(np.max(y_data)-np.min(y_data))/(power_range.max()-power_range.min()),-np.inf]
                    bounds_max = [np.inf, 1.2  , np.pi, (np.max(y_data)-np.min(y_data))/(power_range.max()-power_range.min()), np.inf]

                    try:
                        def residual(params):
                            return np.sum((y_data - model(power_range, *params))**2)
                        result = minimize(residual, p0, bounds=np.array((bounds_min, bounds_max)).T, options={'maxiter':10000})
                        popt = result.x
                        # print('***')
                        # print(p0)
                        # print(popt)
                        # print('---')
                    except RuntimeError as e:
                        plt.figure()
                        plt.plot(power_range, y_data, 'o', label='Data')
                        plt.title(f"Fit failed for output {i}")
                        plt.xlabel("Power (W)")
                        plt.ylabel("Flux")
                        plt.grid()
                        plt.legend()
                        plt.show()
                        raise e                            

                    A, T, phi, slope, offset = popt
                    periods.append(T)
                    params.append(popt)

                    if niter > 1:
                        no_drift_data = y_data - slope * power_range - offset
                    else:
                        no_drift_data = y_data

                    no_drift_outputs.append(no_drift_data)

                no_drift_outputs = np.array(no_drift_outputs)
                no_drift_outputs = no_drift_outputs.T # Shape (n_samples, n_outputs)
                no_drift_flux.append(no_drift_outputs)
                scan_flux.append(fluxes)

            no_drift_flux = np.array(no_drift_flux) # shape (n_iter, n_samples, n_outputs)
            scan_flux = np.array(scan_flux) # shape (n_iter, n_samples, n_outputs)
            shifter_diag_fluxes.append(scan_flux)

            # 2. Average over the iterations
            no_drift_flux_avg = np.nanmean(no_drift_flux, axis=0) # shape (n_samples, n_outputs)
            no_drift_flux_std = np.nanstd(no_drift_flux, axis=0) # shape (n_samples, n_outputs)

            if niter > 1: # Don't do it if only one iteration
                # 3. Fit a model to the averaged data
                if verbose:
                    print('Phase-to-power calibration...')

                periods = [] # For each output
                params = []
                model = sine
                for i in range(no_drift_flux_avg.shape[1]):
                    y_data = no_drift_flux_avg[:, i]
                    y_std = no_drift_flux_std[:, i] / niter**0.5
                    p0 = [(np.max(y_data)-np.min(y_data))/2, 0.59, 0]

                    bounds_min = [0,      0.5, -np.pi]
                    bounds_max = [np.inf, 1.2  , np.pi]

                    try:
                        def residual(params, sigmas=1):
                                return np.sum((y_data - model(power_range, *params))**2 / sigmas**2)

                        f = lambda x: residual(x, sigmas=y_std)
                        result = minimize(f, p0, bounds=np.array((bounds_min, bounds_max)).T, options={'maxiter':10000})
                        popt = result.x
                    except RuntimeError as e:
                        plt.figure()
                        plt.errorbar(power_range, y_data, yerr=y_std, fmt='o')
                        plt.title(f"Fit failed for output {i} (no drift, avg)")
                        plt.xlabel("Power (W)")
                        plt.ylabel("Flux")
                        plt.grid()
                        plt.legend()
                        plt.show()
                        raise e

                    A, T, phi = popt
                    periods.append(T)
                    params.append(popt)

            avg_period = np.mean(periods)
            # Update coefficient
            # Period T corresponds to 2pi phase shift
            # So Power = Phase * Coeff => T = 2pi * Coeff => Coeff = T / 2pi
            new_coeff = avg_period / (2 * np.pi)

            shifter.phase_factor = new_coeff

            if verbose:
                print(f"  ✅ Shifter {shifter.channel} calibrated: Period={avg_period:.4f} W -> Coeff={new_coeff:.4f} W/rad")

            calib_coeffs.append([shifter.channel, avg_period, new_coeff])

            # Turn off channel before next shifter
            shifter.turn_off()

            # 4. Plot
            if plot:
                ax = axs[idx]
                ax.set_title(f"Shifter {shifter.channel} (Average, drift and offset corrected)")
                ax.set_xlabel("Power (W)")
                ax.set_ylabel("Flux")
                ax.grid(True)

                # Plot data points and fit
                for i in range(no_drift_flux_avg.shape[1]):
                    line, = ax.plot(power_range, model(power_range, *params[i]), '-', label=f'Out {i} (T={periods[i]:.3f}W)')
                    ax.plot(power_range, no_drift_flux_avg[:, i], 'o', color=line.get_color(), alpha=0.3) 


                # Hide unused subplots
                for j in range(len(self.shifters), len(axs)):
                    axs[j].axis('off')

        calib_coeffs = np.array(calib_coeffs)

        if plot:
            plt.show()

        # ========== SECOND FIGURE: PHASE SCAN (0 to 2π) ==========
        if plot:
            if verbose:
                print("📊 Performing phase scan (0 to 2π) for verification...")

            phase_range = np.linspace(-2*np.pi, 2*np.pi, samples)

            fig2, axs2 = plt.subplots(rows, cols, figsize=(4*cols, 3*rows), constrained_layout=True)
            fig2.suptitle(f"Phase Scan Verification (0 to 2π) - {self.name}")
            if n_shifters > 1:
                axs2 = np.atleast_1d(axs2).flatten()
            else:
                axs2 = [axs2]

            for idx, shifter in enumerate(self.shifters):
                # Turn off all shifters first
                self.turn_off(verbose=False)
                
                if verbose:
                    print(f"  - Scanning phase for shifter {shifter.channel}...")
                
                fluxes_phase = []
                
                # Scan phase from 0 to 2π
                for phase in phase_range:
                    shifter.set_phase(phase)
                    
                    # Get outputs
                    outs = Cred3().get_outputs()
                    fluxes_phase.append(outs[:self.n_outputs])
                
                shifter.set_power(0)
                fluxes_phase = np.array(fluxes_phase)  # Shape (n_samples, n_outputs)
                
                # Calculate amplitudes to filter out unaffected outputs
                amplitudes_phase = np.ptp(fluxes_phase, axis=0)
                max_amp_phase = np.max(amplitudes_phase) if len(amplitudes_phase) > 0 else 0
                threshold_phase = max_amp_phase / 10.0
                
                # Plot phase scan
                ax2 = axs2[idx]
                ax2.set_title(f"Shifter {shifter.channel}")
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
                
                # Turn off shifter before next
                shifter.turn_off()
            
            # Hide unused subplots in second figure
            for j in range(len(self.shifters), len(axs2)):
                axs2[j].axis('off')
            
            plt.show()

        if verbose:
            print("✅ Phase calibration completed.")

        if not return_metadata:
            return calib_coeffs, np.array(shifter_diag_fluxes), power_range
        else:
            return calib_coeffs, np.array(shifter_diag_fluxes), power_range, {
                'figure1' : fig if plot else None,
                'figure2' : fig2 if plot else None,
            }