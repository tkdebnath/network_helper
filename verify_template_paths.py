import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tasks import upgrade_task
from tasks import upgrade_task_manual_trigger

print("Modules imported successfully.")

# Verify path logic manually
tasks_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")
template_dir = os.path.join(tasks_dir, "templates")

files_to_check = ["ios_download.j2", "ios_file_install.j2"]

for f in files_to_check:
    path = os.path.join(template_dir, f)
    if os.path.exists(path):
        print(f"Verified: {path} exists.")
    else:
        print(f"FAILED: {path} does not exist.")
