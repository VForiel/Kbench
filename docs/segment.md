# Segment Class

The `Segment` class represents an individual segment of the deformable mirror. It allows manipulating the piston, tip, and tilt values for each segment.

## Methods

### `__init__(dm: DM, id: int)`
- **Description**: Initializes a segment with a reference to the parent deformable mirror and a unique identifier.
- **Parameters**:
  - `dm`: Instance of the `DM` class to which this segment belongs.
  - `id`: Unique identifier of the segment.
- **Returns**: None.

---

### `get_piston()`
- **Description**: Retrieves the current piston value for this segment.
- **Parameters**: None.
- **Returns**: Not implemented (prints a message).

---

### `set_piston(value)`
- **Description**: Sets the piston value for this segment.
- **Parameters**:
  - `value`: Piston value to apply (in user units).
- **Returns**: Error status code.

---

### `get_tip()`
- **Description**: Retrieves the current tip value for this segment.
- **Parameters**: None.
- **Returns**: Not implemented (prints a message).

---

### `set_tip(value)`
- **Description**: Sets the tip value for this segment.
- **Parameters**:
  - `value`: Tip value to apply (in user units).
- **Returns**: Error status code.

---

### `get_tilt()`
- **Description**: Retrieves the current tilt value for this segment.
- **Parameters**: None.
- **Returns**: Not implemented (prints a message).

---

### `set_tilt(value)`
- **Description**: Sets the tilt value for this segment.
- **Parameters**:
  - `value`: Tilt value to apply (in user units).
- **Returns**: Error status code.

---

### `ptt_to_dac(piston, tip, tilt)`
- **Description**: Converts piston, tip, and tilt values to DAC values.
- **Parameters**:
  - `piston`: Piston value.
  - `tip`: Tip value.
  - `tilt`: Tilt value.
- **Returns**: Not implemented (raises an exception).
