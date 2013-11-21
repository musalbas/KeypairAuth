"""User configuration management."""

import errno
import os
import shutil
import stat
import time

import dicttools
from external.configobj import ConfigObj
from external.validate import Validator

# Core configuration specification for data types and default values
CORE_CONFIGSPEC = """
[keypairdb_meta]
removed = force_list(default=list())
[keypairdb]
[[__many__]]
name = string(default="")
added = float()
last_used = float(default=-1)
on_interchangeable_storage = integer(default=-1)
passphrased = integer(default=-1)
last_file_check = float(default=-1)
available = boolean(default=False)
fingerprint = string()
"""


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""


class Config():
    """A ConfigObj-based configuration class that self-maintains the user
    configuration and its file."""

    validator = Validator()

    def __init__(self, filename, configspec_string="", sync_deepness=1):
        # Set the configuration "side" files' names
        self._temp_filename = filename + ".temp"
        self._sentinel_filename = filename + ".sentinel"
        self._backup_filename = filename + ".backup"
        self._backup_temp_filename = self._backup_filename + ".temp"

        # Set the number of seconds the temporary configuration "lock" file can
        # exist without it being assumed that the application that made it died
        self._temp_file_timeout = 2

        # Combine core configspec with specified configspec as a list of lines
        combined_configspec = (configspec_string + CORE_CONFIGSPEC)
        combined_configspec = combined_configspec.splitlines()
        self._combined_configspec = combined_configspec

        # Initialise ConfigObj (load configuration file)
        init_start = time.time()
        file_error = True
        while True:
            try:
                configobj = ConfigObj(infile=filename,
                                      configspec=combined_configspec,
                                      file_error=file_error)
                break
            except IOError, e:
                if not str(e).startswith("Config file not found: "):
                    raise
                # The configuration file doesn't exist yet
                if (not os.path.isfile(self._sentinel_filename)):
                    # This is a new configuration, go ahead and allow the file
                    # error to start a fresh configuration
                    file_error = False
                elif (os.path.isfile(self._sentinel_filename)
                      and time.time() > init_start + self._temp_file_timeout):
                    # The configuration isn't new and the configuration file
                    # still doesn't exist even after waiting for any potential
                    # application to finish with the potential lock file;
                    # initialise the configuration from the potential backup
                    try:
                        configobj = ConfigObj(infile=self._backup_filename,
                                              configspec=combined_configspec,
                                              file_error=True)
                        configobj.filename = filename
                        break
                    except IOError, e:
                        if not str(e).startswith("Config file not found: "):
                            raise
                        # Something is very wrong. There is no backup of the
                        # configuration; start a fresh configuration
                        file_error = False
                time.sleep(0.01)
        self._configobj = configobj

        self._sync_time = time.time()  # keep track of config version

        # Validate configuration
        self.validate()

        # Store a version of the configuration before self.sync() is called
        # so that the sync() method can determine the additions and changes to
        # the configuration since the last synchronisation
        self._configobj_before_sync = self._configobj.dict()

        # Set how deep sync() should recursively synchronise individual items
        # in nested configuration sections
        self._sync_deepness = sync_deepness

    @property
    def __getitem__(self):
        return self._configobj.__getitem__

    def save(self):
        """Save the configuration to its file."""
        # Sanity check: ensure that the configuration is valid before saving
        self.validate()

        # Create the configuration directory if it doesn't exist
        dirname = os.path.dirname(self._configobj.filename)
        if not os.path.isdir(dirname):
            # Directory permissions: only the owner can access it
            os.makedirs(dirname, mode=stat.S_IRUSR | stat.S_IWUSR
                        | stat.S_IXUSR)

        # Attempt to move the configuration file to a temporary "lock" file
        # that will be written to (this is to avoid race conditions when
        # multiple calls to this method are made simultaneously)
        move_start = time.time()
        last_attempt = False
        new_config = False
        while True:
            try:
                os.rename(self._configobj.filename, self._temp_filename)
                break
            except OSError:
                # Could not move the configuration file
                if not os.path.isfile(self._sentinel_filename):
                    # There is no sentinel file so the configuration is new;
                    # go ahead and write straight to the temporary file
                    new_config = True
                    # Create the sentinel file to symbolise that the
                    # configuration is no longer new
                    sentinel_file_handle = open(self._sentinel_filename, 'w')
                    sentinel_file_handle.close()
                    break
                elif last_attempt:
                    raise
                elif time.time() > move_start + self._temp_file_timeout:
                    # Still unable to move the configuration file even after
                    # continuously trying again; try to rename the temporary
                    # file back to the configuration file and try again a final
                    # time
                    try:
                        os.rename(self._temp_filename,
                                  self._configobj.filename)
                        last_attempt = True
                    except OSError, e:
                        if e.errno == errno.ENOENT:
                            new_config = True
                            break
                        # "if config doesn't exist now, we're really screwed"
                        # -sbp
                        raise
                time.sleep(0.01)

        # Attempt to secure configuration file permissions (file can only be
        # read from and written to by the owner)
        try:
            os.fchmod(self._temp_filename, stat.S_IRUSR | stat.S_IWUSR)
        except AttributeError:
            # Unsupported by the system
            pass

        # Synchronise the configuration before writing it out
        if not new_config:
            self.sync(filename=self._temp_filename)

        # Make a backup of the configuration file in case the application
        # doesn't finish writing the configuration out
        # Race conditions are OK here since the configuration has been locked
        if not new_config:
            shutil.copy(self._temp_filename, self._backup_temp_filename)
            if os.path.isfile(self._backup_filename):
                os.unlink(self._backup_filename)
            os.rename(self._backup_temp_filename, self._backup_filename)

        # Write out the configuration
        temp_file_handle = open(self._temp_filename, 'w')
        self._configobj.write(outfile=temp_file_handle)
        temp_file_handle.close()

        # Update configuration synchronisation time
        self._sync_time = time.time()

        # Rename the temporary configuration file back to the main filename
        os.rename(self._temp_filename, self._configobj.filename)

    def sync(self, filename=None):
        """Update the configuration values from a specified configuration file
        if the file is newer than the current configuration."""
        if filename is None:
            filename = self._configobj.filename

        # Get the difference between the specified configuration file
        # modification time and the current synchronisation time
        time_difference = os.path.getmtime(filename)
        time_difference -= self._sync_time
        time_difference = round(time_difference, 2)

        if time_difference <= 0:
            # Already in sync; reload not needed
            return False

        # Calculate the additions and changes in the configuration since the
        # last synchronisation
        new_items = dicttools.new_items(self._configobj_before_sync,
                                        self._configobj,
                                        deepness=self._sync_deepness)

        # Load the new configuration
        self._sync_time = time.time()  # update config sync time
        new_config = ConfigObj(filename)

        # Form a new, synchronised configuration dictionary
        new_config = dicttools.recursive_update(new_config, new_items)

        # Replace the current configuration with the synchronised one
        self._configobj.clear()
        self._configobj.update(new_config)

        # Re-attach the configspec as the ConfigObj has been cleared
        # There doesn't seem to be a way to do this with a configspec that
        # isn't a ConfigObj after the ConfigObj has been cleared, without
        # using a protected method - but hey, we're all "consenting adults"
        self._configobj._handle_configspec(self._combined_configspec)

        # Validate configuration
        self.validate()

        # Keep a copy of the current configuration for the next sync() call for
        # comparison
        self._configobj_before_sync = self._configobj.dict()

        return True

    def validate(self):
        """Validate the configuration.

        This verifies the configuration specification against the current
        configuration and copies the default values if required values are
        unspecified.

        """
        if self._configobj.validate(self.validator, copy=True) != True:
            raise ConfigValidationError("user configuration is invalid")
