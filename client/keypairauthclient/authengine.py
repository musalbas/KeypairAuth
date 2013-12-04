"""Core interface for authentication."""

import json
import time
import thread
from urlparse import urlparse

from cherrypy.wsgiserver import CherryPyWSGIServer

MODE_REGISTER = 'register'
MODE_AUTH = 'auth'


def verify_invocation(*args, **kwargs):
    """Call _VerifyInvocation() and return the result."""
    return _VerifyInvocation(*args, **kwargs).result


class _VerifyInvocation():
    """Verify that an authentication request was invoked by the domain and
    scheme that is to be authenticated to, by waiting for a HTTP JSON request
    to localhost that mirrors the specified authentication parameters and has
    an Origin header that matches the auth_url domain and scheme."""

    def __init__(self, auth_url, identity_assertion, mode, timeout=2.5):
        self._auth_url = auth_url
        self._identity_assertion = identity_assertion
        self._mode = mode

        self._auth_url_components = urlparse(auth_url)

        self._result = None  # the result of the verification

        # Start the WSGI server in a new thread
        thread.start_new_thread(self._wsgi_start, ())

        # Wait until self._result changes or the timeout time passes
        wait_start = time.time()
        while True:
            time.sleep(0.01)
            if (timeout + wait_start) < time.time():
                # Timeout time passed, close the server and stop waiting
                self._wsgi_server.stop()
                break
            elif self._result is not None:
                # Result changed, stop waiting
                break

    @property
    def result(self):
        """Return the result."""
        return self._result

    def _wsgi_app(self, environ, start_response):
        """HTTP request handler for the WSGI server."""
        print environ
        # Set base response headers
        response_headers = [('Server', "KeypairAuth invocation verifier")]

        # Get a list of Accept header entries
        accept_entries = []
        if 'HTTP_ACCEPT' in environ:
            for accept_entry in environ['HTTP_ACCEPT'].split(";"):
                accept_entry = accept_entry.strip()
                accept_entries.append(accept_entry)

        # Get components of the Origin header URL
        if 'HTTP_ORIGIN' in environ:
            origin_components = urlparse(environ['HTTP_ORIGIN'])
        else:
            origin_components = urlparse()

        #
        # Check that the request is valid
        #

        # 404 irrelevant requests
        if (environ['PATH_INFO'] != "/verify_invocation"
            or 'HTTP_HOST' not in environ
            or environ['HTTP_HOST'] != "localhost:2448"):
            start_response('404 Not Found', response_headers)
            return ""

        # Allow POST and OPTIONS requests only
        if environ['REQUEST_METHOD'] not in ('POST', 'OPTIONS'):
            start_response('405 Method Not Allowed', response_headers)
            return ""

        # Allow a content type of application/json only
        if ('CONTENT_TYPE' not in environ
            or environ['CONTENT_TYPE'] != 'application/json'):
            start_response('415 Unsupported Media Type', response_headers)
            return ""

        # Accept header must allow for an application/json response
        if 'application/json' not in accept_entries:
            start_response('406 Not Acceptable', response_headers)
            return ""

        # Handle OPTIONS (and CORS preflight) requests
        if environ['REQUEST_METHOD'] == 'OPTIONS':

            response_headers.append(('Allow', 'POST'))
            response_headers.append(('Access-Control-Allow-Methods', 'POST'))

            if (self._auth_url_components[0] == origin_components[0]
                and self._auth_url_components[1] == origin_components[1]):
                auth_url_root = self._auth_url_components[0] + "://"
                auth_url_root += self._auth_url_components[1]
                response_headers.append('Access-Control-Allow-Origin',
                                        auth_url_root)

            start_response('200 OK', response_headers)
            return ""

        # Try to load the JSON data
        try:
            json_data = json.load(environ['wsgi.input'])
            assert ('auth_url' in json_data
                    and 'identity_assertion' in json_data
                    and 'mode' in json_data)
        except (ValueError, AssertionError):
            # Bad JSON data
            start_response('400 Bad Request', response_headers)
            return ""

        #
        # Check the Origin header domain and scheme against the auth_url
        # domain and scheme, and compare the JSON authentication parameters
        # against the authentication parameters specified to this class to
        # verify the invocation
        #

        # Verify the invocation
        if (origin_components[0] == self._auth_url_components[0]
            and origin_components[1] == self._auth_url_components[1]
            and json_data['auth_url'] == self._auth_url
            and json_data['identity_assertion'] == self._identity_assertion
            and json_data['mode'] == self._mode):
            verify_result = True
        else:
            verify_result = False

        # Update self._result if the verification was successful
        if verify_result:
            self._result = True

        # Return the result of the verification in JSON form
        response_headers.append('Content-Type', 'application/json')
        return json.dumps({"success": verify_result})

    def _wsgi_start(self):
        """Start the WSGI server."""
        self._wsgi_server = CherryPyWSGIServer(('127.0.0.1', 2448),
                                               self._wsgi_app)
        self._wsgi_server.start()
