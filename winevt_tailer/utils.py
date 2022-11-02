import json
import os
import uuid
import lxml
import yaml
import signal
import logging.handlers
from lxml import etree
import win32evtlog, win32event, win32file, win32api
import winevt_tailer.errors as errors


def dummy_signal_handler(_: int):
    pass


def setup_exit_signal_handler(signal_handler: type(dummy_signal_handler)):
    signal.signal(signal.SIGINT, lambda signum, _: signal_handler(signum))
    signal.signal(signal.SIGBREAK, lambda signum, _: signal_handler(signum))
    win32api.SetConsoleCtrlHandler(signal_handler, True)  # to catch windows shutdown


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


def park_and_delete_file(file_name: str):
    park_name = file_name + '.' + str(uuid.uuid1())[0:5]
    os.rename(file_name, park_name)
    if os.path.exists(park_name):
        os.remove(park_name)


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self.rotation_filename("%s.%d" % (self.baseFilename, i))
                dfn = self.rotation_filename("%s.%d" % (self.baseFilename, i + 1))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        park_and_delete_file(dfn)
                    os.rename(sfn, dfn)
            dfn = self.rotation_filename(self.baseFilename + ".1")
            if os.path.exists(dfn):
                park_and_delete_file(dfn)
            self.rotate(self.baseFilename, dfn)
        if not self.delay:
            self.stream = self._open()


def store_bookmarks(file_name: str, bookmarks: list, channels: list):
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
        bookmarks_dict[key] = xml_str.replace('\r', '').replace('\n', '')
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
            xml_str = bookmarks_dict.get(key)  # for added or updated channels this may be None
            bookmarks.append(win32evtlog.EvtCreateBookmark(xml_str))
    except Exception as ex:
        raise errors.BookmarksError(ex)
    return bookmarks


def get_effective_config(tailer_name, tailer_config: dict, logging_config: dict) -> str:
    config_dict = {'winevt-tailer': {tailer_name: tailer_config, 'logging': logging_config}}
    yaml_str = yaml.dump(config_dict, indent=4)
    return yaml_str
