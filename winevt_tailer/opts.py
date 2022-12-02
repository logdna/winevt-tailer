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
import winevt_tailer.consts as consts
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


def transforms_path_type(arg_value):
    # can be directory or file (zip)
    if not os.path.exists(arg_value):
        raise errors.ArgError(f"Transform path does exist: '{arg_value}'")
    if not os.access(arg_value, os.R_OK):
        raise errors.ArgError(f"Cannot access: '{arg_value}'")
    return arg_value


def parse_cmd_args(argv=None):
    """
    Args:
        argv[str]: argv list, default: sys.argv[1:]
    Returns:
        dict: parsed arguments as argparse dict
    """
    parser = argparse.ArgumentParser(description='Tail Windows Event logs using single-line JSON format',
                                     add_help=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-v', '--version', action='version',
                       version=f'{consts.TAILER_TYPE} {__version__}', help="Show program version info and exit.")
    group.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                       help='Show this help message and exit.')
    group.add_argument('-l', '--list', action='store_true', help='List event channel names accessible to current '
                                                                 'user. Some channels may need Admin rights.')
    group.add_argument('-e', '--print_config', action='store_true', help='Print effective config and exit.')
    group.add_argument('-i', '--install_service', action='store_true', help='Install windows service.')
    group.add_argument('-u', '--uninstall_service', action='store_true', help='Uninstall windows service.')
    group.add_argument('-r', '--reset', action='store_true', help='Reset persistent state - delete event bookmarks.')
    parser.add_argument('-f', '--follow', action='store_true', help='Follow and output new events as they arrive. '
                                                                    'True in service mode.')
    parser.add_argument('-p', '--persistent', action='store_true',
                        help='Remember last tailed event for each channel and '
                             'tail only new events after restart. Default: off', default=None)
    parser.add_argument('-c', '--config', dest='config_file', help='Config file path, file format: YAML',
                        type=argparse.FileType('r'), metavar='filepath')
    parser.add_argument('-n', '--name', help='Tailer name. Also defines where to look for config: '
                                             f'{consts.TAILER_TYPE}/<name> in YAML file; TAILER_CONFIG_<name> and '
                                             'TAILER_LOGGING_<name> in env vars (as YAML string)',
                        type=lambda val: str_regex_type(val, regex_str=r'^[^\s]+$'), default=consts.DEFAULT_TAILER_NAME)
    parser.add_argument('-b', '--lookback', type=int, help='Defines how many old events to tail. -1 means all '
                                                           f'available events. default is {consts.DEFAULT_LOOKBACK}. '
                                                           'Applied in non-persistent mode or when event channel '
                                                           'persistent state was not stored.')
    parser.add_argument('--tailer_config', help='Named tailer config section as YAML string', type=yaml_regex_type)
    parser.add_argument('--logging_config', help='Logging config section as YAML string', type=yaml_regex_type)
    parser.add_argument('-t', '--transforms_path', help='Path to custom transforms', type=transforms_path_type)
    parser.add_argument('-s', '--startup_hello', action='store_true',
                        help='Output Startup Hello line. Part of Mezmo Agent Tailer API. Default: off', default=None)
    #
    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    return args


class ChannelConfig(pydantic.BaseModel):
    name: str  # channel name
    query: str = "*"  # all events, XPath 1.0 query (see
    transforms: List[PyObject] = []  # ordered, applied before TailerConfig.transforms

    @validator("query")
    def check_transforms(cls, value):
        if not utils.is_valid_xpath(value):
            raise ValueError(f'Channel query is not valid XPath expression: {value}')
        return value


class TailerConfig(pydantic.BaseModel):
    channels: List[ChannelConfig]
    bookmarks_dir: str = "."  # current working directory
    bookmarks_commit_s: int = 10  # seconds
    lookback: int = consts.DEFAULT_LOOKBACK  # number of old events to tail per channel,
    #                                        # 0 - no lookback, only new events
    persistent = False  # don't bookmark last tailed events ids
    transforms: List[PyObject] = ['winevt_tailer.transforms.xml_remove_binary',
                                  'winevt_tailer.transforms.xml_render_message',
                                  'winevt_tailer.transforms.xml_to_json']  # final common transforms, applied after
    #                                                                      # channel transforms
    startup_hello = False
    exit_after_lookback = True  # exit after outputting old events


def parse_tailer_config(config_dict):
    try:
        config = TailerConfig(**config_dict)
    except pydantic.ValidationError as ex:
        raise errors.ConfigError(ex)
    return config


def get_config(args: object, is_service: bool) -> (dict, dict):
    """
    Collect tailer and logging configs from multiple sources (later overrides former):
    - default build-in
    - config file
    - config from env vars:
        - TAILER_CONFIG, TAILER_CONFIG_{args.name}
        - TAILER_LOGGING, TAILER_LOGGING_{args.name}
    - command line arguments:
        - args.tailer_config
        - args.logging_config
    Args:
        args: argparse output
        is_service: true if running as service
    Returns:
        (dict,dict): returns tailer_config_dict, logging_config_dict
    """
    if is_service:
        tailer_config_dict = yaml.safe_load(consts.DEFAULT_CONFIG_FOR_SERVICE.format(args.name))
        # service log and tail output go to different files in c:/ProgramData/logs
        logging_config_dict = yaml.safe_load(consts.DEFAULT_LOGGING_FOR_SERVICE.format(args.name))
    else:
        tailer_config_dict = yaml.safe_load(consts.DEFAULT_CONFIG_FOR_CONSOLE.format(args.name))
        # in cli mode log goes to stderr, while stdout is used for tail output only
        logging_config_dict = yaml.safe_load(consts.DEFAULT_LOGGING_FOR_CONSOLE.format(args.name))
    # from file
    if args.config_file:
        with args.config_file as f:
            config_file_dict = yaml.safe_load(f)
            config_tailers_dict = config_file_dict.get(consts.TAILER_TYPE)
            if not config_tailers_dict:
                raise errors.ConfigError(f'Missing "{consts.TAILER_TYPE}" section in config file: {f.name}')
            tailer_config_dict.update(config_tailers_dict.get(args.name, {}))
            logging_config_dict.update(config_file_dict.get('logging', {}))
    # tailer config from env vars and args
    tailer_env = os.getenv('TAILER_CONFIG')
    tailer_env = os.getenv(f'TAILER_CONFIG_{args.name.upper()}', tailer_env)
    if tailer_env:
        tailer_config_dict.update(yaml.safe_load(tailer_env))
    if args.tailer_config:  # tailer config as YAML string CLI arg
        tailer_config_dict.update(yaml.safe_load(args.tailer_config))
    # logging config from env vars and args
    logging_env = os.getenv('TAILER_LOGGING')
    logging_env = os.getenv(f'TAILER_LOGGING_{args.name.upper()}', logging_env)
    if logging_env:
        logging_config_dict.update(yaml.safe_load(logging_env))
    if args.logging_config:  # logging config as YAML string CLI arg
        logging_config_dict.update(yaml.safe_load(args.logging_config))
    return tailer_config_dict, logging_config_dict
