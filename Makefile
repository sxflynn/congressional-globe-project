.PHONY: gate run-workflow run-static status run-qwen run-gemma run-openai
.NOTPARALLEL:

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
