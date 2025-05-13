# Pupil Mask

The `PupilMask` class is used to control the mask wheel in an optical system. It uses Zaber motors for horizontal and vertical movements, as well as a Newport motor for rotating the wheel.

## Initialization

To initialize an instance of `PupilMask`, you need to specify the serial ports for the Zaber and Newport motors, as well as their reference positions:

```python
from kbench import PupilMask

pupil_mask = PupilMask(
    zaber_port="/dev/ttyUSB0",
    newport_port="/dev/ttyUSB1",
    zaber_h_home=189390,
    zaber_v_home=157602,
    newport_home=56.3
)
```

The default values correspond to those used in the laboratory.

## Attributes

Once initialized, an instance of `PupilMask` contains the following attributes:

- **`zaber_h`** ([`Zaber`](zaber)): Horizontal Zaber motor.
- **`zaber_v`** ([`Zaber`](zaber)): Vertical Zaber motor.
- **`newport`** ([`Newport`](newport)): Newport motor for rotating the mask wheel.
- **`zaber_h_home`** (`int`): Reference position for the horizontal Zaber motor.
- **`zaber_v_home`** (`int`): Reference position for the vertical Zaber motor.
- **`newport_home`** (`float`): Reference position for the Newport motor.

## Methods

### `move_right(pos, abs=False)`
Moves the mask to the right by a certain number of steps. If `abs=True`, the movement is absolute.

### `move_up(pos, abs=False)`
Moves the mask up by a certain number of steps. If `abs=True`, the movement is absolute.

### `rotate_clockwise(pos, abs=False)`
Rotates the mask wheel clockwise by a certain number of degrees. If `abs=True`, the movement is absolute.

Alias: `rotate(pos, abs=False)`

### `apply_mask(mask)`
Positions the mask wheel to the specified mask (by its number).

### `get_pos()`
Returns the current position of the Zaber motors (horizontal and vertical).

### `reset()`
Resets the mask wheel to the reference position (4 vertical holes).

## Example Usage

```python
from kbench import PupilMask

pupil_mask = PupilMask(
    zaber_port="/dev/ttyUSB0",
    newport_port="/dev/ttyUSB1",
    zaber_h_home=189390,
    zaber_v_home=157602,
    newport_home=56.3
)

# Move the mask to the right by 100 steps
pupil_mask.move_right(100)

# Move the mask up by 50 steps
pupil_mask.move_up(50)

# Rotate the wheel to apply mask #2
pupil_mask.aplly_mask(2)

# Get the current position
position = pupil_mask.get_pos()
print(f"Current position: {position}")

# Reset the mask wheel
pupil_mask.reset()
```

```{toctree}
:hidden:
:maxdepth: 1

zaber
newport
```