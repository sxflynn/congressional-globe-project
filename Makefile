.PHONY: gate review review-demo run-workflow run-static status run-qwen run-gemma run-openai v2-sample
.NOTPARALLEL:

review:
	uv run streamlit run src/congressional_globe/review_app.py --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false

review-demo:
	uv run globe review register docs/review-demo.json
	$(MAKE) review

gate:
	uv run ruff format .
	npx prettier@3.9.10 --prose-wrap never --write "**/*.md"
	uv run ruff format --check .
	uv run ruff check .
	uv run ty check
	uv run complexipy src tests --max-complexity-allowed 5
	uv run pytest

run-workflow: run-static

run-static:
	uv run globe static-first --root . --run-id static-final-20261011 \
		--lexicon artifacts/static-audit-20261011/supplemented-lexicon.txt \
		--backend none --ai-limit 0

status:
	uv run globe cleanup status --run-directory artifacts/runs/static-final-20261011 \
		--run-id static-final-20261011

run-qwen:
	uv run globe cleanup status --run-directory artifacts/runs/static-final-20261011 --run-id static-final-20261011
	uv run globe cleanup run --run-directory artifacts/runs/static-final-20261011 \
		--run-id static-final-20261011 --backend ollama --model qwen3.8:27b-mlx \
		--limit 1000 --max-seconds 3600 --progress-interval 30

run-gemma:
	uv run globe cleanup status --run-directory artifacts/runs/static-final-20261011 --run-id static-final-20261011
	uv run globe cleanup run --run-directory artifacts/runs/static-final-20261011 \
		--run-id static-final-20261011 --backend ollama --model gemma4:31b-mlx \
		--limit 1000 --max-seconds 3600 --progress-interval 30

run-openai:
	uv run globe cleanup status --run-directory artifacts/runs/static-final-20261011 --run-id static-final-20261011
	uv run globe cleanup run --run-directory artifacts/runs/static-final-20261011 \
		--run-id static-final-20261011 --backend openai --model gpt-5.4-mini \
		--limit 1000 --max-seconds 3600 --progress-interval 30

# Offline review preparation: creates new artifacts and never calls a model.
v2-sample:
	uv run globe subject-exclusions \
		--samples artifacts/v2-pivot-20261011/tier2/pool.jsonl artifacts/v2-pivot-20261011/raw-vs-static-transfer/windows.jsonl \
		--jobs-database artifacts/runs/static-final-20261011/jobs.sqlite \
		--output artifacts/v2-subject-exclusions.json
	uv run globe subject-sample \
		--pages artifacts/runs/static-final-20261011/canonical_pages.jsonl \
		--exclusions artifacts/v2-subject-exclusions.json \
		--output artifacts/v2-subject-review --seed 20261012 --per-part 2
