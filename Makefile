.PHONY: dev/up
dev/up:
	docker compose -p rag up --build --force-recreate


.PHONY: dev/down
dev/down:
	docker compose -p rag down


.PHONY: opensearch/setup
opensearch/setup:
	python3 opensearch-manager.py


.PHONY: huggingface/login
huggingface/login:
	huggingface-cli login


.PHONY: huggingface/logout
huggingface/logout:
	huggingface-cli logout
