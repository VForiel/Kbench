import numpy as np
from xaosim.shmlib import shm
import matplotlib.pyplot as plt
from tqdm import tqdm
from time import sleep
import phobos
import json
from injection_opt import create_dir

def load_tt(json_path, key):
    with open(json_path) as f:
        content = json.load(f)
        f.close()
        
    return np.array(content[key])

save_path0 = '/media/photonics/SSD 128Go/data/2025-12-18/'
save_path = create_dir(save_path0)

dm = phobos.DM()
segpath = save_path0+'001/TT_config.json'
segOn = load_tt(segpath, 'segOn')
[dm.segments[int(segOn[i, 0])].set_ptt(segOn[i, 1], segOn[i, 2], segOn[i, 3]) for i in range(segOn[:, 0].size)]

dk = shm('/dev/shm/cred3_dark.im.shm')
dark = dk.get_latest_data()
cam = shm('/dev/shm/cred1.im.shm', nosem=False) # the source of data
semid = 0
cam.catch_up_with_sem(semid)    

exposure = 100 # in sec
fps = 500
nb_frames = int(exposure * fps)
datacube = np.zeros_like(cam.get_latest_data(semid))

for i in tqdm(range(nb_frames)):
    img = cam.get_latest_data(semid)
    img = img - dark
    datacube = datacube + img

# datacube = np.array(datacube)
# datacube = datacube.mean(0)
datacube = datacube / nb_frames

np.save(save_path+'datacube_inj', datacube)
np.save(save_path+'dark_inj', dark)

countdown = 40 + exposure # in sec
print('Take dark quick! (%s sec)'%(countdown))
for i in tqdm(range(int(countdown))):
    sleep(1)

segOff = load_tt(segpath, 'segOff')
[dm.segments[int(segOff[i, 0])].set_ptt(segOff[i, 1], segOff[i, 2], segOff[i, 3]) for i in range(segOff[:, 0].size)]
sleep(0.01)

datacube_no_inj = np.zeros_like(datacube)
dark2 = dk.get_latest_data()

for i in tqdm(range(nb_frames)):
    img = cam.get_latest_data(semid)
    img = img - dark2
    datacube_no_inj = datacube_no_inj + img

# datacube_no_inj = np.array(datacube_no_inj)
# datacube_no_inj = datacube_no_inj.mean(0)
datacube_no_inj = datacube_no_inj / nb_frames

np.save(save_path+'datacube_no_inj', datacube_no_inj)
np.save(save_path+'dark_no_inj', dark2)

with open(save_path+'log.txt', 'w') as f:
    [f.write('Seg off\t'+str(int(segOff[i, 0]))+'\t'+str(segOff[i, 1])+ '\t'+\
             str(segOff[i, 2])+'\t'+str(segOff[i, 3])+'\n') for i in range(4)]
    f.write('Exposure\t'+str(exposure)+'\n')
    f.write('fps\t'+str(fps)+'\n')
    
[dm.segments[int(segOff[i, 0])].set_ptt(0,0,0) for i in range(segOff[:, 0].size)]

plt.figure()
plt.imshow(datacube, vmin=-10, vmax=10)

plt.figure()
plt.imshow(datacube_no_inj, vmin=-10, vmax=10)
