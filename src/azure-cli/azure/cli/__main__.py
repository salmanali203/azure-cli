# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
# pylint: disable=wrong-import-position

import timeit
# Log the start time
start_time = timeit.default_timer()

import sys
import uuid

import azure.cli.core.telemetry as telemetry
from azure.cli.core import get_default_cli
from knack.completion import ARGCOMPLETE_ENV_NAME
from knack.log import get_logger


# A workaround for https://bugs.python.org/issue32502 (https://github.com/Azure/azure-cli/issues/5184)
# If uuid1 raises ValueError, use uuid4 instead.
try:
    uuid.uuid1()
except ValueError:
    uuid.uuid1 = uuid.uuid4


logger = get_logger(__name__)


def cli_main(cli, args):
    return cli.invoke(args)


az_cli = get_default_cli()

telemetry.set_application(az_cli, ARGCOMPLETE_ENV_NAME)

# Log the init finish time
init_finish_time = timeit.default_timer()

try:
    telemetry.start()

    exit_code = cli_main(az_cli, sys.argv[1:])

    if exit_code and exit_code != 0:
        if az_cli.result.error is not None and not telemetry.has_exceptions():
            telemetry.set_exception(az_cli.result.error, fault_type='')
        telemetry.set_failure()
    else:
        telemetry.set_success()

    sys.exit(exit_code)

except KeyboardInterrupt:
    telemetry.set_user_fault('keyboard interrupt')
    sys.exit(1)
except SystemExit as ex:  # some code directly call sys.exit, this is to make sure command metadata is logged
    exit_code = ex.code if ex.code is not None else 1
    raise ex

finally:
    try:
        # Log the invoke finish time
        invoke_finish_time = timeit.default_timer()
        logger.info("Command ran in %.3f seconds (init: %.3f, invoke: %.3f)",
                    invoke_finish_time - start_time,
                    init_finish_time - start_time,
                    invoke_finish_time - init_finish_time)
    except NameError:
        pass

    telemetry.set_init_time_elapsed("{:.6f}".format(init_finish_time - start_time))
    telemetry.set_invoke_time_elapsed("{:.6f}".format(invoke_finish_time - init_finish_time))
    telemetry.conclude()
    try:
        if sys.argv[1] != 'upgrade' and az_cli.config.getboolean('auto-upgrade', 'enable', False):
            from azure.cli.core._session import VERSIONS  # pylint: disable=ungrouped-imports
            from azure.cli.core.util import get_cached_latest_versions, _VERSION_UPDATE_TIME  # pylint: disable=ungrouped-imports
            if VERSIONS[_VERSION_UPDATE_TIME]:
                import datetime
                version_update_time = datetime.datetime.strptime(VERSIONS[_VERSION_UPDATE_TIME], '%Y-%m-%d %H:%M:%S.%f')
                if datetime.datetime.now() > version_update_time + datetime.timedelta(days=10):
                    get_cached_latest_versions()
                from distutils.version import LooseVersion
                if LooseVersion(VERSIONS['versions']['core']['local']) < LooseVersion(VERSIONS['versions']['core']['pypi']):  # pylint: disable=line-too-long
                    import subprocess
                    import platform
                    logger.warning("New Azure CLI version available. Running 'az upgrade' to update automatically.")
                    update_all = az_cli.config.getboolean('auto-upgrade', 'all', True)
                    prompt = az_cli.config.getboolean('auto-upgrade', 'prompt', True)
                    cmd = ['az', 'upgrade', '--all', str(update_all)]
                    if not prompt:
                        cmd.append('-y')
                    import os
                    devnull = open(os.devnull, 'w')
                    if prompt:
                        subprocess.call(cmd, shell=platform.system() == 'Windows')
                    else:
                        subprocess.call(cmd, shell=platform.system() == 'Windows', stdout=devnull)
    except Exception:  # pylint: disable=broad-except
        pass
