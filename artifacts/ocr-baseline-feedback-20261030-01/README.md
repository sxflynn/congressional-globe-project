# T104: apply submitted OCR cleanup feedback

The exact HR014v2 submission revision1 is preserved in submission.json. The main comment asks for prompting that treats the OCR as substantially similar to the original, repairs it, and distinguishes missed target words from a whole added sentence. All four evidence-local notes are empty. feedback-disposition.json preserves the exact comment, action, checks and unresolved model-quality question.

The revised scoped instruction explicitly uses the original OCR as the starting point and permits image-supported missing words inside the assigned paragraph, including across lines. It excludes neighbouring sentences. T103 source geometry and visible-context exclusion remain in force. This is a prompt change with no new provider call, CLI or automation. The original T103 candidate and all actual model results remain unchanged.

Inputs: saved target OCR/image, precise target/context bindings and revised instruction. Expected: repair only the assigned paragraph, retaining supported target words and genuine hyphens. Actual offline results: serialized request contains the exact instruction; unchanged T102 copied-neighbour reply rejects; authored expected-target test passes as an unreviewed proposal. There is no new AI response. Actual adherence and missing-word quality remain unproved and need a separately authorized bounded test.

All29focused controls and full make gate1132tests pass. Saved candidate prompt/request/host/schema/projection, registry resources, actual-result hash and code identity support reproducibility. The software check is limited declared-line copy exclusion, not full source fidelity.

HR014v4 presents input → expected → actual software outcomes with three evidence-local comment boxes and one overall comment. Isolated AppTest reports no exceptions and no glossary buttons within historical/model text; surrounding AI prose has glossary help. Computer Use and device/browser interaction were not performed. No production answers were written by the tests. The verified LAN desk is http://10.0.0.56:8501.
