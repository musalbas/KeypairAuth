"""Application (invoked by URI) for authenticating to a web application using a
keypair."""

from urlparse import urlparse

import wx

from keypairauthclient import authengine


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
        if not authengine.verify_invocation(self._auth_url,
                                            self._identity_assertion,
                                            self._mode):
            # No verification was received, raise an exception
            raise_e = Exception("no authentication request invocation " \
                                "verification was received for {0}")
            raise_e.id_string = 'verify_invocation_unverified'
            raise_e.formatting = (self._auth_url_components[0] + "://"
                                  + self._auth_url_components[1],)
            raise raise_e
