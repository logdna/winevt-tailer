from lxml import etree


def remove_binary(context: dict, event: object) -> bool:
    """
        Removes Event/EventData/Binary tag from event
    Args:
        context(dict): context persist over runtime. can be re-used to store key-values pairs
        event(object): event object, lxml
    Returns:
        bool:  False - skip/drop event
    """
    context['last_event'] = event
    ns = {'event': 'http://schemas.microsoft.com/win/2004/08/events/event'}
    for data in event.xpath("//event:Binary", namespaces=ns):
        data.getparent().remove(data)
    return True
