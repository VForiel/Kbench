import numpy as np
import os
import json
import time
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .. import bmc

from ..utils import Singleton
from .config import Config

class DM(metaclass=Singleton):
    """
    Singleton Class to represent a deformable mirror (DM) in the optical system.

        Hardware ranges (bench reference)
        -------------------------------
        The DM has segment-dependent stroke limits. On the PHOBos bench, the injection
        segments typically used for coupling (e.g. around segments 111-114, 135-138,
        145-148 depending on the mapping in ``dm.injection_segments``) have piston
        ranges of roughly:

        - Segments 111-114: piston in [-2520, 264] nm (delta ~2784 nm)
        - Segments 145-148: piston in [-2557, 214] nm (delta ~2771 nm)
        - Segments 135-138: piston in [-2530, 230] nm (delta ~2760 nm)

        Tip/tilt ranges depend on the current piston working point. Around typical
        injection working pistons (-1128 nm / -1150 nm), absolute tip/tilt can reach
        approximately ±5.4 mrad in both axes. In normal operation, tip/tilt values
        are usually kept below ~1.5 mrad for alignment stability.

        Notes
        -----
        - For authoritative limits, always query the controller via
            :meth:`Segment.get_piston_range`, :meth:`Segment.get_tip_range`, and
            :meth:`Segment.get_tilt_range`.
        - Software-side safety clamping is applied in :meth:`Segment.set_piston`.

    Attributes
    ----------
    segments : list[Segment]
        List of segments of the DM.
    """

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "DM" / "DM_config.json"
    N_SEGMENTS = 169
    _initialized = False

    def __init__(self, config_path:str = DEFAULT_CONFIG_PATH):
        """
        Initialize the DM using global configuration.
        """

        # If already initialized, return existing instance
        if self._initialized:
            return
            
        self._initialized = True

        # Initialize the DM with the given serial number
        self.bmcdm = bmc.BmcDm()
        self.bmcdm.open_dm(Config().get('dm.serial_number'))
        self.segments = [Segment(i) for i in range(DM.N_SEGMENTS)]

        time.sleep(Config().get('dm.stabilization_time', 0.001))

    #  Specific methods -------------------------------------------------------

    def __iter__(self):
        """
        Iterate over the segments of the DM.
        
        Yields
        -------
        Segment
            The segments of the DM.
        """
        return iter(self.segments)

    def __getitem__(self, index) -> 'Segment':
        """
        Get a segment by its index.

        Parameters
        ----------
        index : int
            Index of the segment to get.
        Returns
        -------
        Segment
            The segment at the given index.
        """
        try:
            index = int(index)
        except ValueError:
            raise TypeError("Index must be an integer.")
        
        if index < 0 or index >= len(self.segments):
            raise IndexError("Index out of range.")
        
        return self.segments[index]
    
    def __len__(self) -> int:
        """
        Get the number of segments in the DM.

        Returns
        -------
        int
            The number of segments in the DM.
        """
        return len(self.segments)
    
    def __del__(self):
        """
        Close the DM connection when the object is deleted.
        """
        self.bmcdm.close_dm()
        for segment in self.segments:
            del segment
        print(f"DM with serial number {Config().get('dm.serial_number')} closed.")

    #Config -------------------------------------------------------------------

    def save_config(self, path:str = DEFAULT_CONFIG_PATH) -> None:
        """
        Save the current configuration of the DM.

        Parameters
        ----------
        path : str
            Path to the configuration file.
        """

        config = {
            "serial_number": Config().get('dm.serial_number'),
            "segments": {}
        }

        for segment in self.segments:
            config["segments"][segment.id] = {
                "piston": segment.piston,
                "tip": segment.tip,
                "tilt": segment.tilt
            }

        with open(path, 'w') as f:
            json.dump(config, f, indent=4)
        
        print(f"Configuration saved to {path}")

    def load_config(self, config_path:str = DEFAULT_CONFIG_PATH):
        """
        Load the configuration of the DM from a JSON file.

        Parameters
        ----------
        config_path : str
            Path to the configuration file.
        """

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        print(f"Loading config file: {config_path}.")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        for segment_id, segment_config in config["segments"].items():
            segment = self.segments[int(segment_id)]
            segment.set_ptt(segment_config["piston"], segment_config["tip"], segment_config["tilt"])
        
        print("Configuration loaded")

    def off(self, segments=None):
        """
        Turn off specified injection segments by applying maximum tilt.
        
        This tilts the segments to deflect light away from the photonic chip inputs.
        
        Parameters
        ----------
        segments : int, array-like, or None, optional
            Segment input number(s) to turn off (1-4 for the 4 injection inputs).
            - If int: single input number (e.g., 1 for first injection segment)
            - If array-like: multiple input numbers (e.g., [1, 2, 4])
            - If None: turns off all injection segments
            Default is None.
        
        Examples
        --------
        >>> dm = DM()
        >>> dm.off(1)           # Turn off first injection input
        >>> dm.off([1, 3])      # Turn off inputs 1 and 3
        >>> dm.off()            # Turn off all injection inputs
        
        Notes
        -----
        The off position is: piston=-1150 nm, tip=0 mrad, tilt=-5.47 mrad
        """
        # Parse segment indices
        if segments is None:
            # Turn off all injection segments
            seg_indices = Config().get('dm.injection_segments')
        else:
            # Convert input number(s) (1-4) to segment indices
            if isinstance(segments, int):
                segments = [segments]
            
            seg_indices = []
            for seg_num in segments:
                if not 1 <= seg_num <= len(Config().get('dm.injection_segments')):
                    raise ValueError(f"Segment number must be between 1 and {len(Config().get('dm.injection_segments'))}, got {seg_num}")
                seg_indices.append(Config().get('dm.injection_segments')[seg_num - 1])
        
        # Apply off position to selected segments
        for seg_idx in seg_indices:
            self.segments[seg_idx].set_ptt(-1150, 0, -5.47)
        
        print(f"Turned off injection segments: {seg_indices}")

    def _parse_injection_segments(self, segments: Optional[Union[int, Sequence[int]]]=None) -> List[int]:
        """Parse user-facing injection input numbers into DM segment indices.

        Parameters
        ----------
        segments : int, sequence of int, or None
            Injection input number(s) (1..N) or None for all injection segments.

        Returns
        -------
        list[int]
            DM segment indices.
        """

        if segments is None:
            segments=np.array([1,2,3,4])

        injection_segments = Config().get('dm.injection_segments')

        if isinstance(segments, int):
            segments_list = [segments]
        else:
            segments_list = list(segments)

        seg_indices: List[int] = []
        for seg_num in segments_list:
            if not 1 <= int(seg_num) <= len(injection_segments):
                raise ValueError(
                    f"Segment number must be between 1 and {len(injection_segments)}, got {seg_num}"
                )
            seg_indices.append(injection_segments[int(seg_num) - 1])
        return seg_indices

    def _get_ptt_map(self, key: str) -> Dict[str, List[float]]:
        """Return a PTT mapping from config.

        Parameters
        ----------
        key : str
            Config key under `dm.*` (e.g. `dm.ptt_max`, `dm.ptt_balanced`).

        Returns
        -------
        dict
            Mapping from segment index (as string) to `[piston_nm, tip_mrad, tilt_mrad]`.
        """
        import phobos

        data = phobos.config.get(key, {})
        return data if isinstance(data, dict) else {}

    def _set_ptt_map(self, key: str, value: Dict[str, List[float]], autosave: bool = True) -> None:
        """Persist a PTT mapping to config.

        Parameters
        ----------
        key : str
            Config key under `dm.*`.
        value : dict
            Mapping from segment index (as string) to `[piston_nm, tip_mrad, tilt_mrad]`.
        autosave : bool, optional
            If True, persist immediately. If False, only update the in-memory
            config cache (useful to batch multiple updates without creating many backups).
        """
        import phobos

        phobos.config.set(key, value, autosave=autosave)

    def _measure_total_output_flux(self) -> float:
        """Measure total injected flux as sum over all camera outputs.

        Returns
        -------
        float
            Total flux (arbitrary units).
        """
        import phobos

        outs = phobos.Cred3().get_outputs(flux_mode='sum')
        return float(np.sum(outs))

    def _grid_search_tip_tilt(
        self,
        seg_idx: int,
        tip_grid: np.ndarray,
        tilt_grid: np.ndarray,
        objective: Callable[[float], float],
        piston: float = 0.0,
        settle_time_s: float = 0.0,
        plot: bool = False,
        label: str = "",
    ) -> Tuple[float, float, float, Optional[np.ndarray]]:
        """Brute-force grid search for (tip, tilt) that maximizes an objective.

        Notes
        -----
        - `tip_grid` and `tilt_grid` are in mrad.
        - `objective` is called with measured total flux.
        - Returns values in the same units expected by `Segment.set_ptt` (mrad).
        """
        flux_map = np.full((len(tip_grid), len(tilt_grid)), np.nan, dtype=float)

        best_score = -np.inf
        best_tip = 0.0
        best_tilt = 0.0
        best_flux = np.nan

        # Preserve current state to restore later
        p0, t0, tt0 = self.segments[seg_idx].get_ptt()

        try:
            for i, tip in enumerate(tip_grid):
                for j, tilt in enumerate(tilt_grid):
                    self.segments[seg_idx].set_ptt(piston, float(tip), float(tilt))
                    if settle_time_s > 0:
                        time.sleep(settle_time_s)
                    flux = self._measure_total_output_flux()
                    score = float(objective(flux))
                    flux_map[i, j] = flux
                    if score > best_score:
                        best_score = score
                        best_tip = float(tip)
                        best_tilt = float(tilt)
                        best_flux = float(flux)
        finally:
            # restore
            self.segments[seg_idx].set_ptt(p0, t0, tt0)

        if plot:
            try:
                import matplotlib.pyplot as plt
                from mpl_toolkits.axes_grid1 import make_axes_locatable

                plt.figure(figsize=(6, 5))
                plt.title(label or f"Injection segment {seg_idx}: flux map")
                plt.imshow(
                    flux_map.T,
                    origin='lower',
                    aspect='auto',
                    extent=[tip_grid[0], tip_grid[-1], tilt_grid[0], tilt_grid[-1]],
                )
                plt.xlabel("tip (mrad)")
                plt.ylabel("tilt (mrad)")
                plt.colorbar(label="total output flux")
                plt.scatter([best_tip], [best_tilt], c='w', s=50)
                plt.tight_layout()
                plt.show()
            except Exception as e:
                print(f"⚠️ Plot skipped: {e}")

        return best_tip, best_tilt, best_flux, (flux_map if plot else None)
    
    def zero(self, segments=None):
        """Reset specified injection segments to zero (piston=0, tip=0, tilt=0).
        
        This returns the segments to their nominal position for maximum light coupling.
        
        Parameters
        ----------
        segments : int, array-like, or None, optional
            Segment input number(s) to optimize (1-4 for the 4 injection inputs).
            - If int: single input number (e.g., 1 for first injection segment)
            - If array-like: multiple input numbers (e.g., [1, 2, 4])
            - If None: optimizes all injection segments
            Default is None.
        
        Examples
        --------
        >>> dm = DM()
        >>> dm.zero(1)          # Flatten first injection input
        >>> dm.zero([1, 3])     # Flatten inputs 1 and 3
        >>> dm.zero()           # Flatten all injection inputs
        """
        seg_indices = self._parse_injection_segments(segments)
        
        # Apply flat position to selected segments
        for seg_idx in seg_indices:
            self.segments[seg_idx].set_ptt(0, 0, 0)

        print(f"Flattened injection segments: {seg_indices}")

    def flat(self, segments=None):
        """Reset specified injection segments to flat (piston=mean piston, tip=0, tilt=0).
        
        This returns the segments to their nominal position for maximum light coupling.
        
        Parameters
        ----------
        segments : int, array-like, or None, optional
            Segment input number(s) to optimize (1-4 for the 4 injection inputs).
            - If int: single input number (e.g., 1 for first injection segment)
            - If array-like: multiple input numbers (e.g., [1, 2, 4])
            - If None: optimizes all injection segments
            Default is None.
        
        Examples
        --------
        >>> dm = DM()
        >>> dm.flat(1)          # Flatten first injection input
        >>> dm.flat([1, 3])     # Flatten inputs 1 and 3
        >>> dm.flat()           # Flatten all injection inputs
        
        Notes
        -----
        The flat position is: piston=0 nm, tip=0 mrad, tilt=0 mrad
        """
        seg_indices = self._parse_injection_segments(segments)

        mean_piston = np.mean(Config().get('dm.injection_piston_nm'))
        
        # Apply flat position to selected segments
        for seg_idx in seg_indices:
            self.segments[seg_idx].set_ptt(mean_piston, 0, 0)

        print(f"Flattened injection segments: {seg_indices}")

    def max(self, segments=None):
        """Apply stored 'max' injection calibration (tip/tilt) for selected segments.

        Parameters
        ----------
        segments : int, array-like, or None
            Injection input number(s) (1..N), or None for all injection segments.
        """
        seg_indices = self._parse_injection_segments(segments)
        max_map = self._get_ptt_map('dm.ptt_max')

        if not max_map:
            raise RuntimeError(
                "No 'max' injection calibration found. Run DM().calibrate_injection() first."
            )

        for seg_idx in seg_indices:
            ptt = max_map.get(str(seg_idx))
            if ptt is None:
                raise KeyError(f"No 'max' calibration for segment {seg_idx}")
            self.segments[seg_idx].set_ptt(float(ptt[0]), float(ptt[1]), float(ptt[2]))

        print(f"Applied MAX injection calibration on segments: {seg_indices}")

    def calibrate_injection(
        self,
        plot: bool = False,
        grid_n: int = 20,
        tip_range_mrad: float = 2.0,
        tilt_range_mrad: float = 2.0,
        piston_nm: float = -1150.0,
        verbose: bool = False,
        use_tqdm: bool = True,
    ) -> Dict[str, object]:
        """Calibrate injection tip/tilt settings.

        This routine calibrates tip/tilt for all injection segments defined in
                `dm.injection_segments`.

                Two calibrations are produced:
                - `max`: find the maximum-injection tip/tilt point using a centroid estimate
                    of the injection map.
                - `balanced`: choose the weakest segment (based on its `max` flux) as reference
                    and, for each other segment, select the point along the line from (0, 0)
                    to `tt_max` where the injected flux matches the reference flux.

        Parameters
        ----------
        plot : bool, optional
            If True, plot injection maps for each segment. Default is False.
        grid_n : int, optional
            Number of grid points per axis for the tip/tilt scan. Default is 20.
        tip_range_mrad : float, optional
            Tip scan range is [-tip_range_mrad, tip_range_mrad]. Default is 2.
        tilt_range_mrad : float, optional
            Tilt scan range is [-tilt_range_mrad, tilt_range_mrad]. Default is 2.
        piston_nm : float, optional
            Fixed piston value during calibration (nm). Default is -1150.
        verbose : bool, optional
            If True, print centroid and balanced-point computations. Default is False.
        use_tqdm : bool, optional
            If True, show a tqdm progress bar when tqdm is available. Default is True.

        Notes
        -----
        - A single scan is performed per segment (default 20x20 points).
        - The scan range is typically [-2, 2] mrad for both tip and tilt.
        - Piston is kept fixed at `dm.injection_piston_nm` (default -1150 nm).

        Returns
        -------
        dict
            A dict with keys `max` and `balanced`, each mapping segment indices to
            `[piston, tip, tilt]` values (piston in nm, tip/tilt in mrad).
        """
        import phobos

        injection_seg_indices = self._parse_injection_segments(None)

        # Start from a known safe baseline
        self.off(None)
        time.sleep(Config().get('dm.stabilization_time', 0.01))

        # We generally keep piston at the injection working point and scan only tip/tilt.
        # Use explicit parameters; config keys can still be used by callers
        # by passing values from Config().get(...).
        injection_piston_nm = float(piston_nm)
        settle_time_s = float(Config().get('dm.stabilization_time', 0.01))

        # Local helpers: centroid + balanced point along ray
        def _centroid_tip_tilt(
            flux_map: np.ndarray,
            tip_vals: np.ndarray,
            tilt_vals: np.ndarray,
        ) -> Tuple[float, float]:
            w = np.asarray(flux_map, dtype=float)
            w = np.clip(w, 0.0, None)
            s = float(np.sum(w))
            if not np.isfinite(s) or s <= 0:
                return 0.0, 0.0

            tip_grid2d, tilt_grid2d = np.meshgrid(tip_vals, tilt_vals, indexing='ij')
            tip_c = float(np.sum(w * tip_grid2d) / s)
            tilt_c = float(np.sum(w * tilt_grid2d) / s)
            return tip_c, tilt_c

        def _flux_on_ray(
            flux_map: np.ndarray,
            tip_vals: np.ndarray,
            tilt_vals: np.ndarray,
            tip_max: float,
            tilt_max: float,
            s_min: float = -1.0,
            s_max: float = 1.0,
        ) -> Tuple[np.ndarray, np.ndarray]:
            # We scan along the line crossing the origin and tt_max.
            # Using s in [-1, 1] allows solutions on either side of (0,0).
            s_vals = np.linspace(float(s_min), float(s_max), max(len(tip_vals), len(tilt_vals)))
            # nearest-neighbour sampling on the map
            tip_idx = np.clip(np.round((s_vals * tip_max - tip_vals[0]) / (tip_vals[-1] - tip_vals[0]) * (len(tip_vals) - 1)).astype(int), 0, len(tip_vals) - 1)
            tilt_idx = np.clip(np.round((s_vals * tilt_max - tilt_vals[0]) / (tilt_vals[-1] - tilt_vals[0]) * (len(tilt_vals) - 1)).astype(int), 0, len(tilt_vals) - 1)
            flux_s = flux_map[tip_idx, tilt_idx]
            return s_vals, flux_s

        def _bilinear_interpolate(
            values: np.ndarray,
            x_axis: np.ndarray,
            y_axis: np.ndarray,
            x: float,
            y: float,
        ) -> float:
            """Bilinear interpolation on a regular grid.

            Parameters
            ----------
            values : np.ndarray
                Array with shape (len(x_axis), len(y_axis)).
            x_axis, y_axis : np.ndarray
                Monotonic axes corresponding to values indices.
            x, y : float
                Query point.

            Returns
            -------
            float
                Interpolated value.
            """
            x0 = float(x_axis[0])
            x1 = float(x_axis[-1])
            y0 = float(y_axis[0])
            y1 = float(y_axis[-1])

            if x1 == x0 or y1 == y0:
                return float('nan')

            # Clamp to grid bounds
            xc = float(np.clip(x, x0, x1))
            yc = float(np.clip(y, y0, y1))

            # Fractional index coordinates
            fx = (xc - x0) / (x1 - x0) * (len(x_axis) - 1)
            fy = (yc - y0) / (y1 - y0) * (len(y_axis) - 1)
            ix0 = int(np.floor(fx))
            iy0 = int(np.floor(fy))
            ix1 = int(np.clip(ix0 + 1, 0, len(x_axis) - 1))
            iy1 = int(np.clip(iy0 + 1, 0, len(y_axis) - 1))
            ix0 = int(np.clip(ix0, 0, len(x_axis) - 1))
            iy0 = int(np.clip(iy0, 0, len(y_axis) - 1))
            tx = float(fx - ix0)
            ty = float(fy - iy0)

            v00 = float(values[ix0, iy0])
            v10 = float(values[ix1, iy0])
            v01 = float(values[ix0, iy1])
            v11 = float(values[ix1, iy1])
            # Blend
            v0 = (1.0 - tx) * v00 + tx * v10
            v1 = (1.0 - tx) * v01 + tx * v11
            return (1.0 - ty) * v0 + ty * v1

        def _balanced_on_ray(
            flux_map: np.ndarray,
            tip_vals: np.ndarray,
            tilt_vals: np.ndarray,
            tip_max: float,
            tilt_max: float,
            target_flux: float,
        ) -> Tuple[float, float, float]:
            # Sample a dense 1D profile along the tt_0->tt_max line.
            # We interpret this 1D profile as (approximately) Gaussian-shaped.
            n_s = int(max(200, 10 * max(len(tip_vals), len(tilt_vals))))
            s_vals = np.linspace(-1.0, 1.0, n_s)
            tip_s = s_vals * float(tip_max)
            tilt_s = s_vals * float(tilt_max)
            flux_s = np.array(
                [
                    _bilinear_interpolate(flux_map, tip_vals, tilt_vals, float(tx), float(ty))
                    for tx, ty in zip(tip_s, tilt_s)
                ],
                dtype=float,
            )

            # Fallback (closest sample) in case the fit fails.
            def _fallback() -> Tuple[float, float, float]:
                idx0 = int(np.nanargmin(np.abs(flux_s - target_flux)))
                tip_b0 = float(tip_s[idx0])
                tilt_b0 = float(tilt_s[idx0])
                return tip_b0, tilt_b0, float(flux_s[idx0])

            if not np.any(np.isfinite(flux_s)):
                return _fallback()

            # Estimate Gaussian parameters in log-space: log(f) = log(A) - (s-mu)^2/(2*sigma^2)
            # We only use positive flux samples for log.
            mask = np.isfinite(flux_s) & (flux_s > 0)
            if np.count_nonzero(mask) < 6:
                return _fallback()

            y = np.log(flux_s[mask])
            x = s_vals[mask]

            # Quadratic fit y ~= c2*x^2 + c1*x + c0
            try:
                c2, c1, c0 = np.polyfit(x, y, deg=2)
            except Exception:
                return _fallback()

            # For a Gaussian, c2 should be negative.
            if not np.isfinite(c2) or c2 >= 0:
                return _fallback()

            # Recover mu, sigma, A
            mu = float(-c1 / (2.0 * c2))
            sigma = float(np.sqrt(-1.0 / (2.0 * c2)))
            if not np.isfinite(mu) or not np.isfinite(sigma) or sigma <= 0:
                return _fallback()

            logA = float(c0 - (c1 * c1) / (4.0 * c2))
            A = float(np.exp(logA))
            if not np.isfinite(A) or A <= 0:
                return _fallback()

            # Solve A * exp(-(s-mu)^2/(2*sigma^2)) = target_flux
            if target_flux <= 0 or target_flux > A:
                # target above fitted peak (or invalid) -> closest sample fallback
                return _fallback()

            rhs = -2.0 * sigma * sigma * float(np.log(float(target_flux) / A))
            if rhs < 0:
                return _fallback()

            delta = float(np.sqrt(rhs))
            candidates = [mu - delta, mu + delta]
            # Pick candidate within [-1,1] closest to the tt_max side (s=+1)
            cand_in = [s for s in candidates if -1.0 <= s <= 1.0]
            if not cand_in:
                return _fallback()

            s_star = float(min(cand_in, key=lambda s: abs(1.0 - s)))
            tip_b = float(s_star * tip_max)
            tilt_b = float(s_star * tilt_max)
            flux_b = float(A * np.exp(-((s_star - mu) ** 2) / (2.0 * sigma * sigma)))
            return tip_b, tilt_b, flux_b

        # Scan parameters (single scan per segment)
        tip_grid = np.linspace(-float(tip_range_mrad), float(tip_range_mrad), int(grid_n))
        tilt_grid = np.linspace(-float(tilt_range_mrad), float(tilt_range_mrad), int(grid_n))

        # Optional tqdm progress bar
        iterator = injection_seg_indices
        if use_tqdm:
            try:
                from tqdm import tqdm  # type: ignore

                iterator = tqdm(injection_seg_indices, desc="Calibrating injection", leave=True)
            except Exception:
                iterator = injection_seg_indices

        flux_maps: Dict[int, np.ndarray] = {}
        max_ptt: Dict[str, List[float]] = {}
        balanced_ptt: Dict[str, List[float]] = {}

        tt_max: Dict[int, Tuple[float, float]] = {}
        flux_at_max: Dict[int, float] = {}

        # --- Single scan per segment ---
        for seg_idx in iterator:
            self.off(None)
            self.segments[seg_idx].set_ptt(injection_piston_nm, 0.0, 0.0)
            time.sleep(settle_time_s)

            # Build the flux map
            flux_map = np.full((len(tip_grid), len(tilt_grid)), np.nan, dtype=float)
            for i, tip in enumerate(tip_grid):
                for j, tilt in enumerate(tilt_grid):
                    self.segments[seg_idx].set_ptt(injection_piston_nm, float(tip), float(tilt))
                    if settle_time_s > 0:
                        time.sleep(settle_time_s)
                    flux_map[i, j] = self._measure_total_output_flux()

            flux_maps[seg_idx] = flux_map

            # tt_max from centroid of the "gaussian-like" lobe
            tip_c, tilt_c = _centroid_tip_tilt(flux_map, tip_grid, tilt_grid)
            # snap to nearest sample for flux readout
            i0 = int(np.nanargmin(np.abs(tip_grid - tip_c)))
            j0 = int(np.nanargmin(np.abs(tilt_grid - tilt_c)))
            flux_c = float(flux_map[i0, j0])

            tt_max[seg_idx] = (float(tip_grid[i0]), float(tilt_grid[j0]))
            flux_at_max[seg_idx] = flux_c
            max_ptt[str(seg_idx)] = [float(injection_piston_nm), float(tip_grid[i0]), float(tilt_grid[j0])]

            if verbose:
                print(f"[calibrate_injection] seg={seg_idx}: centroid->(tip,tilt)=({tip_c:.3f},{tilt_c:.3f}) mrad; snapped=({tip_grid[i0]:.3f},{tilt_grid[j0]:.3f}); flux_max={flux_c:.3g}")

        # Reference is the weakest segment at its max point
        if len(flux_at_max) == 0:
            raise RuntimeError("No injection segments found for calibration")
        ref_seg = min(flux_at_max, key=lambda k: flux_at_max[k])
        ref_flux = float(flux_at_max[ref_seg])

        flux_at_balanced: Dict[int, float] = {}
        for seg_idx in injection_seg_indices:
            tip_m, tilt_m = tt_max[seg_idx]
            if seg_idx == ref_seg:
                balanced_ptt[str(seg_idx)] = list(max_ptt[str(seg_idx)])
                flux_at_balanced[seg_idx] = float(flux_at_max[seg_idx])
                continue

            tip_b, tilt_b, flux_b = _balanced_on_ray(
                flux_map=flux_maps[seg_idx],
                tip_vals=tip_grid,
                tilt_vals=tilt_grid,
                tip_max=tip_m,
                tilt_max=tilt_m,
                target_flux=ref_flux,
            )
            balanced_ptt[str(seg_idx)] = [float(injection_piston_nm), float(tip_b), float(tilt_b)]
            flux_at_balanced[seg_idx] = float(flux_b)

            if verbose:
                print(f"[calibrate_injection] seg={seg_idx}: balanced on ray to match ref_flux={ref_flux:.3g} -> (tip,tilt)=({tip_b:.3f},{tilt_b:.3f}) mrad; flux_bal={flux_b:.3g}")

        fig = None
        if plot:
            try:
                import matplotlib.pyplot as plt
                from mpl_toolkits.axes_grid1 import make_axes_locatable

                ncols = len(injection_seg_indices)
                fig, axes = plt.subplots(1, ncols, figsize=(4.5 * ncols, 4.5), squeeze=False)
                fig.suptitle("Injection calibration maps", y=1.02)

                im_for_cbar = None

                for col, seg_idx in enumerate(injection_seg_indices):
                    ax = axes[0, col]
                    flux_map = flux_maps[seg_idx]
                    im = ax.imshow(
                        flux_map.T,
                        origin='lower',
                        aspect='auto',
                        extent=[tip_grid[0], tip_grid[-1], tilt_grid[0], tilt_grid[-1]],
                    )
                    if im_for_cbar is None:
                        im_for_cbar = im
                    ax.set_title(f"seg {seg_idx}")
                    ax.set_xlabel("tip (mrad)")
                    ax.set_ylabel("tilt (mrad)")

                    tip_m, tilt_m = tt_max[seg_idx]
                    tip_b = float(balanced_ptt[str(seg_idx)][1])
                    tilt_b = float(balanced_ptt[str(seg_idx)][2])

                    # Markers / line conventions:
                    # - tt_0: cross at (0,0)
                    # - tt_max: triangle
                    # - tt_bal: circle
                    # - Ray: red dashed line
                    f_m = float(flux_at_max[seg_idx])
                    f_b = float(flux_at_balanced[seg_idx])

                    # Flux at tt_0 is the map value at the nearest grid point to (0, 0)
                    i00 = int(np.nanargmin(np.abs(tip_grid - 0.0)))
                    j00 = int(np.nanargmin(np.abs(tilt_grid - 0.0)))
                    f_0 = float(flux_map[i00, j00])

                    ax.scatter([0.0], [0.0], marker='x', c='w', s=60, label=f"tt_0 (f={f_0:.3g})")
                    ax.scatter([tip_m], [tilt_m], marker='^', c='w', s=60, label=f"tt_max (f={f_m:.3g})")
                    ax.plot([0.0, tip_m], [0.0, tilt_m], color='r', linestyle='--', linewidth=1.8, alpha=0.9)
                    ax.scatter([tip_b], [tilt_b], marker='o', c='w', s=55, label=f"tt_bal (f={f_b:.3g})")

                    ax.legend(loc='upper right', framealpha=0.7)

                # Shared colorbar placed at the far right of the whole row
                if im_for_cbar is not None:
                    divider = make_axes_locatable(axes[0, -1])
                    cax = divider.append_axes("right", size="4%", pad=0.15)
                    fig.colorbar(im_for_cbar, cax=cax, label="total output flux")

                plt.tight_layout()
                plt.show()
            except Exception as e:
                print(f"⚠️ Plot skipped: {e}")

        # Persist only the calibrated PTT maps as requested.
        # Batch updates to avoid creating multiple backups.
        self._set_ptt_map('dm.ptt_max', max_ptt, autosave=False)
        self._set_ptt_map('dm.ptt_balanced', balanced_ptt, autosave=False)

        # Single save at the end
        phobos.config.save_to_file()

        print("✅ Injection calibration saved to config under dm.ptt_max and dm.ptt_balanced")
        return {'max': max_ptt, 'balanced': balanced_ptt, 'figure': fig}

    def balanced(self, segments=None):
        """Apply stored 'balanced' injection calibration (tip/tilt) for selected segments.

        Parameters
        ----------
        segments : int, array-like, or None
            Injection input number(s) (1..N), or None for all injection segments.
        """
        seg_indices = self._parse_injection_segments(segments)
        bal_map = self._get_ptt_map('dm.ptt_balanced')

        if not bal_map:
            raise RuntimeError(
                "No 'balanced' injection calibration found. Run DM().calibrate_injection() first."
            )

        for seg_idx in seg_indices:
            ptt = bal_map.get(str(seg_idx))
            if ptt is None:
                raise KeyError(f"No 'balanced' calibration for segment {seg_idx}")
            self.segments[seg_idx].set_ptt(float(ptt[0]), float(ptt[1]), float(ptt[2]))

        print(f"Applied BALANCED injection calibration on segments: {seg_indices}")

    # Backward compatibility: previous API used max() for flat.
    def max_flat(self, segments=None):
        """Deprecated alias for :meth:`flat` (kept for backward compatibility)."""
        import warnings

        warnings.warn(
            "DM.max_flat() is deprecated; use DM.flat() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.flat(segments)

#==============================================================================
# Segment class
#==============================================================================

class Segment():
    """
    Class to represent a segment of the deformable mirror (DM).

    Attributes
    ----------
    dm : DM
        The DM to which the segment belongs.
    id : int
        The ID of the segment.
    piston : float
        The piston value of the segment in nm.
    tip : float
        The tip value of the segment in milliradians.
    tilt : float
        The tilt value of the segment in milliradians.
    """

    __slots__ = ['id', 'piston', 'tip', 'tilt']

    _instances = {}

    # Constructors ------------------------------------------------------------

    def __new__(cls, id: int, *args, **kwargs):

        # Check if channel is valid
        if not (0 <= id <= DM.N_SEGMENTS):
             raise ValueError(f"❌ Invalid channel number {id}. Must be between 1 and {DM.N_SEGMENTS}.")
             
        # Return cached instance if it exists
        if id not in cls._instances:
            cls._instances[id] = super(Segment, cls).__new__(cls)

        return cls._instances[id]

    def __init__(self, id:int):
        """
        Initialize the segment with the given DM and ID.

        Parameters
        ----------
        id : int
            The ID of the segment.
        """

        # If already initialized (from cache), skip
        if hasattr(self, 'id'):
            return

        self.id = id
        self.piston = 0
        self.tip = 0
        self.tilt = 0

    # piston ------------------------------------------------------------------

    def set_piston(self, value) -> str:
        """
        Set the piston value of the segment.

        Parameters
        ----------
        value : float
            The piston value to set in nm.

        Returns
        -------
        str
            The response of the mirror.
        """
        # Clamp to hardware limits (query current range because it can depend on
        # the current segment state).
        try:
            p_min, p_max = self.get_piston_range()
            value = float(np.clip(float(value), float(p_min), float(p_max)))
        except Exception:
            # If range query fails (e.g. sandbox/mock), proceed without clamping.
            value = float(value)

        self.piston = value
        response = DM().bmcdm.set_segment(self.id, value, self.tip, self.tilt, True, True)
        time.sleep(Config().get('dm.stabilization_time'))  # Stabilization delay for BMC hardware
        return response

    def set_phase(self, phase: float, lam: float = 1550.0) -> str:
        """Set the segment piston using a phase command.

        This converts a phase (radians) into an optical path difference expressed
        as a segment piston (nm). The command uses the configured piston range
        to define the phase origin and direction:

        - phase 0 rad corresponds to the center of the piston range,
          i.e. mean(``Config().get('dm.piston_range')``)
        - phase in [0, pi] moves the piston more negative ("recedes")
        - phase in (pi, 2*pi) moves the piston more positive ("advances")

        The phase is first wrapped modulo 2*pi.

        Parameters
        ----------
        phase : float
            Phase command in radians.
        lam : float, optional
            Wavelength in nanometers. Default is 1550.

        Returns
        -------
        str
            Hardware response string from the DM controller.

        Warns
        -----
        UserWarning
            If the target piston is outside the configured piston range.
        """
        lam_nm = float(lam)
        phi = float(phase) % (2 * np.pi)

        pr = Config().get('dm.piston_range')
        if pr is None or len(pr) != 2:
            raise ValueError("Config key 'dm.piston_range' must be a 2-element list [min_nm, max_nm]")

        p_min, p_max = float(pr[0]), float(pr[1])
        p0 = int(0.5 * (p_min + p_max))

        # Map phase to piston offset in [-lam/2, +lam/2)
        # so that 0..pi produces negative offset and pi..2pi produces positive.
        delta_nm = -((phi / (2 * np.pi)) * lam_nm)
        if phi > np.pi:
            delta_nm = lam_nm - ((phi / (2 * np.pi)) * lam_nm)

        piston_target = p0 + float(delta_nm)

        if piston_target < p_min or piston_target > p_max:
            warnings.warn(
                f"Requested piston {piston_target:.1f} nm is outside configured range [{p_min:.1f}, {p_max:.1f}] nm for segment {self.id}.",
                UserWarning,
                stacklevel=2,
            )

        return self.set_piston(piston_target)
    
    def get_piston(self) -> float:
        """
        Get the piston value of the segment.

        Returns
        -------
        float
            The piston value of the segment in nm.
        """
        return self.piston

    def get_piston_range(self) -> list[float]:
        """
        Get the piston range of the segment.

        Returns
        -------
        list[float]
            The piston range ([min, max]) of the segment in nm.
        """
        return DM().bmcdm.get_segment_range(self.id, bmc.DM_Piston, self.piston, self.tip, self.tilt, True)

    # tip ---------------------------------------------------------------------

    def set_tip(self, value: float) -> str:
        """
        Set the tip value of the segment.

        Parameters
        ----------
        value : float
            The tip value to set in milliradians.

        Returns
        -------
        str
            The response of the mirror.
        """
        self.tip = value / 1000.0
        response = DM().bmcdm.set_segment(self.id, self.piston, self.tip, self.tilt, True, True)
        time.sleep(Config().get('dm.stabilization_time'))  # Stabilization delay for BMC hardware
        return response

    def get_tip(self) -> float:
        """
        Get the tip value of the segment.

        Returns
        -------
        float
            The tip value of the segment in milliradians.
        """
        return self.tip * 1000.0

    def get_tip_range(self) -> list[float]:
        """
        Get the tip range of the segment.

        Returns
        -------
        list[float]
            The tip range ([min, max]) of the segment in radians.
        """
        return DM().bmcdm.get_segment_range(self.id, bmc.DM_XTilt, self.piston, self.tip, self.tilt, True)

    # tilt --------------------------------------------------------------------

    def set_tilt(self, value: float) -> str:
        """
        Set the tilt value of the segment.

        Parameters
        ----------
        value : float
            The tilt value to set in milliradians.

        Returns
        -------
        str
            The response of the mirror.
        """
        self.tilt = value / 1000.0
        response = DM().bmcdm.set_segment(self.id, self.piston, self.tip, self.tilt, True, True)
        time.sleep(Config().get('dm.stabilization_time'))  # Stabilization delay for BMC hardware
        return response

    def get_tilt(self) -> float:
        """
        Get the tilt value of the segment.

        Returns
        -------
        float
            The tilt value of the segment in milliradians.
        """
        return self.tilt * 1000.0

    def get_tilt_range(self) -> list[float]:
        """
        Get the tilt range of the segment.

        Returns
        -------
        list[float]
            The tilt range ([min, max]) of the segment in radians.
        """
        return DM().bmcdm.get_segment_range(self.id, bmc.DM_YTilt, self.piston, self.tip, self.tilt, True)

    # ptt ---------------------------------------------------------------------

    def set_ptt(self, piston: float, tip: float, tilt: float) -> tuple[str]:
        """
        Get the tip-tilt value of the segment.

        Parameters
        ----------
        piston : float
            The piston value to set in nm.
        tip : float
            The tip value to set in milliradians.
        tilt : float
            The tilt value to set in milliradians.

        Returns
        -------
        str
            The response of the mirror for the piston change.
        str
            The response of the mirror for the tip change.
        str
            The response of the mirror for the tilt change.
        """
        tip = tip / 1000.
        tilt = tilt / 1000.
        self.piston = piston
        self.tip = tip
        self.tilt = tilt
        response = DM().bmcdm.set_segment(self.id, self.piston, self.tip, self.tilt, True, True)
        time.sleep(Config().get('dm.stabilization_time'))  # Stabilization delay for BMC hardware
        return response        

    def get_ptt(self) -> tuple[float, float, float]:
        """
        Get the tip-tilt value of the segment.

        Returns
        -------
        float
            The piston value of the segment in nm.
        float
            The tip value of the segment in milliradians.
        float
            The tilt value of the segment in milliradians.
        """
        
        # Inline conversion faster than method calls
        return self.piston, self.tip * 1000.0, self.tilt * 1000.0