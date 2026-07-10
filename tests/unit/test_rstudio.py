"""
Test RStudio Server version resolution
"""

from unittest.mock import patch

import pytest

from repo2docker.buildpacks._r_base import rstudio_base_scripts
from repo2docker.buildpacks._rstudio import (
    LEGACY_RSTUDIO_SHA256,
    LEGACY_RSTUDIO_URL,
    fetch_latest_rstudio_server,
    load_rstudio_yaml,
    rstudio_server_installer,
)

LATEST_URL = (
    "https://download2.rstudio.org/server/jammy/amd64/rstudio-server-latest-amd64.deb"
)
LATEST_SHA256 = "0" * 64


def downloads_json(installers):
    return {
        "rstudio": {"open_source": {"stable": {"server": {"installer": installers}}}}
    }


DOWNLOADS_JSON = downloads_json(
    {
        "jammy": {
            "url": LATEST_URL,
            "sha256": LATEST_SHA256,
            "platform": {"name": "Ubuntu 22/Debian 12", "key": "jammy"},
        },
        "noble": {
            "url": "https://example.com/noble.deb",
            "sha256": "1" * 64,
            "platform": {"name": "Ubuntu 24", "key": "noble"},
        },
    }
)


@pytest.fixture(autouse=True)
def clear_fetch_cache():
    fetch_latest_rstudio_server.cache_clear()
    yield
    fetch_latest_rstudio_server.cache_clear()


@pytest.mark.parametrize("r_version", ["3.3.3", "3.5.3", "3.5."])
def test_legacy_rstudio_for_old_r(r_version):
    assert rstudio_server_installer(r_version, None) == (
        LEGACY_RSTUDIO_URL,
        LEGACY_RSTUDIO_SHA256,
    )


@pytest.mark.parametrize("r_version", ["", "3.6", "4.2.1", "4.4."])
def test_latest_rstudio(r_version):
    with patch("repo2docker.buildpacks._rstudio.requests.get") as mock_get:
        mock_get.return_value.json.return_value = DOWNLOADS_JSON
        assert rstudio_server_installer(r_version, None) == (LATEST_URL, LATEST_SHA256)
        mock_get.assert_called_once()


def test_latest_rstudio_base_no_longer_supported():
    # Posit removes installer entries when an OS leaves their support window
    with patch("repo2docker.buildpacks._rstudio.requests.get") as mock_get:
        mock_get.return_value.json.return_value = downloads_json(
            {
                "noble": {
                    "url": "https://example.com/noble.deb",
                    "sha256": "1" * 64,
                    "platform": {"name": "Ubuntu 24", "key": "noble"},
                }
            }
        )
        with pytest.raises(ValueError, match="support window"):
            rstudio_server_installer("4.2.1", None)


def test_latest_rstudio_ambiguous_match():
    with patch("repo2docker.buildpacks._rstudio.requests.get") as mock_get:
        mock_get.return_value.json.return_value = downloads_json(
            {
                "jammy": {
                    "url": LATEST_URL,
                    "sha256": LATEST_SHA256,
                    "platform": {"name": "Ubuntu 22/Debian 12", "key": "jammy"},
                },
                "ubuntu22": {
                    "url": "https://example.com/other.deb",
                    "sha256": "2" * 64,
                    "platform": {"name": "Ubuntu 22 (server)", "key": "ubuntu22"},
                },
            }
        )
        with pytest.raises(ValueError, match="exactly one"):
            rstudio_server_installer("4.2.1", None)


@pytest.fixture
def pinned_version_exists():
    with patch("repo2docker.buildpacks._rstudio.requests.head") as mock_head:
        mock_head.return_value.status_code = 200
        yield mock_head


def test_pinned_rstudio(pinned_version_exists):
    url, sha256 = rstudio_server_installer("4.2.1", {"version": "2023.12.1+402"})
    assert url == (
        "https://download2.rstudio.org/server/jammy/amd64/rstudio-server-2023.12.1-402-amd64.deb"
    )
    assert sha256 is None


def test_pinned_rstudio_with_sha256(pinned_version_exists):
    config = {"version": "2023.12.1+402", "sha256": LEGACY_RSTUDIO_SHA256}
    assert rstudio_server_installer("4.2.1", config) == (
        LEGACY_RSTUDIO_URL,
        LEGACY_RSTUDIO_SHA256,
    )


def test_pinned_rstudio_overrides_legacy(pinned_version_exists):
    # explicit user pin wins over the old-R legacy fallback
    url, _ = rstudio_server_installer("3.5.3", {"version": "2026.06.0+242"})
    assert "2026.06.0-242" in url


def test_pinned_rstudio_requires_version():
    with pytest.raises(ValueError):
        rstudio_server_installer("4.2.1", {"sha256": LEGACY_RSTUDIO_SHA256})


def test_pinned_rstudio_unknown_version():
    with patch("repo2docker.buildpacks._rstudio.requests.head") as mock_head:
        mock_head.return_value.status_code = 404
        with pytest.raises(ValueError, match="does not exist"):
            rstudio_server_installer("4.2.1", {"version": "9999.99.9+999"})


@pytest.mark.parametrize(
    "version", ['2023.12.1"; rm -rf /; echo "', "2023.12.1 402", "$(reboot)"]
)
def test_pinned_rstudio_rejects_unsafe_version(version):
    with pytest.raises(ValueError, match="invalid RStudio version"):
        rstudio_server_installer("4.2.1", {"version": version})


@pytest.mark.parametrize(
    "sha256", ['x" /dev/null; reboot; echo "', "deadbeef", "2ceeebe5" * 9]
)
def test_pinned_rstudio_rejects_unsafe_sha256(sha256):
    with pytest.raises(ValueError, match="sha256"):
        rstudio_server_installer(
            "4.2.1", {"version": "2023.12.1+402", "sha256": sha256}
        )


def test_load_rstudio_yaml(tmpdir):
    assert load_rstudio_yaml(str(tmpdir / "rstudio.yml")) is None
    path = tmpdir / "rstudio.yml"
    path.write("version: 2023.12.1+402\n")
    assert load_rstudio_yaml(str(path))["version"] == "2023.12.1+402"


def test_build_script_verifies_sha256_when_pinned_with_hash(pinned_version_exists):
    config = {"version": "2023.12.1+402", "sha256": LEGACY_RSTUDIO_SHA256}
    user, script = rstudio_base_scripts("4.2.1", config)[0]
    assert f'echo "{LEGACY_RSTUDIO_SHA256} /tmp/rstudio.deb" | sha256sum -c -' in script


def test_build_script_skips_sha256_when_pinned_without_hash(pinned_version_exists):
    user, script = rstudio_base_scripts("4.2.1", {"version": "2023.12.1+402"})[0]
    assert "rstudio.deb" in script
    assert '/tmp/rstudio.deb" | sha256sum' not in script
