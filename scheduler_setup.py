import subprocess
import os

TASK_NAME = "MandiBot_Daily"
PYTHON_PATH = r"C:\mandi_bot\venv\Scripts\python.exe"
SCRIPT_PATH = r"C:\mandi_bot\main.py"
LOG_PATH = r"C:\mandi_bot\logs\mandi_bot.log"

os.makedirs(r"C:\mandi_bot\logs", exist_ok=True)

cmd = [
    "schtasks", "/create",
    "/tn", TASK_NAME,
    "/tr", f"{PYTHON_PATH} {SCRIPT_PATH} >> {LOG_PATH} 2>&1",
    "/sc", "DAILY",
    "/st", "06:30",
    "/f"
]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode == 0:
    print(f"[SCHEDULER] Task '{TASK_NAME}' created — runs daily at 6:30 AM")
else:
    print(f"[SCHEDULER ERROR] {result.stderr}")