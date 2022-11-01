import sys
import os
import signal
import winevt_tailer.opts as opts
import winevt_tailer.utils as utils
import winevt_tailer.consts as consts
from winevt_tailer.tailer import Tailer
import logging.config


def main() -> int:
    args = opts.parse_cmd_args()
    assert args.name

    sys.stdout.reconfigure(encoding='utf-8')

    # print channels to stdout and exit
    if args.list:
        channels = utils.get_event_channels()
        for ch in channels:
            print(ch)
        return 0

    # extract config from various sources
    tailer_config_dict, logging_config_dict = opts.get_config(args)

    # configure logging
    # create default log folder
    os.makedirs(consts.DEFAULT_LOG_DIR, exist_ok=True)
    logging.config.dictConfig(logging_config_dict)

    # args if present always override config
    if args.lookback is not None:
        tailer_config_dict['lookback'] = args.lookback
    if args.persistent is not None:
        tailer_config_dict['persistent'] = args.persistent
    if args.startup_hello is not None:
        tailer_config_dict['startup_hello'] = args.startup_hello
    if args.exit_after_lookback is not None:
        tailer_config_dict['exit_after_lookback'] = args.exit_after_lookback

    # print effective config to stdout and exit
    if args.print_config:
        yaml_str = utils.get_effective_config(args.name, tailer_config_dict, logging_config_dict)
        print(yaml_str)
        return 0

    # run tailing
    # Tailer outputs events as single line JSON to stdout.
    # Custom transforms can be applied to events (lxml object) before they get rendered to JSON.
    # Multiple chained transforms can be specified in tailer config as a list:
    #
    #   transforms: ['xform1', 'xform2' , ...]
    #
    #   - at channel level, applied first
    #   - at tailer level, common transforms, applied last, after channel transforms.
    #
    #  Transform value type is string that represents Python function import path.
    #  Function signature: def transform(context:dict, event:object): object
    #
    assert args.tail
    tailer_config = opts.parse_tailer_config(tailer_config_dict)
    tailer = Tailer(args.name, tailer_config)
    signal.signal(signal.SIGINT, lambda signum, frame: signal_handler(signum, frame, tailer))
    exit_code = tailer.run()
    return exit_code


def signal_handler(signum, frame, tailer):
    tailer.set_exit(True)
    print('Exiting ...', file=sys.stderr)


####################################################################################

if __name__ == '__main__':
    sys.exit(main())
