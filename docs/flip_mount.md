# Flip Mount

```{eval-rst}
.. autoclass:: phobos.FlipMount
   :members:
   :show-inheritance:
```

## Overview

`FlipMount` controls a Thorlabs MFF101 flip mount with two states:

- `0`: up
- `1`: down

The class exposes methods to read the current state, move to a target state, toggle state, and close the device connection.

## Configuration

The class reads the following configuration keys:

- `flip_mount.port`: serial device path (for example `/dev/ttyUSBFlipMount`)
- `flip_mount.stabilization_time`: wait time (seconds) after each move command

Example configuration:

```yaml
flip_mount:
  port: /dev/ttyUSBFlipMount
  stabilization_time: 0.5
```

## Notes

- Positions are validated and must be either `0` or `1`.
- `move_to_position` waits for `stabilization_time` before reading back and printing the final state.
