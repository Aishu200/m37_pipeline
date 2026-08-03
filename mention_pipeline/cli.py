import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from mention_pipeline.batch import Batching
from mention_pipeline.concurrency import ConcurrentBatchProcessor
from mention_pipeline.create_mentions import CreateMentions
from mention_pipeline.deduplication import Deduplicator
from mention_pipeline.llm import MockLLMClient
from mention_pipeline.pipeline import MentionPipeline
from mention_pipeline.reconciliation import ResultReconciler
from mention_pipeline.report_generator import ReportGenerator
from mention_pipeline.retry import RetryHandler


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Process media mentions through the enrichment pipeline."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    enrich_parser = subparsers.add_parser(
        "enrich",
        help="Enrich media mentions.",
    )

    enrich_parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the input mentions JSON file.",
    )

    enrich_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path where the report JSON will be written.",
    )

    return parser



async def enrich(input_path: Path, output_path: Path) -> None:
    mentions = CreateMentions(
        file_location=str(input_path),
    ).process()

    batch_processor = ConcurrentBatchProcessor(
        client=MockLLMClient(),
        retry_handler=RetryHandler(),
    )

    pipeline = MentionPipeline(
        deduplicator=Deduplicator,
        batcher=Batching,
        batch_processor=batch_processor,
        reconciler=ResultReconciler,
        report_generator=ReportGenerator(),
    )

    report = await pipeline.run(mentions)

    report_data = asdict(report)

    report_data["generated_at"] = report.generated_at.isoformat()

    report_data["mentions"].sort(
        key=lambda mention: (
            mention["tenant_id"],
            mention["id"],
        )
    )

    output_path.write_text(
        json.dumps(
            report_data,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


# ====================================================== MAIN =================================================
def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "enrich":
        asyncio.run(
            enrich(
                input_path=args.input,
                output_path=args.output,
            )
        )
