# What happened when we asked the real AI

T31/T32, 2026-10-26. The current chat authorized one small real-AI check. We selected the already-installed local `qwen3.8:27b-mlx` model. We planned at most two sequential requests: a short made-up date check, then the real House-opening passage. No historical role or reading experiment was repeated.

**The first check failed, so the historical request was not sent.** This is an actual model result, not another simulated response. The complete reply is retained unchanged.

## The concrete mistake

The short, explicitly synthetic check said:

> Synthetic transport check only. The meeting was held January 2, 1900.

The AI correctly answered **January 2, 1900** and correctly quoted those words. But it also said they occupied character positions30–55. Those positions actually contain:

> . The meeting was held Ja

The date words are at positions53–68 (counting from zero, stopping before68). The software rejected the answer because its reference did not point to its own quoted evidence. The returned model reply was not repaired or reclassified as valid. The independently computed correct positions appear only in a separate diagnostic record.

This exposes a practical limitation of the current arrangement: it asks an AI to identify the date **and** count the exact characters where it appears. Here, the first part worked and the second part failed. That does not establish accuracy on historical text or prove that the model can handle the Senate/House boundary.

The better next implementation question is whether ordinary software should locate an exact, uniquely occurring quote and produce the positions itself, while preserving the original AI reply and refusing missing or ambiguous matches. That needs explicit versioning and tests; this run did not introduce such a repair or weaken the existing check.

## What we actually ran

One request took **24.436seconds**, with **1,283 input tokens and296output tokens**. The local API charge was$0; local compute, energy and human review still have a cost that is not measured here. The endpoint returned a complete JSON object and known usage. The host marked it invalid for `evidence quote/offset mismatch`.

The [frozen readiness record](readiness.json) allowed no more than2requests,120seconds per request,300seconds total dispatch wall time and2,000output tokens per request, with zero retries. It required the historical request to wait for a successful compatibility check. That condition failed. We stopped with **one attempted request, zero retries and zero historical requests**. The old reading investigation's48attempts/3693.79conservative seconds remain separate and unchanged; its unused allowance was not consumed or treated as new permission.

- [Actual unmodified answer and host rejection](compatibility/run/summary.json).
- [Proposal export showing the rejection](compatibility/run/proposals.json).
- [Terminal evidence, including source text and checkpoint verification](terminal-evidence.json).
- [Unsent real House-opening request](house-opening/intended-api-request.json). This is an intended request, **not an AI answer**.
- [Preparation review](review.json) and [integrity checks](validation.json).

The originally prepared House passage says “HOUSE OF REPRESENTATIVES. Monday, December 4, 1865.” after Senate adjournment text. Its expected date scope remains the old AI-provisional fixture expectation; we have no new model answer or human judgment about it from this run.

## Why this is trustworthy evidence of a failure

Before inference we froze the exact source packets, prompts, schemas, request/settings/code identities, installed model digest, server/client versions, journal paths and stop rules. The selected digest was `5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e`; server version was0.40.8. Fresh process observations included PID, start time and full command; cleanup had zero claimed work, the shared Ollama lock was available and bounded recent POST logs were inspected through the existing tool. Only the server and review app were present before launch. After termination, no processing worker remained. A loaded model after completion does not imply it is still generating.

The existing role runner saved its launch intent, raw reply, usage, request time and invalid disposition. Read-only journal verification checked request, response and terminal-result hashes. Actual worker PID95072/start/full command remains in `compatibility/run/events.jsonl` and the terminal export. T30 recovery code was used without modification. We did not rerun already-passing code tests for this artifact-only live unit; the last code gate remains535tests. Artifact checks verify frozen inputs, unchanged code and stored evidence.

The local adapter uses JSON-object mode plus a schema in its instructions and local host checks. It does **not** force native constrained-schema generation. Current [Ollama compatibility documentation](https://docs.ollama.com/api/openai-compatibility) describes the supported chat interface; the actual installed endpoint's behavior is recorded here separately. A complete JSON response is evidence of transport acceptance, not schema or historical correctness. Native schema acceptance, role-v2 live compatibility, general date quality and P0 remain unproved.

T31 preparation is complete. T32's historical check is blocked by the failed source-coordinate requirement. T35 defines the bounded offline follow-up; another live request requires its own frozen scope and fresh checks, not spending the unused second slot of this stopped run.
