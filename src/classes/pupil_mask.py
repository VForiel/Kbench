import serial

class PupilMask():
    """
    Class to control the mask wheel in the optical system.
    """

    def __init__(self):
        
        # To change if the Zaber is connected to another port
        zaber_session = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1)
        newport_session = serial.Serial("/dev/ttyUSB1", 921600, timeout=0.1)

        self.zaber_v = Zaber(zaber_session, 1)
        self.zaber_h = Zaber(zaber_session, 2)
        self.newport = Newport(newport_session)

    def move_right(self, pos, abs=False):
        """
        Move the mask to the right by a certain number of steps.
        """
        if abs:
            return self.zaber_h.set(pos)
        else:
            return self.zaber_h.add(pos)
        
    def move_up(self, pos, abs=False):
        """
        Move the mask up by a certain number of steps.
        """
        if abs:
            return self.zaber_v.set(pos)
        else:
            return self.zaber_v.add(pos)
        
    def get_pos(self):
        """
        Get the current position of the mask.
        """
        return self.zaber_h.get(), self.zaber_v.get()

class Zaber():
    """
    Class to control the Zaber motors (axis).
    """

    def __init__(self, session, id):
        self.session = session
        self.id = id

    def send_command(self, command):
        self.session.write(f"/{self.id} {command}\r\n".encode())
        return self.session.readline().decode()

    def get(self):
        return self.send_command("get pos")
    
    def set(self, pos):
        return self.send_command(f"move abs {pos}")
    
    def add(self, pos):
        return self.send_command(f"move rel {pos}")
        
class Newport():
    """
    Class to control the Newport motor (wheel).
    """

    def __init__(self, session):
        self.session = session

    def send_command(self, command):
        self.session.write(f"{command}\r\n".encode())
        return self.session.readline().decode()