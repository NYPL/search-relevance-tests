VENV_DIR := .venv

venv:
	python -m venv $(VENV_DIR)
	$(source $(VENV_DIR)/bin/activate)
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r dev-requirements.txt

lint:
	black .

clean:
	rm -rf $(VENV_DIR)

run-tests:
	pytest -vv
