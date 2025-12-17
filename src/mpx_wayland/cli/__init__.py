"""
CLI module for Wayland Multi-Pointer.

Provides the mpx-ctl command-line tool.
"""

from .mpx_ctl import MPXController, main

__all__ = ["MPXController", "main"]
