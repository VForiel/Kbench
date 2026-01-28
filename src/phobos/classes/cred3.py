import numpy as np
from .. import shm, SANDBOX_MODE


from ..utils import Singleton

class Cred3(metaclass=Singleton):
    """
    Singleton Class to interface with the Cred3 camera via shared memory.
    
    The camera writes frames to a shared memory location that can be read
    by this class. Optionally, dark frames can be subtracted.
    
    Configuration is loaded from `phobos.config`.
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Cred3, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        Initialize the Cred3 camera interface using global configuration.
        """
        if self._initialized:
            return
            
        self._initialized = True

        if SANDBOX_MODE:
            print("⛱️ [SANDBOX] Cred3 running in mock mode")
        
        # Load configuration
        import phobos
        
        self.img_shm_path = phobos.config.get('cred3.img_shm_path')
        self.dark_shm_path = phobos.config.get('cred3.dark_shm_path')
        self.semid = phobos.config.get('cred3.semid', 0)
        self.use_dark = phobos.config.get('cred3.use_dark', False)
        
        # Normalize output_centers
        output_centers = phobos.config.get('cred3.output_centers')
        self.output_centers = np.array(output_centers) if output_centers else None
            
        # Normalize output_sizes
        output_sizes = phobos.config.get('cred3.output_sizes')
        if self.output_centers is not None and isinstance(output_sizes, (int, float)):
             self.output_sizes = [output_sizes] * len(self.output_centers)
        else:
             self.output_sizes = output_sizes

        # Normalize bulk_center
        bulk_center = phobos.config.get('cred3.bulk_center')
        self.bulk_center = np.array(bulk_center) if bulk_center else None
            
        self.bulk_size = phobos.config.get('cred3.bulk_size')
        
        # Initialize shared memory for camera
        self.cam = shm(self.img_shm_path, nosem=False)
        self.cam.catch_up_with_sem(self.semid)
        
        # Initialize dark frame if needed
        self.dark_shm_obj = None
        if self.use_dark:
            try:
                self.dark_shm_obj = shm(self.dark_shm_path)
                self.dark = self.dark_shm_obj.get_latest_data()
                mode_prefix = "⛱️ [SANDBOX] " if SANDBOX_MODE else ""
                print(f"{mode_prefix}Cred3 camera initialized with dark subtraction")
            except Exception as e:
                print(f"⚠️ Could not load dark frame: {e}")
                self.dark = None
        else:
            self.dark = None
            mode_prefix = "⛱️ [SANDBOX] " if SANDBOX_MODE else ""
            print(f"{mode_prefix}Cred3 camera initialized without dark subtraction")

    
    def get_image(self, subtract_dark: bool = True) -> np.ndarray:
        """
        Get the latest image from the shared memory.
        
        Parameters
        ----------
        subtract_dark : bool, optional
            If True, subtract the dark frame. If None, uses the default
            set during initialization. Default is True.
        
        Returns
        -------
        img : ndarray
            Latest camera frame, optionally dark-subtracted.
        
        Examples
        --------
        >>> camera = Cred3()
        >>> img = camera.get_image()
        >>> img_no_dark = camera.get_image(subtract_dark=False)
        """
        img = self.cam.get_latest_data(self.semid)
        
        # Determine whether to subtract dark
        if subtract_dark is None:
            subtract_dark = self.use_dark
        
        if subtract_dark:
            # Update dark frame if possible
            if self.dark_shm_obj is not None:
                try:
                    self.dark = self.dark_shm_obj.get_latest_data()
                except Exception:
                    pass  # Keep using existing dark if update fails
            
            if self.dark is not None:
                img = img - self.dark
        
        return img
    
    def _crop_regions(self, 
                     img: np.ndarray, 
                     crop_centers: np.ndarray, 
                     crop_sizes) -> list[np.ndarray]:
        """
        Internal helper to crop regions from an image.
        
        Parameters
        ----------
        img : ndarray
            Input image to crop from.
        crop_centers : ndarray
            Array of (x, y) coordinates for crop centers, shape (N, 2).
        crop_sizes : int or array-like
            Size(s) of the crop windows.
            
        Returns
        -------
        crops : list of ndarray
            List of cropped sub-images.
        """
        img = np.transpose(img)  # Transpose to match (x, y) indexing
        
        # Handle crop_sizes - convert to array
        n_outputs = crop_centers.shape[0]
        if isinstance(crop_sizes, (int, float)):
            crop_sizes_array = np.full(n_outputs, int(crop_sizes))
        else:
            crop_sizes_array = np.array(crop_sizes)
            if len(crop_sizes_array) != n_outputs:
                raise ValueError(f"crop_sizes length ({len(crop_sizes_array)}) must match "
                               f"number of centers ({n_outputs})")
        
        # Compute crops for each output
        crops = []
        for i in range(n_outputs):
            x_center, y_center = crop_centers[i]
            crop_size = crop_sizes_array[i]
            half_size = crop_size // 2
            
            # Define crop boundaries
            x1 = int(x_center - half_size)
            x2 = int(x1 + crop_size)
            y1 = int(y_center - half_size)
            y2 = int(y1 + crop_size)
            
            # Extract crop
            try:
                crop = img[x1:x2, y1:y2]
                crops.append(crop.T)
            except IndexError:
                print(f"⚠️ Crop region {i} outside image boundaries")
                crops.append(np.zeros((crop_size, crop_size)))
        
        return [crop.copy() for crop in crops]
    
    def crop_outputs_from_image(self, img: np.ndarray) -> list[np.ndarray]:
        """
        Crop output regions from an image using configured centers and sizes.
        
        Parameters
        ----------
        img : ndarray
            Input image to crop from.
            
        Returns
        -------
        crops : list of ndarray
            List of cropped sub-images for each configured output.
        """
        if self.output_centers is None:
            raise ValueError("output_centers not configured in phobos.config")
        
        return self._crop_regions(img, self.output_centers, self.output_sizes)

    def get_outputs(self,
                   subtract_dark: bool = True,
                   flux_mode: str = 'mean') -> np.ndarray:
        """
        Get the flux around configured output centers.
        
        This method crops regions around the output centers defined in the configuration
        and returns the flux in each region. The flux can be the mean pixel value
        or the sum of pixel values.
        
        Parameters
        ----------
        subtract_dark : bool, optional
            Whether to subtract dark frame. Default is True.
        flux_mode : str, optional, 'mean' or 'sum'
            Method to compute the flux. 
            'mean': average of pixel values (default)
            'sum': sum of pixel values
        
        Returns
        -------
        flux : ndarray
            Flux in each cropped region, shape (N,).
        
        Examples
        --------
        >>> camera = Cred3()
        >>> # Get averaged outputs from configured centers
        >>> flux = camera.get_outputs()
        >>> 
        >>> # Get integrated flux (sum)
        >>> flux_sum = camera.get_outputs(flux_mode='sum')
        """
        # Use configured centers and sizes
        crop_centers = self.output_centers
        crop_sizes = self.output_sizes
        
        if crop_centers is None:
            raise ValueError("output_centers not configured. Please set them in phobos.config")
            
        # Get the latest image
        img = self.get_image(subtract_dark=subtract_dark)
        
        crops = self.crop_outputs_from_image(img)
        
        # Compute flux
        flux = np.zeros(len(crops))
        for i, crop in enumerate(crops):        
            if flux_mode == 'sum':
                flux[i] = np.sum(crop)
            elif flux_mode == 'mean':
                flux[i] = np.mean(crop)
            else:
                raise ValueError(f"Unknown flux_mode: {flux_mode}. Use 'mean' or 'sum'.")
                
        return flux

    def get_bulk(self,
                subtract_dark: bool = True,
                flux_mode: str = 'mean') -> float:
        """
        Get the flux of the bulk channel using configured center and size.
        
        Parameters
        ----------
        subtract_dark : bool, optional
            Whether to subtract dark frame. Default is True.
        flux_mode : str, optional
            'mean' or 'sum'. Default is 'mean'.
            
        Returns
        -------
        flux : float
            Flux in the bulk region.
        """
        # Use configured bulk values
        if self.bulk_center is None:
            raise ValueError("bulk_center not configured in phobos.config")
        
        crop_center = self.bulk_center
        crop_size = self.bulk_size

        # Get the latest image
        img = self.get_image(subtract_dark=subtract_dark)
        
        # Use internal helper for cropping
        centers = np.array([crop_center])
        crops = self._crop_regions(img, centers, crop_size)
        
        if not crops:
            return 0.0
            
        crop = crops[0]
        
        if flux_mode == 'sum':
            return float(np.sum(crop))
        elif flux_mode == 'mean':
            return float(np.mean(crop))
        else:
            raise ValueError(f"Unknown flux_mode: {flux_mode}")
    
    def update_dark(self, dark_shm_path: str = None):
        """
        Update the dark frame from shared memory.
        
        Parameters
        ----------
        dark_shm_path : str, optional
            Shared memory path for the new dark frame. If None, uses
            the default dark_shm_path. Default is None.
        
        Examples
        --------
        >>> camera = Cred3()
        >>> camera.update_dark()  # Reload dark from default location
        """
        if dark_shm_path is None:
            dark_shm_path = self.dark_shm_path
        
        try:
            dk = shm(dark_shm_path)
            self.dark = dk.get_latest_data()
            self.use_dark = True
            print(f"Dark frame updated from {dark_shm_path}")
        except Exception as e:
            print(f"⚠️ Could not update dark frame: {e}")
    
    def take_darks(self, nb_frames: int = 1000, save_to_shm: bool = True) -> np.ndarray:
        """
        Acquire dark frames and compute the average.
        
        This method acquires a specified number of frames, computes their average,
        and optionally saves the result to shared memory for use as a dark frame.
        
        Parameters
        ----------
        nb_frames : int, optional
            Number of frames to acquire and average. Default is 1000.
        save_to_shm : bool, optional
            If True, save the averaged dark frame to shared memory at
            self.dark_shm_path. Default is True.
        
        Returns
        -------
        dark_mean : ndarray
            The averaged dark frame.
        
        Notes
        -----
        - Ensure the camera source is turned OFF before acquiring darks
        - The method checks for late frames (when semaphore value > 0)
        - The dark frame is automatically loaded if save_to_shm is True
        
        Examples
        --------
        >>> camera = Cred3()
        >>> # Acquire 100 dark frames (default)
        >>> dark = camera.take_darks()
        >>> 
        >>> # Acquire 50 frames without saving to shared memory
        >>> dark = camera.take_darks(nb_frames=50, save_to_shm=False)
        """
        try:
            from tqdm import tqdm
            use_tqdm = True
        except ImportError:
            use_tqdm = False
            print("⚠️ tqdm not available, progress bar disabled")
        
        if SANDBOX_MODE:
            print(f"⛱️ [SANDBOX] Simulating acquisition of {nb_frames} dark frames")
            # In sandbox mode, generate random dark frames
            import time
            time.sleep(0.5)  # Simulate acquisition time
            dark_mean = np.random.randint(0, 100, size=(320, 256), dtype=np.uint16)
            print(f"⛱️ [SANDBOX] Dark acquisition complete")
            return dark_mean
        
        # images = []
        log_sem = []
        
        print(f"Taking {nb_frames} dark frames...")
        
        # Catch up with semaphore before starting
        self.cam.catch_up_with_sem(self.semid)
        
        # Acquire frames
        iterator = tqdm(range(nb_frames)) if use_tqdm else range(nb_frames)
        images = np.zeros_like(self.cam.get_latest_data(self.semid))
        for ii in iterator:
            img = self.cam.get_latest_data(self.semid)
            # images.append(img)
            images += img 
            semval = self.cam.sems[self.semid].value
            log_sem.append(semval)
        
        # images = np.array(images)
        print('Acquisition complete')
        
        # Check for late frames
        log_sem = np.array(log_sem)
        if np.any(log_sem > 0):
            mask = np.where(log_sem > 0)[0]
            print(f'⚠️ Total late frames: {len(mask)}')
        
        # Compute average dark
        # dark_mean = images.mean(axis=0)
        dark_mean = images / nb_frames
        
        # Save to shared memory if requested
        if save_to_shm:
            print(f'Saving dark frame to {self.dark_shm_path}...')
            try:
                dark_shm_obj = shm(self.dark_shm_path, data=dark_mean)
                print('✅ Dark frame saved to shared memory')
                
                # Update the internal dark frame
                self.dark = dark_mean
                self.dark_shm_obj = dark_shm_obj
                self.use_dark = True
            except Exception as e:
                print(f"⚠️ Could not save dark to shared memory: {e}")
        
        return dark_mean
    
    def close(self):
        """
        Close the shared memory connections.
        
        This method is provided for compatibility but shared memory
        objects are typically managed by the system.
        """
        # Shared memory objects don't need explicit closing in xaosim
        print("Cred3 camera interface closed")

    def reset(self):
        """
        Reset the camera settings (use_dark, outputs strategies) to the configuration.
        """
        # Reload configuration
        import phobos
        
        self.use_dark = phobos.config.get('cred3.use_dark', False)
        # Re-apply dark mechanism
        if self.use_dark:
             if self.dark_shm_obj is None:
                  try:
                      self.dark_shm_obj = shm(self.dark_shm_path)
                      self.dark = self.dark_shm_obj.get_latest_data()
                  except Exception:
                      pass
        else:
             self.dark = None
             
        # Restore crop settings
        output_centers = phobos.config.get('cred3.output_centers')
        self.output_centers = np.array(output_centers) if output_centers else None
        
        output_sizes = phobos.config.get('cred3.output_sizes')
        if self.output_centers is not None and isinstance(output_sizes, (int, float)):
             self.output_sizes = [output_sizes] * len(self.output_centers)
        else:
             self.output_sizes = output_sizes
             
        bulk_center = phobos.config.get('cred3.bulk_center')
        self.bulk_center = np.array(bulk_center) if bulk_center else None
        self.bulk_size = phobos.config.get('cred3.bulk_size')
        
        print("✅ Cred3 reset to configuration defaults.")