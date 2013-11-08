"""Cross-platform abstractions for dealing with storage drives."""

import os

imported_windll_kernel32 = False

try:
    # Win32-based operating systems
    from ctypes import windll
    if 'kernel32' not in dir(windll):
        raise ImportError("ctypes.windll does not contain kernel32 object")
    imported_windll_kernel32 = True
except ImportError:
    raise ImportError("no implementation could be imported")


def _is_interchangeable_win32(filename):
    drive = os.path.splitdrive(filename)[0] + '\\'
    drive = unicode(drive)
    drive_type = windll.kernel32.GetDriveTypeW(drive)
    if drive_type in (2, 5):
        return True
    elif drive_type == 1:
        raise ValueError("specified drive root path is invalid")
    else:
        return False


def is_interchangeable(*args, **kwargs):
    """Return True if filename is on removable media or a CD."""
    if imported_windll_kernel32:
        return _is_interchangeable_win32(*args, **kwargs)
