"""
Industry Standards Module
Contains lookup tables and constants from IPC-2221A, IEC 62368-1, and other standards
"""

from .ipc_2221a import IPC2221A
from .iec_62368 import IEC62368
from .e_series import ESeries
from .mlcc_derating import MLCCDerating
from .current_capacity import CurrentCapacity
from .bus_standards import BusStandards

__all__ = [
    'IPC2221A',
    'IEC62368', 
    'ESeries',
    'MLCCDerating',
    'CurrentCapacity',
    'BusStandards'
]
