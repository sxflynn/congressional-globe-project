"""Command-line interface for local corpus construction and optional AI submission."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from congressional_globe.ai import prepare_batch, reconcile_batch, submit_batch
from congressional_globe.cleanup import export_results, run_database, run_jobs
from congressional_globe.inventory import PARTS
from congressional_globe.pipeline import build_rag, extract_identifier, write_inventory
from congressional_globe.static_cleanup import normalize_jsonl
from congressional_globe.storage import (
    CleanupJob,
    create_run,
    job_by_id,
    retry_review_jobs,
    run_summary,
)


def main() -> None:
    load_dotenv()
    parser = _parser()
    arguments = parser.parse_args()
    root = Path(getattr(arguments, "root", ".")).resolve()
    _commands()[arguments.command](arguments, root)


CommandHandler = Callable[[argparse.Namespace, Path], None]


def _commands() -> dict[str, CommandHandler]:
    return {
        "inventory": _inventory,
        "extract": _extract,
        "build-rag": _build_rag,
        "prepare-ai": _prepare_ai,
        "submit-batch": _submit_batch,
        "reconcile-ai": _reconcile_ai,
        "cleanup": _cleanup,
        "static-cleanup": _static_cleanup,
    }


def _inventory(arguments: argparse.Namespace, root: Path) -> None:
    write_inventory(root, Path(arguments.output), arguments.hashes)


def _extract(arguments: argparse.Namespace, root: Path) -> None:
    extract_identifier(root, Path(arguments.output), arguments.identifier)


def _build_rag(arguments: argparse.Namespace, root: Path) -> None:
    build_rag(root, Path(arguments.output), arguments.run_id, arguments.single_json)


def _prepare_ai(arguments: argparse.Namespace, _: Path) -> None:
    prepare_batch(Path(arguments.paragraphs), Path(arguments.output), arguments.model)


def _submit_batch(arguments: argparse.Namespace, _: Path) -> None:
    submit_batch(Path(arguments.requests), Path(arguments.state_dir), arguments.confirm_submit)


def _reconcile_ai(arguments: argparse.Namespace, _: Path) -> None:
    reconcile_batch(
        Path(arguments.batch_output),
        Path(arguments.paragraphs),
        Path(arguments.output),
        Path(arguments.review_output),
    )


def _cleanup(arguments: argparse.Namespace, _: Path) -> None:
    _cleanup_handlers()[arguments.cleanup_command](arguments)


def _static_cleanup(arguments: argparse.Namespace, _: Path) -> None:
    count = normalize_jsonl(
        Path(arguments.paragraphs), Path(arguments.lexicon), Path(arguments.output)
    )
    print(json.dumps({"paragraphs": count, "output": arguments.output}))


CleanupHandler = Callable[[argparse.Namespace], None]


def _cleanup_handlers() -> dict[str, CleanupHandler]:
    return {
        "init": _cleanup_init_run,
        "run": _cleanup_run_jobs,
        "status": _cleanup_show_status,
        "export": _cleanup_export_results,
        "inspect": _cleanup_inspect_job,
        "retry": _cleanup_retry_review,
    }


def _cleanup_init_run(arguments: argparse.Namespace) -> None:
    run_directory = Path(arguments.run_directory)
    count = create_run(
        run_database(run_directory),
        arguments.run_id,
        Path(arguments.paragraphs),
        arguments.limit,
        arguments.scan_leaf,
        set(arguments.paragraph_id) if arguments.paragraph_id else None,
    )
    print(json.dumps({"run_id": arguments.run_id, "jobs_created": count}))


def _cleanup_run_jobs(arguments: argparse.Namespace) -> None:
    counts = run_jobs(
        Path(arguments.run_directory),
        arguments.run_id,
        arguments.backend,
        arguments.model,
        arguments.limit,
        arguments.base_url,
        arguments.progress_interval,
    )
    print(json.dumps(counts, sort_keys=True))


def _cleanup_show_status(arguments: argparse.Namespace) -> None:
    print(
        json.dumps(
            run_summary(run_database(Path(arguments.run_directory)), arguments.run_id),
            sort_keys=True,
        )
    )


def _cleanup_export_results(arguments: argparse.Namespace) -> None:
    count = export_results(Path(arguments.run_directory), arguments.run_id, Path(arguments.output))
    print(json.dumps({"exported": count, "output": arguments.output}))


def _cleanup_inspect_job(arguments: argparse.Namespace) -> None:
    job = job_by_id(
        run_database(Path(arguments.run_directory)), arguments.run_id, arguments.paragraph_id
    )
    print(json.dumps(_job_payload(job), indent=2))


def _cleanup_retry_review(arguments: argparse.Namespace) -> None:
    count = retry_review_jobs(run_database(Path(arguments.run_directory)), arguments.run_id)
    print(json.dumps({"run_id": arguments.run_id, "jobs_requeued": count}))


def _job_payload(job: CleanupJob | None) -> dict[str, object]:
    if job is None:
        raise ValueError("No matching paragraph in this run")
    return {column.name: getattr(job, column.name) for column in job.__table__.columns}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="globe")
    commands = parser.add_subparsers(dest="command", required=True)
    _inventory_command(commands)
    _extract_command(commands)
    _build_command(commands)
    _prepare_command(commands)
    _submit_command(commands)
    _reconcile_command(commands)
    _cleanup_command(commands)
    _static_cleanup_command(commands)
    return parser


def _static_cleanup_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("static-cleanup")
    command.add_argument("--paragraphs", required=True)
    command.add_argument("--lexicon", required=True)
    command.add_argument("--output", required=True)


def _inventory_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("inventory")
    _root_argument(command)
    command.add_argument("--output", default="artifacts/inventory.json")
    command.add_argument("--hashes", action="store_true")


def _extract_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("extract")
    _root_argument(command)
    command.add_argument("--identifier", choices=PARTS, required=True)
    command.add_argument("--output", default="artifacts/extraction")


def _build_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("build-rag")
    _root_argument(command)
    command.add_argument("--run-id", required=True)
    command.add_argument("--output", default="artifacts")
    command.add_argument("--single-json", action="store_true")


def _prepare_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("prepare-ai")
    command.add_argument("--paragraphs", required=True)
    command.add_argument("--output", required=True)
    command.add_argument("--model", required=True)


def _submit_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("submit-batch")
    command.add_argument("--requests", required=True)
    command.add_argument("--state-dir", default="artifacts/ai-runs")
    command.add_argument("--confirm-submit", action="store_true")


def _reconcile_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("reconcile-ai")
    command.add_argument("--batch-output", required=True)
    command.add_argument("--paragraphs", required=True)
    command.add_argument("--output", required=True)
    command.add_argument("--review-output", required=True)


def _cleanup_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("cleanup")
    subcommands = command.add_subparsers(dest="cleanup_command", required=True)
    _cleanup_init(subcommands)
    _cleanup_run(subcommands)
    _cleanup_status(subcommands)
    _cleanup_export(subcommands)
    _cleanup_inspect(subcommands)
    _cleanup_retry(subcommands)


def _cleanup_init(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("init")
    _cleanup_shared(command)
    command.add_argument("--paragraphs", required=True)
    command.add_argument("--limit", type=int)
    command.add_argument("--scan-leaf", type=int)
    command.add_argument("--paragraph-id", action="append")


def _cleanup_run(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("run")
    _cleanup_shared(command)
    command.add_argument("--backend", choices=("ollama", "openai"), default="ollama")
    command.add_argument("--model", required=True)
    command.add_argument("--limit", type=int, default=1)
    command.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    command.add_argument("--progress-interval", type=int, default=30)


def _cleanup_status(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("status")
    _cleanup_shared(command)


def _cleanup_export(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("export")
    _cleanup_shared(command)
    command.add_argument("--output", required=True)


def _cleanup_inspect(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("inspect")
    _cleanup_shared(command)
    command.add_argument("--paragraph-id", required=True)


def _cleanup_retry(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("retry")
    _cleanup_shared(command)


def _cleanup_shared(command: argparse.ArgumentParser) -> None:
    command.add_argument("--run-directory", required=True)
    command.add_argument("--run-id", required=True)


def _root_argument(command: argparse.ArgumentParser) -> None:
    command.add_argument("--root", default=".")
