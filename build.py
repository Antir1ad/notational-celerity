#!/usr/bin/env python3
"""
Build script for Notational Celerity
Creates platform-specific executables using PyInstaller
"""

import os
import sys
import subprocess
import platform

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build_executable():
    """Build the executable using PyInstaller"""
    print("Building executable...")
    
    # Platform-specific options
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        cmd = [
            "pyinstaller",
            "--onefile",
            "--windowed",
            "--name=Notational Celerity",
            "--icon=icon.icns" if os.path.exists("icon.icns") else "",
            "main.py"
        ]
    elif system == "windows":  # "that" OS
        cmd = [
            "pyinstaller",
            "--onefile",
            "--windowed",
            "--name=Notational Celerity",
            "--icon=icon.ico" if os.path.exists("icon.ico") else "",
            "main.py"
        ]
    else:  # UNIX / GNU/Linux
        cmd = [
            "pyinstaller",
            "--onefile",
            "--name=notational-celerity",
            "--icon=icon.png" if os.path.exists("icon.png") else "",
            "main.py"
        ]
    
    # Remove empty strings from command
    cmd = [arg for arg in cmd if arg]
    
    subprocess.check_call(cmd)
    print(f"Build complete! Executable created in dist/ directory")

def clean_build():
    """Clean build artifacts"""
    print("Cleaning build artifacts...")
    if os.path.exists("build"):
        import shutil
        shutil.rmtree("build")
    if os.path.exists("dist"):
        import shutil
        shutil.rmtree("dist")
    if os.path.exists("Notational Celerity.spec"):
        os.remove("Notational Celerity.spec")
    if os.path.exists("notational-celerity.spec"):
        os.remove("notational-celerity.spec")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean_build()
    else:
        try:
            install_dependencies()
            build_executable()
        except subprocess.CalledProcessError as e:
            print(f"Build failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            sys.exit(1) 