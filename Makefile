.PHONY: eval lint test api artifacts

# Existing eval
eval:
	python evaluation/run_eval.py --golden data/sample/golden.json --out evaluation/results.json && \
	python evaluation/gate.py --results evaluation/results.json --f1 0.75 --ece 0.05

# Static checks (mirror CI)
lint:
	PYTHONPATH=$(PWD) ruff check .
	PYTHONPATH=$(PWD) black --check .
	PYTHONPATH=$(PWD) isort --check-only .

# Run tests locally (mirror CI)
test:
	PYTHONPATH=$(PWD) pytest -q

# Run local API for manual testing
api:
	uvicorn api.main:app --reload

# --- CI artifacts -----------------------------------------------------------
# Requires: gh (GitHub CLI) authenticated to the repo
ART_DIR ?= artifacts
ART_NAME ?= aura-reports

artifacts:
	@RID=$$(gh run list --branch main -L 1 --json databaseId --jq '.[0].databaseId'); \
	echo "Downloading artifacts for run $$RID..."; \
	gh run download "$$RID" --name $(ART_NAME) -D $(ART_DIR); \
	echo "Saved to $(ART_DIR)/"
