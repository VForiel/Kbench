import os
import yaml
import shutil
import glob
import subprocess
import collections
from datetime import datetime
from types import SimpleNamespace

# Recursive dictionary update
def update_recursive(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = update_recursive(d.get(k, {}), v)
        else:
            d[k] = v
    return d

class Config:
    """
    Singleton configuration class for PHOBos.
    Interfaces with the 'config/bench.yml' file.
    
    Usage:
    >>> from phobos import config
    >>> print(config.hardware.camera.semid)
    >>> config.hardware.camera.semid = 1
    >>> config.save()
    >>> config.export_config("backup.yml")
    """
    _instance = None
    _config_data = {}
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path=None):
        if self._initialized:
            return
            
        self._initialized = True
        
        # Determine root directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        
        if config_path is None:
            self.config_path = os.path.join(self.root_dir, 'config', 'bench.yml')
        else:
            self.config_path = config_path

        self.reload()

    def reload(self):
        """Reload configuration from file."""
        self._config_data = self._load_from_file()
        # Create attributes for dot access
        self._create_attributes(self._config_data)

    def import_config(self, path):
        """
        Load configuration from a specific file path and update current settings.
        This effectively switches the active configuration to the content of 'path'.
        
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
            # Re-create attributes
            self._create_attributes(self._config_data)
            
            # Update config path to point to this new file?
            # The user user said "recover or force". 
            # If we just import data, we might want to stay on current config_path 
            # but with new data? Or switch to that path?
            # Typically "import" implies bringing data IN.
            # But the CLI "import" sets the path.
            # Let's update the path to match CLI behavior if possible, 
            # though CLI manages persistence in ~/.phobos.json.
            self.config_path = os.path.abspath(path)
            
            print(f"✅ Configuration imported from {path}")
            
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
        # Ensure data is up to date
        self._update_data_from_attributes()
        
        try:
            with open(path, 'w') as f:
                yaml.dump(self._config_data, f, default_flow_style=False)
            print(f"✅ Configuration exported to {path}")
        except Exception as e:
            print(f"❌ Error exporting config: {e}")

    def save(self):
        """
        Save current configuration to file and create a history backup.
        """
        # 1. Update _config_data from attributes (in case of dot-notation changes)
        self._update_data_from_attributes()
        
        # 2. Write to main config file
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(self._config_data, f, default_flow_style=False)
            print(f"✅ Configuration saved to {self.config_path}")
        except Exception as e:
            print(f"❌ Error saving config file: {e}")
            
        # 3. Create backup
        self.backup()

    def backup(self):
        """
        Create a backup of the current config file in config/history.
        Format: YYYY-MM-DD-hh-mm-<commit_id>_N.yml
        """
        if not os.path.exists(self.config_path):
            return

        history_dir = os.path.join(os.path.dirname(self.config_path), 'history')
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
            # Extract Ns
            ns = []
            for f in existing_files:
                try:
                    # .._N.yml -> split by _ -> last part -> split by . -> first part
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
            shutil.copy2(self.config_path, backup_path)
            # print(f"Start of setup.py: config.backup() called") # Debug
            # print(f"History backup created: {backup_filename}")
        except Exception as e:
            print(f"⚠️ Could not create config backup: {e}")

    def _load_from_file(self):
        """Load YAML file."""
        if not os.path.exists(self.config_path):
            # print(f"⚠️ Config file not found at {self.config_path}. Using empty config.")
            return {}
            
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"❌ Error loading config file: {e}")
            return {}

    def _create_attributes(self, data):
        """Recursively create SimpleNamespace attributes for dot access."""
        # Clean existing attributes first to avoid stale data? 
        # For now, just overwrite.
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, self._dict_to_namespace(value))
            else:
                setattr(self, key, value)

    def _dict_to_namespace(self, d):
        """Convert dictionary to SimpleNamespace recursively."""
        ns = SimpleNamespace()
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(ns, k, self._dict_to_namespace(v))
            else:
                setattr(ns, k, v)
        return ns

    def _update_data_from_attributes(self):
        """Reconstruct _config_data dictionary from attributes."""
        # Iterate over keys present in _config_data (structural source of truth)
        # OR iterate over __dict__ and filter?
        # Better to iterate over the keys we know were loaded or added.
        # But if we added new keys via code? 
        # For a simple implementation, let's assume structure is defined by _config_data keys
        # PLUS anything else in __dict__ that isn't private.
        
        new_data = {}
        for key, value in self.__dict__.items():
            if key.startswith('_') or key in ['root_dir', 'config_path']:
                continue
            
            if isinstance(value, SimpleNamespace):
                new_data[key] = self._namespace_to_dict(value)
            else:
                # Assuming valid config types (int, float, str, list, dict-as-namespace)
                new_data[key] = value
        
        self._config_data = new_data
        
    def _namespace_to_dict(self, ns):
        """Convert SimpleNamespace back to dictionary."""
        d = {}
        for k, v in ns.__dict__.items():
            if isinstance(v, SimpleNamespace):
                d[k] = self._namespace_to_dict(v)
            else:
                d[k] = v
        return d

    def get(self, key, default=None):
        """Get value by key (supports dot notation string 'hardware.camera.semid')."""
        try:
            keys = key.split('.')
            val = self
            for k in keys:
                if isinstance(val, dict):
                    val = val[k]
                else:
                    val = getattr(val, k)
            return val
        except (KeyError, AttributeError):
            return default

    def to_dict(self):
        """Return raw dictionary."""
        # Ensure it's up to date
        self._update_data_from_attributes()
        return self._config_data

    def __repr__(self):
        return f"<Config path='{self.config_path}' keys={list(self._config_data.keys())}>"
