import numpy as np
import bmc
import os
import json

class DM():
    """
    Class to represent a deformable mirror (DM) in the optical system.

    Attributes
    ----------
    serial_number : str
        Serial number of the DM.
    segments : list[Segment]
        List of segments of the DM.
    """

    _default_config_path = "./DM_config.json"
    _all = []

    def __init__(self, serial_number:str = "27BW007#051", config_path:str = _default_config_path):
        """
        Initialize the DM with the given serial number and configuration file.

        Parameters
        ----------
        serial_number : str
            Serial number of the DM.
        config_path : str
            Path to the configuration file.
        """

        # Ensure that the DM is not already in use
        for dm in DM._all:
            if dm._serial_number == serial_number:
                raise ValueError(f"DM with serial number {serial_number} already exists.")
        DM._all.append(self)

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

    # Properties ------------------------------------------------------------

    @property
    def serial_number(self) -> str:
        return self._serial_number
    
    @serial_number.setter
    def serial_number(self, _):
        raise AttributeError("Serial number is read-only and cannot be modified.")
    
    @property
    def segments(self) -> list['Segment']:
        return self._segments
    
    @segments.setter
    def segments(self, _):
        raise AttributeError("Segments are read-only and cannot be modified.")

    #  Specific methods -------------------------------------------------------

    def __iter__(self):
        """
        Iterate over the segments of the DM.
        
        Yields
        -------
        Segment
            The segments of the DM.
        """
        for segment in self.segments:
            yield segment

    def __getitem__(self, index) -> 'Segment':
        """
        Get a segment by its index.

        Parameters
        ----------
        index : int
            Index of the segment to get.
        Returns
        -------
        Segment
            The segment at the given index.
        """
        try:
            index = int(index)
        except ValueError:
            raise TypeError("Index must be an integer.")
        
        if index < 0 or index >= len(self.segments):
            raise IndexError("Index out of range.")
        
        return self.segments[index]
    
    def __len__(self) -> int:
        """
        Get the number of segments in the DM.

        Returns
        -------
        int
            The number of segments in the DM.
        """
        return len(self.segments)
    
    def __del__(self):
        """
        Close the DM connection when the object is deleted.
        """
        self.bmcdm.close_dm()
        print(f"DM with serial number {self._serial_number} closed.")
        DM._all.remove(self)

    #Config -------------------------------------------------------------------

    def save_config(self, path:str = _default_config_path) -> None:
        """
        Save the current configuration of the DM.

        Parameters
        ----------
        path : str
            Path to the configuration file.
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

    def load_config(self, config_path:str = _default_config_path):
        """
        Load the configuration of the DM from a JSON file.

        Parameters
        ----------
        config_path : str
            Path to the configuration file.
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

    Attributes
    ----------
    dm : DM
        The DM to which the segment belongs.
    id : int
        The ID of the segment.
    piston : float
        The piston value of the segment in nm.
    tip : float
        The tip value of the segment in radians.
    tilt : float
        The tilt value of the segment in radians.
    """

    def __init__(self, dm:DM, id:int):
        """
        Initialize the segment with the given DM and ID.

        Parameters
        ----------
        dm : DM
            The DM to which the segment belongs.
        id : int
            The ID of the segment.
        """

        self.dm = dm
        self.id = id

        self._piston = 0
        self._tip = 0
        self._tilt = 0

    # piston ------------------------------------------------------------------

    @property
    def piston(self) -> float:
        return self.get_piston()
    
    @piston.setter
    def piston(self, value: float):
        self.set_piston(value)
        
    
    def set_piston(self, value) -> str:
        """
        Set the piston value of the segment.

        Parameters
        ----------
        value : float
            The piston value to set in nm.

        Returns
        -------
        str
            The response of the mirror.
        """
        self._piston = value
        return self.dm.bmcdm.set_segment(self.id, value, self.tip, self.tilt, True, True)
    
    def get_piston(self) -> float:
        """
        Get the piston value of the segment.

        Returns
        -------
        float
            The piston value of the segment in nm.
        """
        return self._piston

    def get_piston_range(self) -> list[float]:
        """
        Get the piston range of the segment.

        Returns
        -------
        list[float]
            The piston range ([min, max]) of the segment in nm.
        """
        return self.dm.bmcdm.get_segment_range(self.id, bmc.DM_Piston, self.piston, self.tip, self.tilt, True)

    # tip ---------------------------------------------------------------------

    @property
    def tip(self) -> float:
        return self.get_tip()
    
    @tip.setter
    def tip(self, value: float) -> None:
        self.set_tip(value)

    def set_tip(self, value: float) -> str:
        """
        Set the tip value of the segment.

        Parameters
        ----------
        value : float
            The tip value to set in radians.

        Returns
        -------
        str
            The response of the mirror.
        """
        self._tip = value
        return self.dm.bmcdm.set_segment(self.id, self.piston, value, self.tilt, True, True)

    def get_tip(self) -> float:
        """
        Get the tip value of the segment.

        Returns
        -------
        float
            The tip value of the segment in radians.
        """
        return self._tip

    def get_tip_range(self) -> list[float]:
        """
        Get the tip range of the segment.

        Returns
        -------
        list[float]
            The tip range ([min, max]) of the segment in radians.
        """
        return self.dm.bmcdm.get_segment_range(self.id, bmc.DM_XTilt, self.piston, self.tip, self.tilt, True)

    # tilt --------------------------------------------------------------------

    @property
    def tilt(self) -> float:
        return self.get_tilt()
    
    @tilt.setter
    def tilt(self, value: float) -> None:
        self.set_tilt(value)

    def set_tilt(self, value: float) -> str:
        """
        Set the tilt value of the segment.

        Parameters
        ----------
        value : float
            The tilt value to set in radians.

        Returns
        -------
        str
            The response of the mirror.
        """
        self._tilt = value
        return self.dm.bmcdm.set_segment(self.id, self.piston, self.tip, value, True, True)

    def get_tilt(self) -> float:
        """
        Get the tilt value of the segment.

        Returns
        -------
        float
            The tilt value of the segment in radians.
        """
        return self._tilt

    def get_tilt_range(self) -> list[float]:
        """
        Get the tilt range of the segment.

        Returns
        -------
        list[float]
            The tilt range ([min, max]) of the segment in radians.
        """
        return self.dm.bmcdm.get_segment_range(self.id, bmc.DM_YTilt, self.piston, self.tip, self.tilt, True)

    # ptt ---------------------------------------------------------------------

    def set_ptt(self, piston: float, tip: float, tilt: float) -> tuple[str]:
        """
        Get the tip-tilt value of the segment.

        Parameters
        ----------
        piston : float
            The piston value to set in nm.
        tip : float
            The tip value to set in radians.
        tilt : float
            The tilt value to set in radians.

        Returns
        -------
        str
            The response of the mirror for the piston change.
        str
            The response of the mirror for the tip change.
        str
            The response of the mirror for the tilt change.
        """
        return self.set_piston(piston), self.set_tip(tip), self.set_tilt(tilt)

    def get_ptt(self) -> tuple[float]:
        """
        Get the tip-tilt value of the segment.

        Returns
        -------
        float
            The piston value of the segment in nm.
        float
            The tip value of the segment in radians.
        float
            The tilt value of the segment in radians.
        """
        return self.piston, self.tip, self.tilt