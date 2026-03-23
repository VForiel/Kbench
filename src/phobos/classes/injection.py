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
from astropy.io import fits
from datetime import datetime
from pathlib import Path
import os

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
        n_roi: int = 4,
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
        n_roi : int, optional
            Number of ROI on a frame to include in the flux calculation.
            Default is 4.
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

                    flux = np.zeros_like(self._measure_flux(camera, n_roi, avg_frames, flux_mode='mean'))
                    for _ in range(avg_frames):
                        flux += self._measure_flux(camera, n_roi, avg_frames, flux_mode='mean')
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
           verbose: bool = False
         ):

        """Estimate per-channel maximum injection tip/tilt by two-pass 2D Gaussian fitting.

        Perform a robust two-stage estimation of the tip/tilt coordinates that
        maximise the injected flux for each channel:

        1. Coarse fit: fit a 2D Gaussian to the full channel map to obtain a
        first estimate of the amplitude, centroid (tip, tilt), spreads and
        orientation.
        2. Crop & refine: define a cropping window around the coarse centroid
        using `nb_std` × sigma from the coarse fit and perform a second 2D
        Gaussian fit on the cropped data to improve centroid precision.
        3. Compute diagnostics: generate model maps, residuals and chi-squared
        for both passes. Optionally produce matplotlib figures for inspection.

        Parameters
        ----------
        injection_maps : ndarray
            3D array of shape (n_channels, n_tt, n_tt) containing total output
            flux measured for each tip/tilt grid point.
        tt_ramp : ndarray
            1D array of tip/tilt coordinate values (mrad) used to build the maps.
        nb_std : float
            Number of standard deviations from the coarse fit sigma used to
            define the cropping window for the refined fit (e.g. 1.0).
        plot : bool, optional
            If True, generate diagnostic plots (maps, models, cropped fits and
            residuals). Default is True.
        verbose : bool, optional
            Print progress and debugging information. Default is False.

        Returns
        -------
        dict
            Dictionary with the following keys:

            - 'max' : dict
                Mapping from segment index (string) to [piston_nm, tip_mrad, tilt_mrad]
                representing the refined maximum injection point.
            - 'params' : ndarray
                Coarse-fit parameter array (n_channels, n_params).
            - 'params_cropped' : ndarray
                Refined-fit parameter array for the cropped maps.
            - 'models' : ndarray
                Modeled maps from the coarse fits with same shape as injection_maps.
            - 'cropped_data' : list
                List of cropped data entries used for the refined fits.
            - 'models_cropped' : list
                List of refined-fit model maps and their grids.
            - 'fig' : list
                List of matplotlib Figures produced when `plot=True`. Elements may be
                None if a particular plot failed to render.
            - 'diag' : list
                Convenience list of [tip_mrad, tilt_mrad] per channel extracted from
                the refined fits.

        Notes
        -----
        - The function expects channel indices to be provided by
        `self._injection_segments` and uses `Config().get('dm.piston_range')`
        to determine the piston applied to reporting values.
        - Returned tip/tilt values are in milliradians (mrad).
        - The fitting routine uses `scipy.optimize.curve_fit` and falls back to
        zero-filled parameter arrays if the fit fails to converge for a channel.
        - This routine does not modify DM state; it only analyses `injection_maps`.

        Examples
        --------
        >>> inj = Injection()
        >>> maps, tt = inj.get_injection_maps(grid_n=21, ttamp=2.0, avg_frames=2)
        >>> result = inj.find_max_injection(maps, tt, nb_std=1.0, plot=True)
        >>> max_positions = result['diag']  # list of [tip, tilt] per channel
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
            fig = plt.figure(figsize=(10,10))
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

            return fig

        injection_seg_indices = self._injection_segments
        piston_nm = float(np.mean(Config().get('dm.piston_range')))
        max_ptt = {}

        x, y = np.meshgrid(tt_ramp, tt_ramp) # tilt and tip

        # -- Find gross splodge's centroids and spread in tip and tilt
        print("\n── Find gross TT for max injection and spread ──")
        params = []
        models = []

        for i in range(injection_maps.shape[0]):
            tt_map = injection_maps[i]
            popt, pcov = fit_model(tt_map, x, y)
            params.append(popt)
            models.append(twoD_Gaussian((x, y), *popt).reshape(x.shape))

            if verbose:
                print(f"Injection max of seg={injection_seg_indices[i]}: (tip, tilt) = ({popt[1]:.5f},{popt[2]:.5f}) mrad")
                print(f"Injection spread of seg={injection_seg_indices[i]}: (tip, tilt) = ({popt[3]:.5f},{popt[4]:.5f}) mrad")

        params = np.array(params)
        models = np.array(models)
        residuals = injection_maps - models
        chi2 = np.sum(residuals**2, (1,2)) / (injection_maps[0].size - len(popt))

        # -- Find fine splodge's centroids and spread in tip and tilt
        print("\n── Find precise TT for max injection ──")
        cropped_data = []
        params_cropped = []
        models_cropped = []
        max_tt = []

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
            models_cropped.append([twoD_Gaussian((x, y), *popt).reshape(tt_map.shape), cropped_tip, cropped_tilt])
            best_tip, best_tilt = float(popt[1]), float(popt[2])

            max_ptt[str(injection_seg_indices[i])] = np.array([piston_nm, best_tip, best_tilt])
            max_tt.append(np.array([best_tip, best_tilt]))

            print(f"Injection max of seg={injection_seg_indices[i]}: (tip, tilt) = ({best_tip:.5f},{best_tilt:.5f}) mrad; flux = {popt[0]:.4g}")

        params_cropped = np.array(params_cropped)
        residuals_cropped = [cropped_data[i][0] - models_cropped[i][0] for i in range(len(cropped_data))]
        chi2_cropped = [np.sum(residuals_cropped[i]**2) / (cropped_data[i][0].size - len(params_cropped[i])) for i in range(len(residuals))]

        Config().set('injection.max', np.array(max_tt).tolist(), autosave=False)
        Config().save_to_file()

        if verbose:
            print("✅ Injection calibration saved to config "
                "(injection.max)")

        figs = [None] * 6
        if plot:
            data = [[injection_maps[i], tt_ramp, tt_ramp] for i in range(len(injection_maps))]
            seg_max = params[:,1:3]
            figs[0] = plot_fit(data, seg_max, 'Injection maps')

            data = [[models[i], tt_ramp, tt_ramp] for i in range(len(models))]
            seg_max = params[:,1:3]
            figs[1] = plot_fit(data, seg_max, 'Injection models', [r"($\chi^2$=%.3f)"%(elt) for elt in chi2])

            data = [[residuals[i], tt_ramp, tt_ramp] for i in range(len(residuals))]
            seg_max = params[:,1:3]
            figs[2] = plot_fit(data, seg_max, 'Residuals')

            seg_max = params[:,1:3]
            figs[3] = plot_fit(cropped_data, seg_max, 'Cropped injection maps')

            seg_max = params[:,1:3]
            figs[4] = plot_fit(models_cropped, seg_max, 'Cropped injection models', [r'($\chi^2$=%.3f)'%(elt) for elt in chi2_cropped])

            data = [[residuals_cropped[i], cropped_data[i][1], cropped_data[i][2]] for i in range(len(residuals_cropped))]
            seg_max = params[:,1:3]
            figs[5] = plot_fit(data, seg_max, 'Cropped residuals')

        return {'max_ptt':max_ptt,
                'params':params,
                'params_cropped':params_cropped,
                'models':models,
                'cropped_data':cropped_data,
                'models_cropped':models_cropped,
                'fig':figs,
                'max_tt':np.array(max_tt)}


    def find_balanced_injection(
        self,
        injection_maps,
        tt_ramp,
        tilt_bound: float,
        avg_frames: int,
        n_roi: int,
        tilt_tol: float = 1e-3,
        plot: bool = True,
        verbose: bool = False
           ):

        """Find balanced injection positions using a dichotomy search on tilt.

        Perform a balance procedure that equalises the output flux of all input
        channels to the peak flux of the weakest channel. The algorithm:

        1. Determine each channel's maximum flux position (tip, tilt) by
        locating the brightest pixel in its injection map.
        2. Identify the weakest channel (minimum peak flux) and use its peak
        flux as the balancing target.
        3. For every other channel, keep tip fixed at the channel's peak-tip and
        perform a dichotomy (bisection) search on tilt to find the tilt value
        that yields the target flux. The search moves away from the local peak
        until the flux monotonically decreases and then bisects the interval
        to converge to the target within `tilt_tol`.
        4. Record diagnostic information suitable for plotting (per-channel
        dichotomy evaluation history).

        Parameters
        ----------
        injection_maps : ndarray
            3D array with shape (n_channels, n_tt, n_tt) containing measured flux
            values from the tip/tilt raster scans.
        tt_ramp : ndarray
            1D array of tip/tilt coordinate values (mrad) used to build the maps.
        tilt_bound : float
            Absolute tilt search bound (mrad). The dichotomy search interval is
            clamped to [-tilt_bound, +tilt_bound].
        avg_frames : int
            Number of camera frames to average for each flux measurement.
        n_roi : int
            Number of ROI to read from the frame.
        tilt_tol : float, optional
            Convergence tolerance on tilt (mrad) for the dichotomy. Default: 1e-3.
        plot : bool, optional
            If True, generate diagnostic figures (maps, dichotomy traces and flux
            comparison). Default: True.
        verbose : bool, optional
            Enable verbose logging. Default: False.

        Returns
        -------
        dict
            Dictionary containing calibration and diagnostic results with keys:

            - 'max' : list[list[float]]
                Per-channel [tip_mrad, tilt_mrad] for the maximum-injection point.
            - 'balanced' : list[list[float]]
                Per-channel [tip_mrad, tilt_mrad] at the balanced positions.
            - 'flux_max' : list[float]
                Peak flux per channel at the max position.
            - 'flux_balanced' : list[float]
                Flux per channel at the balanced position.
            - 'injection_maps' : ndarray
                The original injection_maps argument (returned for convenience).
            - 'tt_ramp' : ndarray
                The original tt_ramp argument (returned for convenience).
            - 'figure' : matplotlib.Figure or None
                Backwards-compatible primary figure (maps) if `plot` is True.
            - 'figures' : dict or None
                Additional figures dictionary: e.g. {'maps', 'dichotomy', 'comparison'}.

        Notes
        -----
        - All channel indices are 0-based and map to DM segments via the instance
        configuration (injection.segments).
        - The method uses self._measure_flux for camera averaging and
        self._plot_calibration to generate figures when requested.
        - The function persists results to Config keys 'injection.max' and
        'injection.balanced' (Config.save_to_file is called).
        - The dichotomy history is recorded and included in diagnostic plots to
        visualise the evaluated tilt points and measured fluxes during the search.

        Examples
        --------
        >>> inj = Injection()
        >>> result = inj.find_balanced_injection(
        ...     injection_maps=maps, tt_ramp=tt, tilt_bound=3.0, avg_frames=2,
        ...     tilt_tol=1e-3, plot=True, verbose=False
        ... )
        >>> balanced_positions = result['balanced']
        >>> fluxes = result['flux_balanced']
        """
        segs = self._injection_segments
        n_ch = len(segs)
        piston_nm = float(np.mean(Config().get('dm.piston_range')))
        camera = Cred3()
        settle = float(Config().get('dm.stabilization_time', 0.01))

        # ── Find max injection (brightest pixel) ─────────────────────
        print("\n── Finding maximum injection points ──")

        max_tt = [None] * n_ch  # [tip, tilt] per channel
        flux_max = [0.0] * n_ch
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

        # ── Balanced injection via dichotomy on tilt ─────────────────
        print("\n── Balancing injection fluxes ──")

        # Identify weakest channel
        flux_max = np.max(injection_maps, axis=(1,2))
        weak_ch = np.argmin(flux_max)
        weak_seg = segs[weak_ch]
        target_flux = flux_max[weak_ch]

        if verbose:
            print(
                f"  Weakest channel: {weak_ch} (seg {weak_seg}), "
                f"target flux = {target_flux:.4g}"
            )

        balanced_tt = [None] * n_ch  # [tip, tilt] per channel
        flux_balanced = [0.0] * n_ch

        # Record dichotomy evaluation history for diagnostic plotting. Each
        # element is a dict with lists 'tilts' and 'fluxes' storing the
        # evaluated tilts and corresponding fluxes during the bisection.
        dichotomy_history = [{'tilts':[], 'fluxes':[]} for _ in range(n_ch)]

        # The weakest channel stays at its max position
        balanced_tt[weak_ch] = list(max_tt[weak_ch])
        flux_balanced[weak_ch] = float(target_flux)

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
            tilt_bound_pos = tilt_bound
            tilt_bound_neg = -tilt_bound

            # Measure flux at peak position first.
            self.dm.segments[seg].set_ptt(piston_nm, fixed_tip, best_tilt)
            time.sleep(settle)
            peak_flux = self._measure_flux(camera, n_roi, avg_frames)

            # store initial point (peak)
            dichotomy_history[ch_idx]['tilts'].append(best_tilt)
            dichotomy_history[ch_idx]['fluxes'].append(peak_flux)

            # Try a small step in the positive tilt direction
            test_tilt = min(best_tilt + 0.5, tilt_bound_pos)
            self.dm.segments[seg].set_ptt(piston_nm, fixed_tip, test_tilt)
            time.sleep(settle)
            test_flux = self._measure_flux(camera, n_roi, avg_frames)

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
                mid_flux = self._measure_flux(camera, n_roi, avg_frames)

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
            bal_flux = self._measure_flux(camera, n_roi, avg_frames)

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
        Config().set('injection.balanced', np.array(balanced_tt).tolist(), autosave=False)
        Config().save_to_file()

        print("✅ Injection calibration saved to config "
              "(injection.balanced)")

        # ── Plot ─────────────────────────────────────────────────────────────
        fig = None
        fig_dict = None
        if plot:
            fig_dict = self._plot_calibration(
                injection_maps, tt_ramp, segs,
                max_tt, balanced_tt, flux_max, flux_balanced,
                dichotomy_history=dichotomy_history,
                target_flux=target_flux
            )
            # Backwards-compatible primary figure (maps)
            if isinstance(fig_dict, dict):
                fig = fig_dict.get('maps')
            else:
                fig = fig_dict

        return {
            'balanced': balanced_tt,
            'flux_balanced': flux_balanced,
            'max': max_tt,
            'flux_max': flux_max,
            'figure': fig,
            'figures': fig_dict,
        }

    def calibrate(self,
        grid_n: int = 31,
        ttamp: float = 3.0,
        avg_frames: int = 1,
        avg_frames_bal: int = 5,
        n_roi: int = 4,
        nb_std: float = 1.0,
        tilt_bound: float = 3.0,
        tilt_tol: float = 1e-3,
        use_tqdm: bool = True,
        plot: bool = False,
        verbose: bool = False,
        save_path = None
    ):

        """Calibrate injection tip/tilt positions for all input channels.

        Perform a complete injection calibration consisting of:
        1) A 2-D raster scan of tip × tilt for each channel while other
        channels are parked, producing per-channel flux maps.
        2) A two-stage Gaussian fitting on each map to estimate the tip/tilt
        coordinates of the flux maximum ("max" positions).
        3) A flux balancing stage where the weakest channel (lowest peak flux)
        is used as a reference and remaining channels undergo a dichotomy
        search on tilt (with tip fixed at their per-channel maximum) to
        equalise their output fluxes to the weakest channel's peak.

        The method stores the resulting calibration entries in the global
        configuration under the keys ``injection.max`` and ``injection.balanced``
        and returns diagnostic data and figures.

        Parameters
        ----------
        grid_n : int, optional
            Number of sample points per axis for the tip/tilt raster scan.
            Default is 31.
        ttamp : float, optional
            Half-range of the tip/tilt scan in mrad (scan from -ttamp to +ttamp).
            Default is 3.0 mrad.
        avg_frames : int, optional
            Number of camera frames to average per measurement point. Default is 1.
        n_roi : int, optional
            Number of ROI to read from the frame. Default is 4.
        nb_std : float, optional
            Number of standard deviations used to crop the region for the
            second (refined) Gaussian fit. Default is 1.0.
        tilt_bound : float, optional
            Absolute tilt bound (mrad) used as search limit during dichotomy.
            Default is 3.0 mrad.
        tilt_tol : float, optional
            Convergence tolerance on tilt (mrad) for the dichotomy search.
            Default is 1e-3 mrad.
        use_tqdm : bool, optional
            Show a progress bar when scanning maps if ``tqdm`` is available.
            Default is True.
        plot : bool, optional
            If True, generate diagnostic figures (maps, models, dichotomy traces,
            and flux comparison). Default is False.
        verbose : bool, optional
            Print progress and debug information. Default is False.
        save_path: Path object, optional
            Path to directory where to save the diagnostic data

        Returns
        -------
        dict
            A dictionary containing calibration results and diagnostic data with
            the following keys:

            - 'injection_maps' : ndarray
                The raw flux maps of shape (n_channels, grid_n, grid_n).
            - 'tt_ramp' : ndarray
                1-D array of tip/tilt values (mrad) used for the scan axes.
            - 'max_inj' : dict
                Output of the max-finding routine (fitted piston, tip, tilt).
            - 'bal_data' : dict
                Output of the balancing routine containing:
                - 'balanced' : list[list[float]] — per-channel [tip, tilt] at balanced positions.
                - 'flux_balanced' : list[float] — flux per channel at balanced positions.
                - 'max' : list[list[float]] — per-channel [tip, tilt] at max positions.
                - 'flux_max' : list[float] — peak flux per channel.
                - 'figure' : matplotlib.Figure or None — primary figure (maps) if plot=True.
                - 'figures' : dict or None — additional figures (dichotomy, comparison) if plot=True.

        Notes
        -----
        - The method uses the camera interface (Cred3) and the DM segments mapped
        via the configuration key ``injection.segments``.
        - All channel indices are 0-based.
        - Calibration data are saved to the persistent Config but returned as well.
        - The dichotomy search keeps tip constant at each channel's max-tip and
        searches on tilt to match the weakest channel's peak flux.
        - In the directory to save the diagnostic, a subdirectory of the date of creation will be made and the diagnostic data will be stored inside
        - The diagnostic consists of a FITS file with the TT injection map, its axes, gross centroids and width in tip and tilt

        Examples
        --------
        >>> inj = Injection()
        >>> result = inj.calibrate(grid_n=21, ttamp=2.0, avg_frames=2, plot=True)
        >>> maps = result['injection_maps']
        >>> balanced_positions = result['bal_data']['balanced']
        """
        injection_maps, tt_ramp = self.get_injection_maps(grid_n, ttamp, avg_frames, n_roi, use_tqdm, verbose)
        max_data = self.find_max_injection(injection_maps, tt_ramp, nb_std, plot, verbose)
        balanced_data = self.find_balanced_injection(injection_maps, tt_ramp,
                                                     tilt_bound, avg_frames_bal, n_roi,
                                                     tilt_tol, plot, verbose)

        if save_path is not None:
            images_info = [{'data':injection_maps, 'extname':'TT map', 'segments':",".join(map(str, self._injection_segments))}]
            tables_info = [{'extname':'TT axes', 'columns':[('tip', 'D', tt_ramp), ('tilt', 'D', tt_ramp)]},
                           {'extname':'Centroids (mrad)', 'columns':[('segments', 'J', self._injection_segments),
                                                                     ('tip', 'D', max_data['max_tt'][:,0]),
                                                                     ('tilt', 'D', max_data['max_tt'][:,1])]},
                           {'extname':'Width (mrad)', 'columns':[('segments', 'J', self._injection_segments),
                                                                  ('tip', 'D', max_data['params'][:,3]),
                                                                  ('tilt', 'D', max_data['params'][:,4])]}]

            name = 'injection_telemetry_' + datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + '.fits'
            filename = save_path / name

            self.save_telemetry(filename, images_info, tables_info)

        return {'injection_maps':injection_maps,
                'tt_ramp':tt_ramp,
                'max_inj':max_data,
                'bal_data':balanced_data}

    def save_telemetry(self, filename, images_info, tables_info):
        """
            Saves multiple images and multiple tables to a single FITS file.

            Parameters:
            -----------
            filename : str
                The path and name of the output FITS file.
            images_info : list of dict
                A list representing the images to save.
                Format: [{'data': array, 'extname': 'NAME', 'timestamp': 'Optional custom time'}, ...]
            tables_info : list of dict
                A list representing the table extensions.
                Format: [{'extname': 'NAME', 'columns': [('label', 'format', array), ...]}, ...]
        """

        # Ensure the directory exists before doing anything else
        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        # Timestamp of the FITS file
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # Put images in FITS
        hdulist = []
        first_img = images_info[0]
        primary_hdu = fits.PrimaryHDU(data=first_img['data'])
        primary_hdu.header['timestamp'] = (timestamp, 'Date of FITS creation of FITS')

        if 'extname' in first_img.keys():
            primary_hdu.header['EXTNAME'] = first_img['extname']

        for key, value in first_img.items():
            if key != 'data' and key != 'extname':
                primary_hdu.header[key] = value

        hdulist.append(primary_hdu)

        for img in images_info[1:]:
            image_hdu = fits.ImageHDU(data=img['data'])

            if 'extname' in img.keys():
                image_hdu.header['EXTNAME'] = img['extname']

            for key, value in img.items():
                if key != 'data' and key != 'extname':
                    image_hdu.header[key] = value

            hdulist.append(image_hdu)

        # Put tables in FITS
        for table in tables_info:
            fits_columns = []

            for col_name, col_format, col_array in table['columns']:
                        fits_column = fits.Column(name=col_name, format=col_format, array=col_array)
                        fits_columns.append(fits_column)

            coldefs = fits.ColDefs(fits_columns)
            table_hdu = fits.BinTableHDU.from_columns(coldefs)

            if 'extname' in table:
                table_hdu.name = table['extname']

            hdulist.append(table_hdu)

        # Save FITS
        hdul = fits.HDUList(hdulist)
        hdul.writeto(filename, overwrite=True)

        print("Successfully saved in FITS")

    # -- private helpers ------------------------------------------------------

    @staticmethod
    def _measure_flux(camera: 'Cred3',
                      n_roi: int,
                      avg_frames: int = 1, 
                      flux_mode: str = 'mean') -> float:
        """Measure total output flux (sum of all camera outputs).

        Parameters
        ----------
        camera : Cred3
            Camera instance.
        n_roi : int
            Number of ROI to read from the frame.
        avg_frames : int
            Number of frames to average.
        flux_mode : str
            Mode for flux calculation (e.g., 'mean', 'sum').

        Returns
        -------
        float
            Total output flux.
        """
        flux = np.zeros_like(camera.get_outputs(flux_mode=flux_mode)[:n_roi])
        for _ in range(avg_frames):
            flux += camera.get_outputs(flux_mode=flux_mode)[:n_roi]
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
        target_flux: Optional[float] = None
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
        dichotomy_history : list of dict, optional
            Diagnostic history recorded during per-channel dichotomy searches.
            Each element corresponds to a channel and is a dict with keys:
            - 'tilts': list of tested tilt values (mrad),
            - 'fluxes': list of measured total fluxes at the corresponding tilts.
            When provided, these points are overlaid on the dichotomy evolution plots.
            Default is None.
        target_flux : float or None, optional
            Target flux used for balancing (typically the peak flux of the weakest
            channel). If provided, a horizontal dashed line at this value is drawn
            on the comparison plot to visualise the balancing target. Default is None.


        Returns
        -------
        matplotlib.figure.Figure or None
        """
        try:
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
                fig2, axs2 = plt.subplots(1, n_ch, figsize=(4 * n_ch, 3), sharey=True)
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

                    # balanced target as horizontal guide
                    if target_flux is not None:
                        ax.axhline(float(target_flux), color='black', linestyle='--',
                                   linewidth=1, alpha=0.7, label='target flux')

                    # mark max and balanced
                    ax.scatter([tilt_m], [flux_max[ch_idx]], marker='^', color='C2',
                               s=80, edgecolors='black', label='max', zorder=5)
                    ax.scatter([tilt_b], [flux_balanced[ch_idx]], marker='o', color='C3',
                               s=80, edgecolors='black', label='balanced', zorder=10)

                    # fix y dynamic per channel with a small margin
                    y_vals = [np.asarray(profile, dtype=float),
                              np.asarray([flux_max[ch_idx], flux_balanced[ch_idx]], dtype=float)]
                    if target_flux is not None:
                        y_vals.append(np.asarray([float(target_flux)], dtype=float))
                    if dichotomy_history and len(dichotomy_history) > ch_idx:
                        h = dichotomy_history[ch_idx]
                        if h and len(h.get('fluxes', [])) > 0:
                            y_vals.append(np.asarray(h['fluxes'], dtype=float))

                    y_all = np.concatenate(y_vals)
                    y_min = float(np.nanmin(y_all))
                    y_max = float(np.nanmax(y_all))
                    dy = max(1e-12, y_max - y_min)
                    margin = 0.08 * dy
                    ax.set_ylim(y_min - margin, y_max + margin)

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
                if target_flux is not None:
                    ax3.axhline(float(target_flux), color='black', linestyle='--', linewidth=1.5, label='target')
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
