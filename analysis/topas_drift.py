#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 14:09:01 2026

@author: mmartinod
"""

import numpy as np
import matplotlib.pyplot as plt
import pickle
import os
from pathlib import Path
from typing import Any, Iterable

plt.ion()

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

def look_for_file(path, pattern, extension):
    """Search for files in a directory that match a given pattern.

    Parameters
    ----------
    path : str | os.PathLike[str]
        The directory path to search in.
    pattern : str
        The pattern to match file names against.

    Returns
    -------
    list[str]
        A list of file paths that match the given pattern.
    """
    return [os.path.join(path, elt) for elt in os.listdir(path) if pattern in elt and elt.endswith(extension)]

def load_pickle_sans_popup(path):
    was_interactive = plt.isinteractive()
    plt.ioff()
    try:
        with open(path, "rb") as f:
            obj = pickle.load(f)
    finally:
        plt.close("all")          # ferme toute figure recréée
        if was_interactive:
            plt.ion()
    return obj

date = '2026-07-29'
path = f'/home/mmartinod/projects/photonics/data/{date}_24e476e/1_injection_drift/'

datafile = look_for_file(path, 'topa_stability_all_shifters_0.6W_2026-07-', '.npy')
data = np.load(datafile[0])
afterfile = look_for_file(path, f'injection_drift_after4ps-cold_{date}', '.npy')
after_data = np.load(afterfile[0])

beforefile = look_for_file(path, f'injection_drift_before4ps_{date}', '.pkl')
afterfile = look_for_file(path, f'injection_drift_after4ps-cold_{date}', '.pkl')
before, _ = load_pickle_files(beforefile)
after, _ = load_pickle_files(afterfile)


pattern = f'injection_drift_during4ps_{date}T'
list_files = sorted([path + elt for elt in os.listdir(path) if pattern in elt])
during, normalized_paths = load_pickle_files(list_files)

time = [0.] + [elt['actual_elapsed'] for elt in during] + [after[0]['actual_elapsed']]
tip = [before[0]['max_inj']['max_tt'][:, 0]] + [elt['max_tt'][:, 0] for elt in during] + [after[0]['max_tt'][:, 0]]
tilt = [before[0]['max_inj']['max_tt'][:, 1]] + [elt['max_tt'][:, 1] for elt in during] + [after[0]['max_tt'][:, 1]]

time = np.array(time)
tip = np.array(tip)
tilt = np.array(tilt)

tip[tip == 0] = np.nan
tilt[tilt == 0] = np.nan

# argsort = np.argsort(time)
# time = time[argsort]
# tip = tip[argsort]
# tilt = tilt[argsort]

t = np.append(data[:,1], after_data[1])
temperatures = np.append(data[:,2], after_data[2])
target_power = np.append(data[:,3], after_data[3])
applied_power = np.append(data[:,4:8], after_data[4:8])
flux_currentinj = np.append(data[:,8:12]-data[:,12][:,None], after_data[8:12][None,:]-after_data[12], axis=0)
flux_origininj = np.append(data[:,13:-1]-data[:,-1][:,None], after_data[13:-1][None,:]-after_data[-1], axis=0)
dark_currentinj = np.append(data[:,12], after_data[12])
dark_origininj = np.append(data[:,-1], after_data[-1])

width = 18
ratio_fig = 1.618

plt.figure(figsize=(width, width/ratio_fig))
title_fs = 20
label_fs = 18
tick_fs = 14
legend_fs = 14
marker_sz = 10
ax1 = plt.subplot(311)
ax1.plot(time, tip, 'o', markersize=marker_sz)
ax1.grid()
ax1.set_ylabel('Tip [rad]', fontsize=label_fs)
ax1.set_xlabel('Time [s]', fontsize=label_fs)
ax1.tick_params(labelsize=tick_fs)
ax1.set_title('Tip evolution', fontsize=title_fs)
ax1.set_ylim(-3, 3)

ax2 = plt.subplot(312, sharex=ax1)
ax2.plot(time, tilt, 'o', markersize=marker_sz)
ax2.grid()
ax2.set_ylabel('Tilt [rad]', fontsize=label_fs)
ax2.set_xlabel('Time [s]', fontsize=label_fs)
ax2.tick_params(labelsize=tick_fs)
ax2.set_title('Tilt evolution', fontsize=title_fs)
ax2.set_ylim(-3, 3)

ax3 = plt.subplot(313)
ax3.plot(t, flux_currentinj.mean(1), '+', label='Updated TT', markeredgewidth=2.5, markersize=marker_sz)
ax3.plot(t, flux_origininj.mean(1), 'x', label='Original TT', markeredgewidth=2.5, markersize=marker_sz)
ax3.grid()
ax3.set_ylabel('Flux [a.u.]', fontsize=label_fs)
ax3.set_xlabel('Time [s]', fontsize=label_fs)
ax3.tick_params(labelsize=tick_fs)
ax3.set_title('Flux evolution', fontsize=title_fs)
ax3.legend(fontsize=legend_fs)

# Event times in seconds (x-axis is in seconds)
topas_on_s = 10 * 60
topas_off_s = 20 * 60

for ax in (ax1, ax2, ax3):
    ax.axvline(topas_on_s, color='tab:green', linestyle='--', linewidth=1.8, alpha=0.9)
    ax.axvline(topas_off_s, color='tab:red', linestyle='--', linewidth=1.8, alpha=0.9)

    ax.text(
        topas_on_s, 0.98, 'TOPAs ON',
        transform=ax.get_xaxis_transform(),
        color='tab:green', fontsize=12, ha='left', va='top'
    )
    ax.text(
        topas_off_s, 0.98, 'TOPAs OFF',
        transform=ax.get_xaxis_transform(),
        color='tab:red', fontsize=12, ha='left', va='top'
    )

ax3.set_xlim(ax1.get_xlim())  # same x-limits as first two subplots
plt.tight_layout()
plt.savefig(path + f'tip_tilt_flux_{date}.png', dpi=300)

# plt.close('all')

"""
Observational report (2026-07-27)
--------------------
The first 10 minutes are stable. Tip and tilt remain close to their initial
values, and the mean injected flux stays near 9.6e2 a.u. for both references.

After the TOPAs are powered at 0.6 W (t = 600 s), the four channels show a
clear drift in both tip and tilt. The drift is not uniform across beams.

The flux decrease starts shortly after the TOPAs are turned on and becomes
severe within a few minutes. Around t = 800 s, the mean flux has already
dropped to about 4.7 a.u. with the updated tip-tilt reference and to about
2.6 a.u. with the original reference. Near t = 1000 s, both curves are
close to zero, which indicates a nearly complete loss of injection.

After the TOPAs are switched off at t = 1200 s, the injection does not recover
immediately. The flux remains close to zero for a significant fraction of the
remaining acquisition, then shows only a partial recovery near the end of the
record. 

Conclusion: in this dataset, the TOPAs introduce a strong thermally induced
misalignment that mainly appears as a tip-tilt drift and leads to a major loss
of coupling efficiency. Updating the tip-tilt reference improves the residual
flux during and after heating, but it does not compensate the thermal drift
well enough to maintain stable injection over the 30-minute sequence.
"""

"""
Observational report (2026-07-28)
--------------------
Four 1550 nm beams were injected into the 4x4 MMI. The injection was optimized
by independently adjusting the tip and tilt of four segmented-mirror elements.

Before the TOPAs were powered (t < 600 s), the tip and tilt settings were stable
for all four beams. The mean flux was also stable, at approximately 1.37e3 a.u.
for both the updated and original tip-tilt references.

Once 0.6 W was applied to the TOPAs, the tip and tilt settings drifted in
different directions and with different amplitudes for the four beams. This
drift coincided with a rapid loss of injection. At about t = 775 s, the mean
flux had fallen to approximately 5.5e2 a.u. with the updated reference and
4.1e2 a.u. with the original reference. By t = 1034 s, both curves were close
to 10 a.u., indicating an almost complete loss of coupling.

After the TOPAs were switched off at t = 1200 s, the flux remained near zero in
the available record. The last flux measurement, at about t = 1535 s, reached
only 7.2e1 a.u. with the updated reference and 9.9e1 a.u. with the original
reference. A later tip-tilt measurement near t = 2500 s is closer to the
initial settings, but there is no corresponding late flux measurement.

Conclusion: applying power to the TOPAs is associated with a strong,
thermally induced misalignment and a substantial reduction in injection into
the MMI. The updated tip-tilt reference provides a modest advantage during the
early flux decrease, but it does not prevent the loss of coupling. The
available flux data do not establish whether full recovery occurs after a
longer cooling time.
The TOPS move the chip undr the heat resulting in TT drift and enventually
misalignment too big to be compensated by the semgented mirrors.
"""

"""
Observational report (2026-07-29)
---------------------------------
Four monochromatic 1550 nm beams were injected into the 4x4 MMI. The injection
was optimized by adjusting the tip and tilt of four segmented-mirror elements.

Before the TOPAs were powered (t < 600 s), the tip and tilt settings were
stable for the four beams. The mean flux was also stable, close to 1.23e3 a.u.
for both the updated and original tip-tilt references.

After 0.6 W was applied to the TOPAs, the tilt settings drifted strongly while
the tip settings evolved more moderately. This behavior coincided with a large
loss of injected flux. At about t = 824 s, the mean flux was approximately
8.9e2 a.u. with the updated reference, compared with 1.8e2 a.u. with the
original reference. By approximately t = 1200 s, both flux measurements were
close to zero, indicating a near-complete loss of coupling.

Switching the TOPAs off did not produce an immediate recovery. The flux remained
very low for several minutes after t = 1200 s. A measurement near t = 1570 s
shows a partial recovery with the updated reference (about 6.8e2 a.u.), while
the original reference remains low (about 2.6e1 a.u.). The late measurement near
t = 3313 s is close to the initial flux level for both references.

Conclusion: the measurements are consistent with a thermally induced displacement
of the chip relative to the injection alignment, causing a tip-tilt drift and a
temporary loss of coupling. Updating the tip-tilt reference delays the flux loss
and improves the early recovery, but it does not maintain injection throughout
the heated interval. The late measurement indicates that the alignment can
largely recover after a longer cooling period.
"""

# from PIL import Image, ImageDraw, ImageFont
# from datetime import datetime

# def add_text_to_png(
#     input_png: str | Path,
#     output_png: str | Path,
#     text: str,
#     x: int,
#     y: int,
#     color: tuple[int, int, int, int] | tuple[int, int, int] = (255, 255, 255),
#     font_size: int = 32,
#     font_path: str | None = None,
#     anchor: str = "lt",
#     stroke_width: int = 0,
#     stroke_color: tuple[int, int, int, int] | tuple[int, int, int] = (0, 0, 0),
#     preview: bool = False,
# ) -> Path:
#     input_png = Path(input_png)
#     output_png = Path(output_png)

#     if not input_png.exists():
#         raise FileNotFoundError(f"Input file not found: {input_png}")
#     if input_png.suffix.lower() != ".png":
#         raise ValueError("Input file must be a PNG image.")

#     if font_path:
#         font = ImageFont.truetype(font_path, font_size)
#     else:
#         try:
#             font = ImageFont.truetype("DejaVuSans.ttf", font_size)
#         except OSError:
#             font = ImageFont.load_default()

#     image = Image.open(input_png).convert("RGBA")
#     draw = ImageDraw.Draw(image)

#     draw.text(
#         (x, y),
#         text,
#         fill=color,
#         font=font,
#         anchor=anchor,
#         stroke_width=stroke_width,
#         stroke_fill=stroke_color,
#     )

#     if preview:
#         plt.figure(figsize=(10, 6))
#         plt.imshow(image)
#         plt.axis("off")
#         plt.title("Preview before save")

#     output_png.parent.mkdir(parents=True, exist_ok=True)
#     image.save(output_png, format="PNG")
#     return output_png

# def make_gif(
#     image_paths: list[str | Path],
#     output_gif: str | Path,
#     duration_ms: int = 200,
#     loop: int = 0,
# ) -> Path:
#     output_gif = Path(output_gif)
#     frames = [Image.open(p).convert("RGB") for p in image_paths]

#     if not frames:
#         raise ValueError("image_paths must contain at least one image.")

#     output_gif.parent.mkdir(parents=True, exist_ok=True)
#     frames[0].save(
#         output_gif,
#         format="GIF",
#         save_all=True,
#         append_images=frames[1:],
#         duration=duration_ms,
#         loop=loop,
#     )
#     return output_gif

# if date == '2026-07-28':
#     figure_list = sorted([elt for elt in os.listdir(path) if elt.endswith(".png") and f"injection_map_{date}" in elt and not '_annotated' in elt])

#     elapsed = []
#     for f in figure_list:
#         figure_png = Path(path) / f
#         annotated_file = f[:-4]+"_annotated.png"
#         annotated_png = Path(path) / annotated_file
#         timestamp_str = f.removeprefix("injection_map_").removesuffix(".png")
#         dt = datetime.fromisoformat(timestamp_str)
#         elapsed.append(dt)

#     elapsed = np.array([(elt - elapsed[0]).total_seconds() for elt in elapsed])
#     for i, f in enumerate(figure_list):
#         figure_png = Path(path) / f
#         annotated_file = f[:-4]+"_annotated.png"
#         annotated_png = Path(path) / annotated_file

#         text1 = "Elapsed time = %03d s"%(elapsed[i])
#         if elapsed[i] >= topas_on_s and elapsed[i] <= topas_off_s:
#             text2 = ", TOPS = 0.6 W"
#         else:
#             text2 = ", TOPS off"

#         add_text_to_png(
#             input_png=figure_png,
#             output_png=annotated_png,
#             text=text1 + text2,
#             x=0,
#             y=10,
#             color=(255, 0, 0, 255),
#             font_size=20,
#             anchor="lt",
#             stroke_width=0,
#             stroke_color=(255, 0, 0, 0),
#             preview=True,
#         )

#     annotated_paths = [Path(path) / (f[:-4] + "_annotated.png") for f in figure_list]
#     gif_path = Path(path) / f"injection_map_{date}.gif"
#     make_gif(annotated_paths, gif_path, duration_ms=750, loop=0)
