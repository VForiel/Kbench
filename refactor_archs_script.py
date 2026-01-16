
import os
import re
import glob

ARCH_DIR = r"d:\PHOBos\src\phobos\classes\archs"

def refactor_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip if already refactored
    if "metaclass=Singleton" in content and "_Arch as Arch" in content:
        print(f"Skipping {filepath} (already refactored)")
        return

    original_content = content

    # 1. Update imports
    # Replace 'from ..photonic_chip import Arch' with '_Arch as Arch' and add Singleton import
    if "from ..photonic_chip import Arch" in content:
        content = content.replace(
            "from ..photonic_chip import Arch",
            "from ..photonic_chip import _Arch as Arch\nfrom ..utils import Singleton"
        )
    else:
        print(f"⚠️ 'from ..photonic_chip import Arch' not found in {filepath}")
        # Try to find where to insert Singleton import
        if "from ..utils import Singleton" not in content:
             content = "from ..utils import Singleton\n" + content

    # 2. Update Class Definition
    # Regex to find 'class ArchN(Arch):' and add metaclass
    # Assumption: class ArchX(Arch):
    # We want: class ArchX(Arch, metaclass=Singleton):
    
    pattern = r"class (Arch\d+)\(Arch\):"
    replacement = r"class \1(Arch, metaclass=Singleton):"
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content == original_content:
        print(f"⚠️ No class definition change in {filepath}")
    else:
        print(f"✅ Refactoring {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

def main():
    files = glob.glob(os.path.join(ARCH_DIR, "arch_*.py"))
    print(f"Found {len(files)} arch files.")
    for f in files:
        refactor_file(f)

if __name__ == "__main__":
    main()
