import sys
import winevt_tailer.opts as opts
import winevt_tailer.utils as utils
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
    # by default log goes to stderr
    logging.config.dictConfig(logging_config_dict)

    # run tailing
    # Tailer outputs events as single line JSON to stdout.
    # custom transforms can be applied to events (lxml object) before they get rendered to JSON.
    # transforms can be specified in tailer config as a list:
    #
    #   transforms: ['xform1', 'xform2' , ...]       - at tailer level or at channel level, global processed first,
    #                                                  transform value is Python (or CFFI native) function import path.
    #                                                  function signature: def transform(context:dict, event:lxml_obj)
    #
    #  default global transform: 'winevt_tailer.transforms.remove_binary' - removes Data field from events.
    #
    assert args.tail
    tailer_config = opts.parse_tailer_config(tailer_config_dict)
    tailer = Tailer(args.name, tailer_config)
    exit_code = tailer.run()
    return exit_code


####################################################################################

if __name__ == '__main__':
    sys.exit(main())
