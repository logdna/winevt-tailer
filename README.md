# winevt-tailer
Windows Event Log Tailer provides live tailing of Windows events to standard output when running as console application or to log file when running as a service. It is written in Python, and is MIT licensed open source.

<!-- TOC -->
* [Features](#features)
* [Installation](#installation)
* [Getting Started](#getting-started)
  * [Console mode](#console-mode)
  * [Service mode](#service-mode)
* [Advanced Usage](#advanced-usage)
  * [CLI Options](#cli-options)
  * [Configuration File](#configuration-file)
  * [Event Channels and XPath queries](#event-channels-and-xpath-queries)
  * [Environment vars](#environment-vars)
  * [Event Transforms](#event-transforms)
* [How to Build](#how-to-build)
* [Integration with Mezmo Agent](#integration-with-mezmo-agent)
<!-- TOC -->

## Features

- Live tail - following new events
- Lookback
- XPath queries
- Event Transforms - applying user defined transformations to events
- Keeping track of last tailed events - maintaining persistent state between runs
- Windows service mode with self install and uninstall
- Custom tail output using standard logging framework
- Using fast native libxml2 (lxml) for XML parsing and XSLT transforms (JSON assembly)
- Integration with Mezmo Agent

## Installation

Tailer is distributed as signed standalone executable available for download from [Releases](https://github.com/logdna/winevt-tailer/releases).

## Getting Started

### Console mode

To tail last 100 events from Application and last 100 events from System event logs:

```
winevt-tailer
```

Tailer will output each event log message to stdout as utf-8 encoded single-line JSON. New line, '\' and '"' chars in JSON field values are escaped with '\'.

To tail last 10 events and to follow new events:

```
winevt-tailer -f -b 10
```


### Service mode

To install Tailer as Windows service:

```winevt-tailer -i```

or

```winevt-tailer -i <CLI options>```

Service defaults:
- service name: ```winevt-tailer_<tailer_name>```
- tailer name: ```tail1```, see "-n" option

Functionally this service will be equivalent to CLI mode: ```winevt-tailer <CLI options>```. To change service CLI options - just run the same "-i" command again with new set of options. Persistent state "-p" and follow mode "-f" are enabled by default in service mode.

Tailer logs by default are stored in ```c:/ProgramData/logs```:

```
windows_tail1.log           -- Windows events in one-line-JSON format, ready to be streamed by Mezmo Agent
winevt-tailer_tail1.log     -- service instance log
```

The location can be changed in config file in ```winevt-tailer.logging``` section.

To uninstall the service:

```winevt-tailer -u```


## Advanced Usage

### CLI Options

```
> winevt-tailer.exe -h

usage: winevt-tailer.exe [-v | -h | -l | -e | -i | -u | -r] [-f] [-p] [-c filepath] [-n NAME] [-b LOOKBACK] [--tailer_config TAILER_CONFIG] [--logging_config LOGGING_CONFIG]
                         [-t TRANSFORMS_PATH] [-s]

Tail Windows Event logs using single-line JSON format

options:
  -v, --version         Show program version info and exit.
  -h, --help            Show this help message and exit.
  -l, --list            List event channel names accessible to current user. Some channels may need Admin rights.
  -e, --print_config    Print effective config and exit.
  -i, --install_service
                        Install windows service.
  -u, --uninstall_service
                        Uninstall windows service.
  -r, --reset           Reset persistent state - delete event bookmarks.
  -f, --follow          Follow and output new events as they arrive. True in service mode.
  -p, --persistent      Remember last tailed event for each channel and tail only new events after restart. Default: off
  -c filepath, --config filepath
                        Config file path, file format: YAML
  -n NAME, --name NAME  Tailer name. Also defines where to look for config: winevt-tailer/<name> in YAML file; TAILER_CONFIG_<name> and TAILER_LOGGING_<name> in env vars (as YAML string)
  -b LOOKBACK, --lookback LOOKBACK
                        Defines how many old events to tail. -1 means all available events. default is 100. Applied in non-persistent mode or when event channel persistent state was not
                        stored.
  --tailer_config TAILER_CONFIG
                        Named tailer config section as YAML string
  --logging_config LOGGING_CONFIG
                        Logging config section as YAML string
  -t TRANSFORMS_PATH, --transforms_path TRANSFORMS_PATH
                        Path to custom transforms
  -s, --startup_hello   Output Startup Hello line. Part of Mezmo Agent Tailer API. Default: off
 ```

### Configuration File

Tailer accepts configuration file name in "-c" option. The file format is YAML. Use "-e" option to dump effective config to a file and then use it as configuration file:

```
winevt-tailer -f -b 10 -e > config.yaml
```

Then you can start Tailer with generated config file:

```
winevt-tailer -c config.yaml
```

which will be equivalent to running "winevt-tailer -f -b 10".

Configuration file structure:

```
winevt-tailer:
    logging:
      <standard python logging config>
    tail1:
      <named tailer config>
```

Named tailer config section corresponds to tailer name specified in "-n" option, default is "tail1". Configuration file can have multiple named tailer configs. 
When tailer service starts it prints effective config to service log file. Default service log file: ```c:\ProgramData\logs\winevt-tailer_tail1.log```.
In service mode persistent state "-p" and follow mode "-f" are enabled by default.

### Event Channels and XPath queries

Tailer supports up to 64 event channels with optional individual custom filters using the same XPath syntax used in Windows Event Viewer.
Default event channels: ```Application, System```. Channels are defined in named tailer config section. Output from "winevt-tailer -e":

```
winevt-tailer:
    tail1:
        bookmarks_dir: .
        channels:
        -   name: Application           <<<< Channel name
            query: '*'                  <<<< XPath query
        -   name: System
            query: '*'
```

The same channel name can be used multiple times with different query filters. This may create duplicate events if channels queries produce overlapped content.

Windows event Viewer can be used to create channel filter:

![image](https://user-images.githubusercontent.com/7530150/204931587-6e2e045d-e7fe-402f-97b3-1fc44e26da0b.png)

then switch to XML view of the filter and extract XPath query (highlighted):

![image](https://user-images.githubusercontent.com/7530150/204931845-68af1728-38fa-4549-9d65-30582e533681.png)

Use extracted XPath string as query value in tailer config file:
```
winevt-tailer:
    tail1:
        bookmarks_dir: .
        channels:
        -   name: Application
            query: '*[System[(EventID=4098)]]'
```


### Environment vars

Named tailer config and logging config sections can be passed in environment vars (as minified one-line-yaml string):

```
  TAILER_CONFIG                     - content of named tailer config section
  TAILER_CONFIG_<tailer_name>       - overrides TAILER_CONFIG

  TAILER_LOGGING                    - content of logging section
  TAILER_LOGGING_<tailer_name>      - overrides TAILER_LOGGING
```

Environment vars override config file. CLI options override environment vars and config file.


### Event Transforms

Tailer event processing pipeline:

```
  Event Channel -> Event XML Object -> Transforms (channel level) -> Transforms (top level) -> XML Object to JSON -> Output
```

Transforms can be configured at two levels:

- channel      - applied first, channel specific 
- top level    - applied at the end, common transforms for all channels

Example:

```
winevt-tailer:
    tail1:
        transforms:                                       <<<< top level
        - winevt_tailer.transforms.xml_remove_binary
        - winevt_tailer.transforms.xml_render_message
        - winevt_tailer.transforms.xml_to_json
        channels:
        - name: Application
          query: '*'
          transforms:                                     <<<< channel level 
          - my_transform.custom_channel_specific
```

Transform name is Python object importable full dotted path that used in import statements. Transforms are applied in the listed order. Tailer supports adding custom transforms defined in external py module file.

Here's a working example of event *deduplication transform* or reduction filter that skips subsequent events that have the same text in Message tag:

```
from lxml import etree
import win32evtlog


def dedup_by_message(context: dict, event_h, event_obj: object) -> object:
    """
    This transform implements simple deduplication based on rendered Message field by transforms.xml_render_message
    xform. It uses context object to store last event.
    Args:
        context: a dictionary that can be used to store data that preserved between calls
        event_h: event handle returned from win32evtlog API
        event_obj:  lxml.etree - parsed XMl object
    Returns:
        None - to skip event, otherwise unmodified original event obj
    """
    my_context = context.get("dedup_by_message")
    if my_context is None:
        context["dedup_by_message"] = {}
        return event_obj  # No skip, 1st event
    try:
        new_msg = etree.SubElement(event_obj, 'Message')
        last_event = my_context.get("last_event")
        if last_event is not None:
            last_msg = etree.SubElement(last_event, 'Message')
            if last_msg.text == new_msg.text:
                return None  # Skip, same message
    except Exception:
        # pywintypes.error: (2, 'EvtOpenPublisherMetadata', 'The system cannot find the file specified.')
        pass
    finally:
        my_context["last_event"] = event_obj
    return event_obj  # No skip
```

Save it to ```my_transforms.py```. Create default config file and add new transform function dot path ```my_transforms.dedup_by_message``` after ```xml_render_message```:

```
winevt-tailer:
    tail1:
      transforms:
      - winevt_tailer.transforms.xml_remove_binary
      - winevt_tailer.transforms.xml_render_message
      - my_transforms.dedup_by_message                   <<<<<<<<< the deduping transform
      - winevt_tailer.transforms.xml_to_json
```

Then run Tailer:

```
winevt-tailer -f -c config.yaml
```

For other examples see built-in transforms in: [winevt_tailer/transforms.py](winevt_tailer/transforms.py)

In CLI mode Tailer is looking for transforms in current working directory, in service mode - in the location of winevt-tailer.exe. Transforms path can also be specified using "-t" option. 


## How to Build

Recommended development setup:
- install [miniconda](https://repo.anaconda.com/miniconda/Miniconda3-py38_4.12.0-Windows-x86_64.exe)
- start conda shell
- create env

```
conda create -n work -c conda-forge python=3.10 git make
conda activate work
pip install poetry
```

- build exe

```
make clean
make lint
make test
make build
```

build will create ```winevt-tailer.exe``` in folder ```build/dist```

- test executable

```
build/dist/winevt-tailer.exe
```


## Integration with Mezmo Agent

Tailer can be used with [Mezmo Agent](https://github.com/logdna/logdna-agent-v2) to stream log files to [Mezmo.com](https://www.mezmo.com). Just install Tailer as service and then install [Mezmo Agent for Windows](https://community.chocolatey.org/packages/mezmo-agent). More tight integration with Mezmo Agent using Agent Tailer API (IPC) will be available in next Agent release.
