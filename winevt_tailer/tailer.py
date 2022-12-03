import os
import sys
import logging
import time
import contextlib
from  lazy_string import LazyString
import lxml
from lxml import etree
import win32evtlog
import win32event
import win32con
import winevt_tailer.opts as opts
import winevt_tailer.utils as utils
import winevt_tailer.consts as consts
import winevt_tailer.errors as errors


class Tailer:
    """
    Tailer outputs events as single line JSON to stdout by default.
    Custom transforms can be applied to events (lxml object) before they get rendered to JSON.
    Multiple chained transforms can be specified in tailer config as a list:

      transforms: ['xform1', 'xform2' , ...]

      - at channel level, applied first
      - at tailer level, common transforms, applied last, after channel transforms.

     Transform value type is string that represents Python function import path.
     Function signature: def transform(context:dict, event:object): object
    """

    def __init__(self, name, config: opts.TailerConfig):
        self.name = name
        self.is_stop = False
        self.config = config
        self.log = logging.getLogger("tailer")
        self.tail_out = logging.getLogger('tail_out')
        self.tail_out.propagate = False
        # max number of channels per tailer is limited
        if len(config.channels) > win32event.MAXIMUM_WAIT_OBJECTS:
            raise errors.ConfigError(
                f'Too many channels - {len(config.channels)}. Maximum supported - {win32event.MAXIMUM_WAIT_OBJECTS}')
        self.context = {}
        self.channel_transforms = [channel.transforms for channel in config.channels]
        self.final_transforms = config.transforms
        self.signals = [win32event.CreateEvent(None, 0, 0, None) for _ in config.channels]
        if self.config.lookback < 0:
            self.config.lookback = sys.maxsize
        self.bookmarks_filename = f'{self.config.bookmarks_dir}/{consts.TAILER_TYPE}_{self.name}.bookmarks'
        if self.config.persistent:
            os.makedirs(config.bookmarks_dir, exist_ok=True)
        if config.persistent and os.path.isfile(self.bookmarks_filename):
            self.bookmarks = utils.load_bookmarks(self.bookmarks_filename, config.channels)
        else:
            self.bookmarks = [win32evtlog.EvtCreateBookmark(None) for _ in config.channels]
        self.bookmarks_commit_ts = 0  # monotonic
        self.bookmarks_update_ts = 0  # monotonic

    def reset_state(self):
        """
        Reset persistent state - remove bookmarks
        """
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.bookmarks_filename)
        self.log.info(f'Removed file: "{self.bookmarks_filename}"')

    def stop(self) -> bool:
        if self.is_stop:
            return False
        self.is_stop = True
        return True

    def run(self) -> int:
        """
        This is main loop. Any error or exception is fatal. Exits on self.is_stop set in main by
        exit signal handler.
        """
        self.log.info("start")
        # output startup hello
        if self.config.startup_hello:
            self.tail_out.info(consts.STARTUP_HELLO % self.name)
        # query old events
        qrys = []
        for ch_idx in range(0, len(self.config.channels)):
            channel = self.config.channels[ch_idx]
            qry = win32evtlog.EvtQuery(channel.name, win32evtlog.EvtQueryForwardDirection, channel.query)
            qrys.append(qry)
        del qry
        # tail old events if any and subscribe
        subs = []  # subscriptions
        for ch_idx in range(0, len(self.config.channels)):
            last_event_h = None
            fetch_old_events = False
            # try to seek to bookmark with fallback to lookback if enabled
            try:
                win32evtlog.EvtSeek(qrys[ch_idx], 0, win32evtlog.EvtSeekRelativeToBookmark | win32evtlog.EvtSeekStrict,
                                    self.bookmarks[ch_idx])
                fetch_old_events = True
            except Exception:
                if self.config.lookback > 0:
                    win32evtlog.EvtSeek(qrys[ch_idx], -(self.config.lookback - 1), win32evtlog.EvtSeekRelativeToLast)
                    fetch_old_events = True
                pass
            # fetch & handle old events
            if fetch_old_events:
                while True:
                    if self.is_stop:
                        self.log.info("stop")
                        return 0
                    events = win32evtlog.EvtNext(qrys[ch_idx], Count=50, Timeout=100)
                    if len(events) == 0:
                        break
                    for event_h in events:
                        if self.handle_event(ch_idx, event_h):  # False means event was ignored
                            last_event_h = event_h
                    del events
                if last_event_h:  # last event if any
                    win32evtlog.EvtUpdateBookmark(self.bookmarks[ch_idx], last_event_h)
                    self.bookmarks_update_ts = time.monotonic()
                # subscribe after bookmark
                channel = self.config.channels[ch_idx]
                sub = win32evtlog.EvtSubscribe(
                    channel.name,
                    win32evtlog.EvtSubscribeStartAfterBookmark,
                    Bookmark=self.bookmarks[ch_idx],
                    SignalEvent=self.signals[ch_idx],
                    Query=channel.query
                )
                subs.append(sub)
            else:
                # subscribe to new events
                channel = self.config.channels[ch_idx]
                sub = win32evtlog.EvtSubscribe(
                    channel.name,
                    win32evtlog.EvtSubscribeToFutureEvents,
                    SignalEvent=self.signals[ch_idx],
                    Query=channel.query
                )
                subs.append(sub)
        del qrys
        # commit bookmarks if persistent mode is enabled
        if self.config.persistent:
            utils.store_bookmarks(self.bookmarks_filename, self.bookmarks, self.config.channels)
            self.bookmarks_commit_ts = time.monotonic()
        # exit after old events printed?
        if self.config.exit_after_lookback or self.is_stop:
            self.log.info("stop")
            return 0
        # fetch & handle new events before waiting
        for ch_idx in range(0, len(self.config.channels)):
            last_event_h = None
            while True:
                if self.is_stop:
                    self.log.info("stop")
                    return 0
                events = win32evtlog.EvtNext(subs[ch_idx], Count=50, Timeout=100)
                if len(events) == 0:
                    break
                for event_h in events:
                    if self.handle_event(ch_idx, event_h):  # False means event was ignored
                        last_event_h = event_h
                del events
            if last_event_h:  # last event if any
                win32evtlog.EvtUpdateBookmark(self.bookmarks[ch_idx], last_event_h)
                self.bookmarks_update_ts = time.monotonic()
        del sub
        # main event loop
        self.log.info("event loop running")
        while True:
            # commit bookmarks
            if self.config.persistent and self.bookmarks_update_ts > self.bookmarks_commit_ts and \
                    self.bookmarks_commit_ts + self.config.bookmarks_commit_s < time.monotonic():
                utils.store_bookmarks(self.bookmarks_filename, self.bookmarks, self.config.channels)
                self.bookmarks_commit_ts = time.monotonic()
            # wait for channels to be signaled
            while True:
                if self.is_stop:
                    self.log.info("stop")
                    return 0
                signaled = win32event.WaitForMultipleObjectsEx(self.signals, False, 500, True)
                if win32con.WAIT_OBJECT_0 <= signaled < win32con.WAIT_OBJECT_0 + win32event.MAXIMUM_WAIT_OBJECTS:
                    ch_idx = signaled - win32con.WAIT_OBJECT_0
                    break
            # fetch & handle new events from signalled channel
            last_event_h = None
            while True:
                events = win32evtlog.EvtNext(subs[ch_idx], Count=50, Timeout=100)
                if len(events) == 0 or self.is_stop:
                    break
                for event_h in events:
                    if self.handle_event(ch_idx, event_h):  # False means event was ignored
                        last_event_h = event_h
                del events
            if last_event_h:  # update bookmark from last event if any
                win32evtlog.EvtUpdateBookmark(self.bookmarks[ch_idx], last_event_h)
                self.bookmarks_update_ts = time.monotonic()

    def handle_event(self, ch_idx: int, event_h) -> bool:
        xml_str = win32evtlog.EvtRender(event_h, win32evtlog.EvtRenderEventXml)
        event_obj = lxml.etree.fromstring(xml_str)
        self.log.debug(LazyString(lambda: etree.tostring(event_obj, pretty_print=True).decode()))
        # apply channel transforms
        for xform in self.channel_transforms[ch_idx]:
            event_obj = xform(self.context, event_h, event_obj)
            if event_obj is None:
                return False  # skipped
        # apply common transforms
        for xform in self.final_transforms:
            event_obj = xform(self.context, event_h, event_obj)
            if event_obj is None:
                return False  # skipped
        # print to tailer output configured in logging config
        self.tail_out.info(event_obj)
        return True
