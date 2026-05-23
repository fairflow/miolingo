"""Shared pytest configuration for the Miolingo desktop suite.

Forces Qt's offscreen platform so GUI tests run headlessly (CI / cloud) without
a display. Must be set before any Qt import.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
