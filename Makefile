SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

ARGS ?=

.PHONY: run

run: ## Starts local app
	scripts/dev app
