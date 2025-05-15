import numpy as np
import bmc
import os
import json

class DM():
    """
    Class to represent a deformable mirror (DM) in the optical system.
    """

    default_config_path = "./DM_config.json"
    __all__ = []

    def __init__(self, serial_number:str = "27BW007#051", config_path:str = default_config_path):

        # Ensure that the DM is not already in use
        for dm in DM.__all__:
            if dm._serial_number == serial_number:
                raise ValueError(f"DM with serial number {serial_number} already exists.")
        DM.__all__.append(self)

        self._serial_number = serial_number

        # Initialize the DM with the given serial number
        self.bmcdm = bmc.BmcDm()
        self.bmcdm.open_dm(self._serial_number)
        self.segments = [Segment(self, i) for i in range(169)]

        # Set the initial configuration of the DM
        try:
            self.load_config(config_path)
        except FileNotFoundError:
            print(f"Config file not found: {config_path}. Reseting all segments to ptt = (0,0,0).")
            for segment in self.segments:
                segment.set_ptt(0, 0, 0)

    #  Specific methods -------------------------------------------------------

    def __iter__(self):
        """
        Iterate over the segments of the DM.
        """
        for segment in self.segments:
            yield segment

    def __getitem__(self, index):
        """
        Get a segment by its index.
        """

        try:
            index = int(index)
        except ValueError:
            raise TypeError("Index must be an integer.")
        
        if index < 0 or index >= len(self.segments):
            raise IndexError("Index out of range.")
        
        return self.segments[index]
    
    def __len__(self):
        """
        Get the number of segments in the DM.
        """
        return len(self.segments)
    
    def __del__(self):
        """
        Close the DM connection when the object is deleted.
        """
        self.bmcdm.close_dm()
        print(f"DM with serial number {self._serial_number} closed.")
        DM.__all__.remove(self)

    #Config -------------------------------------------------------------------

    def save_config(self, path:str = default_config_path):
        """
        Save the current configuration of the DM.
        """

        config = {
            "serial_number": self._serial_number,
            "segments": {}
        }

        for segment in self.segments:
            config["segments"][segment.id] = {
                "piston": segment.piston,
                "tip": segment.tip,
                "tilt": segment.tilt
            }

        with open(path, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"Configuration saved to {path}")

    def load_config(self, config_path:str = default_config_path):
        """
        Load the configuration of the DM from a JSON file.
        """

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        print(f"Loading config file: {config_path}.")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        for segment_id, segment_config in config["segments"].items():
            segment = self.segments[int(segment_id)]
            segment.set_ptt(segment_config["piston"], segment_config["tip"], segment_config["tilt"])
        
        print("Configuration loaded")

#==============================================================================
# Segment class
#==============================================================================

class Segment():
    """
    Class to represent a segment of the deformable mirror (DM).
    """

    def __init__(self, dm:DM, id:int):
        self.dm = dm
        self.id = id

        self._piston = 0
        self._tip = 0
        self._tilt = 0

    # piston ------------------------------------------------------------------

    @property
    def piston(self):
        """
        Get the piston value of the segment.
        """
        return self.get_piston()
    
    @piston.setter
    def piston(self, value):
        """
        Set the piston value of the segment.
        """
        self.set_piston(value)
        
    
    def set_piston(self, value):
        """
        Set the piston value of the segment.
        """
        self._piston = value
        return self.dm.bmcdm.set_segment(self.id, value, self.tip, self.tilt, True, True)
    
    def get_piston(self):
        """
        Get the piston value of the segment.
        """
        return self._piston
    
    def get_piston_range(self):
        """
        Get the piston range of the segment.
        """
        return self.dm.bmcdm.get_segment_range(self.id, bmc.DM_Piston, self.piston, self.tip, self.tilt, True)

    # tip ---------------------------------------------------------------------

    @property
    def tip(self):
        """
        Get the tip value of the segment.
        """
        return self.get_tip()
    
    @tip.setter
    def tip(self, value):
        """
        Set the tip value of the segment.
        """
        self.set_tip(value)

    def set_tip(self, value):
        """
        Set the tip value of the segment.
        """
        self._tip = value
        return self.dm.bmcdm.set_segment(self.id, self.piston, value, self.tilt, True, True)
    
    def get_tip(self):
        """
        Get the tip value of the segment.
        """
        return self._tip

    def get_tip_range(self):
        """
        Get the tip range of the segment.
        """
        return self.dm.bmcdm.get_segment_range(self.id, bmc.DM_XTilt, self.piston, self.tip, self.tilt, True)

    # tilt --------------------------------------------------------------------

    @property
    def tilt(self):
        """
        Get the tilt value of the segment.
        """
        return self.get_tilt()
    
    @tilt.setter
    def tilt(self, value):
        """
        Set the tilt value of the segment.
        """
        self.set_tilt(value)
    
    def set_tilt(self, value):
        """
        Set the tilt value of the segment.
        """
        self._tilt = value
        return self.dm.bmcdm.set_segment(self.id, self.piston, self.tip, value, True, True)

    def get_tilt(self):
        """
        Get the tilt value of the segment.
        """
        return self._tilt
    
    def get_tilt_range(self):
        """
        Get the tilt range of the segment.
        """
        return self.dm.bmcdm.get_segment_range(self.id, bmc.DM_YTilt, self.piston, self.tip, self.tilt, True)

    # ptt ---------------------------------------------------------------------

    def set_ptt(self, piston, tip, tilt):
        """
        Get the tip-tilt value of the segment.
        """
        return self.set_piston(piston), self.set_tip(tip), self.set_tilt(tilt)

    def get_ptt(self):
        """
        Get the tip-tilt value of the segment.
        """
        return self.piston, self.tip, self.tilt