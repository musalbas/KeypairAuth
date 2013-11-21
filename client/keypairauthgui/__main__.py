"""Application entry point."""

import sys

from keypairauthgui.application import Application

app = Application(cl_args=sys.argv)
app.MainLoop()
