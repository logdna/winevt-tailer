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
    tailer_service_name = f'{consts.TAILER_TYPE}_{tailer_name}'
    is_service = utils.is_running_as_service()

    # print windows event channels to stdout and exit
    if args.list:
        channels = utils.get_event_channels()
        for ch in channels:
            print(ch)
        return 0

    # collect config from various sources
    tailer_config_dict, logging_config_dict = opts.get_config(args, is_service)

    # cli args override other config sources
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
        yaml_str = utils.compose_effective_config(tailer_name, tailer_config_dict, logging_config_dict)
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
    log = logging.getLogger('main')
    log.info('init')

    # create tailer config obj
    tailer_config = opts.parse_tailer_config(tailer_config_dict)

    # create tailer instance
    tailer = Tailer(tailer_name, tailer_config)

    # reset persistent state - remove bookmarks
    if args.reset:
        tailer.reset_state()
        log.info('Reset completed')
        return 0

    if is_service:
        # service mode
        yaml_str = utils.compose_effective_config(tailer_name, tailer_config_dict, logging_config_dict)
        log.info('\n' + yaml_str)
        sys.stdout = sys.stderr = open('nul', 'w')
        TailerService._svc_name_ = tailer_service_name
        TailerService._svc_display_name_ = tailer_service_name
        TailerService._svc_impl = tailer
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(TailerService)
        servicemanager.StartServiceCtrlDispatcher()  # returns when the service has stopped
        exit_code = 0
    else:
        # cli, console mode
        utils.setup_exit_signal_handler(lambda signum: exit_signal_handler(signum, tailer))
        # run tailer main loop
        exit_code = tailer.run()

    log.info(f'exit ({exit_code})')
    return exit_code


def exit_signal_handler(signum, tailer):
    tailer.stop() and print('Exiting ...', file=sys.stderr)


class TailerService(win32serviceutil.ServiceFramework):
    # these fields must be defined in main() before object instantiation
    _svc_name_ = None
    _svc_display_name_ = None
    _svc_impl: Tailer = None

    def __init__(self, args):
        super().__init__(args)
        self.log = logging.getLogger("service")
        # handle "Start Parameters" passed to Service in SCM dialog
        if "-r" in args:
            self._svc_impl.reset_state()
            self.log.info('Reset completed')

    def SvcStop(self):
        # trigger stop
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._svc_impl.stop()

    def SvcDoRun(self):
        # start the service, does not return until stopped
        # base class will automatically tell SCM the service has stopped when this returns
        try:
            servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE, servicemanager.PYS_SERVICE_STARTED,
                                  (self._svc_name_, ''))
            self.log.info("started")
            self._svc_impl.run()
            self.log.info("stopped")
        except Exception as ex:
            self.log.error(ex)


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
        # remove -i, -u = install & uninstall
        #  append -f, -p = follow & persistent
        svc_args = " ".join(
            [s for s in sys.argv[1:] if s not in ['-i', '--install_service', '-u', '-uninstall_service']]) + '-f -p'
        win32serviceutil.InstallService(
            None,
            tailer_service_name,
            tailer_service_name,
            description=tailer_service_name,
            startType=win32service.SERVICE_AUTO_START,
            exeArgs=svc_args,
        )
        print(f'Service installed: {tailer_service_name}')
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
        print(f'Service uninstalled: {tailer_service_name}')
    except pywintypes.error as ex:
        print(f'{ex}', file=sys.stderr)
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
