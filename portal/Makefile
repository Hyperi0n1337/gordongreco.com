SHELL := /bin/bash
PYTHON ?= python

.PHONY: verify test compile manifest
verify:
	$(PYTHON) scripts/verify.py

test:
	PYTHONPATH=packages:apps/api:apps/worker $(PYTHON) -m pytest -q

compile:
	$(PYTHON) -m compileall -q packages apps tests scripts

manifest:
	$(PYTHON) scripts/build_manifest.py
