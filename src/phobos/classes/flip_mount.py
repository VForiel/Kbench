# External imports
from pylablib.devices import Thorlabs
import time

# Internal imports
from ..utils.singleton import Singleton
import phobos

class FlipMount(metaclass=Singleton):
    """
    Class for the Thorlabs MFF101 Flip Mount.
    """

    def __init__(self) -> None:
        """
        Initialize the flip mount.
        """
        self.mount = Thorlabs.MFF(phobos.config.get('flip_mount.port'))
        self.sleep = phobos.config.get('flip_mount.stabilization_time') # Wait time after command
        self.pos_label = ["up", "down"]

    def get_position(self) -> int:
        """
        Get the current position of the flip mount.

        Returns
        -------
        int
            The current position index : 0 = up; 1 = down.
        """
        pos = self.mount.get_state()
        print(f'Current flip position: {self.pos_label[pos]}')
        return pos

    def move_to_position(self, position: int) -> None:
        """
        Move the flip mount to the specified position.

        Parameters
        ----------
        position : int
            Target position index : 0 = up; 1 = down.
        
        Raises
        ------
        ValueError
            If the position is not 0 or 1.
        """
        if position not in [0, 1]:
            raise ValueError("Position must be 0 (up) or 1 (down).")
            
        self.mount.move_to_state(position)
        time.sleep(self.sleep)
        pos = self.mount.get_state()
        print(f"Moving FlipMount to position {pos} ({self.pos_label[pos]})")

    def toggle(self) -> None:
        """
        Toggle the flip mount between position 0 and 1.
        """
        pos = self.mount.get_state()
        new_position = 1 if pos == 0 else 0
        self.move_to_position(new_position)

    def close(self) -> None:
        """
        Close the connection to the simulated device.
        """
        self.mount.close()
        print("Closed connection to FlipMount.")