# winevt-tailer
Windows Event Log Tailer allows to live tail Windows events to standard output when running as console application or to log file when running as a service. It is written in Python, and is MIT licensed open source.

## Features
- Live tail - following new events
- Lookback
- XPath queries
- Keeping track of tailed events - presistent state
- Windows service mode with self install / uninstall
- Allows to add custom event transforms
- Custom tail output using standard logging framework
- Interation with Mezmo Agent

## Intallation
Tailer is distributed as standalone executable.

## Getting Started

### Console mode (CLI)

To tail last 100 events from Application and last 100 events from System event logs (channels):

```
winevt-tailer
```

Tailer will output each event log message to stdout as single-line-JSON. Multi-line values are escaped with '\n'.

To tail last 10 events and to follow new events:

```
winevt-tailer -f -b 10
```


### Service mode
To install Tailer as Windows service:

```winevt-tailer -i```

or

```winevt-tailer -i <CLI args>```

- default service name: ```winevt-tailer_<tailer_name>```. default tailer name: ```tail1```, controlled by "-n" CLI arg


Functionally this service will be equivalent to CLI mode:  ```winevt-tailer <CLI args>```. To change CLI args - just call the same "-i" command again with different set of CLI args.

In service mode logs go to ```c:/ProgramData/logs```:

```
    windows_tail1.log           -- Windows events in one-line-JSON format, ready to be streamed by Mezmo Agent
    winevt-tailer_tail1.log     -- service instance log
```

To uninstall the service:

```winevt-tailer -u```

## Advanced Usage

```
> winevt-tailer.exe -h

usage: winevt-tailer.exe [-v | -h | -l | -e | -i | -u | -r] [-f] [-p] [-c filepath] [-n NAME] [-b LOOKBACK] [--tailer_config TAILER_CONFIG] [--logging_config LOGGING_CONFIG] [-s]

Tail Windows Event logs using single-line JSON format

options:
  -v, --version         Show program version info and exit.
  -h, --help            Show this help message and exit.
  -l, --list            List event channel names accessible to current user. Some channels may need Admin rights.
  -e, --print_config    Print effective config end exit.
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
                        Defines how many old events to tail. -1 means all available events. default is 100. Applicable only to channels without persisted state
  --tailer_config TAILER_CONFIG
                        Named tailer config section as YAML string
  --logging_config LOGGING_CONFIG
                        Logging config section as YAML string
  -s, --startup_hello   Output Startup Hello line. Part of Mezmo Agent Tailer API. Default: off
 ```


## Integration with Mezmo Agent

Tailer can be used with [Mezmo Agent](https://github.com/logdna/logdna-agent-v2) to stream log files to [Mezmo.com](https://www.mezmo.com).
