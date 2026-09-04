#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 14:09:01 2026

@author: mmartinod
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
import pickle
from pathlib import Path
import os
from typing import Any, Callable, Iterable

plt.ion()

# Font sizes and figure geometry shared by all plots in this script.
SUPTITLE_FS = 22
TITLE_FS = 20
LABEL_FS = 18
TICK_FS = 16
LEGEND_FS = 16
FIGURE_WIDTH = 10
FIGURE_RATIO = 1.618
OUTPUT_COLORS = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']

def load_pickle_files(
    file_paths: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
    close_matplotlib_figures: bool = True,
) -> tuple[list[Any], list[Path]]:
    """Load one or multiple pickle files.

    Parameters
    ----------
    file_paths : str | os.PathLike[str] | Iterable[str | os.PathLike[str]]
        Path to a pickle file, or an iterable of pickle file paths.
    close_matplotlib_figures : bool, default=True
        If True, prevent matplotlib popups during unpickling by temporarily
        disabling interactive mode and closing only figures created while loading.

    Returns
    -------
    tuple[list[Any], list[Path]]
        Loaded objects and normalized paths in the same order.

    Raises
    ------
    ValueError
        If no file path is provided.
    FileNotFoundError
        If one of the provided files does not exist.
    TypeError
        If one of the provided values is not path-like.
    pickle.UnpicklingError
        If a file cannot be unpickled.
    """
    if isinstance(file_paths, (str, os.PathLike)):
        normalized_paths = [Path(file_paths)]
    else:
        normalized_paths = [Path(p) for p in file_paths]

    if not normalized_paths:
        raise ValueError("file_paths must contain at least one path.")

    loaded_objects: list[Any] = []
    for path in normalized_paths:
        if not isinstance(path, Path):
            raise TypeError(
                "Each item in file_paths must be a string or os.PathLike object."
            )
        if not path.is_file():
            raise FileNotFoundError(f"Pickle file not found: {path}")

        if close_matplotlib_figures:
            existing_figs = set(plt.get_fignums())
            was_interactive = plt.isinteractive()
            plt.ioff()

        try:
            with path.open("rb") as stream:
                loaded_objects.append(pickle.load(stream))
        finally:
            if close_matplotlib_figures:
                created_figs = [n for n in plt.get_fignums() if n not in existing_figs]
                for fig_num in created_figs:
                    plt.close(fig_num)
                if was_interactive:
                    plt.ion()

    return loaded_objects, normalized_paths


def compute_phase(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute the kernel-nulling phase from 4 combiner outputs.

    Parameters
    ----------
    data : np.ndarray
        Combiner outputs ordered as (Null, Grey+, Grey-, Bright) along axis 1,
        e.g. shape ``(n_points, 4)`` or ``(n_points, 4, n_wavelengths)``.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        Wrapped phase and its unwrapped version (unwrapped along axis 0).
    """
    phase = np.arctan2(data[:, 2] - data[:, 1], data[:, 3] - data[:, 0])
    unwrapped_phase = np.unwrap(phase, axis=0)
    return phase, unwrapped_phase


def plot_output_flux(
    x: np.ndarray,
    outs: np.ndarray,
    xlabel: str,
    pair: tuple[int, int],
    title: str | None = None,
    secondary_axis_functions: tuple[Callable, Callable] | None = None,
    secondary_axis_label: str | None = None,
    width: float = FIGURE_WIDTH,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot the raw flux of each combiner output against a scan variable.

    Parameters
    ----------
    x : np.ndarray
        Scan variable (e.g. piston or power ramp).
    outs : np.ndarray
        Output fluxes, shape ``(n_points, n_outputs)``.
    xlabel : str
        Label of the main x-axis.
    pair : tuple[int, int]
        Telescope pair, used in the figure title.
    title : str | None, default=None
        Optional axis title.
    secondary_axis_functions : tuple[Callable, Callable] | None, default=None
        Forward/inverse functions used to add a secondary top x-axis.
    secondary_axis_label : str | None, default=None
        Label of the secondary x-axis, required if `secondary_axis_functions` is set.
    width : float, default=FIGURE_WIDTH
        Figure width in inches.

    Returns
    -------
    tuple[plt.Figure, plt.Axes]
        The created figure and axes.
    """
    fig, axs = plt.subplots(1, 1, figsize=(width, width / FIGURE_RATIO))
    fig.suptitle(f'Pair ({pair[0]}-{pair[1]})', fontsize=SUPTITLE_FS)
    n_outputs = outs.shape[1]
    for o in range(n_outputs):
        axs.plot(x, outs[:, o], color=OUTPUT_COLORS[o], label=f'Output {o}')
    axs.plot(x, outs.mean(1), color='k', linestyle='-', alpha=0.6, label='Mean')
    axs.tick_params(labelsize=TICK_FS)
    if title:
        axs.set_title(title, fontsize=TITLE_FS)
    axs.set_xlabel(xlabel, fontsize=LABEL_FS)
    axs.set_ylabel('Output Flux', fontsize=LABEL_FS)
    axs.legend(loc='upper right', fontsize=LEGEND_FS)
    axs.grid()
    if secondary_axis_functions is not None:
        secax = axs.secondary_xaxis('top', functions=secondary_axis_functions)
        secax.set_xlabel(secondary_axis_label, fontsize=LABEL_FS)
        secax.tick_params(labelsize=TICK_FS)
    fig.tight_layout()
    return fig, axs


def plot_spectral_phase(
    x: np.ndarray,
    spectral_phase: np.ndarray,
    spectral_axs: np.ndarray,
    xlabel: str,
    ylabel: str = 'Phase [rad]',
    center: int = 320,
    half_width: int = 170,
    width: float = 7,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot spectral phase curves across a wavelength range.

    Curves are colored by wavelength using a continuous colormap, with a
    colorbar that provides the wavelength legend. The two curves at the edges
    of the range are highlighted with their corresponding wavelength.

    Parameters
    ----------
    x : np.ndarray
        Scan variable (e.g. OPD or power ramp).
    spectral_phase : np.ndarray
        Spectral phase, shape ``(n_points, n_wavelengths)``.
    spectral_axs : np.ndarray
        Wavelength axis for each output, shape ``(n_outputs, n_wavelengths)``.
    xlabel : str
        Label of the x-axis.
    center : int, default=320
        Central wavelength index of the selected range.
    half_width : int, default=170
        Half-width, in indices, of the selected range around `center`.
    width : float, default=7
        Figure width in inches.

    Returns
    -------
    tuple[plt.Figure, plt.Axes]
        The created figure and axes.
    """
    lo, hi = center - half_width, center + half_width - 1
    wavelengths = spectral_axs[0, lo : hi + 1]
    color_map = plt.colormaps['viridis']
    normalization = Normalize(vmin=wavelengths.min(), vmax=wavelengths.max())

    fig, axs = plt.subplots(1, 1, figsize=(width, width / FIGURE_RATIO))
    for wavelength_index, wavelength in enumerate(wavelengths, start=lo):
        axs.plot(
            x,
            spectral_phase[:, wavelength_index],
            color=color_map(normalization(wavelength)),
            alpha=0.5,
        )
    axs.set_xlabel(xlabel, fontsize=LABEL_FS)
    axs.set_ylabel(ylabel, fontsize=LABEL_FS)
    axs.grid()
    axs.tick_params(labelsize=TICK_FS)
    colorbar = fig.colorbar(
        ScalarMappable(norm=normalization, cmap=color_map),
        ax=axs,
    )
    colorbar.set_label('Wavelength [nm]', fontsize=LABEL_FS)
    colorbar.ax.tick_params(labelsize=TICK_FS)
    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight', format='png')
    fig.tight_layout()
    return fig, axs


path = '/home/mmartinod/projects/photonics/data/2026-07-29_84d7be5/1_2T_charac/'
filename_dm = 'opd0_dm_scan_pair_2-0_ref_230nm_range_-2530_230nm.npz'
filename_topa = 'opd0_topa_scan_pair_2-0_ref_230_start_-2379.217803030303_range_0_1W.npz'

path = '/home/mmartinod/projects/photonics/data/2026-07-31_bf46f81/1_2T_charac/'
filename_dm = 'opd0_topa_dm_scan_pair_2-0_ref_230_pos_-1101.npz'
filename_topa = 'opd0_topa_scan_pair_2-0_ref_230_start_-2361_range_0_1W.npz'

suffix = '_nstack100'
path = '/home/mmartinod/projects/photonics/data/2026-08-17_347a303/2_2T_charac/'
filename_dm = f'opd0_topa_dm_scan_pair_2-0_ref_230_pos_-1122{suffix}.npz'
filename_topa = f'opd0_topa_scan_pair_2-0_ref_230_start_-2382_range_0_1W{suffix}.npz'

pair = (2, 0)
spec_law = np.load(path + 'spec_cal_coeffs_and_errors.npy')[0]
crop_areas = [0, 640]  # Got the spectral bounds of each track
spectral_axs = np.arange(crop_areas[0], crop_areas[-1])
spectral_axs = np.array([np.polyval(spec_law[i], spectral_axs) for i in range(spec_law.shape[0])])
revert_spectral_axs = lambda wl: (wl - spec_law[:,1]) / spec_law[:,0]

output_labels = ['Null', 'Grey+', 'Grey-', 'Bright']
phase_shift = np.array([np.pi, np.pi/2, -np.pi/2, 0.])
ref_cart = 230

wl_min = 1500
wl_max = 1600
px_min = revert_spectral_axs(wl_min)
px_max = revert_spectral_axs(wl_max)
px_min = int(np.around(px_min.mean()))
px_max = int(np.around(px_max.mean()))

#### DM scan ####
data = np.load(path + filename_dm)
outs = data['data']
outs_spectral = data['spectral_data']
piston_range = data['piston_range']
max_bright_idx = np.argmax(outs[:, 3])
max_null_idx = np.argmax(outs[:, 0])
max_bright_pos = piston_range[np.argmax(outs[:, 3])]
max_null_pos = piston_range[np.argmax(outs[:, 0])]

opd_range = (piston_range - max_bright_pos) * 2.0
opd_step = opd_range[1] - opd_range[0]
opd_to_piston = lambda opd, rc=max_bright_pos: opd / 2.0 + rc
piston_to_opd = lambda piston, rc=max_bright_pos: (piston - rc) * 2.0


phase, unwrap = compute_phase(outs)
spectral_phase, spectral_unwrap = compute_phase(outs_spectral)
spectral_unwrap -= 2*np.pi
plot_spectral_phase(opd_range, spectral_phase, spectral_axs, 'OPD [nm]', 
                    save_path=path + f'analysis_recons_phase_dm.png')
plot_spectral_phase(opd_range, spectral_unwrap, spectral_axs, 'OPD [nm]', 
                    save_path=path + f'analysis_recons_phase_dm_unwrap.png')

dm_fit = np.polyfit(opd_range, spectral_unwrap, 1)
dm_period = 2 * np.pi / dm_fit[0, px_min:px_max]
dm_period = dm_period / spectral_axs[0][px_min:px_max] # in lambda units

spectral_unwrap_norm = spectral_unwrap * spectral_axs[0] / (2*np.pi)
dm_fit_norm = np.polyfit(opd_range, spectral_unwrap_norm[:,px_min:px_max], 1)

dm_ramps = np.array([np.poly1d(dm_fit[:,i])(opd_range) for i in range(dm_fit.shape[1])])
dm_ramps = dm_ramps.T
spectral_unwrap_rescaled = spectral_unwrap - dm_ramps
figr, axsr = plot_spectral_phase(opd_range, spectral_unwrap_rescaled, spectral_axs, 
                    'OPD [nm]', 'Residuals [rad]')
axsr.set_ylim(-0.45, 0.45)
figr.savefig(path + f'analysis_recons_phase_dm_unwrap_residuals.png', dpi=300, bbox_inches='tight', format='png')

step_opd = np.diff(opd_range).mean()
step_wl = np.diff(spectral_axs[0]).mean()
fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, FIGURE_WIDTH / FIGURE_RATIO))
image = ax.imshow(spectral_unwrap_rescaled[:,px_min:px_max], aspect='auto', origin='lower',
                  extent=[spectral_axs[0, px_min:px_max][0]-step_wl/2, spectral_axs[0, px_min:px_max][-1]+step_wl/2, 
                          opd_range[0]-step_opd/2, opd_range[-1]+step_opd/2])
ax.set_xlabel('Wavelength [nm]', fontsize=LABEL_FS)
ax.set_ylabel('OPD [nm]', fontsize=LABEL_FS)
ax.set_title('DM phase residuals', fontsize=TITLE_FS)
ax.tick_params(labelsize=TICK_FS)
colorbar = fig.colorbar(image, ax=ax)
colorbar.set_label('Residual phase [rad]', fontsize=LABEL_FS)
colorbar.ax.tick_params(labelsize=TICK_FS)
fig.tight_layout()
figr.savefig(path + f'analysis_recons_phase_dm_unwrap_residuals_map.png', dpi=300, bbox_inches='tight', format='png')



#### TOPA scan ####
data = np.load(path + filename_topa)
topa_outs = data['data']
topa_outs_spectral = data['spectral_data']
power_ramp = data['power_ramp']
topa_max_bright_idx = np.argmax(topa_outs[:, 3])
topa_max_null_idx = np.argmax(topa_outs[:, 0])
topa_max_bright_pos = power_ramp[np.argmax(topa_outs[:, 3])]
topa_max_null_pos = power_ramp[np.argmax(topa_outs[:, 0])]

# plot_output_flux(power_ramp, topa_outs, 'Power ramp [W]', pair)

topa_phase, topa_unwrap = compute_phase(topa_outs)
topa_spectral_phase, topa_spectral_unwrap = compute_phase(topa_outs_spectral)
mask = np.where(topa_spectral_unwrap[0] < 0 )[0]
topa_spectral_unwrap[:, mask] += 2*np.pi
plot_spectral_phase(power_ramp, topa_spectral_phase, spectral_axs, 
                    'Power [W]', save_path=path + f'analysis_recons_phase_topa.png')
plot_spectral_phase(power_ramp, topa_spectral_unwrap, spectral_axs, 
                    'Power [W]', save_path=path + f'analysis_recons_phase_topa_unwrap.png')
topa_fit = np.polyfit(power_ramp, -topa_spectral_unwrap, 1)
topa_period = 2 * np.pi / topa_fit[0, px_min:px_max] #* 2.1e-3 * 2.5e-5 * 0.7/1000 / 8.9
topa_period = topa_period / (spectral_axs[0][px_min:px_max]*1e-9)**2 # in lambda units

topa_spectral_unwrap_norm = topa_spectral_unwrap * spectral_axs[0] / (2*np.pi)
topa_fit_norm = np.polyfit(power_ramp, topa_spectral_unwrap_norm[:,px_min:px_max], 1)

topa_ramps = np.array([np.poly1d(topa_fit[:,i])(power_ramp) for i in range(topa_fit.shape[1])])
topa_ramps = topa_ramps.T
topa_spectral_unwrap_rescaled = topa_spectral_unwrap + topa_ramps
figr, axsr = plot_spectral_phase(power_ramp, topa_spectral_unwrap_rescaled, spectral_axs, 
                    'Power [W]', 'Residuals [rad]')
axsr.set_ylim(-0.45, 0.45)
figr.savefig(path + f'analysis_recons_phase_topa_unwrap_residuals.png', dpi=300, bbox_inches='tight', format='png')

step_power = np.diff(power_ramp).mean()
step_wl = np.diff(spectral_axs[0]).mean()
fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, FIGURE_WIDTH / FIGURE_RATIO))
image = ax.imshow(topa_spectral_unwrap_rescaled[:,px_min:px_max], aspect='auto', origin='lower',
                  extent=[spectral_axs[0, px_min:px_max][0]-step_wl/2, spectral_axs[0, px_min:px_max][-1]+step_wl/2, 
                          power_ramp[0]-step_power/2, power_ramp[-1]+step_power/2])
ax.set_xlabel('Wavelength [nm]', fontsize=LABEL_FS)
ax.set_ylabel('Power [W]', fontsize=LABEL_FS)
ax.set_title('TOPA phase residuals', fontsize=TITLE_FS)
ax.tick_params(labelsize=TICK_FS)
colorbar = fig.colorbar(image, ax=ax)
colorbar.set_label('Residual phase [rad]', fontsize=LABEL_FS)
colorbar.ax.tick_params(labelsize=TICK_FS)
fig.tight_layout()
figr.savefig(path + f'analysis_recons_phase_topa_unwrap_residuals_map.png', dpi=300, bbox_inches='tight', format='png')

fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, FIGURE_WIDTH / FIGURE_RATIO))
image = ax.imshow(spectral_unwrap_rescaled[:,px_min:px_max] - topa_spectral_unwrap_rescaled[:,px_min:px_max], aspect='auto', origin='lower',
                  extent=[spectral_axs[0, px_min:px_max][0]-step_wl/2, spectral_axs[0, px_min:px_max][-1]+step_wl/2, 
                          opd_range[0]-step_opd/2, opd_range[-1]+step_opd/2])
ax.set_xlabel('Wavelength [nm]', fontsize=LABEL_FS)
ax.set_ylabel('OPD [nm]', fontsize=LABEL_FS)
ax.set_title('Diff phase residuals', fontsize=TITLE_FS)
ax.tick_params(labelsize=TICK_FS)
colorbar = fig.colorbar(image, ax=ax)
colorbar.set_label('Residual phase [rad]', fontsize=LABEL_FS)
colorbar.ax.tick_params(labelsize=TICK_FS)
fig.tight_layout()

fig, ax1 = plt.subplots(figsize=(FIGURE_WIDTH, FIGURE_WIDTH / FIGURE_RATIO))
line1, = ax1.plot(spectral_axs[0][px_min:px_max], dm_period, color='tab:blue', label='DM scan')
ax1.set_xlabel('Wavelength [nm]', size=LABEL_FS)
ax1.set_ylabel(r'DM phase period [$\lambda$]', size=LABEL_FS, color='tab:blue')
ax1.tick_params(axis='y', labelcolor='tab:blue', labelsize=TICK_FS)
ax1.tick_params(axis='x', labelsize=TICK_FS)
ax1.grid()

ax2 = ax1.twinx()
line2, = ax2.plot(spectral_axs[0][px_min:px_max], topa_period, color='tab:orange', label='TOPA scan')
ax2.set_ylabel(r'TOPA phase period [$\lambda^2$]', size=LABEL_FS, color='tab:orange')
ax2.tick_params(axis='y', labelcolor='tab:orange', labelsize=TICK_FS)

ax1.legend(handles=[line1, line2], fontsize=LEGEND_FS, loc='best')
fig.suptitle(f'Phase periods', fontsize=TITLE_FS)
fig.tight_layout()
# fig.savefig(path + f'analysis_phase_periods.png', dpi=300, bbox_inches='tight', format='png')


ppp

### Null depth ###
dm_null = outs_spectral[max_bright_idx, 0] / outs_spectral[max_bright_idx, 3]
dm_null_noise = outs_spectral[max_bright_idx, 4] / outs_spectral[max_bright_idx, 3]
topa_null = topa_outs_spectral[topa_max_bright_idx, 0] / topa_outs_spectral[topa_max_bright_idx, 3]
topa_null_noise = topa_outs_spectral[topa_max_bright_idx, 4] / topa_outs_spectral[topa_max_bright_idx, 3]


plt.figure(figsize=(FIGURE_WIDTH*1.2, FIGURE_WIDTH*1.2 / FIGURE_RATIO))
plt.subplot(121)
plt.plot(spectral_axs[0], outs_spectral[max_bright_idx].T)
plt.grid()
plt.xticks(fontsize=TICK_FS)
plt.yticks(fontsize=TICK_FS)
plt.xlabel('Wavelength [nm]', size=LABEL_FS)
plt.ylabel('Flux [a.u]', size=LABEL_FS)
plt.title(f'Outputs at white fringe with DM scan', fontsize=TITLE_FS)
plt.subplot(122)
plt.plot(spectral_axs[0], topa_outs_spectral[topa_max_bright_idx].T)
plt.grid()
plt.xticks(fontsize=TICK_FS)
plt.yticks(fontsize=TICK_FS)
plt.xlabel('Wavelength [nm]', size=LABEL_FS)
plt.ylabel('Flux [a.u]', size=LABEL_FS)
plt.title(f'Outputs at white fringe with TOPS scan', fontsize=TITLE_FS)
plt.tight_layout()

plt.figure(figsize=(FIGURE_WIDTH, FIGURE_WIDTH / FIGURE_RATIO))
plt.semilogy(spectral_axs[0], dm_null, label='DM scan', c='blue')
plt.semilogy(spectral_axs[0], topa_null, label='TOPA scan', c='orange')
plt.semilogy(spectral_axs[0], dm_null_noise, label='DM scan noise', c='blue', linestyle='--', alpha=0.8)
plt.semilogy(spectral_axs[0], topa_null_noise, label='TOPA scan noise', c='orange', linestyle='--', alpha=0.8)
plt.grid()
plt.xticks(fontsize=TICK_FS)
plt.yticks(fontsize=TICK_FS)
plt.xlabel('Wavelength [nm]', size=LABEL_FS)
plt.ylabel('Null depth', size=LABEL_FS)
plt.title(f'Null depth for pair ({pair[0]}-{pair[1]})', fontsize=TITLE_FS)
plt.legend(fontsize=LEGEND_FS)
plt.tight_layout()
plt.savefig(path + f'analysis_null_depth.png', dpi=300, bbox_inches='tight', format='png')




