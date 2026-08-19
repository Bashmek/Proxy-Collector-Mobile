"""Скрипт для создания современного .exe файла."""
import subprocess
import sys
import os

def main():
    print("=" * 70)
    print("Building Modern Soft-Dark Proxy Collector App...")
    print("=" * 70)
    
    print("\n1. Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    print("\n2. Building executable...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "ProxyCollector",
        "--icon", "icon.png",           # ← Иконка для .exe файла
        "--add-data", "icon.png;.",     # ← Включаем иконку внутрь сборки
        "--collect-all", "ttkbootstrap",
        "--collect-all", "PIL",
        "--hidden-import", "cryptography",
        "--clean",
        "app.py"
    ]
    
    subprocess.check_call(cmd)
    
    print("\n" + "=" * 70)
    print("✅ Build complete!")
    print("📁 Executable location: dist/ProxyCollector.exe")
    print("=" * 70)

if __name__ == "__main__":
    main()