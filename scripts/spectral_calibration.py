#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 15 14:49:04 2026

@author: photonics
"""

import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from datetime import datetime


def open_fits(file_path):
    hdu = fits.open(file_path)
    return hdu[0].data

path = '/media/photonics/SSD 128Go/data/2026-01-22/spectral_calibration/'
dark = open_fits(path+'dark.fits')
data1550 = open_fits(path+'1550nm.fits') - dark
data1530 = open_fits(path+'1530nm.fits') - dark
data1540 = open_fits(path+'1540nm.fits') - dark
data1560 = open_fits(path+'1560nm.fits') - dark

wl = np.array([1530, 1540, 1550, 1560])

# plt.figure()
# plt.imshow(data1527, vmin=0, vmax=1000, origin='lower')
# plt.title('1527')

# plt.figure()
# plt.imshow(data1550, vmin=0, vmax=1000, origin='lower')
# plt.title('1550')

# plt.figure()
# plt.imshow(data1553, vmin=0, vmax=1000, origin='lower')
# plt.title('1553')

# plt.figure()
# plt.imshow(data1565, vmin=0, vmax=1000, origin='lower')
# plt.title('1565')

d1530 = data1530[220:274,:].mean(0)
d1540 = data1540[220:274,:].mean(0)
d1550 = data1550[220:274,:].mean(0)
d1560 = data1560[220:274,:].mean(0)

plt.figure()
plt.plot(d1530, label=str(wl[0]))
plt.plot(d1540, label=str(wl[1]))
plt.plot(d1550, label=str(wl[2]))
plt.plot(d1560, label=str(wl[3]))
plt.grid()
plt.legend(loc='best')
plt.xlabel('Pixel column')
plt.ylabel('Intensity (count)')
plt.savefig(path+'integrated_flux.png', dpi=150)

peaks_pos = np.array([np.argmax(d1530), np.argmax(d1540), np.argmax(d1550), np.argmax(d1560)])

plt.figure()
plt.plot(peaks_pos, wl, '.')
plt.grid()

coeffs = np.polyfit(peaks_pos, wl, deg=1)
p = np.poly1d(coeffs)

x = np.arange(640)
y = p(x)

plt.plot(x, y)
plt.xlabel('Pixel column')
plt.ylabel('Wavelength (nm)')
plt.savefig(path+'spectral_calibration_curve.png', dpi=150)

print('=== RESULTS ===')
print('Pixel width:\t\t\t\t%.3f nm'%(coeffs[0]))
print('Bandwidth on detector:\t\t%.2f nm'%(y.max() - y.min()))
print('Spectrum span on detector:\t%.2f - %.2f nm'%(y.min(), y.max()))

with open(path+'log.txt', 'w') as f:
    date_now = datetime.now()
    f.write(date_now.isoformat()+'\n')
    f.write('=== RESULTS ===\n')
    f.write('Pixel width:\t\t\t\t%.3f nm\n'%(coeffs[0]))
    f.write('Bandwidth on detector:\t\t%.2f nm\n'%(y.max() - y.min()))
    f.write('Spectrum span on detector:\t%.2f - %.2f nm\n'%(y.min(), y.max()))
    
np.save(path+'coeffs_px_to_nm', coeffs)