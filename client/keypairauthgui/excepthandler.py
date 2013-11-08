"""Uncaught exceptions handler."""

import wx


class ExceptHandler(object):
    """Handle uncaught exceptions graphically by showing message dialogs."""

    def __init__(self, locale=None, parent=None):
        self._locale = locale
        if locale is not None:
            self._text = locale['text']
        self._parent = parent  # parent window of the message dialogs

    @property
    def locale(self):
        return self._locale

    @locale.setter
    def locale(self, value):
        self._locale = value
        self._text = value['text']

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value

    def _show(self, message, caption):
        """Show an error dialog with the specified message and caption."""
        dialog = wx.MessageDialog(self._parent, message, caption=caption,
                                  style=wx.OK | wx.ICON_ERROR)
        dialog.ShowModal()

    def excepthook(self, type_, value, traceback):
        """Replacement for sys.excepthook that displays a message dialog."""
        name = type_.__name__  # get the name of the exception

        # Set dialog message and caption
        if self._locale is None:
            # Set the message and caption to the raw exception type and value
            # by themselves as locale is unknown
            message = name + ": " + str(value) + "."
            caption = name
        else:
            # Locale is known, attempt to translate the message and caption
            try:
                message = self._text[name][value.id]
            except (AttributeError, KeyError):
                try:
                    message = self._text[name][value]
                except KeyError:
                    message = str(value)
            try:
                caption = self._text[name]['__name__']
            except KeyError:
                caption = name

            message = self._text['except_message'].format(caption, message)
            caption = self._text['except_caption'].format(caption)

        # Show message dialog
        self._show(message, caption)
