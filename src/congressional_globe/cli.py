"""Command-line interface for local corpus construction and optional AI submission."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from congressional_globe.ai import prepare_batch, reconcile_batch, submit_batch
from congressional_globe.benchmarking import run_benchmark
from congressional_globe.cleanup import export_results, run_database, run_jobs
from congressional_globe.inventory import PARTS
from congressional_globe.pipeline import (
    build_rag,
    build_rag_from_pages,
    extract_identifier,
    merge_normalized_paragraphs,
    write_inventory,
)
from congressional_globe.planning import estimate, load_summary
from congressional_globe.providers import (
    CleanupProvider,
    OllamaProvider,
    OpenAIResponsesProvider,
)
from congressional_globe.static_cleanup import normalize_jsonl
from congressional_globe.storage import (
    CleanupJob,
    create_run,
    job_by_id,
    retry_review_jobs,
    run_summary,
)
from congressional_globe.workflow import run_static_first


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
        "benchmark": _benchmark,
        "estimate": _estimate,
        "export-rag": _export_rag,
        "prepare-ai": _prepare_ai,
        "submit-batch": _submit_batch,
        "reconcile-ai": _reconcile_ai,
        "cleanup": _cleanup,
        "static-cleanup": _static_cleanup,
        "static-first": _static_first,
    }


def _inventory(arguments: argparse.Namespace, root: Path) -> None:
    write_inventory(root, Path(arguments.output), arguments.hashes)


def _extract(arguments: argparse.Namespace, root: Path) -> None:
    extract_identifier(root, Path(arguments.output), arguments.identifier)


def _build_rag(arguments: argparse.Namespace, root: Path) -> None:
    build_rag(root, Path(arguments.output), arguments.run_id, arguments.single_json)


def _benchmark(arguments: argparse.Namespace, _: Path) -> None:
    provider = _benchmark_provider(arguments)
    summary = run_benchmark(
        Path(arguments.cases),
        provider,
        backend=arguments.backend,
        model=arguments.model,
        run_id=arguments.run_id,
        limit=arguments.limit,
        artifacts_dir=Path(arguments.output),
    )
    print(summary.model_dump_json())


def _benchmark_provider(arguments: argparse.Namespace) -> CleanupProvider:
    if arguments.backend == "ollama":
        return OllamaProvider(arguments.model, arguments.base_url, arguments.timeout)
    return OpenAIResponsesProvider(arguments.model, arguments.timeout)


def _estimate(arguments: argparse.Namespace, _: Path) -> None:
    summary = load_summary(Path(arguments.summary))
    projection = estimate(
        summary,
        arguments.jobs,
        input_usd_per_million=arguments.input_rate,
        output_usd_per_million=arguments.output_rate,
        retry_fraction=arguments.retry_fraction,
    )
    print(projection.model_dump_json(indent=2))


def _export_rag(arguments: argparse.Namespace, _: Path) -> None:
    pages = Path(arguments.pages)
    paragraphs = Path(arguments.paragraphs)
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    canonical_pages = output / "canonical_pages.jsonl"
    chunks = output / "chunks.jsonl"
    _reject_cli_output_aliases(chunks, (pages, paragraphs))
    page_count = merge_normalized_paragraphs(pages, paragraphs, canonical_pages)
    chunk_count = build_rag_from_pages(canonical_pages, chunks)
    print(
        json.dumps(
            {
                "canonical_pages": str(canonical_pages),
                "pages": page_count,
                "chunks": str(chunks),
                "chunk_count": chunk_count,
            },
            sort_keys=True,
        )
    )


def _reject_cli_output_aliases(output: Path, sources: tuple[Path, ...]) -> None:
    for source in sources:
        same_path = output.resolve() == source.resolve()
        same_file = output.exists() and source.exists() and output.samefile(source)
        if same_path or same_file:
            raise ValueError(f"Output path aliases an input file: {source}")


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


def _static_first(arguments: argparse.Namespace, root: Path) -> None:
    report = run_static_first(
        root,
        arguments.run_id,
        Path(arguments.lexicon),
        output_root=Path(arguments.output_root),
        page_limit=arguments.page_limit,
        backend=arguments.backend,
        model=arguments.model,
        ai_limit=arguments.ai_limit,
        plan_only=arguments.plan_only,
        benchmark_summary_path=(
            Path(arguments.benchmark_summary) if arguments.benchmark_summary else None
        ),
        input_usd_per_million=arguments.input_rate,
        output_usd_per_million=arguments.output_rate,
        base_url=arguments.base_url,
        progress_interval=arguments.progress_interval,
    )
    print(json.dumps(report, sort_keys=True))


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
    _benchmark_command(commands)
    _estimate_command(commands)
    _export_rag_command(commands)
    _prepare_command(commands)
    _submit_command(commands)
    _reconcile_command(commands)
    _cleanup_command(commands)
    _static_cleanup_command(commands)
    _static_first_command(commands)
    return parser


def _static_cleanup_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("static-cleanup")
    command.add_argument("--paragraphs", required=True)
    command.add_argument("--lexicon", required=True)
    command.add_argument("--output", required=True)


def _static_first_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser(
        "static-first", help="Build a provenance-first static cleanup run across all five parts"
    )
    _root_argument(command)
    command.add_argument("--run-id", required=True)
    command.add_argument("--lexicon", required=True)
    command.add_argument("--output-root", default="artifacts/runs")
    command.add_argument("--page-limit", type=int)
    command.add_argument("--plan-only", action="store_true")
    command.add_argument("--backend", choices=("none", "ollama", "openai"), default="none")
    command.add_argument("--model")
    command.add_argument("--ai-limit", type=int)
    command.add_argument("--benchmark-summary")
    command.add_argument("--input-rate", type=float)
    command.add_argument("--output-rate", type=float)
    command.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    command.add_argument("--progress-interval", type=int, default=30)


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


def _benchmark_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser(
        "benchmark", help="Run an explicit small-sample provider benchmark"
    )
    command.add_argument("--cases", required=True)
    command.add_argument("--backend", choices=("ollama", "openai"), default="ollama")
    command.add_argument("--model", required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument("--limit", type=int, default=6)
    command.add_argument("--timeout", type=float, default=45)
    command.add_argument("--base-url", default="http://localhost:11434/v1")
    command.add_argument("--output", default="artifacts/benchmarks")


def _estimate_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("estimate", help="Project time and API cost without model calls")
    command.add_argument("--summary", required=True)
    command.add_argument("--jobs", type=int, required=True)
    command.add_argument("--input-rate", type=float)
    command.add_argument("--output-rate", type=float)
    command.add_argument("--retry-fraction", type=float, default=0)


def _export_rag_command(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    command = commands.add_parser("export-rag")
    command.add_argument("--pages", required=True)
    command.add_argument("--paragraphs", required=True)
    command.add_argument("--output", required=True)


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
