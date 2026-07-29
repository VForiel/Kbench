#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 14:09:01 2026

@author: mmartinod
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import pickle

plt.ion()

def sellemier(wl):
    n_eff2 = 1 + 3.0249 * wl**2 / (wl**2 - 0.1353406**2) + 40314 * wl**2 / (wl**2 - 1239.842**2)
    return np.sqrt(n_eff2)

n_roi = 4
path = '/home/mmartinod/projects/photonics/data/2026-06-18_75b9dd8/2_hypernull/'
spec_law = np.load(path + 'spec_cal_coeffs_and_errors.npy')
ref_cart = 230.
hyperdata00 = np.load(path + 'dm_scan_kernel_4x4_datacube_injbalanced.npy')[:,:,:,:n_roi,:] # 137, 136, 135, nroi, spectral channels
print(hyperdata00.shape)
hyperdata0 = hyperdata00 / np.sum(hyperdata00, axis=3, keepdims=True)
hyperdata = np.mean(hyperdata0, axis=-1)
kernel0 = hyperdata0[:,:,:,2,:] - hyperdata0[:,:,:,1,:]
kernel = np.mean(kernel0, axis=-1)
start = -2530.
end = 230.

output_labels = ['Null', 'Grey+', 'Grey-', 'Bright']
o = 3

piston_range = np.linspace(start, end, hyperdata.shape[0])


spectral_axs = np.arange(hyperdata0.shape[-1])
spectral_axs = np.array([np.polyval(spec_law[0][i], spectral_axs) for i in range(n_roi)])
spectral_step = spectral_axs[:,1] - spectral_axs[:,0]

argmin = np.unravel_index(np.argmin(hyperdata[:,:,:,o]), hyperdata[:,:,:,o].shape)
argmin = np.array(argmin)
argmax = np.unravel_index(np.argmax(hyperdata[:,:,:,3]), hyperdata[:,:,:,3].shape)
argmax = np.array(argmax)

selector = argmax.copy()
# selector[1] = 27
# selector[0] = 28
# selector[2] = 4

o = 0

opd_chip = 2*(piston_range[argmax] - ref_cart) / sellemier(1.55)

opd_range = (piston_range[:,None] - ref_cart) * 2 + abs(opd_chip[None,:])
opd_range = opd_range.T

opd_range = (piston_range - ref_cart) * 2
opd_range = np.array([opd_range, opd_range, opd_range])
opd_step = opd_range[:,1] - opd_range[:,0]

print(argmin, hyperdata[:,:,:,o].min())
print(argmax, hyperdata[:,:,:,3].max())

plt.figure(figsize=(12, 8))
plt.subplot(131)
plt.plot(opd_range[0], hyperdata[:, selector[1], selector[2], o], 'o-')
plt.grid()
plt.xlabel('OPD [nm]')
plt.title(f'{output_labels[o]} output, \n p2 = {opd_range[1][selector[1]]:.2f} nm, \n p3 = {opd_range[2][selector[2]]:.2f} nm')

plt.subplot(132)
plt.plot(opd_range[1], hyperdata[selector[0], :, selector[2], o], 'o-')
plt.grid()
plt.xlabel('OPD [nm]')
plt.title(f'{output_labels[o]} output, \n p1 = {opd_range[0][selector[0]]:.2f} nm, \n p3 = {opd_range[2][selector[2]]:.2f} nm')

plt.subplot(133)
plt.plot(opd_range[2], hyperdata[selector[0], selector[1], :, o], 'o-')
plt.grid()
plt.xlabel('OPD [nm]')
plt.title(f'{output_labels[o]} output, \n p1 = {opd_range[0][selector[0]]:.2f} nm, \n p2 = {opd_range[1][selector[1]]:.2f} nm')
plt.tight_layout()


plt.figure()
plt.semilogy(spectral_axs[o], hyperdata0[selector[0], selector[1], selector[2], :, :].T)
plt.semilogy(spectral_axs[o], hyperdata00[selector[0], selector[1], selector[2], :, :].sum(0))
plt.grid()
plt.xlabel('Wavelength [nm]')
plt.ylabel('Intensity [a.u.]')
plt.title(f'{output_labels[o]} output, \n p1 = {opd_range[0][selector[0]]:.2f} nm, \n p2 = {opd_range[1][selector[1]]:.2f} nm, \n p3 = {opd_range[2][selector[2]]:.2f} nm')

plt.close('all')
for k in range(3):
    fixed = [j for j in range(3) if j != k]
    suptitle = ', '.join(f'p{j+1} = {opd_range[j][selector[j]]:.2f} nm' for j in fixed)
    idx = list(selector)
    idx[k] = slice(None)

    from matplotlib.colors import LogNorm
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle(suptitle + '\n', fontsize=20)
    im = None
    norm = LogNorm(vmin=max(hyperdata0.min(), 0.02), vmax=hyperdata0.max())
    for i, ax in enumerate(axes.flat):
        ax.set_title(f'{output_labels[i]} output', fontsize=18)
        im = ax.imshow(hyperdata0[tuple(idx) + (i, slice(None))],
                   aspect='auto',
                   extent=[spectral_axs[i][0] - spectral_step[i]*0.5,
                           spectral_axs[i][-1] + spectral_step[i]*0.5,
                           piston_range[-1]-opd_step[0]*0.5, 
                           piston_range[0]+opd_step[0]*0.5],
                   norm=norm,
                   )
        if i >= 2:
            ax.set_xlabel('Wavelength [nm]', fontsize=16)
        if i in [0,2]:
            ax.set_ylabel('DM piston [nm]', fontsize=16)
        ax.tick_params(labelsize=14)
    fig.subplots_adjust(right=0.88)
    cbar_ax = fig.add_axes([0.91, 0.1, 0.02, 0.8])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.ax.tick_params(labelsize=14)

    plt.figure(figsize=(6, 6))
    t = f'Kernel'#\n'+suptitle
    plt.title(t, fontsize=20)
    k1 = hyperdata0[tuple(idx) + (1, slice(None))]
    k2 = hyperdata0[tuple(idx) + (2, slice(None))]
    k1 = k1 - k1.mean(0, keepdims=True)
    k2 = k2 - k2.mean(0, keepdims=True)
    kernel =  k1 - k2
    plt.imshow(kernel,
                aspect='auto',
                extent=[spectral_axs[i][0] - spectral_step[i]*0.5,
                        spectral_axs[i][-1] + spectral_step[i]*0.5,
                        piston_range[-1]-opd_step[0]*0.5, 
                        piston_range[0]+opd_step[0]*0.5],
                # vmin=-0.15,
                # vmax=0.3,
                )
    plt.xlabel('Wavelength [nm]', fontsize=16)
    plt.ylabel('DM piston [nm]', fontsize=16)
    plt.tick_params(labelsize=14)
    cbar = plt.colorbar()
    cbar.ax.tick_params(labelsize=14)
    plt.tight_layout()
    plt.savefig(path + f'kernel_p{fixed[0]+1}_p{fixed[1]+1}_fixed.png', dpi=300)

    plt.figure(figsize=(6, 6))
    t = f'{output_labels[1]} - {output_labels[2]} output\n'+suptitle
    plt.title(t, fontsize=20)
    plt.plot(spectral_axs[0], kernel.T)
    plt.grid()
    plt.xlabel('Wavelength [nm]', fontsize=16)
    plt.ylabel('Kernel [a.u.]', fontsize=16)
    plt.tick_params(labelsize=14)

plt.close('all')

plt.figure()
plt.semilogy(spectral_axs[0], hyperdata00[argmax[0], argmax[1], argmax[2], :, :].T)
plt.gca().set_prop_cycle(None)
plt.semilogy(spectral_axs[0], hyperdata00[argmax[0]-1, argmax[1], argmax[2], :, :].T, '--')
plt.grid()
plt.xlabel('Wavelength [nm]')
plt.ylabel('Intensity [a.u.]')
plt.ylim(2, 200)

from itertools import product
triplets = list(product([1, 0, -1], repeat=3))
triplets = np.array(triplets)
k1 = hyperdata00[argmax[0], argmax[1], argmax[2], 1, :]
k2 = hyperdata00[argmax[0], argmax[1], argmax[2], 2, :]
kernel = k2 - k1

kn = lambda t: hyperdata00[argmax[0] + t[0], argmax[1] + t[1], argmax[2] + t[2], 2, :] - \
                hyperdata00[argmax[0] + t[0], argmax[1] + t[1], argmax[2] + t[2], 1, :]

n_triplets = len(triplets)
n_cols = int(np.ceil(np.sqrt(n_triplets)))
n_rows = int(np.ceil(n_triplets / n_cols))
fig, axes = plt.subplots(n_rows, n_cols,
                         figsize=(3.2 * n_cols, 2.8 * n_rows),
                         sharex=True, sharey=True)
axes = np.atleast_1d(axes).ravel()
shape_xyz = hyperdata00.shape[:3]
gaps = []
gap_triplets = []
gap_kernels = []
for i, t in enumerate(triplets):
    i0 = argmax[0] + t[0]
    i1 = argmax[1] + t[1]
    i2 = argmax[2] + t[2]

    ax = axes[i]
    if not (0 <= i0 < shape_xyz[0] and 0 <= i1 < shape_xyz[1] and 0 <= i2 < shape_xyz[2]):
        ax.set_title(f"Triplet {t}\nout of range")
        ax.grid(True)
        continue

    k1bis = hyperdata00[i0, i1, i2, 1, :]
    k2bis = hyperdata00[i0, i1, i2, 2, :]
    kernelbis = k2bis - k1bis
    gap = np.mean(np.abs(kernel - kernelbis))
    gaps.append(gap)
    gap_triplets.append(t)
    gap_kernels.append(kernelbis)

    ax.set_title(f"Triplet {t}, gap={gap:.3f}")
    ax.plot(spectral_axs[0], kernel, label="kernel ref")
    ax.plot(spectral_axs[0], kernelbis, "--", label="kernel shifted")
    ax.grid(True)
    ax.set_ylim(-10, 10)

for ax in axes[n_triplets:]:
    ax.set_visible(False)

# Common labels for the full figure
fig.supxlabel("Wavelength [nm]")
fig.supylabel("Intensity [a.u.]")
fig.suptitle(f"Kernel comparison for all {n_triplets} triplets")

# Single legend for the full figure
handles, labels = axes[0].get_legend_handles_labels()
if handles:
    fig.legend(handles, labels, loc="upper center", ncol=2)

plt.tight_layout(rect=[0, 0, 1, 0.97])

gaps = np.array(gaps)
gaps_sort = np.argsort(gaps)
print(np.argsort(gaps))

n_valid = len(gaps)
if n_valid > 0:
    n_cols_sorted = int(np.ceil(np.sqrt(n_valid)))
    n_rows_sorted = int(np.ceil(n_valid / n_cols_sorted))
    fig_sorted, axes_sorted = plt.subplots(n_rows_sorted, n_cols_sorted,
                                           figsize=(3.2 * n_cols_sorted, 2.8 * n_rows_sorted),
                                           sharex=True, sharey=True)
    axes_sorted = np.atleast_1d(axes_sorted).ravel()

    for rank, idx in enumerate(gaps_sort):
        ax = axes_sorted[rank]
        t = gap_triplets[idx]
        gap = gaps[idx]
        kernelbis = gap_kernels[idx]

        ax.set_title(f"Triplet {t}, gap={gap:.3f}")
        ax.plot(spectral_axs[0], kernel, label="kernel ref")
        ax.plot(spectral_axs[0], kernelbis, "--", label="kernel shifted")
        ax.grid(True)
        ax.set_ylim(-10, 10)

    for ax in axes_sorted[n_valid:]:
        ax.set_visible(False)

    fig_sorted.supxlabel("Wavelength [nm]")
    fig_sorted.supylabel("Intensity [a.u.]")
    fig_sorted.suptitle("Kernel comparison ordered by increasing gap")

    handles_sorted, labels_sorted = axes_sorted[0].get_legend_handles_labels()
    if handles_sorted:
        fig_sorted.legend(handles_sorted, labels_sorted, loc="upper center", ncol=2)

    plt.tight_layout(rect=[0, 0, 1, 0.97])


plt.figure()
plt.plot(spectral_axs[0], kernel, c='k', label="Kernel at null point")
plt.plot(spectral_axs[0], kn(triplets[gaps_sort[1]]), label=f"Kernel around null point", alpha=0.5)
plt.plot(spectral_axs[0], kn(triplets[gaps_sort[2]]), label=f"Kernel around null point", alpha=0.5)
plt.grid()
plt.xlabel('Wavelength [nm]')
plt.ylabel('Kernel [a.u.]')
plt.legend()

# Fenetre de lissage (en nombre de points spectraux) : change cette valeur
window_pts = 21  # ex: 5, 11, 21...

def moving_average(y, w):
    w = max(1, int(w))
    if w % 2 == 0:
        w += 1  # force une fenetre impaire (plus pratique pour centrer)
    kernel_ma = np.ones(w) / w
    pad = w // 2
    y_pad = np.pad(y, pad_width=pad, mode='edge')
    return np.convolve(y_pad, kernel_ma, mode='valid')

k_ref = kernel
k_1 = kn(triplets[gaps_sort[1]])
k_2 = kn(triplets[gaps_sort[2]])
dopd1 = np.array(triplets[gaps_sort[1]]) * opd_step[0]
dopd2 = np.array(triplets[gaps_sort[2]]) * opd_step[0]
dopd1 = dopd1.astype(int)
dopd2 = dopd2.astype(int)

plt.figure(figsize=(10,10))
# Courbes brutes (legeres)
plt.plot(spectral_axs[0], k_ref, c='k', alpha=0.25, label='Kernel at null')
plt.plot(spectral_axs[0], k_1, alpha=0.20, label=f'Kernel at {dopd1} nm away')
plt.plot(spectral_axs[0], k_2, alpha=0.20, label=f'Kernel at {dopd2} nm away')
plt.gca().set_prop_cycle(None)  # Reset color cycle for the smoothed curves
# Courbes lissees
plt.plot(spectral_axs[0], moving_average(k_ref, window_pts), c='k', lw=3.0,
         label=f'Kernel at null MA({window_pts})')
plt.plot(spectral_axs[0], moving_average(k_1, window_pts), lw=3.0,
         label=f'Kernel at {dopd1} nm away MA({window_pts})')
plt.plot(spectral_axs[0], moving_average(k_2, window_pts), lw=3.0,
         label=f'Kernel at {dopd2} nm away MA({window_pts})')

plt.grid()
plt.title('Kernels', fontsize=26)
plt.xlabel('Wavelength [nm]', fontsize=22)
plt.ylabel('Kernel [a.u.]', fontsize=22)
plt.xticks(fontsize=20)
plt.yticks(fontsize=20)
plt.legend(ncol=1, fontsize=16)
plt.tight_layout()
plt.savefig(path + f'kernel_comparison.png', dpi=300)

np.savez(path + f'kernel_comparison_data.npz', spectral_axs=spectral_axs, k_ref=k_ref, k_1=k_1, k_2=k_2, dopd1=dopd1, dopd2=dopd2)
ppp

def calculate_kernth(wl, ref_cart, p1, p2, p3, neff):
    return 0.25 * (np.cos(2 * np.pi / wl[None,:] * (p2[:,None] - ref_cart) * neff) + \
                   np.cos(2 * np.pi / wl[None,:] * (p1[:,None] - p3[:,None]) * neff))

# plt.close('all')
combiner = 0.25 * np.array([
                            [1, -1, 1, -1],
                            [1, -1j, -1, 1j],
                            [1, 1j, -1, -1j],
                            [1, 1, 1, 1],])

# lam = 1550.
# offset = -np.array([1, 1, 1.])*-100
# opd_range = (piston_range - ref_cart) * 2

# hypersim = []
# for p1 in opd_range:
#     temp1 = []
#     for p2 in opd_range:
#         temp2 = []
#         for p3 in opd_range:
#             e_in = np.array([np.exp(1j * 2 * np.pi / spectral_axs[0] * (ref_cart)),
#                              np.exp(1j * 2 * np.pi / spectral_axs[0] * (p1 + offset[0])),
#                              np.exp(1j * 2 * np.pi / spectral_axs[0] * (p2 + offset[1])),
#                              np.exp(1j * 2 * np.pi / spectral_axs[0] * (p3 + offset[2]))
#                              ])
#             e_out = np.einsum('ij,j...->i...', combiner, e_in)
#             i_out = np.abs(e_out)**2
#             temp2.append(i_out)
#         temp1.append(temp2)
#     hypersim.append(temp1)

# hypersim = np.array(hypersim)

# argminsim = np.unravel_index(np.argmin(hypersim.mean(-1)[:,:,:,o]), hypersim.mean(-1)[:,:,:,o].shape)
# argminsim = np.array(argminsim)

# for k in range(1):
#     fixed = [j for j in range(3) if j != k]
#     suptitle = 'Sim\n' + ', \n '.join(f'p{j+1} = {opd_range[selector[j]]:.2f} nm' for j in fixed)
#     idx = list(selector)
#     idx[k] = slice(None)

#     plt.figure(figsize=(12, 12))
#     plt.suptitle(suptitle)
#     for i in range(4):
#         plt.subplot(2, 3, i+1)
#         plt.title(f'{output_labels[i]} output')
#         plt.imshow(np.log10(hypersim[tuple(idx) + (i, slice(None))]),
#                    aspect='auto',
#                    extent=[spectral_axs[i][0] - spectral_step[i]*0.5,
#                            spectral_axs[i][-1] + spectral_step[i]*0.5,
#                            piston_range[-1]-opd_step[0]*0.5, 
#                            piston_range[0]+opd_step[0]*0.5],
#                    vmin=-1.7,
#                    vmax=0,
#                    )
#         plt.xlabel('Wavelength [nm]')
#         plt.ylabel('DM piston [nm]')
#     plt.subplot(3, 2, 5)
#     plt.title(f'{output_labels[1]} - {output_labels[2]} output')
#     plt.imshow(np.log10(hypersim[tuple(idx) + (1, slice(None))] - hypersim[tuple(idx) + (2, slice(None))]),
#                aspect='auto',
#                extent=[spectral_axs[0][0] - spectral_step[0]*0.5,
#                        spectral_axs[0][-1] + spectral_step[0]*0.5,
#                        piston_range[-1]-opd_step[0]*0.5, 
#                        piston_range[0]+opd_step[0]*0.5],
#                vmin=-1.7,
#                vmax=0,
#                )
#     plt.xlabel('Wavelength [nm]')
#     plt.ylabel('DM piston [nm]')        
#     plt.tight_layout()

plt.close('all')
combiner = 0.25 * np.array([
                            [1, -1, 1, -1],
                            [1, -1j, -1, 1j],
                            [1, 1j, -1, -1j],
                            [1, 1, 1, 1],])

lam = 1550
pistons, step = np.linspace(-lam/4, lam/4, 31, retstep=True)
pistons *= 2.
step *= 2.
center = np.where(pistons == 0)[0][0]

hypersim = []
for p1 in pistons:
    temp1 = []
    for p2 in pistons:
        temp2 = []
        for p3 in pistons:
            e_in = np.array([np.exp(1j * 2 * np.pi / spectral_axs[0] * (0)),
                             np.exp(1j * 2 * np.pi / spectral_axs[0] * (p1)),
                             np.exp(1j * 2 * np.pi / spectral_axs[0] * (p2)),
                             np.exp(1j * 2 * np.pi / spectral_axs[0] * (p3))
                             ])
            e_out = np.einsum('ij,j...->i...', combiner, e_in)
            i_out = np.abs(e_out)**2
            temp2.append(i_out)
        temp1.append(temp2)
    hypersim.append(temp1)

hypersim = np.array(hypersim)
argmax = np.unravel_index(np.argmax(hypersim.mean(-1)[:,:,:,3]), hypersim.mean(-1)[:,:,:,3].shape)
argmax = np.array(argmax)

plt.figure()
for i in range(4):
    plt.subplot(2,2,i+1)
    plt.imshow(hypersim[:,center+3,center,i,:], aspect='auto', extent=[spectral_axs[0][0] - spectral_step[0]*0.5,
                                                            spectral_axs[0][-1] + spectral_step[0]*0.5,
                                                            pistons[-1]-step*0.5,
                                                            pistons[0]+step*0.5])
    plt.colorbar()

kernel_sim = hypersim[:,:,:,2,:] - hypersim[:,:,:,1,:]

plt.figure()
plt.plot(spectral_axs[0], kernel_sim[center+1, center+1, center+1, :], c='k', label="Kernel at null")
plt.grid()

n_triplets = len(triplets)
n_cols = int(np.ceil(np.sqrt(n_triplets)))
n_rows = int(np.ceil(n_triplets / n_cols))
fig, axes = plt.subplots(n_rows, n_cols,
                         figsize=(3.2 * n_cols, 2.8 * n_rows),
                         sharex=True, sharey=True)
axes = np.atleast_1d(axes).ravel()
shape_xyz = hypersim.shape[:3]
gaps = []
gap_triplets = []
gap_kernels = []
for i, t in enumerate(triplets):
    i0 = center + t[0]
    i1 = center + t[1]
    i2 = center + t[2]

    ax = axes[i]
    if not (0 <= i0 < shape_xyz[0] and 0 <= i1 < shape_xyz[1] and 0 <= i2 < shape_xyz[2]):
        ax.set_title(f"Triplet {t}\nout of range")
        ax.grid(True)
        continue

    k1bis = hypersim[i0, i1, i2, 1, :]
    k2bis = hypersim[i0, i1, i2, 2, :]
    kernelbis = k2bis - k1bis

    ax.set_title(f"Triplet {t}, gap={gap:.3f}")
    ax.plot(spectral_axs[0], kernel_sim[center, center, center, :], label="kernel ref")
    ax.plot(spectral_axs[0], kernelbis, "--", label="kernel shifted")
    ax.grid(True)
    ax.set_ylim(-10, 10)

for ax in axes[n_triplets:]:
    ax.set_visible(False)

# Common labels for the full figure
fig.supxlabel("Wavelength [nm]")
fig.supylabel("Intensity [a.u.]")
fig.suptitle(f"Simu Kernel comparison for all {n_triplets} triplets")

# Single legend for the full figure
handles, labels = axes[0].get_legend_handles_labels()
if handles:
    fig.legend(handles, labels, loc="upper center", ncol=2)

plt.tight_layout(rect=[0, 0, 1, 0.97])