import numpy as np
import bmc
import os
import json

class DM():
    """
    Class to represent a deformable mirror (DM) in the optical system.
    """

    def __init__(self, serial_number:str = "27BW007#051", config_path:str = "./DM_config.json"):

        self.serial_number = serial_number

        self.bmcdm = bmc.BmcDm()
        self.bmcdm.open_dm(serial_number)

        self.segments = [Segment(self, i) for i in range(169)]

        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            self.load_config(config)
        else:
            print(f"Config file not found: {config_path}. Segment positions is unknown, reset them using the reset() method before accessing their value.")

    #--------------------------------------------------------------------------

    def __iter__(self):
        """
        Iterate over the segments of the DM.
        """
        for segment in self.segments:
            yield segment

    #Config -------------------------------------------------------------------

    def save_config(self, path:str = "./config.json"):
        """
        Save the current configuration of the DM.
        """

        config = {
            "serial_number": self.serial_number,
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

    def load_config(self, config:dict):
        """
        Load the configuration of the DM from a dictionary.
        """
        
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

        self.piston = None
        self.tip = None
        self.tilt = None

    # piston ------------------------------------------------------------------

    @property
    def piston(self):
        """
        Get the piston value of the segment.
        """
        return self._piston
    
    @piston.setter
    def piston(self, value):
        """
        Set the piston value of the segment.
        """
        self._piston = value
        return self.dm.bmcdm.set_segment(self.id, value, self.tip, self.tilt, True, True)

    # tip ---------------------------------------------------------------------

    @property
    def tip(self):
        """
        Get the tip value of the segment.
        """
        return self._tip
    
    @tip.setter
    def tip(self, value):
        """
        Set the tip value of the segment.
        """
        self._tip = value
        return self.dm.bmcdm.set_segment(self.id, self.piston, value, self.tilt, True, True)

    # tilt --------------------------------------------------------------------

    @property
    def tilt(self):
        """
        Get the tilt value of the segment.
        """
        return self._tilt
    
    @tilt.setter
    def tilt(self, value):
        """
        Set the tilt value of the segment.
        """
        self._tilt = value
        return self.dm.bmcdm.set_segment(self.id, self.piston, self.tip, value, True, True)

    # ptt ---------------------------------------------------------------------

    def set_ptt(self, piston, tip, tilt):
        """
        Get the tip-tilt value of the segment.
        """
        
        self.piston = piston
        self.tip = tip
        self.tilt = tilt

    def get_ptt(self):
        """
        Get the tip-tilt value of the segment.
        """
        
        return self.piston, self.tip, self.tilt