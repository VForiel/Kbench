# Pupil Mask

The `PupilMask` class allows controlling the mask wheel in an optical system. It uses Zaber motors for horizontal and vertical movements, as well as a Newport motor for wheel rotation.

## Initialization

To initialize a `PupilMask` instance, you need to specify the serial ports for the Zaber and Newport motors, as well as their reference positions:

```python
from kbench.classes.pupil_mask import PupilMask

pupil_mask = PupilMask(
    zaber_port="/dev/ttyUSB0",
    newport_port="/dev/ttyUSB1",
    zaber_h_home=189390,
    zaber_v_home=157602,
    newport_home=56.3
)
```

The default values you find here correspond to the ones used in the lab.

## Main Methods

### `move_right(pos, abs=False)`
Moves the mask to the right by a certain number of steps. If `abs=True`, the movement is absolute.

### `move_up(pos, abs=False)`
Moves the mask upward by a certain number of steps. If `abs=True`, the movement is absolute.

### `rotate_clockwise(pos, abs=False)`
Rotates the mask wheel clockwise by a certain number of degrees. If `abs=True`, the movement is absolute.

Alias: `rotate(pos, abs=False)`

### `aplly_mask(mask)`
Positions the mask wheel to the specified mask (by its number).

### `get_pos()`
Returns the current position of the Zaber motors (horizontal and vertical).

### `reset()`
Resets the mask wheel to the reference position (4 vertical holes).

## Subclasses

### `Zaber`

The `Zaber` class is used to control the Zaber motors for horizontal and vertical movements.

#### Methods

- `get()`: Returns the current position of the motor.
- `set(pos)`: Moves the motor to an absolute position.
- `add(pos)`: Moves the motor by a relative number of steps.

#### Example

```python
zaber_motor = Zaber(session, id=1)
zaber_motor.set(1000)  # Move to position 1000
current_position = zaber_motor.get()
print(f"Zaber motor position: {current_position}")
```

### `Newport`

The `Newport` class is used to control the Newport motor for rotating the mask wheel.

#### Methods

- `get()`: Returns the current angular position of the motor.
- `set(pos)`: Rotates the motor to an absolute angular position.
- `add(pos)`: Rotates the motor by a relative angle.

#### Example

```python
newport_motor = Newport(session)
newport_motor.set(45)  # Rotate to 45 degrees
current_angle = newport_motor.get()
print(f"Newport motor angle: {current_angle}")
```

## Usage Example

```python
# Move the mask to the right by 100 steps
pupil_mask.move_right(100)

# Move the mask upward by 50 steps
pupil_mask.move_up(50)

# Rotate the mask wheel to apply mask #2
pupil_mask.aplly_mask(2)

# Get the current position
position = pupil_mask.get_pos()
print(f"Current position: {position}")

# Reset the mask wheel
pupil_mask.reset()
```

