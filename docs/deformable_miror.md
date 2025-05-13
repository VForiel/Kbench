# DM

The `DM` class represents a deformable mirror in the optical system. It provides methods to control the mirror's segments by setting global values for piston, tip, and tilt.

## Methods

### `__init__()`
Initialize the deformable mirror by opening a connection to the hardware and loading a calibration file.

**Parameters**  
None

**Returns**  
None

---

### `set_piston(value)`
Set a global piston value for all the mirror's segments.

**Parameters**  
- **value** (`float`) – Piston value to apply (in user units).

**Returns**  
None

---

### `set_tip(value)`
Set a global tip value for all the mirror's segments.

**Parameters**  
- **value** (`float`) – Tip value to apply (in user units).

**Returns**  
None

---

### `set_tilt(value)`
Set a global tilt value for all the mirror's segments.

**Parameters**  
- **value** (`float`) – Tilt value to apply (in user units).

**Returns**  
None

```{toctree}
: maxdepth: 1
: hidden:

segment
```