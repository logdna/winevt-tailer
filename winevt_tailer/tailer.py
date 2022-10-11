import math
import os
import logging
import time
import win32evtlog, win32event, win32con
import winevt_tailer.opts as opts
import winevt_tailer.utils as utils
import winevt_tailer.errors as errors
from lxml import etree


class Tailer:

    def __init__(self, name, config: opts.TailerConfig):
        self.name = name
        self.is_exit = False
        self.config = config
        self.log = logging.getLogger(name)
        if len(config.channels) > win32event.MAXIMUM_WAIT_OBJECTS:
            raise errors.ConfigError(
                f'Too many channels - {len(config.channels)}. Maximum supported - {win32event.MAXIMUM_WAIT_OBJECTS}')
        self.context = {}
        self.channel_transforms = [channel.transforms for channel in config.channels]
        self.final_transforms = config.transforms
        self.signals = [win32event.CreateEvent(None, 0, 0, None) for _ in config.channels]
        if config.persistent:
            os.makedirs(config.bookmarks_dir, exist_ok=True)
            self.bookmarks_filename = os.path.join(config.bookmarks_dir, f'winevt-tailer-{name}.bookmarks')
        else:
            self.bookmarks_filename = None
        if config.persistent and os.path.isfile(self.bookmarks_filename):
            self.bookmarks = utils.load_bookmarks(self.bookmarks_filename, config.channels)
        else:
            self.bookmarks = [win32evtlog.EvtCreateBookmark(None) for _ in config.channels]
        self.bookmarks_commit_ts = 0  # monotonic
        self.bookmarks_update_ts = 0  # monotonic

    def set_exit(self, is_exit):
        self.is_exit = is_exit

    def run(self) -> int:
        # query old events
        qrys = []
        for ch_idx in range(0, len(self.config.channels)):
            channel = self.config.channels[ch_idx]
            qry = win32evtlog.EvtQuery(channel.name, win32evtlog.EvtQueryForwardDirection, channel.query)
            qrys.append(qry)
        del qry
        # old events loop
        for ch_idx in range(0, len(self.config.channels)):
            last_event_h = None
            # try to seek to bookmark with fallback to lookback if enabled
            try:
                win32evtlog.EvtSeek(qrys[ch_idx], 0, win32evtlog.EvtSeekRelativeToBookmark | win32evtlog.EvtSeekStrict, self.bookmarks[ch_idx])
            except Exception as ex:
                if self.config.lookback:
                    win32evtlog.EvtSeek(qrys[ch_idx], -self.config.lookback, win32evtlog.EvtSeekRelativeToLast)
                pass
            # fetch old events
            while True:
                if self.is_exit:
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
        del qrys
        # subscribe to channels for events after bookmarks
        subs = []
        for ch_idx in range(0, len(self.config.channels)):
            channel = self.config.channels[ch_idx]
            sub = win32evtlog.EvtSubscribe(
                channel.name,
                win32evtlog.EvtSubscribeStartAfterBookmark,
                Bookmark=self.bookmarks[ch_idx],
                SignalEvent=self.signals[ch_idx],
                Query=channel.query
            )
            subs.append(sub)
        # fetch new events before waiting
        for ch_idx in range(0, len(self.config.channels)):
            last_event_h = None
            while True:
                if self.is_exit:
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
        while True:
            # commit bookmarks
            if self.config.persistent and self.bookmarks_update_ts > self.bookmarks_commit_ts and \
                    self.bookmarks_commit_ts + self.config.bookmarks_commit_s < time.monotonic():
                utils.store_bookmarks(self.bookmarks_filename, self.bookmarks, self.config.channels)
                self.bookmarks_commit_ts = time.monotonic()
            # wait for channels to be signaled
            while True:
                if self.is_exit:
                    return 0
                signaled = win32event.WaitForMultipleObjectsEx(self.signals, False, 500, True)
                if win32con.WAIT_OBJECT_0 <= signaled < win32con.WAIT_OBJECT_0 + win32event.MAXIMUM_WAIT_OBJECTS:
                    ch_idx = signaled - win32con.WAIT_OBJECT_0
                    break
            # fetch new events from signalled channel
            last_event_h = None
            while True:
                events = win32evtlog.EvtNext(subs[ch_idx], Count=50, Timeout=100)
                if len(events) == 0 or self.is_exit:
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
        event_obj = etree.fromstring(xml_str)
        # apply channel transforms
        for xform in self.channel_transforms[ch_idx]:
            event_obj = xform(self.context, event_h, event_obj)
            if event_obj is None:
                return False
        # apply common transforms
        for xform in self.final_transforms:
            event_obj = xform(self.context, event_h, event_obj)
            if event_obj is None:
                return False
        # print to stdout
        print(event_obj)
        return True
