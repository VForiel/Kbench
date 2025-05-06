import serial

#==============================================================================
# Pupil Mask Class
#==============================================================================

class PupilMask():
    """
    Class to control the mask wheel in the optical system.

    Attributes
    ----------
    zaber_h : Zaber
        Instance of the Zaber class for controlling the horizontal motor.
    zaber_v : Zaber
        Instance of the Zaber class for controlling the vertical motor.
    newport : Newport
        Instance of the Newport class for controlling the mask wheel.
    zaber_h_home : int
        Home position for the horizontal motor (in steps).
    zaber_v_home : int
        Home position for the vertical motor (in steps).
    newport_home : float
        Angular home position for the first mask (in degrees).
    """

    def __init__(
            self,
            # On which ports the components are connected
            zaber_port:str = "/dev/ttyUSB0",
            newport_port:str = "/dev/ttyUSB1",
            zaber_h_home:int = 189390, # Horizontal axis home position (steps)
            zaber_v_home:int = 157602, # Vertical axis home position (steps)
            newport_home:float = 56.3, # Angle of the pupil mask n°1 (degree)
            ):
        
        # Initialize the serial connections for Zaber and Newport
        zaber_session = serial.Serial(zaber_port, 115200, timeout=0.1)
        newport_session = serial.Serial(newport_port, 921600, timeout=0.1)

        self.zaber_h_home = zaber_h_home
        self.zaber_v_home = zaber_v_home
        self.newport_home = newport_home

        # Initialize the Zaber and Newport objects
        self.zaber_v = Zaber(zaber_session, 1)
        self.zaber_h = Zaber(zaber_session, 2)
        self.newport = Newport(newport_session)

    #--------------------------------------------------------------------------

    def move_right(self, pos, abs=False):
        """
        Move the mask to the right by a certain number of steps.

        Parameters
        ----------
        pos : int
            Number of steps to move.
        abs : bool, optional
            If True, move to an absolute position. Default is False.
        """
        if abs:
            return self.zaber_h.set(pos)
        else:
            return self.zaber_h.add(pos)
        
    #--------------------------------------------------------------------------
        
    def move_up(self, pos, abs=False):
        """
        Move the mask up by a certain number of steps.

        Parameters
        ----------
        pos : int
            Number of steps to move.
        abs : bool, optional
            If True, move to an absolute position. Default is False.
        """
        if abs:
            return self.zaber_v.set(pos)
        else:
            return self.zaber_v.add(pos)
        
    #--------------------------------------------------------------------------

    def rotate_clockwise(self, pos, abs=False):
        """
        Rotate the mask clockwise by a certain number of degrees.

        Parameters
        ----------
        pos : float
            Number of degrees to rotate.
        abs : bool, optional
            If True, rotate to an absolute position. Default is False.
        """
        if abs:
            return self.newport.set(pos)
        else:
            return self.newport.add(pos)
        
    # Alias
    def rotate(self, pos, abs=False):
        return self.rotate_clockwise(pos, abs)

    #--------------------------------------------------------------------------

    def apply_mask(self, mask:int):
        """
        Rotate the mask wheel to the desired mask position.

        Parameters
        ----------
        mask : int
            Mask number to apply.
        """
        return self.newport.set(self.newport_home + (mask-1)*60) # Move to the desired mask position
        
    #--------------------------------------------------------------------------
        
    def get_pos(self):
        """
        Get the current position of the mask.

        Returns
        -------
        tuple
            Current positions of the horizontal and vertical motors.
        """
        return self.zaber_h.get(), self.zaber_v.get()
    
    #--------------------------------------------------------------------------

    def reset(self) -> None:
        """
        Reset the mask wheel to the 4 vertical holes.
        """
        self.newport.set(self.newport_home + 3*60) # Move to 4 vertical holes position
        self.zaber_h.set(self.zaber_h_home)
        self.zaber_v.set(self.zaber_v_home)
    
#==============================================================================
# Zaber Class
#==============================================================================

class Zaber():
    """
    Class to control the Zaber motors (axis).

    Methods
    -------
    get()
        Get the current position of the motor.
    set(pos)
        Move the motor to an absolute position.
    add(pos)
        Move the motor by a relative number of steps.
    """

    def __init__(self, session, id):
        self.session = session
        self.id = id

    #--------------------------------------------------------------------------

    def send_command(self, command):
        self.session.write(f"/{self.id} {command}\r\n".encode())
        return self.session.readline().decode()
    
    #--------------------------------------------------------------------------

    def get(self):
        """
        Get the current position of the motor.

        Returns
        -------
        str
            Current position of the motor.
        """
        return self.send_command("get pos")
    
    #--------------------------------------------------------------------------
    
    def set(self, pos):
        """
        Move the motor to an absolute position.

        Parameters
        ----------
        pos : int
            Target position in steps.
        """
        return self.send_command(f"move abs {pos}")
    
    #--------------------------------------------------------------------------
    
    def add(self, pos):
        """
        Move the motor by a relative number of steps.

        Parameters
        ----------
        pos : int
            Number of steps to move.
        """
        return self.send_command(f"move rel {pos}")
    
#==============================================================================
# Newport Class
#==============================================================================

class Newport():
    """
    Class to control the Newport motor (wheel).

    Methods
    -------
    get()
        Get the current angular position of the motor.
    set(pos)
        Rotate the motor to an absolute angular position.
    add(pos)
        Rotate the motor by a relative angle.
    """

    def __init__(self, session):
        self.session = session

    #--------------------------------------------------------------------------

    def send_command(self, command):
        self.session.write(f"{command}\r\n".encode())
        return self.session.readline().decode()
    
    #--------------------------------------------------------------------------

    def get(self):
        """
        Get the current angular position of the motor.

        Returns
        -------
        str
            Current angular position of the motor.
        """
        return self.send_command("1TP?")
    
    #--------------------------------------------------------------------------

    def set(self, pos:int):
        """
        Rotate the motor to an absolute angular position.

        Parameters
        ----------
        pos : int
            Target angular position in degrees.
        """
        return self.send_command(f"1PA{pos}")
    
    #--------------------------------------------------------------------------

    def add(self, pos:int):
        """
        Rotate the motor by a relative angle.

        Parameters
        ----------
        pos : int
            Angle to rotate in degrees.
        """
        return self.send_command(f"1PR{pos}")