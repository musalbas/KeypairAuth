"""Application launcher."""

import os
import sys
import thread
import time
import urlparse

from external.configobj import ConfigObj
from keypairauthclient.config import Config
from keypairauthclient.keypairdb import KeypairDB
import osdirs
from pkg_resources import resource_stream
import wx

from keypairauthgui import authenticator
from keypairauthgui import keypairmanager
from keypairauthgui.excepthandler import ExceptHandler

# Configuration specification for default values and data types
CONFIGSPEC = """
[ui]
locale = option('en-int', default='en-int')
[gui]
keypair_files_syncer = integer(default=-1)
"""


class Application():
    """Launch and manage the KeypairAuth GUI application.

    Arguments:
        cl_args: List of command-line arguments.
        name: Unique name for the application.
        config_filename: Path to configuration INI file.
        my_keypairs_dir: Default/main keypair storage directory. This directory
                         is watched for additions and deletions. Set to False
                         to disable, or None to allow the application to choose
                         a sensible directory.
        graphical_except: If set to True, uncaught exceptions are shown as
                          message dialogs.
        config_sync_interval: Seconds to wait in between synchronising the
                              configuration.

    """

    def __init__(self, cl_args=[], name="KeypairAuth", config_filename=None,
                 my_keypairs_dir=None, graphical_except=True,
                 config_sync_interval=1):
        # Initialise wxWidgets application
        self._wxapp = wx.App(redirect=False)
        self._wxapp.SetAppName(name)

        # Prepare graphical uncaught exceptions handler if enabled
        if graphical_except:
            self._excepthandler = ExceptHandler()
            sys.excepthook = self._excepthandler.excepthook
        else:
            self._excepthandler = None

        # Load user configuration
        if config_filename is None:
            user_data_dir = osdirs.get_user_data_dir(self._wxapp.GetAppName())
            config_filename = os.path.join(user_data_dir, "userconfig.ini")
        self._config = Config(filename=config_filename,
                              configspec_string=CONFIGSPEC)

        # Load locale
        locale_stream = resource_stream('keypairauthgui.res.locales',
                                        self._config['ui']['locale'] + ".ini")
        self._locale = ConfigObj(infile=locale_stream)
        if self._excepthandler is not None:
            self._excepthandler.locale = self._locale

        # Set my_keypairs_dir if unspecified
        if my_keypairs_dir is None:
            # Determine a sensible directory in the OS 'My Documents' folder
            my_keypairs_dir = os.path.join(osdirs.get_documents_dir(),
                                           "My Keypairs")
        elif not my_keypairs_dir:
            # Disable the My Keypairs directory
            my_keypairs_dir = None

        # Load keypair database
        self._keypairdb = KeypairDB(self._config,
                                    my_keypairs_dir=my_keypairs_dir)

        # Start the needed application
        if len(cl_args) != 2:
            # No command-line arguments; start the keypair manager
            self._main_window = self._start_keypairmanager()
        else:
            # Possible command-line arguments for authentication; parse the
            # arguments and start the authenticator
            auth_query = urlparse.parse_qs(cl_args[1])

            try:
                auth_url = auth_query['auth_url'][0]
            except KeyError:
                raise_e = ValueError("authentication URL not specified")
                raise_e.id_string = 'auth_url_unspecified'
                raise raise_e

            try:
                auth_identity_assertion = auth_query['identity_assertion'][0]
            except KeyError:
                raise_e = ValueError("identity assertion string not specified")
                raise_e.id_string = 'identity_assertion_unspecified'
                raise raise_e

            try:
                auth_mode = auth_query['mode'][0]
            except KeyError:
                raise_e = ValueError("authentication mode not specified")
                raise_e.id_string = 'auth_mode_unspecified'
                raise raise_e

            window = self._start_authenticator(auth_url,
                                               auth_identity_assertion,
                                               auth_mode)
            self._main_window = window

        # Update the parent window for the exceptions handler's message dialogs
        if self._excepthandler is not None:
            self._excepthandler.parent = self._main_window

        # Start thread to synchronise the configuration when its file is
        # modified
        thread.start_new_thread(self._config_sync_loop,
                                (config_sync_interval,))

    def _config_sync_loop(self, interval):
        """Periodically synchronise the configuration after every interval."""
        while True:

            time.sleep(interval)

            try:
                synced = self._config.sync()
            except OSError:
                synced = False

            if synced:
                try:
                    self._main_window.config_sync_callback()
                except AttributeError:
                    pass

            try:
                self._main_window.config_sync_interval_callback()
            except AttributeError:
                pass

    def _start_authenticator(self, auth_url, identity_assertion, mode):
        """Start the authentication application."""
        return authenticator.Authenticator(self._config, self._locale,
                                          self._keypairdb, auth_url,
                                          identity_assertion, mode)

    def _start_keypairmanager(self):
        """Start the keypair management application."""
        return keypairmanager.MainWindow(self._config, self._locale,
                                         self._keypairdb)

    def MainLoop(self):
        self._wxapp.MainLoop()
