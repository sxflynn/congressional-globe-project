# T70: owned local HTTP runner, offline proof

The new library can send an exact frozen request to a private local server, save the complete HTTP response before interpreting it, export a separate source-linked proposal, and recover a completed request after the parent process is killed. This evidence uses an inspected fake server and invented text with a white test image. It contains no new historical transcription or model inference.

The raw OCR remains immutable. A proposed reading is a separate unreviewed layer with exact edits and links to its raw text, scan, diagnostics and model/request identities. A software-valid proposal is not a verified historical reading or human approval.

## Implemented and checked

- A distinct owned-local mode uses the unchanged durable journal. It checks approval, exact frozen jobs, model, code, bounds and complete fit evidence, and requires fresh process/queue/log/model evidence before each individual send. It has no automatic batch, retry, pull or warmup.
- The adapter starts only its explicitly selected, hash-verified private server, verifies the listening process and retains PID, start time and command evidence. Request deadlines include verification/startup and shutdown reserve. It never attaches to or stops the shared Ollama service.
- Exact HTTP bytes are saved before JSON parsing. Truncated/surplus framing, bad encoding, missing usage, incomplete responses and identity changes fail conservatively. Failure exports preserve raw entity bytes rather than inventing a model reply.
- Per-unit reply schemas freeze role, unit and paragraph aliases. Complete fit requires the exact rendered text and token trace, image tile bytes/schedule, schema, diagnostics and saved proposal. A partial text counter is rejected. Dry/offline preflight does not require a previous generation, but its authentic producer is still missing.
- [Recovery observations](recovery.json) show four fresh-process SIGKILL/resume cases: after durable HTTP spool, raw journal before stop observation, raw result, and terminal result. Each retains exactly one POST/request. The successful case also reuses its saved result without a new request.
- [Review dispositions](review.json) record the bounded delegate findings and fixes. The full repository gate log and exact test-source hashes are retained with this evidence.

The success folder contains its frozen request, prepared job, readiness, registered supporting bytes, raw HTTP spool, stop receipt, journal and exported result. The four other folders retain crash/resume journals and receipts. The machine-specific fake executable and SQLite transient files were removed after observation; these are evidence snapshots, not runnable saved jobs. The tracked tests and retained driver reproduce the fixtures in a new directory.

## Still blocked

T55 is not ready. S3/S4 source crops are missing; the actual native image/text preprocessing evidence is unavailable; real backend compatibility and stopping are unproved. D1's earlier illustrative native-grid scenario exceeded the candidate input ceiling, which remains unchanged. The new fit validator cannot turn a hypothetical schedule into authentic backend evidence.

Real execution deliberately has no trusted T55 clearance identity. A caller cannot clear these conditions by registering self-asserted JSON. A future reviewed readiness unit must establish and pin that exact artifact before the existing approved seven-unit run can start. The simulation entry point is an explicit engineering test hook for inspected fixture code, not an arbitrary-executable sandbox.

The recorded human approval remains valid within its original scope. No new human approval is requested. No source fetch, model download, dependency, real inference, desk grading packet or cleanup-policy acceptance was added by T70.

## Evidence checkpoints and checks

The earlier [01 checkpoint](../owned-ocr-transport-20261028-01/README.md) predates the final authority/export fixes. [02](../owned-ocr-transport-20261028-02/README.md) records a refused overlapping fake evidence run: it collided with the full gate's shared request lock. Both observations are preserved; the final evidence above ran sequentially. The initial relative-path fixture setup was rejected before any server launch and is recorded in validation.json.

Final checks and their exact outcomes are in validation.json. Parent stages M2/M5 remain partial; this proves implementation and bounded fake-server recovery, not actual model behavior, historical efficacy or a ready 30-minute study.
