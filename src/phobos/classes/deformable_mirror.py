import numpy as np
import os
import json
import time
from pathlib import Path

from .. import bmc

from ..utils import Singleton

class DM(metaclass=Singleton):
    """
    Singleton Class to represent a deformable mirror (DM) in the optical system.

    Attributes
    ----------
    serial_number : str
        Serial number of the DM.
    segments : list[Segment]
        List of segments of the DM.
    """

    from .config import Config
    config = Config().dm


    _default_config_path = Path(__file__).parent.parent.parent / "config" / "DM" / "DM_config.json"
    _initialized = False

    def __init__(self):
        """
        Initialize the DM using global configuration.
        """

        # If already initialized, return existing instance
        if self._initialized:
            return
            
        self._initialized = True

        self.N_SEGMENTS = 169

        # Initialize the DM with the given serial number
        self.bmcdm = bmc.BmcDm()
        self.bmcdm.open_dm(config.serial_number)
        self.segments = [Segment(self, i) for i in range(self.N_SEGMENTS)]

        # Set the initial configuration of the DM
        try:
            self.load_config(config_path)
        except FileNotFoundError:
            print(f"Config file not found: {config_path}. Reseting all segments to ptt = (0,0,0).")
            for segment in self.segments:
                segment.set_ptt(0, 0, 0)

        time.sleep(stabilization_time)

    #  Specific methods -------------------------------------------------------

    def __iter__(self):
        """
        Iterate over the segments of the DM.
        
        Yields
        -------
        Segment
            The segments of the DM.
        """
        return iter(self.segments)

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

    def off(self, segments=None):
        """
        Turn off specified injection segments by applying maximum tilt.
        
        This tilts the segments to deflect light away from the photonic chip inputs.
        
        Parameters
        ----------
        segments : int, array-like, or None, optional
            Segment input number(s) to turn off (1-4 for the 4 injection inputs).
            - If int: single input number (e.g., 1 for first injection segment)
            - If array-like: multiple input numbers (e.g., [1, 2, 4])
            - If None: turns off all injection segments
            Default is None.
        
        Examples
        --------
        >>> dm = DM()
        >>> dm.off(1)           # Turn off first injection input
        >>> dm.off([1, 3])      # Turn off inputs 1 and 3
        >>> dm.off()            # Turn off all injection inputs
        
        Notes
        -----
        The off position is: piston=-1150 nm, tip=0 mrad, tilt=-5.47 mrad
        """
        # Parse segment indices
        if segments is None:
            # Turn off all injection segments
            seg_indices = self._injection_segments
        else:
            # Convert input number(s) (1-4) to segment indices
            if isinstance(segments, int):
                segments = [segments]
            
            seg_indices = []
            for seg_num in segments:
                if not 1 <= seg_num <= len(self._injection_segments):
                    raise ValueError(f"Segment number must be between 1 and {len(self._injection_segments)}, got {seg_num}")
                seg_indices.append(self._injection_segments[seg_num - 1])
        
        # Apply off position to selected segments
        for seg_idx in seg_indices:
            self.segments[seg_idx].set_ptt(-1150, 0, -5.47)
        
        print(f"Turned off injection segments: {seg_indices}")
    
    def max(self, segments=None):
        """
        Reset specified injection segments to optimal injection position.
        
        This returns the segments to their nominal position for maximum light coupling.
        
        Parameters
        ----------
        segments : int, array-like, or None, optional
            Segment input number(s) to optimize (1-4 for the 4 injection inputs).
            - If int: single input number (e.g., 1 for first injection segment)
            - If array-like: multiple input numbers (e.g., [1, 2, 4])
            - If None: optimizes all injection segments
            Default is None.
        
        Examples
        --------
        >>> dm = DM()
        >>> dm.max(1)           # Optimize first injection input
        >>> dm.max([1, 3])      # Optimize inputs 1 and 3
        >>> dm.max()            # Optimize all injection inputs
        
        Notes
        -----
        The optimal position is: piston=0 nm, tip=0 mrad, tilt=0 mrad
        """
        # Parse segment indices
        if segments is None:
            # Optimize all injection segments
            seg_indices = self._injection_segments
        else:
            # Convert input number(s) (1-4) to segment indices
            if isinstance(segments, int):
                segments = [segments]
            
            seg_indices = []
            for seg_num in segments:
                if not 1 <= seg_num <= len(self._injection_segments):
                    raise ValueError(f"Segment number must be between 1 and {len(self._injection_segments)}, got {seg_num}")
                seg_indices.append(self._injection_segments[seg_num - 1])
        
        # Apply optimal position to selected segments
        for seg_idx in seg_indices:
            self.segments[seg_idx].set_ptt(0, 0, 0)
        
        print(f"Optimized injection segments: {seg_indices}")

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
        The tip value of the segment in milliradians.
    tilt : float
        The tilt value of the segment in milliradians.
    """

    __slots__ = ['id', 'piston', 'tip', 'tilt']

    _instances = {}

    # Constructors ------------------------------------------------------------

    def __new__(cls, channel: int, *args, **kwargs):

        # Check if channel is valid
        if not (0 <= channel <= dm.N_SEGMENTS):
             raise ValueError(f"❌ Invalid channel number {channel}. Must be between 1 and {dm.N_SEGMENTS}.")
             
        # Return cached instance if it exists
        if channel not in cls._instances:
            cls._instances[channel] = super(PhaseShifter, cls).__new__(cls)

        return cls._instances[channel]
    
    def __init__(self, id:int):
        """
        Initialize the segment with the given DM and ID.

        Parameters
        ----------
        id : int
            The ID of the segment.
        """

        # If already initialized (from cache), skip
        if hasattr(self, 'channel'):
            return

        self.id = id
        self.piston = 0
        self.tip = 0
        self.tilt = 0

    # piston ------------------------------------------------------------------

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
        self.piston = value
        response = self.dm.bmcdm.set_segment(self.id, value, self.tip, self.tilt, True, True)
        # time.sleep(0.01)  # Stabilization delay for BMC hardware
        return response
    
    def get_piston(self) -> float:
        """
        Get the piston value of the segment.

        Returns
        -------
        float
            The piston value of the segment in nm.
        """
        return self.piston

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

    def set_tip(self, value: float) -> str:
        """
        Set the tip value of the segment.

        Parameters
        ----------
        value : float
            The tip value to set in milliradians.

        Returns
        -------
        str
            The response of the mirror.
        """
        self.tip = value / 1000.0
        response = dm.bmcdm.set_segment(self.id, self.piston, self.tip, self.tilt, True, True)
        # time.sleep(0.01)  # Stabilization delay for BMC hardware
        return response

    def get_tip(self) -> float:
        """
        Get the tip value of the segment.

        Returns
        -------
        float
            The tip value of the segment in milliradians.
        """
        return self.tip * 1000.0

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

    def set_tilt(self, value: float) -> str:
        """
        Set the tilt value of the segment.

        Parameters
        ----------
        value : float
            The tilt value to set in milliradians.

        Returns
        -------
        str
            The response of the mirror.
        """
        self.tilt = value / 1000.0
        response = self.dm.bmcdm.set_segment(self.id, self.piston, self.tip, value, True, True)
        # time.sleep(0.01)  # Stabilization delay for BMC hardware
        return response

    def get_tilt(self) -> float:
        """
        Get the tilt value of the segment.

        Returns
        -------
        float
            The tilt value of the segment in milliradians.
        """
        return self.tilt * 1000.0

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
            The tip value to set in milliradians.
        tilt : float
            The tilt value to set in milliradians.

        Returns
        -------
        str
            The response of the mirror for the piston change.
        str
            The response of the mirror for the tip change.
        str
            The response of the mirror for the tilt change.
        """
        tip = tip / 1000.
        tilt = tilt / 1000.
        self.piston = piston
        self.tip = tip
        self.tilt = tilt
        response = self.dm.bmcdm.set_segment(self.id, self.piston, self.tip, self.tilt, True, True)
        # time.sleep(0.01)  # Stabilization delay for BMC hardware
        return response        

    def get_ptt(self) -> tuple[float, float, float]:
        """
        Get the tip-tilt value of the segment.

        Returns
        -------
        float
            The piston value of the segment in nm.
        float
            The tip value of the segment in milliradians.
        float
            The tilt value of the segment in milliradians.
        """
        
        # Inline conversion faster than method calls
        return self.piston, self.tip * 1000.0, self.tilt * 1000.0