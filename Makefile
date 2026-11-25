# Convenience commands for the Flood Response Simulation Platform
.PHONY: install run test experiments clean

install:
	cd backend && pip install -r requirements.txt

run:
	cd backend && uvicorn app.main:app --reload --port 8000
	@echo "Open http://localhost:8000"

test:
	cd backend && pytest -q

experiments:
	cd backend && python -m experiments.run_experiments --seeds 30

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/experiments/results
