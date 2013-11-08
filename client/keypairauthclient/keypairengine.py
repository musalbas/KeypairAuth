"""Core cryptography interface for keypairs."""

import base64
import hashlib
import os
import stat

from Crypto.PublicKey import RSA


def fingerprint(keypair):
    """Return the SSH-format fingerprint of a keypair's public key."""
    openssh_export = keypair.publickey().exportKey(format='OpenSSH')
    raw_key = base64.b64decode(openssh_export.split(" ")[1])
    md5_fingerprint = hashlib.md5(raw_key).hexdigest()
    return ":".join(a + b for a, b in zip(md5_fingerprint[::2],
                                          md5_fingerprint[1::2]))


def generate():
    """Return a fresh RSA key(pair) object."""
    return RSA.generate(2048)


def is_pem_passphrased(filename):
    """Return True if the PEM file contains a private key encrypted with a
    passphrase."""
    file_handle = open(filename, 'r')
    reading_private_key = False

    for line in file_handle:
        if (line.startswith("-----BEGIN ")
              and line.endswith(" PRIVATE KEY-----")):
            reading_private_key = True
        elif (line.startswith("-----END ")
              and line.endswith(" PRIVATE KEY-----")):
            break
        elif (reading_private_key
            and line.startswith("Proc-Type: ")
            and line.endswith(",ENCRYPTED\n")
            and line[11].isdigit()):
            file_handle.close()
            return True

    file_handle.close()
    return False


def read(filename, passphrase=None):
    """Import a keypair from file."""
    file_handle = open(filename, mode='r')
    keypair = RSA.importKey(file_handle.read(), passphrase=passphrase)
    file_handle.close()

    # Sanity check: keypair must have a private component
    if not keypair.has_private():
        raise ValueError("keypair must have a private component")

    return keypair


def save(keypair, filename, passphrase=None):
    """Save a keypair's private key as a PEM file."""
    # Sanity check: keypair must have a private component
    if not keypair.has_private():
        raise ValueError("keypair must have a private component")

    # Open file
    file_handle = open(filename, mode='w')

    # Set file permissions so that it can only be read and written to by the
    # owner if the system supports it
    try:
        os.fchmod(filename, stat.S_IRUSR | stat.S_IWUSR)
    except AttributeError:
        pass

    # Export and write private key
    file_handle.write(keypair.exportKey(passphrase=passphrase))

    # Close file
    file_handle.close()
