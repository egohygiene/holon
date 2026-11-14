#!/usr/bin/env python3
"""Prepare/check immutable source archives; never choose or publish a release.

Release declaration semantics remain with the checksum-pinned Aether reference
tool. This adapter selects reviewed Git objects and verifies complete bytes.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "catalog/distribution-candidate.json"
MAX_BYTES = 20 * 1024 * 1024
MAX_FILES = 1024
MANIFEST = "holon/DISTRIBUTION.json"


class CandidateError(ValueError):
    """The selected source or archive is not the exact declared candidate."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def object_json(data: bytes) -> dict:
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CandidateError("duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(CandidateError("non-finite JSON")))
    if not isinstance(value, dict):
        raise CandidateError("JSON root must be an object")
    return value


def safe_path(value: str) -> str:
    if (not isinstance(value, str) or not value or "\\" in value
            or any(part in {"", ".", "..", ".git"} for part in value.split("/"))
            or PurePosixPath(value).is_absolute() or re.search(r"[\x00-\x20\x7f]", value)):
        raise CandidateError("unsafe candidate path")
    return value


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(ROOT), *arguments],
                                   stderr=subprocess.PIPE)


def prepare(source: str, output: Path) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise CandidateError("source must be one full immutable commit")
    if git("rev-parse", source + "^{commit}").decode().strip() != source:
        raise CandidateError("source does not identify the exact commit")
    if git("show", source + ":tools/distribution_candidate.py") != Path(__file__).read_bytes():
        raise CandidateError("running preparer differs from selected immutable source")
    profile_bytes = git("show", source + ":" + PROFILE)
    profile = object_json(profile_bytes)
    if profile.get("status") != "candidate-only" or profile.get("repository") != "egohygiene/holon":
        raise CandidateError("source does not declare this unreleased candidate")
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)-rc\.(?:0|[1-9][0-9]*)", profile.get("version", "")):
        raise CandidateError("version must be an explicit safe release-candidate identifier")
    selected = [safe_path(path) for path in profile["included_paths"]]
    if len(selected) != len(set(selected)):
        raise CandidateError("duplicate source selection")
    listing = git("ls-tree", "-rz", "--full-tree", source, "--", *selected)
    files = {}
    for row in listing.split(b"\0"):
        if not row:
            continue
        metadata, path_bytes = row.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        path = safe_path(path_bytes.decode())
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise CandidateError("source contains a symlink, submodule or unsupported mode")
        if not any(path == item or path.startswith(item + "/") for item in selected):
            raise CandidateError("source escaped its finite selection")
        files[path] = (git("cat-file", "blob", blob), int(mode[-3:], 8))
    if any(not any(path == item or path.startswith(item + "/") for path in files) for item in selected):
        raise CandidateError("declared archive input is missing")
    if not files or len(files) > MAX_FILES or sum(len(data) for data, _ in files.values()) > MAX_BYTES:
        raise CandidateError("candidate exceeds declared bounds")
    manifest = {"schema": "holon.distribution-archive/v1", "repository": profile["repository"],
                "source_commit": source, "version": profile["version"], "status": "candidate-only",
                "profile_sha256": digest(profile_bytes), "interfaces": profile["interfaces"],
                "supported_environments": profile["supported_environments"], "exclusions": profile["exclusions"],
                "files": {path: {"sha256": digest(data), "bytes": len(data), "mode": f"{mode:04o}"}
                          for path, (data, mode) in sorted(files.items())}}
    raw = io.BytesIO()
    epoch = int(git("show", "-s", "--format=%ct", source).decode().strip())
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path, (data, mode) in sorted({**{"holon/" + path: item for path, item in files.items()},
                                        MANIFEST: (canonical(manifest), 0o644)}.items()):
            entry = tarfile.TarInfo(path)
            entry.size, entry.mode, entry.mtime = len(data), mode, epoch
            archive.addfile(entry, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=compressed, mode="wb", mtime=0, compresslevel=9) as stream:
        stream.write(raw.getvalue())
    filename = f"holon-{profile['version']}-{source[:12]}.tar.gz"
    receipt = {"schema": "holon.distribution-candidate-receipt/v1", "repository": "egohygiene/holon",
               "source_commit": source, "version": profile["version"], "status": "candidate-only",
               "archive": filename, "archive_sha256": digest(compressed.getvalue()),
               "tar_sha256": digest(raw.getvalue()), "manifest_sha256": digest(canonical(manifest)),
               "files": len(files), "publication": "not-performed"}
    output = output.absolute()
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise CandidateError("output cannot traverse a symlink")
    if output == ROOT or ROOT in output.parents:
        raise CandidateError("candidate output must remain outside the source checkout")
    output.mkdir(parents=True, exist_ok=False)
    (output / filename).write_bytes(compressed.getvalue())
    (output / "candidate.json").write_bytes(canonical(receipt))
    return receipt


def verify(archive_path: Path, expected_sha256: str, extract: Path | None = None) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise CandidateError("an independently retained archive digest is required")
    if archive_path.is_symlink() or not archive_path.is_file() or archive_path.stat().st_size > MAX_BYTES:
        raise CandidateError("candidate archive is unavailable or exceeds bounds")
    packed = archive_path.read_bytes()
    if digest(packed) != expected_sha256:
        raise CandidateError("candidate archive digest mismatch")
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise CandidateError("expanded archive exceeds bounds")
    contents = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for entry in archive:
            path = safe_path(entry.name)
            if (not entry.isfile() or not path.startswith("holon/") or path in contents
                    or entry.mode not in {0o644, 0o755} or entry.size > MAX_BYTES
                    or len(contents) >= MAX_FILES + 1):
                raise CandidateError("archive has an unsupported or duplicate member")
            stream = archive.extractfile(entry)
            assert stream is not None
            contents[path] = (stream.read(), entry.mode)
        if any(raw[archive.offset:]):
            raise CandidateError("archive has undeclared trailing payload")
    if MANIFEST not in contents:
        raise CandidateError("archive manifest is missing")
    manifest = object_json(contents[MANIFEST][0])
    if (manifest.get("schema") != "holon.distribution-archive/v1"
            or manifest.get("repository") != "egohygiene/holon" or manifest.get("status") != "candidate-only"
            or not re.fullmatch(r"[0-9a-f]{40}", manifest.get("source_commit", ""))):
        raise CandidateError("archive is not a scoped immutable Holon candidate")
    expected_files = manifest.get("files")
    if not isinstance(expected_files, dict) or set(contents) != {MANIFEST, *("holon/" + safe_path(p) for p in expected_files)}:
        raise CandidateError("archive inventory differs from complete manifest")
    for path, record in expected_files.items():
        data, mode = contents["holon/" + path]
        if record != {"sha256": digest(data), "bytes": len(data), "mode": f"{mode:04o}"}:
            raise CandidateError("archive payload differs from declared bytes")
    profile = object_json(contents["holon/" + PROFILE][0])
    if (digest(contents["holon/" + PROFILE][0]) != manifest["profile_sha256"]
            or profile["version"] != manifest["version"] or profile["interfaces"] != manifest["interfaces"]
            or profile["exclusions"] != manifest["exclusions"]):
        raise CandidateError("archive scope differs from its source authority")
    if extract is not None:
        extract = extract.absolute()
        if any(path.is_symlink() for path in (extract, *extract.parents)) or extract.exists():
            raise CandidateError("extraction needs a new directory without symlink ancestors")
        # Every entry and byte is admitted before creating a destination.
        extract.mkdir(parents=True)
        for path, (data, mode) in sorted(contents.items()):
            destination = extract / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(data)
            destination.chmod(mode)
    return {"source_commit": manifest["source_commit"], "archive_sha256": digest(packed),
            "manifest_sha256": digest(contents[MANIFEST][0]), "files": len(expected_files),
            "status": "candidate-only", "publication": "not-performed"}


def verify_inputs(source: Path) -> dict:
    lock = object_json((ROOT / PROFILE).read_bytes())["preparation_inputs"]["aether"]
    for item in lock["files"]:
        path = source / safe_path(item["path"])
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != item["sha256"]:
            raise CandidateError("Aether reference input differs from its immutable lock")
    return {"repository": lock["repository"], "revision": lock["revision"], "files": lock["files"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("prepare")
    build.add_argument("--source-commit", required=True)
    build.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--archive", type=Path, required=True)
    check.add_argument("--sha256", required=True)
    check.add_argument("--extract", type=Path)
    inputs = sub.add_parser("verify-inputs")
    inputs.add_argument("--aether-source", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = (prepare(args.source_commit, args.output) if args.command == "prepare" else
                  verify(args.archive, args.sha256, args.extract) if args.command == "verify" else
                  verify_inputs(args.aether_source))
        print(json.dumps(result, sort_keys=True))
    except (CandidateError, OSError, ValueError, KeyError, subprocess.CalledProcessError, tarfile.TarError) as error:
        parser.exit(1, f"candidate refused: {error}\n")


if __name__ == "__main__":
    main()
