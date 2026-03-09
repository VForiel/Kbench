# External imports
import numpy as np
import time
import re
import warnings
from datetime import datetime
import os
from itertools import combinations

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
        
        for shifter, phase in zip(self.shifters, phases):
            shifter.set_phase(phase, verbose=verbose)
    
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
    
    def phase_calibration(self, samples: int = 100, plot: bool = False, verbose: bool = False):
        """
        Calibrate phase-to-power conversion coefficients for all shifters in this chip.
        
        This method scans each shifter individually from 0 to 1.2W, measures the output flux
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

        out_fluxes = []
        for idx, shifter in enumerate(self.shifters):

            # Turn off all shifters first
            self.turn_off(verbose=verbose)

            if verbose:
                print(f"  - Scanning shifter {shifter.channel}...")
            fluxes = []
            
            # Scan power
            for p in power_range:
                shifter.set_power(p)
                
                # Get outputs
                outs = Cred3().get_outputs()
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
                
                shifter.phase_factor = new_coeff
                
                if verbose:
                    print(f"  ✅ Shifter {shifter.channel} calibrated: Period={avg_period:.4f} W -> Coeff={new_coeff:.4f} W/rad")
            else:
                if verbose:
                    print(f"  ❌ Shifter {shifter.channel} calibration failed: no valid fits.")

            # Turn off channel before next
            shifter.turn_off()

        if plot:
            # Hide unused subplots
            for j in range(len(self.shifters), len(axs)):
                axs[j].axis('off')
            
            # ========== SECOND FIGURE: PHASE SCAN (0 to 2π) ==========
            if verbose:
                print("📊 Performing phase scan (0 to 2π) for verification...")
            
            phase_range = np.linspace(0, 2*np.pi, samples)
            
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
                    fluxes_phase.append(outs)
                
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

        return np.array(out_fluxes)

    def characterize(self, phase_samples=51, n_averages=10, plot=True, verbose=True):
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
            print(f"   Inputs: {self.n_inputs}, Outputs: {self.n_outputs}, Shifters: {len(self.shifters)}")
        
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
        
        total_scans = len(input_combinations) * len(self.shifters)
        scan_count = 0
        
        # Dictionary to store all scan data
        all_scans = {}
        
        # Scan each input combination
        for active_inputs, combo_label in input_combinations:
            n_active = len(active_inputs)
            
            if verbose:
                print(f"\n📊 Scanning with {n_active} input(s) active: {active_inputs}")
            
            # Set DM: turn off all, then turn on selected inputs
            DM().off()  # Turn off all inputs
            DM().flat(active_inputs)  # Turn on selected inputs
            
            # Scan each shifter
            for shifter_idx, shifter in enumerate(self.shifters):
                scan_count += 1
                
                if verbose:
                    print(f"  [{scan_count}/{total_scans}] Shifter {shifter.channel} " +
                          f"(TOPA {shifter_idx+1}/{len(self.shifters)})")
                
                # Turn off all shifters, prepare to scan this one
                self.turn_off(verbose=False)
                
                fluxes = []
                
                # Scan phase
                for phase in phase_range:
                    shifter.set_phase(phase)
                    
                    # Average multiple frames
                    temp_fluxes = []
                    for _ in range(n_averages):
                        outs = Cred3().get_outputs()
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
        DM().flat()  # Restore all inputs
    
        # Prepare data for saving: flatten nested dict structure
        save_dict = {
            # Global metadata
            'metadata_n_outputs': self.n_outputs,
            'metadata_crop_centers': Config().get('cred3.output_centers'),
            'metadata_crop_sizes': Config().get('cred3.output_sizes'),
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
        
        from ...utils import archive
        path = archive.new("MMI Characterization") / "data.npz"
        np.savez(path, **save_dict)
        
        if verbose:
            print(f"\n✅ Characterization complete!")
            print(f"   Total scans: {scan_count}")
            print(f"   Consolidated archive: {path}")
        
        # Automatically plot results if requested
        if plot:
            if verbose:
                print(f"\n📊 Generating plots...")
            self.plot_characterization(path)
        
        return path

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