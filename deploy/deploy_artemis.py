import argparse
import os
from subprocess import PIPE, CalledProcessError, Popen

from git import Repo
from packaging.version import Version

recognised_beamlines = ["dev", "i03"]


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

    # Deploy location depends on the latest artemis version (...software/bluesky/artemis_V...)
    def set_deploy_location(self, release_area):
        self.deploy_location = os.path.join(release_area, self.name)
        if os.path.isdir(self.deploy_location):
            raise Exception(
                f"{self.deploy_location} already exists, stopping deployment for {self.name}"
            )


# Get the release directory based off the beamline and the latest artemis version
def get_artemis_release_dir_from_args(repo: repo) -> str:
    if repo.name != "artemis":
        raise ValueError("This function should only be used with the artemis repo")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "beamline",
        type=str,
        choices=recognised_beamlines,
        help="The beamline to deploy artemis to",
    )

    args = parser.parse_args()
    if args.beamline == "dev":
        print("Running as dev")
        return "/tmp/artemis_release_test/bluesky"
    elif args.beamline == "i03":
        return f"/dls_sw/{args.beamline}/software/bluesky"
    else:
        raise Exception("not running in dev mode, exiting... (remove this)")


if __name__ == "__main__":
    artemis_repo = repo(
        name="artemis",
        repo_args=os.path.join(os.path.dirname(__file__), "../.git"),
    )

    # Gives path to /bluesky
    release_area = get_artemis_release_dir_from_args(artemis_repo)

    release_area_version = os.path.join(
        release_area, f"artemis_{artemis_repo.latest_version_str}"
    )

    print(f"Putting releases into {release_area_version}")

    dodal_repo = repo(
        name="dodal",
        repo_args=os.path.join(os.path.dirname(__file__), "../../dodal/.git"),
    )

    dodal_repo.set_deploy_location(release_area_version)
    artemis_repo.set_deploy_location(release_area_version)

    # Deploy artemis repo
    artemis_repo.deploy(artemis_repo.origin.url)

    # Get version of dodal that latest artemis version uses
    with open(f"{release_area_version}/artemis/setup.cfg", "r") as setup_file:
        dodal_url = [
            line
            for line in setup_file
            if "https://github.com/DiamondLightSource/python-dodal" in line
        ]

    # Now deploy the correct version of dodal
    dodal_repo.deploy(dodal_url)

    # Set up environment and run /dls_dev_env.sh...
    os.chdir(artemis_repo.deploy_location)
    print(f"Setting up environment in {artemis_repo.deploy_location}")

    if artemis_repo.name == "artemis":
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
    # Creates symlink: software/bluesky/artemis_version -> software/bluesky/artemis
    if move_symlink == "y":
        live_location = os.path.join(release_area, "artemis")
        new_tmp_location = os.path.join(release_area, "tmp_art")
        os.symlink(artemis_repo.deploy_location, new_tmp_location)
        os.rename(new_tmp_location, live_location)
        print(f"New version moved to {live_location}")
        print("To start this version run artemis_restart from the beamline's GDA")
    else:
        print("Quiting without latest version being updated")
