#!/usr/bin/env python3
"""Build an isolated ReplicatorBench execution input from a Codex workspace."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from normalize_rb_replication_info import normalize_metadata, read_json


REQUIRED_TASK_FILES = (
    "initial_details.txt",
    "original_paper.pdf",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create an isolated RB input directory containing only task "
            "materials, Codex-generated executables, dependencies, and "
            "normalized replication metadata."
        )
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Codex workspace containing task_input and generated artifacts",
    )
    parser.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Official RB Python preregistration schema",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination directory for the isolated RB input",
    )
    return parser.parse_args()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required file does not exist: {path}")


def executable_filenames(metadata: dict[str, Any]) -> list[str]:
    study = metadata.get("replication_study")
    if not isinstance(study, dict):
        raise ValueError("Input metadata must contain replication_study")

    codebase = study.get("codebase")
    if not isinstance(codebase, dict):
        raise ValueError("Input metadata must contain replication_study.codebase")

    files = codebase.get("files")

    if isinstance(files, dict):
        names = list(files.keys())
    elif isinstance(files, list):
        names = files
    else:
        raise ValueError(
            "replication_study.codebase.files must be a list or object"
        )

    normalized: list[str] = []

    for value in names:
        filename = str(value).strip()

        if not filename:
            continue

        relative = Path(filename)

        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe executable path in metadata: {filename}")

        normalized.append(filename)

    if not normalized:
        raise ValueError("No executable files were listed in codebase.files")

    return normalized


def copy_file(source: Path, destination: Path) -> None:
    require_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build_rb_input(
    workspace: Path,
    template_path: Path,
    output: Path,
) -> None:
    workspace = workspace.resolve()
    template_path = template_path.resolve()
    output = output.resolve()

    if not workspace.is_dir():
        raise FileNotFoundError(f"Workspace does not exist: {workspace}")

    if output == workspace or workspace in output.parents:
        if output.name != "rb_input":
            raise ValueError(
                "Output inside the workspace must use the dedicated "
                "'rb_input' directory name"
            )

    task_input = workspace / "task_input"
    replication_data = task_input / "replication_data"
    rich_metadata_path = workspace / "replication_info_rb.json"
    standard_metadata_path = workspace / "replication_info.json"

    # Historical runs may contain a richer preregistration under the alternate
    # filename. Future prompt-compliant runs should use replication_info.json.
    generated_metadata_path = (
        rich_metadata_path
        if rich_metadata_path.is_file()
        else standard_metadata_path
    )

    require_file(template_path)
    require_file(generated_metadata_path)

    if not replication_data.is_dir():
        raise FileNotFoundError(
            f"Replication data directory does not exist: {replication_data}"
        )

    generated_metadata = read_json(generated_metadata_path)
    template = read_json(template_path)
    normalized_metadata = normalize_metadata(generated_metadata, template)

    # Derive executable paths from the repaired metadata, not from malformed
    # historical Codex output such as {"file_name": "..."}.
    executables = executable_filenames(normalized_metadata)

    if output.exists():
        shutil.rmtree(output)

    output.mkdir(parents=True)

    for filename in REQUIRED_TASK_FILES:
        copy_file(task_input / filename, output / filename)

    optional_post_registration = task_input / "post_registration.json"
    if optional_post_registration.is_file():
        copy_file(optional_post_registration, output / "post_registration.json")

    # RB execution scripts may retain the original task_input-relative path,
    # while the execution evaluator expects replication_data at the input root.
    root_data = output / "replication_data"
    task_data = output / "task_input" / "replication_data"
    shutil.copytree(replication_data, root_data)
    shutil.copytree(replication_data, task_data)

    for filename in executables:
        copy_file(workspace / filename, output / filename)

    requirements = workspace / "requirements.txt"
    if requirements.is_file():
        copy_file(requirements, output / "requirements.txt")

    (output / "replication_info.json").write_text(
        json.dumps(normalized_metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Built isolated RB input: {output}")
    print("Included files:")

    for path in sorted(output.rglob("*")):
        if path.is_file():
            print(f"  {path.relative_to(output)}")


def main() -> None:
    args = parse_args()
    build_rb_input(
        workspace=args.workspace,
        template_path=args.template,
        output=args.output,
    )


if __name__ == "__main__":
    main()
