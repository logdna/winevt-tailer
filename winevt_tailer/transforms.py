from lxml import etree
import winevt_tailer.const as const

xml_to_json_xform = etree.XSLT(etree.fromstring(const.XSLT_XML_TO_JSON2))

def xml_to_json(context: dict, event: object) -> object:
    event_out = xml_to_json_xform(event)
    return event_out


def xml_remove_binary(context: dict, event: object) -> object:
    """
        Removes Event/EventData/Binary tag from event
    Args:
        context(dict): context persist over runtime. can be re-used to store key-values pairs
        event(object): event object, lxml tree object
    Returns:
        object:  None - skip/drop event
    """
    context['last_event'] = event
    ns = {'event': 'http://schemas.microsoft.com/win/2004/08/events/event'}
    for data in event.xpath("//event:Binary", namespaces=ns):
        data.getparent().remove(data)
    return event
