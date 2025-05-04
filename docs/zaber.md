# Zaber

The `Zaber` class is used to control Zaber motors for horizontal and vertical movements.

## Initialization

To initialize an instance of `Zaber`, you need to provide a serial session and an axis identifier:

```python
from kbench import Zaber
import serial

session = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1)
zaber_motor = Zaber(session, id=1)
```

## Methods

- `get()`: Returns the current position of the motor.
- `set(pos)`: Moves the motor to an absolute position.
- `add(pos)`: Moves the motor by a relative number of steps.

## Example

```python
from kbench import Zaber
import serial

session = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.1)
zaber_motor = Zaber(session, id=1)
zaber_motor.set(1000)  # Move to position 1000
current_position = zaber_motor.get()
print(f"Zaber motor position: {current_position}")
```
