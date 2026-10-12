"""Offline trusted human subject-review import checks."""

import hashlib
import json
from pathlib import Path

import pytest

from congressional_globe.subject_review import (
    build_subject_review_template,
    import_subject_reviews,
)
from congressional_globe.subjects import SubjectDefinition, SubjectVocabulary


def _fixture(tmp_path: Path) -> tuple[Path, Path, str, str]:
    sample = tmp_path / "sample"
    sample.mkdir()
    vocabulary = SubjectVocabulary(
        version="draft-1",
        definitions=[
            SubjectDefinition(subject_id="subj.tax", label="Taxation", scope="Tax policy")
        ],
    )
    (sample / "vocabulary.json").write_text(vocabulary.model_dump_json(), encoding="utf-8")
    packet = {
        "window_id": "window-1",
        "item_identifier": "globe39part1",
        "part_number": 1,
        "scan_leaf": 12,
        "hocr_page_id": "page_12",
        "printed_page": {"detected": "42", "inferred": None, "source": "unknown"},
        "human_review_status": "pending",
        "human_subject_labels": None,
        "paragraphs": [
            {
                "paragraph_id": "p-1",
                "raw_text": "Debate on taxation continued.",
                "raw_text_sha256": hashlib.sha256(b"Debate on taxation continued.").hexdigest(),
                "hocr_line_ids": ["line-1"],
                "bbox": None,
            }
        ],
    }
    packet_path = sample / "review_packets.jsonl"
    packet_path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
    packet_digest = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    manifest = {
        "review_packets_sha256": packet_digest,
        "vocabulary_digest": vocabulary.digest,
        "vocabulary_version": vocabulary.version,
    }
    (sample / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return sample, tmp_path / "reviews.jsonl", packet_digest, vocabulary.digest


def _review(packet_digest: str, vocabulary_digest: str) -> dict:
    return {
        "window_id": "window-1",
        "packet_sha256": packet_digest,
        "vocabulary_digest": vocabulary_digest,
        "decision": "subjects",
        "reviewer_id": "reviewer-1",
        "reviewed_at": "2026-10-12T14:00:00Z",
        "note": "Substantive discussion is present.",
        "subjects": [
            {
                "subject_id": "subj.tax",
                "decision": "in_scope",
                "note": "The issue is discussed directly.",
                "evidence": [
                    {
                        "paragraph_id": "p-1",
                        "start_char": 10,
                        "end_char": 18,
                        "quote": "taxation",
                    }
                ],
            }
        ],
    }


def test_import_emits_separate_bound_human_labels(tmp_path: Path) -> None:
    sample, reviews, packet_digest, vocabulary_digest = _fixture(tmp_path)
    reviews.write_text(json.dumps(_review(packet_digest, vocabulary_digest)) + "\n")
    output = tmp_path / "accepted.jsonl"
    report = import_subject_reviews(sample, reviews, output)
    item = json.loads(output.read_text())
    assert report.windows_imported == 1
    assert report.output_sha256 == hashlib.sha256(output.read_bytes()).hexdigest()
    assert item["decision"] == "subjects"
    assert item["subjects"][0]["evidence"][0]["quote"] == "taxation"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: {**row, "packet_sha256": "0" * 64}, "digest mismatch"),
        (lambda row: {**row, "window_id": "wrong"}, "exhaustively match"),
        (
            lambda row: {
                **row,
                "subjects": [{**row["subjects"][0], "subject_id": "unknown"}],
            },
            "absent from selected vocabulary",
        ),
        (
            lambda row: {
                **row,
                "subjects": [
                    {
                        **row["subjects"][0],
                        "evidence": [
                            {
                                "paragraph_id": "p-1",
                                "start_char": 10,
                                "end_char": 18,
                                "quote": "taxation!",
                            }
                        ],
                    }
                ],
            },
            "quote",
        ),
        (
            lambda row: {**row, "decision": "unknown", "subjects": row["subjects"]},
            "cannot contain in_scope",
        ),
    ],
)
def test_rejects_mismatched_or_invalid_human_decisions(
    tmp_path: Path, mutation, message: str
) -> None:
    sample, reviews, packet_digest, vocabulary_digest = _fixture(tmp_path)
    row = mutation(_review(packet_digest, vocabulary_digest))
    reviews.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match=message):
        import_subject_reviews(sample, reviews, tmp_path / "out.jsonl")
    assert not (tmp_path / "out.jsonl").exists()


def test_rejects_incomplete_review_set(tmp_path: Path) -> None:
    sample, reviews, _, _ = _fixture(tmp_path)
    reviews.write_text("")
    with pytest.raises(ValueError, match="exhaustively"):
        import_subject_reviews(sample, reviews, tmp_path / "out.jsonl")


def test_rejects_invalid_raw_paragraph_hash_before_no_subject_import(tmp_path: Path) -> None:
    sample, reviews, packet_digest, vocabulary_digest = _fixture(tmp_path)
    packet_path = sample / "review_packets.jsonl"
    packet = json.loads(packet_path.read_text())
    packet["paragraphs"][0]["raw_text_sha256"] = "0" * 64
    packet_path.write_text(json.dumps(packet) + "\n")
    manifest_path = sample / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["review_packets_sha256"] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    row = _review(packet_digest, vocabulary_digest)
    row.update(decision="no_subject", subjects=[])
    reviews.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="raw_text_sha256"):
        import_subject_reviews(sample, reviews, tmp_path / "out.jsonl")


def test_template_and_import_outputs_refuse_overwrite(tmp_path: Path) -> None:
    sample, reviews, packet_digest, vocabulary_digest = _fixture(tmp_path)
    template = tmp_path / "template.jsonl"
    assert build_subject_review_template(sample, template) == 1
    with pytest.raises(FileExistsError):
        build_subject_review_template(sample, template)
    reviews.write_text(json.dumps(_review(packet_digest, vocabulary_digest)) + "\n")
    output = tmp_path / "accepted.jsonl"
    import_subject_reviews(sample, reviews, output)
    with pytest.raises(FileExistsError):
        import_subject_reviews(sample, reviews, output)


def test_oov_can_coexist_with_in_scope_subject_and_exact_evidence(tmp_path: Path) -> None:
    sample, reviews, packet_digest, vocabulary_digest = _fixture(tmp_path)
    row = _review(packet_digest, vocabulary_digest)
    row["out_of_vocabulary"] = [
        {
            "description": "A distinct unrepresented policy issue",
            "evidence": [
                {
                    "paragraph_id": "p-1",
                    "start_char": 10,
                    "end_char": 18,
                    "quote": "taxation",
                }
            ],
        }
    ]
    reviews.write_text(json.dumps(row) + "\n")
    output = tmp_path / "accepted.jsonl"
    report = import_subject_reviews(sample, reviews, output)
    accepted = json.loads(output.read_text())
    assert accepted["subjects"][0]["decision"] == "in_scope"
    assert (
        accepted["out_of_vocabulary"][0]["description"]
        == row["out_of_vocabulary"][0]["description"]
    )
    assert report.reviews_sha256 == hashlib.sha256(reviews.read_bytes()).hexdigest()


def test_no_subject_can_record_incidental_mention_only(tmp_path: Path) -> None:
    sample, reviews, packet_digest, vocabulary_digest = _fixture(tmp_path)
    row = _review(packet_digest, vocabulary_digest)
    row["decision"] = "no_subject"
    row["subjects"][0]["decision"] = "mention_only"
    reviews.write_text(json.dumps(row) + "\n")
    output = tmp_path / "accepted.jsonl"
    import_subject_reviews(sample, reviews, output)
    accepted = json.loads(output.read_text())
    assert accepted["decision"] == "no_subject"
    assert accepted["subjects"][0]["decision"] == "mention_only"
