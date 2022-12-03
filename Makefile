# Makefile Version 2021032403
#
# Source in repository specific environment variables
include .config.mk

POETRY_COMMAND := poetry

# Exports the variables for shell use
export

# This helper function makes debugging much easier.
.PHONY:debug-%
debug-%: ## Debug a variable by calling `make debug-VARIABLE`
	@echo $(*) = $($(*))

.PHONY:help
.SILENT:help
help: ## Show this help, includes list of all actions.
	@awk 'BEGIN {FS = ":.*?## "}; /^.+: .*?## / && !/awk/ {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' ${MAKEFILE_LIST}

.PHONY:run
run: install ## purge build time artifacts
	$(DOCKER_COMMAND) bash

.PHONY:clean
clean: ## purge build time artifacts
	rm -rf dist/ build/ coverage/ pypoetry/ pip/ **/__pycache__/ .pytest_cache/ .cache .coverage

.PHONY:changelog
changelog: install ## print the next version of the change log to stdout
	$(POETRY_COMMAND) run semantic-release changelog --unreleased

.PHONY:install
install: ## install development and build time dependencies
	$(POETRY_COMMAND) install --no-interaction

.PHONY:lint
lint: install ## run lint rules and print error report
	$(POETRY_COMMAND) run task lint

.PHONY:lint-fix
lint-fix: install ## attempt to auto fix linting error and report remaining errors
	$(POETRY_COMMAND) run task lint:fix

.PHONY:build
build: install
	$(POETRY_COMMAND) run task create_version_file 
	$(POETRY_COMMAND) run task create_exe

.PHONY:package
package: install ## Generate a python sdist and wheel
	$(POETRY_COMMAND) build

.PHONY:release
release: clean install fetch-tags ## run semantic release build and publish results to github + pypi based on unreleased commits
	$(POETRY_COMMAND) run task release

.PHONY: fetch-tags
fetch-tags:  ## workaround for jenkins repo cloning behavior
	git fetch origin --tags

.PHONY:release-dry
release-dry: clean install fetch-tags changelog ## run semantic release in noop mode
	$(POETRY_COMMAND) run semantic-release publish --noop --verbosity=DEBUG

.PHONY:release-patch
release-patch: clean install ## run semantic release build and force a patch release
	$(POETRY_COMMAND) run semantic-release publish --patch

.PHONY:release-minor
release-minor: clean install                    ## run semantic release build and force a minor release
	$(POETRY_COMMAND) run semantic-release publish --minor

.PHONY:release-major
release-major: clean install                    ## run semantic release build and force a major release
	$(POETRY_COMMAND) run semantic-release publish --major

.PHONY:test
test: install ## run project test suite
	$(POETRY_COMMAND) run task pre_test
	$(POETRY_COMMAND) run task test
	$(POETRY_COMMAND) run task post_test
