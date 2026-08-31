#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import matplotlib.pyplot as plt
import phobos

plt.ion()

chip = phobos.Arch6()
channels = range(4)
n_roi = 4

for i, seg in enumerate([135, 136, 137, 138]):

    taps = ['L47', 'L46', 'L45', 'L44']

    path = '/home/mmartinod/projects/photonics/data/2026-08-26_503082d/1_crosstalks/'
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
            axs[ch, shifter_idx].set_title(f'Ch. {ch}, Tap {taps[ch]}, Shifter {shifter.channel}', fontsize=14)
            axs[ch, shifter_idx].set_xlabel('Power (W)', fontsize=13)
            axs[ch, shifter_idx].set_ylabel('Flux (ADU)', fontsize=13)
            axs[ch, shifter_idx].tick_params(axis='both', labelsize=11)
            axs[ch, shifter_idx].grid(True)
            if ch == 1 and shifter_idx == 0:
                axs[ch, shifter_idx].legend([f'Output {i}' for i in range(n_roi)] + ['Mean'], loc='best', fontsize=11)
    # extra hspace keeps each row's title clear of the xlabel above it
    fig.tight_layout(rect=[0, 0.03, 1, 0.97], h_pad=4.5, w_pad=0.5)
    # fig.savefig(path + f'analysis_crosstalks_phase_shifter_seg{taps[i]}.png', dpi=300)