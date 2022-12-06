import lxml
from lxml import etree
import win32evtlog
import winevt_tailer.consts as const

g_xml_to_json_xform = lxml.etree.XSLT(lxml.etree.fromstring(const.XSLT_XML_TO_JSON))

g_event_ns = {'event': 'http://schemas.microsoft.com/win/2004/08/events/event'}


def xml_to_json(context: dict, event_h, event_obj: object) -> object:
    """
        Converts etree event object to single line JSON string
    Args:
        context(dict): context persist over runtime, can be re-used to store key-values pairs
        event_h(PyHANDLE): event handle returned from win32evtlog API
        event_obj(object): event object, lxml tree object
    Returns:
        object:  event as single line JSON string
    """
    tree_obj = g_xml_to_json_xform(event_obj)
    event_json = str(tree_obj)
    return event_json


def xml_remove_binary(context: dict, event_h, event_obj: object) -> object:
    """
        Removes Event/EventData/Binary tag from event_obj
    Args:
        context(dict): context persist over runtime, can be re-used to store key-values pairs
        event_h(PyHANDLE): event handle returned from win32evtlog API
        event_obj(object): event object, lxml tree object
    Returns:
        object:  modified event_obj or None - to skip/drop event
    """
    for tag in event_obj.xpath("//event:Binary", namespaces=g_event_ns):
        tag.getparent().remove(tag)
    return event_obj


def xml_render_message(context: dict, event_h, event_obj: object) -> object:
    """
        Adds new "Message" xml tag with rendered log event message text.
    Args:
        context(dict): context persist over runtime, can be re-used to store key-values pairs
        event_h(PyHANDLE): event handle returned from win32evtlog API
        event_obj(object): event object, lxml tree object
    Returns:
        object:  modified event_obj or None - to skip/drop event
    """
    try:
        provider_name = event_obj.xpath("//event:Provider/@Name", namespaces=g_event_ns)
        metadata = win32evtlog.EvtOpenPublisherMetadata(provider_name[0])
    except Exception:
        # pywintypes.error: (2, 'EvtOpenPublisherMetadata', 'The system cannot find the file specified.')
        pass
    else:
        try:
            message: str = win32evtlog.EvtFormatMessage(metadata, event_h, win32evtlog.EvtFormatMessageEvent)
        except Exception:
            # pywintypes.error: (15027, 'EvtFormatMessage: allocated 0, need buffer of size 0', 'The message resource
            # is present but the message was not found in the message table.')
            pass
        else:
            sub = lxml.etree.SubElement(event_obj, 'Message')
            sub.text = message
    return event_obj


def xml_remove_eventdata(context: dict, event_h, event_obj: object) -> object:
    """
        Removes Event/EventData tag from event_obj only when Event/Message tag exists
    Args:
        context(dict): context persist over runtime, can be re-used to store key-values pairs
        event_h(PyHANDLE): event handle returned from win32evtlog API
        event_obj(object): event object, lxml tree object
    Returns:
        object:  modified event_obj or None - to skip/drop event
    """
    message = event_obj.xpath("/event:Event/Message", namespaces=g_event_ns)
    if message:
        for tag in event_obj.xpath("//event:EventData", namespaces=g_event_ns):
            tag.getparent().remove(tag)
    return event_obj
