import os
import yaml
import shutil
import glob
import subprocess
import copy
from datetime import datetime
import shutil


class Config:
    """
    Singleton configuration class for PHOBos.
    Interfaces with the 'config/bench.yml' file.

    Parameters
    ----------
    path : str, optional
        Path to the configuration file. If not provided, defaults to
        './config/bench.yml'.

    Usage:
    >>> from phobos import config
    >>> print(config.get('cred3.semid'))
    >>> config.set('cred3.semid', 1)  # Saves to file immediately
    >>> config.save()   # Snapshot hardware state to config and save
    >>> config.apply()  # Apply config to hardware
    >>> config.reload() # Reload cache from file
    >>> config.import_config("history/backup.yml") # Restore backup
    """
    _instance = None
    _config_data = {}
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, path=None):
        if self._initialized:
            return
            
        self._initialized = True
        
        # Determine root directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        
        if path is None:
            self.path = os.path.join(self.root_dir, 'config', 'bench.yml')
            if not os.path.exists(self.path):
                # Copy from bench_template.yml
                shutil.copy(os.path.join(self.root_dir, 'config', 'bench_template.yml'), self.path)
        else:
            self.path = path

        self.reload()

    def reload(self):
        """Reload configuration from file into cache."""
        self._config_data = self._load_from_file()

    def get(self, key: str, default=None):
        """
        Get a config value by dot-notation key.
        
        Parameters
        ----------
        key : str
            Dot-notation key path (e.g., 'cred3.semid', 'filter_wheel.port')
        default : any, optional
            Value to return if key is not found. Default is None.
            
        Returns
        -------
        any
            The config value, or default if not found.
            
        Examples
        --------
        >>> config.get('cred3.semid')
        0
        >>> config.get('nonexistent.key', 'fallback')
        'fallback'
        """
        try:
            keys = key.split('.')
            val = self._config_data
            for k in keys:
                if isinstance(val, dict):
                    val = val[k]
                else:
                    return default
            return copy.deepcopy(val)
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value, autosave: bool = True) -> None:
        """
        Set a config value and save to file immediately.
        
        Parameters
        ----------
        key : str
            Dot-notation key path (e.g., 'cred3.semid')
        value : any
            Value to set (must be YAML-serializable)
        autosave : bool, optional
            If True, persist to file immediately (and therefore create a backup).
            If False, only update the in-memory cache; caller can later call
            :meth:`_save_to_file` (or any method that saves) once.
            Default is True.
            
        Examples
        --------
        >>> config.set('cred3.semid', 1)
        >>> config.set('filter_wheel.selected_filter', 3)
        """
        keys = key.split('.')
        data = self._config_data
        
        # Navigate to parent, creating dicts as needed
        for k in keys[:-1]:
            if k not in data or not isinstance(data[k], dict):
                data[k] = {}
            data = data[k]
        
        # Set the value
        data[keys[-1]] = value
        
        if autosave:
            # Persist to file
            self._save_to_file()

            # Reload cache for consistency
            self.reload()

    def save(self):
        """
        Snapshot the current state of hardware components and save as configuration.
        """
        import phobos
        print("💾 Snapshotting current hardware state...")
        
        # 1. PupilMask
        try:
            pm = phobos.PupilMask()
            wheel, zh, zv = pm.get_pos()
            
            self.set('pupil_mask.zaber_h_pos', zh)
            self.set('pupil_mask.zaber_v_pos', zv)
            
            # Calculate selected mask based on wheel angle
            newport_home = self.get('pupil_mask.newport_home')
            if newport_home is not None:
                delta = wheel - newport_home
                estimated_index = round(delta / 60.0)
                mask_id = estimated_index + 1
                self.set('pupil_mask.selected_mask', int(mask_id))

            print(f"   Shape: PupilMask -> Mask {self.get('pupil_mask.selected_mask')} (Angle {wheel:.2f}°), H:{zh}, V:{zv}")
        except Exception as e:
            print(f"   ⚠️ PupilMask update skipped: {e}")

        # 2. FilterWheel
        try:
            fw = phobos.FilterWheel()
            slot = fw.get_pos()
            self.set('filter_wheel.selected_filter', slot)
            print(f"   Shape: FilterWheel -> Slot {slot}")
        except Exception as e:
            print(f"   ⚠️ FilterWheel update skipped: {e}")

        # 3. Cred3
        try:
            cam = phobos.Cred3()
            self.set('cred3.use_dark', cam.use_dark)
            if cam.output_centers is not None:
                self.set('cred3.output_centers', cam.output_centers.tolist())
            if cam.bulk_center is not None:
                self.set('cred3.bulk_center', cam.bulk_center.tolist())
                 
            print(f"   Shape: Cred3 -> use_dark={cam.use_dark}")
        except Exception as e:
             print(f"   ⚠️ Cred3 update skipped: {e}")
            
        print("✅ Hardware state saved to configuration.")

    def save_to_file(self) -> None:
        """Persist current in-memory configuration to disk once.

        Notes
        -----
        This is useful when multiple keys have been updated with
        ``autosave=False`` in :meth:`set` and you want to create only one
        backup + write operation.
        """
        self._save_to_file()
        self.reload()
        
    def apply(self):
        """
        Apply configuration state to all hardware components.
        """
        import phobos
        print("🚀 Applying configuration state to hardware...")
        
        # 1. PupilMask
        try:
            phobos.PupilMask().reset()
        except Exception as e:
            print(f"   ⚠️ PupilMask reset failed: {e}")
            
        # 2. FilterWheel
        try:
            phobos.FilterWheel().reset()
        except Exception as e:
            print(f"   ⚠️ FilterWheel reset failed: {e}")
            
        # 3. Cred3
        try:
            phobos.Cred3().reset()
        except Exception as e:
            print(f"   ⚠️ Cred3 reset failed: {e}")
            
        print("✅ Hardware reset complete.")

    def import_config(self, path):
        """
        Load configuration from a specific file path.
        
        Parameters
        ----------
        path : str
            Path to the configuration file (.yml or .yaml).
        """
        if not os.path.exists(path):
            print(f"❌ Error: Config file not found at {path}")
            return

        try:
            with open(path, 'r') as f:
                new_data = yaml.safe_load(f) or {}
            
            # Update internal data
            self._config_data = new_data
            
            # Import copies the data into the MAIN config file
            self.path = os.path.join(self.root_dir, 'config', 'bench.yml')
            
            print(f"✅ Configuration data loaded from {path}")
            print(f"   Targeting main config file: {self.path}")
            
            # Persist the imported data to the main config file
            self.backup()
            self._save_to_file()
            
        except Exception as e:
            print(f"❌ Error importing config: {e}")

    def export_config(self, path):
        """
        Save current configuration to a specific file path.
        
        Parameters
        ----------
        path : str
            Destination path.
        """
        try:
            with open(path, 'w') as f:
                yaml.dump(self._config_data, f, default_flow_style=False)
            print(f"✅ Configuration exported to {path}")
        except Exception as e:
            print(f"❌ Error exporting config: {e}")

    def backup(self):
        """
        Create a backup of the current config file in config/history.
        Format: YYYY-MM-DD-hh-mm-<commit_id>_N.yml
        """
        if not os.path.exists(self.path):
            return

        history_dir = os.path.join(os.path.dirname(self.path), 'history')
        os.makedirs(history_dir, exist_ok=True)

        # Get Commit ID
        try:
            commit_id = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], 
                                              cwd=self.root_dir).decode('ascii').strip()
        except Exception:
            commit_id = "unknown"

        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        
        # Base pattern
        base_name = f"{timestamp}-{commit_id}"
        
        # Find next N
        existing_files = glob.glob(os.path.join(history_dir, f"{base_name}_*.yml"))
        
        n = 1
        if existing_files:
            ns = []
            for f in existing_files:
                try:
                    parts = os.path.basename(f).split('_')
                    num_part = parts[-1].split('.')[0]
                    ns.append(int(num_part))
                except (IndexError, ValueError):
                    pass
            if ns:
                n = max(ns) + 1
        
        backup_filename = f"{base_name}_{n}.yml"
        backup_path = os.path.join(history_dir, backup_filename)
        
        try:
            shutil.copy2(self.path, backup_path)
        except Exception as e:
            print(f"⚠️ Could not create config backup: {e}")

    def _load_from_file(self):
        """Load YAML file."""
        if not os.path.exists(self.path):
            return {}
            
        try:
            with open(self.path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"❌ Error loading config file: {e}")
            return {}

    def _save_to_file(self):
        """Save current config data to YAML file."""
        self.backup()
        try:
            with open(self.path, 'w') as f:
                yaml.dump(self._config_data, f, default_flow_style=False)
        except Exception as e:
            print(f"❌ Error saving config file: {e}")

    def to_dict(self):
        """Return raw dictionary."""
        return self._config_data.copy()

    def __repr__(self):
        return f"<Config path='{self.path}' keys={list(self._config_data.keys())}>"