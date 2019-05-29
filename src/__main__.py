
import os
import sys
import socket
import inspect
import logging

from typing import Callable

from .external import handlers, connection


def direct_target_provider(args) -> Callable[[connection.Connection], None]:

    module = __import__(args.get('module'))
    target = getattr(module, args.get('target'), None)

    if target is None:
        raise Exception(f"Did not find target '{args.get('target')}' in module '{args.get('module')}'")

    if inspect.isclass(target):
        return lambda conn: target().handle(conn)

    if callable(target):
        return target

    raise TypeError(f"Unable to initialize suitable target using symbol '{target}'")


def indirect_target_provider(args) -> Callable[[connection.Connection], None]:

    target = None

    def fail_on_registration(handler):
        raise Exception(f"Already registered handler {target}; cannot register second handler {handler}")

    def register_target(handler):
        nonlocal target
        target = handler
        handlers.push_register_handler_hook(fail_on_registration)

    handlers.push_register_handler_hook(register_target)

    # Modules will register a handler when they load.
    __import__(args.get('module'))

    if target is None:
        raise Exception(f"Found no registered handlers after loading module '{args.get('module')}'")

    return target


def main(args):
    args = dict(zip(['port', 'module', 'target'], args))

    logging.debug(f"Starting external Python module '{args.get('module')}' in state: [ACTIVE]")
    logging.debug(f"Connecting to parent on port {args.get('port')}")

    address = ('localhost', int(args.get('port')))

    with connection.Connection(socket.create_connection(address, 30)) as conn:

        target_provider = direct_target_provider if 'target' in args else indirect_target_provider
        target = target_provider(args)
        target(conn)


if __name__ == '__main__':
    logging.basicConfig(format="%(asctime)s.%(msecs)03d %(levelname)s [ext. Python %(process)d] %(message)s",
                        level=logging.getLevelName(os.environ.get('GADGETRON_EXTERNAL_LOG_LEVEL', 'DEBUG')),
                        datefmt="%m-%d %H:%M:%S")
    main(sys.argv[1:])
