import numpy as np
import os
import json
import time
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from .. import bmc

from ..utils import Singleton
from .config import Config

class DM(metaclass=Singleton):
    """
    Singleton Class to represent a deformable mirror (DM) in the optical system.

        Hardware ranges (bench reference)
        -------------------------------
        The DM has segment-dependent stroke limits. On the PHOBos bench, the injection
        segments typically used for coupling (e.g. around segments 111-114, 135-138,
        145-148 depending on the mapping in ``injection.segments``) have piston
        ranges of roughly:

        - Segments 111-114: piston in [-2520, 264] nm (delta ~2784 nm)
        - Segments 145-148: piston in [-2557, 214] nm (delta ~2771 nm)
        - Segments 135-138: piston in [-2530, 230] nm (delta ~2760 nm)

        Tip/tilt ranges depend on the current piston working point. Around typical
        injection working pistons (-1128 nm / -1150 nm), absolute tip/tilt can reach
        approximately ±5.4 mrad in both axes. In normal operation, tip/tilt values
        are usually kept below ~1.5 mrad for alignment stability.

        Notes
        -----
        - For authoritative limits, always query the controller via
            :meth:`Segment.get_piston_range`, :meth:`Segment.get_tip_range`, and
            :meth:`Segment.get_tilt_range`.
        - Software-side safety clamping is applied in :meth:`Segment.set_piston`.

    Attributes
    ----------
    segments : list[Segment]
        List of segments of the DM.
    """

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "DM" / "DM_config.json"
    N_SEGMENTS = 169
    _initialized = False

    def __init__(self, config_path:str = DEFAULT_CONFIG_PATH):
        """
        Initialize the DM using global configuration.
        """

        # If already initialized, return existing instance
        if self._initialized:
            return

        self._initialized = True

        # Initialize the DM with the given serial number
        self.bmcdm = bmc.BmcDm()
        self.bmcdm.open_dm(Config().get('dm.serial_number'))
        self.segments = [Segment(i) for i in range(DM.N_SEGMENTS)]

        time.sleep(Config().get('dm.stabilization_time', 0.001))

    # Properties --------------------------------------------------------------

    @property
    def mid_piston(self):
        """
        The middle piston position of the DM (in nm).
        """
        return int(np.mean(Config().get('dm.piston_range')))
    
    @mid_piston.setter
    def mid_piston(self, value):
        raise ValueError("DM().mid_piston is read-only.")

    # Specific methods --------------------------------------------------------

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
        for segment in self.segments:
            del segment
        print(f"DM with serial number {Config().get('dm.serial_number')} closed.")

    #Config -------------------------------------------------------------------

    def save_config(self, path:str = DEFAULT_CONFIG_PATH) -> None:
        """
        Save the current configuration of the DM.

        Parameters
        ----------
        path : str
            Path to the configuration file.
        """

        config = {
            "serial_number": Config().get('dm.serial_number'),
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

    def load_config(self, config_path:str = DEFAULT_CONFIG_PATH):
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

    # ------------------------------------------------------------------
    # Backward-compatible injection helpers (delegate to Injection())
    # ------------------------------------------------------------------
    # The old DM API used **1-based** input numbers; the new Injection
    # singleton uses **0-based** channels.  The thin wrappers below
    # convert automatically and emit a DeprecationWarning.

    @staticmethod
    def _segments_to_channels(segments):
        """Convert 1-based segment numbers (old DM API) to 0-based channels."""
        if segments is None:
            return None
        if isinstance(segments, (int, np.integer)):
            return int(segments) - 1
        return [int(s) - 1 for s in segments]

    def off(self, segments=None):
        """Deprecated – use ``Injection().off()`` instead.

        .. deprecated::
            Will be removed in a future version.
        """
        warnings.warn(
            "DM.off() is deprecated; use Injection().off() instead.",
            DeprecationWarning, stacklevel=2,
        )
        from .injection import Injection
        Injection().off(self._segments_to_channels(segments))

    def zero(self, segments=None):
        """Deprecated – use ``Injection().zero()`` instead.

        .. deprecated::
            Will be removed in a future version.
        """
        warnings.warn(
            "DM.zero() is deprecated; use Injection().zero() instead.",
            DeprecationWarning, stacklevel=2,
        )
        from .injection import Injection
        Injection().zero(self._segments_to_channels(segments))

    def flat(self, segments=None):
        """Deprecated – use ``Injection().flat()`` instead.

        .. deprecated::
            Will be removed in a future version.
        """
        warnings.warn(
            "DM.flat() is deprecated; use Injection().flat() instead.",
            DeprecationWarning, stacklevel=2,
        )
        from .injection import Injection
        Injection().flat(self._segments_to_channels(segments))

    def max(self, segments=None):
        """Deprecated – use ``Injection().max()`` instead.

        .. deprecated::
            Will be removed in a future version.
        """
        warnings.warn(
            "DM.max() is deprecated; use Injection().max() instead.",
            DeprecationWarning, stacklevel=2,
        )
        from .injection import Injection
        Injection().max(self._segments_to_channels(segments))

    def balanced(self, segments=None):
        """Deprecated – use ``Injection().balanced()`` instead.

        .. deprecated::
            Will be removed in a future version.
        """
        warnings.warn(
            "DM.balanced() is deprecated; use Injection().balanced() instead.",
            DeprecationWarning, stacklevel=2,
        )
        from .injection import Injection
        Injection().balanced(self._segments_to_channels(segments))

    # Backward compatibility: previous API used max_flat() for flat.
    def max_flat(self, segments=None):
        """Deprecated alias for :meth:`flat` (kept for backward compatibility)."""
        warnings.warn(
            "DM.max_flat() is deprecated; use Injection().flat() instead.",
            DeprecationWarning, stacklevel=2,
        )
        from .injection import Injection
        Injection().flat(self._segments_to_channels(segments))

    def get_injection_maps(self, *args, **kwargs):
        """Deprecated – use ``Injection().get_injection_maps()`` instead.

        .. deprecated::
            Will be removed in a future version.
        """
        warnings.warn(
            "DM.get_injection_maps() is deprecated; use Injection().get_injection_maps() instead.",
            DeprecationWarning, stacklevel=2,
        )
        from .injection import Injection
        return Injection().get_injection_maps(*args, **kwargs)

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

    def __new__(cls, id: int, *args, **kwargs):

        # Check if channel is valid
        if not (0 <= id <= DM.N_SEGMENTS):
             raise ValueError(f"❌ Invalid channel number {id}. Must be between 1 and {DM.N_SEGMENTS}.")

        # Return cached instance if it exists
        if id not in cls._instances:
            cls._instances[id] = super(Segment, cls).__new__(cls)

        return cls._instances[id]

    def __init__(self, id:int):
        """
        Initialize the segment with the given DM and ID.

        Parameters
        ----------
        id : int
            The ID of the segment.
        """

        # If already initialized (from cache), skip
        if hasattr(self, 'id'):
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
        # Clamp to hardware limits (query current range because it can depend on
        # the current segment state).
        try:
            p_min, p_max = self.get_piston_range()
            value = float(np.clip(float(value), float(p_min), float(p_max)))
        except Exception:
            # If range query fails (e.g. sandbox/mock), proceed without clamping.
            value = float(value)

        self.piston = value
        response = DM().bmcdm.set_segment(self.id, value, self.tip, self.tilt, True, True)
        time.sleep(Config().get('dm.stabilization_time'))  # Stabilization delay for BMC hardware
        return response

    def set_phase(self, phase: float, lam: float = 1550.0) -> str:
        """Set the segment piston using a phase command.

        This converts a phase (radians) into an optical path difference expressed
        as a segment piston (nm). The command uses the configured piston range
        to define the phase origin and direction:

        - phase 0 rad corresponds to the center of the piston range,
          i.e. mean(``Config().get('dm.piston_range')``)
        - phase in [0, pi] moves the piston more negative ("recedes")
        - phase in (pi, 2*pi) moves the piston more positive ("advances")

        The phase is first wrapped modulo 2*pi.

        Parameters
        ----------
        phase : float
            Phase command in radians.
        lam : float, optional
            Wavelength in nanometers. Default is 1550.

        Returns
        -------
        str
            Hardware response string from the DM controller.
        """

        # Get corresponding distance
        distance = phase * lam / (2 * np.pi)

        # Get zero position
        zero = int(np.mean(Config().get('dm.piston_range')))

        # Position to set
        position = zero + distance

        # Check if position is within range
        if position < Config().get('dm.piston_range')[0] or position > Config().get('dm.piston_range')[1]:
            raise ValueError(f"Position {position} is outside the configured range")

        return self.set_piston(position)

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
        return DM().bmcdm.get_segment_range(self.id, bmc.DM_Piston, self.piston, self.tip, self.tilt, True)

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
        response = DM().bmcdm.set_segment(self.id, self.piston, self.tip, self.tilt, True, True)
        time.sleep(Config().get('dm.stabilization_time'))  # Stabilization delay for BMC hardware
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
        return DM().bmcdm.get_segment_range(self.id, bmc.DM_XTilt, self.piston, self.tip, self.tilt, True)

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
        response = DM().bmcdm.set_segment(self.id, self.piston, self.tip, self.tilt, True, True)
        time.sleep(Config().get('dm.stabilization_time'))  # Stabilization delay for BMC hardware
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
        return DM().bmcdm.get_segment_range(self.id, bmc.DM_YTilt, self.piston, self.tip, self.tilt, True)

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
        response = DM().bmcdm.set_segment(self.id, self.piston, self.tip, self.tilt, True, True)
        time.sleep(Config().get('dm.stabilization_time'))  # Stabilization delay for BMC hardware
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
