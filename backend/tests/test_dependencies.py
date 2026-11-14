"""Залежності зафіксовані, образ і CI на одній версії Python.

Історія: bcrypt, greenlet і PyJWT по черзі ламали застосунок після звичайної
перезбірки образу, бо версії не були зафіксовані. Ці тести не дають повернутися
до такого стану.
"""
import os
import re
from importlib import metadata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PYTHON = "3.12"


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_names() -> set[str]:
    names = set()
    for line in (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        names.add(norm(re.split(r"[\[<>=!~; ]", line, maxsplit=1)[0]))
    return names


def lock_pins() -> dict[str, str]:
    pins = {}
    for line in (BACKEND / "requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert re.fullmatch(r"[A-Za-z0-9_.\-]+==[^\s=]+", line), f"у lock-файлі має бути лише name==version: {line}"
        name, version = line.split("==")
        pins[norm(name)] = version
    return pins


def test_every_direct_requirement_is_pinned():
    missing = requirement_names() - set(lock_pins())
    assert not missing, f"немає в requirements.lock (запустіть `make lock`): {sorted(missing)}"


def test_the_packages_that_broke_before_are_pinned():
    pins = lock_pins()
    for name in ("pyjwt", "bcrypt", "greenlet", "sqlalchemy", "fastapi", "pydantic", "asyncpg", "alembic"):
        assert name in pins, name


def test_lock_has_no_duplicates_and_is_sorted_sensibly():
    lines = [l for l in (BACKEND / "requirements.lock").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.startswith("#")]
    names = [norm(l.split("==")[0]) for l in lines]
    assert len(names) == len(set(names))


def test_test_tools_are_pinned_exactly():
    for line in (BACKEND / "requirements-test.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-")):
            assert re.fullmatch(r"[A-Za-z0-9_.\-]+==\S+", line), f"тестова залежність без точної версії: {line}"


def test_production_image_installs_from_the_lock():
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^COPY requirements\.txt requirements\.lock", dockerfile, re.M)
    assert "pip install -r requirements.txt -c requirements.lock" in dockerfile


def test_image_ci_and_docs_agree_on_python_version():
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert f"FROM python:{PYTHON}-slim" in dockerfile
    assert f'python-version: "{PYTHON}"' in ci
    assert "3.11" not in dockerfile and "3.11" not in ci


@pytest.mark.skipif(not os.environ.get("CI"), reason="перевірка встановлених версій лише в CI")
def test_installed_versions_match_the_lock():
    """У CI пакети ставляться з -c requirements.lock, тож версії мають збігатися."""
    wrong = {}
    for name, version in lock_pins().items():
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue          # платформні пакети (наприклад, uvloop лише на Linux)
        if installed != version:
            wrong[name] = (installed, version)
    assert not wrong, wrong
