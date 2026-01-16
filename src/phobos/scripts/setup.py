import os
import sys
import time
import yaml
import subprocess
import shutil

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'bench.yml')

def recursive_review(config_data, prefix=""):
    """
    Recursively review and update configuration dictionary.
    """
    for key, value in config_data.items():
        current_path = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):
            recursive_review(value, current_path)
        else:
            # Display current value and ask for update
            print(f"   {current_path}: {value}")
            new_val = input(f"   (Press Enter to keep, or type new value): ").strip()
            if new_val:
                # Simple type conversion
                if isinstance(value, bool):
                    config_data[key] = new_val.lower() in ('true', 'yes', '1', 'on')
                elif isinstance(value, int):
                    try:
                        config_data[key] = int(new_val)
                    except ValueError:
                        print("   ⚠️ Invalid integer, keeping original value.")
                elif isinstance(value, float):
                    try:
                        config_data[key] = float(new_val)
                    except ValueError:
                        print("   ⚠️ Invalid float, keeping original value.")
                elif isinstance(value, list):
                    # Lists are hard to parse interactively safely without complexity
                    # For now, treat as string eval or skip
                    try:
                        # rigorous list parsing is risky, maybe just warn or eval
                        # let's try json/ast parsing if user insists, but for now warning
                        import ast
                        config_data[key] = ast.literal_eval(new_val)
                    except:
                        print("   ⚠️ Could not parse list, keeping original value.")
                else:
                    config_data[key] = new_val

def load_or_create_config():
    import phobos
    default_config = {
        'hardware': {
            'dm': {
                'serial_number': "27BW007#051",
                'config_path': "./config/DM/DM_config.json",
                'stabilization_time': 0.001,
                'injection_segments': [138, 137, 136, 135]
            },
            'camera': {
                'img_shm_path': "/dev/shm/cred1.im.shm",
                'dark_shm_path': "/dev/shm/cred3_dark.im.shm",
                'semid': 0,
                'use_dark': True,
                'output_centers': [[0, 0], [0, 0], [0, 0], [0, 0]],
                'output_sizes': 10,
                'bulk_center': [0, 0],
                'bulk_size': 10
            },
            'pupil_mask': {
                'zaber_port': "/dev/ttyUSBzaber",
                'newport_port': "/dev/ttyUSBnewport",
                'zaber_h_home': 188490,
                'zaber_v_home': 154402,
                'newport_home': 56.15
            },
            'filter_wheel': {
                'port': "/dev/ttyUSBthorlabs"
            },
            'photonic_chip': {
                'driver_port_match': "2341:8036",
                'arch': 6,
                'bright_output': 2
            }
        }
    }

    config_exists = os.path.exists(CONFIG_PATH)
    should_review = True
    
    if config_exists:
        print(f"✅ Found configuration file: {CONFIG_PATH}")
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
            
        # Ask if user wants to review (Default: No)
        ans = input("🧐 Review configuration? (y/N): ").strip().lower()
        should_review = ans in ('y', 'yes', 'true', '1')
        
    else:
        print(f"⚠️ Configuration file not found at {CONFIG_PATH}")
        print("🔧 Creating default configuration...")
        config = default_config
        # New config -> Force review (or default Yes)
        should_review = True
    
    # Review process
    if should_review:
        print("\n🧐 Reviewing Configuration:")
        print("   Please confirm or modify each setting.")
        recursive_review(config)
    
    # Save updated config
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    # Reload config in phobos to ensure singletons picking it up see the new values
    print("🔄 Reloading configuration...")
    phobos.config.reload()
    
    print(f"✅ Configuration verified/saved: {CONFIG_PATH}")
    return config

def prompt_step(message):
    input(f"👉 {message} (Press Enter to continue...)")

def launch_camera_server():
    print("🚀 Launching Camera Server...")
    
    cmd = "cd ~/Progs/repos/dcs/asgard-cred1-server && /opt/EDTpdv/initcam -f cred3_edt_config.cfg && ./asgard_cam_server"
    
    try:
        subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f'{cmd}; exec bash'])
        print("✅ Camera server terminal launched.")
        return True
    except FileNotFoundError:
        print("⚠️ 'gnome-terminal' not found. Trying 'x-terminal-emulator'...")
        try:
            subprocess.Popen(['x-terminal-emulator', '-e', f'bash -c "{cmd}; exec bash"'])
            print("✅ Camera server terminal launched.")
            return True
        except FileNotFoundError:
             print(f"❌ Could not launch terminal automatically. Please run this manually:\n   {cmd}")
             return False

def main():
    import phobos
    print("="*60)
    print("🧪 PHOBos Bench Setup Script")
    print("="*60)
    
    # Backup existing configuration
    print("💾 Backing up current configuration...")
    try:
        phobos.config.backup()
    except Exception as e:
        print(f"⚠️  Backup failed: {e}")

    config = load_or_create_config()
    
    # 1. Preparation & Dark Frames
    print("\n🌑 PREPARATION")
    prompt_step("Turn OFF the lab lights and ensure the Laser Source is OFF")
    
    print("\n📸 Acquiring Dark Frames...")
    try:
        # Instantiate Cred3 (loads from config automatically)
        cam = phobos.Cred3()
        # Force use_dark to False for dark acquisition
        cam.use_dark = False
        cam.take_darks(nb_frames=100) 
        print("✅ Dark frames acquired and saved.")
    except Exception as e:
        print(f"❌ Error acquiring dark frames: {e}")
        print("   (Continuing setup, but check camera...)")

    # 2. Manual Power-Up
    print("\n⚡ MANUAL POWER-UP SEQUENCE")
    print("   Please perform the following steps:")
    print("   1. Switch on the Generator for XPOW")
    print("   2. Switch on the Photonic Chip Driver (XPOW) itself")
    print("   3. Switch on the Laser Source")
    prompt_step("Confirm when ALL steps above are completed")
    
    # 3. Camera Server
    print("\n🖥️  CAMERA SERVER")
    cam_server_launched = launch_camera_server()
    
    if cam_server_launched:
        print("\n✅ Setup Complete! The bench should be ready.")
    else:
        print("\n⚠️  Setup partial. Some automated steps failed.")
        print("👉 Please manually launch the camera server (see above) to finalize setup.")

if __name__ == "__main__":
    import phobos
    main()
