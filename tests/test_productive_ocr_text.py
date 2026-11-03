"""T97: real saved inputs, numeric routing and offline v3 recovery, never source acceptance."""

import copy
import json
import runpy
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from congressional_globe.deterministic_geometry import GeometryRegistry
from congressional_globe.deterministic_lexicon import Lexicon
from congressional_globe.deterministic_models import ExactEdit, replay_with_map
from congressional_globe.deterministic_repair import DeterministicResult, analyze_paragraph
from congressional_globe.deterministic_rules import Resources
from congressional_globe.productive_ocr_authority import verify_real_authority
from congressional_globe.productive_ocr_host import canonical_json, sha256_bytes, validate_host
from congressional_globe.productive_ocr_measurement_inputs import ASSEMBLY, _registry
from congressional_globe.productive_ocr_projection import (
    compile_request_projection,
    derive_reply_schema,
)
from congressional_globe.productive_ocr_reply import validate_reply
from congressional_globe.productive_ocr_routing import (
    TEXT_PROMPT,
    prepare_text_host,
    route_paragraph,
)
from congressional_globe.productive_ocr_runner import RunnerContext, execute, freeze_job
from congressional_globe.productive_ocr_text_reply import (
    coarse_proposal,
    export_text_reply,
    validate_text_reply,
)
from congressional_globe.repair_feedback import FeedbackRequirement

DET = runpy.run_path(str(Path(__file__).with_name("test_deterministic_repair.py")))
RUN = runpy.run_path(str(Path(__file__).with_name("test_productive_ocr_runner.py")))
BASE = Path("artifacts/deterministic-sample-20261028-01")


def saved_results():
    return [
        DeterministicResult.model_validate_json(json.dumps(r))
        for r in json.loads((BASE / "results.json").read_bytes())
    ]


def saved_resources(result):
    lookups = {
        entry.spec.purpose: Lexicon(spec=entry.spec, data=Path(entry.spec.label).read_bytes())
        for entry in result.lexicons
    }
    return Resources(
        **lookups,
        geometry=GeometryRegistry(
            data=(BASE / "geometry-registry.json").read_bytes(),
            expected_sha256=result.geometry_registry_sha256,
        ),
    )


def saved_case(unit):
    host = json.loads((ASSEMBLY / unit / "host.json").read_bytes())
    index = json.loads((ASSEMBLY / "registry-index.json").read_bytes())
    registry = _registry(ASSEMBLY, host, index)
    source_id = host["payload"]["paragraphs"][0]["source_id"]
    result = next(r for r in saved_results() if r.input.source.source_id == source_id)
    resources = saved_resources(result)
    selected = saved_requirements(unit)
    prepared, routes = prepare_text_host(host, registry, {"P1": result}, resources, selected)
    prompt = registry.files[prepared["payload"]["prompt_sha256"]].decode()
    projection, schema = compile_request_projection(prepared, registry, prompt, "offline-test-only")
    return prepared, registry, result, routes, projection, schema


def reply(host, text):
    return json.dumps(
        dict(
            contract="ocr-productive-repair-text-reply-v3",
            unit_id=host["payload"]["unit_id"],
            readings=[
                dict(paragraph_alias="P1", coverage="complete", corrected_text=text, reason=None)
            ],
        )
    )


@pytest.mark.parametrize(
    "unit,old,new", [("S1", "loyal ' and", "loyal and"), ("S2", "propei-ty", "property")]
)
def test_real_software_inputs_preserve_feedback_and_full_target(unit, old, new):
    host, registry, result, routes, projection, schema = saved_case(unit)
    target = host["payload"]["paragraphs"][0]
    assert target["static"]["text"] == result.proposed_text
    assert len(routes) == 1
    assert old in registry.files[host["payload"]["prompt_sha256"]].decode()
    assert "all other supported errors" in registry.files[host["payload"]["prompt_sha256"]].decode()
    corrected = result.proposed_text.replace(old, new).replace("in- sisted", "insisted")
    exported = export_text_reply(host, projection.body_utf8, reply(host, corrected))
    proposal = exported.outcome["derived_proposals"][0]
    assert proposal["text"] == corrected
    edits = tuple(ExactEdit.model_validate(e) for e in proposal["raw_edits"])
    assert replay_with_map(result.input.source.raw_text, edits)[0] == corrected
    assert proposal["alignment"] == "coarse_whole_paragraph_not_token_alignment"
    assert schema.contract == "productive-ocr-reply-schema-v3"
    with pytest.raises(ValueError, match="feedback"):
        validate_text_reply(reply(host, result.proposed_text), host)
    with pytest.raises(ValueError):
        validate_reply(reply(host, corrected), host)


@pytest.mark.parametrize(
    "form",
    [
        "703",
        "2794",
        "1865-10-30",
        "$1,000.50",
        "21st",
        "one",
        "twenty-first",
        "II",
        "I",
        "fortieth",
        "half",
        "H.R.703",
    ],
)
def test_legacy_numeric_forms_reconstruct_historical_all_word_number_routing(form):
    raw = f"Known {form} text."
    source = DET["_input"](raw)
    lex = DET["_lexicon"](["known", "text", form, "one", "twenty", "first", "half"])
    resources = Resources(words=lex, names=DET["_lexicon"](["Known", form], "names"))
    result = analyze_paragraph(source, resources)
    routed = route_paragraph(result, resources, "P1", legacy_written_numbers=True)
    numbers = [s for s in routed.signals if s["category"] == "number"]
    assert numbers
    assert routed.selection == "secondary_inspection"
    assert "incomplete" in routed.coverage_gaps


def test_legacy_joined_apparent_success_retains_historical_written_number_signal():
    source = DET["_input"]("twen- ty 703 703.", ["twen-", "ty 703 703."])
    resources = DET["_resources"](source, ["twenty"])
    result = analyze_paragraph(source, resources)
    assert result.proposed_text == "twenty 703 703."
    routed = route_paragraph(result, resources, "P1", legacy_written_numbers=True)
    assert any(s["raw_quote"] == "twen- ty" for s in routed.signals if s["category"] == "number")
    assert {s["paragraph_alias"] for s in routed.signals} == {"P1"}


def test_known_word_is_not_source_proof_names_explicit_and_audits_retained():
    source = DET["_input"]("Mr. Brown reads form.")
    words = DET["_lexicon"](["mr", "brown", "reads", "form"])
    missing = route_paragraph(
        analyze_paragraph(source, Resources(words=words)), Resources(words=words), "P1"
    )
    assert missing.name_list_state == "not_assessed"
    assert any("name_list_not_assessed" in s["flags"] for s in missing.signals)
    resources = Resources(words=words, names=DET["_lexicon"](["Mr", "Brown"], "names"))
    known = route_paragraph(analyze_paragraph(source, resources), resources, "P1")
    assert not any("name_list_unfamiliar" in s["flags"] for s in known.signals)
    plain = DET["_input"]("reads form")
    audit = route_paragraph(analyze_paragraph(plain, resources), resources, "P1")
    assert audit.selection == "audit_only"  # dictionary false positive remains auditable


@pytest.mark.parametrize("text", ["property", "Mr. BROWN.", "private propei-ty."])
def test_fragment_cannot_claim_complete_paragraph(text):
    host, *_ = saved_case("S2")
    with pytest.raises(ValueError):
        validate_text_reply(reply(host, text), host)


@pytest.mark.parametrize(
    "text",
    [
        "a new repeated word repeated.",
        "repeated repeated word.",
        "Entirely replaced text.",
        "repeated word.",
    ],
)
def test_repeated_reordered_inserted_deleted_text_has_replay_but_no_false_token_precision(text):
    target: dict = dict(
        alias="P1",
        source_id="fixture:0:p",
        raw=dict(text="repeated word repeated.", sha256=sha256_bytes(b"repeated word repeated.")),
        static=dict(sha256="a" * 64),
    )
    proposal = coarse_proposal(target, text)
    assert proposal["replay_verified"]
    assert proposal["support_map"][0]["raw_start"] == 0
    assert proposal["support_map"][0]["raw_end"] == len(target["raw"]["text"])
    assert proposal["source_quality"] == "not_verified"


def test_wrong_unit_target_duplicate_missing_and_empty_rejected():
    host, _, result, *_ = saved_case("S2")
    text = result.proposed_text.replace("propei-ty", "property")
    original = json.loads(reply(host, text))
    variants = [
        dict(original, unit_id="foreign"),
        dict(original, readings=[]),
        dict(original, readings=original["readings"] * 2),
    ]
    for value in variants:
        with pytest.raises(ValueError):
            validate_text_reply(json.dumps(value), host)
    with pytest.raises(ValueError):
        validate_text_reply(reply(host, ""), host)
    foreign = copy.deepcopy(original)
    foreign["readings"][0]["paragraph_alias"] = "P2"
    with pytest.raises(ValueError):
        validate_text_reply(json.dumps(foreign), host)


def test_missing_numeric_image_retains_seven_assignments_without_request():
    units = json.loads((ASSEMBLY / "units.json").read_bytes())
    assert [u["unit_id"] for u in units] == ["S1", "S2", "S3", "S4", "S5", "D1", "D2"]
    assert [u["unit_id"] for u in units if u["status"] == "missing_source_image"] == ["S3", "S4"]
    result = next(
        r for r in saved_results() if r.input.source.source_id.endswith("par_000083_000042")
    )
    route = route_paragraph(result, saved_resources(result), "P1")
    assert _number_quotes(route) >= {"703", "2794"}
    host, *_ = saved_case("S2")
    host["payload"]["image"] = None
    with pytest.raises(ValueError, match="image"):
        validate_text_reply(reply(host, "A complete reading."), host)


def fake_session(started=None):
    jobs, registry, bounds = RUN["_session"](started)
    source = DET["_input"]("By Mr. Example.")
    source = source.model_copy(
        update={
            "source": source.source.model_copy(
                update={"source_id": jobs[0].host["payload"]["paragraphs"][0]["source_id"]}
            )
        }
    )
    resources = Resources(words=DET["_lexicon"](["By", "Mr", "Example"]))
    result = analyze_paragraph(source, resources)
    converted = []
    for job in jobs:
        host, _ = prepare_text_host(job.host, registry, {"P1": result}, resources)
        schema = derive_reply_schema(host)
        new_job = freeze_job(
            host, registry, TEXT_PROMPT, schema.schema_text, "invented-fake-model", 2, "a" * 64
        )
        fit = dict(
            model_name="invented-fake-model",
            body_sha256=new_job.body_sha256,
            model_digest=host["payload"]["model_digest"],
            input_tokens=2,
            output_tokens=1500,
            evidence_scope="synthetic_test",
        )
        data = canonical_json(fit)
        registry.files[sha256_bytes(data)] = data
        converted.append(new_job.model_copy(update={"token_fit_sha256": sha256_bytes(data)}))
    return tuple(converted), registry, bounds


class TextCall(RUN["Call"]):
    def result(self, timeout):
        response = RUN["_response"](self.unit)
        text: dict = dict(
            contract="ocr-productive-repair-text-reply-v3",
            unit_id=self.unit,
            readings=[
                dict(
                    paragraph_alias="P1",
                    coverage="complete",
                    corrected_text="By Mr. Example.",
                    reason=None,
                )
            ],
        )
        response["output_text"] = json.dumps(text)
        response["raw_response"] = response["output_text"]
        if self.mode == "incomplete":
            text["readings"][0].update(
                coverage="incomplete", corrected_text=None, reason="Image unclear"
            )
            response.update(output_text=json.dumps(text), raw_response=json.dumps(text))
        return response


class TextClient(RUN["Client"]):
    def start(self, body):
        unit = json.loads(json.loads(body)["messages"][1]["content"])["unit_id"]
        self.calls.append(unit)
        if self.sent:
            with self.sent.open("a") as stream:
                stream.write(unit + "\n")
        return TextCall(unit, self.mode)


def test_fake_v3_journal_recovers_saved_raw_without_duplicate_call(tmp_path):
    jobs, registry, bounds = fake_session()
    client = TextClient()

    def checkpoint(name):
        if name == "after_raw":
            raise SystemExit("synthetic interruption after raw and stop receipt")

    with pytest.raises(SystemExit):
        execute(tmp_path, jobs, bounds, RunnerContext(registry, client, checkpoint=checkpoint))
    assert client.calls == ["U1"]
    result = execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert result["statuses"]["valid"] == 2
    assert client.calls == ["U1", "U2"]
    assert execute(tmp_path, jobs, bounds, RunnerContext(registry, client)) == result


def test_withheld_blocks_followup_and_v3_cannot_borrow_live_authority(tmp_path):
    jobs, registry, bounds = fake_session()
    client = TextClient("incomplete")
    with pytest.raises(ValueError, match="incomplete/unresolved"):
        execute(tmp_path, jobs, bounds, RunnerContext(registry, client))
    assert client.calls == ["U1"]
    with pytest.raises(ValueError, match="offline only"):
        verify_real_authority(None, [SimpleNamespace(job=jobs[0])], None, registry, "unused")


def test_new_schema_is_frozen_not_chosen_by_reply():
    host, registry, *_ = saved_case("S2")
    host["payload"]["response_schema_sha256"] = sha256_bytes(b"{}")
    registry.files[sha256_bytes(b"{}")] = b"{}"
    host["packet_sha256"] = sha256_bytes(canonical_json(host["payload"]))
    with pytest.raises(ValueError, match="schema"):
        validate_host(host, registry)


def saved_requirements(unit):
    data = json.loads(
        Path("artifacts/hr012-feedback-20261029-01/required-followup.json").read_bytes()
    )
    selected = [row for row in data["source_cases"] if row["unit_id"] == unit]
    return [_requirement(row) for row in selected]


def _number_quotes(route):
    return {s["raw_quote"].rstrip(",)") for s in route.signals if s["category"] == "number"}


def _requirement(row):
    return FeedbackRequirement.model_validate({k: v for k, v in row.items() if k != "unit_id"})


@pytest.mark.parametrize(
    "raw,text",
    [
        ("A [one] B [two].", "A [two] B [one]."),
        ("A [one].", "A [one] [one]."),
        ("A [one].", "A [two]."),
        ("A [broken.", "A [broken]."),
        ("A [nested [word]].", "A [nested word]."),
    ],
)
def test_bracket_order_and_malformed_source_withhold_complete_text(raw, text):
    host, *_ = saved_case("S2")
    target = host["payload"]["paragraphs"][0]
    target["raw"]["text"] = raw
    target["static"]["text"] = raw
    host["payload"]["diagnostics"]["signals"] = []
    with pytest.raises(ValueError, match="bracket"):
        validate_text_reply(reply(host, text), host)


@pytest.mark.parametrize("placement", ["before", "after", "only"])
def test_context_cannot_be_attached_to_target(placement):
    host, *_ = saved_case("S2")
    context = copy.deepcopy(host["payload"]["paragraphs"][0])
    context.update(alias="P2", role="context")
    context["raw"]["text"] = "Unrelated adjacent passage."
    host["payload"]["paragraphs"].append(context)
    target = host["payload"]["paragraphs"][0]["raw"]["text"].replace("propei-ty", "property")
    text = dict(
        before=context["raw"]["text"] + target,
        after=target + context["raw"]["text"],
        only=context["raw"]["text"],
    )[placement]
    with pytest.raises(ValueError, match="context"):
        validate_text_reply(reply(host, text), host)


@pytest.mark.parametrize("form", ["½", "Ⅳ", "²"])
def test_unicode_numbers_also_route(form):
    source = DET["_input"](f"Known {form} text.")
    resources = Resources(words=DET["_lexicon"](["Known", form, "text"]))
    route = route_paragraph(analyze_paragraph(source, resources), resources, "P1")
    assert any(s["category"] == "number" for s in route.signals)


def test_feedback_phrase_at_wrong_location_does_not_close_named_obligation():
    host, _, result, *_ = saved_case("S2")
    wrong = result.proposed_text.replace("propei-ty", "unknown") + " property"
    with pytest.raises(ValueError, match="feedback"):
        validate_text_reply(reply(host, wrong), host)


FRESH_WORKER = r"""
import os, runpy, signal, sys
from pathlib import Path
ns = runpy.run_path(sys.argv[1])
base = Path(sys.argv[2])
jobs, registry, bounds = ns['fake_session'](float((base / 'started').read_text()))
client = ns['TextClient'](sent=base / 'sent')
def checkpoint(name):
    if name == sys.argv[3]:
        os.kill(os.getpid(), signal.SIGKILL)
context = ns['RunnerContext'](registry, client, checkpoint=checkpoint)
ns['execute'](base / 'run', jobs, bounds, context)
"""


def test_fresh_process_v3_replays_saved_raw_mode_without_duplicate_send(tmp_path):
    (tmp_path / "started").write_text(str(time.time()))
    command = [sys.executable, "-c", FRESH_WORKER, __file__, str(tmp_path)]
    killed = subprocess.run([*command, "after_raw"], capture_output=True, timeout=30)
    assert killed.returncode == -signal.SIGKILL, killed.stderr.decode()
    resumed = subprocess.run([*command, "none"], capture_output=True, timeout=30)
    assert resumed.returncode == 0, resumed.stderr.decode()
    assert (tmp_path / "sent").read_text().splitlines() == ["U1", "U2"]
