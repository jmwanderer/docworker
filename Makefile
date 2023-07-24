.PHONY: test
.PHONY: build

test:
	PYTHONPATH=. pytest
	python3 -m unittest docworker/users_test.py
	python3 -m unittest docworker/docx_util_test.py


build:
	python3 -m build  --wheel
