import os
import sys

# Ensure clean state
if "DEVICE_USERNAME" in os.environ:
    del os.environ["DEVICE_USERNAME"]

print(f"Initial DEVICE_USERNAME: {os.getenv('DEVICE_USERNAME')}")

try:
    # This will trigger load_dotenv in app/main.py
    from app import main
except Exception as e:
    print(f"Import failed (expected if dependencies missing, but load_dotenv runs first): {e}")

print(f"Loaded DEVICE_USERNAME: {os.getenv('DEVICE_USERNAME')}")
