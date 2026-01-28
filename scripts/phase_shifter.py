#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec  2 15:50:12 2025

@author: photonics
"""

import phobos
import matplotlib.pyplot as plt
import numpy as np
from xaosim.shmlib import shm
from scipy.optimize import curve_fit
from tqdm import tqdm
from time import sleep, time
from datetime import datetime
import json
from injection_opt import check_cropping, create_dir, get_frame, crop_frames
from time import sleep

chip = phobos.Chip(6)
# chip.set_currents([300., 0., 0., 0.])
# chip.set_voltages([30., 0., 0., 0.])


# voltages = chip.get_voltages()
# currents = chip.get_currents()

# print('voltages', voltages)
# print('currents', currents)

# =============================================================================
# Test the new set_power() method with auto-calibration
# =============================================================================
# channel = phobos.PhaseShifter(17)

# channel.dac_calibration(verbose=True)

# power_range = np.linspace(0, 1, 31) # in watt

# real_voltage = np.empty_like(power_range)
# real_current = np.empty_like(power_range)
# real_power = np.empty_like(power_range)

# for i, p in enumerate(power_range):
#     channel.set_power(p)
#     real_voltage[i] = channel.get_voltage()
#     real_current[i] = channel.get_current()
#     real_power[i] = channel.get_power()

# fig, axs = plt.subplots(1, 3, figsize=(12, 4))
# axs[0].plot(power_range, real_voltage, '-o')
# axs[0].set_ylabel("Voltage (V)")
# axs[0].set_xlabel("Set Power (W)")
# axs[0].grid()

# axs[1].plot(power_range, real_current, '-o')
# axs[1].set_ylabel("Current (mA)")
# axs[1].set_xlabel("Set Power (W)")
# axs[1].grid()

# axs[2].plot(power_range, real_power, '-o')
# axs[2].plot(power_range, power_range, '--', label='Ideal')
# axs[2].set_ylabel("Measured Power (W)")
# axs[2].set_xlabel("Set Power (W)")
# axs[2].legend()
# axs[2].grid()
# plt.tight_layout()

# # =============================================================================
# # Calibrate phase vs power
# # =============================================================================
# ramp = np.linspace(0., 1., 101)
# datacube = []
# channel = phobos.PhaseShifter(17)
# wait = 0.005

# cam = shm('/dev/shm/cred1.im.shm', nosem=False) # the source of data
# semid = 0
# cam.catch_up_with_sem(semid)

# dk = shm('/dev/shm/cred3_dark.im.shm')
# dark = dk.get_latest_data()

# crop_size = 10 # px window around the output
# crop_centers = np.array([(319, 311),
#                         (352, 311),
#                         (385, 311),
#                         (417, 311)])

# crop_coords = [((crop_centers[0,0]-crop_size//2, crop_centers[0,0]+crop_size//2+1), (crop_centers[0,1]-crop_size//2, crop_centers[0,1]+crop_size//2+1)), 
#                ((crop_centers[1,0]-crop_size//2, crop_centers[1,0]+crop_size//2+1), (crop_centers[1,1]-crop_size//2, crop_centers[1,1]+crop_size//2+1)),
#                ((crop_centers[2,0]-crop_size//2, crop_centers[2,0]+crop_size//2+1), (crop_centers[2,1]-crop_size//2, crop_centers[2,1]+crop_size//2+1)),
#                ((crop_centers[3,0]-crop_size//2, crop_centers[3,0]+crop_size//2+1), (crop_centers[3,1]-crop_size//2, crop_centers[3,1]+crop_size//2+1))] # [((x1, x2), (y1, y2))]*4

# # check_cropping(crop_coords)
# # ppp

# for p in ramp:
#     channel.set_power(p)
#     img0 = get_frame(cam, semid)
#     img0 = img0 - dark
#     datacube.append(img0)

# datacube = np.array(datacube)
# cropped_cube = crop_frames(datacube, crop_coords)
# flux = np.mean(cropped_cube, axis=(-1, -2))

# channel.turn_off()

# plt.figure()
# plt.plot(ramp, flux)
# plt.xlabel("Power (W)")
# plt.ylabel("Flux (ADU)")
# plt.title("Flux vs Power")
# plt.grid()

# =============================================================================
# Playing with phase shifter
# =============================================================================
