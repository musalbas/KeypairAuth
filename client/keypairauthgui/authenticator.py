"""Application (invoked by URI) for authenticating to a web application using a
keypair."""

from urlparse import urlparse

import wx

from keypairauthclient import authengine
from keypairauthgui import keypairmanager


class Authenticator(wx.Frame):
    """GUI where the authentication process is started and managed.

    Arguments:
        auth_url: HTTP(S) URL hosting the server-side authentication
                  application.
        identity_assertion: A string appended to the authentication request,
                            which together will be signed with a private key
                            so the server can verify the signature against a
                            public key.
        mode: Mode of authentication. authengine.MODE_REGISTER sends the server
        a public key in addition to authengine.MODE_AUTH, which sends a plain
        authentication request.

    """

    def __init__(self, config, locale, keypairdb, auth_url, identity_assertion,
                 mode):
        self._config = config
        self._locale = locale
        self._text = locale['text']
        self._keypairdb = keypairdb
        self._auth_url = auth_url
        self._auth_url_components = urlparse(auth_url)
        self._identity_assertion = identity_assertion
        self._mode = mode

        #
        # Firstly verify that this authentication request was invoked by the
        # domain and scheme that is to be authenticated to
        #
#         if not authengine.verify_invocation(self._auth_url,
#                                             self._identity_assertion,
#                                             self._mode):
#             # No verification was received, raise an exception
#             raise_e = Exception("no authentication request invocation " \
#                                 "verification was received for {0}")
#             raise_e.id_string = 'verify_invocation_unverified'
#             raise_e.formatting = (self._auth_url_components[0] + "://"
#                                   + self._auth_url_components[1],)
#             raise raise_e

        #
        # Build keypair selection window
        #

        # Initialise window
        wx.Frame.__init__(self, None, title=self._text['authenticator_title'],
                          size=(350, 400))
        self.Centre()
        self.base_panel = wx.Panel(self)
        self.base_boxsizer = wx.BoxSizer(wx.VERTICAL)
        self.base_panel.SetSizer(self.base_boxsizer)

        # Determine authentication message text
        if (self._mode == authengine.MODE_REGISTER
            and self._auth_url_components[0] != 'https'):
            message_locale = 'authentication_message_register_unencrypted'
        elif (self._mode == authengine.MODE_REGISTER
              and self._auth_url_components[0] == 'https'):
            message_locale = 'authentication_message_register_encrypted'
        elif (self._mode == authengine.MODE_AUTH
              and self._auth_url_components[0] != 'https'):
            message_locale = 'authentication_message_auth_unencrypted'
        elif (self._mode == authengine.MODE_AUTH
              and self._auth_url_components[0] == 'https'):
            message_locale = 'authentication_message_auth_encrypted'
        message_text_format = (self._auth_url_components[1].upper(),
                               self._auth_url_components[0].upper())
        message_text = self._text[message_locale].format(*message_text_format)

        # Display authentication message
        self.message_statictext = wx.StaticText(self.base_panel,
                                                label=message_text)
        self.base_boxsizer.Add(self.message_statictext, flag=wx.TOP | wx.LEFT
                               | wx.RIGHT, border=10)

        # Display keypair list control
        listctrl = keypairmanager.KeypairListCtrl(self._config, self._locale,
                                                  self._keypairdb,
                                                  self.base_panel,
                                                  style=wx.LC_REPORT
                                                  | wx.LC_SINGLE_SEL)
        self.keypairlistctrl = listctrl
        self.base_boxsizer.Add(self.keypairlistctrl, flag=wx.ALL | wx.EXPAND,
                               border=10, proportion=1)

        # Determine "authenticate" button text depending on the authentication
        # mode
        if self._mode == authengine.MODE_REGISTER:
            authenticate_button_text = self._text['register_button']
        elif self._mode == authengine.MODE_AUTH:
            authenticate_button_text = self._text['authenticate_button']

        # Display buttons
        self.buttons_panel = wx.Panel(self.base_panel)
        self.base_boxsizer.Add(self.buttons_panel, flag=wx.BOTTOM | wx.LEFT
                               | wx.RIGHT | wx.EXPAND, border=10)
        self.buttons_boxsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.buttons_panel.SetSizer(self.buttons_boxsizer)
        self.buttons_boxsizer.AddStretchSpacer()
        manage_keypairs_button_text = self._text['manage_keypairs_button']
        manage_keypairs_button = wx.Button(self.buttons_panel, wx.ID_ANY,
                                           label=manage_keypairs_button_text)
        self.manage_keypairs_button = manage_keypairs_button
        self.buttons_boxsizer.Add(self.manage_keypairs_button)
        self.authenticate_button = wx.Button(self.buttons_panel, wx.ID_ANY,
                                             label=authenticate_button_text)
        self.buttons_boxsizer.Add(self.authenticate_button)

        # Bind events
        self.Bind(wx.EVT_SIZE, self.on_size)

        # Show window
        self.Show()

    def on_size(self, event):
        """Handle a window resize, by correcting the window layout where
        necessary."""
        # Rewrap authentication message static text
        self.message_statictext.SetLabel(self.message_statictext.GetLabel()
                                         .replace("\n", " "))
        self.message_statictext.Wrap(self.GetSize()[0] - 2 * 10)
        event.Skip()
