.PHONY: test lint eval clean

PYTHON ?= python

test:
	$(PYTHON) -m unittest discover tests

lint:
	$(PYTHON) -m src.linter.ast_check src/ tests/

eval:
	$(PYTHON) -m src.cli eval --protocol all --episodes 100

clean:
	rm -rf __pycache__ src/__pycache__ tests/__pycache__ src/*/__pycache__ .pytest_cache *.html
