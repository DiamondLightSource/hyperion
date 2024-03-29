import argparse
import os
from subprocess import PIPE, CalledProcessError, Popen
from uuid import uuid1

from git import Repo
from packaging.version import Version

recognised_beamlines = ["dev", "i03", "i04"]


class repo:
    # Set name, setup remote origin, get the latest version"""
    def __init__(self, name: str, repo_args):
        self.name = name
        self.repo = Repo(repo_args)

        self.origin = self.repo.remotes.origin
        self.origin.fetch()

        self.versions = [t.name for t in self.repo.tags]
        self.versions.sort(key=Version, reverse=True)
        print(f"Found {self.name}_versions:\n{os.linesep.join(self.versions)}")
        self.latest_version_str = self.versions[0]

    def deploy(self, url):
        print(f"Cloning latest version {self.name} into {self.deploy_location}")

        deploy_repo = Repo.init(self.deploy_location)
        deploy_origin = deploy_repo.create_remote("origin", self.origin.url)

        deploy_origin.fetch()
        deploy_repo.git.checkout(self.latest_version_str)

        print("Setting permissions")
        groups_to_give_permission = ["i03_staff", "gda2", "dls_dasc"]
        setfacl_params = ",".join(
            [f"g:{group}:rwx" for group in groups_to_give_permission]
        )

        # Set permissions and defaults
        os.system(f"setfacl -R -m {setfacl_params} {self.deploy_location}")
        os.system(f"setfacl -dR -m {setfacl_params} {self.deploy_location}")

    # Deploy location depends on the latest hyperion version (...software/bluesky/hyperion_V...)
    def set_deploy_location(self, release_area):
        self.deploy_location = os.path.join(release_area, self.name)
        if os.path.isdir(self.deploy_location):
            raise Exception(
                f"{self.deploy_location} already exists, stopping deployment for {self.name}"
            )


# Get the release directory based off the beamline and the latest hyperion version
def get_hyperion_release_dir_from_args() -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "beamline",
        type=str,
        choices=recognised_beamlines,
        help="The beamline to deploy hyperion to",
    )

    args = parser.parse_args()
    if args.beamline == "dev":
        print("Running as dev")
        return "/scratch/30day_tmp/hyperion_release_test/bluesky"
    else:
        return f"/dls_sw/{args.beamline}/software/bluesky"


if __name__ == "__main__":
    # Gives path to /bluesky
    release_area = get_hyperion_release_dir_from_args()

    this_repo_top = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    print(f"Repo top is {this_repo_top}")

    hyperion_repo = repo(
        name="hyperion",
        repo_args=os.path.join(this_repo_top, ".git"),
    )

    if hyperion_repo.name != "hyperion":
        raise ValueError("This function should only be used with the hyperion repo")

    release_area_version = os.path.join(
        release_area, f"hyperion_{hyperion_repo.latest_version_str}"
    )

    print(f"Putting releases into {release_area_version}")

    dodal_repo = repo(
        name="dodal",
        repo_args=os.path.join(this_repo_top, "../dodal/.git"),
    )

    dodal_repo.set_deploy_location(release_area_version)
    hyperion_repo.set_deploy_location(release_area_version)

    # Deploy hyperion repo
    hyperion_repo.deploy(hyperion_repo.origin.url)

    # Get version of dodal that latest hyperion version uses
    with open(f"{release_area_version}/hyperion/setup.cfg", "r") as setup_file:
        dodal_url = [
            line
            for line in setup_file
            if "https://github.com/DiamondLightSource/python-dodal" in line
        ]

    # Now deploy the correct version of dodal
    dodal_repo.deploy(dodal_url)

    # Set up environment and run /dls_dev_env.sh...
    os.chdir(hyperion_repo.deploy_location)
    print(f"Setting up environment in {hyperion_repo.deploy_location}")

    if hyperion_repo.name == "hyperion":
        env_script = os.path.join(
            hyperion_repo.deploy_location, "utility_scripts/dls_dev_env.sh"
        )
        with Popen(env_script, stdout=PIPE, bufsize=1, universal_newlines=True) as p:
            if p.stdout is not None:
                for line in p.stdout:
                    print(line, end="")

    if p.returncode != 0:
        raise CalledProcessError(p.returncode, p.args)

    def create_symlink_by_tmp_and_rename(dirname, target, linkname):
        tmp_name = str(uuid1())
        target_path = os.path.join(dirname, target)
        linkname_path = os.path.join(dirname, linkname)
        tmp_path = os.path.join(dirname, tmp_name)
        os.symlink(target_path, tmp_path)
        os.rename(tmp_path, linkname_path)

    move_symlink = input(
        """Move symlink (y/n)? WARNING: this will affect the running version!
Only do so if you have informed the beamline scientist and you're sure Hyperion is not running.
"""
    )
    # Creates symlinks: software/bluesky/hyperion_latest -> software/bluesky/hyperion_{version}/hyperion
    #                   software/bluesky/hyperion -> software/bluesky/hyperion_latest
    if move_symlink == "y":
        old_live_location = os.path.relpath(
            os.path.realpath(os.path.join(release_area, "hyperion")), release_area
        )
        make_live_stable_symlink = input(
            f"The last live deployment was {old_live_location}, do you want to set this as the stable version? (y/n)"
        )
        if make_live_stable_symlink == "y":
            create_symlink_by_tmp_and_rename(
                release_area, old_live_location, "hyperion_stable"
            )

        relative_deploy_loc = os.path.join(
            os.path.relpath(hyperion_repo.deploy_location, release_area)
        )
        create_symlink_by_tmp_and_rename(
            release_area, relative_deploy_loc, "hyperion_latest"
        )
        create_symlink_by_tmp_and_rename(release_area, "hyperion_latest", "hyperion")
        print(f"New version moved to {hyperion_repo.deploy_location}")
        print("To start this version run hyperion_restart from the beamline's GDA")
    else:
        print("Quitting without latest version being updated")
