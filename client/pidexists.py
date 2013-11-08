"""Cross-platform abstraction for checking if a process ID exists."""

import errno
import os

imported_windll_kernel32 = False

try:
    # Win32-based operating systems
    from ctypes import windll
    if 'kernel32' not in dir(windll):
        raise ImportError("ctypes.windll does not contain kernel32 object")
    imported_windll_kernel32 = True
except ImportError:
    if os.name != 'posix':
        raise ImportError("no implementation could be imported")


def _pid_exists_win32(pid):
    process = windll.kernel32.OpenProcess(0x100000, False, pid)
    if process != 0:
        windll.kernel32.CloseHandle(process)
        return True
    else:
        return False


def _pid_exists_posix(pid):
    try:
        os.kill(pid, 0)
    except OSError, e:
        return e.errno == errno.EPERM

    return True


def pid_exists(*args, **kwargs):
    """Return True if pid exists in the current process table."""
    if imported_windll_kernel32:
        return _pid_exists_win32(*args, **kwargs)
    elif os.name == 'posix':
        return _pid_exists_posix(*args, **kwargs)
