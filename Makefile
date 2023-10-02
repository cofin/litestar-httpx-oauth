# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
.DEFAULT_GOAL:=help
.ONESHELL:
ENV_PREFIX=$(shell python3 -c "if __import__('pathlib').Path('.venv/bin/pip').exists(): print('.venv/bin/')")
USING_POETRY=$(shell grep "tool.poetry" pyproject.toml && echo "yes")
POETRY_INSTALLED=$(shell if poetry --version > /dev/null; then echo "yes"; fi)
VENV_EXISTS=$(shell python3 -c "if __import__('pathlib').Path('.venv/bin/activate').exists(): print('yes')")
# grep the version from pyproject.toml, squeeze multiple spaces, delete double
#   and single quotes, get 3rd val. This command tolerates
#   multiple whitespace sequences around the version number
VERSION := $(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)


.EXPORT_ALL_VARIABLES:

ifndef VERBOSE
.SILENT:
endif


help:											## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


.PHONY: upgrade
upgrade:									## Upgrade all dependencies to the latest stable versions
	@if [ "$(USING_POETRY)" ]; then poetry update; fi
	@echo "Python Dependencies Updated"


.PHONY: install
install:									## Install the project in dev mode.
	@if ! poetry --version > /dev/null; then echo 'poetry is required, installing from from https://install.python-poetry.org'; curl -sSL https://install.python-poetry.org | python3 -; fi
	@if [ "$(VENV_EXISTS)" ]; then echo "Removing existing environment" && rm -Rf .venv;  fi
	@if [ "$(USING_POETRY)" ]; then poetry config virtualenvs.in-project true --local  && poetry config virtualenvs.options.always-copy true --local && python3 -m venv --copies .venv && source $(ENV_PREFIX)/activate && $(ENV_PREFIX)/pip3 install -U cython pip nodeenv && poetry install --with dev; fi
	@echo "=> Install complete.  ** If you want to re-install re-run 'make install'"


.PHONY: clean
clean:										## remove all build, testing, and static documentation files
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +
	find . -name '.ipynb_checkpoints' -exec rm -fr {} +
	find . -name '.terraform' -exec rm -fr {} +
	rm -fr .tox/
	rm -fr .coverage
	rm -fr coverage.xml
	rm -fr coverage.json
	rm -fr htmlcov/
	rm -fr .pytest_cache
	rm -fr .mypy_cache
	rm -fr site


.PHONY: test
test:												## Test project files
	@echo "=> Launching Python test cases..."
	@$(ENV_PREFIX)pytest tests/
 