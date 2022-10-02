import logging
import win32evtlog, win32event, win32con
import winevt_tailer.opts as opts
import winevt_tailer.errors as errors
from lxml import etree
import winevt_tailer.const as const


class Tailer:

    def __init__(self, name, config: opts.TailerConfig):
        self.name = name
        self.log = logging.getLogger(name)
        self.num = len(config.channels)
        if self.num > win32event.MAXIMUM_WAIT_OBJECTS:
            raise errors.ConfigError(
                f'Too many channels - {self.num}. Maximum supported - {win32event.MAXIMUM_WAIT_OBJECTS}')
        self.config = config
        self.context = {}
        self.global_transforms = config.transforms
        self.channel_transforms = [channel.transforms for channel in config.channels]
        self.signals = [win32event.CreateEvent(None, 0, 0, None) for _ in config.channels]
        self.xslt_xform = etree.XSLT(etree.fromstring(const.XSLT_XML_TO_JSON))

    def run(self) -> int:
        # subscribe
        # TODO: bookmarks & lookback
        subs = []
        for ch_idx in range(0, self.num):
            channel = self.config.channels[ch_idx]
            sub = win32evtlog.EvtSubscribe(
                channel.name,
                win32evtlog.EvtSubscribeStartAtOldestRecord,
                SignalEvent=self.signals[ch_idx],
                Query=channel.query
            )
            subs.append(sub)
        # fetch old events
        call_timeout_ms = 1000
        for ch_idx in range(0, self.num):
            while True:
                events = win32evtlog.EvtNext(subs[ch_idx], call_timeout_ms)
                if len(events) == 0:
                    break
                for event in events:
                    xml_str = win32evtlog.EvtRender(event, win32evtlog.EvtRenderEventXml)
                    self.handle_event(ch_idx, xml_str)
        # event loop
        while True:
            while True:
                signaled = win32event.WaitForMultipleObjectsEx(self.signals, False, 2000, True)
                if win32con.WAIT_OBJECT_0 <= signaled < win32con.WAIT_OBJECT_0 + win32event.MAXIMUM_WAIT_OBJECTS:
                    ch_idx = signaled - win32con.WAIT_OBJECT_0
                    break
                    # TODO check for exit
            while True:
                events = win32evtlog.EvtNext(subs[ch_idx], call_timeout_ms)
                if len(events) == 0:
                    break
                for event in events:
                    print(win32evtlog.EvtRender(event, win32evtlog.EvtRenderEventXml))
                print("retrieved %s events" % len(events))
        return 0

    def handle_event(self, ch_idx: int, event_xml: str):
        xml_obj = etree.fromstring(event_xml)
        for xform in self.global_transforms:
            xform(self.context, xml_obj)
        for xform in self.channel_transforms[ch_idx]:
            xform(self.context, xml_obj)
        json_doc = self.xslt_xform(xml_obj)
        print(json_doc)
        pass
