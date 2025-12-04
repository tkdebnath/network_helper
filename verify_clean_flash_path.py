import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tasks import upgrade_task

print("Module imported successfully.")

# Verify path logic manually
tasks_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")
template_dir = os.path.join(tasks_dir, "templates")
applet_path = os.path.join(template_dir, "event_applet_clean_flash.txt")

if os.path.exists(applet_path):
    print(f"Verified: {applet_path} exists.")
else:
    print(f"FAILED: {applet_path} does not exist.")
