.PHONY: test
.PHONY: systest
.PHONY: unittest
.PHONY: build


test: systest unittest

systest:
	PYTHONPATH=. pytest

build:
	python3 -m build  --wheel


unittest:
	python3 -m unittest docworker/users_test.py
	python3 -m unittest docworker/prompts_test.py
	python3 -m unittest docworker/doc_gen_test.py
	python3 -m unittest docworker/dw_cli_test.py
	python3 -m unittest docworker/document_test.py
	python3 -m unittest docworker/doc_convert_test.py

