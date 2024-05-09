import sys
from subprocess import PIPE, CalledProcessError, Popen


def setup_venv(path_to_create_venv_script):
    with Popen(
        path_to_create_venv_script, stdout=PIPE, bufsize=1, universal_newlines=True
    ) as p:
        if p.stdout is not None:
            for line in p.stdout:
                print(line, end="")
    if p.returncode != 0:
        raise CalledProcessError(p.returncode, p.args)


if __name__ == "__main__":
    path_to_create_venv_script = sys.argv[1]
    setup_venv(path_to_create_venv_script)
