import subprocess
import sys

print("Installing requirements (skipping anything already installed)...")
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
    check=False,
)
if r.returncode != 0:
    print("Some packages failed to install. The app may still run.")
    print("Tip: pyaudio was already removed from requirements.txt.")
    print("Tip: Microsoft C++ Build Tools are needed for some packages.")

print("Installing Playwright browsers...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=False)

print("")
print("Setup finished. Run 'python main.py' or start_lisa.bat to start Lisa AI.")
