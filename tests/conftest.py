"""
Pytest configuration for Miolingo tests.

Adds src/ to the import path so tests can import app modules directly.
"""

import sys
from pathlib import Path

# Add src/ to path so we can import modules without installing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
