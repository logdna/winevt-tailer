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
import winevt_tailer.const as const


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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-l', '--list', action='store_true', help='list event channel names accessible to current '
                                                                 'user. Some channels need Admin rights.')
    group.add_argument('-t', '--tail', action='store_true', help='tail events to stdout, format is single line JSON')
    parser.add_argument('-c', '--config', dest='config_file', help='config file path, file format: yaml',
                        type=argparse.FileType('r'),
                        metavar='filepath')
    parser.add_argument('-n', '--name', help='tailer name. also defines where to look for tailer config: '
                                             'tailers/<name> in yaml file; TAILER_CONFIG_<name> in env var (yaml)',
                        type=lambda val: str_regex_type(val, regex_str=r'^[^\s]+$'), default='default')
    parser.add_argument('-b', '--lookback', type=int, help='start tailing at N events back. -1 means start-at-oldest')
    parser.add_argument('--logging_yaml', help='logging config as yaml string',
                        type=yaml_regex_type)
    parser.add_argument('--config_yaml', help='tailer config as yaml string',
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
    bookmarks_file: str = None
    bookmark_interval_s: int = 10
    lookback: int = -1  # start-at-oldest
    transforms: List[PyObject] = ['winevt_tailer.transforms.xml_remove_binary',
                                  'winevt_tailer.transforms.xml_to_json']


def parse_tailer_config(yaml_dict):
    try:
        config = TailerConfig(**yaml_dict)
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
    #
    if args.config_file:
        with args.config_file as f:
            config_file_dict = yaml.safe_load(f)
            config_tailers_dict = config_file_dict.get('tailers')
            if not config_tailers_dict:
                raise errors.ConfigError(f'Missing "tailers" section in config file: {f.name}')
            tailer_config_dict.update(config_tailers_dict.get(args.name, {}))
            if not tailer_config_dict:
                raise errors.ConfigError(f'Missing "tailers.{args.name}" section in config file {f.name}')
            logging_config_dict.update(config_file_dict.get('logging', {}))
    #
    tailer_env = os.getenv(f'TAILER_CONFIG')
    tailer_env = os.getenv(f'TAILER_CONFIG_{args.name.upper()}', tailer_env)
    if tailer_env:
        tailer_config_dict.update(yaml.safe_load(tailer_env))
    if args.config_yaml:  # tailer config as yaml string
        tailer_config_dict.update(yaml.safe_load(args.config_yaml))
    #
    logging_env = os.getenv(f'TAILER_LOGGING')
    logging_env = os.getenv(f'TAILER_LOGGING_{args.name.upper()}', logging_env)
    if logging_env:
        logging_config_dict.update(yaml.safe_load(logging_env))
    if args.logging_yaml:  # logging config as yaml string
        logging_config_dict.update(yaml.safe_load(args.logging_yaml))

    return tailer_config_dict, logging_config_dict
