from ..arch import _Arch as Arch
from ....utils import Singleton
import numpy as np
import scipy.optimize

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

class Arch15(Arch, metaclass=Singleton):
    """
    Architecture 15: Mega Kernel Nuller Reconfig (14 shifters, 4 inputs, 7 outputs).
    
    This is the full kernel-nulling architecture with:
    - 4 inputs (controlled via DM)
    - 7 outputs: 1 Bright + 6 Darks + (3 Kernels computed from Darks)
    - 14 phase shifters (TOPAs)
    """
    
    def __init__(self):
        super().__init__(
            name="Mega Kernel Nuller Reconfig",
            id="N2x2-D4",
            n_inputs=4,
            n_outputs=7,
            topas=(6,7,33,34,35,36,37,38,28,27,26,25,39,40),
            number=15
        )
    
    def null_calibration_obs(
        self,
        n: int = 1_000,
        n_averages: int = 10,
        plot: bool = False,
        figsize: tuple = (30, 20),
        save_as=None,
    ):
        """
        Optimize calibration via least squares sampling for Architecture 15.
        
        This method systematically scans phase shifters to optimize the kernel nuller performance:
        1. Maximize bright output (3 configurations)
        2. Maximize dark pairs (1 configuration)
        3. Minimize kernel outputs (3 configurations)
        
        Parameters
        ----------
        n : int, optional
            Number of sampling points for least squares. Default is 1000.
        n_averages : int, optional
            Number of frames to average per phase point. Default is 10.
        plot : bool, optional
            If True, plot the optimization process. Default is False.
        figsize : tuple, optional
            Figure size for plots. Default is (30, 20).
        save_as : str, optional
            Path to save the plot if plot is True. Default is None.
            
        Notes
        -----
        The calibration follows the strategy from the PHISE simulation:
        - Shifters 2, 4, 7 control bright maximization with different input pairs
        - Shifter 8 controls dark pair symmetry
        - Shifters 11, 13, 14 minimize kernel outputs
        - If polychromatic: shifters [1,2], [3,4], [5,7] for achromatic bright control
        
        The method scans each shifter from 0 to 2π, fits a sinusoid,
        and sets the optimal phase for maximum/minimum transmission.
        
        Examples
        --------
        >>> from phobos import Arch15
        >>> 
        >>> arch = Arch15()
        >>> arch.null_calibration_obs(plot=True)
        """
        from ..deformable_mirror import DM
        from ..cred3 import Cred3
        
        dm = DM()
        cred3 = Cred3()
        
        # Get crop centers from config
        if cred3.output_centers is None or len(cred3.output_centers) != 7:
            raise ValueError(f"❌ Architecture 15 expects 7 output spots, got {len(cred3.output_centers) if cred3.output_centers is not None else 0}. Please configure phobos.config.cred3.output_centers")
        
        if plot and plt is not None:
            _, axs = plt.subplots(6, 3, figsize=figsize, constrained_layout=True)
            for i in range(7):
                axs.flatten()[i].set_xlabel("Phase shift (rad)")
                axs.flatten()[i].set_ylabel("Throughput (normalized)")
        
        def maximize_bright(shifter_indices, plt_coords=None):
            """Maximize bright output (output 0) by scanning shifter(s)."""
            if not isinstance(shifter_indices, list):
                shifter_indices = [shifter_indices]
            
            # Get the PhaseShifter objects
            shifters = [self.channels[idx - 1] for idx in shifter_indices]
            
            # If multiple shifters, maintain relative phase
            if len(shifters) > 1:
                initial_phases = [ch.get_phase() for ch in shifters]
                Δφ = initial_phases[1] - initial_phases[0] if len(initial_phases) > 1 else 0
            
            x = np.linspace(0, 2 * np.pi, n)
            y = np.empty(n)
            
            for i in range(n):
                # Set phase for primary shifter
                shifters[0].set_phase(x[i])
                
                # If multiple shifters, maintain phase difference
                if len(shifters) > 1:
                    shifters[1].set_phase(x[i] + Δφ)
                
                # Measure bright output (index 0)
                temp_outs = []
                for _ in range(n_averages):
                    outs = cred3.get_outputs()
                    temp_outs.append(outs[0])  # Bright output
                y[i] = np.mean(temp_outs)
            
            # Normalize
            y = y / np.max(y) if np.max(y) > 0 else y
            
            # Fit sinusoid
            def sin_model(x, x0):
                return (np.sin(x - x0) + 1) / 2 * (np.max(y) - np.min(y)) + np.min(y)
            
            popt = scipy.optimize.minimize(lambda x0: np.sum((y - sin_model(x, x0)) ** 2), x0=[0], method='Nelder-Mead').x
            
            # Set optimal phase (π/2 shift for maximum)
            optimal_phase = np.mod(popt[0] + np.pi / 2, 2 * np.pi)
            shifters[0].set_phase(optimal_phase)
            
            if len(shifters) > 1:
                shifters[1].set_phase(optimal_phase + Δφ)
            
            if plot and plt is not None and plt_coords is not None:
                axs[plt_coords].set_title(f"Bright (shifter {'s' if len(shifter_indices) > 1 else ''} {shifter_indices})")
                axs[plt_coords].scatter(x, y, label='Data', color='tab:blue', s=1)
                axs[plt_coords].plot(x, sin_model(x, *popt), label='Fit', color='tab:orange')
                axs[plt_coords].axvline(x=optimal_phase, color='k', linestyle='--', label='Optimal')
                axs[plt_coords].set_xlabel("Phase shift (rad)")
                axs[plt_coords].set_ylabel("Bright throughput")
                axs[plt_coords].legend()
        
        def minimize_kernel(shifter_idx, kernel_idx, plt_coords=None):
            """Minimize kernel output by scanning a shifter."""
            shifter = self.channels[shifter_idx - 1]
            
            x = np.linspace(0, 2 * np.pi, n)
            y = np.empty(n)
            
            for i in range(n):
                shifter.set_phase(x[i])
                
                # Measure outputs and compute kernel
                temp_outs = []
                for _ in range(n_averages):
                    outs = cred3.get_outputs()
                    # Kernel = |D_{2k-1}|² - |D_{2k}|²
                    # Outputs: [Bright, D1, D2, D3, D4, D5, D6]
                    # Kernels: K1 = D1 - D2, K2 = D3 - D4, K3 = D5 - D6
                    if kernel_idx == 1:
                        kernel = outs[1] - outs[2]
                    elif kernel_idx == 2:
                        kernel = outs[3] - outs[4]
                    else:  # kernel_idx == 3
                        kernel = outs[5] - outs[6]
                    temp_outs.append(np.abs(kernel))
                y[i] = np.mean(temp_outs)
            
            # Normalize
            y = y / np.max(y) if np.max(y) > 0 else y
            
            # Fit sinusoid
            def sin_model(x, x0):
                return (np.sin(x - x0) + 1) / 2 * (np.max(y) - np.min(y)) + np.min(y)
            
            popt = scipy.optimize.minimize(lambda x0: np.sum((y - sin_model(x, x0)) ** 2), x0=[0], method='Nelder-Mead').x
            
            # Set optimal phase (minimum)
            optimal_phase = np.mod(popt[0] + 3*np.pi/2, 2 * np.pi) # Min of sin(x-x0) is at x = x0 + 3pi/2
            shifter.set_phase(optimal_phase)
            
            if plot and plt is not None and plt_coords is not None:
                axs[plt_coords].set_title(f"Kernel {kernel_idx} (shifter {shifter_idx})")
                axs[plt_coords].scatter(x, y, label='Data', color='tab:blue', s=1)
                axs[plt_coords].plot(x, sin_model(x, *popt), label='Fit', color='tab:orange')
                axs[plt_coords].axvline(x=optimal_phase, color='k', linestyle='--', label='Optimal')
                axs[plt_coords].set_xlabel("Phase shift (rad)")
                axs[plt_coords].set_ylabel(f"K{kernel_idx} throughput")
                axs[plt_coords].legend()
        
        def maximize_darks(shifter_idx, dark_indices, plt_coords=None):
            """Maximize sum of dark pair outputs."""
            shifter = self.channels[shifter_idx - 1]
            
            x = np.linspace(0, 2 * np.pi, n)
            y = np.empty(n)
            
            for i in range(n):
                shifter.set_phase(x[i])
                
                # Measure dark pair sum
                temp_outs = []
                for _ in range(n_averages):
                    outs = cred3.get_outputs()
                    # Sum specified dark outputs (1-indexed to 0-indexed)
                    dark_sum = np.sum([outs[d] for d in dark_indices])
                    temp_outs.append(dark_sum)
                y[i] = np.mean(temp_outs)
            
            # Normalize
            y = y / np.max(y) if np.max(y) > 0 else y
            
            # Fit sinusoid
            def sin_model(x, x0):
                return (np.sin(x - x0) + 1) / 2 * (np.max(y) - np.min(y)) + np.min(y)
            
            popt = scipy.optimize.minimize(lambda x0: np.sum((y - sin_model(x, x0)) ** 2), x0=[0], method='Nelder-Mead').x
            
            # Set optimal phase (π/2 shift for maximum)
            optimal_phase = np.mod(popt[0] + np.pi / 2, 2 * np.pi)
            shifter.set_phase(optimal_phase)
            
            if plot and plt is not None and plt_coords is not None:
                axs[plt_coords].set_title(f"Darks {dark_indices} (shifter {shifter_idx})")
                axs[plt_coords].scatter(x, y, label='Data', color='tab:blue', s=1)
                axs[plt_coords].plot(x, sin_model(x, *popt), label='Fit', color='tab:orange')
                axs[plt_coords].axvline(x=optimal_phase, color='k', linestyle='--', label='Optimal')
                axs[plt_coords].set_xlabel("Phase shift (rad)")
                axs[plt_coords].set_ylabel(f"Dark pair throughput")
                axs[plt_coords].legend()
        
        # ============ Calibration sequence ============
        
        print("🔧 Starting Architecture 15 calibration...")
        
        # Bright maximization (single shifters with different input pairs)
        print("  [1/7] Maximizing bright with inputs 1,2 → shifter 2")
        dm.off()
        dm.flat([1, 2])
        maximize_bright(2, plt_coords=(0, 0))
        
        print("  [2/7] Maximizing bright with inputs 3,4 → shifter 4")
        dm.off()
        dm.flat([3, 4])
        maximize_bright(4, plt_coords=(0, 1))
        
        print("  [3/7] Maximizing bright with inputs 1,3 → shifter 7")
        dm.off()
        dm.flat([1, 3])
        maximize_bright(7, plt_coords=(0, 2))
        
        # Darks maximization
        print("  [4/7] Maximizing dark pair [1,2] with inputs 1,4 (inverted) → shifter 8")
        dm.off()
        dm.flat([1, 4])  # Note: In simulation, input 4 is inverted (attenuation=-1)
        maximize_darks(8, [1, 2], plt_coords=(1, 0))
        
        # Kernel minimization (requires all inputs active)
        print("  [5/7] Minimizing kernel 1 with input 1 only → shifter 11")
        dm.off()
        dm.flat([1])
        minimize_kernel(11, 1, plt_coords=(2, 0))
        
        print("  [6/7] Minimizing kernel 2 with input 1 only → shifter 13")
        minimize_kernel(13, 2, plt_coords=(2, 1))
        
        print("  [7/7] Minimizing kernel 3 with input 1 only → shifter 14")
        minimize_kernel(14, 3, plt_coords=(2, 2))
        
        # Polychromatic correction (shifter pairs for achromatic control)
        # This would require additional calibration data
        # Skipped for now as it requires knowing if setup is monochromatic or not
        
        # Restore all inputs
        dm.flat()
        
        if plot and plt is not None:
            axs[1, 1].axis('off')
            axs[1, 2].axis('off')
            
            if save_as:
                plt.savefig(save_as, dpi=150, bbox_inches='tight')
            plt.show()
        
        print("✅ Architecture 15 calibration complete!")

    def null_calibration_gen(
        self,
        beta: float = 0.8,
        verbose: bool = False,
        plot: bool = False,
        figsize: tuple = (10, 10),
        save_as=None,
    ) -> dict:
        """
        Optimize phase shifter offsets to maximize nulling performance using a genetic-like gradient descent.
        
        Adaptation of Context.calibrate_gen from PHISE.
        
        Parameters
        ----------
        beta : float, optional
            Decay factor for the step size (0.5 <= beta < 1). Default is 0.8.
        verbose : bool, optional
            If True, print optimization progress. Default is False.
        plot : bool, optional
            If True, plot the optimization process. Default is False.
        figsize : tuple, optional
            Figure size for plots. Default is (10, 10).
        save_as : str, optional
            Path to save the plot if plot is True. Default is None.
            
        Returns
        -------
        dict
            Dictionary with optimization history (depth, shifters).
        """
        from ..cred3 import Cred3
        
        cred3 = Cred3()

        if beta < 0.5 or beta >= 1:
            raise ValueError("Beta must be in the range [0.5, 1[")
        
        # Initial step size
        ε = 1e-4 # Minimum shift step size in radians
        Δφ = np.pi / 2 # Initial step
        
        # Shifters that contribute to redirecting light to the bright output
        φb = [1, 2, 3, 4, 5, 7]
        
        # Shifters that contribute to the symmetry of the dark outputs
        φk = [6, 8, 9, 10, 11, 12, 13, 14]
        
        # History
        depth_history = []
        shifters_history = []
        
        # Cache current phases to avoid repeated hardware calls
        current_phases = [ch.get_phase() for ch in self.channels]
        
        def get_metrics_from_cam():
            outs = cred3.get_outputs()
            # outs: [Bright, D1, D2, D3, D4, D5, D6]
            b = outs[0]
            
            # Kernels: K1 = D1 - D2, K2 = D3 - D4, K3 = D5 - D6
            k1 = outs[1] - outs[2]
            k2 = outs[3] - outs[4]
            k3 = outs[5] - outs[6]
            
            # Metric for kernel nulling: mean of absolute kernels
            k_metric = (np.abs(k1) + np.abs(k2) + np.abs(k3)) / 3.0
            return b, k_metric
            
        print("🧬 Starting Genetic Calibration...")
        
        iteration_count = 0
        
        while Δφ > ε:
            if verbose:
                print(f"--- Iteration {iteration_count} --- Δφ={Δφ:.2e}")
            
            for i in φb + φk:
                # i is 1-based index
                shifter = self.channels[i - 1]
                
                log = ""
                
                # Measure current state
                b_old, k_old = get_metrics_from_cam()
                
                # Get current phase from cache
                current_phase = current_phases[i - 1]
                
                # Positive step
                shifter.set_phase((current_phase + Δφ) % (2 * np.pi))
                b_pos, k_pos = get_metrics_from_cam()
                
                # Negative step
                shifter.set_phase((current_phase - Δφ) % (2 * np.pi))
                b_neg, k_neg = get_metrics_from_cam()
                
                # Restore original position (for now, will update if better)
                shifter.set_phase(current_phase)
                
                # Metrics for history
                depth = k_old / b_old if b_old > 0 else 0
                depth_history.append(depth)
                shifters_history.append(list(current_phases))
                
                # Decision logic
                updated = False
                
                # Group 1: Maximize Bright
                if i in φb:
                    log += f"Shift {i} Bright: {b_neg:.2e} | {b_old:.2e} | {b_pos:.2e} -> "
                    
                    if b_pos > b_old and b_pos > b_neg:
                        log += " + "
                        new_phase = (current_phase + Δφ) % (2 * np.pi)
                        shifter.set_phase(new_phase)
                        current_phases[i - 1] = new_phase
                        updated = True
                    elif b_neg > b_old and b_neg > b_pos:
                        log += " - "
                        new_phase = (current_phase - Δφ) % (2 * np.pi)
                        shifter.set_phase(new_phase)
                        current_phases[i - 1] = new_phase
                        updated = True
                    else:
                        log += " = "
                
                # Group 2: Minimize Kernel
                else: # i in φk
                    log += f"Shift {i} Kernel: {k_neg:.2e} | {k_old:.2e} | {k_pos:.2e} -> "
                    
                    if k_pos < k_old and k_pos < k_neg:
                        log += " + "
                        new_phase = (current_phase + Δφ) % (2 * np.pi)
                        shifter.set_phase(new_phase)
                        current_phases[i - 1] = new_phase
                        updated = True
                    elif k_neg < k_old and k_neg < k_pos:
                        log += " - "
                        new_phase = (current_phase - Δφ) % (2 * np.pi)
                        shifter.set_phase(new_phase)
                        current_phases[i - 1] = new_phase
                        updated = True
                    else:
                        log += " = "
                        
                if verbose:
                    print(log)
            
            # Decay step size
            Δφ *= beta
            iteration_count += 1
            
        print(f"✅ Genetic calibration complete in {iteration_count} iterations.")
        
        if plot and plt is not None:
            shifters_hist_arr = np.array(shifters_history)
            
            _, axs = plt.subplots(2, 1, figsize=figsize, constrained_layout=True)
            
            axs[0].plot(depth_history)
            axs[0].set_xlabel("Steps")
            axs[0].set_ylabel("Kernel-Null depth (K/B)")
            axs[0].set_yscale("log")
            axs[0].set_title("Performance of the Kernel-Nuller")
            
            for i in range(shifters_hist_arr.shape[1]):
                # Only plot active shifters? Or all? Let's plot all.
                axs[1].plot(shifters_hist_arr[:, i], label=f"Ch {i+1}")
            
            axs[1].set_xlabel("Steps")
            axs[1].set_ylabel("Phase shift (rad)")
            axs[1].set_title("Convergence of phase shifters")
            # axs[1].legend(loc='upper right', bbox_to_anchor=(1,1), fontsize='small', ncol=2)
            
            if save_as:
                plt.savefig(save_as, dpi=150, bbox_inches='tight')
            plt.show()
            
        return {
            "depth": np.array(depth_history),
            "shifters": np.array(shifters_history)
        }

