#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 13 15:39:06 2025

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

def load_tt(json_path, key):
    with open(json_path) as f:
        content = json.load(f)
        f.close()
        
    return np.array(content[key])

def model(x, V, alpha, beta, I0, phi0):
    wl = 1572.
    flx = (1 + alpha) * (I0 + beta * x) + 2 * alpha**0.5 * (I0 + beta * x) * V * np.cos(2*np.pi / wl * x + phi0)
    
    return flx

def load_flat(flatmap):
    cmd = np.loadtxt(flatmap)
    cmd = cmd[:507]
    
    return cmd
        
wait_seg = 0.005
mid_piston = [-1128]*4
mid_piston = [-1150]*4
piston_minmax = (-2520, 264)
piston_minmax = (-2530, 230)
active_seg = 0
off_tip = 3
off_tilt = 0

nloop = 1
cooldown = 15. # in min

active_segs = [111, 112, 113, 114]
active_segs = [135, 136, 137, 138]

inactive_idx = [i for i in range(4)]
inactive_idx.remove(active_seg)
neighbour_segs = []
# neighbour_segs = [114, 126, 125, 112, 99, 100] #1st ring of seg 113
# neighbour_segs = [114, 126, 125, 112, 99, 100, 111, 124, 123, 110, 97, 98, 99]
# neighbour_segs.remove(112)

# neighbour_segs = neighbour_segs + [84, 85, 86, 101, 115, 127, 138, 137, 136, 124, 111, 98]
# neighbour_segs = neighbour_segs + [69, 70, 71, 72, 87, 102, 116, 128, 139, 149, 148, 147, 146, 135, 123, 110, 97, 83]
# neighbour_segs = [i for i in range(169)]

scan_neighbours = False
date = '2025-12-18'
save_path0 = '/media/photonics/SSD 128Go/data/' + date + '/'

tt_file = '/media/photonics/SSD 128Go/data/' + date + '/005/TT_config.json'

crop_size = 7 # px window around the output
crop_size2 = 180
crop_centers = np.array([(285, 211),
                    (317, 211),
                    (350, 211),
                    (382, 211),
                        (197, 346)])

crop_coords = [((crop_centers[0,0]-crop_size//2, crop_centers[0,0]+crop_size//2+1), (crop_centers[0,1]-crop_size//2, crop_centers[0,1]+crop_size//2+1)), 
               ((crop_centers[1,0]-crop_size//2, crop_centers[1,0]+crop_size//2+1), (crop_centers[1,1]-crop_size//2, crop_centers[1,1]+crop_size//2+1)),
               ((crop_centers[2,0]-crop_size//2, crop_centers[2,0]+crop_size//2+1), (crop_centers[2,1]-crop_size//2, crop_centers[2,1]+crop_size//2+1)),
               ((crop_centers[3,0]-crop_size//2, crop_centers[3,0]+crop_size//2+1), (crop_centers[3,1]-crop_size//2, crop_centers[3,1]+crop_size//2+1))] # [((x1, x2), (y1, y2))]*4
# crop_coords2 = [((crop_centers[4,0]-crop_size2//2, crop_centers[4,0]+crop_size2//2+1), (crop_centers[4,1]-crop_size2//2, crop_centers[4,1]+crop_size2//2+1))] 
crop_coords2 = [((45,335), (210,475))] 

# crop_centers_noise = crop_centers.copy()
# crop_centers_noise[:,0] = crop_centers_noise[:,0] - (crop_size + 2)
# crop_coords_noise = [((crop_centers_noise[0,0]-crop_size//2, crop_centers_noise[0,0]+crop_size//2+1), (crop_centers_noise[0,1]-crop_size//2, crop_centers_noise[0,1]+crop_size//2+1)), 
#                ((crop_centers_noise[1,0]-crop_size//2, crop_centers_noise[1,0]+crop_size//2+1), (crop_centers_noise[1,1]-crop_size//2, crop_centers_noise[1,1]+crop_size//2+1)),
#                ((crop_centers_noise[2,0]-crop_size//2, crop_centers_noise[2,0]+crop_size//2+1), (crop_centers_noise[2,1]-crop_size//2, crop_centers_noise[2,1]+crop_size//2+1)),
#                ((crop_centers_noise[3,0]-crop_size//2, crop_centers_noise[3,0]+crop_size//2+1), (crop_centers_noise[3,1]-crop_size//2, crop_centers_noise[3,1]+crop_size//2+1))] # [((x1, x2), (y1, y2))]*4

# check_cropping(crop_centers[:-1], crop_size)
# check_cropping(crop_centers[-1:], crop_size2)
# ppp

piston_range, pstep = np.linspace(-2000, 100, 201, retstep=True)
seg = load_tt(tt_file, 'seg'+str(active_seg+1))
try:
    neighbour_segs.remove(int(seg[active_seg,0]))
except:
    pass

pup = phobos.PupilMask()
dm = phobos.DM()

visi_list = []
noise_list = []

cooldown *= 60. # in sec
cooldown -= 5. # 5 seconds for doing the scqn

start_chrono = time()
for it in range(nloop):
    plt.close('all')
    print(it+1, '/', nloop)
    
    [dm.segments[seg].set_ptt(0, 0., 0.) for seg in active_segs]
    [dm.segments[seg].set_ptt(0, 0., 0.) for seg in neighbour_segs]
    cmd = load_flat('/home/photonics/Progs/repos/HexDMserver/Closed_Loop_Flat_Maps/27W007#051_ClosedLoop1750nmOffset.txt')
    dm.bmcdm.send_data(cmd)
    print('All seg flat')
    sleep(wait_seg)
    
    # [dm.segments[seg].set_ptt(mid_piston[0], off_tip, 0) for seg in range(106)]
    # [dm.segments[seg].set_ptt(mid_piston[0], -off_tip, 0) for seg in range(119, 169)]
    # [dm.segments[seg].set_ptt(mid_piston[0], 0, -off_tilt) for seg in range(114, 119)]
    # [dm.segments[seg].set_ptt(mid_piston[0], 0, off_tilt) for seg in range(106, 113)] 
    # [dm.segments[seg].set_ptt(0, off_tip, off_tilt) for seg in active_segs]
    # dm.segments[114].set_ptt(mid_piston[0], off_tip, -off_tilt)
    # [dm.segments[seg].set_ptt(mid_piston[0], off_tip, off_tilt) for seg in [111, 112]]
    # print('All Seg Off+piston')
    # sleep(wait_seg)
    
    seg_on = load_tt(tt_file, 'segOn')
    seg_off = load_tt(tt_file, 'segOff')
    
    [dm.segments[int(seg_off[i,0])].set_ptt(mid_piston[i], seg_off[i,2], seg_off[i,3]) for i in range(4)]
    print('All seg piston+TT Off')
    sleep(wait_seg)
    
    dm.segments[int(seg[active_seg,0])].set_ptt(mid_piston[active_seg], seg[active_seg,2], seg[active_seg,3])
    print('One seg injected')
    sleep(wait_seg)
    
    save_path = create_dir(save_path0)
    
    # =============================================================================
    # Acquisition
    # =============================================================================
    cam = shm('/dev/shm/cred1.im.shm', nosem=False) # the source of data
    dk = shm('/dev/shm/cred3_dark.im.shm')
    semid = 0
    avg = 10
    
    datacube = []
    log_semval = []
    for p in tqdm(piston_range):
        cam.catch_up_with_sem(semid)    
        dark = dk.get_latest_data()

        dm.segments[int(seg[active_seg,0])].set_ptt(p, seg[active_seg,2], seg[active_seg,3])
        if scan_neighbours:
            [dm.segments[neighbour].set_ptt(p, 0, 0) for neighbour in neighbour_segs]
            [dm.segments[active_segs[i]].set_ptt(p, 3., seg_off[i,3]) for i in inactive_idx]
        sleep(wait_seg)    
        img = np.zeros_like(dark)
        for k in range(avg):
            img0 = get_frame(cam, semid)
            img0 = img0 - dark
            img = img + img0
        img /= float(avg)
        semval = cam.sems[semid].value
        log_semval.append([p, semval])    
        datacube.append(img)
        
    datacube = np.array(datacube)
    
    [dm.segments[seg].set_ptt(0, 0., 0.) for seg in range(169)]
    print('All seg flat')
    
    # =============================================================================
    # Process
    # =============================================================================
    data_cropped = crop_frames(datacube, crop_coords) # Axes (piston, outputs, framey, framex)
    data_cropped2 = crop_frames(datacube, crop_coords2) # Axes (piston, outputs, framey, framex)
    flux = np.mean(data_cropped, axis=(-1, -2))
    flux2 = np.mean(data_cropped2, axis=(-1, -2)) # Flux of the bulk output
    np.save(save_path+'flux', flux)
    np.save(save_path+'flux2', flux2)
    np.save(save_path + 'frame', datacube[0])
    
    if it == 0:
        np.save(save_path + 'dark', dark)
    
    noise_list.append([datacube[0,10:100,10:100].mean(), datacube[0,10:100,10:100].std()])
    
    # =============================================================================
    # Analysis
    # =============================================================================
    x = piston_range * 2
    
    plt.figure()
    plt.title(save_path[-4:-1])
    plt.plot(x, flux)
    plt.plot(x, flux2, '--')
    plt.grid()
    plt.xlabel('OPD (nm)')
    plt.ylabel('Flux (avg count)')
   
    try:
        initial_guess = [0.01, 1., 0.1, flux[:,0].mean(), 0]
        popt, pcov = curve_fit(model, x, flux[:,0], p0=initial_guess,
                               bounds=((0, 0, -np.inf, 0, -np.pi), (1, np.inf, np.inf, np.inf, np.pi)))

        print('Visibility =', popt[0], '+/-', np.diag(pcov)[0]**0.5)
        np.save(save_path + 'fit_popt', popt)
        np.save(save_path + 'fit_pcov', pcov)
        y = model(x, *popt)
        plt.plot(x, y)
        visi_list.append(popt[0])
    except:
        print('Fit failed')
        visi_list.append(-1.5)
        pass
    
    plt.tight_layout()
    plt.savefig(save_path+'incoherent_scan.png', dpi=150, format='png')

    plt.figure()
    plt.title(save_path[-4:-1])
    plt.plot(x, flux - flux.mean(0))
    plt.plot(x, flux2 - flux2.mean(), '--')
    plt.grid()
    plt.xlabel('OPD (nm)')
    plt.ylabel('Flux at mean 0 (avg count)')
    plt.savefig(save_path+'incoherent_scan_avg0.png', dpi=150, format='png')
    
    with open(save_path + 'log.log', 'w') as f:
        date_log = datetime.now()
        f.write(date_log.isoformat()+'\n')
        try:
            f.write('Visibility\t'+str(popt[0])+'\n')
        except:
            f.write('Fit failed\n')
        try:
            f.write('Visibility err\t'+str(np.diag(pcov)[0]**0.5)+'\n')
        except:
            f.write('Fit failed\n')
        f.write('Active segment\t'+str(int(seg[active_seg,0]))+'\n')
        f.write('neighbours_segments\t'+str(neighbour_segs)+'\n')
        f.write('Scan neighbours\t'+str(scan_neighbours)+'\n')
        f.write('Mask position\t'+str(pup.get_pos())+'\n')
        f.write('Off tip\t'+str(off_tip)+'\n')
        f.write('Off tilt\t'+str(off_tilt)+'\n')
    
    if nloop > 1:
        sleep(cooldown)
        
if nloop > 1:
    visi_list = np.array(visi_list)
    np.save(save_path0+'visibilities', visi_list)

    noise_list = np.array(noise_list)
    np.save(save_path0+'noise_stats', noise_list)

stop_chrono = time()
print('Total time (min)', (stop_chrono - start_chrono) / 60.)