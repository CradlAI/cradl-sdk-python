CID := $(shell cat /tmp/prism.cid)

.PHONY: lint
lint:
	uv run --extra dev flake8 src tests
	uv run --extra dev mypy src tests

.PHONY: test
test:
	@echo "Running test suite..."
	uv run --extra dev pytest

.PHONY: prism-start
prism-start:
	@echo "Starting mock API..."
	docker run -t \
		--init \
		--detach \
		-p 4010:4010 \
		stoplight/prism:5.5.0 mock -d -h 0.0.0.0 \
		https://public.cradl.ai/api/openapi.json \
		> /tmp/prism.cid


.PHONY: prism-stop
prism-stop:
ifeq ("$(wildcard /tmp/prism.cid)","")
	@echo "Nothing to stop."
else
	docker stop $(CID)
endif

.PHONY: publish
publish:
	uv build
	uv publish
