#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import matplotlib.pyplot as plt
import phobos
from scipy.optimize import curve_fit

plt.ion()

def model(x, eps, f, phi, slope, intersect):
    I0 = slope * x + intersect
    I = I0 * (1 + eps) + 2 * I0 * eps**0.5 * np.cos(2 * np.pi * f * x + phi)
    return I

chip = phobos.Arch6()
channels = range(4)
n_roi = 4

taps = ['L47', 'L46', 'L45', 'L44']
path = '/home/mmartinod/projects/photonics/data/2026-08-26_503082d/1_crosstalks/'

res2 = []
res3 = []
for i, seg in enumerate([138, 137, 136, 135]):

    filename = f'crosstalks_phase_shifter_seg{seg}.npz'
    fdata = np.load(path + filename)
    power_ramp = fdata['power_ramp']
    data = fdata['flux']

    fig, axs = plt.subplots(4, 4, figsize=(16, 16))
    fig.suptitle('Phase shiter cross-talks', fontsize=20)
    for ch in channels:
        for shifter_idx, shifter in enumerate(chip.shifters):
            axs[ch, shifter_idx].plot(power_ramp, data[ch, shifter_idx][:, :n_roi])
            axs[ch, shifter_idx].plot(power_ramp, data[ch, shifter_idx][:, :n_roi].mean(1), '--', c='k')
            axs[ch, shifter_idx].set_title(f'Tap {taps[ch]}, Shifter {shifter.channel}', fontsize=14)
            axs[ch, shifter_idx].set_xlabel('Power (W)', fontsize=13)
            axs[ch, shifter_idx].set_ylabel('Flux (ADU)', fontsize=13)
            axs[ch, shifter_idx].tick_params(axis='both', labelsize=11)
            axs[ch, shifter_idx].grid(True)
            if ch == i:
                for k in range(n_roi):
                    p0 = [0.1, 1/0.3, 0, 0, data[ch, shifter_idx][:, k].mean()]
                    boundaries = ([0, 1/0.7, -np.pi, -np.inf, 0], [1, 1/0.1, np.pi, np.inf, np.inf])
                    popt, _ = curve_fit(model, power_ramp, data[ch, shifter_idx][:, k], 
                                        p0=p0, 
                                        bounds=boundaries)
                    axs[ch, shifter_idx].plot(power_ramp, model(power_ramp, *popt), '--')
                    res2.append([seg, shifter.channel, k, popt[0]])
                    res3.append([int(taps[i][1:]), shifter.channel, k, popt[0]])
            if ch == 1 and shifter_idx == 0:
                axs[ch, shifter_idx].legend([f'Output {i}' for i in range(n_roi)] + ['Mean'], loc='best', fontsize=11)
    # extra hspace keeps each row's title clear of the xlabel above it
    fig.tight_layout(rect=[0, 0.03, 1, 0.97], h_pad=4.5, w_pad=0.5)
    # fig.savefig(path + f'analysis_crosstalks_phase_shifter_seg{seg}_{taps[i]}_with_fits.png', dpi=300)

res2 = np.array(res2)
res3 = np.array(res3)

input_ids = np.array([47, 46, 45, 44])  # Acquisition / physical order
shifter_ids = np.array([shifter.channel for shifter in chip.shifters])
output_ids = np.arange(n_roi)

cube = np.full(
    (len(input_ids), len(shifter_ids), len(output_ids)),
    np.nan,
)

input_index = {value: index for index, value in enumerate(input_ids)}
shifter_index = {value: index for index, value in enumerate(shifter_ids)}
output_index = {value: index for index, value in enumerate(output_ids)}

for input_id, shifter_id, output_id, epsilon in res3:
    cube[
        input_index[int(input_id)],
        shifter_index[int(shifter_id)],
        output_index[int(output_id)],
    ] = epsilon

fig, axes = plt.subplots(
    1, len(input_ids), figsize=(18, 5), sharey=True, constrained_layout=True
)

cross_talk_percent = cube * 100
vmax = max(np.nanmax(cross_talk_percent), 1e-12)

for axis, input_id, values in zip(axes, input_ids, cross_talk_percent):
    image = axis.imshow(
        values,
        cmap="viridis",
        vmin=0,
        vmax=vmax,
        aspect="equal",
    )
    axis.set_title(f"Injected L{input_id}", fontsize=18, pad=12)
    axis.set_xlabel("Output", fontsize=16, labelpad=8)
    axis.set_xticks(output_ids)
    axis.set_xticklabels([f"Out {output_id}" for output_id in output_ids])
    axis.set_yticks(np.arange(len(shifter_ids)))
    axis.set_yticklabels([f"PS {shifter_id}" for shifter_id in shifter_ids])
    axis.tick_params(axis="both", labelsize=14)

    for (row, column), value in np.ndenumerate(values):
        axis.text(
            column,
            row,
            f"{value:.4f}",
            ha="center",
            va="center",
            color="white",# if value > vmax * 0.55 else "black",
            fontsize=12,
        )

axes[0].set_ylabel("Phase shifter", fontsize=16, labelpad=12)
colorbar = fig.colorbar(image, ax=axes)
colorbar.set_label(r"Fitted cross-talk $\epsilon$ (%)", fontsize=16, labelpad=12)
colorbar.ax.tick_params(labelsize=14)
fig.suptitle("Phase-shifter cross-talk map", fontsize=22)
fig.savefig(path + f'analysis_crosstalks_map.png', dpi=300)