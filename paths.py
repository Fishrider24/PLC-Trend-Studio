import os
import sys

if getattr(sys, "frozen", False):
    APP_PATH = os.path.dirname(sys.executable)
else:
    APP_PATH = os.path.dirname(os.path.abspath(__file__))

WORKSPACE_PATH = os.path.join(APP_PATH, "Workspaces")
DATA_PATH = os.path.join(APP_PATH, "Data")
REPORT_PATH = os.path.join(APP_PATH, "Reports")
PREVIOUS_TAGS_PATH = os.path.join(APP_PATH, "PreviousTags")

os.makedirs(PREVIOUS_TAGS_PATH, exist_ok=True)
os.makedirs(WORKSPACE_PATH, exist_ok=True)
os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(REPORT_PATH, exist_ok=True)