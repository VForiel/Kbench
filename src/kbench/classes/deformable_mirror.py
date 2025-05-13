import numpy as np
import bmc

class DM():
    """
    Class to represent a deformable mirror (DM) in the optical system.
    """

    def __init__(self):
        dm_serial_number = "27BW007#051"

        self.dm = bmc.BmcDm()
        self.dm.open_dm(dm_serial_number)
        self.dm.load_calibration_file("")

        self.segments = [Segment(self, i) for i in range(169)]

    #--------------------------------------------------------------------------

    def set_piston(self, value:float):
        """
        Set a global piston value of the DM segments.
        """
        for segment in self.segments:
            segment.set_piston(value)

    #--------------------------------------------------------------------------

    def set_tip(self, value:float):
        """
        Set a global tip value of the DM segments.
        """
        for segment in self.segments:
            segment.set_tip(value)

    #--------------------------------------------------------------------------

    def set_tilt(self, value:float):
        """
        Set a global tilt value of the DM segments.
        """
        for segment in self.segments:
            segment.set_tilt(value)

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

    #--------------------------------------------------------------------------

    def get_piston(self):
        """
        Get the piston value of the segment.
        """
        print("get_piston not implemented")
        ...

    #--------------------------------------------------------------------------

    def set_piston(self, value):
        """
        Set the piston value of the segment.
        """
        return self.dm.set_segment(self.id, value, 0, 0, True, True)

    #--------------------------------------------------------------------------

    def get_tip(self):
        """
        Get the tip value of the segment.
        """
        print("get_tip not implemented")
        ...

    #--------------------------------------------------------------------------

    def set_tip(self, value):
        """
        Set the tip value of the segment.
        """
        return self.dm.set_segment(self.id, 0, value, 0, True, True)

    #--------------------------------------------------------------------------

    def get_tilt(self):
        """
        Get the tilt value of the segment.
        """
        print("get_tilt not implemented")
        ...

    #--------------------------------------------------------------------------

    def set_tilt(self, value):
        """
        Set the tilt value of the segment.
        """
        return self.dm.set_segment(self.id, 0, 0, value, True, True)

    def ptt_to_dac(self, piston, tip, tilt):
        """
        Convert piston, tip, and tilt values to DAC values.
        """

        # TODO
        raise NotImplementedError("ptt_to_dac not implemented")

        a0 = 218.75
        again = 4000.0
        sq3_2 = np.sqrt(3/2)
        
        a_left  = piston + a0 * sq3_2 * tilt + a0/2 * tip;
        a_top   = piston - a0 * tip;
        a_right = piston - a0 * sq3_2 * tilt + a0/2 * tip;
