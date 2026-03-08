"""pytest konfiguratsioon OpenClaw testidele."""
import sys
import os

# Lisa state/ kataloog sys.path'i kõigile testidele
STATE_DIR = os.path.join(os.path.dirname(__file__), "..", "state")
if STATE_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(STATE_DIR))
