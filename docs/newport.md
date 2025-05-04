# Newport

The `Newport` class is used to control the Newport motor for rotating the mask wheel.

## Initialization

To initialize an instance of `Newport`, you need to provide a serial session:

```python
from kbench import Newport
import serial

session = serial.Serial("/dev/ttyUSB1", 921600, timeout=0.1)
newport_motor = Newport(session)
```

## Methods

- `get()`: Returns the current angular position of the motor.
- `set(pos)`: Rotates the motor to an absolute angular position.
- `add(pos)`: Rotates the motor by a relative angle.

## Example

```python
from kbench import Newport
import serial

session = serial.Serial("/dev/ttyUSB1", 921600, timeout=0.1)
newport_motor = Newport(session)
newport_motor.set(45)  # Rotate to 45 degrees
current_angle = newport_motor.get()
print(f"Newport motor angle: {current_angle}")
```
