IMAGE ?= docker.io/umairedu/kube-right-sizer:latest

.PHONY: check lint test chart demo demo-down image clean

check: lint test chart

lint:
	uv run ruff check .

test:
	uv run pytest -q

chart:
	helm lint chart
	helm template t chart > /dev/null
	helm template t chart -f demo/values.yaml --set slack.channel=C0123,slack.token=x > /dev/null

demo:
	./demo/run.sh

demo-down:
	kind delete cluster --name right-sizer-demo

image:
	docker build -t $(IMAGE) .

clean:
	rm -rf .venv .pytest_cache .ruff_cache out
	find . -name __pycache__ -prune -exec rm -rf {} +
