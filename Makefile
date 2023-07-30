.PHONY: test
test: unittest systest 

.PHONY: systest
systest:
	PYTHONPATH=. pytest

.PHONY: unittest
unittest:
	python3 -m unittest docworker/users_test.py
	python3 -m unittest docworker/prompts_test.py
	python3 -m unittest docworker/doc_gen_test.py
	python3 -m unittest docworker/dw_cli_test.py
	python3 -m unittest docworker/document_test.py
	python3 -m unittest docworker/doc_convert_test.py

.PHONY: build
build:
	python3 -m build  --wheel


.PHONY: coverage
coverage:
	PYTHONPATH=. coverage run -m pytest
	coverage run -a -m unittest docworker/users_test.py
	coverage run -a -m unittest docworker/prompts_test.py
	coverage run -a -m unittest docworker/doc_gen_test.py
	coverage run -a -m unittest docworker/dw_cli_test.py
	coverage run -a -m unittest docworker/document_test.py
	coverage run -a -m unittest docworker/doc_convert_test.py
	coverage report
	coverage html
