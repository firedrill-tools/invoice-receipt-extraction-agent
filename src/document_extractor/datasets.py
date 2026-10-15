"""Digest-checked PDF inputs; listing never starts a model run."""

from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .extract import load_pdf
from .models import Contract, DatasetSelection

_packaged = Path(__file__).with_name("sample_data") / "manifest.json"
DEFAULT_MANIFEST = _packaged if _packaged.exists() else Path(__file__).resolve().parents[2] / "data/manifest.json"


class Case(Contract):
    case_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pages: int = Field(ge=1)


class Profile(Contract):
    name: Literal["starter", "busy", "ambiguous", "boundary"]
    cases: list[Case] = Field(min_length=1)


class Manifest(Contract):
    dataset_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    profiles: list[Profile]

    @model_validator(mode="after")
    def unique_population(self):
        if sorted(profile.name for profile in self.profiles) != ["ambiguous", "boundary", "busy", "starter"]:
            raise ValueError("Manifest needs each of the four profiles exactly once")
        cases = [case for profile in self.profiles for case in profile.cases]
        if len({case.case_id for case in cases}) != len(cases) or len({case.path for case in cases}) != len(cases):
            raise ValueError("Case identities and source paths must be unique")
        return self


def load_manifest(path: Path = DEFAULT_MANIFEST) -> Manifest:
    with path.open("rb") as source:
        data = source.read(128 * 1024 + 1)
    if len(data) > 128 * 1024:
        raise ValueError("Manifest exceeds 128 KiB")
    return Manifest.model_validate_json(data)


def _source(root: Path, case: Case) -> tuple[Path, bytes]:
    path = (root / case.path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Dataset PDF must remain inside its manifest directory")
    data = load_pdf(path)
    if sha256(data).hexdigest() != case.sha256:
        raise ValueError(f"Dataset digest mismatch for {case.case_id}; qualify a new version")
    return path, data


def select_case(case_id: str, path: Path = DEFAULT_MANIFEST) -> tuple[Path, bytes, DatasetSelection]:
    manifest = load_manifest(path)
    for profile in manifest.profiles:
        for case in profile.cases:
            if case.case_id == case_id:
                source, data = _source(path.parent.resolve(), case)
                return source, data, DatasetSelection(dataset_id=manifest.dataset_id, version=manifest.version,
                    profile=profile.name, case_id=case.case_id, source_sha256=case.sha256)
    raise ValueError(f"Dataset case not found: {case_id}")


def describe_cases(path: Path = DEFAULT_MANIFEST) -> dict:
    manifest = load_manifest(path)
    for profile in manifest.profiles:
        for case in profile.cases:
            _source(path.parent.resolve(), case)
    return {"dataset_id": manifest.dataset_id, "version": manifest.version,
            "case_count": sum(len(profile.cases) for profile in manifest.profiles),
            "profiles": [{"name": profile.name, "case_ids": [case.case_id for case in profile.cases]}
                         for profile in manifest.profiles]}
