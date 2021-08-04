import argparse
import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

from utils import (run_cmd, run_cmd_quietly, set_up_logging, valid_dir_path,
                   verify_image)


def parse_args(args: List[str]) -> argparse.Namespace:
    """Create a argument parser and parse the command-line arguments.

    Args:
        args: A list of arguments to parse.

    Returns:
        A parser object containing parsed arguments.
    """

    parser = argparse.ArgumentParser(prog="run", description="MONAI Application Runner (MAR)")

    parser.add_argument("map", metavar="<map-image[:tag]>", help="MAP image name")

    parser.add_argument("input_dir", metavar="<input_dir>", type=valid_dir_path,
                        help="input directory path")

    parser.add_argument("output_dir", metavar="<output_dir>", type=valid_dir_path,
                        help="output directory path")

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        default=False, help='verbose mode')

    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', default=False,
                        help='execute MAP quietly without printing container logs onto console')

    return parser.parse_args(args)


def fetch_map_manifest(map_name: str) -> Tuple[dict, int]:
    """
    Execute MONAI Application Package and fetch application manifest.

    Args:
        map_name: MAP image name.

    Returns:
        app_info: application manifest as a python dict.
        returncode: command return code
    """
    logging.info("\nReading MONAI App Package manifest...")

    with tempfile.TemporaryDirectory() as info_dir:
        cmd = f'docker run --rm -it -v {info_dir}:/var/run/monai/export/config {map_name}'

        returncode = run_cmd(cmd)
        if returncode != 0:
            return {}, returncode

        app_json = Path(f'{info_dir}/app.json')
        pkg_json = Path(f'{info_dir}/pkg.json')

        logging.debug("-------------------application manifest-------------------")
        logging.debug(app_json.read_text())
        logging.debug("----------------------------------------------\n")

        logging.debug("-------------------package manifest-------------------")
        logging.debug(pkg_json.read_text())
        logging.debug("----------------------------------------------\n")

        app_info = json.loads(app_json.read_text())
        return app_info, returncode


def run_app(map_name: str, input_dir: Path, output_dir: Path, app_info: dict, quiet: bool) -> int:
    """
    Executes the MONAI Application.

    Args:
        map_name: MONAI Application Package
        input_dir: input directory path
        output_dir: output directory path
        app_info: application manifest dictionary
        quiet: boolean flag indicating quiet mode

    Returns:
        returncode: command returncode
    """
    cmd = 'docker run --rm -it -v {}:{} -v {}:{} {}'.format(input_dir, app_info['input']['path'],
                                                    output_dir, app_info['output']['path'],
                                                    map_name)

    if quiet:
        return run_cmd_quietly(cmd, waiting_msg="Running MONAI Application...")

    return run_cmd(cmd)


def dependency_verification(map_name: str) -> bool:
    """Check if all the dependencies are installed or not.

    Args:
        None.

    Returns:
        True if all dependencies are satisfied, otherwise False.
    """
    logging.info("Checking dependencies...")

    # check for docker
    prog = "docker"
    logging.info('--> Verifying if "%s" is installed...\n', prog)
    if not shutil.which(prog):
        logging.error('ERROR: "%s" not installed, please install docker.', prog)
        return False

    # check for map image
    logging.info('--> Verifying if "%s" is available...\n', map_name)
    if not verify_image(map_name):
        logging.error('ERROR: Unable to fetch required image.')
        return False

    return True


def main():
    """
    Main entry function for MONAI Application Runner.
    """
    args = parse_args(sys.argv[1:])
    set_up_logging(args.verbose)
    print(type(args))

    if not dependency_verification(args.map):
        logging.error("Aborting...")
        sys.exit()

    # Fetch application manifest from MAP
    app_info, returncode = fetch_map_manifest(args.map)
    if returncode != 0:
        logging.error("ERROR: Failed to fetch MAP manifest. Aborting...")
        sys.exit()

    # Run MONAI Application
    returncode = run_app(args.map, args.input_dir, args.output_dir, app_info, quiet=args.quiet)

    if returncode != 0:
        logging.error('\nERROR: MONAI Application "%s" failed.', args.map)
        sys.exit()


if __name__ == "__main__":
    main()
