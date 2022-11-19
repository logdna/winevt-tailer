import sys
import os
import logging.config
import win32serviceutil
import win32service
import servicemanager
import winevt_tailer.opts as opts
import winevt_tailer.utils as utils
import winevt_tailer.consts as consts
from winevt_tailer.tailer import Tailer


def main() -> int:
    args = opts.parse_cmd_args()
    assert args.name
    tailer_name = args.name

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
    if args.follow:
        tailer_config_dict['exit_after_lookback'] = False

    # print effective config to stdout and exit
    if args.print_config:
        yaml_str = utils.get_effective_config(tailer_name, tailer_config_dict, logging_config_dict)
        print(yaml_str)
        return 0

    # create tailer config obj
    tailer_config = opts.parse_tailer_config(tailer_config_dict)

    # create tailer
    tailer = Tailer(tailer_name, tailer_config)

    if utils.is_running_as_service():
        # service runtime mode
        TailerService._svc_name_ = f'winenvt-tailer.{tailer_name}'
        TailerService._svc_display_name_ = f'winenvt-tailer.{tailer_name}'
        TailerService._svc_impl = tailer
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(TailerService)
        servicemanager.StartServiceCtrlDispatcher()  # returns when the service has stopped
        exit_code = 0
    else:
        # cli runtime mode
        # setup signal handler
        utils.setup_exit_signal_handler(lambda signum: exit_signal_handler(signum, tailer))
        # run tailer main loop
        exit_code = tailer.run()

    return exit_code


def exit_signal_handler(signum, tailer):
    tailer.stop() and print('Exiting ...', file=sys.stderr)


class TailerService(win32serviceutil.ServiceFramework):
    _svc_name_ = None
    _svc_display_name_ = None
    _svc_impl = None

    def SvcStop(self):
        # stop the service
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.service_impl.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        # start the service, does not return until stopped
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        self.service_impl = TailerService._svc_impl
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        # run the service
        self.service_impl.run()


if __name__ == '__main__':
    sys.exit(main())
