#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script performs tip-tilt scans on the photonic chip 
to find the flat position, best injection and off injection.
"""

import phobos
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from tqdm import tqdm
from time import time, sleep
import os
import json
from datetime import datetime

def get_frame(cam, semid):
    """
    Grab frame from the shared memory and correct for the dark.
    It uses the semaphores to take the frame right after a tip-tilt
    position is send to the DM.

    Parameters
    ----------
    cam : obj
        Shared memory instance of the camera.
    semid : int
        Semaphore value.

    Returns
    -------
    img : 2d-array
        Frame corrected from dark.

    """
    img = cam.get_latest_data()
    
    return img

def crop_frames(datacube, crop_coords):
    """
    Crop frames in a datacube.
    The datacube must be of at least 3 dimensions.

    Parameters
    ----------
    datacube : nd-array
        Datacube to crop.
    crop_coords : list-like
        Coordinates to crop.

    Returns
    -------
    cropped_cube : nd-array
        Cropped datacube of shape(..., nb of regions, y-size of subframes, x-size of subframes).

    """
    crop_coords = np.array(crop_coords)
    datacube_t = np.transpose(datacube) # Put frames on the first 2 axes
    
    cropped_cube = []
    for i in range(crop_coords.shape[0]):
        cropx, cropy = crop_coords[i]
        out = datacube_t[cropx[0]:cropx[1],cropy[0]:cropy[1]]
        cropped_cube.append(out)
        
    cropped_cube = np.array(cropped_cube)
    cropped_cube = np.transpose(cropped_cube) # Revert to original axes order
    cropped_cube = np.moveaxis(cropped_cube, [-3, -2, -1], [-2, -1, -3]) # Put frames on the last 2 axes
    
    return cropped_cube

def twoD_Gaussian(xy, amplitude, yo, xo, sigma_y, sigma_x, theta, offset):
    x, y = xy
    xo = float(xo)
    yo = float(yo)    
    a = (np.cos(theta)**2)/(2*sigma_x**2) + (np.sin(theta)**2)/(2*sigma_y**2)
    b = -(np.sin(2*theta))/(4*sigma_x**2) + (np.sin(2*theta))/(4*sigma_y**2)
    c = (np.sin(theta)**2)/(2*sigma_x**2) + (np.cos(theta)**2)/(2*sigma_y**2)
    g = offset + amplitude*np.exp( - (a*((x-xo)**2) + 2*b*(x-xo)*(y-yo) 
                            + c*((y-yo)**2)))
    return g.ravel()

def create_dir(save_path):
    """
    Create a directory. The format is like 001, 
    then 002 if a directory already exists in 'save_path', 
    003 if 2 directories already exist...

    Parameters
    ----------
    save_path : str
        Path where to create the subdirectory.

    Returns
    -------
    new_dir : string
        Name of the subdirectory.

    """
    dirlist = [filename for filename in os.listdir(save_path) if os.path.isdir(os.path.join(save_path,filename))]
    numbered_dir = []
    for elt in dirlist:
        try:
            numbered_dir.append(int(elt))
        except ValueError:
            pass
    try:
        new_dir = '%03d'%(max(numbered_dir) + 1)
    except ValueError:
        new_dir = '%03d'%(1)
    new_dir = os.path.join(save_path, new_dir) + '/'
    os.mkdir(new_dir)
    return new_dir


def save_config(save_path, pistons, seg_on, seg_off, active_seg):
    """
    Save the optimial injection profiles.

    Parameters
    ----------
    save_path : string
        path to save the file.
    pistons : array-like
        Piston position of the segments.
    seg_on : array
        optimal tip and tilt positions of the segments.
    seg_off : array
        tip and tilt to reduce injection.
    active_seg : list
        List of the segments of interest.

    Returns
    -------
    None.

    """
    config_file = save_path + 'TT_config.json'
    
    config = {'segOn':[[active_seg[i]]+[pistons[i]]+list(seg_on[i]) for i in range(len(active_seg))],
              'segOff':[[active_seg[i]]+[pistons[i]]+list(seg_off[i]) for i in range(len(active_seg))]}
    
    for i in range(len(active_seg)):
        config['seg'+str(i+1)] = [[active_seg[j]]+[pistons[i]]+list(seg_on[j]) if j == i else \
                                  [active_seg[j]]+[pistons[i]]+list(seg_off[j]) for j in range(len(active_seg))]
    
    with open(config_file, 'w') as f:
        json.dump(config, f)
    
def check_cropping(crop_centers, crop_size):
    """
    Check the cropping of the frame circle the signal and not noise.

    Parameters
    ----------
    crop_coords : array
        Array of coordinates in x, y.

    Returns
    -------
    None.

    """
    camera = phobos.Cred3()
    img = camera.get_image(subtract_dark=True)
    tt_cropped = camera.crop_outputs_from_image(img)#, crop_centers, crop_size)
    
    plt.figure(figsize=(10, 10))
    for i in range(len(tt_cropped)):
        if len(tt_cropped) == 1:
            plt.subplot(1, 1, i+1)
        else:
            plt.subplot(2, 2, i+1)
        plt.title('Beam '+str(i+1))
        plt.imshow(tt_cropped[i], origin='lower', cmap='jet',
                   vmin=0,
                   vmax=max([elt.max() for elt in tt_cropped]))
        plt.colorbar()
    plt.tight_layout()
   
if __name__ == '__main__':
    date_now = datetime.now()
    npts = 31
    off_tip = 0
    off_tilt = -5.47 
    
    ttamp = 3.
    wait_seg = 0.005
    mid_piston = [-1150]*4
    active_segs0 = [111, 112, 113, 114]
    active_segs0 = [135, 136, 137, 138][::-1]
    save_path0 = '/media/photonics/SSD 128Go/data/'+'%04d'%(date_now.year)+'-'+'%02d'%(date_now.month)+'-'+'%02d'%(date_now.day)+'/'
    

    dm = phobos.DM()
    [dm.segments[seg].set_ptt(0, 0., 0.) for seg in active_segs0]
    print('All seg flat')
    
    crop_size = 13 # px window around the output
    crop_centers = np.array([(315, 323),
                        (346, 323),
                        (378, 323),
                        (409, 323)])
    
    # check_cropping(crop_centers, crop_size)
    # ppp

    if not os.path.exists(save_path0):
        os.mkdir(save_path0)
        
    # [dm.segments[seg].set_ptt(mid_piston[0], off_tt, off_tt) for seg in active_segs0]
    # [dm.segments[seg].set_ptt(mid_piston[0], off_tt, 0) for seg in range(106)]
    # [dm.segments[seg].set_ptt(mid_piston[0], -off_tt, 0) for seg in range(119, 169)]
    # [dm.segments[seg].set_ptt(mid_piston[0], 0, -off_tt) for seg in range(115, 119)]
    # [dm.segments[seg].set_ptt(mid_piston[0], 0, off_tt) for seg in range(106, 111)]    
    # print('All Seg Off+piston')
    # sleep(0.01)
    
    for it in range(1):
        plt.close('all')
        save_path = create_dir(save_path0)
        
        active_segs = active_segs0[:]
        nbeams = len(active_segs)
        
        tip_range, tip_step = np.linspace(-ttamp, ttamp, npts, retstep=True)
        tilt_range, tilt_step = np.linspace(-ttamp, ttamp, npts, retstep=True)
    
        camera = phobos.Cred3()
        
        # =============================================================================
        # Acquiring data
        # =============================================================================
        start_acq = time()
        
        # Flat
        [dm.segments[seg].set_ptt(mid_piston[0], 0., 0.) for seg in active_segs]
        print('Some Seg flat+piston')
        sleep(wait_seg)
        
        # Off on 4 apertures
        [dm.segments[seg].set_ptt(mid_piston[0], off_tip, off_tilt) for seg in active_segs]
        print('Some Seg Off+piston')
        sleep(0.01)
        
        avg = 1
        
        log_semval = []
        tt_flux = []
        for i in tqdm(range(nbeams)):
            temp1 = []
            for tip in tip_range:
                temp2 = []
                for tilt in tilt_range:
                    dm.segments[active_segs[i]].set_ptt(mid_piston[i], tip, tilt)
                    sleep(wait_seg)
                    flx = np.zeros_like(camera.get_outputs(True, 'mean'))
                    for k in range(avg):
                        flx0 = camera.get_outputs(True, 'mean')
                        flx = flx + flx0
                    flx /= float(avg)
                    semval = camera.cam.sems[camera.semid].value
                    log_semval.append([i, tip, tilt, semval])
                    temp2.append(flx)
                temp1.append(temp2)
            tt_flux.append(temp1)
            dm.segments[active_segs[i]].set_ptt(mid_piston[i], off_tip, off_tilt)
            sleep(wait_seg)
            
        tt_flux = np.array(tt_flux) # Axes (Beams, tip, tilt, flux outputs)
        log_semval = np.array(log_semval)
        np.savetxt(save_path+'log_semval.txt', log_semval)
        [dm.segments[seg].set_ptt(mid_piston[i], 0., 0.) for seg in active_segs]
        print('Some Seg flat+piston')
        sleep(wait_seg)
        stop_acq = time()

        # =============================================================================
        # Process data
        # =============================================================================
        start_process = time()
        flux = np.sum(tt_flux, axis=-1)
        np.save(save_path+'flux', flux)
        stop_process = time()
        
        # =============================================================================
        # Analyse data
        # =============================================================================
        start_analysis = time()
        x, y = np.meshgrid(tilt_range, tip_range)
        params = []
        pcovs = []
        
        for i in range(flux.shape[0]):
            output = flux[i]
            initial_guess = [output.max(), 0., 0., 1., 1., 0., 0.]
            try:
                popt, pcov = curve_fit(twoD_Gaussian, (x, y), output.ravel(), p0=initial_guess)
            except RuntimeError as e:
                print(i, e)
                popt = np.zeros((len(initial_guess),))
                pcov = np.zeros((len(initial_guess), len(initial_guess)))
            params.append(popt)
            pcovs.append(pcov)
            
        params = np.array(params)
        pcovs = np.array(pcovs)
        seg_on = params[:,1:3]
        seg_flat = np.zeros((flux.shape[0], 2))
        seg_off = np.ones_like(seg_on)
        seg_off[:,0] = off_tip
        seg_off[:,1] = off_tilt
        
        stop_analysis = time()
        
        np.savetxt(save_path + 'fit_params.txt', params)
        np.save(save_path + 'fit_pcovs', pcovs)
        save_config(save_path, mid_piston, seg_on, seg_off, active_segs)
        np.save(save_path+'time_stamp', time())
        
        # Plot
        plt.figure(figsize=(10, 10))
        for i in range(len(active_segs)):
            plt.subplot(2, 2, i+1)
            plt.title('Seg '+str(active_segs0[i]))
            plt.imshow(flux[i], origin='lower', cmap='jet',
                       extent=[-ttamp-tilt_step/2, ttamp+tilt_step/2,
                               -ttamp-tip_step/2, ttamp+tip_step/2],
                       vmin=flux.min(),
                       vmax=flux.max())
            plt.colorbar()
            plt.scatter(seg_on[i,1], seg_on[i,0], c='w', marker='+', s=100)
            plt.xlabel('Tilt (mrad)')
            plt.ylabel('Tip (mrad)')
        plt.tight_layout()
        plt.savefig(save_path + 'TT_map.png', dpi=150, format='png')
        # plt.close('all')

        print('\n=== Time stats ===')
        print('Total', stop_analysis - start_acq)
        print('Acq', stop_acq - start_acq)
        print('Process', stop_process - start_process)
        print('Analysis', stop_analysis - start_analysis)
        
        with open(save_path+'log.txt', 'w') as f:
            f.write(date_now.isoformat()+'\n')
            f.write('Grid size\t'+str(npts)+'\n')
            f.write('Avg\t'+str(avg)+'\n')
            f.write('Wait seg\t'+str(wait_seg)+'\n')
            f.write('Total\t'+str(stop_analysis - start_acq)+'\n')
            f.write('Acq\t'+str(stop_acq - start_acq)+'\n')
            f.write('Process\t'+str(stop_process - start_process)+'\n')
            f.write('Analysis\t'+str(stop_analysis - start_analysis)+'\n')
        
        print('')
        print('Positions and widths')
        print(params[:,1:5]) # Pos and width of Gaussian
        print('')
        np.savetxt(save_path + 'pos_and_width.txt', params[:,1:5])
                   
    [dm.segments[seg].set_ptt(0, 0., 0.) for seg in active_segs0]
    print('All Seg flat')
    sleep(wait_seg)
    
    # a = dm.calibrate_injection2()
    # def check_max_bal(dictio):
    #     camera = phobos.Cred3()
    #     maxi = dictio['max']
    #     out_maxi = []
    #     for key, vals in maxi.items():
    #         [dm.segments[int(k)].set_ptt(-1158, 0., -5.47) for k in maxi.keys()]
    #         sleep(0.1)
    #         dm.segments[int(key)].set_ptt(*vals)
    #         sleep(0.1)
    #         img = camera.get_image(subtract_dark=True)
    #         sleep(0.1)
    #         tt_cropped = camera.crop_outputs_from_image(img)#, crop_centers, crop_size)
    #         tt_cropped = np.array(tt_cropped)
    #         out_maxi.append(tt_cropped.sum())
            
    #     bali = dictio['balanced']
    #     out_bali = []
    #     for key, vals in bali.items():
    #         [dm.segments[int(k)].set_ptt(-1158, 0., -5.47) for k in bali.keys()]
    #         sleep(0.1)
    #         dm.segments[int(key)].set_ptt(*vals)
    #         sleep(0.1)
    #         img = camera.get_image(subtract_dark=True)
    #         sleep(0.1)
    #         tt_cropped = camera.crop_outputs_from_image(img)#, crop_centers, crop_size)
    #         tt_cropped = np.array(tt_cropped)
    #         out_bali.append(tt_cropped.sum())