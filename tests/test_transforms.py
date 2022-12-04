import winevt_tailer.transforms as transforms
import lxml
from lxml import etree
import json


def test_xml_to_json():
    xml_str = r'''<?xml version="1.0"?>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
  <System>
    <Provider Name="Application Error"/>
    <EventID Qualifiers="0">1000</EventID>
    <Level>2</Level>
    <Task>100</Task>
    <Keywords>0x80000000000000</Keywords>
    <TimeCreated SystemTime="2022-11-29T08:34:36.419275100Z"/>
    <EventRecordID>22621</EventRecordID>
    <Channel>Application</Channel>
    <Computer>EC2AMAZ-B48FPS0</Computer>
    <Security/>
  </System>
  <EventData>
    <Data>ConsoleApp1.exe</Data>
    <Data>1.0.0.0</Data>
    <Data>6331eb0e</Data>
    <Data>KERNELBASE.dll</Data>
    <Data>10.0.17763.3469</Data>
    <Data>42aebc9e</Data>
    <Data>e0434352</Data>
    <Data>0000000000039319</Data>
    <Data>1020</Data>
    <Data>01d903cd695d5a7a</Data>
    <Data>C:\Users\dmitri\RiderProjects\FileWatcher\ConsoleApp1\bin\Debug\net6.0\ConsoleApp1.exe</Data>
    <Data>C:\Windows\System32\KERNELBASE.dll</Data>
    <Data>"string in double quotes"</Data>
    <Data>51b68da5-4c24-4bcd-a5ca-3d579fd62991</Data>
    <Data/>
    <Data/>
  </EventData>
</Event>
'''
    event_obj = lxml.etree.fromstring(xml_str)
    json_str: str = transforms.xml_to_json({}, None, event_obj)
    json.loads(json_str)
    assert json_str.find('\n') == -1
