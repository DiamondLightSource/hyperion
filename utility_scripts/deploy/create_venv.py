import os
import sys
from subprocess import PIPE, CalledProcessError, Popen


def setup_venv(path_to_create_venv_script, deployment_directory):
    # Set up environment and run /dls_dev_env.sh...
    os.chdir(deployment_directory)
    print(f"Setting up environment in {deployment_directory}")

    with Popen(
        path_to_create_venv_script, stdout=PIPE, bufsize=1, universal_newlines=True
    ) as p:
        if p.stdout is not None:
            for line in p.stdout:
                print(line, end="")
    if p.returncode != 0:
        raise CalledProcessError(p.returncode, p.args)


if __name__ == "__main__":
    # This should only be entered from the control machine
    path_to_create_venv_script = sys.argv[1]
    deployment_directory = sys.argv[2]
    setup_venv(path_to_create_venv_script, deployment_directory)
