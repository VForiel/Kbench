
class DM():
    """
    Class to represent a deformable mirror (DM) in the optical system.
    """

    def __init__(self):
        self.segments = [Segment(self, i) for i in range(169)]

    #--------------------------------------------------------------------------

    def send_command(self, command):
        """
        Send a command to the DM.
        """
        ...

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

    def __init__(self, DM, id:int):
        self.DM = DM
        self.id = id

    #--------------------------------------------------------------------------

    def get_piston(self):
        """
        Get the piston value of the segment.
        """
        ...

    #--------------------------------------------------------------------------

    def set_piston(self, value):
        """
        Set the piston value of the segment.
        """
        ...

    #--------------------------------------------------------------------------

    def get_tip(self):
        """
        Get the tip value of the segment.
        """
        ...

    #--------------------------------------------------------------------------

    def set_tip(self, value):
        """
        Set the tip value of the segment.
        """
        ...

    #--------------------------------------------------------------------------

    def get_tilt(self):
        """
        Get the tilt value of the segment.
        """
        ...

    #--------------------------------------------------------------------------

    def set_tilt(self, value):
        """
        Set the tilt value of the segment.
        """
        ...
