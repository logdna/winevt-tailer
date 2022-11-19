import sys
import os
import logging.config
import pywintypes
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
    tailer_service_name = f'winenvt-tailer.{tailer_name}'

    sys.stdout.reconfigure(encoding='utf-8')

    # print channels to stdout and exit
    if args.list:
        channels = utils.get_event_channels()
        for ch in channels:
            print(ch)
        return 0

    # extract config from various sources
    tailer_config_dict, logging_config_dict = opts.get_config(args)

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

    if args.install_service:
        return install_tailer_service(tailer_service_name)

    if args.uninstall_service:
        return uninstall_tailer_service(tailer_service_name)

    # create default log folder
    os.makedirs(consts.DEFAULT_LOG_DIR, exist_ok=True)
    # configure logging
    logging.config.dictConfig(logging_config_dict)

    # create tailer config obj
    tailer_config = opts.parse_tailer_config(tailer_config_dict)

    # create tailer instance
    tailer = Tailer(tailer_name, tailer_config)

    if utils.is_running_as_service():
        # run as service
        sys.stdout = sys.stderr = open('nul', 'w')
        TailerService._svc_name_ = tailer_service_name
        TailerService._svc_display_name_ = tailer_service_name
        TailerService._svc_impl = tailer
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(TailerService)
        servicemanager.StartServiceCtrlDispatcher()  # returns when the service has stopped
        exit_code = 0
    else:
        # run as console app
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

    def __init__(self, args):
        super().__init__(args)
        self.service_impl = None

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
        log = logging.getLogger("service")
        try:
            self.service_impl.run()
        except Exception as ex:
            log.error(ex)


def install_tailer_service(tailer_service_name) -> int:
    # requires admin rights
    if not utils.is_admin_user():
        try:
            exitcode = utils.restart_elevated()
            if exitcode:
                print(f'Failed exitcode: {exitcode}', file=sys.stderr)
            return exitcode
        except win32service.error as ex:
            print(f'{ex}', file=sys.stderr)
            return 1
    try:
        win32serviceutil.RemoveService(tailer_service_name)
    except win32service.error as ex:
        pass
    try:
        # remove -i, -u and append -f (service always follows)
        svc_args = " ".join(
            [s for s in sys.argv[1:] if s not in ['-i', '--install_service', '-u', '-uninstall_service']] + ['-f'])
        win32serviceutil.InstallService(
            None,
            tailer_service_name,
            tailer_service_name,
            description=tailer_service_name,
            startType=win32service.SERVICE_AUTO_START,
            exeArgs=svc_args,
        )
        print(f'Service installed: {tailer_service_name}', file=sys.stderr)
    except win32service.error as ex:
        print(f'{ex}', file=sys.stderr)
        pass
    return 0


def uninstall_tailer_service(tailer_service_name) -> int:
    # requires admin rights
    if not utils.is_admin_user():
        try:
            exitcode = utils.restart_elevated()
            if exitcode:
                print(f'Failed exitcode: {exitcode}', file=sys.stderr)
            return exitcode
        except win32service.error as ex:
            print(f'{ex}', file=sys.stderr)
            return 1
    try:
        win32serviceutil.RemoveService(tailer_service_name)
        print(f'Service uninstalled: {tailer_service_name}', file=sys.stderr)
    except pywintypes.error as ex:
        print(f'{ex}', file=sys.stderr)
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
