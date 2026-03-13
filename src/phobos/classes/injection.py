"""
High-level injection control.

This module provides the :class:`Injection` singleton, which abstracts away
raw DM segment IDs and lets the user work with **input channel numbers**
(0 … N-1).  The mapping from channel number to physical DM segment is read from
the bench configuration key ``injection.segments``.

Typical workflow
----------------
>>> from phobos.classes.injection import Injection
>>> inj = Injection()
>>> result = inj.calibrate()   # scan & calibrate
>>> inj.max()                            # apply max-injection positions
>>> inj.balanced()                       # equalise all inputs
>>> inj.off()                            # park all inputs
"""

import time
import warnings
from copy import deepcopy as copy
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

from ..utils import Singleton
from .config import Config
from .cred3 import Cred3
from .deformable_mirror import DM


class Injection(metaclass=Singleton):
    """Singleton for high-level photonic-chip injection control.

    All public methods accept *channel* numbers (0-based) that are mapped to
    DM segment indices via ``Config().get('injection.segments')``.

    Attributes
    ----------
    dm : DM
        Reference to the underlying DM singleton.
    """

    _initialized = False

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.dm = DM()

    # -- helpers --------------------------------------------------------------

    @property
    def _injection_segments(self) -> List[int]:
        """Return the list of DM segment indices used for injection."""
        return Config().get('injection.segments')

    @property
    def n_channels(self) -> int:
        """Number of injection channels."""
        return len(self._injection_segments)

    def _parse_channels(
        self,
        channels: Optional[Union[int, Sequence[int]]] = None,
    ) -> List[int]:
        """Convert user-facing channel numbers (0-based) to DM segment indices.

        Parameters
        ----------
        channels : int, sequence of int, or None
            Channel number(s).  ``None`` selects all channels.

        Returns
        -------
        list[int]
            Corresponding DM segment indices.
        """
        injection_segments = self._injection_segments

        if channels is None:
            channels = list(range(len(injection_segments)))
        elif isinstance(channels, (int, np.integer)):
            channels = [int(channels)]
        else:
            channels = [int(c) for c in channels]

        seg_indices: List[int] = []
        for ch in channels:
            if not 0 <= ch < len(injection_segments):
                raise ValueError(
                    f"Channel number must be between 0 and "
                    f"{len(injection_segments) - 1}, got {ch}"
                )
            seg_indices.append(injection_segments[ch])
        return seg_indices

    def _channel_for_segment(self, seg_idx: int) -> int:
        """Return the 0-based channel number for a DM segment index."""
        return self._injection_segments.index(seg_idx)

    # -- preset positions -----------------------------------------------------

    def off(self, channels=None) -> None:
        """Turn off injection by tilting segments away from the chip inputs.

        Parameters
        ----------
        channels : int, array-like, or None, optional
            Channel number(s) (0-based) to turn off, or ``None`` for all.

        Notes
        -----
        The off position is: piston = mean(piston_range), tip = 0 mrad,
        tilt = ``dm.tilt_range[0]`` (max negative tilt to deflect light).
        """
        seg_indices = self._parse_channels(channels)
        piston = DM().mid_piston
        off_tilt = float(Config().get('dm.tilt_range', [-5.47, 5.0])[0])

        for seg_idx in seg_indices:
            self.dm.segments[seg_idx].set_ptt(piston, 0.0, off_tilt)

        print(f"Injection OFF on channels "
              f"{[self._channel_for_segment(s) for s in seg_indices]} "
              f"(segments {seg_indices})")

    def flat(self, channels=None) -> None:
        """Reset injection segments to flat position (zero tip/tilt).

        Parameters
        ----------
        channels : int, array-like, or None, optional
            Channel number(s) (0-based), or ``None`` for all.

        Notes
        -----
        Flat position is: piston = mean(piston_range), tip = 0, tilt = 0.
        """
        seg_indices = self._parse_channels(channels)
        piston = float(np.mean(Config().get('dm.piston_range')))

        for seg_idx in seg_indices:
            self.dm.segments[seg_idx].set_ptt(piston, 0.0, 0.0)

        print(f"Injection FLAT on channels "
              f"{[self._channel_for_segment(s) for s in seg_indices]} "
              f"(segments {seg_indices})")

    def zero(self, channels=None) -> None:
        """Reset injection segments to zero (piston=0, tip=0, tilt=0).

        Parameters
        ----------
        channels : int, array-like, or None, optional
            Channel number(s) (0-based), or ``None`` for all.
        """
        seg_indices = self._parse_channels(channels)

        for seg_idx in seg_indices:
            self.dm.segments[seg_idx].set_ptt(0.0, 0.0, 0.0)

        print(f"Injection ZERO on channels "
              f"{[self._channel_for_segment(s) for s in seg_indices]} "
              f"(segments {seg_indices})")

    def set_max(self, channels=None) -> None:
        """Apply stored *max* injection calibration to selected channels.

        Parameters
        ----------
        channels : int, array-like, or None, optional
            Channel number(s) (0-based), or ``None`` for all.

        Raises
        ------
        RuntimeError
            If no max calibration data is found in the config.
        """
        seg_indices = self._parse_channels(channels)
        segs = self._injection_segments
        max_list = Config().get('injection.max', None)
        piston = float(np.mean(Config().get('dm.piston_range')))

        if not max_list:
            raise RuntimeError(
                "No 'max' injection calibration found. "
                "Run Injection().calibrate() first."
            )

        for seg_idx in seg_indices:
            ch = self._channel_for_segment(seg_idx)
            if ch >= len(max_list) or max_list[ch] is None:
                raise KeyError(
                    f"No 'max' calibration for channel {ch} "
                    f"(segment {seg_idx})"
                )
            tip, tilt = max_list[ch]
            self.dm.segments[seg_idx].set_ptt(piston, float(tip), float(tilt))

        print(f"Injection MAX on channels "
              f"{[self._channel_for_segment(s) for s in seg_indices]} "
              f"(segments {seg_indices})")

    def set_balanced(self, channels=None) -> None:
        """Apply stored *balanced* injection calibration to selected channels.

        Parameters
        ----------
        channels : int, array-like, or None, optional
            Channel number(s) (0-based), or ``None`` for all.

        Raises
        ------
        RuntimeError
            If no balanced calibration data is found in the config.
        """
        seg_indices = self._parse_channels(channels)
        segs = self._injection_segments
        bal_list = Config().get('injection.balanced', None)
        piston = float(np.mean(Config().get('dm.piston_range')))

        if not bal_list:
            raise RuntimeError(
                "No 'balanced' injection calibration found. "
                "Run Injection().calibrate() first."
            )

        for seg_idx in seg_indices:
            ch = self._channel_for_segment(seg_idx)
            if ch >= len(bal_list) or bal_list[ch] is None:
                raise KeyError(
                    f"No 'balanced' calibration for channel {ch} "
                    f"(segment {seg_idx})"
                )
            tip, tilt = bal_list[ch]
            self.dm.segments[seg_idx].set_ptt(piston, float(tip), float(tilt))

        print(f"Injection BALANCED on channels "
              f"{[self._channel_for_segment(s) for s in seg_indices]} "
              f"(segments {seg_indices})")

    # -- injection maps -------------------------------------------------------

    def get_injection_maps(
        self,
        grid_n: int = 31,
        ttamp: float = 3.0,
        avg_frames: int = 1,
        use_tqdm: bool = True,
        verbose: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Scan tip/tilt space and build injection flux maps for all channels.

        For each injection channel the other channels are parked (off) and a
        2-D raster scan of tip × tilt is performed.  The total output flux
        (sum over all camera outputs) is recorded at every grid point.

        Parameters
        ----------
        grid_n : int, optional
            Number of scan points per axis.  Default is 31.
        ttamp : float, optional
            Half-range of the scan in mrad (scan from ``-ttamp`` to ``+ttamp``).
            Default is 3.0.
        avg_frames : int, optional
            Number of camera frames to average per point.  Default is 1.
        use_tqdm : bool, optional
            Show a progress bar if *tqdm* is available.  Default is True.
        verbose : bool, optional
            Print progress information.  Default is False.

        Returns
        -------
        injection_maps : ndarray, shape (N_channels, grid_n, grid_n)
            Flux map for each channel.  Axes are (channel, tip_index,
            tilt_index).
        tt_ramp : ndarray, shape (grid_n,)
            The tip/tilt values in mrad corresponding to each axis index.
        """
        segs = self._injection_segments
        n_ch = len(segs)
        camera = Cred3()

        tt_ramp = np.linspace(-float(ttamp), float(ttamp), int(grid_n))
        injection_maps = np.empty((n_ch, grid_n, grid_n))

        # Build iterator (optionally with tqdm)
        ch_iter = range(n_ch)
        if use_tqdm:
            try:
                from tqdm import tqdm
                ch_iter = tqdm(ch_iter, desc="Scanning injection maps", leave=True)
            except ImportError:
                pass

        for ch_idx in ch_iter:
            seg = segs[ch_idx]

            if verbose:
                print(f"  Channel {ch_idx} (segment {seg}): scanning…")

            # Park all other channels
            others = [c for c in range(n_ch) if c != ch_idx]
            self.off(others)

            for i, tip in enumerate(tt_ramp):
                for j, tilt in enumerate(tt_ramp):
                    self.dm.segments[seg].set_ptt(DM().mid_piston, float(tip), float(tilt))

                    flux = np.zeros_like(camera.get_outputs(flux_mode='sum'))
                    for _ in range(avg_frames):
                        flux += camera.get_outputs(flux_mode='sum')
                    flux /= float(avg_frames)

                    injection_maps[ch_idx, i, j] = float(np.sum(flux))

            # Park this channel while scanning the next one
            self.off(ch_idx)

        # Restore flat position at the end
        self.flat()

        return injection_maps, tt_ramp

    # -- calibration ----------------------------------------------------------
    def find_max_injection(self,
           injection_maps,
           tt_ramp,
           nb_std: float,
           plot: bool = True,
         ):

        """
        Find the maximum injection position (tip and tilt) for specific segments.

        This method performs a two-pass 2D Gaussian fit on injection flux maps to
        determine the optimal tip and tilt coordinates. The first pass identifies
        the general "splodge" location, while the second pass refines the
        measurement by fitting within a cropped region defined by a multiple
        of the initial standard deviation.

        Parameters
        ----------
        injection_maps : ndarray
            A 3D NumPy array of shape (n_segments, n_tt, n_tt) containing the
            recorded flux intensity for each tip/tilt combination.
        tt_ramp : ndarray
            A 1D NumPy array representing the tip and tilt coordinate values
            (typically in mrad) used to generate the meshgrid for fitting.
        nb_std : float
            The number of standard deviations from the first-pass fit used to
            define the cropping window for the refined second-pass fit.
        plot : bool, optional
            If True, generates diagnostic plots including the raw maps,
            Gaussian models, and residuals for both the full and cropped data.
            Default is True.

        Returns
        -------
        max_ptt : dict
            A dictionary where keys are the segment indices (as strings) and
            values are lists containing:
            [piston_nm, optimal_tip, optimal_tilt].

        Notes
        -----
        - The function assumes that `self._injection_segments` and a global
          `Config` object providing 'dm.piston_range' are available.
        - The 2D Gaussian model accounts for amplitude, position, sigma (spread),
          rotation (theta), and a global offset.
        - Chi-squared ($\chi^2$) values are calculated for both the gross and
          fine fits to provide a measure of fit quality.
        """

        def twoD_Gaussian(xy, amplitude, yo, xo, sigma_y, sigma_x, theta, offset):
            """
            Generate a flat array of a 2D-Gausian.

            Parameters
            ----------
            xy : tuple
                Meshgrid on which sampling the surface.
            amplitude : float
                Amplitude.
            yo : float
                Locate parameter along row axis.
            xo : float
                Locate parameter along column axis.
            sigma_y : float
                Scale parameter of the Gaussian in row axis.
            sigma_x : float
                Scale parameter of the Gaussian in column axis.
            theta : float
                Orientation of the Gaussian, in radians.
            offset : float
                Global offset.

            Returns
            -------
            1d-array
                Flattened array of the 2d Gaussian.

            """
            x, y = xy
            xo = float(xo)
            yo = float(yo)
            a = (np.cos(theta)**2)/(2*sigma_x**2) + (np.sin(theta)**2)/(2*sigma_y**2)
            b = -(np.sin(2*theta))/(4*sigma_x**2) + (np.sin(2*theta))/(4*sigma_y**2)
            c = (np.sin(theta)**2)/(2*sigma_x**2) + (np.cos(theta)**2)/(2*sigma_y**2)
            g = offset + amplitude*np.exp( - (a*((x-xo)**2) + 2*b*(x-xo)*(y-yo)
                                    + c*((y-yo)**2)))
            return g.ravel()

        def fit_model(data, x, y):
            """
            Fit a 2D Gaussian model to the provided data using non-linear least squares.

            This function utilizes `scipy.optimize.curve_fit` to determine the
            optimal parameters of a 2D Gaussian distribution that best describes
            the input intensity map.

            Parameters
            ----------
            data : ndarray
                A 2D NumPy array representing the observed flux or intensity map
                to be fitted.
            x : ndarray
                A 2D meshgrid array of the x-coordinates (typically representing
                tilt or column indices).
            y : ndarray
                A 2D meshgrid array of the y-coordinates (typically representing
                tip or row indices).

            Returns
            -------
            popt : ndarray
                An array of the optimal parameters found by the fit:
                `[amplitude, yo, xo, sigma_y, sigma_x, theta, offset]`.
                If the fit fails to converge, returns an array of zeros.
            pcov : ndarray
                The estimated covariance of `popt`. The diagonals provide the
                variance of the parameter estimates. Returns an array of zeros
                if the fit fails.

            Notes
            -----
            The optimization starts with an initial guess ($p_0$) defined as:
            * **Amplitude:** `data.max()`
            * **Center (yo, xo):** (0, 0)
            * **Sigma (y, x):** (1, 1)
            * **Rotation (theta):** 0
            * **Offset:** 0

            In the event of a `RuntimeError` (e.g., the maximum number of
            iterations is reached without convergence), the function catches
            the exception and returns zero-filled arrays to avoid crashing
            the main loop.
            """

            initial_guess = [data.max(), 0., 0., 1., 1., 0., 0.]
            try:
                popt, pcov = curve_fit(twoD_Gaussian, (x, y), data.ravel(), p0=initial_guess)
            except RuntimeError as e:
                print(i, e)
                popt = np.zeros((len(initial_guess),))
                pcov = np.zeros((len(initial_guess), len(initial_guess)))

            return popt, pcov

        def plot_fit(data, seg_max, suptitle, subtitle=''):
            """
                Visualize the injection maps or models with overlaid maximum positions.

                This function generates a figure containing a grid of subplots (up to 2x2)
                displaying 2D maps (e.g., raw data, fitted models, or residuals). It
                overlays a white crosshair at the detected maximum tip/tilt coordinates
                for each segment.

                Parameters
                ----------
                data : list of lists
                    A list where each element is a container of `[image, tip_range, tilt_ramp]`.
                    - `image` (ndarray): The 2D intensity map to plot.
                    - `tip_range` (ndarray): 1D array of tip coordinates for the y-axis.
                    - `tilt_ramp` (ndarray): 1D array of tilt coordinates for the x-axis.
                seg_max : ndarray
                    An array of shape (n_segments, 2) containing the [tip, tilt] coordinates
                    of the maximum injection point to be marked on the plots.
                suptitle : str
                    The main title for the entire figure.
                subtitle : str or list of str, optional
                    A string or list of strings to append to each subplot title (e.g.,
                    $\chi^2$ values). If a list is provided, it must match the number of
                    segments. Default is an empty string.

                Returns
                -------
                None
                    The function renders a Matplotlib figure but does not return a value.

                Notes
                -----
                - This function assumes a maximum of 4 segments due to the hardcoded
                  `plt.subplot(2, 2, i+1)` layout.
                - It depends on the `injection_seg_indices` variable defined in the
                  parent function's scope.
                - The color scale (`vmin`, `vmax`) is normalized across all subplots
                  based on the minimum and maximum values found in the input `data`.
                """
            plt.figure(figsize=(10,10))
            plt.suptitle(suptitle)
            for i in range(len(injection_seg_indices)):
                image, tip_range, tilt_ramp = data[i]
                tilt_step = np.diff(tilt_ramp)[0]
                tip_step = np.diff(tip_range)[0]
                plt.subplot(2,2,i+1)
                try:
                    plt.title('Seg '+str(injection_seg_indices[i])+subtitle[i])
                except:
                    plt.title('Seg '+str(injection_seg_indices[i])+subtitle)
                plt.imshow(image, origin='lower', cmap='jet',
                        extent=[tilt_ramp.min()-tilt_step/2, tilt_ramp.max()+tilt_step/2,
                                tip_range.min()-tip_step/2, tip_range.max()+tip_step/2],
                        vmin=min([elt[0].min() for elt in data]),
                        vmax=max([elt[0].max() for elt in data]))
                plt.colorbar()
                plt.scatter(seg_max[i,1], seg_max[i,0], c='w', marker='+', s=100, label='tt_max')
                plt.xlabel('Tilt (mrad)')
                plt.ylabel('Tip (mrad)')
            plt.tight_layout()

        injection_seg_indices = self._injection_segments
        piston_nm = Config().get('dm.piston_range')
        max_ptt = {}

        x, y = np.meshgrid(tt_ramp, tt_ramp) # tilt and tip

        # -- Find gross splodge's centroids and spread in tip and tilt
        params = []
        models = []

        for i in range(injection_maps.shape[0]):
            tt_map = injection_maps[i]
            popt, pcov = fit_model(tt_map, x, y)
            params.append(popt)
            models.append(twoD_Gaussian((x, y), *popt).reshape(x.shape))

            print(f"Injection spread of seg={injection_seg_indices[i]}: (tip, tilt) = ({popt[3]:.5f},{popt[4]:.5f}) mrad")

        params = np.array(params)
        models = np.array(models)
        residuals = injection_maps - models
        chi2 = np.sum(residuals**2, (1,2)) / (injection_maps[0].size - len(popt))

        # -- Find fine splodge's centroids and spread in tip and tilt
        cropped_data = []
        params_cropped = []
        models_cropped = []

        for i in range(injection_maps.shape[0]):
            mask_tip = (tt_ramp >= params[i, 1] - nb_std * params[i, 3]) & (tt_ramp <= params[i, 1] + nb_std * params[i, 3])
            mask_tilt = (tt_ramp >= params[i, 2] - nb_std * params[i, 4]) & (tt_ramp <= params[i, 2] + nb_std * params[i, 4])
            cropped_tip = tt_ramp[mask_tip]
            cropped_tilt = tt_ramp[mask_tilt]

            tt_map = injection_maps[i, mask_tip]
            tt_map = tt_map[:, mask_tilt]

            cropped_data.append([tt_map, cropped_tip, cropped_tilt])

            x, y = np.meshgrid(cropped_tilt, cropped_tip)
            popt, pcov = fit_model(tt_map, x, y)
            params_cropped.append(popt)
            models_cropped.append([twoD_Gaussian((x, y), *popt).reshape(x.shape), cropped_tip, cropped_tilt])

            max_ptt[str(injection_seg_indices[i])] = [piston_nm[i], popt[1], popt[2]]

            print(f"Injection max of seg={injection_seg_indices[i]}: (tip, tilt) = ({popt[1]:.5f},{popt[2]:.5f}) mrad; flux = {popt[0]:.4g}")

        params_cropped = np.array(params_cropped)
        residuals_cropped = [cropped_data[i][0] - models_cropped[i] for i in range(len(cropped_data))]
        chi2_cropped = [np.sum(residuals_cropped[i]**2) / (cropped_data[i][0].size - len(params_cropped[i])) for i in range(len(residuals))]

        if plot:
            data = [injection_maps, tt_ramp, tt_ramp]
            seg_max = params[:,1:3]
            plot_fit(data, seg_max, 'Injection maps')

            data = [models, tt_ramp, tt_ramp]
            seg_max = params[:,1:3]
            plot_fit(data, seg_max, 'Injection models', [r'(\chi^2=%.3f)'%(elt) for elt in chi2])

            data = [models, tt_ramp, tt_ramp]
            seg_max = params[:,1:3]
            plot_fit(residuals, seg_max, 'Residuals')

            seg_max = params[:,1:3]
            plot_fit(cropped_data, seg_max, 'Cropped injection maps')

            seg_max = params[:,1:3]
            plot_fit(models_cropped, seg_max, 'Cropped injection models', [r'(\chi^2=%.3f)'%(elt) for elt in chi2_cropped])

            data = [residuals_cropped[i], cropped_data[i][1], cropped_data[i][2]]
            seg_max = params[:,1:3]
            plot_fit(data, seg_max, 'Cropped residuals')

        return max_ptt


    def calibrate(
        self,
        grid_n: int = 31,
        ttamp: float = 3.0,
        piston_nm: Optional[float] = None,
        avg_frames: int = 1,
        use_tqdm: bool = True,
        plot: bool = True,
        tilt_tol: float = 1e-3,
        verbose: bool = False,
    ) -> dict:
        """Calibrate injection tip/tilt for all channels.

        **Algorithm**

        1. *Scan* – For each channel (other channels parked), perform a 2-D
           tip × tilt raster scan and record the total output flux.
        2. *Find max* – The optimal (tip, tilt) is the grid pixel with the
           highest flux (no fitting, no centroid).
        3. *Find balanced* – Identify the channel whose maximum flux is the
           lowest (the "weakest" channel).  For each of the remaining channels,
           keep tip fixed at its max-flux value and perform a **dichotomy
           search on tilt** (perpendicular to the channel plane, avoiding
           cross-talk) to find the tilt that equalises the flux to the weakest
           channel's maximum.  The search picks one side of the peak
           arbitrarily (positive tilt direction).
        4. *Return metadata* – A dictionary with max and balanced tip/tilt
           positions and the corresponding flux values.

        Parameters
        ----------
        grid_n : int, optional
            Number of points per axis for the initial scan.  Default is 31.
        ttamp : float, optional
            Half-range of the tip/tilt scan in mrad.  Default is 3.0.
        piston_nm : float or None, optional
            Piston applied during calibration.  If ``None``, the midpoint of
            ``dm.piston_range`` is used.
        avg_frames : int, optional
            Frames averaged per measurement.  Default is 1.
        use_tqdm : bool, optional
            Show progress bar.  Default is True.
        plot : bool, optional
            Show diagnostic plots.  Default is True.
        tilt_tol : float, optional
            Tolerance on tilt (mrad) for the dichotomy convergence.
            Default is 1e-3.
        verbose : bool, optional
            Print debugging information.  Default is False.

        Returns
        -------
        dict
            Dictionary with the following keys:

            ``'max'``
                ``list[list[float]]`` – Per channel, ``[tip_mrad, tilt_mrad]``
                that maximises flux.
            ``'balanced'``
                ``list[list[float]]`` – Same structure, positions that
                equalise all channels to the weakest channel's peak flux.
            ``'flux_max'``
                ``list[float]`` – Peak flux per channel at max position.
            ``'flux_balanced'``
                ``list[float]`` – Flux per channel at balanced position.
            ``'injection_maps'``
                ``ndarray`` – The raw scan maps (N_ch, grid_n, grid_n).
            ``'tt_ramp'``
                ``ndarray`` – The tip/tilt ramp used for the scan.
        """

        segs = self._injection_segments
        n_ch = len(segs)
        camera = Cred3()
        settle = float(Config().get('dm.stabilization_time', 0.01))

        if piston_nm is None:
            piston_nm = float(np.mean(Config().get('dm.piston_range')))

        # ── Step 1: Scan tip/tilt space ──────────────────────────────────────
        print("── Step 1/3: Scanning tip/tilt space ──")
        injection_maps, tt_ramp = self.get_injection_maps(
            grid_n=grid_n,
            ttamp=ttamp,
            avg_frames=avg_frames,
            use_tqdm=use_tqdm,
            verbose=verbose,
        )

        # ── Step 2: Find max injection (brightest pixel) ─────────────────────
        print("── Step 2/3: Finding maximum injection points ──")

        max_tt: List[List[float]] = [None] * n_ch  # [tip, tilt] per channel
        flux_max: List[float] = [0.0] * n_ch
        tip_max_arr = np.empty(n_ch)
        tilt_max_arr = np.empty(n_ch)

        for ch_idx in range(n_ch):
            seg = segs[ch_idx]
            fmap = injection_maps[ch_idx]

            # Brightest pixel
            idx_flat = int(np.argmax(fmap))
            i_max, j_max = np.unravel_index(idx_flat, fmap.shape)

            best_tip = float(tt_ramp[i_max])
            best_tilt = float(tt_ramp[j_max])
            best_flux = float(fmap[i_max, j_max])

            tip_max_arr[ch_idx] = best_tip
            tilt_max_arr[ch_idx] = best_tilt
            max_tt[ch_idx] = [best_tip, best_tilt]
            flux_max[ch_idx] = best_flux

            if verbose:
                print(
                    f"  Channel {ch_idx} (seg {seg}): max flux = {best_flux:.4g} "
                    f"at (tip, tilt) = ({best_tip:.4f}, {best_tilt:.4f}) mrad"
                )

        # ── Step 3: Balanced injection via dichotomy on tilt ─────────────────
        print("── Step 3/3: Balancing injection fluxes ──")

        # Identify weakest channel
        weak_ch = int(np.argmin(flux_max))
        weak_seg = segs[weak_ch]
        target_flux = flux_max[weak_ch]

        if verbose:
            print(
                f"  Weakest channel: {weak_ch} (seg {weak_seg}), "
                f"target flux = {target_flux:.4g}"
            )

        balanced_tt: List[List[float]] = [None] * n_ch  # [tip, tilt] per channel
        flux_balanced: List[float] = [0.0] * n_ch

        # Record dichotomy evaluation history for diagnostic plotting. Each
        # element is a dict with lists 'tilts' and 'fluxes' storing the
        # evaluated tilts and corresponding fluxes during the bisection.
        dichotomy_history: List[dict] = [dict(tilts=[], fluxes=[]) for _ in range(n_ch)]

        # The weakest channel stays at its max position
        balanced_tt[weak_ch] = list(max_tt[weak_ch])
        flux_balanced[weak_ch] = target_flux

        for ch_idx in range(n_ch):
            seg = segs[ch_idx]
            if ch_idx == weak_ch:
                continue

            if verbose:
                print(f"  Dichotomy on channel {ch_idx} (seg {seg})…")

            # Park all other channels
            others = [c for c in range(n_ch) if c != ch_idx]
            self.off(others)

            # Fix tip at max-flux value
            fixed_tip = float(tip_max_arr[ch_idx])
            best_tilt = float(tilt_max_arr[ch_idx])

            # Determine the search direction: we move tilt away from the peak
            # towards positive tilt (arbitrary side choice).  If moving in the
            # positive direction does not decrease flux, we try the negative
            # direction instead.
            tilt_bound_pos = float(ttamp)
            tilt_bound_neg = -float(ttamp)

            # Measure flux at peak position first.
            self.dm.segments[seg].set_ptt(piston_nm, fixed_tip, best_tilt)
            time.sleep(settle)
            peak_flux = self._measure_flux(camera, avg_frames)

            # store initial point (peak)
            dichotomy_history[ch_idx]['tilts'].append(best_tilt)
            dichotomy_history[ch_idx]['fluxes'].append(peak_flux)

            # Try a small step in the positive tilt direction
            test_tilt = min(best_tilt + 0.5, tilt_bound_pos)
            self.dm.segments[seg].set_ptt(piston_nm, fixed_tip, test_tilt)
            time.sleep(settle)
            test_flux = self._measure_flux(camera, avg_frames)

            # store the test point
            dichotomy_history[ch_idx]['tilts'].append(test_tilt)
            dichotomy_history[ch_idx]['fluxes'].append(test_flux)

            if test_flux < peak_flux:
                # Positive direction reduces flux → search [best_tilt, +ttamp]
                # In this interval flux decreases monotonically from peak.
                # lo = peak side (high flux), hi = far side (low flux).
                search_sign = +1.0
                lo_tilt = best_tilt
                hi_tilt = tilt_bound_pos
            else:
                # Negative direction reduces flux → search [-ttamp, best_tilt]
                search_sign = -1.0
                lo_tilt = tilt_bound_neg
                hi_tilt = best_tilt

            # Dichotomy: we maintain the invariant
            #   flux(lo_tilt) >= target_flux >= flux(hi_tilt)
            # when search_sign > 0  (lo near peak, hi far away)
            # and the symmetric when search_sign < 0.
            n_iter = 0
            max_iter = 50  # safety limit
            while abs(hi_tilt - lo_tilt) > tilt_tol and n_iter < max_iter:
                mid_tilt = (lo_tilt + hi_tilt) / 2.0
                self.dm.segments[seg].set_ptt(piston_nm, fixed_tip, mid_tilt)
                time.sleep(settle)
                mid_flux = self._measure_flux(camera, avg_frames)

                # record mid-point evaluation for diagnostics
                dichotomy_history[ch_idx]['tilts'].append(mid_tilt)
                dichotomy_history[ch_idx]['fluxes'].append(mid_flux)

                if search_sign > 0:
                    # lo is near peak (high flux), hi is far (low flux)
                    if mid_flux > target_flux:
                        lo_tilt = mid_tilt  # move away from peak
                    else:
                        hi_tilt = mid_tilt  # move closer to peak
                else:
                    # lo is far (low flux), hi is near peak (high flux)
                    if mid_flux > target_flux:
                        hi_tilt = mid_tilt  # move away from peak
                    else:
                        lo_tilt = mid_tilt  # move closer to peak

                n_iter += 1

            # Final measurement at converged point
            bal_tilt = (lo_tilt + hi_tilt) / 2.0
            self.dm.segments[seg].set_ptt(piston_nm, fixed_tip, bal_tilt)
            time.sleep(settle)
            bal_flux = self._measure_flux(camera, avg_frames)

            # store final converged point
            dichotomy_history[ch_idx]['tilts'].append(bal_tilt)
            dichotomy_history[ch_idx]['fluxes'].append(bal_flux)

            balanced_tt[ch_idx] = [fixed_tip, bal_tilt]
            flux_balanced[ch_idx] = bal_flux

            if verbose:
                print(
                    f"    → balanced tilt = {bal_tilt:.4f} mrad, "
                    f"flux = {bal_flux:.4g} (target {target_flux:.4g}), "
                    f"iterations = {n_iter}"
                )

        # Park everything and restore flat
        self.flat()

        # ── Persist to config ────────────────────────────────────────────────
        Config().set('injection.max', max_tt, autosave=False)
        Config().set('injection.balanced', balanced_tt, autosave=False)
        Config().save_to_file()

        print("✅ Injection calibration saved to config "
              "(injection.max / injection.balanced)")

        # ── Plot ─────────────────────────────────────────────────────────────
        fig = None
        fig_dict = None
        if plot:
            fig_dict = self._plot_calibration(
                injection_maps, tt_ramp, segs,
                max_tt, balanced_tt, flux_max, flux_balanced,
                dichotomy_history=dichotomy_history,
            )
            # Backwards-compatible primary figure (maps)
            if isinstance(fig_dict, dict):
                fig = fig_dict.get('maps')
            else:
                fig = fig_dict

        return {
            'max': max_tt,
            'balanced': balanced_tt,
            'flux_max': flux_max,
            'flux_balanced': flux_balanced,
            'injection_maps': injection_maps,
            'tt_ramp': tt_ramp,
            'figure': fig,
            'figures': fig_dict,
        }

    # -- private helpers ------------------------------------------------------

    @staticmethod
    def _measure_flux(camera: 'Cred3', avg_frames: int = 1) -> float:
        """Measure total output flux (sum of all camera outputs).

        Parameters
        ----------
        camera : Cred3
            Camera instance.
        avg_frames : int
            Number of frames to average.

        Returns
        -------
        float
            Total output flux.
        """
        flux = np.zeros_like(camera.get_outputs(flux_mode='sum'))
        for _ in range(avg_frames):
            flux += camera.get_outputs(flux_mode='sum')
        flux /= float(avg_frames)
        return float(np.sum(flux))

    @staticmethod
    def _plot_calibration(
        injection_maps: np.ndarray,
        tt_ramp: np.ndarray,
        segs: List[int],
        max_tt: List[List[float]],
        balanced_tt: List[List[float]],
        flux_max: List[float],
        flux_balanced: List[float],
        dichotomy_history: List[dict] = None,
    ):
        """Generate diagnostic plots for the calibration.

        Parameters
        ----------
        injection_maps : ndarray
            Shape (N_ch, grid_n, grid_n).
        tt_ramp : ndarray
            Tip/tilt ramp values (mrad).
        segs : list[int]
            DM segment indices.
        max_tt : list[list[float]]
            Max calibration data, list of [tip, tilt] per channel.
        balanced_tt : list[list[float]]
            Balanced calibration data, list of [tip, tilt] per channel.
        flux_max : list[float]
            Flux at max position per channel.
        flux_balanced : list[float]
            Flux at balanced position per channel.

        Returns
        -------
        matplotlib.figure.Figure or None
        """
        try:
            import matplotlib.pyplot as plt

            n_ch = len(segs)
            step = float(tt_ramp[1] - tt_ramp[0]) if len(tt_ramp) > 1 else 1.0
            e = float(tt_ramp[-1]) + step / 2.0
            e_min = float(tt_ramp[0]) - step / 2.0

            vmin = float(np.min(injection_maps))
            vmax = float(np.max(injection_maps))

            fig, axs = plt.subplots(1, n_ch, figsize=(4 * n_ch, 4))
            if n_ch == 1:
                axs = [axs]

            for ch_idx, ax in enumerate(axs):
                seg = segs[ch_idx]
                fmap = injection_maps[ch_idx]

                ax.set_title(f"Channel {ch_idx} (seg {seg})")
                im = ax.imshow(
                    fmap, cmap='jet', origin='lower',
                    extent=[e_min, e, e_min, e],
                    vmin=vmin, vmax=vmax,
                )
                plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

                # Max marker
                tip_m, tilt_m = max_tt[ch_idx]
                fm = flux_max[ch_idx]
                ax.scatter(
                    tilt_m, tip_m, color='white', marker='^',
                    s=80, edgecolors='black', linewidths=0.5,
                    label=f"Max (f={fm:.2e})",
                )

                # Balanced marker
                tip_b, tilt_b = balanced_tt[ch_idx]
                fb = flux_balanced[ch_idx]
                ax.scatter(
                    tilt_b, tip_b, color='white', marker='o',
                    s=60, edgecolors='black', linewidths=0.5,
                    label=f"Bal (f={fb:.2e})",
                )

                ax.set_xlabel("Tilt (mrad)")
                ax.set_ylabel("Tip (mrad)")
                ax.legend(fontsize='small')

            fig.suptitle("Injection Calibration", y=1.02)
            plt.tight_layout()
            plt.show()

            # ── Dichotomy evolution at fixed tip (profile slice) ───────────
            try:
                fig2, axs2 = plt.subplots(1, n_ch, figsize=(4 * n_ch, 3))
                if n_ch == 1:
                    axs2 = [axs2]

                for ch_idx, ax in enumerate(axs2):
                    seg = segs[ch_idx]
                    tip_m, tilt_m = max_tt[ch_idx]
                    tip_b, tilt_b = balanced_tt[ch_idx]

                    # find nearest tip index in tt_ramp
                    tip_idx = int(np.argmin(np.abs(tt_ramp - float(tip_m))))
                    profile = injection_maps[ch_idx, tip_idx, :]
                    ax.plot(tt_ramp, profile, '-k', lw=1, label='profile (fixed tip)')

                    # plot dichotomy history if available
                    if dichotomy_history and len(dichotomy_history) > ch_idx:
                        h = dichotomy_history[ch_idx]
                        if h and len(h.get('tilts', [])) > 0:
                            ax.plot(h['tilts'], h['fluxes'], '-o', color='C1',
                                    label='dichotomy evals')

                    # mark max and balanced
                    ax.scatter([tilt_m], [flux_max[ch_idx]], marker='^', color='C2',
                               s=80, edgecolors='black', label='max')
                    ax.scatter([tilt_b], [flux_balanced[ch_idx]], marker='o', color='C3',
                               s=60, edgecolors='black', label='balanced')

                    ax.set_xlabel('Tilt (mrad)')
                    ax.set_title(f'Ch {ch_idx} (seg {seg})')
                    ax.legend(fontsize='small')

                plt.tight_layout()
                plt.show()
            except Exception:
                fig2 = None

            # ── Compare flux_max vs flux_balanced ───────────────────────────
            try:
                fig3, ax3 = plt.subplots(figsize=(6, 4))
                x = np.arange(n_ch)
                width = 0.35
                ax3.bar(x - width/2, flux_max, width, label='max')
                ax3.bar(x + width/2, flux_balanced, width, label='balanced')
                ax3.set_xticks(x)
                ax3.set_xticklabels([str(i) for i in range(n_ch)])
                ax3.set_xlabel('Channel index')
                ax3.set_ylabel('Flux (sum)')
                ax3.set_title('Max vs Balanced Flux per Channel')
                ax3.legend()
                plt.tight_layout()
                plt.show()
            except Exception:
                fig3 = None

            return {'maps': fig, 'dichotomy': fig2, 'comparison': fig3}
        except Exception as exc:
            print(f"⚠️  Plot skipped: {exc}")
            return None
