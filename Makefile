.PHONY: setup test check demo up monitoring down package
setup:
	python3 scripts/bootstrap.py
test:
	python -m pytest -q
check:
	python -m compileall -q devpilot scripts runner
	python scripts/validate-configs.py
	python -m ruff check devpilot tests scripts runner
demo:
	python -m devpilot serve --seed
up:
	docker compose up -d --build
monitoring:
	docker compose -f compose.yaml -f compose.monitoring.yaml up -d --build
down:
	docker compose -f compose.yaml -f compose.monitoring.yaml down
package:
	python scripts/package_zip.py --output ../devpilot-devops-complete.zip
