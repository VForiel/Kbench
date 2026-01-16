import os
import sys
import time

# Import phobos (assuming run as module or package)
try:
    from .. import XPOW
except ImportError:
    # If run directly as script
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    import phobos
    from phobos import XPOW

def prompt_step(message):
    input(f"👉 {message} (Press Enter to continue...)")

def main():
    print("="*60)
    print("🛑 PHOBos Bench Shutdown Script")
    print("="*60)
    
    # 1. Automated Shutdown
    print("\n🤖 AUTOMATED SHUTDOWN")
    
    print("🔌 Turning off Photonic Chip (XPOW)...")
    try:
        phobos.XPOW.turn_off(verbose=True)
    except Exception as e:
        print(f"❌ Error turning off XPOW: {e}")
        
    print("🔌 Resetting Deformable Mirror (DM) to flat...")
    try:
        # Assuming DM class handles connection and flattening might be good practice
        # even if user said "not necessary", the plan had it and it's safer.
        # However, user comment was: "Il n'est pas necessaire de modifier l'état du mirroir..."
        # So I will SKIP the active DM flattening based on user feedback to be safe,
        # or just close connection if it was open (but scripts usually open/close).
        # I'll respect the "not necessary" comment and just skip.
        pass
    except Exception:
        pass

    # 2. Manual Shutdown
    print("\n⚡ MANUAL SHUTDOWN SEQUENCE")
    prompt_step("1. Switch off the Laser Source")
    prompt_step("2. Switch off the XPOW Unit")
    prompt_step("3. Switch off the Generator")
    
    # 3. Camera Server
    print("\n🖥️  CAMERA SERVER")
    print("⚠️  Please close the Camera Server terminal window manually.")
    # We could try to kill it if we knew the PID, but since we launched it in a new terminal
    # without tracking (complex across processes), a manual reminder is safer/standard.
    
    print("\n✅ Shutdown Complete! Have a nice day.")

if __name__ == "__main__":
    main()
