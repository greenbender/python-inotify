# Copyright (c) 2005 Manuel Amador <rudd-o@rudd-o.com>
# Copyright (c) 2009-2011 Forest Bond <forest@alittletooquiet.net>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

# Major modifications 2012-05-21 Byron Platt <byron.platt@gmail.com>
# (too many changes to mention)

"""
inotify provides a simple Python binding to the linux inotify system event
monitoring API inspired by inotifyx and an enhanced interface inspired by
pyinotify (but hopefully a bit easier to use).
"""

import os
import threading
import binding

for name in dir(binding):
    if name.startswith("IN_"):
        globals()[name] = getattr(binding, name)

class INotify(object):
    """Basic inotify wrapper class.

    See inotify(7), inotify_add_watch(2) and inotify_rm_watch(2) for detailed
    information on the base API.
    """

    def __init__(self):
        """Initialises a new inotify instance.

        Note: See inotify_init(2) for further details.
        """

        self._fd = binding.init()
        self._closed = False

    def __del__(self):
        """Cleans up the inotify instance.

        Closes the file descriptor opened by the constructor.

        Note: See inotify_init(2) for further details.
        """

        self.close()

    def close(self):
        """Closes the file descriptor opened by the constructor.

        Note: Do not try to use the instance after calling this function.
        """
        if not self._closed:
            self._closed = True
            try:
                os.close(self._fd)
            except OSError:
                pass

    def add_watch(self, path, mask=IN_ALL_EVENTS):
        """Adds a new watch, or modifies an existing watch.

        Args:
            path: Pathname to watch for files filesystem events.
            mask: Bitmask of events to be monitored for the path.

        Returns:
            A nonnegative watch descriptor.

        Raises:
            IOError: On error.

        Note: If a watch is added to the same inode more than once i.e a
            directory is being watched then a watch is added on a symlink to
            that same directory the most recently added watch will replace any
            existing watch.

        Note: See inotify_add_watch(2) for further information. See inotify(7)
            for a description of the bits that can be set in mask.
        """

        return binding.add_watch(self._fd, path, mask)

    def rm_watch(self, wd):
        """Removes a watch.

        Args:
            wd: The watch descriptor to remove.

        Note: Removing a watch causes an IN_IGNORED event to be generated for
            this watch descriptor.

        Raises:
            IOError: On error.

        Note: See inotify_rm_watch(2) for further information.
        """

        binding.rm_watch(self._fd, wd)

    def get_events(self, timeout=None):
        """Get a list of inotify events.

        Args:
            timeout: Specifies a timeout as a floating point number in seconds.
                A timeout of None will cause get_event to block until an event
                occurs. A timeout of zero specifies a poll and never blocks.

        Returns:
            A list of tuples of wd, mask, cookie and name in that order. If
            there is no name associated with the event the name will be an empty
            string.

        Raises:
            IOError: On error.

        Note: See inotify(7) for a detailed description of the returned fields.
        """

        return binding.get_events(self._fd, timeout)

INE_AUTO_ADD = 0x01
"""Automatically add watches to directories created on watched path."""

INE_REMOVE_MOVED = 0x02
"""Automatically remove watch if the watch is itself moved."""

class INotifyEvent(object):
    """Basic class representing and inotify event.

    Note: See inotify(7) for further details.
    """

    def __init__(self, wd, mask, cookie, name):

        self.__wd = wd
        self.__mask = mask
        self.__cookie = cookie
        self.__name = name

    wd = property(lambda self: self.__wd, None, None,
    """Watch descriptor associated with event.""")

    mask = property(lambda self: self.__mask, None, None, 
    """Event mask.""")

    cookie = property(lambda self: self.__cookie, None, None,
    """Event cookie.""")

    name = property(lambda self: self.__name, None, None,
    """Event name.""")

    def __str__(self):

        return "(%d, 0x%08x, %d, '%s')" % (self.wd, self.mask, self.cookie,
            self.name)

    def __repr__(self):

        return "%s%s" % (self.__class__.__name__, str(self))

class INotifyWatch(object):
    """Basic class representing and inotify watch.

    Note: If you want to modify a watch use add_watch() with the modified
        values.

    Note: The inode_path and path properties will become invalid when a watch is
        itself moved as there is no way to track the destination of the move
        operation.
    """

    def __init__(self, wd, path, inode_path, mask, flags=0):

        self.__wd = wd
        self.__path = path
        self.__inode_path = inode_path
        self.__mask = mask
        self.__flags = flags

    wd = property(lambda self: self.__wd, None, None,
    """Watch descriptor.""")

    path = property(lambda self: self.__path, None, None,
    """Path that watch was added to (at the time it was added).""")

    inode_path = property(lambda self: self.__inode_path, None, None,
    """Path of the inode that watch was added to (a the time it was added).""")

    mask = property(lambda self: self.__mask, None, None,
    """Bitmask of events to watch for.""")

    flags = property(lambda self: self.__flags, None, None,
    """Enhanced inotify flags.""")

    def __str__(self):

        return "(%d, '%s', '%s', 0x%08x, flags=0x%02x)" % (self.wd, self.path,
            self.inode_path, self.mask, self.flags)

    def __repr__(self):

        return "%s%s" % (self.__class__.__name__, str(self))

class INotifyEnhanced(INotify):
    """Enhanced inotify functionality.

    Adds the following capabilities:
        - Uses basic classes for Events and Watches.
        - Keeps track of active watches.
        - Associates inotify events with watches.
        - Recursively add watches to a path.
        - Monitor for creation of directories in a watch and automatically
          add a watch for the newly created directory.
        - Generator function for events.
        - Accessor functions for watches.

    Note: Due the nature of inotify there are number of caveats that must be
        observed when using the enhanced class. The class has been designed to
        behave in an intuitive manner which will meet the requirements of the
        majority of use cases. The following limitations exist:
            - If you create a watch on a symlink and the IN_DONT_FOLLOW mask
              flag is not set then the watch will be created on the inode of the
              destination of the symlink, for this reason deletion of the
              symlink itself will not result in removal of the watch.
            - For reasons stated in the above point, if the INE_AUTO_ADD flag
              was set on the watch and following the deletion of the symlink a
              a directrory is created in the watch then the path for the
              automatically added watch will be based on the 'inode path' of the
              watch, rather than the 'path' of the watch (which no longer
              exists).
            - If a path you are watching is moved then the path and node_path
              properties of the watch are no longer valid since the destination
              of the move is not known. The INE_REMOVE_MOVED flag is available
              to lessen the effects of this problem.

    Note: Be aware that receiving an event on a watch does not necessarily mean
        that the path associated with that watch still exists. Keep this in mind
        when performing operations on a watch path as a result of an event and
        always expect that an exception may occur as a result of a missing path
        or other error related to filesystem changes.
    """

    def __init__(self):

        INotify.__init__(self)
        self.__watches = {}
        self.__paths_to_watches = {}
        self.__inode_paths_to_watches = {}

    def add_watch(self, path, mask=IN_ALL_EVENTS, flags=0):
        """Adds a new watch, or modifies an existing watch.

        Args:
            path: Pathname to watch for files filesystem events.
            mask: Bitmask of events to be monitored for the path.
            flags: Enhanced inotify flags.

        Returns:
            An INotifyWatch instance.

        Note: If the INE_AUTO_ADD or INE_REMOVE_MOVED flags are set the actions
            performed by the options are only performed during a call to
            get_events() or in the events() generator function.

        Note: See INotify.add_watch() for further information.
        """

        m = mask

        # auto add
        if flags & INE_AUTO_ADD:
            m |= IN_CREATE | IN_MOVED_TO

        # auto remove moved
        if flags & INE_REMOVE_MOVED:
            m |= IN_MOVE_SELF

        # add watch
        wd = INotify.add_watch(self, path, m)

        # get inode path
        inode_path = path
        if not m & IN_DONT_FOLLOW:
            inode_path = os.path.realpath(path)

        watch = INotifyWatch(wd, path, inode_path, mask, flags)
        self.__watches[wd] = watch
        self.__paths_to_watches[path] = watch
        self.__inode_paths_to_watches[inode_path] = watch

        return watch

    def add_watches(self, path, mask=IN_ALL_EVENTS, flags=0, topdown=True):
        """Recursively adds new watches, or modifies existing watches.

        Args:
            path: Pathname to walk adding and add watches to.
            mask: Bitmask of events to be monitored.
            flags: Enhanced inotify flags.
            topdown: Add new watches topdown or bottom up.

        Returns:
            A list of INotifyWatch instances.

        Note: Whether or not symlinks should be followed is determined via the
            IN_DONT_FOLLOW flag of the supplied mask. By default this flag is
            set and symlinks will be followed.

        Note: If watches are added topdown (the default) then IN_OPEN and
            IN_CLOSE_NO_WRITE events will be generated for the watched parent
            directory when it is opened/closed to scan for child directories.
            Setting topdown to False prevents this behaviour.

        Note: See INotifyEnhanced.add_watch() for further information.
        """

        # should we follow symlinks
        follow = True
        if mask & IN_DONT_FOLLOW:
            follow = False

        # walk path adding watches to directories
        watches = []
        for root, dirs, files in os.walk(path, topdown, followlinks=follow):
            watch = self.add_watch(root, mask, flags)
            watches.append(watch)

        return watches

    def get_watch(self, wd):
        """Gets a watch.

        Args:
            path: The watch descriptor.

        Raises:
            KeyError: If there is no watch for the specified descriptor.

        Returns:
            The watch associated with the supplied descriptor as an
            INotifyWatch.
        """

        return self.__watches[wd]

    def get_watch_by_path(self, path):
        """Gets a watch.

        Args:
            path: The path of the watch.

        Raises:
            KeyError: If there is no watch on the path.

        Returns:
            The watch associated with the supplied pathname as an INotifyWatch
            instance if a watch matches.
        """

        try:
            watch = self.__inode_paths_to_watches[path]
        except KeyError:
            watch = self.__paths_to_watches[path]

        return watch

    def get_all_watches(self):
        """Gets a list of current watches.

        Returns:
            A list of the current watches as INotifyWatch instances.
        """

        return self.__watches.values()

    def _rm_watch(self, watch):
        """Remove watch.

        Internal rm_watch only called when an IN_IGNORED event is handled in
        in get_events. A call to rm_watch or the os removing a watch (as a
        result of unlinking a path) will trigger the IN_IGNORED event.
        """

        del self.__inode_paths_to_watches[watch.inode_path]
        del self.__paths_to_watches[watch.path]
        del self.__watches[watch.wd]

    def rm_watch(self, watch):
        """Removes a watch.

        Args:
            watch: The watch to remove.

        Note: When a watch is removed it may will appear not no have been
            removed until events have been processed using get_events() or the
            events() generator function. This is because watches are only fully
            removed once there has been confirmation of removal from inotify
            using the IN_IGNORED event mask flag. There will be no new events
            generated on the watch after removal.

        Note: See INotify.rm_watch() for further details.
        """

        INotify.rm_watch(self, watch.wd)

    def get_events(self, timeout=None):
        """Get a list of inotify events.

        Args:
            timeout: Specifies a timeout as a floating point number in seconds.
                A timeout of None will cause get_event to block until an event
                occurs. A timeout of zero specifies a poll and never blocks.

        Returns:
            A list of tuples of the form (watch, event) where watch is the
            INotifyWatch instance associated with the event, which is an
            INotifyEvent instance.

        Note: See INotify.get_events() for further information.
        """

        events = []
        for wd, mask, cookie, name in INotify.get_events(self, timeout):
            if mask & IN_Q_OVERFLOW and wd == -1:
                events.append((None, INotifyEvent(wd, mask, cookie, name)))
                continue

            watch = self.get_watch(wd)

            # get event and watch
            event = INotifyEvent(wd, mask, cookie, name)

            # auto remove
            if mask & IN_IGNORED:
                self._rm_watch(watch)

            # auto remove moved
            if watch.flags & INE_REMOVE_MOVED and mask & IN_MOVE_SELF:
                try:
                    self.rm_watch(watch)
                except IOError:
                    pass

            # auto add
            if watch.flags & INE_AUTO_ADD and mask & (IN_CREATE | IN_MOVED_TO):
          
                # use path or inode path
                path = os.path.join(watch.path, name)
                inode_path = os.path.join(watch.inode_path, name)

                # check for directory creation
                if mask & IN_ISDIR:
                    try:
                        self.add_watches(path, watch.mask, watch.flags, True)
                    except IOError:
                        try:
                            self.add_watches(inode_path, watch.mask, watch.flags, True)
                        except IOError:
                            pass

                # check for symlink to directory creation
                elif not mask & IN_DONT_FOLLOW and os.path.isdir(path):
                    try:
                        self.add_watches(path, watch.mask, watch.flags, True)
                    except IOError:
                        try:
                            self.add_watches(inode_path, watch.mask, watch.flags, True)
                        except IOError:
                            pass

            # check match on requested mask
            if mask & watch.mask:
                events.append((watch, event))

        return events

    def events(self, timeout=None):
        """Generator for inotify events.

        Args:
            timeout: Specifies a timeout as a floating point number in seconds.
                A timeout of None will cause get_event to block until an event
                occurs. A timeout of zero specifies a poll and never blocks.

        Returns:
            A tuple of the form (watch, event) where watch is the INotifyWatch
            instance associated with the event, which is an INotifyEvent
            instance.
        """

        while True:
            for event in self.get_events(timeout):
                yield event

class INotifyThreaded(threading.Thread, INotifyEnhanced):
    """Threaded version of INotifyEnhanced.
    """

    def __init__(self, callback=None):
        
        threading.Thread.__init__(self)
        INotifyEnhanced.__init__(self)
        
        self.__lock = threading.Lock()
        self.__callback = callback
        self.__running = False

    def add_watch(self, path, mask=IN_ALL_EVENTS, flags=0):
        """Adds a new watch, or modifies an existing watch.

        Same as INotifyEnhanced.add_watch() but thread safe.
        """
        
        self.__lock.acquire()
        try:
            watch = INotifyEnhanced.add_watch(self, path, mask, flags)
        finally:
            self.__lock.release()

        return watch

    def get_watch(self, wd):
        """Gets a watch.

        Same as INotifyEnhanced.get_watch() but thread safe.
        """

        self.__lock.acquire()
        try:
            watch = INotifyEnhanced.get_watch(self, wd)
        finally:
            self.__lock.release()

        return watch

    def get_watch_by_path(self, path):
        """Gets a watch.

        Same as INotifyEnhanced.get_watch_by_path() but thread safe.
        """

        self.__lock.acquire()
        try:
            watch = INotifyEnhanced.get_watch_by_path(self, path)
        finally:
            self.__lock.release()

        return watch

    def get_all_watches(self):
        """Gets a list of current watches.

        Same as INotifyEnhanced.get_all_watches() but thread safe.
        """

        self.__lock.acquire()
        try:
            watches = INotifyEnhanced.get_all_watches(self)
        finally:
            self.__lock.release()

        return watches

    def _rm_watch(self, watch):
        """Remove watch.

        Same as INotifyEnhanced._rm_watch() but thread safe.
        """

        self.__lock.acquire()
        try:
            INotifyEnhanced._rm_watch(self, watch)
        finally:
            self.__lock.release()

    def handle_event(self, watch, event):

        if self.__callback:
            self.__callback(watch, event)

    def run(self):

        self.__running = True

        while self.__running:

            for event in self.get_events(0.1):
                self.handle_event(*event)

    def stop(self):
        """Stops processing events and join thread.

        Note: Removes all watches and closes the file descriptor for inotify.
            See INotify.close() for further information.
        """

        self.close()

        self.__running = False
