#!/usr/bin/env python3
import argparse
import locale
import os
import re
import subprocess
from functools import partial
from sys import stderr, stdout

SETUP_CFG_PATTERN = re.compile("(.*?\\S)\\s*(@(.*))?$")
SETUP_UNPINNED_PATTERN = re.compile("(.*?\\S)\\s*([<>=]+(.*))?$")
PIP = "pip"


def rename_original(suffix):
    os.rename("setup.cfg", "setup.cfg" + suffix)


def normalize(package_name: str):
    return re.sub(r"[-_.]+", "-", package_name).lower()


def fetch_pin_versions() -> dict[str, str]:
    process = run_pip_freeze()
    if process.returncode == 0:
        output = process.stdout
        lines = output.split("\n")
        pin_versions = {}
        for line in lines:
            kvpair = line.split("==")
            if len(kvpair) != 2:
                stderr.write(f"Unable to parse {line} - ignored\n")
            else:
                pin_versions[normalize(kvpair[0]).strip()] = kvpair[1].strip()
        return pin_versions
    else:
        stderr.write(f"pip freeze failed with error code {process.returncode}\n")
        stderr.write(process.stderr)
        exit(1)


def run_pip_freeze():
    process = subprocess.run(
        [PIP, "freeze"], capture_output=True, encoding=locale.getpreferredencoding()
    )
    return process


def process_setup_cfg(input_fname, output_fname, dependency_processor):
    with open(input_fname) as input_file:
        with open(output_fname, "w") as output_file:
            process_files(input_file, output_file, dependency_processor)


def process_files(input_file, output_file, dependency_processor):
    while line := input_file.readline():
        output_file.write(line)
        if line.startswith("install_requires"):
            break
    while (line := input_file.readline()) and not line.startswith("["):
        if line.isspace():
            output_file.write(line)
        else:
            dependency_processor(line, output_file)
    output_file.write(line)
    while line := input_file.readline():
        output_file.write(line)


def strip_comment(line: str):
    split = line.rstrip("\n").split("#", 1)
    return split[0], (split[1] if len(split) > 1 else None)


def write_with_comment(comment, text, output_file):
    output_file.write(text)
    if comment:
        output_file.write(" #" + comment)
    output_file.write("\n")


def update_setup_cfg_line(version_map: dict[str, str], line, output_file):
    stripped_line, comment = strip_comment(line)
    if match := SETUP_UNPINNED_PATTERN.match(stripped_line):
        normalized_name = normalize(match[1].strip())
        if normalized_name not in version_map:
            stderr.write(
                f"Unable to find {normalized_name} in installed python packages\n"
            )
            exit(1)

        write_with_comment(
            comment,
            f"    {normalized_name} == {version_map[normalized_name]}",
            output_file,
        )
    else:
        output_file.write(line)


def write_commit_message(pinned_versions: dict[str, str]):
    message = f"Pin dependencies prior to release. Dodal {pinned_versions['dls-dodal']}, nexgen {pinned_versions['nexgen']}"
    stdout.write(message)


def unpin_versions(line, output_file):
    stripped_line, comment = strip_comment(line)
    if match := SETUP_CFG_PATTERN.match(stripped_line):
        if match[3] and match[3].strip().startswith("git+"):
            write_with_comment(comment, match[1], output_file)
            return

    output_file.write(line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pin dependency versions in setup.cfg")
    parser.add_argument(
        "--unpin",
        help="remove pinned hashes from setup.cfg prior to pip installing latest",
        action="store_true",
    )
    args = parser.parse_args()

    if args.unpin:
        rename_original(".orig")
        process_setup_cfg("setup.cfg.orig", "setup.cfg", unpin_versions)
    else:
        rename_original(".unpinned")
        installed_versions = fetch_pin_versions()
        process_setup_cfg(
            "setup.cfg.unpinned",
            "setup.cfg",
            partial(update_setup_cfg_line, installed_versions),
        )
        write_commit_message(installed_versions)
