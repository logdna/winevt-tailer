import argparse
import sys
import yaml
import os
import re
import pydantic
from pydantic import PyObject, validator
from typing import List
import winevt_tailer.errors as errors
import winevt_tailer.utils as utils
import winevt_tailer.consts as const
from winevt_tailer import __version__


def str_regex_type(arg_value, regex_str):
    pat = re.compile(regex_str)
    if not pat.match(arg_value):
        raise errors.ArgError(f"Invalid 'name' value: '{arg_value}', allowed: '{regex_str}'")
    return arg_value


def yaml_regex_type(arg_value):
    try:
        yaml.safe_load(arg_value)
    except Exception as ex:
        raise errors.ArgError(ex)
    return arg_value


def parse_cmd_args(argv=None):
    """
    Args:
        argv[str]: argv list, default: sys.argv[1:]
    Returns:
        dict: parsed arguments as argparse dict
    """

    parser = argparse.ArgumentParser(description='Tails Windows Event logs to stdout.'
                                                 'JSON format.')
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-v', '--version', action='version',
                       version=f'winevt-tailer {__version__}', help="Show program version info and exit.")
    group.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                       help='Show this help message and exit.')
    group.add_argument('-l', '--list', action='store_true', help='List event channel names accessible to current '
                                                                 'user. Some channels need Admin rights.')
    group.add_argument('-e', '--print_config', action='store_true', help='Print effective config end exit.')
    group.add_argument('-t', '--tail', action='store_true', help='Tail events to stdout, format is single line JSON')
    parser.add_argument('-p', '--persistent', action='store_true',
                        help='Remember last tailed event for each channel and '
                             'tail only new events after restart.', default=None)
    parser.add_argument('-c', '--config', dest='config_file', help='Config file path, file format: yaml',
                        type=argparse.FileType('r'),
                        metavar='filepath')
    parser.add_argument('-n', '--name', help='Tailer name. Also defines where to look for config: '
                                             'winevt-tailer/<name> in yaml file; TAILER_CONFIG_<name> and '
                                             'TAILER_LOGGING_<name> in env vars (as yaml string)',
                        type=lambda val: str_regex_type(val, regex_str=r'^[^\s]+$'), default='tailer1')
    parser.add_argument('-b', '--lookback', type=int, help='Defines how many old events to tail for new/modified '
                                                           'channels. -1 means all available events ('
                                                           'default). Only for channels without persisted state.')
    parser.add_argument('--config-yaml', help='Tailer config as yaml string',
                        type=yaml_regex_type)
    parser.add_argument('--logging-yaml', help='Logging config as yaml string',
                        type=yaml_regex_type)
    #
    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    return args


class ChannelConfig(pydantic.BaseModel):
    name: str  # channel name
    query: str = "*"  # all events
    transforms: List[PyObject] = []  # ordered, applied after TailerConfig.transforms

    @validator("query")
    def check_transforms(cls, value):
        if not utils.is_valid_xpath(value):
            raise ValueError(f'Channel query is not valid xpath: {value}')
        return value


class TailerConfig(pydantic.BaseModel):
    channels: List[ChannelConfig]
    bookmarks_dir: str = "."  # default: current working directory
    bookmarks_commit_s: int = 10  # seconds
    lookback: int = -1  # start-at-oldest, all old events
    persistent = False  # remember last tailed event
    transforms: List[PyObject] = ['winevt_tailer.transforms.xml_remove_binary',
                                  'winevt_tailer.transforms.xml_render_message',
                                  'winevt_tailer.transforms.xml_to_json']


def parse_tailer_config(config_dict):
    try:
        config = TailerConfig(**config_dict)
    except pydantic.ValidationError as ex:
        raise errors.ConfigError(ex)
    return config


def get_config(args: object) -> (dict, dict):
    """
    Collect tailer and logging configs from multiple sources (later overrides former):
    - default build-in
    - config file
    - config from env vars:
        - TAILER_CONFIG, TAILER_CONFIG_{args.name}
        - TAILER_LOGGING, TAILER_LOGGING_{args.name}
    - command line arguments:
        - args.tailer_yaml
        - args.logging_yaml
    Args:
        args: argparse output
    Returns:
        (dict,dict): returns tailer_config_dict, logging_config_dict
    """
    tailer_config_dict = yaml.safe_load(const.DEFAULT_TAILER_CONFIG)
    logging_config_dict = yaml.safe_load(const.DEFAULT_LOGGING_CONFIG)
    # load from file
    if args.config_file:
        with args.config_file as f:
            config_file_dict = yaml.safe_load(f)
            config_tailers_dict = config_file_dict.get('winevt-tailer')
            if not config_tailers_dict:
                raise errors.ConfigError(f'Missing "winevt-tailer" section in config file: {f.name}')
            tailer_config_dict.update(config_tailers_dict.get(args.name, {}))
            logging_config_dict.update(config_file_dict.get('logging', {}))
    # from env vars and args
    # tailer config
    tailer_env = os.getenv(f'TAILER_CONFIG')
    tailer_env = os.getenv(f'TAILER_CONFIG_{args.name.upper()}', tailer_env)
    if tailer_env:
        tailer_config_dict.update(yaml.safe_load(tailer_env))
    if args.config_yaml:  # tailer config as yaml string
        tailer_config_dict.update(yaml.safe_load(args.config_yaml))
    # logging config
    logging_env = os.getenv(f'TAILER_LOGGING')
    logging_env = os.getenv(f'TAILER_LOGGING_{args.name.upper()}', logging_env)
    if logging_env:
        logging_config_dict.update(yaml.safe_load(logging_env))
    if args.logging_yaml:  # logging config as yaml string
        logging_config_dict.update(yaml.safe_load(args.logging_yaml))

    return tailer_config_dict, logging_config_dict
