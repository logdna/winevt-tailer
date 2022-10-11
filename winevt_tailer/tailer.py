import os
import logging
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
        self.bookmarks_filename = ""
        if os.path.isfile(self.bookmarks_filename):
            self.bookmarks = utils.load_bookmarks(self.bookmarks_filename, config.channels)
        else:
            self.bookmarks = [win32evtlog.EvtCreateBookmark(None) for _ in config.channels]

    def set_exit(self, is_exit):
        self.is_exit = is_exit

    def run(self) -> int:
        # subscribe to channels for events
        subs = []
        qrys = []
        for ch_idx in range(0, len(self.config.channels)):
            channel = self.config.channels[ch_idx]
            qry = win32evtlog.EvtQuery(channel.name, win32evtlog.EvtQueryForwardDirection, channel.query)
            sub = win32evtlog.EvtSubscribe(
                channel.name,
                win32evtlog.EvtSubscribeToFutureEvents,
                SignalEvent=self.signals[ch_idx],
                Query=channel.query
            )
            subs.append(sub)
            qrys.append(qry)
        del qry, sub
        # fetch old events
        for ch_idx in range(0, len(self.config.channels)):
            last_event_h = None
            if self.config.lookback:
                win32evtlog.EvtSeek(qrys[ch_idx], -self.config.lookback, win32evtlog.EvtSeekRelativeToLast)
            while True:
                if self.is_exit:
                    return 0
                events = win32evtlog.EvtNext(qrys[ch_idx], Count=50, Timeout=100)
                if len(events) == 0:
                    break
                for event_h in events:
                    if self.handle_event(ch_idx, event_h):  # False means event was ignored
                        last_event_h = event_h
            if last_event_h:  # last event if any
                win32evtlog.EvtUpdateBookmark(self.bookmarks[ch_idx], last_event_h)
        del qrys
        # event loop
        while True:
            # wait for channels to be signaled about new events, one channel at the time
            while True:
                if self.is_exit:
                    return 0
                signaled = win32event.WaitForMultipleObjectsEx(self.signals, False, 500, True)
                if win32con.WAIT_OBJECT_0 <= signaled < win32con.WAIT_OBJECT_0 + win32event.MAXIMUM_WAIT_OBJECTS:
                    ch_idx = signaled - win32con.WAIT_OBJECT_0
                    break
            # fetch new events for signalled channel
            last_event_h = None
            while True:
                events = win32evtlog.EvtNext(subs[ch_idx], Count=50, Timeout=100)
                if len(events) == 0 or self.is_exit:
                    break
                for event_h in events:
                    if self.handle_event(ch_idx, event_h):  # False means event was ignored
                        last_event_h = event_h
            if last_event_h:  # update bookmark for last event if any
                win32evtlog.EvtUpdateBookmark(self.bookmarks[ch_idx], last_event_h)

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
