import time
from .. import serial

from .utils import Singleton

class FilterWheel(metaclass=Singleton):
    def __init__(self):
        """
        Singleton Class to control the Thorlabs filter wheel. The wheel has 6 positions:
            - 1: ND?
            - 2: ND?
            - 3: ND?
            - 4: ND?
            - 5: ND?
            - 6: ND?
        
        Configuration loaded from `phobos.config.filter_wheel`.
        """
        import phobos
        # Load config
        cfg = phobos.config.filter_wheel
        port = cfg.port
        
        try:
            # super().__init__(port) # This line is commented out as it's not in the original context
            self.session = serial.Serial(port, 115200, timeout=0.1) # Modified to use 'port' from config
            print(f"Filter Wheel connected on port {port}") # Modified to use 'port' from config
            self._connected = True
        except Exception as e:
            if not os.environ.get("PHOBOS_SANDBOX"):
                 print(f"⚠️ FilterWheel connection failed: {e}")
            self._connected = False

        self.default_slot = getattr(phobos.config.filter_wheel, 'default_slot', 1)
        
    def reset(self):
        """
        Reset the filter wheel to the default position defined in config.
        """
        # Reload default slot from dynamic config in case it changed
        import phobos
        self.default_slot = getattr(phobos.config.filter_wheel, 'default_slot', 1) # Changed hardware.filter_wheel to filter_wheel
        self.move(self.default_slot)
        
    def _purge(self):
        """
        Purge all the history of the responses of the filter wheel.
        """
        # Reading the lines actually flush the info after the request
        dummy = self.session.readlines()
    
    def close(self):
        """
        Close the serial connection.
        """
        self.session.close()    

        
    def get(self):
        """
        Get the current info from the filter wheel.

        Returns
        -------
        response : str
            Status of the wheel.

        """
        self._purge() # flush
        self.session.write("pos?\r".encode())
        response = self.session.readline().decode()
        
        return response

        
    def get_pos(self):
        """
        Returns the current position of the filter wheel.

        Returns
        -------
        slot : int
            Current position number of the wheel.

        """
        time.sleep(0.1)
        resp = self.get()
        
        slot = int(resp[5])
        
        return slot

    def move(self, slot:int):
        """
        Move the filter wheel to the specified position.

        Parameters
        ----------
        slot : int
            Position number of the wheel to reach.
        """
        print('FILT - Move to position '+str(slot))
        self.session.write(("pos="+str(slot)+"\r").encode())
        self.wait()

    
    def wait(self) -> None:
        """
        Wait for the motor to reach the target position.
        """
        position = ''
        while len(position) == 0:
            position = self.get()
            time.sleep(0.1)
