import lxml
from lxml import etree
import win32evtlog, win32event


def is_valid_xpath(s) -> bool:
    valid = True
    try:
        lxml.etree.XPath(s)
    except lxml.etree.XPathSyntaxError:
        valid = False
    return valid


def get_event_channels() -> [str]:
    """
    Returns list of available channel names:
    - only non-direct channels
    - channels accessible by current user

    Returns:
        [str]: list of channel names
    """
    h = win32event.CreateEvent(None, 0, 0, None)
    ch = win32evtlog.EvtOpenChannelEnum()
    names = []
    while True:
        name = win32evtlog.EvtNextChannelPath(ch)
        if name is None:
            break
        try:
            win32evtlog.EvtSubscribe(name, win32evtlog.EvtSubscribeStartAtOldestRecord, SignalEvent=h)
        except Exception as ignore:
            continue
        names.append(name)
    h.Close()
    names.sort()
    return names
