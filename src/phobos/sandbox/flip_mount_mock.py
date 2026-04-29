class FlipMount:
    """
    Sandbox mock class for the Thorlabs MFF101 Flip Mount.
    
    This class simulates the behavior of the real hardware when the 
    SANDBOX_MODE is active, allowing development and testing without
    the physical device.
    """

    def __init__(self, serial_number: str = None) -> None:
        """
        Initialize the sandbox flip mount.

        Parameters
        ----------
        serial_number : str, optional
            The serial number of the device, by default None.
        """
        self._position = 1
        print(f"⛱️ [SANDBOX] Initialized FlipMount (SN: {serial_number}). Current position: {self._position}")

    def get_position(self) -> int:
        """
        Get the current position of the flip mount.

        Returns
        -------
        int
            The current position index (typically 1 or 2).
        """
        return self._position

    def move_to_position(self, position: int) -> None:
        """
        Move the flip mount to the specified position.

        Parameters
        ----------
        position : int
            Target position index (1 or 2).
        
        Raises
        ------
        ValueError
            If the position is not 1 or 2.
        """
        if position not in [1, 2]:
            raise ValueError("Position must be 1 or 2.")
            
        self._position = position
        print(f"⛱️ [SANDBOX] Moving FlipMount to position {self._position}")

    def toggle(self) -> None:
        """
        Toggle the flip mount between position 1 and 2.
        """
        new_position = 2 if self._position == 1 else 1
        self.move_to_position(new_position)

    def close(self) -> None:
        """
        Close the connection to the simulated device.
        """
        print("⛱️ [SANDBOX] Closed connection to FlipMount.")