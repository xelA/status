APP_NAME = Status
PRISMA_SCHEME = "./schema.prisma"

target:
	@awk -F ':|##' '/^[^\t].+?:.*?##/ { printf "\033[0;36m%-15s\033[0m %s\n", $$1, $$NF }' $(MAKEFILE_LIST)

install:  ## Install the project
	uv sync

install_dev:	 ## Install the package in development mode
	uv sync --all-extras

git_pull:  ## Pull the latest code from git
	git pull

pm2_start:  ## Create a PM2 instance
	pm2 start uv --name $(APP_NAME) --interpreter none -- run index.py -u

pm2_restart:  ## Restart PM2
	pm2 restart $(APP_NAME)

soft_update: git_pull pm2_restart  ## Pull and reboot PM2
update: git_pull db_push pm2_restart  ## Pull, push database and reboot PM2

db_push:  ## Update the database with Prisma
	uv run prisma format --schema $(PRISMA_SCHEME)
	uv run prisma db push --schema $(PRISMA_SCHEME) --skip-generate

db_pull:  ## Pull the database from Prisma
	uv run prisma db pull --schema $(PRISMA_SCHEME)

db_format:	## Format to make Prisma happy
	uv run prisma format --schema $(PRISMA_SCHEME)
