import numpy as np
import matplotlib.pyplot as plt
import pickle

plt.ion()

def open_file(path, n_roi, xlabel):
    datacube0 = np.load(path)

    try:
        datacube = datacube0['data'][:,:,:,:n_roi,:]
        x_range = datacube0[xlabel]
    except IndexError as e:
        print(e)
        start = -2530.
        end = 230.
        x_range = np.linspace(start, end, datacube0.shape[0])
        datacube = datacube0[:,:,:,:n_roi,:]

    return datacube, x_range

def normalise_outputs(datacube):
    datacube_normed = datacube / np.sum(datacube, axis=3, keepdims=True)
    return datacube_normed

def find_white_light(datacube, output, mode):
    if mode == 'max':
        arg_extreme = np.unravel_index(np.argmax(datacube[:,:,:,output]), datacube[:,:,:,output].shape)
    else:
        arg_extreme = np.unravel_index(np.argmin(datacube[:,:,:,output]), datacube[:,:,:,output].shape)
    arg_extreme = np.array(arg_extreme)

    return arg_extreme

def plot_diagnostics(indx, indx_labels, hypercube_normed, spectral_axs,):
    labels = indx_labels
    outputs = [3, 0, 1, 2, 0]
    fig, axs = plt.subplots(3, 2, figsize=(14, 10))
    axs = axs.flatten()
    for i in range(len(axs)-1):
        axs[i].plot(spectral_axs[outputs[i]], hypercube_normed[indx[i][0], indx[i][1], indx[i][2], :, :].T,)
        axs[i].set_title(labels[i])
        axs[i].set_xlabel('Differential piston (nm)')
        axs[i].set_ylabel('Flux (normalized)')
        axs[i].grid(True)
    fig.tight_layout()

def locate_all_white_lights(non_spectral_cube):
    white_light_pos = find_white_light(non_spectral_cube, 3, 'max')
    dark_light_pos = find_white_light(non_spectral_cube, 0, 'min')
    dark_light_pos2 = find_white_light(non_spectral_cube, 1, 'min')
    dark_light_pos3 = find_white_light(non_spectral_cube, 2, 'min')

    return white_light_pos, dark_light_pos, dark_light_pos2, dark_light_pos3

def plot_null_depth(spectral_axs, null_depths, noise_level, outputs_labels, title):
    plt.figure()
    plt.semilogy(spectral_axs[0], null_depths[0], label=outputs_labels[0])
    plt.semilogy(spectral_axs[-1], noise_level, 'k--', label='Noise level')
    plt.xlabel('Wavelength (nm)')
    plt.ylabel('Null depth')
    plt.legend(loc='best')
    plt.grid(True)
    plt.title(title)
    plt.ylim(1e-4, 1.)

def main(path, filename, n_roi, xlabel, fig_titles):
    hypercube, x_range = open_file(path+filename, n_roi, xlabel)

    spectral_axs = np.arange(hypercube.shape[-1])
    spectral_axs = np.array([np.polyval(spec_law[0][i], spectral_axs) for i in range(n_roi)])
    spectral_steps = spectral_axs[:,1] - spectral_axs[:,0]

    hypercube_normed = hypercube.copy() #normalise_outputs(hypercube)
    non_spectral_cube = np.mean(hypercube_normed, axis=-1)


    white_light_pos, dark_light_pos, dark_light_pos2, dark_light_pos3 = locate_all_white_lights(non_spectral_cube)
    non_spectral_cube_normed = non_spectral_cube / np.sum(non_spectral_cube, axis=(0,1,2), keepdims=True)
    non_spectral_cube_sum = np.sum(non_spectral_cube_normed[:,:,:,:3], axis=-1, keepdims=True)
    dark_light_pos_sum = find_white_light(non_spectral_cube_sum, 0, 'min')

    indx = [white_light_pos, dark_light_pos, dark_light_pos2, dark_light_pos3, dark_light_pos_sum]
    indx_labels = ['White light', 'Dark light 1', 'Dark light 2', 'Dark light 3', 'Dark light sum']

    plot_diagnostics(indx, indx_labels, hypercube_normed, spectral_axs)


    outputs_labels = ['Double Null output', 'Kernel1 output', 'Kernel2 output', 'Bright output']
    null_depth_white_light = hypercube_normed[white_light_pos[0], white_light_pos[1], white_light_pos[2], :n_roi-1] / hypercube_normed[white_light_pos[0], white_light_pos[1], white_light_pos[2], 3]
    null_depth_dark_light = hypercube_normed[dark_light_pos_sum[0], dark_light_pos_sum[1], dark_light_pos_sum[2], :n_roi-1] / hypercube_normed[dark_light_pos_sum[0], dark_light_pos_sum[1], dark_light_pos_sum[2], 3]


    plot_null_depth(spectral_axs, null_depth_white_light, outputs_labels, fig_titles[0])
    plot_null_depth(spectral_axs, null_depth_dark_light, outputs_labels, fig_titles[1])

    return hypercube, x_range, spectral_axs, spectral_steps


path = '/home/mmartinod/projects/photonics/data/2026-06-30/6_4T2T_hypercube/'
filename = 'dm_scan_kernel_4x4_datacube_refcart_230_2T_pair_2-0.npz'
filename = 'dm_scan_kernel_4x4_datacube_refcart_230_4T.npz'

spec_law = np.load(path + 'spec_cal_coeffs_and_errors.npy')
ref_cart = 230.

n_roi = 4
xlabel = 'piston_range_p2'

# hypercube, x_range, spectral_axs, spectral_steps = main(path, filename, n_roi, xlabel, ['Null depth at white light position (DM)', 'Null depth at 3 dark outputs position (DM)'])

hypercube, x_range = open_file(path+filename, 5, xlabel)

spectral_axs = np.arange(hypercube.shape[-1])
spectral_axs = np.array([np.polyval(spec_law[0][i], spectral_axs) for i in range(n_roi)])
spectral_steps = spectral_axs[:,1] - spectral_axs[:,0]

res = []

boundaries = [[1500, 1550], [1525, 1575], [1575, 1625]]
for spectral_bounds in boundaries:
    spectral_mask = np.where((spectral_axs[0] >= spectral_bounds[0]) & (spectral_axs[0] <= spectral_bounds[1]))[0]

    hypercube_normed = hypercube.copy() #normalise_outputs(hypercube)
    non_spectral_cube = np.mean(hypercube_normed[:,:,:,:,spectral_mask], axis=-1)


    white_light_pos, dark_light_pos, dark_light_pos2, dark_light_pos3 = locate_all_white_lights(non_spectral_cube)
    non_spectral_cube_normed = non_spectral_cube / np.sum(non_spectral_cube, axis=(0,1,2), keepdims=True)
    non_spectral_cube_sum = np.sum(non_spectral_cube_normed[:,:,:,:3], axis=-1, keepdims=True)
    dark_light_pos_sum = find_white_light(non_spectral_cube_sum, 0, 'min')

    indx = [white_light_pos, dark_light_pos, dark_light_pos2, dark_light_pos3, dark_light_pos_sum]
    indx_labels = ['White light', 'Dark light 1', 'Dark light 2', 'Dark light 3', 'Dark light sum']

    plot_diagnostics(indx, indx_labels, hypercube_normed, spectral_axs)

    select = 4
    used_pos = indx[select]

    outputs_labels = ['Double Null output', 'Kernel1 output', 'Kernel2 output', 'Bright output']
    null_depth = hypercube_normed[used_pos[0], used_pos[1], used_pos[2], :n_roi-1] / hypercube_normed[used_pos[0], used_pos[1], used_pos[2], 3]
    null_depth_dark_light = hypercube_normed[dark_light_pos_sum[0], dark_light_pos_sum[1], dark_light_pos_sum[2], :n_roi-1] / hypercube_normed[dark_light_pos_sum[0], dark_light_pos_sum[1], dark_light_pos_sum[2], 3]
    null_noise = hypercube_normed[used_pos[0], used_pos[1], used_pos[2], 4] / hypercube_normed[used_pos[0], used_pos[1], used_pos[2], 3]
    null_noise_dark_light = hypercube_normed[dark_light_pos_sum[0], dark_light_pos_sum[1], dark_light_pos_sum[2], 4] / hypercube_normed[dark_light_pos_sum[0], dark_light_pos_sum[1], dark_light_pos_sum[2], 3]

    fig_titles = [f'Null depth at {indx_labels[select]} position', 'Null depth at 3 dark outputs position']
    plot_null_depth(spectral_axs, null_depth, null_noise, outputs_labels, fig_titles[0])
    # plot_null_depth(spectral_axs, null_depth_dark_light, null_noise_dark_light, outputs_labels, fig_titles[1])

    res.append([null_depth, null_noise])


ratio = 1.618
height = 6
plt.figure(figsize=(height*ratio, height))
plt.semilogy(spectral_axs[-1], res[0][1], 'k--', label='Noise depth')
for k in range(len(boundaries)):
    plt.semilogy(spectral_axs[0], res[k][0][0], label=f'Double null depth ({boundaries[k][0]}-{boundaries[k][1]} nm)', lw=3)
plt.grid()
plt.xlabel('Wavelength (nm)', fontsize=16)
plt.ylabel('Null depth', fontsize=16)
plt.tick_params(labelsize=14)
plt.legend(loc='best', fontsize=16)
plt.tight_layout()

pickle_output_path = path + f'null_depth_results_{indx_labels[select].replace(" ", "")}bis.pkl'
with open(pickle_output_path, 'wb') as f:
    pickle.dump({'res': res, 'spectral_axs': spectral_axs}, f)

print(f'Saved pickle file: {pickle_output_path}')


# plt.close('all')

def moving_average(y, w):
    w = max(1, int(w))
    if w % 2 == 0:
        w += 1  # force une fenetre impaire (plus pratique pour centrer)
    kernel_ma = np.ones(w) / w
    pad = w // 2
    y_pad = np.pad(y, pad_width=pad, mode='edge')
    return np.convolve(y_pad, kernel_ma, mode='valid')

window_size = 1
plt.figure(figsize=(height*ratio, height))
for k in range(len(boundaries)):
    plt.semilogy(spectral_axs[-1], moving_average(res[k][1], window_size), '--', label='Noise depth')
    plt.semilogy(spectral_axs[0], moving_average(res[k][0][0], window_size), label=f'Double null depth ({boundaries[k][0]}-{boundaries[k][1]} nm)', lw=3)
plt.grid()
plt.xlabel('Wavelength (nm)', fontsize=16)
plt.ylabel('Null depth', fontsize=16)
plt.tick_params(labelsize=14)
plt.legend(loc='best', fontsize=16)
plt.tight_layout()

path1 = '/home/mmartinod/projects/photonics/data/2026-06-30/6_4T2T_hypercube/'
path2 = '/home/mmartinod/projects/photonics/data/2026-06-30/6_4T2T_hypercube/'

pickle_output_path_1 = path1 + 'null_depth_results_Darklightsumbis.pkl'
pickle_output_path_2 = path2 + 'null_depth_pair_2-0_results_Darklight1.pkl'

with open(pickle_output_path_1, 'rb') as f:
    data_1 = pickle.load(f)

with open(pickle_output_path_2, 'rb') as f:
    data_2 = pickle.load(f)

res_1 = data_1['res']
spectral_axs_1 = data_1['spectral_axs']
res_2 = data_2['res']
spectral_axs_2 = data_2['spectral_axs']

mask_wl1 = (spectral_axs_1[0] > 1475) & (spectral_axs_1[0] < 1620)
mask_wl2 = (spectral_axs_2[0] > 1475) & (spectral_axs_2[0] < 1620)

window_size = 1
ratio = 1.618
height = 6
fig, axs = plt.subplots(2, 1, figsize=(height*ratio, height*1.35), sharex=True, sharey=True)
axs[0].semilogy(spectral_axs_1[-1][mask_wl1], moving_average(res_1[0][1][mask_wl1], window_size), 'k--', label='Detection limit', alpha=0.8)
for k in range(len(boundaries)):
    axs[0].semilogy(spectral_axs_1[0][mask_wl1], moving_average(res_1[k][0][0][mask_wl1], window_size), label=f'Double null depth ({boundaries[k][0]}-{boundaries[k][1]} nm)', lw=3)
axs[0].set_title('4T configuration', fontsize=16)
axs[0].set_ylabel('Null depth', fontsize=16)
axs[0].grid(True)
axs[0].legend(loc='best', fontsize=14)
axs[1].semilogy(spectral_axs_2[-1][mask_wl2], moving_average(res_2[0][1][mask_wl2], window_size), 'k--', label='Detection limit', alpha=0.8)
for k in range(len(boundaries)):
    axs[1].semilogy(spectral_axs_2[0][mask_wl2], moving_average(res_2[k][0][0][mask_wl2], window_size), label=f'Bracewell null depth ({boundaries[k][0]}-{boundaries[k][1]} nm)', lw=3)
axs[1].set_title('2T configuration', fontsize=16)
axs[1].set_xlabel('Wavelength (nm)', fontsize=16)
axs[1].set_ylabel('Null depth', fontsize=16)
axs[1].grid(True)
axs[1].legend(loc='best', fontsize=14)
for ax in axs:
    ax.tick_params(labelsize=14)
    ax.set_ylim(1e-4, 1.0)
fig.tight_layout()
# fig.savefig(path2 + 'null_depth_comparison_4T_2T_subfigs.png', dpi=300)

height = 8
fig, axs = plt.subplots(1, 1, figsize=(height*ratio, height))
for k in range(len(boundaries)):
    axs.semilogy(spectral_axs_1[0][mask_wl1], moving_average(res_1[k][0][0][mask_wl1], window_size), label=f'Double null depth ({boundaries[k][0]}-{boundaries[k][1]} nm)', lw=3)
# for k in range(len(boundaries)):
#     axs.semilogy(spectral_axs_2[0][mask_wl2], moving_average(res_2[k][0][0][mask_wl2], window_size), label=f'Bracewell null depth ({boundaries[k][0]}-{boundaries[k][1]} nm)', lw=3-1.5*k)
axs.set_ylabel('Null depth', fontsize=16)
axs.grid(True)
axs.legend(loc='best', fontsize=14)
axs.semilogy(spectral_axs_1[-1][mask_wl1], moving_average(res_1[0][1][mask_wl1], window_size), 'k--', label='Detection limit', alpha=0.8)
# axs.semilogy(spectral_axs_2[-1][mask_wl2], moving_average(res_2[0][1][mask_wl2], window_size), '-.', color='grey', label='Detection limit (Bracewell)', alpha=0.8)
axs.set_xlabel('Wavelength (nm)', fontsize=16)
axs.legend(loc='best', fontsize=14, ncol=2)
axs.tick_params(labelsize=14)
axs.set_ylim(5e-5, 1.0)

fig.tight_layout()
# fig.savefig(path2 + 'null_depth_comparison_4T.png', dpi=300)
