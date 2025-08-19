VENV_DIR := .venv

venv: $(VENV_DIR)/touchfile

$(VENV_DIR)/touchfile: requirements.txt dev-requirements.txt
	test -d $(VENV_DIR) || virtualenv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate
	pip3 install --upgrade pip
	pip3 install -r requirements.txt
	pip3 install -r dev-requirements.txt
	touch $(VENV_DIR)/touchfile

lint:
	black .

clean:
	rm -rf $(VENV_DIR)

run-tests:
	pytest -vv
