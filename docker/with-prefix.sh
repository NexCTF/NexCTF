#!/usr/bin/env python3
"""Run a command and prefix every output line with [name]."""
import subprocess
import sys


def main() -> None:
    name = f"[{sys.argv[1]}]".encode()
    proc = subprocess.Popen(sys.argv[2:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.buffer.write(name + b" " + line)
        sys.stdout.buffer.flush()
    sys.exit(proc.wait())


if __name__ == "__main__":
    main()
