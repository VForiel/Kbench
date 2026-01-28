#!/usr/bin/env python3
"""
Example script demonstrating the calibrate_obs method for Architecture 15 and 6.

This script shows how to use the calibration methods adapted from the PHISE simulation
project to work with real hardware in the PHOBos optical bench.

Requirements:
- Deformable Mirror (DM) for input control
- Cred3 camera for flux measurements
- Configured XPOW controller for phase shifters
- Properly aligned optical setup with known output positions

Author: Adapted from PHISE project (https://github.com/VForiel/PHISE)
Date: 2025-12-18
"""

import numpy as np
from phobos import DM
from phobos.classes.cred3 import Cred3
from phobos.classes.archs.arch_15 import Arch15
from phobos.classes.archs.arch_6 import Arch6


def calibrate_architecture_15():
    """
    Calibration example for Architecture 15: Mega Kernel Nuller Reconfig.
    
    This architecture has:
    - 14 phase shifters (TOPAs: 6,7,33,34,35,36,37,38,28,27,26,25,39,40)
    - 4 inputs (controlled by DM)
    - 7 outputs: 1 Bright + 6 Darks (3 Kernels computed from Dark pairs)
    """
    
    print("=" * 80)
    print("Architecture 15 Calibration Example")
    print("=" * 80)
    
    # Initialize hardware
    dm = DM()
    camera = Cred3()
    arch = Arch15()
    
    # Define output spot positions on the camera
    # These coordinates must be measured/determined for your specific setup
    crop_centers = [
        [100, 100],  # Bright output
        [200, 100],  # Dark 1
        [300, 100],  # Dark 2
        [100, 200],  # Dark 3
        [200, 200],  # Dark 4
        [300, 200],  # Dark 5
        [100, 300],  # Dark 6
    ]
    
    # Run calibration with plotting
    arch.calibrate_obs(
        dm_object=dm,
        cred3_object=camera,
        crop_centers=crop_centers,
        crop_sizes=10,           # Size of crop window around each spot
        n=1000,                  # Number of phase samples per scan
        n_averages=10,           # Frames to average per phase point
        plot=True,               # Show calibration plots
        figsize=(30, 20),        # Large figure for 7 subplots
        save_as="arch15_calibration.png"  # Save plot
    )
    
    print("\n✅ Architecture 15 calibrated successfully!")
    print("Optimal phase shifter values have been set.")
    print("The system is now configured for kernel-nulling operation.")


def calibrate_architecture_6():
    """
    Calibration example for Architecture 6: 4-Port MMI Active.
    
    This architecture has:
    - 4 phase shifters (TOPAs: 17, 18, 19, 20)
    - 4 inputs (controlled by DM)
    - 4 outputs
    """
    
    print("=" * 80)
    print("Architecture 6 Calibration Example")
    print("=" * 80)
    
    # Initialize hardware
    dm = DM()
    camera = Cred3()
    arch = Arch6()
    
    # Define output spot positions
    crop_centers = [
        [150, 150],  # Output 1
        [250, 150],  # Output 2
        [150, 250],  # Output 3
        [250, 250],  # Output 4
    ]
    
    # Method 1: Standard calibration (maximize all outputs)
    print("\n--- Method 1: Standard Calibration ---")
    arch.calibrate_obs(
        dm_object=dm,
        cred3_object=camera,
        crop_centers=crop_centers,
        crop_sizes=10,
        n=1000,
        n_averages=10,
        plot=True,
        figsize=(16, 12),
        save_as="arch6_standard_calibration.png"
    )
    
    # Method 2: Nulling calibration (maximize one output, minimize another)
    print("\n--- Method 2: Nulling Calibration ---")
    arch.calibrate_nulling(
        dm_object=dm,
        cred3_object=camera,
        crop_centers=crop_centers,
        bright_output_idx=0,  # Maximize output 1
        null_output_idx=1,    # Minimize output 2
        crop_sizes=10,
        n=500,
        n_averages=10,
        plot=True,
        save_as="arch6_nulling_calibration.png"
    )
    
    print("\n✅ Architecture 6 calibrated successfully!")


def quick_test():
    """
    Quick test to verify hardware connections without full calibration.
    """
    
    print("=" * 80)
    print("Quick Hardware Test")
    print("=" * 80)
    
    # Initialize
    dm = DM()
    camera = Cred3()
    arch6 = Arch6()
    
    # Test DM control
    print("\n1. Testing DM input control...")
    dm.max()  # All inputs on
    print("   ✅ All inputs activated")
    
    dm.off()  # All inputs off
    print("   ✅ All inputs blocked")
    
    dm.max([1, 3])  # Only inputs 1 and 3
    print("   ✅ Selective inputs activated")
    
    # Test camera
    print("\n2. Testing camera acquisition...")
    frame = camera.get_image()
    print(f"   ✅ Frame captured: shape={frame.shape}, dtype={frame.dtype}")
    
    # Test phase shifters
    print("\n3. Testing phase shifters...")
    for i, channel in enumerate(arch6.channels, start=1):
        channel.set_phase(np.pi / 2)
        phase = channel.get_phase()
        print(f"   ✅ Shifter {i} (channel {channel.channel}): phase={phase:.3f} rad")
    
    # Reset
    arch6.turn_off()
    dm.max()
    
    print("\n✅ Hardware test complete!")


def main():
    """
    Main function to run calibration examples.
    """
    
    import argparse
    
    parser = argparse.ArgumentParser(
    description="Calibrate PHOBos photonic chip architectures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python calibrate_architectures.py --test         # Quick hardware test
  python calibrate_architectures.py --arch 15      # Calibrate Architecture 15
  python calibrate_architectures.py --arch 6       # Calibrate Architecture 6
  python calibrate_architectures.py --arch all     # Calibrate both architectures
        """
    )
    
    parser.add_argument(
        '--arch',
        type=str,
        choices=['6', '15', 'all'],
        help='Architecture to calibrate (6, 15, or all)'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run quick hardware test only'
    )
    
    args = parser.parse_args()
    
    if args.test:
        quick_test()
    elif args.arch == '15':
        calibrate_architecture_15()
    elif args.arch == '6':
        calibrate_architecture_6()
    elif args.arch == 'all':
        calibrate_architecture_6()
        print("\n" + "=" * 80 + "\n")
        calibrate_architecture_15()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
