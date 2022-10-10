import json
import os
import lxml
from lxml import etree
import win32evtlog, win32event, win32file
import winevt_tailer.errors as errors


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


def replace_file(src_file_name: str, dest_file_name: str):
    if not os.path.isfile(dest_file_name):
        open(dest_file_name, 'a').close()
    win32file.ReplaceFile(src_file_name, dest_file_name)


def store_bookmarks(bookmarks: list, channels: list, file_name: str):
    """
    Store bookmarks to file in JSON format
    Args:
        bookmarks: bookmark handles
        channels: list of ChannelConfig
        file_name: destination file. override if exists
    """
    assert len(channels) == len(bookmarks)
    tmp_file_name = file_name + '.tmp'
    bookmarks_dict = {}
    for i in range(0, len(channels)):
        ch = channels[i]
        key = ch.name + '#' + ch.query
        xml_str = win32evtlog.EvtRender(bookmarks[i], win32evtlog.EvtRenderBookmark)
        bookmarks_dict[key] = xml_str
    with open(tmp_file_name, 'w') as f:
        json.dump(bookmarks_dict, f)
    replace_file(tmp_file_name, file_name)


def load_bookmarks(file_name, channels: list) -> list:
    """
    Args: file_name: existing bookmarks file name, JSON channels([ChannelConfig]): list of channels from TailerConfig
    Returns: list[handle]: returns list of bookmark handles corresponding to channels. new bookmarks created for
    channels missing in the file
    """
    bookmarks = []
    try:
        with open(file_name, 'r') as f:
            bookmarks_dict = json.load(f)
        for ch in channels:
            key = ch.name + '#' + ch.query
            xml_str = bookmarks_dict.get(key)
            bookmarks.append(win32evtlog.EvtCreateBookmark(xml_str))
    except Exception as ex:
        raise errors.BookmarksError(ex)
    return bookmarks
