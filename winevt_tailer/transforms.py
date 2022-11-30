from lxml import etree
import win32evtlog
import winevt_tailer.consts as const

xml_to_json_xform = etree.XSLT(etree.fromstring(const.XSLT_XML_TO_JSON))


def xml_to_json(context: dict, event_h, event_obj: object) -> object:
    tree_obj = xml_to_json_xform(event_obj)
    event_out = str(tree_obj).replace("\n", "\\n")  # TODO: do it using XSLT
    return event_out


def xml_remove_binary(context: dict, event_h, event_obj: object) -> object:
    """
        Removes Event/EventData/Binary tag from event_obj
    Args:
        context(dict): context persist over runtime. can be re-used to store key-values pairs
        event_obj(object): event object, lxml tree object
    Returns:
        object:  None - skip/drop event
    """
    context['last_event'] = event_obj
    ns = {'event': 'http://schemas.microsoft.com/win/2004/08/events/event'}
    for data in event_obj.xpath("//event:Binary", namespaces=ns):
        data.getparent().remove(data)
    return event_obj


def xml_render_message(context: dict, event_h, event_obj: object) -> object:
    message = ''
    try:
        ns = {'event': 'http://schemas.microsoft.com/win/2004/08/events/event'}
        provider_name = event_obj.xpath("//event:Provider/@Name", namespaces=ns)
        metadata = win32evtlog.EvtOpenPublisherMetadata(provider_name[0])
    except Exception:
        # pywintypes.error: (2, 'EvtOpenPublisherMetadata', 'The system cannot find the file specified.')
        pass
    else:
        try:
            message = win32evtlog.EvtFormatMessage(metadata, event_h, win32evtlog.EvtFormatMessageEvent)
        except Exception:
            # pywintypes.error: (15027, 'EvtFormatMessage: allocated 0, need buffer of size 0', 'The message resource is present but the message was not found in the message table.')
            pass
        else:
            sub = etree.SubElement(event_obj, 'Message')
            sub.text = message
    return event_obj
