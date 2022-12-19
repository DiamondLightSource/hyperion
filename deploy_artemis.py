import argparse
import os
from subprocess import PIPE, CalledProcessError, Popen

from git import Repo
from packaging.version import Version

recognised_beamlines = ["dev", "i03"]


def get_release_dir_from_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--beamline",
        type=str,
        choices=recognised_beamlines,
        help="The beamline to deploy artemis to",
        required=True,
    )
    args = parser.parse_args()
    if args.beamline == "dev":
        print("Running as dev")
        return "/tmp/artemis_release_test"
    else:
        return f"/dls_sw/{args.beamline}/software"


if __name__ == "__main__":
    release_area = get_release_dir_from_args()

    print(f"Putting releases into {release_area}")
    print("Gathering version tags from this repo")

    this_repo = Repo(os.path.join(os.path.dirname(__file__), ".git"))

    this_origin = this_repo.remotes.origin
    this_origin.fetch()

    versions = [t.name for t in this_repo.tags]
    versions.sort(key=Version, reverse=True)

    print(f"Found versions:\n{os.linesep.join(versions)}")

    latest_version_str = versions[0]

    deploy_location = os.path.join(release_area, f"artemis_{latest_version_str}")

    print(f"Cloning latest version {latest_version_str} into {deploy_location}")

    deploy_repo = Repo.init(deploy_location)
    deploy_origin = deploy_repo.create_remote("origin", this_origin.url)
    deploy_origin.fetch()

    deploy_repo.git.checkout(latest_version_str)

    print(f"Setting up environment in {deploy_location}")
    os.chdir(deploy_location)

    with Popen(
        "./dls_dev_env.sh", stdout=PIPE, bufsize=1, universal_newlines=True
    ) as p:
        if p.stdout is not None:
            for line in p.stdout:
                print(line, end="")

    if p.returncode != 0:
        raise CalledProcessError(p.returncode, p.args)

    move_symlink = input(
        """Move symlink (y/n)? WARNING: this will affect the running version!
Only do so if you have informed the beamline scientist and you're sure Artemis is not running.
"""
    )
    if move_symlink == "y":
        live_location = os.path.join(release_area, "artemis")
        new_tmp_location = os.path.join(release_area, "tmp_art")
        os.symlink(deploy_location, new_tmp_location)
        os.rename(new_tmp_location, live_location)
        print(f"New version moved to {live_location}")
        print("To start this version run artemis_restart from the beamline's GDA")
    else:
        print("Quiting without latest version being updated")
