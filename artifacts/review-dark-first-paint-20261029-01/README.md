# T73: respect device theme from the initial page document

The review desk now paints a subdued dark canvas on dark-mode devices before the app loads. Light-mode devices receive the configured light background. `make review` starts the same app through a small launcher that inserts early theme CSS into the initial HTML document. Both automatic device themes remain configured; app CSS, historical passages, review packets and answers are unchanged.

## Implementation and maintenance boundary

The launcher reads and validates the existing light/dark background colors from `.streamlit/config.toml`. It creates a temporary directory containing one customized `index.html` and symlinks to the installed Streamlit assets. Before server route construction it overrides the static-directory lookup within that server process. It does not modify installed package bytes or copy/vendor the asset bundle. On exit or error it restores the lookup and command arguments and removes the temporary directory.

Streamlit has no app-level head hook in the inspected installed version, and app-injected CSS arrives after the initial document paint. This fix therefore uses an internal hook. The launcher accepts exactly the pinned Streamlit 1.66.1 and fails clearly on an upgrade until the integration is rechecked. This compatibility dependency is the material maintenance risk. The public command remains `make review`; no scheduler, model tool, new dependency or recurring workload is introduced.

## Verification

Seven focused tests cover early-style placement, theme-color validation, refusal of unexpected HTML, unchanged installed-source bytes, symlinked asset delivery through the actual Streamlit static route, and process-state restoration on success and failure. Root corrected fixture assignments after full-gate typing and Ruff failures. The final full `make gate` passes formatting, Ruff, ty, complexity at most five, and **929 tests**. A separate bounded Luna code review found no material issue.

Live verification uses an isolated launcher on port18503 and a copy of the actual review database. Startup frames cover dark/light preferences at desktop1280×900 and mobile375×812 widths, both cold load and reload. These are browser emulations, not tests on a physical phone. Sampled startup frames show a dark canvas/skeleton for dark preference and a light canvas/skeleton for light preference. Some filenames ending in `final` still show the startup skeleton; separately named `review-rendered` frames show the fully loaded desk in all four preference/width combinations. The screenshots establish the sampled startup behavior, not every possible browser or network timing. Root visually inspected the rendered dark desktop and light mobile views as well as a dark startup skeleton.

[Live findings](findings.json) and the captured measurement artifacts record the exact protocol, source binding, frames, observations, isolated-server shutdown and review-store preservation checks. Historical spike evidence is retained separately from current implementation verification; only selected baseline evidence is included in this portable package, not its copied Streamlit tree.

## Actual desk refresh

After the code gate and live startup checks, root stopped only the identified old unpatched desk and started the tested launcher on the existing port8501. The current verified LAN address is [http://10.0.0.56:8501](http://10.0.0.56:8501). [Launch receipt](main-server-launch.json), [served document](main-index.html), and [HTTP/process verification](main-server-verification.json) record the change. The new server returns HTTP200 and includes the early theme rule. Its Python process started2026-10-29 14:31:41local, PID75258; observations are dated evidence, not future runtime truth.

The real review database SHA-256 is unchanged at `6b95d4a689af34f3b21e972c3afdc02dcc7a4920e2e4bca468d1b1d6676c617b`:9packets,0drafts,7submissions and7application receipts. No test answer, draft or grading submission was saved. The obsolete prior-session spike on port8502 was also stopped after verifying its exact process identity; the actual desk on8501 remains running.

This completes the bounded desk-usability task only. It creates no historical quality labels, new review request, source correction, model request or milestone acceptance.
