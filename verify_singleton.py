
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

try:
    import phobos
    print("✅ phobos imported")
except ImportError as e:
    print(f"❌ phobos import failed: {e}")
    sys.exit(1)

# Test Config
try:
    print(f"Config camera (cred3) path: {phobos.config.hardware.cred3.img_shm_path}")
    print("✅ Config loaded")
except Exception as e:
    print(f"❌ Config access failed: {e}")

# Test Cred3 Singleton
try:
    from phobos.classes.cred3 import Cred3
    c1 = Cred3()
    c2 = Cred3()
    if c1 is c2:
        print("✅ Cred3 is Singleton")
    else:
        print("❌ Cred3 is NOT Singleton")
except Exception as e:
    print(f"❌ Cred3 instantiation failed: {e}")

# Test Chip Factory and Arch6
try:
    # Ensure config points to Arch 6 for testing
    phobos.config.hardware.photonic_chip.arch = 6
    
    from phobos import chip
    print(f"Chip instance: {chip}")
    print(f"Chip name: {chip.name}")
    
    from phobos.classes.photonic_chip import Chip
    c3 = Chip()
    if chip is c3:
        print("✅ Chip() factory returns singleton")
    else:
        print("❌ Chip() factory returns different instances")
        
    if chip.number == 6:
        print("✅ Correct Arch loaded (Arch6)")
    else:
        print(f"❌ Incorrect Arch loaded: {chip.number}")

except Exception as e:
    print(f"❌ Chip/Arch testing failed: {e}")
    import traceback
    traceback.print_exc()

# Test Utils Singleton directly
try:
    from phobos.classes.utils import Singleton
    print("✅ Singleton metaclass importable")
except ImportError:
    print("❌ Singleton metaclass import failed")

print("Verification complete.")
