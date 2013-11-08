"""Keypair management application."""

import os
import thread
import time

from keypairauthclient import keypairengine
from pidexists import pid_exists
from pkg_resources import resource_stream
import wx
from wx.lib.mixins.listctrl import ColumnSorterMixin


class Generate():
    """Generate a new keypair while showing a progress dialog."""

    def __init__(self, config, locale, keypairdb, parent, filename,
                 keypairlistctrl=None):
        self._config = config
        self._locale = locale
        self._text = locale['text']
        self._keypairdb = keypairdb
        self._parent = parent
        self._filename = filename
        self._keypairlistctrl = keypairlistctrl

        self._cancellation_signal = False

        # Create progress dialog and pulser
        dialog = wx.ProgressDialog(self._text['generate_progress_title'],
                                   self._text['generate_progress_message'],
                                   style=wx.PD_CAN_ABORT)
        self._progress_dialog = dialog
        self._progress_pulser = wx.Timer(self._progress_dialog)
        self._progress_pulser.Start(30)
        self._progress_dialog.Bind(wx.EVT_TIMER, self._on_progress_pulser_tick,
                                   self._progress_pulser)

        # Start keypair generation thread
        thread.start_new_thread(self.generate, ())

    def _on_progress_pulser_tick(self, event):
        """Pulse the progress bar."""
        if not self._progress_dialog.Pulse()[0]:
            # Cancel button pressed
            self.cancel()

    def _kill_progress_dialog(self):
        """Kill the progress dialog."""
        self._progress_dialog.Destroy()
        self._progress_pulser.Stop()

    def cancel(self):
        """Safely signal cancellation of keypair generation."""
        self._cancellation_signal = True

        # Kill the progress dialog
        self._kill_progress_dialog()

    def generate(self):
        """Generate a new keypair, add it to the keypair database and update
        the keypair list control if one is specified."""
        # Generate a new keypair
        keypair = keypairengine.generate()

        # Don't continue if cancellation is requested
        if self._cancellation_signal:
            return

        # Generation complete; kill the progress dialog
        self._kill_progress_dialog()

        # Save new keypair as a PEM file
        keypairengine.save(keypair, self._filename)

        # Import keypair to the keypair database
        self._keypairdb.import_from_file(self._filename)

        # Immediately load the keypair into the keypair list control if one is
        # specified
        if self._keypairlistctrl is not None:
            self._keypairlistctrl.load_keypair(self._filename)


class KeypairListCtrl(wx.ListCtrl, ColumnSorterMixin):
    """Keypair list control."""

    def __init__(self, config, locale, keypairdb, *args, **kwargs):
        self._config = config
        self._locale = locale
        self._text = locale['text']
        self._keypairdb = keypairdb

        # Initialise
        wx.ListCtrl.__init__(self, *args, **kwargs)

        # Setup columns
        self.InsertColumn(0, self._text['keypairlist_column_name'], width=150)
        self.InsertColumn(1, self._text['keypairlist_column_added'], width=95)
        self.InsertColumn(2, self._text['keypairlist_column_last_used'],
                          width=95)
        self.InsertColumn(3, self._text['keypairlist_column_location'],
                          width=125)
        self.InsertColumn(4, self._text['keypairlist_column_encryption'],
                          width=80)

        # Enable sorting of keypairs by column
        self.itemDataMap = {}  # see ColumnSorterMixin documentation
        ColumnSorterMixin.__init__(self, 5)
        self.SortListItems(0, 1)  # sort by keypair name by default

        # A map to map keypair filenames to their self.itemDataMap keys so that
        # list items can be manipulated directly by knowing the filenames of
        # the keypairs they represent
        self._filename_to_data_map_key_map = {}

        # A dictionary to store the state (see
        # KeypairDB.get_keypair_files_state()) of each keypair file for use
        # by sync() to poll keypair file states
        self._keypair_files_state = {}
        self._first_sync = True  # changed to False on the first sync() call

        # Load all keypairs
        self.load_all_keypairs()

    def _get_item_by_data_map_key(self, data_map_key):
        """Return the index of a keypair item from its self.itemDataMap key."""
        return self.FindItemData(-1, data_map_key)

    def GetListCtrl(self):
        return self

    def load_all_keypairs(self):
        """Load all keypairs from the keypair database."""
        for filename in self._keypairdb:
            self.load_keypair(filename)

    def load_keypair(self, filename):
        """Load a keypair to the list control from the keypair database."""
        # Get keypair properties configuration object
        properties = self._keypairdb[filename]

        # Update keypair files state dictionary to prevent re-loading of this
        # keypair on the next self.sync() call, if this method wasn't called
        # from self.sync()
        keypair_file_state = self._keypairdb.get_keypair_file_state(filename)
        self._keypair_files_state[filename] = keypair_file_state

        #
        # Add keypair properties to self.itemDataMap for sorting
        #

        # Create a new key for the keypair in self.itemDataMap if one doesn't
        # already exist
        try:
            item_data_map_key = self._filename_to_data_map_key_map[filename]
        except KeyError:
            try:
                item_data_map_key = max(self.itemDataMap) + 1
            except ValueError:
                item_data_map_key = 0
            self._filename_to_data_map_key_map[filename] = item_data_map_key

        item_data = self.itemDataMap[item_data_map_key] = []

        item_data.append(properties['name'])
        item_data.append(properties['added'])
        item_data.append(properties['last_used'])

        if properties['on_interchangeable_storage'] == -1:
            item_data.append(self._text['keypairlistctrl_location_unknown']
                             .format(filename))
        elif properties['on_interchangeable_storage']:
            item_data.append(self._text['keypairlistctrl_location_external']
                             .format(filename))
        elif not properties['on_interchangeable_storage']:
            item_data.append(self._text['keypairlistctrl_location_internal']
                             .format(filename))

        item_data.append(properties['passphrased'])

        #
        # Add keypair to the graphical list
        #

        # Get an existing index for the keypair as it may already exist in the
        # list control
        index = self._get_item_by_data_map_key(item_data_map_key)

        if index == wx.NOT_FOUND:
            # New item
            index = self.GetItemCount()
            self.InsertStringItem(index, item_data[0])
            self.SetItemData(index, item_data_map_key)
        else:
            # Existing item
            self.SetStringItem(index, 0, item_data[0])

        self.SetStringItem(index, 1,
                           time.strftime(self._locale['datetime'],
                                         time.localtime(item_data[1])))

        if item_data[2] == -1:
            self.SetStringItem(index, 2,
                               self._text['keypairlistctrl_last_used_never'])
        else:
            self.SetStringItem(index, 2,
                               time.strftime(self._locale['datetime'],
                                             time.localtime(item_data[2])))

        self.SetStringItem(index, 3, item_data[3])

        if item_data[4] == -1:
            self.SetStringItem(index, 4,
                               self._text['keypairlistctrl_encryption_unknown']
                               )
        elif item_data[4]:
            self.SetStringItem(index, 4,
                               self._text['keypairlistctrl_encryption_passed'])
        elif not item_data[4]:
            self.SetStringItem(index, 4,
                               self._text['keypairlistctrl_encryption_none'])

        if properties['available']:
            self.SetItemTextColour(index, 'black')
        else:
            self.SetItemTextColour(index, 'grey')

        self.SortListItems()

    def purge_dead(self):
        """Remove all keypairs that are no longer in the keypair database from
        the list control."""
        for filename in self._filename_to_data_map_key_map.keys():
            if filename not in self._keypairdb:
                self.remove(filename)

    def remove(self, filename):
        """Remove a keypair from the list control."""
        item_data_map_key = self._filename_to_data_map_key_map[filename]
        item = self._get_item_by_data_map_key(item_data_map_key)

        del self._filename_to_data_map_key_map[filename]
        del self.itemDataMap[item_data_map_key]

        try:
            del self._keypair_files_state[filename]
        except KeyError:
            pass

        self.DeleteItem(item)

    def sync(self):
        """Synchronise all keypairs with their PEM files.

        The first call to this method doesn't actually synchronise the keypairs
        but does an initial poll of the state of the keypair files for
        comparison by the next call to this method.

        """
        new_keypair_files_state = self._keypairdb.get_keypair_files_state()

        if (new_keypair_files_state != self._keypair_files_state
            and not self._first_sync):

            # New or modified keypair PEM file properties
            for filename, state in new_keypair_files_state.iteritems():
                if filename not in self._keypair_files_state:
                    self.load_keypair(filename)
                else:
                    if ((state is False
                        or self._keypair_files_state[filename] is False)
                        and state != self._keypair_files_state[filename]):
                        time_difference = True
                    else:
                        time_difference = state
                        time_difference -= self._keypair_files_state[filename]
                        time_difference = round(time_difference, 2)

                    if time_difference > 0:
                        self.load_keypair(filename)

            # Removed keypairs
            for filename in self._keypair_files_state.keys():
                if filename not in new_keypair_files_state:
                    self.remove(filename)

        # Update keypair files state dictionary
        self._keypair_files_state = new_keypair_files_state
        self._first_sync = False


class MainWindow(wx.Frame):
    """Parent keypair management window."""

    def __init__(self, config, locale, keypairdb):
        self._config = config
        self._locale = locale
        self._text = locale['text']
        self._keypairdb = keypairdb

        # Initialise window
        wx.Frame.__init__(self, None, title=self._text['keypairmanager_title'],
                          size=(566, 350))
        self.Centre()
        self.Show(show=True)

        # Load PNG icons as bitmap objects from keypairauthgui.res.icons
        png_icon_names = (
                          'contact-new',
                          'document-open',
                          'list-remove',
                          'edit-delete',
                          'unlocked',
                          'locked',
                          )

        icons = {}
        for png_icon_name in png_icon_names:
            icons[png_icon_name] = {}
            for icon_size in (16, 32):
                icon_res_name = str(icon_size) + "/" + png_icon_name + ".png"
                icon = resource_stream('keypairauthgui.res.icons',
                                       icon_res_name)
                icon = wx.ImageFromStream(icon, type=wx.BITMAP_TYPE_PNG)
                icon = icon.ConvertToBitmap()
                icons[png_icon_name][icon_size] = icon

        # Setup File menu
        self.file_menu = wx.Menu()

        self.menu_generate = wx.MenuItem(parentMenu=self.file_menu,
                                         id=wx.ID_NEW,
                                         text=self._text['menu_generate'],
                                         help=self._text['help_generate'])
        self.menu_generate.SetBitmap(icons['contact-new'][16])
        self.file_menu.AppendItem(self.menu_generate)

        self.menu_import = wx.MenuItem(parentMenu=self.file_menu,
                                       id=wx.ID_OPEN,
                                       text=self._text['menu_import'],
                                       help=self._text['help_import'])
        self.menu_import.SetBitmap(icons['document-open'][16])
        self.file_menu.AppendItem(self.menu_import)

        self.file_menu_separator_0 = self.file_menu.AppendSeparator()

        self.menu_rename = wx.MenuItem(parentMenu=self.file_menu, id=wx.ID_ANY,
                                       text=self._text['menu_rename'],
                                       help=self._text['help_rename'])
        self.file_menu.AppendItem(self.menu_rename)

        self.menu_remove = wx.MenuItem(parentMenu=self.file_menu,
                                       id=wx.ID_REMOVE,
                                       text=self._text['menu_remove'],
                                       help=self._text['help_remove'])
        self.menu_remove.SetBitmap(icons['list-remove'][16])
        self.file_menu.AppendItem(self.menu_remove)

        self.menu_delete = wx.MenuItem(parentMenu=self.file_menu,
                                       id=wx.ID_DELETE,
                                       text=self._text['menu_delete'],
                                       help=self._text['help_delete'])
        self.menu_delete.SetBitmap(icons['edit-delete'][16])
        self.file_menu.AppendItem(self.menu_delete)

        self.file_menu_separator_1 = self.file_menu.AppendSeparator()

        self.menu_set_pass = wx.MenuItem(parentMenu=self.file_menu,
                                         id=wx.ID_ANY,
                                         text=self._text['menu_set_pass'],
                                         help=self._text['help_set_pass'])
        self.menu_set_pass.SetBitmap(icons['unlocked'][16])
        self.file_menu.AppendItem(self.menu_set_pass)

        self.menu_edit_pass = wx.MenuItem(parentMenu=self.file_menu,
                                          id=wx.ID_ANY,
                                          text=self._text['menu_edit_pass'],
                                          help=self._text['help_edit_pass'])
        self.menu_edit_pass.SetBitmap(icons['locked'][16])
        self.file_menu.AppendItem(self.menu_edit_pass)

        self.menu_unpass = wx.MenuItem(parentMenu=self.file_menu, id=wx.ID_ANY,
                                       text=self._text['menu_unpass'],
                                       help=self._text['help_unpass'])
        self.file_menu.AppendItem(self.menu_unpass)

        self.file_menu_separator_2 = self.file_menu.AppendSeparator()

        self.menu_quit = wx.MenuItem(parentMenu=self.file_menu, id=wx.ID_ANY,
                                     text=self._text['menu_quit'],
                                     help=self._text['help_quit'])
        self.file_menu.AppendItem(self.menu_quit)

        # Setup Help menu
        self.help_menu = wx.Menu()

        self.menu_about = wx.MenuItem(parentMenu=self.help_menu,
                                      id=wx.ID_ABOUT,
                                      text=self._text['menu_about'],
                                      help=self._text['help_about'])
        self.help_menu.AppendItem(self.menu_about)

        # Setup menu bar
        self.menubar = wx.MenuBar()
        self.menubar.Append(self.file_menu, self._text['file_menu'])
        self.menubar.Append(self.help_menu, self._text['help_menu'])
        self.SetMenuBar(self.menubar)

        # Setup tool bar
        self.toolbar = self.CreateToolBar()
        add_tool = self.toolbar.AddLabelTool

        self.tool_generate = add_tool(wx.ID_NEW, self._text['tool_generate'],
                                      icons['contact-new'][32],
                                      shortHelp=self._text['menu_generate'],
                                      longHelp=self._text['help_generate'])

        self.tool_import = add_tool(wx.ID_OPEN, self._text['tool_import'],
                                    icons['document-open'][32],
                                    shortHelp=self._text['menu_import'],
                                    longHelp=self._text['help_import'])

        self.toolbar_separator_0 = self.toolbar.AddSeparator()

        self.tool_remove = add_tool(wx.ID_REMOVE, self._text['tool_remove'],
                                    icons['list-remove'][32],
                                    shortHelp=self._text['menu_remove'],
                                    longHelp=self._text['help_remove'])

        self.tool_delete = add_tool(wx.ID_DELETE, self._text['tool_delete'],
                                    icons['edit-delete'][32],
                                    shortHelp=self._text['menu_delete'],
                                    longHelp=self._text['help_delete'])

        self.tool_set_pass = add_tool(wx.ID_ANY, self._text['tool_set_pass'],
                                      icons['unlocked'][32],
                                      shortHelp=self._text['menu_set_pass'],
                                      longHelp=self._text['help_set_pass'])

        self.tool_edit_pass = add_tool(wx.ID_ANY, self._text['tool_edit_pass'],
                                       icons['locked'][32],
                                       shortHelp=self._text['menu_edit_pass'],
                                       longHelp=self._text['help_edit_pass'])

        self.toolbar.Realize()

        # Setup status bar
        self.statusbar = self.CreateStatusBar()

        # Designate this application instance as the keypair files synchroniser
        # if one doesn't already exist
        self.config_sync_interval_callback(designate_only=True)

        # Setup keypair list control
        self.keypairlistctrl = KeypairListCtrl(self._config, self._locale,
                                               self._keypairdb, self,
                                               style=wx.BORDER_NONE |
                                               wx.LC_REPORT | wx.LC_VRULES |
                                               wx.LC_SINGLE_SEL)

        # Bind button events
        self.Bind(wx.EVT_MENU, self._on_quit, source=self.menu_quit)
        self.Bind(wx.EVT_CLOSE, self._on_quit)

        self.Bind(wx.EVT_MENU, self._on_generate, source=self.menu_generate)
        self.Bind(wx.EVT_TOOL, self._on_generate, source=self.tool_generate)

    def _on_generate(self, event):
        """Generate a new keypair."""
        # Some language-dependent text
        generate_saver_what = self._text['generate_saver_what']
        overwrite_caption = self._text['overwrite_caption']

        # Request a filename from the user to save the keypair to
        filename = None
        default_filename = os.path.join(self._keypairdb.my_keypairs_dir,
                                        self._text['generate_default_name'])
        while True:
            if filename is None:
                # Show a save file selector
                filename = wx.SaveFileSelector(generate_saver_what, ".key",
                                               default_name=default_filename)
            elif os.path.isfile(filename):
                # File already exists, get overwrite confirmation from the user
                basename = os.path.basename(filename)
                overwrite_message = self._text['overwrite_message']
                overwrite_message = overwrite_message.format(basename)
                overwrite = wx.MessageDialog(self, overwrite_message,
                                             caption=overwrite_caption,
                                             style=wx.YES_NO | wx.ICON_WARNING
                                             | wx.NO_DEFAULT)
                overwrite = overwrite.ShowModal()
                if overwrite == wx.ID_YES:
                    break
                elif overwrite == wx.ID_NO:
                    filename = None
            elif filename == '':
                # User closed the selector
                return
            else:
                # A filename has successfully been selected
                break

        # Generate
        Generate(self._config, self._locale, self._keypairdb, self, filename,
                 keypairlistctrl=self.keypairlistctrl)

    def _on_quit(self, event):
        """Quit application."""
        self.Destroy()

    def config_sync_callback(self):
        """Called when the configuration is synchronised."""
        # Reload all the keypairs in the keypair list control
        self.keypairlistctrl.load_all_keypairs()
        self.keypairlistctrl.purge_dead()

    def config_sync_interval_callback(self, designate_only=False):
        """Called at the end of every configuration synchronisation
        interval."""
        #
        # Synchronise the keypairs in the keypair list control with their PEM
        # files and the My Keypairs directory if this application instance's
        # pid is designated the synchroniser (this is to prevent other running
        # instances of the application from repeating the same synchronisation
        # tasks)
        #

        if ('keypair_files_syncer' not in self._config['gui']
            or not pid_exists(self._config['gui']['keypair_files_syncer'])):
            # Designate this application instance as the synchroniser as one
            # doesn't already exist
            self._config['gui']['keypair_files_syncer'] = os.getpid()
            self._config.save()
            self._keypairdb.sync_my_keypairs_dir = True

        if designate_only:
            return

        if self._config['gui']['keypair_files_syncer'] == os.getpid():
            self.keypairlistctrl.sync()
        else:
            self._keypairdb.sync_my_keypairs_dir = False
