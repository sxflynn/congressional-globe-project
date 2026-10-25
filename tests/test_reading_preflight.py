from __future__ import annotations

from congressional_globe.reading_preflight import (
    SUPPORTED_MODELS,
    RuntimeEvidence,
    TokenFitEvidence,
    _assess,
    build_report,
)


def _runtime(
    model: str = "qwen3.8:27b-mlx",
    digest: str | None = SUPPORTED_MODELS["qwen3.8:27b-mlx"],
    capabilities: list[str] | None = None,
) -> RuntimeEvidence:
    return RuntimeEvidence(
        model=model,
        digest=digest,
        runner="mlx",
        capabilities=capabilities or ["completion", "vision"],
        runtime_version="0.40.8",
        model_context_limit=262144,
        prior_probe_config={"num_ctx": 8192, "max_output_tokens": 256},
        prior_loaded_models=[],
        prior_ps_snapshot_sha256="b" * 64,
        snapshot_file="snapshot.json",
        snapshot_sha256="a" * 64,
        evidence_age="current_snapshot",
        current_loaded_models=[],
        current_ps_snapshot_sha256="d" * 64,
        runtime_evidence_files={},
        process_observation={"worker_state": "idle"},
    )


def test_unsupported_model_is_blocked():
    assessment = _assess(_runtime(model="other-model"))
    assert "unsupported_model" in assessment.blockers
    assert assessment.launch_ready is False


def test_missing_exact_digest_is_blocked():
    assessment = _assess(_runtime(digest=None))
    assert "missing_exact_digest" in assessment.blockers
    assert assessment.launch_ready is False


def test_image_capability_absent_is_blocked():
    assessment = _assess(_runtime(capabilities=["completion"]))
    assert "image_capability_absent" in assessment.blockers
    assert assessment.launch_ready is False


def test_unknown_text_and_image_fit_never_launch_ready():
    assessment = _assess(_runtime())
    assert assessment.text_tokens is None
    assert assessment.image_tokens is None
    assert assessment.token_fit_status == "unknown"
    assert "exact_text_token_fit_unknown" in assessment.blockers
    assert "image_token_fit_unknown" in assessment.blockers
    assert assessment.launch_ready is False


def test_measured_request_over_context_is_blocked():
    fit = TokenFitEvidence(
        text_tokens=7200,
        image_tokens=600,
        output_reserve_tokens=512,
        requested_context_tokens=8192,
        method="local_model_tokenizer_processor",
        evidence_sha256="c" * 64,
    )
    assessment = _assess(_runtime(), fit)
    assert assessment.token_fit_status == "exceeds"
    assert "measured_request_exceeds_requested_context" in assessment.blockers
    assert assessment.launch_ready is False


def test_report_uses_frozen_candidates_and_current_runtime_evidence():
    report = build_report("2026-10-24T00:00:00Z")
    assert report.frozen_inputs.candidate_count == 23
    assert report.frozen_inputs.primary_count == 18
    assert report.frozen_inputs.confirmation_count == 5
    assert report.frozen_inputs.primary_word_count == 6367
    assert len(report.supported_models) == 3
    assert len(report.tokenizer_assets) >= 8


def test_report_preserves_unknown_token_fit_and_never_launches():
    report = build_report("2026-10-24T00:00:00Z")
    assert all(row["exists"] is True for row in report.tokenizer_assets)
    assert all(row.launch_ready is False for row in report.supported_models)
    assert all(row.text_tokens is None for row in report.supported_models)
    assert all(row.image_tokens is None for row in report.supported_models)
    assert all(row.token_fit_status == "unknown" for row in report.supported_models)


def test_report_binds_completed_geometry_coverage_proof():
    report = build_report("2026-10-24T00:00:00Z")
    assert report.image_evidence["proof_matches_index"] is True
    assert report.image_evidence["geometry_coverage_complete"] is True
    assert report.image_evidence["primary_units"] == 18
    assert report.image_evidence["images"] == 19


def test_report_preserves_process_and_call_evidence():
    report = build_report("2026-10-24T00:00:00Z")
    assert report.runtime_api_calls == 6
    assert report.inference_calls == report.warmup_calls == report.downloads == 0
    assert report.process_inspection["status"] == "confirmed"
    assert all(row.runtime_state == "idle" for row in report.supported_models)


def test_current_snapshot_does_not_fall_back_to_historical_identity():
    from congressional_globe.reading_preflight import _snapshot_values

    values = _snapshot_values(
        "qwen3.8:27b-mlx",
        {"capabilities": ["vision"], "model_info": {}},
        {},
        {"models": []},
        {"models": []},
        {"digest": "historical", "runner": "mlx", "version": "old"},
        "current_snapshot",
    )
    assert values["digest"] is None
    assert values["runner"] is None
    assert values["runtime_version"] is None


def test_loaded_model_listing_alone_does_not_claim_runtime_busy():
    from congressional_globe.reading_preflight import _runtime_state

    runtime = _runtime()
    runtime = runtime.model_copy(update={"current_loaded_models": [{"name": "warm"}]})
    assert _runtime_state(runtime) == "unknown"
