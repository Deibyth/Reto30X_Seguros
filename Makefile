.PHONY: dev backend frontend build shell clean

dev:          ## Start all services
	docker compose up --build

backend:      ## Start backend only
	docker compose up --build backend

frontend:     ## Start frontend only
	docker compose up --build frontend

build:        ## Build all images
	docker compose build

shell:        ## Open backend Python shell
	docker compose exec backend python

clean:        ## Stop and remove containers + volumes
	docker compose down -v
