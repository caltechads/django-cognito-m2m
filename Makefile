RAWVERSION = $(filter-out __version__ = , $(shell grep __version__ django_cognito_m2m/__init__.py))
VERSION = $(strip $(shell echo $(RAWVERSION)))

PACKAGE = django-cognito-m2m

clean:
	rm -rf *.tar.gz dist build *.egg-info *.rpm
	find . -name "*.pyc" | xargs rm
	find . -name "__pycache__" | xargs rm -rf

version:
	@echo $(VERSION)

dist: clean
	@hatch build

release: dist
	@bin/release.sh

compile: uv.lock
	@uv pip compile pyproject.toml -o requirements.txt

.PHONY: check-branch check-clean _release \
        release-dev release-patch release-minor release-major

# Allow overriding the main branch (defaults to master)
MAIN_BRANCH ?= master

# --- Gate checks ---
check-branch:
	@branch="$$(git rev-parse --abbrev-ref HEAD)"; \
	[[ "$$branch" == "$(MAIN_BRANCH)" ]] || { echo "You're not on $(MAIN_BRANCH); aborting."; exit 1; }

check-clean:
	@[[ -z "$$(git status --untracked-files=no --porcelain)" ]] || { echo "You have uncommitted changes; aborting."; exit 1; }

# --- Shared release pipeline ---
# Expects BUMP=dev|patch|minor|major
_release: compile check-branch check-clean
	@echo "Releasing $(BUMP) version"
	@bump-my-version bump "$(BUMP)"
	${MAKE} release

# --- Explicit release targets (better tab-complete & discoverability) ---
release-dev:
	$(MAKE) _release BUMP=dev

release-patch:
	$(MAKE) _release BUMP=patch

release-minor:
	$(MAKE) _release BUMP=minor

release-major:
	$(MAKE) _release BUMP=major
