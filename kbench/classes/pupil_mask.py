import serial

#==============================================================================
# Pupil Mask Class
#==============================================================================

class PupilMask():
    """
    Class to control the mask wheel in the optical system.
    """

    def __init__(
            self,
            # On which ports the components are conencted
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
        """
        if abs:
            return self.zaber_h.set(pos)
        else:
            return self.zaber_h.add(pos)
        
    #--------------------------------------------------------------------------
        
    def move_up(self, pos, abs=False):
        """
        Move the mask up by a certain number of steps.
        """
        if abs:
            return self.zaber_v.set(pos)
        else:
            return self.zaber_v.add(pos)
        
    #--------------------------------------------------------------------------

    def rotate_clockwise(self, pos, abs=False):
        """
        Rotate the mask clockwise by a certain number of degrees.
        """
        if abs:
            return self.newport.set(pos)
        else:
            return self.newport.add(pos)
        
    # Alias
    def rotate(self, pos, abs=False):
        return self.rotate_clockwise(pos, abs)

    #--------------------------------------------------------------------------

    def aplly_mask(self, mask:int):
        """
        Rotate the mask wheel to the desired mask position.
        """
        return self.newport.set(PupilMask.CONFIG["newport_home"] + (mask-1)*60) # Move to the desired mask position
        
    #--------------------------------------------------------------------------
        
    def get_pos(self):
        """
        Get the current position of the mask.
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
# Zaber Classe
#==============================================================================

class Zaber():
    """
    Class to control the Zaber motors (axis).
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
        return self.send_command("get pos")
    
    #--------------------------------------------------------------------------
    
    def set(self, pos):
        return self.send_command(f"move abs {pos}")
    
    #--------------------------------------------------------------------------
    
    def add(self, pos):
        return self.send_command(f"move rel {pos}")
    
#===========================================================================
# Newport Class
#===========================================================================
        
class Newport():
    """
    Class to control the Newport motor (wheel).
    """

    def __init__(self, session):
        self.session = session

    #--------------------------------------------------------------------------

    def send_command(self, command):
        self.session.write(f"{command}\r\n".encode())
        return self.session.readline().decode()
    
    #--------------------------------------------------------------------------

    def get(self):
        return self.send_command("1TP?")
    
    #--------------------------------------------------------------------------

    def set(self, pos:int):
        return self.send_command(f"1PA{pos}")
    
    #--------------------------------------------------------------------------

    def add(self, pos:int):
        return self.send_command(f"1PR{pos}")