"""
Resolution of the RStudio Server version to install.

By default the latest stable release is resolved from Posit's
downloads.json at Dockerfile generation time, so that RStudio keeps up
with current R releases (newer R graphics engines require newer RStudio).

Users can pin a specific version with an `rstudio.yml` in their
repository:

    version: 2023.12.1+402
    sha256: 2ceeebe5...  # optional

Pinned versions are downloaded over HTTPS but only verified against
sha256 when the user provides one.
"""

import os
import re
from functools import lru_cache

import requests
from ruamel.yaml import YAML

from ..semver import parse_version as V

RSTUDIO_DOWNLOADS_URL = "https://www.rstudio.com/wp-content/downloads.json"

# Ubuntu major version of the base image (see Repo2Docker.base_image),
# matched against platform names in downloads.json ("Ubuntu 22/Debian 12").
# The version number is a more stable identity than Posit's series keys,
# whose naming conventions vary across their products.
RSTUDIO_UBUNTU_VERSION = "22"

# Ubuntu series segment of download2.rstudio.org paths, used to construct
# URLs for user-pinned versions without depending on downloads.json
RSTUDIO_UBUNTU_SERIES = "jammy"

# Current RStudio releases require R >= 3.6.0
# https://docs.posit.co/ide/desktop-pro/getting_started/prerequisites.html
RSTUDIO_MIN_R_VERSION = "3.6"

# Last release supporting R >= 3.3, for repos pinning R < 3.6
LEGACY_RSTUDIO_URL = "https://download2.rstudio.org/server/jammy/amd64/rstudio-server-2023.12.1-402-amd64.deb"
LEGACY_RSTUDIO_SHA256 = (
    "2ceeebe5d1d77068b36e85f7cf366cd1409f7642a80261b6bbeb3da945ef0888"
)


@lru_cache()
def fetch_latest_rstudio_server():
    """Return (url, sha256) of the latest stable RStudio Server .deb."""
    resp = requests.get(RSTUDIO_DOWNLOADS_URL, timeout=30)
    resp.raise_for_status()
    installers = resp.json()["rstudio"]["open_source"]["stable"]["server"]["installer"]
    matches = [
        entry
        for entry in installers.values()
        if re.search(rf"\bUbuntu {RSTUDIO_UBUNTU_VERSION}\b", entry["platform"]["name"])
    ]
    if len(matches) != 1:
        names = ", ".join(entry["platform"]["name"] for entry in installers.values())
        raise ValueError(
            f"could not find exactly one RStudio Server build for "
            f"Ubuntu {RSTUDIO_UBUNTU_VERSION} in {RSTUDIO_DOWNLOADS_URL} "
            f"(available: {names}); the base image may no longer be within "
            f"RStudio's support window"
        )
    return matches[0]["url"], matches[0]["sha256"]


def load_rstudio_yaml(path):
    """Return the parsed rstudio.yml, or None if it does not exist."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return YAML().load(f)


def parse_r_version(r_version):
    """Parse an R version pin; conda pins like "r-base=4.4.*" leave a trailing dot."""
    return V(r_version.rstrip("."))


def rstudio_server_installer(r_version, rstudio_config):
    """Return (url, sha256) of the RStudio Server .deb to install.

    sha256 is None when the user pinned a version without a hash.
    """
    if rstudio_config is not None:
        # rstudio.yml comes from the repository being built; these values end
        # up in root-executed build scripts, so validate them strictly
        if "version" not in rstudio_config:
            raise ValueError("rstudio.yml must contain a 'version' field")
        version = str(rstudio_config["version"]).replace("+", "-")
        if not re.fullmatch(r"[0-9A-Za-z.-]+", version):
            raise ValueError(
                f"invalid RStudio version in rstudio.yml: {rstudio_config['version']!r}"
            )
        sha256 = rstudio_config.get("sha256")
        if sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", str(sha256)):
            raise ValueError("sha256 in rstudio.yml must be a 64-character hex string")
        url = f"https://download2.rstudio.org/server/{RSTUDIO_UBUNTU_SERIES}/amd64/rstudio-server-{version}-amd64.deb"
        resp = requests.head(url, timeout=30)
        if resp.status_code != 200:
            raise ValueError(
                f"RStudio Server {rstudio_config['version']} specified in rstudio.yml "
                f"does not exist: {url} returned {resp.status_code}"
            )
        return url, sha256
    if r_version and parse_r_version(r_version) < V(RSTUDIO_MIN_R_VERSION):
        return LEGACY_RSTUDIO_URL, LEGACY_RSTUDIO_SHA256
    return fetch_latest_rstudio_server()
