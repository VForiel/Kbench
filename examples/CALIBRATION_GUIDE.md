# Architecture Calibration Guide

This guide explains how to use the `calibrate_obs` method for photonic chip architectures, adapted from the [PHISE simulation project](https://github.com/VForiel/PHISE).

## Overview

The `calibrate_obs` method performs systematic phase shifter calibration to optimize the performance of kernel-nulling interferometer architectures. It scans each phase shifter through a full 2π cycle, measures the output response, fits a sinusoidal model, and sets the optimal phase for maximum/minimum transmission as required.

## Supported Architectures

### Architecture 15: Mega Kernel Nuller Reconfig
- **14 phase shifters** (TOPAs: 6, 7, 33, 34, 35, 36, 37, 38, 28, 27, 26, 25, 39, 40)
- **4 inputs** (controlled via DM)
- **7 outputs**: 1 Bright + 6 Darks
  - Kernels computed as K₁ = D₁ - D₂, K₂ = D₃ - D₄, K₃ = D₅ - D₆

#### Calibration Strategy for Arch 15
1. **Bright maximization** with different input pairs:
   - Shifter 2: Inputs 1,2 active
   - Shifter 4: Inputs 3,4 active
   - Shifter 7: Inputs 1,3 active

2. **Dark pair maximization**:
   - Shifter 8: Inputs 1,4 active → maximize D₁ + D₂

3. **Kernel minimization** (input 1 only):
   - Shifter 11: minimize K₁
   - Shifter 13: minimize K₂
   - Shifter 14: minimize K₃

### Architecture 6: 4-Port MMI Active
- **4 phase shifters** (TOPAs: 17, 18, 19, 20)
- **4 inputs** (controlled via DM)
- **4 outputs**

#### Calibration Strategies for Arch 6

**Method 1: Standard Calibration**
- All inputs active
- Each shifter independently optimizes its corresponding output
- Goal: Maximize throughput on all outputs

**Method 2: Nulling Calibration**
- All inputs active
- Shifter 1: Maximize bright port (e.g., output 1)
- Shifter 2: Minimize null port (e.g., output 2)
- Goal: Create high-contrast nulling pattern

## Usage

### Basic Example

```python
from phobos import DM
from phobos.classes.cred3 import Cred3
from phobos.classes.archs.arch_15 import Arch15

# Initialize hardware
dm = DM()
camera = Cred3()
arch = Arch15()

# Define output positions (measured from your setup)
crop_centers = [
    [100, 100],  # Bright
    [200, 100],  # Dark 1
    [300, 100],  # Dark 2
    [100, 200],  # Dark 3
    [200, 200],  # Dark 4
    [300, 200],  # Dark 5
    [100, 300],  # Dark 6
]

# Run calibration
arch.calibrate_obs(
    dm_object=dm,
    cred3_object=camera,
    crop_centers=crop_centers,
    n=1000,           # Phase samples per scan
    n_averages=10,    # Frames to average
    plot=True,        # Show results
    save_as="calibration_results.png"
)
```

### Architecture 6 with Nulling

```python
from phobos.classes.archs.arch_6 import Arch6

arch = Arch6()

# Standard calibration
arch.calibrate_obs(dm, camera, crop_centers, plot=True)

# Or nulling calibration
arch.calibrate_nulling(
    dm, camera, crop_centers,
    bright_output_idx=0,  # Maximize this output
    null_output_idx=1,    # Minimize this output
    plot=True
)
```

### Command-Line Usage

```bash
# Quick hardware test
python examples/calibrate_architectures.py --test

# Calibrate Architecture 6
python examples/calibrate_architectures.py --arch 6

# Calibrate Architecture 15
python examples/calibrate_architectures.py --arch 15

# Calibrate both
python examples/calibrate_architectures.py --arch all
```

## Parameters

### Common Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dm_object` | DM | required | Deformable mirror for input control |
| `cred3_object` | Cred3 | required | Camera for flux measurements |
| `crop_centers` | array-like | required | Output spot positions (7 for Arch15, 4 for Arch6) |
| `crop_sizes` | int | 10 | Crop window size around each spot |
| `n` | int | 1000 | Number of phase samples per scan |
| `n_averages` | int | 10 | Frames to average per phase point |
| `plot` | bool | False | Show calibration plots |
| `figsize` | tuple | varies | Figure size for plots |
| `save_as` | str | None | Path to save plot |

### Architecture 6 Nulling Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bright_output_idx` | int | 0 | Output to maximize |
| `null_output_idx` | int | 1 | Output to minimize |

## Output Interpretation

### Calibration Plots

Each subplot shows:
- **Blue dots**: Measured flux vs phase shift
- **Orange curve**: Fitted sinusoidal model
- **Black dashed line**: Optimal phase position

### Success Criteria

✅ **Good calibration**:
- Clear sinusoidal pattern in measured data
- Fit curve closely matches data points
- Optimal phase set at maximum/minimum as intended

⚠️ **Warning signs**:
- Noisy or non-sinusoidal data → Check alignment or averaging
- Flat response → Wrong shifter/output mapping or no light
- Phase drift → Thermal instability or vibrations

## Hardware Requirements

1. **DM (Deformable Mirror)**:
   - Used to block/unblock specific inputs
   - Must support `max()`, `off()`, and `max([1,2,...])` methods

2. **Cred3 Camera**:
   - Must provide `get_outputs(crop_centers, crop_sizes)` method
   - Returns flux array for specified output spots

3. **XPOW Controller**:
   - Connected and configured for phase shifter control
   - PhaseShifter instances must support `set_phase()` and `get_phase()`

4. **Optical Alignment**:
   - Output spots clearly visible on camera
   - Accurate crop center positions measured
   - Sufficient flux for reliable measurements

## Troubleshooting

### Problem: Flat or noisy calibration curves

**Solution**:
- Increase `n_averages` (try 20-50)
- Check optical alignment
- Verify output spot positions in `crop_centers`
- Ensure sufficient input flux

### Problem: Calibration fails with errors

**Solution**:
- Check hardware connections (DM, camera, XPOW)
- Verify `crop_centers` has correct number of outputs
- Ensure all inputs/shifters are functional
- Check for error messages in terminal

### Problem: Optimal phases don't improve performance

**Solution**:
- Verify input blocking patterns match expectations
- Check that correct outputs are being measured
- Ensure shifter-to-output mapping is correct
- Consider thermal drift (recalibrate if needed)

## Differences from PHISE Simulation

| Aspect | PHISE (Simulation) | PHOBos (Hardware) |
|--------|-------------------|-------------------|
| **Input control** | `chip.input_attenuation` array | DM `max([...])` method |
| **Phase units** | Length units (with wavelength) | Radians (via `set_phase()`) |
| **Flux measurement** | `self.observe()` method | Camera `get_outputs()` |
| **Output processing** | `chip.process_outputs()` | Kernel computed from Dark pairs |
| **Averaging** | Single observation | Multiple frame averaging |

## References

- Original PHISE implementation: [context.py#L867](https://github.com/VForiel/PHISE/blob/main/src/phise/classes/context.py#L867)
- PHOBos documentation: [docs/](../docs/)
- Architecture details: [bench_overview.md](../docs/bench_overview.md)

## License

This code is adapted from the PHISE project and follows the same license terms.
