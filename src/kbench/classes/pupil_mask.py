import serial
import time

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
            zaber_h_home:int = 188490, # Horizontal axis home position (steps)
            zaber_v_home:int = 154402, # Vertical axis home position (steps)
            newport_home:float = 56.15, # Angle of the pupil mask n°1 (degree)
            ):
        """
        Parameters
        ----------
        zaber_port : str
            Port for the Zaber motors (default is "/dev/ttyUSB0").
        newport_port : str
            Port for the Newport motor (default is "/dev/ttyUSB1").
        zaber_h_home : int
            Home position for the horizontal motor (default is 188490).
        zaber_v_home : int
            Home position for the vertical motor (default is 154402).
        newport_home : float
            Angular home position for the first mask (default is 56.15).
        """
        
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

        self.reset()

    #--------------------------------------------------------------------------

    def move_right(self, pos:int, abs:bool=False) -> str:
        """
        Move the mask to the right by a certain number of steps.

        Parameters
        ----------
        pos : int
            Number of steps to move.
        abs : bool, optional
            If True, move to an absolute position. Default is False.

        Returns
        -------
        str
            Response from the motor after moving to the target position.
        """
        if abs:
            return self.zaber_h.set(pos)
        else:
            return self.zaber_h.add(pos)
        
    #--------------------------------------------------------------------------

    def move_up(self, pos:int, abs:bool=False) -> str:
        """
        Move the mask up by a certain number of steps.

        Parameters
        ----------
        pos : int
            Number of steps to move.
        abs : bool, optional
            If True, move to an absolute position. Default is False.

        Returns
        -------
        str
            Response from the motor after moving to the target position.
        """
        if abs:
            return self.zaber_v.set(pos)
        else:
            return self.zaber_v.add(pos)
        
    #--------------------------------------------------------------------------

    def rotate_clockwise(self, pos:float, abs:bool=False) -> str:
        """
        Rotate the mask clockwise by a certain number of degrees.
        Alias: rotate()

        Parameters
        ----------
        pos : float
            Number of degrees to rotate.
        abs : bool, optional
            If True, rotate to an absolute position. Default is False.

        Returns
        -------
        str
            Response from the motor after moving to the target position.
        """
        if abs:
            return self.newport.set(pos)
        else:
            return self.newport.add(pos)
      
    def rotate(self, pos:float, abs:bool=False) -> str:
        return self.rotate_clockwise(pos, abs)

    # Apply Mask --------------------------------------------------------------

    def apply_mask(self, mask:int) -> str:
        """
        Rotate the mask wheel to the desired mask position.

        Parameters
        ----------
        mask : int
            Mask number to apply.

        Returns
        -------
        str
            Response from the motor after moving to the target position.
        """
        return self.newport.set(self.newport_home + (mask-1)*60) # Move to the desired mask position
        
    #--------------------------------------------------------------------------
        
    def get_pos(self):
        """
        Get the current position of the mask.

        Returns
        -------
        float
            Current angular position of the mask wheel (in degrees).
        int
            Current position of the horizontal Zaber motor (in steps).
        int
            Current position of the vertical Zaber motor (in steps).
        """
        return self.newport.get(), self.zaber_h.get(), self.zaber_v.get()
    
    #--------------------------------------------------------------------------

    def reset(self) -> None:
        """
        Reset the mask wheel to the 4 vertical holes and the Zaber motors to their home positions.
        """
        self.apply_mask(4)
        self.zaber_h.set(self.zaber_h_home)
        self.zaber_v.set(self.zaber_v_home)
    
#==============================================================================
# Zaber Class
#==============================================================================

class Zaber():
    """
    Class to control the Zaber motors (axis).

    Attributes
    ----------
    id : int
        ID of the Zaber motor.
    """

    def __init__(self, session, id):
        """
        Parameters
        ----------
        session : serial.Serial
            Serial connection to the Zaber motor.
        id : int
            ID of the Zaber motor.
        """
        self._session = session
        self.id = id

    # Properties --------------------------------------------------------------

    @property
    def id(self) -> int:
        return self._id
    
    @id.setter
    def id(self, id:int) -> None:
        raise ValueError("ID cannot be changed after initialization.")
    

    # Wait --------------------------------------------------------------------

    def wait(self) -> None:
        """
        Wait for the motor to reach the target position.
        """
        position = None
        while position != self.get():
            position = self.get()
            time.sleep(0.1)

    #--------------------------------------------------------------------------

    def send_command(self, command):
        """
        Send a command to the motor and return the response.

        Parameters
        ----------
        command : str
            Command to send to the motor.

        Returns
        -------
        str
            Response from the motor.
        """
        self._session.write(f"/{self.id} {command}\r\n".encode())
        return self._session.readline().decode()
    
    #--------------------------------------------------------------------------

    def get(self) -> int:
        """
        Get the current position of the motor.

        Returns
        -------
        int
            Current position of the motor (in steps).
        """
        return self.send_command("get pos")
    
    #--------------------------------------------------------------------------
    
    def set(self, pos:int) -> str:
        """
        Move the motor to an absolute position.

        Parameters
        ----------
        pos : int
            Target position in steps.

        Returns
        -------
        str
            Response from the motor after moving to the target position.
        """
        response = self.send_command(f"move abs {pos}")
        self.wait()
        return response
    
    #--------------------------------------------------------------------------

    def add(self, pos:int) -> str:
        """
        Move the motor by a relative number of steps.

        Parameters
        ----------
        pos : int
            Number of steps to move.

        Returns
        -------
        str
            Response from the motor after moving to the target position.
        """
        response = self.send_command(f"move rel {pos}")
        self.wait()
        return response
    
#==============================================================================
# Newport Class
#==============================================================================

class Newport():
    """
    Class to control the Newport motor (wheel).
    """

    def __init__(self, session):
        """
        Initialize the Newport motor.

        Parameters
        ----------
        session : serial.Serial
            Serial connection to the Newport motor.
        """
        self._session = session
        self.home_search()

    #--------------------------------------------------------------------------

    def home_search(self) -> str:
        """
        Move the motor to the home position.

        Returns
        -------
        str
            Response from the motor after moving to home position.
        """
        response = self.send_command("1OR?")
        self.wait()
        return response

    # Wait --------------------------------------------------------------------

    def wait(self) -> None:
        """
        Wait for the motor to reach the target position.
        """
        position = None
        while position != self.get():
            position = self.get()
            time.wait(0.1)

    #--------------------------------------------------------------------------

    def send_command(self, command):
        """
        Send a command to the motor and return the response.

        Parameters
        ----------
        command : str
            Command to send to the motor.

        Returns
        -------
        str
            Response from the motor.
        """

        self._session.write(f"{command}\r\n".encode())
        return self._session.readline().decode()
    
    #--------------------------------------------------------------------------

    def get(self) -> float:
        """
        Get the current angular position of the motor (in degrees).

        Returns
        -------
        float
            Current angular position (in degrees) of the motor in degrees.
        """
        return float(self.send_command("1TP?")[3:-2])
    
    #--------------------------------------------------------------------------

    def set(self, pos:float) -> str:
        """
        Rotate the motor to an absolute angular position (in degrees).

        Parameters
        ----------
        pos : int
            Target angular position in degrees.

        Returns
        -------
        str
            Response from the motor after moving to the target position.
        """
        response = self.send_command(f"1PA{pos}")
        self.wait()
        return response
    
    #--------------------------------------------------------------------------

    def add(self, pos:int) -> str:
        """
        Rotate the motor by a relative angle.

        Parameters
        ----------
        pos : int
            Angle to rotate in degrees.

        Returns
        -------
        str
            Response from the motor after moving to the target position.
        """
        response = self.send_command(f"1PR{pos}")
        self.wait()
        return response