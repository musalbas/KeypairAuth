"""Keypair database management."""

import binascii
import glob
import os
import stat
import time

try:
    import drives
except ImportError:
    pass
from keypairauthclient import keypairengine


class KeypairDB():
    """A keypair database object for managing (adding, removing, etc)
    keypairs.

    Arguments:
        keypairdb_config: A ConfigObj-based object where the keypair database
                          is held in the 'keypairdb' key.
        my_keypairs_dir: Default/main keypair storage directory. This directory
                         is checked for additions and deletions if
                         sync_my_keypairs_dir is True.
        sync_my_keypairs_dir: See my_keypairs_dir.

    """

    def __init__(self, config, my_keypairs_dir=None,
                 sync_my_keypairs_dir=False):
        self._config = config
        self._my_keypairs_dir = my_keypairs_dir
        self.sync_my_keypairs_dir = sync_my_keypairs_dir

        self._my_keypairs_dir_listing = None
        self._no_sync = []

    @property
    def __iter__(self):
        # Synchronise the keypair database with the My Keypairs directory
        # before returning the iterator
        if self.sync_my_keypairs_dir:
            self._sync_my_keypairs_dir()

        # Return the iterator
        return self._keypairdb_config.__iter__

    @property
    def _keypairdb_config(self):
        return self._config['keypairdb']

    @property
    def _keypairdb_meta_config(self):
        return self._config['keypairdb_meta']

    @property
    def my_keypairs_dir(self):
        """Return the My Keypairs directory, creating it if it doesn't
        exist."""
        if not os.path.isdir(self._my_keypairs_dir):
            # Create directory with permissions that only allow the owner to
            # read and write to it (Unix)
            os.makedirs(self._my_keypairs_dir, mode=stat.S_IRUSR |
                        stat.S_IWUSR | stat.S_IXUSR)

        return self._my_keypairs_dir

    def __getitem__(self, filename):
        """Return a keypair's properties, determining or updating dynamic
        properties as necessary."""
        properties = self._keypairdb_config[filename]
        new_properties = {}

        # Determine keypair name from filename
        new_properties['name'] = os.path.basename(filename)
        new_properties['name'] = os.path.splitext(new_properties['name'])[0]

        # Calculate the difference between the current keypair file
        # modification time and the modification time when it was last checked
        try:
            mtime = os.path.getmtime(filename)
            time_difference = mtime - properties['last_file_check']
            time_difference = round(time_difference, 2)
            new_properties['available'] = True
        except OSError:
            # An example of a legitimate case when this might happen is if the
            # PEM file is stored on removable media, and the media is removed
            time_difference = 0
            new_properties['available'] = False

        #
        # Perform property updates that involve accessing the keypair's PEM
        # file if it has been modified since the last check
        #
        if time_difference != 0:

            # Update last check modification time
            new_properties['last_file_check'] = mtime

            # Is the PEM file on removable media?
            try:
                is_interchangeable = int(drives.is_interchangeable(filename))
            except NameError:
                is_interchangeable = -1
            new_properties['on_interchangeable_storage'] = is_interchangeable

            # Is the private key encrypted with a passphrase?
            is_pem_passphrased = keypairengine.is_pem_passphrased(filename)
            new_properties['passphrased'] = int(is_pem_passphrased)

        # Update the keypair's properties and save the configuration if the new
        # properties are different than the old properties
        updated_properties = properties.dict()
        updated_properties.update(new_properties)
        if properties != updated_properties:
            properties = self._keypairdb_config[filename] = updated_properties
            self._config.save()

        return properties

    def _get_my_keypairs_dir_listing(self):
        return glob.glob(os.path.join(self._my_keypairs_dir, "*"))

    def _sync_my_keypairs_dir(self):
        """Synchronise the keypair database with the My Keypairs directory."""
        new_my_keypairs_dir_listing = self._get_my_keypairs_dir_listing()

        if new_my_keypairs_dir_listing != self._my_keypairs_dir_listing:
            self._my_keypairs_dir_listing = new_my_keypairs_dir_listing

            removed_keypairs = self._keypairdb_meta_config['removed']

            # Additions
            for filename in new_my_keypairs_dir_listing:
                if (os.path.splitext(filename)[1] == ".key"
                    and filename not in self._keypairdb_config
                    and filename not in removed_keypairs
                    and filename not in self._no_sync):
                    try:
                        self.import_from_file(filename)
                    except (IOError, ValueError, binascii.Error):
                        # Avoid trying to automatically import this keypair
                        # for the rest of the session
                        self._no_sync.append(filename)

            # Deletions
            for filename in self._keypairdb_config:
                if (os.path.dirname(filename) == self._my_keypairs_dir
                    and filename not in new_my_keypairs_dir_listing):
                    self.remove(filename, persistent=False)

    def get_keypair_file_state(self, filename):
        """Return the modified time of a (keypair) file, or False if the file
        isn't currently accessible."""
        try:
            return os.path.getmtime(filename)
        except OSError:
            return False

    def get_keypair_files_state(self):
        """Return a dictionary storing the state of each keypair file."""
        keypair_files_state = {}

        for filename in self:
            keypair_file_state = self.get_keypair_file_state(filename)
            keypair_files_state[filename] = keypair_file_state

        return keypair_files_state

    def import_from_file(self, filename, passphrase=None):
        """Import a keypair to the database from a PEM file containing its
        private key."""
        properties = {
                      'added': time.time(),
                      }

        # Get fingerprint
        keypair = keypairengine.read(filename, passphrase=passphrase)
        properties['fingerprint'] = keypairengine.fingerprint(keypair)

        # Add this keypair to the keypair database
        self._keypairdb_config[filename] = properties

        # Untag as removed
        if filename in self._keypairdb_meta_config['removed']:
            self._keypairdb_meta_config['removed'].remove(filename)

        # Validate configuration to enforce the default values
        self._config.validate()

        # Initial load into the database
        self.__getitem__(filename)

    def remove(self, filename, persistent=True):
        """Remove a keypair from the database."""
        del self._keypairdb_config[filename]

        # If the keypair file is located in the My Keypairs directory, tag it
        # as removed so that it isn't automatically re-imported
        if persistent and os.path.dirname(filename) == self._my_keypairs_dir:
            self._keypairdb_meta_config['removed'].append(filename)

        # Save configuration
        self._config.save()
