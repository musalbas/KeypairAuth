"""Application (invoked by URI) for authenticating to a web application using a
keypair."""

MODE_REGISTER = 0
MODE_AUTH = 1


class Authenticate():
    """Central class where the authentication process is started and managed.

    Arguments:
        auth_url: HTTP(S) URL hosting the server-side authentication
                  application.
        identity_assertion: A string appended to the authentication request,
                            which together will be signed with a private key
                            so the server can verify the signature against a
                            public key.
        mode: Mode of authentication. MODE_REGISTER sends the server a public
              key in addition.

    """

    def __init__(self, config, locale, keypairdb, auth_url, identity_assertion,
                 mode=MODE_AUTH):
        self._config = config
        self._locale = locale
        self._text = locale['text']
        self._keypairdb = keypairdb
        self._auth_url = auth_url
        self._identity_assertion = identity_assertion
        self._mode = mode
