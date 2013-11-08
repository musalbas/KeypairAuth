"""Abstractions for getting OS-specific directories.

Note: at present this module is only designed for usage by wxPython
applications and therefore relies on wxPython. In the future this module will
be updated to use the core operating system APIs instead, to allow support for
non-wxPython applications.

"""

import wx


def get_documents_dir():
    """Return the directory containing the current user's documents."""
    return wx.StandardPaths.Get().GetDocumentsDir()


def get_user_data_dir(appname):
    """Return the directory for the user-dependent application data files.

    Note: at present the appname argument is ignored as wxPython deals with it.
    It is required for future compatibility (see the comment at the top of this
    file). Therefore input appname should be the same as the wx.app AppName to
    ensure future compatibility.

    """
    return wx.StandardPaths.Get().GetUserDataDir()
