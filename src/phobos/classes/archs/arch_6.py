from ..photonic_chip import _Arch as Arch
from ..utils import Singleton
import numpy as np
import scipy.optimize

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

class Arch6(Arch, metaclass=Singleton):
    """
    Architecture 6: 4-Port MMI Active (4 shifters, 4 inputs, 4 outputs).
    
    This is a simplified 4x4 MMI architecture with:
    - 4 inputs (controlled via DM)
    - 4 outputs (all potentially used for beam combining)
    - 4 phase shifters (TOPAs: channels 17, 18, 19, 20)
    """
    
    def __init__(self):
        super().__init__(
            name="4-Port MMI Active",
            id="N4x4-T8",
            n_inputs=4,
            n_outputs=4,
            topas=(17,18,19,20),
            number=6
        )
        
        # Matrix model --------------------------------------------------------
        
        # Matrix A (MMI Transfer Function)
        self.A_model = np.array([
            [0.49 * np.exp(1j * -0.10 * np.pi), 0.50 * np.exp(1j * -0.35 * np.pi), 0.50 * np.exp(1j * 0.13 * np.pi), 0.51 * np.exp(1j * -0.21 * np.pi)],
            [0.50 * np.exp(1j * -0.50 * np.pi), 0.49 * np.exp(1j * 0.74 * np.pi), 0.52 * np.exp(1j * 0.21 * np.pi), 0.50 * np.exp(1j * 0.40 * np.pi)],
            [0.50 * np.exp(1j * -0.73 * np.pi), 0.50 * np.exp(1j * -0.50 * np.pi), 0.49 * np.exp(1j * 0.99 * np.pi), 0.50 * np.exp(1j * 0.17 * np.pi)],
            [0.51 * np.exp(1j * 0.89 * np.pi), 0.51 * np.exp(1j * -0.35 * np.pi), 0.49 * np.exp(1j * 0.13 * np.pi), 0.49 * np.exp(1j * 0.79 * np.pi)]
        ])

        # Matrix Cin (Input Crosstalk)
        self.C_model = np.array([
            [0.01 * np.exp(1j * 0.64 * np.pi), 0.01 * np.exp(1j * 0.54 * np.pi), 0.01 * np.exp(1j * 0.71 * np.pi), 0.97 * np.exp(1j * -0.44 * np.pi)],
            [0.02 * np.exp(1j * 0.52 * np.pi), 0.04 * np.exp(1j * 0.42 * np.pi), 0.95 * np.exp(1j * -0.21 * np.pi), 0.03 * np.exp(1j * -0.44 * np.pi)],
            [0.03 * np.exp(1j * -0.46 * np.pi), 0.93 * np.exp(1j * -0.14 * np.pi), 0.02 * np.exp(1j * -0.46 * np.pi), 0.02 * np.exp(1j * 0.67 * np.pi)],
            [0.96 * np.exp(1j * -0.05 * np.pi), 0.03 * np.exp(1j * -0.04 * np.pi), 0.02 * np.exp(1j * -0.24 * np.pi), 0.01 * np.exp(1j * -0.02 * np.pi)]
        ])

        # Vector Ein ON (Input Fields when ON)
        self.Eon_model = np.array([
            41.02 * np.exp(1j * -0.11 * np.pi),
            39.35 * np.exp(1j * -0.25 * np.pi),
            38.66 * np.exp(1j * -0.20 * np.pi),
            36.68 * np.exp(1j * 0.32 * np.pi)
        ])

        # Vector Ein OFF (Input Fields when OFF - Leakage)
        self.Eoff_model = np.array([
            0.18 * np.exp(1j * 0.84 * np.pi),
            0.67 * np.exp(1j * -0.25 * np.pi),
            2.72 * np.exp(1j * -0.35 * np.pi),
            1.34 * np.exp(1j * 0.17 * np.pi)
        ])

        # Association ABCD to output 0,1,2,3 depending of the pair of active input
        self.abcd = {
            (0,1) : (0,1,3,2),
            (0,2) : (0,3,1,2),
            (0,3) : None, # Not suitable for ABCD method
            (1,2) : None, # Not suitable for ABCD method
            (1,3) : (0,1,3,2),
            (2,3) : (0,3,1,2)
        }

    def predict_output(
        self, 
        injected_phases: np.ndarray = None,
        input_fields: np.ndarray = None, 
        multiplicative: bool = False, 
    ) -> np.ndarray:
        """
        Simulate the MMI output using the characterized analytical model.
        
        Model: E_out = A . P . Cin . E_in_eff
        
        Parameters
        ----------
        injected_phases : np.ndarray, optional
            Phases injected by the phase shifters (in radians).
            If None, assumes 0 for all shifters.
        input_fields : np.ndarray
            Input complex fields (shape 4,).
            If None, assumes 1+0j for all inputs.
        multiplicative : bool, optional
            If True, input_fields multiplies self.Eon_model (element-wise).
            If False, input_fields replaces self.Eon_model.
            Default is False.
            
        Returns
        -------
        np.ndarray
            Output intensities (shape 4,).
        """

        # 0. Handle Default Inputs
        if input_fields is None:
            input_fields = np.ones(4, dtype=complex)

        # 1. Determine Effective Input Field
        if multiplicative:
            # Modulate the characterized input profile
            E_eff = input_fields * self.Eon_model
        else:
            # Use provided fields directly (e.g. for custom combinations with OFF states)
            E_eff = input_fields.astype(complex)
            
        # 2. Apply Input Crosstalk
        # v = Cin . E_eff
        v = self.C_model @ E_eff
        
        # 3. Apply Phase Shifters
        # v' = P . v
        if injected_phases is None:
            injected_phases = np.zeros(4)
            
        # P is diagonal correlation phase matrix
        # P_matrix = np.diag(np.exp(1j * injected_phases))
        # v_prime = P_matrix @ v
        # Faster element-wise multiplication:
        v_prime = v * np.exp(1j * injected_phases)
        
        # 4. Apply MMI Transfer Function
        # E_out = A . v'
        E_out = self.A_model @ v_prime
        
        # 5. Return Intensities
        return np.abs(E_out)**2


    def predict_phasors(
        self, 
        injected_phases: np.ndarray = None,
        input_fields: np.ndarray = None, 
        multiplicative: bool = False, 
        plot: bool = True,
        calibrated: bool = False,
        relative: bool = True
    ) -> np.ndarray:
        """
        Return the complex phasors at the output, separated by input contribution.
        Mimics predict_output but returns (4, 4) complex array.
        
        Parameters
        ----------
        injected_phases : np.ndarray, optional
            Phases injected by the phase shifters (radians).
        input_fields : np.ndarray, optional
            Input complex fields (shape 4,).
        multiplicative : bool
            If True, input_fields multiplies model. Else replaces it.
        plot : bool
            If True, displays a polar plot of the phasors.
        calibrated : bool
            If True, first runs predict_null_calibration_gen to optimize phases for nulling, 
            then adds these optimal phases to injected_phases.
        relative : bool
            If True, rotates the plot so that Input 1 (Index 0) has phase 0.
        
        Returns
        -------
        np.ndarray
            Complex phasors array of shape (4, 4).
            output[i, j] is the contribution of Input j to Output i.
        """
        # 0. Handle Default Inputs
        if input_fields is None:
            input_fields = np.ones(4, dtype=complex)
            
        if injected_phases is None:
            injected_phases = np.zeros(4)
            
        # Calibration (Optional)
        if calibrated:
            print("⚙️ Running Auto-Calibration before phasor computation...")
            calib_res = self.predict_null_calibration_gen(verbose=False, plot=False, input_fields=input_fields)
            cal_phases = calib_res['final_phases']
            # Add calibration phases to requested injection
            injected_phases = injected_phases + cal_phases

        # 1. Determine Effective Input Field
        if multiplicative:
            # Modulate the characterized input profile
            E_eff_total = input_fields * self.Eon_model
        else:
            # Use provided fields directly
            E_eff_total = input_fields.astype(complex)
            
        # Initialize output array (4 outputs, 4 inputs)
        phasors = np.zeros((4, 4), dtype=complex)
        
        if injected_phases is None:
            injected_phases = np.zeros(4)
        
        # We process each input independently to isolate its contribution
        for j in range(4):
            # Isolate Input j
            E_eff_j = np.zeros(4, dtype=complex)
            E_eff_j[j] = E_eff_total[j]
            
            # 2. Apply Input Crosstalk
            v = self.C_model @ E_eff_j
            
            # 3. Apply Phase Shifters
            v_prime = v * np.exp(1j * injected_phases)
            
            # 4. Apply MMI Transfer Function
            E_out_j = self.A_model @ v_prime
            
            # Store in column j (Output i, Input j)
            phasors[:, j] = E_out_j
            
        if plot:
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(1, 4, subplot_kw={'projection': 'polar'}, figsize=(20, 5))
            colors = ['C0', 'C1', 'C2', 'C3'] # Colors for Inputs 0-3
            
            for i in range(4): # Loop over Outputs
                ax = axes[i]
                
                # Calculate rotation for Relative mode
                rot_angle = 0.0
                title_suffix = ""
                if relative:
                    # Reference: Input 0
                    z_ref = phasors[i, 0]
                    # We want angle(z_ref) + rot = 0
                    rot_angle = -np.angle(z_ref)
                    title_suffix = " (Rel to In 0)"
                
                ax.set_title(f"Output {i}{title_suffix}", va='bottom')
                
                # Plot contributions from each Input j
                # We chain them head-to-tail to show vector addition
                current_sum = 0j
                
                # Plot vectors head-to-tail
                for j in range(4):
                    z = phasors[i, j]
                    
                    # Apply rotation for plot
                    z_plot = z * np.exp(1j * rot_angle)
                    
                    # Plot Vector
                    # Start at current sum tail
                    # start = current_sum
                    # end = current_sum + z_plot
                    
                    # Store for next
                    # current_sum += z_plot
                    
                    # Draw arrow (or line)
                    # Polar plot takes (theta, r). 
                    # Calculating segments in polar is tricky for OFF-origin lines.
                    # EASIER: Plot individual vectors from origin to see phases? 
                    # OR plot the cumulative sum? 
                    # Thesis usually shows "contributions" radiating from center?
                    # Let's check the mental model: "Contribution de chaque télescope".
                    # Usually we want to see if they destructively interfere.
                    # So showing them from origin is good to compare angles.
                    
                    ax.plot([0, np.angle(z_plot)], [0, np.abs(z_plot)], color=colors[j], label=f"In {j}", alpha=0.7, lw=2)
                    ax.scatter(np.angle(z_plot), np.abs(z_plot), color=colors[j], s=30)
                
                # Plot Resultant Sum
                total = np.sum(phasors[i, :])
                total_plot = total * np.exp(1j * rot_angle)
                
                ax.plot([0, np.angle(total_plot)], [0, np.abs(total_plot)], color='k', linestyle='--', lw=2, label="Total")
                ax.scatter(np.angle(total_plot), np.abs(total_plot), color='k', marker='x', s=100)
                
                # ax.legend(loc='lower right', fontsize='x-small')
                ax.set_yticklabels([]) # Hide radius labels for cleanliness
             
            # Legend on first plot only or outside?
            axes[0].legend(loc='upper left', bbox_to_anchor=(-0.3, 1.1), fontsize='small')
            
            plt.suptitle(f"4x4 MMI Output Phasors")
            plt.tight_layout()
            plt.show()

        return phasors

    def verify_model(self, data_path=False, save_as=None):
        """
        Verify the analytical model against data or theoretical expectations.
        
        Plots the predicted response of the MMI using the stored characterization matrices 
        (self.A_model, self.C_model, etc.).
        If data_path is provided, overlays the measured data points.
        
        Parameters
        ----------
        data_path : str or bool, optional
            Path to .npz characterization data file. 
            If False or None, only plots the theoretical curves.
        save_as : str, optional
            Path to save the generated plots.
        """
        import os
        
        processed_items = []
        
        # 1. Load Data if provided
        if data_path:
            print(f"📊 Loading verification data from {data_path}...")
            try:
                raw_data = np.load(data_path, allow_pickle=True)
            except FileNotFoundError:
                print(f"❌ File {data_path} not found. Proceeding with theoretical model only.")
                data_path = False
            
            if data_path:
                # Handle flattened format (newer)
                if 'metadata_scan_keys' in raw_data:
                    scan_keys = raw_data['metadata_scan_keys']
                    for key in scan_keys:
                        fluxes = raw_data[f"{key}_fluxes"]
                        active_inputs = raw_data[f"{key}_active_inputs"]
                        shifter_channel = raw_data[f"{key}_shifter_channel"]
                        
                        # Handle scaler/array scalar weirdness
                        if hasattr(shifter_channel, 'item'):
                            if shifter_channel.ndim == 0: shifter_channel = shifter_channel.item()
                            elif shifter_channel.size == 1: shifter_channel = shifter_channel.flatten()[0]
                            
                        try:
                            shifter_idx = self.topas.index(shifter_channel)
                        except (ValueError, TypeError):
                            continue
                            
                        active_mask = np.zeros(4, dtype=bool)
                        for i in active_inputs:
                            active_mask[i-1] = True
                            
                        processed_items.append({
                            'active_mask': active_mask,
                            'scanned_input_idx': shifter_idx,
                            'key': key,
                            'phases': raw_data.get(f"{key}_phases", None),
                            'fluxes': fluxes
                        })
                else:
                    # Legacy format
                    for key in raw_data.files:
                        if not key.startswith("n"): continue
                        try:
                            scan_data = raw_data[key].item()
                        except ValueError: continue
                        
                        val_fluxes = scan_data['fluxes']
                        val_active = scan_data['active_inputs']
                        val_shifter = scan_data['shifter_channel']
                        
                        try:
                            shifter_idx = self.topas.index(val_shifter)
                        except ValueError: continue
                        
                        active_mask = np.zeros(4, dtype=bool)
                        for i in val_active:
                             active_mask[i-1] = True
                        
                        processed_items.append({
                            'active_mask': active_mask,
                            'scanned_input_idx': shifter_idx,
                            'key': key,
                            'phases': scan_data.get('phases', None),
                            'fluxes': val_fluxes
                        })
                        
        # 2. If no data, generate theoretical items
        if not processed_items and not data_path:
            print("generating theoretical scan items...")
            from itertools import product
            # Generate all combinations of active inputs
            for inputs in product([False, True], repeat=4):
                mask = np.array(inputs)
                if not np.any(mask): continue
                
                # For each combo, scan each shifter
                for shifter_idx in range(4):
                    processed_items.append({
                        'active_mask': mask,
                        'scanned_input_idx': shifter_idx,
                        'phases': np.linspace(0, 2*np.pi, 50),
                        'fluxes': None, # No measured data
                        'key': f"theo_mask{mask}_scan{shifter_idx}"
                    })

        # 3. Plotting
        if plt is None:
            print("Matplotlib not available.")
            return

        # Group by number of inputs
        plot_groups = {} 
        input_combos_by_n = {}
        
        for i, item in enumerate(processed_items):
            n_inputs = item['active_mask'].sum()
            if n_inputs not in plot_groups:
                plot_groups[n_inputs] = []
                input_combos_by_n[n_inputs] = set()
            
            # Store combo tuple for sorting columns
            item['combo_tuple'] = tuple(item['active_mask'])
            plot_groups[n_inputs].append(item)
            input_combos_by_n[n_inputs].add(tuple(item['active_mask']))
            
        # Plot each group
        for n_inputs in sorted(plot_groups.keys()):
            combos = sorted(list(input_combos_by_n[n_inputs]))
            n_cols = len(combos)
            n_rows = 4 
            
            fig, axs = plt.subplots(n_rows, n_cols, figsize=(4*n_cols, 3*n_rows), 
                                   constrained_layout=True, squeeze=False)
            fig.suptitle(f"Model Verification - {n_inputs} Inputs", fontsize=16)
            
            for item in plot_groups[n_inputs]:
                shifter_idx = item['scanned_input_idx']
                combo_idx = combos.index(item['combo_tuple'])
                ax = axs[shifter_idx, combo_idx]
                
                phases = item['phases']
                fluxes = item['fluxes']
                
                # Normalize phases to [0, 2pi] for plotting
                if phases is None and fluxes is not None:
                     phases = np.linspace(0, 2*np.pi, fluxes.shape[0])
                
                colors = ['C0', 'C1', 'C2', 'C3']
                
                # Plot Data if available
                if fluxes is not None:
                    for out_ch in range(4):
                        ax.scatter(phases, fluxes[:, out_ch], s=10, alpha=0.5, color=colors[out_ch], label=f'Meas {out_ch+1}' if shifter_idx==0 and combo_idx==n_cols-1 else "")
                else:
                    # If no phases provided (synthetic), make sure we have a range
                    if phases is None:
                        phases = np.linspace(0, 2*np.pi, 50)

                # Plot Model
                # Need to generate dense model prediction
                phase_dense = np.linspace(0, 2*np.pi, 50)
                
                # Construct effective input fields (using ON/OFF leakage model)
                # mask = item['active_mask']
                # E_in_eff = np.where(mask, self.Eon_model, self.Eoff_model)
                
                # But wait, we need to handle the array shapes properly
                # We can compute for all phases at once if predict_output supports batch, 
                # but currently predict_output takes (4,) inputs and (4,) phases.
                # So we iterate.
                
                model_fluxes = []
                active_mask = np.array(item['active_mask'])
                
                # Mix of vector ON and vector OFF based on mask
                # Note: This reproduces the "physics" of the test bench where "OFF" beams leak through.
                E_input_eff = np.where(active_mask, self.Eon_model, self.Eoff_model)
                
                for p in phase_dense:
                    # Construct phase array
                    injected_phases = np.zeros(4)
                    injected_phases[shifter_idx] = p
                    
                    # Predict
                    # We pass E_input_eff with multiplicative=False because we already constructed it manually
                    out = self.predict_output(E_input_eff, multiplicative=False, injected_phases=injected_phases)
                    model_fluxes.append(out)
                    
                model_fluxes = np.array(model_fluxes)
                
                for out_ch in range(4):
                    ax.plot(phase_dense, model_fluxes[:, out_ch], '-', color=colors[out_ch], label=f'Mod {out_ch+1}' if shifter_idx==0 and combo_idx==n_cols-1 else "")
                
                ax.set_xticks([0, np.pi, 2*np.pi])
                ax.set_xticklabels(['0', r'$\pi$', r'$2\pi$'])
                
                # Title
                active_inputs_list = [k+1 for k in range(4) if item['active_mask'][k]]
                ax.set_title(f"Scan S{shifter_idx+1}, In{active_inputs_list}", fontsize=10)

                if shifter_idx == n_rows - 1: 
                    ax.set_xlabel("Phase (rad)")
                
                if combo_idx == 0: 
                    ax.set_ylabel("Output (ADU)")
                
                if shifter_idx == 0 and combo_idx == n_cols - 1:
                    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='small')
                    
            if save_as:
                base, ext = os.path.splitext(save_as)
                fig.savefig(f"{base}_N{n_inputs}{ext}", dpi=150, bbox_inches='tight')
            plt.show()

    def null_calibration_gen(
        self,
        beta: float = 0.8,
        verbose: bool = False,
        plot: bool = False,
        figsize: tuple = (10, 10),
        save_as=None,
    ) -> dict:
        """
        Optimize phase shifter offsets to maximize nulling performance (minimize Null-Depth).
        
        Uses a genetic-like gradient descent algorithm adapted for Arch6.
        Metric: Null-Depth = sum(Nulls) / Bright
        
        Parameters
        ----------
        beta : float, optional
            Descent step size. Default is 0.8.
        verbose : bool, optional
            Print iteration details. Default is False.
        plot : bool, optional
            Plot calibration curves. Default is False.
        figsize : tuple, optional
            Figure size for plots. Default is (10, 10).
        save_as : str, optional
            Path to save the plot.
            
        Returns
        -------
        np.ndarray
            Optimized phase offsets (radians).
        
        Notes
        -----
        This method uses a simpler genetic algorithm (gradient descent on metrics)
        rather than full genetic evolution.
        
        Examples
        --------
        >>> arch = Arch6()
        >>> offsets = arch.null_calibration_gen(verbose=True, plot=True)
        >>> arch.set_phases(offsets)  # Apply calibration
        """
        import phobos
        from ..cred3 import Cred3
        cred3 = Cred3()
        
        # Get bright output from config
        bright_output = phobos.config.photonic_chip.bright_output
        
        # Initial step size
        ε = 1e-4 # Minimum shift step size in radians
        Δφ = np.pi / 2 # Initial step
        
        # Arch6 has 4 channels, all participate in optimization
        shifter_indices = range(len(self.channels))
        
        # History
        depth_history = []
        shifters_history = []
        
        # Cache current phases to avoid repeated hardware calls
        current_phases = [ch.get_phase() for ch in self.channels]
        
        def get_metric():
            outs = cred3.get_outputs()
            # Expected outs: [Bright, Null1, Null2, Null3]
            # Verify we have at least 4 outputs? 
            # Trusting user input on crop_centers for now.
            
            b = outs[0]
            nulls_sum = np.sum(outs[1:])
            
            # Metric: Null-Depth = sum(Nulls) / Bright
            metric = nulls_sum / b if b > 0 else 0
            
            return metric
            
        print("🧬 Starting Genetic Calibration for Arch6...")
        
        iteration_count = 0
        
        while Δφ > ε:
            if verbose:
                print(f"--- Iteration {iteration_count} --- Δφ={Δφ:.2e}")
            
            for i in shifter_indices:
                shifter = self.channels[i]
                
                log = ""
                
                # Measure current state
                m_old = get_metric()
                
                # Get current phase from cache or hardware if first time
                current_phase = current_phases[i]
                
                # Positive step
                shifter.set_phase((current_phase + Δφ) % (2 * np.pi))
                m_pos = get_metric()
                
                # Negative step
                shifter.set_phase((current_phase - Δφ) % (2 * np.pi))
                m_neg = get_metric()
                
                # Restore original position for now
                shifter.set_phase(current_phase)
                
                # Record history
                depth_history.append(m_old)
                shifters_history.append(list(current_phases)) # Use cached values
                
                # Decision logic: Minimize Metric
                updated = False
                log += f"Shift {shifter.channel} Metric: {m_neg:.2e} | {m_old:.2e} | {m_pos:.2e} -> "
                
                if m_pos < m_old and m_pos < m_neg:
                    log += " + "
                    new_phase = (current_phase + Δφ) % (2 * np.pi)
                    shifter.set_phase(new_phase)
                    current_phases[i] = new_phase
                    updated = True
                elif m_neg < m_old and m_neg < m_pos:
                    log += " - "
                    new_phase = (current_phase - Δφ) % (2 * np.pi)
                    shifter.set_phase(new_phase)
                    current_phases[i] = new_phase
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
            axs[0].set_ylabel("Null-Depth (ΣNulls/Bright)")
            axs[0].set_yscale("log")
            axs[0].set_title("Performance of the Nuller")
            
            for i in range(shifters_hist_arr.shape[1]):
                axs[1].plot(shifters_hist_arr[:, i], label=f"Ch {self.channels[i].channel}")
            
            axs[1].set_xlabel("Steps")
            axs[1].set_ylabel("Phase shift (rad)")
            axs[1].set_title("Convergence of phase shifters")
            axs[1].legend(loc='upper right', bbox_to_anchor=(1,1), fontsize='small', ncol=2)
            
            if save_as:
                plt.savefig(save_as, dpi=150, bbox_inches='tight')
            plt.show()
            
        return {
            "depth": np.array(depth_history),
            "shifters": np.array(shifters_history)
        }

    def predict_null_calibration_gen(
        self,
        verbose: bool = False,
        plot: bool = False,
        plot_title: str = "Analytical Calibration",
        input_fields: np.ndarray = None
    ) -> dict:
        """
        Optimize phase shifter offsets using the analytical model to maximize nulling performance.
        Mimics null_calibration_gen but uses predict_output and scipy.optimize.
        Metric: Null-Depth = sum(Nulls) / Bright
        Outputs are assumed to be: 0=Bright, 1,2,3=Nulls (Standard Arch6)
        """
        from scipy.optimize import minimize
        
        # 0. Handle Defaults
        if input_fields is None:
            input_fields = np.ones(4, dtype=complex)
            
        # 1. Objective Function Setup
        history = []
        
        def objective(phases):
            # phases shape (4,)
            outs = self.predict_output(input_fields=input_fields, injected_phases=phases, multiplicative=False)
            bright = outs[0]
            nulls = np.sum(outs[1:])
            
            # Avoid division by zero
            metric = nulls / bright if bright > 1e-9 else 1e9
            history.append(metric)
            return metric

        # 2. Run Optimization
        x0 = np.zeros(4)
        if verbose:
            print("🧬 Starting Analytical Calibration...")
            
        # Optimization Call
        # Ensure we capture result object
        res = None
        try:
            res = minimize(objective, x0, method='L-BFGS-B', options={'ftol': 1e-9, 'disp': verbose})
        except Exception as e:
            print(f"❌ Minimization FAILED: {e}")
            return {'final_phases': x0, 'depth_history': history, 'metric': 1e9}

        
        optimized_phases = res.x % (2*np.pi)
        
        if verbose:
            print(f"✅ Calibration Optimization Complete. Metric: {res.fun:.2e}")
            
        # 3. Plotting (Optional)
        if plot:
            import matplotlib.pyplot as plt
            if plt is not None:
                plt.figure(figsize=(8, 4))
                plt.plot(history)
                plt.yscale('log')
                plt.xlabel('Evaluations')
                plt.ylabel('Null-Depth')
                plt.title(f"{plot_title}\nFinal: {res.fun:.2e}")
                plt.grid(True, which='both', alpha=0.3)
                plt.show()

        # 4. Return Results
        return {
            'final_phases': optimized_phases,
            'depth_history': history,
            'metric': res.fun
        }



    def solve_matrix(self, data_path=None, plot=True, save_as=None, **kwargs):
        """
        Solve for the interaction matrix A, crosstalk C_before, and input vectors I_ON/OFF.
        
        This method characterizes the component using the Total Flux conservation model:
        O_total = E_in^dag . C_before^dag . P^dag . A . P . C_before . E_in
        
        Where A is the effective Hermitian transfer matrix (M^dag . C_after^dag . C_after . M).
        
        Parameters
        ----------
        data_path : str, optional
            Path to an existing .npz characterization file. If None, runs characterization.
        plot : bool
            If True, plot the comparison between measured and predicted data.
        save_as : str
            Path to save the plot.
        **kwargs : dict
            Arguments to pass to characterize() if data_path is None.
            
        Returns
        -------
        dict
            {'A': matrix (4x4), 'C_before': matrix (4x4), 'I_ON': vector (4,), 'I_OFF': vector (4,), 'cost': float}
        """
        from scipy.optimize import least_squares
        from scipy.linalg import expm, svd
        import re
        
        # 1. Acquire Data
        if data_path is None:
            print("🚀 No data path provided. Running characterization...")
            data_path = self.characterize(plot=False, **kwargs)
            print(f"📂 Data saved to: {data_path}")
            
        # 2. Process Data (Extract Harmonic Coefficients)
        print(f"📊 Loading and processing data from {data_path}...")
        try:
            raw_data = np.load(data_path, allow_pickle=True)
        except FileNotFoundError:
            raise FileNotFoundError(f"File {data_path} not found.")
            
        processed_items = []
        
        # Check if we have the new data format (flattened) or old (nested)
        if 'metadata_scan_keys' in raw_data:
            # New format (flattened keys)
            scan_keys = raw_data['metadata_scan_keys']
            
            for key in scan_keys:
                fluxes = raw_data[f"{key}_fluxes"]
                active_inputs = raw_data[f"{key}_active_inputs"]
                shifter_channel = raw_data[f"{key}_shifter_channel"]
                if hasattr(shifter_channel, 'item'): 
                    # If it's a 0-d array, item() gives scalar.
                    # If it's 1-d array, item() fails or we need to handle it.
                    if shifter_channel.ndim == 0:
                        shifter_channel = shifter_channel.item()
                    elif shifter_channel.size == 1:
                        shifter_channel = shifter_channel.flatten()[0]
                
                # Map shifter channel to 0-3 index
                try:
                    shifter_idx = self.topas.index(shifter_channel)
                except ValueError:
                    # Try converting to int (handle type mismatch like int32 vs int)
                    try:
                        shifter_idx = self.topas.index(int(shifter_channel))
                    except (ValueError, TypeError):
                        print(f"Skipping key {key}. shifter_channel={shifter_channel} not found in {self.topas}.")
                        continue 
                    
                # Construct active mask (size 4)
                active_mask = np.zeros(4, dtype=bool)
                for i in active_inputs:
                    active_mask[i-1] = True
                    
                # FFT to extract harmonics
                N = fluxes.shape[0]
                fft_res = np.fft.fft(fluxes, axis=0) / N
                
                # Keep harmonics for EACH output k
                dc_k = np.abs(fft_res[0]) # Shape (4,)
                fundamental_k = fft_res[1] # Shape (4,)
                
                processed_items.append({
                    'dc': dc_k,
                    'fundamental': fundamental_k,
                    'active_mask': active_mask,
                    'scanned_input_idx': shifter_idx,
                    'key': key,
                    'phases': raw_data.get(f"{key}_phases", None), 
                    'fluxes': fluxes # Store raw for plotting
                })
                
        else:
            # Legacy format support (or unknown format)
            # Iterate over keys in the npz file
            for key in raw_data.files:
                if not key.startswith("n"):
                    continue
                    
                # Each key contains a dictionary-like object (if saved with savez w/ kwargs)
                # or it might be flat arrays if saved differently. 
                # Arch.characterize uses: np.savez(..., **all_scans) where all_scans values are dicts? 
                # No, all_scans values are dicts, but np.savez kwargs saves them as 0-d arrays containing the dict.
                
                try:
                    scan_data = raw_data[key].item()
                except ValueError:
                    # Skip keys that are not scalar objects (e.g. metadata or flattened arrays if mixed)
                    continue
                
                fluxes = scan_data['fluxes'] # Shape (P, 4)
                # phases = scan_data['phases'] # Shape (P,)
                active_inputs = scan_data['active_inputs']
                shifter_channel = scan_data['shifter_channel']
                
                # Map shifter channel to 0-3 index
                try:
                    shifter_idx = self.topas.index(shifter_channel)
                except ValueError:
                    continue 
                    
                # Construct active mask (size 4)
                active_mask = np.zeros(4, dtype=bool)
                for i in active_inputs:
                    active_mask[i-1] = True
                    
                # FFT to extract harmonics
                N = fluxes.shape[0]
                fft_res = np.fft.fft(fluxes, axis=0) / N
                
                # Keep harmonics for EACH output k
                dc_k = np.abs(fft_res[0])
                fundamental_k = fft_res[1]
                
                processed_items.append({
                    'dc': dc_k,
                    'fundamental': fundamental_k,
                    'active_mask': active_mask,
                    'scanned_input_idx': shifter_idx,
                    'key': key,
                    'phases': scan_data.get('phases', None),
                    'fluxes': fluxes
                })
            
        N_sub = len(processed_items)
        if N_sub == 0:
            raise ValueError("No valid scan data found in archive.")
            
        print(f"✅ Extracted {N_sub} data points (Total Flux) for optimization.")
        
        # Prepare arrays for optimization
        measure_dc_arr = np.array([d['dc'] for d in processed_items]) # (N_sub,)
        measure_fund_arr = np.array([d['fundamental'] for d in processed_items]) # (N_sub,)
        active_masks_arr = np.array([d['active_mask'] for d in processed_items], dtype=bool) # (N_sub, 4)
        scanned_indices_arr = np.array([d['scanned_input_idx'] for d in processed_items], dtype=int) # (N_sub,)
        
        # 3. Define Model and Residuals
        
        # 3. Define Model and Residuals
        
        # Helpers for Unitary Parametrization
        # A = exp(iH), where H is Hermitian (16 real params for 4x4)
        # H has 4 real diagonal elements + 6 complex off-diagonal (12 params) = 16 params
        
        def pack_params(H_params, C, I_ON, I_OFF):
            # H_params: 16 floats (4 diag, 6 real off, 6 imag off)
            # C: 32 floats (4x4 complex)
            # I_ON: 8 floats
            # I_OFF: 8 floats
            # Total: 16 + 32 + 8 + 8 = 64 parameters
            return np.concatenate([
                H_params,
                C.real.ravel(), C.imag.ravel(),
                I_ON.real.ravel(), I_ON.imag.ravel(),
                I_OFF.real.ravel(), I_OFF.imag.ravel()
            ])

        def unpack_params(x):
            # H (4x4 Hermitian)
            # Diagonals (4 real)
            h_diag = x[0:4]
            # Off-diagonals (6 complex -> 12 real)
            # Upper triangle indices: (0,1), (0,2), (0,3), (1,2), (1,3), (2,3)
            h_off_real = x[4:10]
            h_off_imag = x[10:16]
            
            H = np.zeros((4,4), dtype=complex)
            # Set diagonals
            np.fill_diagonal(H, h_diag)
            
            # Set off-diagonals
            idx = 0
            for i in range(4):
                for j in range(i+1, 4):
                    val = h_off_real[idx] + 1j * h_off_imag[idx]
                    H[i,j] = val
                    H[j,i] = np.conj(val)
                    idx += 1
            
            # A = exp(iH) is strictly Unitary
            A = expm(1j * H)
            
            # C (4x4 Complex) - 32 params
            ptr = 16
            c_real = x[ptr:ptr+16].reshape(4,4); ptr += 16
            c_imag = x[ptr:ptr+16].reshape(4,4); ptr += 16
            C = c_real + 1j * c_imag
            
            # I_ON - 8 params
            ion_real = x[ptr:ptr+4]; ptr += 4
            ion_imag = x[ptr:ptr+4]; ptr += 4
            I_ON = ion_real + 1j * ion_imag
            
            # I_OFF - 8 params
            ioff_real = x[ptr:ptr+4]; ptr += 4
            ioff_imag = x[ptr:ptr+4]; ptr += 4
            I_OFF = ioff_real + 1j * ioff_imag
            
            return A, C, I_ON, I_OFF

        def compute_residuals(x):
            A, C_before, I_ON, I_OFF = unpack_params(x)
            
            # --- Standard Residuals ---
            # 1. Inputs E_in
            Is_ON = I_ON[None, :]
            Is_OFF = I_OFF[None, :]
            E_in_base = np.where(active_masks_arr, Is_ON, Is_OFF) # (N_sub, 4)
            
            # 2. Pre-Shifter States v = C_before . E_in
            v = (C_before @ E_in_base.T).T # (N_sub, 4)
            
            k_indices = scanned_indices_arr # (N_sub,)
            
            # 3. Model: E_out = A @ P(phi) @ v
            # A_ks = A[:, s]
            A_ks = A[:, k_indices] # (4, N_sub)
            
            # v_s: Input component entering the phase shifter
            v_s = v[np.arange(N_sub), k_indices]
            
            # Z_mod = A_{ks} * v_s
            Z_mod = (A_ks * v_s).T 
            
            # E_0 = A @ v (Field at phi=0)
            E_0 = (A @ v.T).T # (N_sub, 4)
            
            # Z_static = E_0 - Z_mod
            Z_static = E_0 - Z_mod 
            
            # Predicted Harmonics
            pred_dc = np.abs(Z_mod)**2 + np.abs(Z_static)**2
            pred_fund = Z_mod * np.conj(Z_static)
            
            # Measurement Residuals
            diff_dc = (pred_dc - measure_dc_arr).ravel() 
            diff_fund = (pred_fund - measure_fund_arr).ravel()
            
            residuals = np.concatenate([diff_dc, diff_fund.real, diff_fund.imag])
            
            # --- Constraints / Penalties ---
            
            # Constraint: Spectral Norm of C <= 1
            # Penalty = w * max(0, sigma_max - 1)
            # We apply it to all singular values > 1
            s = svd(C_before, compute_uv=False)
            penalty_C = np.maximum(0, s - 1.0) * 1e3 # Strong weight
            
            return np.concatenate([residuals, penalty_C])

        # 4. Run Optimization
        print("🧠 Running constrained optimization (Unitary A, |C|<=1)...")
        
        # Initial Guess
        # A = I => H = 0
        H_init = np.zeros(16) # 4 diag + 12 off (real/imag)
        
        C_init = np.eye(4, dtype=complex)
        I_ON_init = np.ones(4, dtype=complex)
        I_OFF_init = np.zeros(4, dtype=complex)
        
        x0 = pack_params(H_init, C_init, I_ON_init, I_OFF_init)
        
        res = least_squares(compute_residuals, x0, method='lm', max_nfev=5000, verbose=1)
        
        A_final, C_before_final, I_ON_final, I_OFF_final = unpack_params(res.x)
        
        print(f"✅ Optimization complete. Cost: {res.cost:.2e}")

        
        # 5. Plotting (Detailed)
        if plot and plt is not None:
            A, C_before, I_ON, I_OFF = A_final, C_before_final, I_ON_final, I_OFF_final
            
            # Organize data for plotting
            plot_groups = {} 
            input_combos_by_n = {}
            
            for i, item in enumerate(processed_items):
                n_inputs = item['active_mask'].sum()
                if n_inputs not in plot_groups:
                    plot_groups[n_inputs] = []
                    input_combos_by_n[n_inputs] = set()
                item_data = item.copy()
                item_data['global_idx'] = i
                item_data['combo_tuple'] = tuple(item['active_mask'])
                plot_groups[n_inputs].append(item_data)
                input_combos_by_n[n_inputs].add(tuple(item['active_mask']))
                
            for n_inputs in sorted(plot_groups.keys()):
                combos = sorted(list(input_combos_by_n[n_inputs]))
                n_cols = len(combos)
                n_rows = 4 
                
                fig, axs = plt.subplots(n_rows, n_cols, figsize=(4*n_cols, 3*n_rows), 
                                       constrained_layout=True, squeeze=False)
                fig.suptitle(f"Fit Result - {n_inputs} Inputs", fontsize=16)
                
                def predict_flux(phase_val, shifter_idx, active_mask):
                    mask = active_mask
                    E_in = np.where(mask, I_ON, I_OFF)
                    v = C_before @ E_in
                    Pv = v.copy()
                    Pv[shifter_idx] *= np.exp(1j * phase_val)
                    E_out = A @ Pv
                    return np.abs(E_out)**2
                
                for item in plot_groups[n_inputs]:
                    shifter_idx = item['scanned_input_idx']
                    combo_idx = combos.index(item['combo_tuple'])
                    ax = axs[shifter_idx, combo_idx]
                    
                    phases = item['phases']
                    fluxes = item['fluxes']
                    if phases is None: phases = np.linspace(0, 2*np.pi, fluxes.shape[0])
                    
                    colors = ['C0', 'C1', 'C2', 'C3']
                    
                    # Plot Measured
                    for out_ch in range(4):
                        ax.scatter(phases, fluxes[:, out_ch], s=10, alpha=0.5, color=colors[out_ch], label=f'Meas {out_ch+1}')
                    
                    # Plot Model
                    phase_dense = np.linspace(0, 2*np.pi, 50)
                    model_fluxes = np.array([predict_flux(p, shifter_idx, item['active_mask']) for p in phase_dense])
                    
                    for out_ch in range(4):
                        ax.plot(phase_dense, model_fluxes[:, out_ch], '-', color=colors[out_ch], label=f'Mod {out_ch+1}')
                    
                    ax.set_xticks([0, np.pi, 2*np.pi])
                    ax.set_xticklabels(['0', r'$\pi$', r'$2\pi$'])
                    
                    # Title
                    active_inputs_list = [k+1 for k in range(4) if item['active_mask'][k]]
                    ax.set_title(f"Scan S{shifter_idx+1}, In{active_inputs_list}", fontsize=10)

                    if shifter_idx == n_rows - 1: 
                        ax.set_xlabel("Phase (rad)")
                    
                    if combo_idx == 0: 
                        ax.set_ylabel("Output (ADU)")
                    
                    if shifter_idx == 0 and combo_idx == n_cols - 1:
                        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='small')
                        
                if save_as:
                    base, ext = os.path.splitext(save_as)
                    fig.savefig(f"{base}_N{n_inputs}{ext}", dpi=150, bbox_inches='tight')
                plt.show()

        self.A_model = A_final
        self.C_model = C_before_final
        self.Eon_model = I_ON_final
        self.Eoff_model = I_OFF_final

        return {
            'A': A_final,
            'C_before': C_before_final,
            'I_ON': I_ON_final,
            'I_OFF': I_OFF_final,
            'cost': res.cost
        }

    def abcd_fringe_tracking(
        self,
        atmosphere_params: dict,
        dm_segments_indices: tuple,
        input_indices: tuple = (0,1),
    ):
        """
        Simulate and correct atmospheric piston errors using ABCD Fringe Tracking on a classical nuller.
        """
        from ..deformable_mirror import DM
        from ..cred3 import Cred3
        # Import get_delays inside method to avoid potential circular imports
        from ...modules.atmosphere import get_delays
        
        # Instantiate singletons
        dm = DM()
        cred3 = Cred3()
        
        print("\n🔵 Starting ABCD Fringe Tracking Simulation (Hardware)")
        print("="*40)
            
        # 2. Generate Atmosphere
        delays, times, wavelength = self._setup_atmosphere(atmosphere_params)
        n_steps = len(times)
        n_inputs = 4
        
        # 3. Setup DM State
        print("🔌 Setting up DM inputs...")
        unused_inputs = [i for i in range(n_inputs) if i not in input_indices]
        for idx in unused_inputs:
            seg_id = dm_segments_indices[idx]
            # Set to OFF position
            dm.segments[seg_id].set_ptt(-1150, 0, -5.47)
            
        active_seg_ids = [dm_segments_indices[i] for i in input_indices]
        
        # Store results
        # Store ALL fluxes for plotting: (N, 4)
        fluxes_open = np.zeros((n_steps, 4))
        fluxes_closed = np.zeros((n_steps, 4))
        corrections = np.zeros(n_steps)
        
        # Track phases individually for plotting
        phases_atmo_0 = np.zeros(n_steps)
        phases_atmo_1 = np.zeros(n_steps)
        phases_inj_0 = np.zeros(n_steps)
        phases_inj_1 = np.zeros(n_steps)
        
        # --- OPEN LOOP ---
        print("🔓 Running Open Loop simulation...")
        for t in range(n_steps):
            # 1. Apply Atmospheric Piston
            for i, input_idx in enumerate(input_indices):
                delay_nm = delays[t, input_idx]
                seg_id = active_seg_ids[i]
                dm.segments[seg_id].set_piston(delay_nm)
            
            # 2. Measure Flux
            outs = cred3.get_outputs()
            fluxes_open[t, :] = outs
            
            if t % 10 == 0: print(f"\rStep {t}/{n_steps}", end="")
        print("\rOpen Loop done.          ")
        
        # --- CLOSED LOOP ---
        print("🔒 Running Closed Loop simulation...")
        
        # Reset Phase Shifters
        for ch in self.channels: ch.set_phase(0.0)
            
        gain = 0.5
        current_correction_rad = 0.0
        
        # Resolve correct shifter for the control input (input_indices[1])
        ctrl_input_idx = input_indices[1]
        ctrl_shifter_idx = self.get_shifter_for_input(ctrl_input_idx)
        correction_shifter = self.channels[ctrl_shifter_idx]
        print(f"Correction applied on Shifter {ctrl_shifter_idx} (Channel {correction_shifter.channel}) for Input {ctrl_input_idx}")
        
        for t in range(n_steps):
            # 1. Apply Atmospheric Piston
            for i, input_idx in enumerate(input_indices):
                delay_nm = delays[t, input_idx]
                seg_id = active_seg_ids[i]
                dm.segments[seg_id].set_piston(delay_nm)
                
                # Record phases
                phi_rad = (delay_nm * 1e-9 / wavelength) * 2 * np.pi
                if i == 0: phases_atmo_0[t] = phi_rad
                if i == 1: phases_atmo_1[t] = phi_rad
            
            # 2. Apply Correction
            correction_shifter.set_phase(current_correction_rad % (2*np.pi))
            phases_inj_1[t] = current_correction_rad
            phases_inj_0[t] = 0 # No correction on channel 0
            
            # 3. Measure Fluxes
            outs = cred3.get_outputs()
            fluxes_closed[t, :] = outs
            
            # 4. ABCD Estimation
            diff = self._calculate_abcd_error(outs, input_indices)
            if diff is not None:
                current_correction_rad -= gain * diff
            
            corrections[t] = current_correction_rad

            if t % 10 == 0: print(f"\rStep {t}/{n_steps}", end="")
        print("\rClosed Loop done.          ")
        
        phases_data = {
            'atmo_0': phases_atmo_0,
            'atmo_1': phases_atmo_1,
            'inj_0': phases_inj_0,
            'inj_1': phases_inj_1
        }
        
        print("\rClosed Loop done.          ")
        
        phases_data = {
            'atmo_0': phases_atmo_0,
            'atmo_1': phases_atmo_1,
            'inj_0': phases_inj_0,
            'inj_1': phases_inj_1
        }
        
        # Plotting with wavelength info
        self._plot_tracking_results(times, fluxes_open, fluxes_closed, phases_data, input_indices, wavelength=wavelength)
            
        return {
            "fluxes_open": fluxes_open,
            "fluxes_closed": fluxes_closed,
            "corrections": corrections,
            "times": times,
            "phases_data": phases_data
        }

    def predict_abcd_fringe_tracking(
        self,
        atmosphere_params: dict = None,
        input_indices: tuple = (0,1),
    ):
        """
        Simulate fringe tracking using the analytical model (Arch6.predict_output).
        Does not require hardware.
        """
        print("\n🔵 Starting Theoretical ABCD Fringe Tracking Simulation")
        print("="*40)
        
        # 1. Generate Atmosphere
        delays, times, wavelength = self._setup_atmosphere(atmosphere_params)
        n_steps = len(times)
        
        fluxes_open = np.zeros((n_steps, 4))
        fluxes_closed = np.zeros((n_steps, 4))
        corrections = np.zeros(n_steps)
        
        phases_atmo_0 = np.zeros(n_steps)
        phases_atmo_1 = np.zeros(n_steps)
        phases_inj_0 = np.zeros(n_steps)
        phases_inj_1 = np.zeros(n_steps)
        
        # --- OPEN LOOP ---
        print("🔓 Running Theoretical Open Loop...")
        for t in range(n_steps):
            # Compute Input Fields with Atmosphere
            phis_atmo = (delays[t] * 1e-9 / wavelength) * 2 * np.pi
            
            # Build E_eff for this timestep (Atmosphere + Crosstalk/Leakage)
            E_eff = np.zeros(4, dtype=complex)
            for i in range(4):
                if i in input_indices:
                    phi = phis_atmo[i]
                    # Simulate ON beam with phase delay
                    E_eff[i] = self.Eon_model[i] * np.exp(1j * phi)
                else:
                    # Simulate OFF beam (leakage)
                    E_eff[i] = self.Eoff_model[i]
            
            # Predict Output
            outs = self.predict_output(input_fields=E_eff, multiplicative=False, injected_phases=None)
            fluxes_open[t, :] = outs
            
        # --- CLOSED LOOP ---
        print("🔒 Running Theoretical Closed Loop...")
        gain = 0.3 # Reduced gain for stability
        current_correction_rad = 0.0
        
        for t in range(n_steps):
            # 1. Disturbance Phase
            phis_atmo = (delays[t] * 1e-9 / wavelength) * 2 * np.pi
            
            # Record Phases
            phases_atmo_0[t] = phis_atmo[input_indices[0]]
            phases_atmo_1[t] = phis_atmo[input_indices[1]]
            
            # 2. Build Injected Correction Phases
            injected_phases = np.zeros(4)
            # Find which shifter controls input_indices[1]
            ctrl_input_idx = input_indices[1]
            ctrl_shifter_idx = self.get_shifter_for_input(ctrl_input_idx)
            
            injected_phases[ctrl_shifter_idx] = current_correction_rad
            
            phases_inj_0[t] = 0
            phases_inj_1[t] = current_correction_rad
            
            # 3. Build Inputs (same as open loop)
            E_eff = np.zeros(4, dtype=complex)
            for i in range(4):
                if i in input_indices:
                    phi = phis_atmo[i]
                    E_eff[i] = self.Eon_model[i] * np.exp(1j * phi)
                else:
                    E_eff[i] = self.Eoff_model[i]
            
            # 4. Predict
            outs = self.predict_output(input_fields=E_eff, multiplicative=False, injected_phases=injected_phases)
            fluxes_closed[t, :] = outs
            
            # 5. Correction
            diff = self._calculate_abcd_error(outs, input_indices)
            if diff is not None:
                current_correction_rad -= gain * diff
            
            corrections[t] = current_correction_rad
        
        phases_data = {
            'atmo_0': phases_atmo_0,
            'atmo_1': phases_atmo_1,
            'inj_0': phases_inj_0,
            'inj_1': phases_inj_1
        }
            
        self._plot_tracking_results(times, fluxes_open, fluxes_closed, phases_data, input_indices, wavelength=wavelength)
        
        return {
            "fluxes_open": fluxes_open,
            "fluxes_closed": fluxes_closed,
            "corrections": corrections,
            "times": times,
            "phases_data": phases_data
        }

    # --- Helpers ---

    def _setup_atmosphere(self, params = None):
        from ...modules.atmosphere import get_delays
        print("☁️  Generating atmospheric turbulence...")
        # Force demo=False to just get the data
        if params is None:
            params = {}
        p = params.copy()
        p['demo'] = False
        
        # Enforce smoother transitions if not specified
        # Criteria: Lambda/10 per step.
        # dt ~ 0.005s for v=10m/s, r0=0.8m is safe.
        if 'time_step' not in p:
            p['time_step'] = 0.005 # 5 ms
            print(f"⚠️  Enforcing time_step={p['time_step']}s for smooth tracking.")
            
        delays, times = get_delays(**p)
        wavelength = p.get('wavelength', 1.65e-6)
        return delays, times, wavelength

    def get_shifter_for_input(self, input_idx):
        """
        Identify which phase shifter (row of C_model) dominates the given input (col of C_model).
        """
        return np.argmax(np.abs(self.C_model[:, input_idx]))

    def _calculate_abcd_error(self, outs, input_indices):
        I = outs
        if np.sum(I) < 1e-6: return None
        
        # Get ABCD mapping from dictionary
        # Sort indices to match dictionary keys format
        key = tuple(sorted(input_indices))
        
        if key not in self.abcd or self.abcd[key] is None:
            # print(f"Warning: Inputs {key} not suitable for ABCD tracking.")
            return None
            
        # Unpack mapping indices
        idx_A, idx_B, idx_C, idx_D = self.abcd[key]
        
        # Construct Phasors
        # U = A - C (Cos-like component)
        U = I[idx_A] - I[idx_C]
        
        # V = B - D (Sin-like component)
        V = I[idx_B] - I[idx_D]
        
        # This estimator maps the phase circle to [-pi, pi]
        current_phase = np.arctan2(V, U)
        
        # Target: Lock to Phase 0 (Max at A)
        # Since A corresponds to 0 phase delay in standard ABCD
        target = 0.0
        
        diff = current_phase - target
        diff = (diff + np.pi) % (2*np.pi) - np.pi
        return diff

    def _plot_tracking_results(self, times, f_open, f_closed, phases_data, input_indices, wavelength=1.65e-6):
        """
        phases_data: dict containing:
            'atmo_0': array,
            'atmo_1': array,
            'inj_0': array,
            'inj_1': array
        """
        key = tuple(sorted(input_indices))
        bright_output_index = 0 # Default value

        if bright_output_index == 0 and hasattr(self, 'abcd') and key in self.abcd and self.abcd[key] is not None:
            if self.bright_output_index is None:
             import phobos
             config = phobos.config
             bright_output_index = config.photonic_chip.bright_output
             self.bright_output_index = bright_output_index
        
        bright_idx = bright_output_index

        if plt is not None:
            # Layout:
            # Row 0: Flux Time Series (4 cols)
            # Row 1: Flux Histograms (4 cols)
            # Row 2: Phases (1 col)
            fig = plt.figure(figsize=(16, 12), constrained_layout=True)
            gs = fig.add_gridspec(3, 4, height_ratios=[1, 1, 1])
            
            # --- Row 0: Time Series ---
            ax_fluxes = [fig.add_subplot(gs[0, i]) for i in range(4)]
            for i in range(4):
                ax = ax_fluxes[i]
                ax.plot(times, f_open[:, i], label="Open", alpha=0.6, lw=1)
                ax.plot(times, f_closed[:, i], label="Closed", alpha=0.8, lw=1)
                ax.set_title(f"Output {i} - Flux")
                if i==0: ax.set_ylabel("Flux (ADU)")
                ax.grid(True, alpha=0.3)
                if i==bright_idx: # Highlight target
                    ax.set_facecolor('#f0fff0')
            ax_fluxes[0].legend(loc='upper right', fontsize='small')
            
            # --- Row 1: Histograms ---
            ax_hists = [fig.add_subplot(gs[1, i]) for i in range(4)]
            for i in range(4):
                ax = ax_hists[i]
                # Determine common bins
                all_data = np.concatenate([f_open[:, i], f_closed[:, i]])
                bins = np.linspace(np.min(all_data), np.max(all_data), 30)
                
                ax.hist(f_open[:, i], bins=bins, alpha=0.5, label="Open", density=True, color='C0')
                ax.hist(f_closed[:, i], bins=bins, alpha=0.5, label="Closed", density=True, color='C1')
                
                # Statistics lines
                mean_closed = np.mean(f_closed[:, i])
                ax.axvline(mean_closed, color='C1', linestyle='--', alpha=0.8, lw=2)
                
                ax.set_title(f"Output {i} - Dist")
                if i==0: ax.set_ylabel("Density")
                ax.set_xlabel("Flux (ADU)")
                ax.grid(True, alpha=0.3)
                if i==bright_idx:
                    ax.set_facecolor('#f0fff0')
            ax_hists[0].legend(fontsize='small')

            # --- Row 2: Phases ---
            ax_phase = fig.add_subplot(gs[2, :])
            
            p = phases_data
            
            # Convert rad to nm and wrap to [0, lambda]
            def to_nm_wrapped(rad_arr):
                # Standard conversion
                nm = (rad_arr / (2*np.pi)) * wavelength * 1e9
                # Wrap
                nm_wrapped = nm % (wavelength * 1e9)
                return nm_wrapped

            atmo_0_nm = to_nm_wrapped(p['atmo_0'])
            atmo_1_nm = to_nm_wrapped(p['atmo_1'])
            inj_1_nm = to_nm_wrapped(p['inj_1'])
            
            # Calculate Relative Atmospheric Phase (Atmo 1 - Atmo 0)
            # This is what we want to correct.
            atmo_diff_nm = to_nm_wrapped(p['atmo_1'] - p['atmo_0'])
            
            ax_phase.plot(times, atmo_0_nm, label="Atmo In 0", color='C0', alpha=0.3, linestyle='--', lw=1)
            ax_phase.plot(times, atmo_1_nm, label="Atmo In 1", color='C1', alpha=0.3, linestyle='--', lw=1)
            
            # Plot Relative Atmosphere (Thicker, solid dashed?)
            ax_phase.plot(times, atmo_diff_nm, label="Atmo Diff (1-0)", color='purple', alpha=0.8, linestyle='-', lw=1.5)
            
            # Plot Injection (Correction)
            ax_phase.plot(times, inj_1_nm, label="Inj In 1 (Corr)", color='green', alpha=0.8, linestyle='-', lw=1.5)
            
            ax_phase.set_ylabel("Phase (nm)")
            ax_phase.set_xlabel("Time (s)")
            ax_phase.set_ylim(0, wavelength*1e9)
            ax_phase.legend(loc='upper left', ncol=5)
            ax_phase.grid(True, alpha=0.3)
            ax_phase.set_title(f"Phase Contributions (Modulo {wavelength*1e9:.0f} nm)")
            
            plt.show()