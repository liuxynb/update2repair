#!/usr/bin/env python3

import os
import shlex
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def script_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_config_path() -> Path:
    return script_root() / "conf" / "config.xml"


def load_config(config_path: Path) -> dict:
    tree = ET.parse(config_path)
    root = tree.getroot()
    values = {}
    for attr in root.findall("attribute"):
        name = attr.findtext("name", default="")
        if not name:
            continue
        entries = [value.text.strip() for value in attr.findall("value") if value.text]
        if name == "helpers.address":
            values[name] = entries
        elif entries:
            values[name] = entries[0]
    return values


def helper_hosts(config: dict) -> list[str]:
    hosts = []
    for entry in config.get("helpers.address", []):
        if "/" in entry:
            hosts.append(entry.split("/", 1)[1])
        else:
            hosts.append(entry)
    return hosts


def run_local(command: str, check: bool = True) -> int:
    result = subprocess.run(command, shell=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed: {command}")
    return result.returncode


def run_remote(host: str, command: str, check: bool = True) -> int:
    quoted = f"ssh {host} {shlex_quote(command)}"
    return run_local(quoted, check=check)


def copy_file(src: Path, host: str, remote_dir: str) -> None:
    run_local(f"scp {shlex_quote(str(src))} {shlex_quote(f'{host}:{remote_dir}/')}")


def copy_directory(src: Path, host: str, remote_dir: str) -> None:
    if shutil.which("rsync"):
        run_local(
            f"rsync -az --delete {shlex_quote(str(src))}/ {shlex_quote(f'{host}:{remote_dir}/{src.name}/')}"
        )
    else:
        run_remote(host, f"rm -rf {remote_dir}/{src.name}")
        run_local(f"scp -r {shlex_quote(str(src))} {shlex_quote(f'{host}:{remote_dir}/')}")


def shlex_quote(text: str) -> str:
    return shlex.quote(text)
