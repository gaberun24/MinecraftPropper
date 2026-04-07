.PHONY: dev dev-setup install test lint

dev-setup:
	mkdir -p dev_minecraft/{world,world_nether,world_the_end,plugins/Geyser-Spigot,plugins/floodgate,logs}
	mkdir -p dev_backups/{daily,monthly,update}
	mkdir -p dev_versions
	echo "level-name=world" > dev_minecraft/server.properties
	echo "server-port=25565" >> dev_minecraft/server.properties
	echo "gamemode=survival" >> dev_minecraft/server.properties
	echo "difficulty=normal" >> dev_minecraft/server.properties
	echo "max-players=10" >> dev_minecraft/server.properties
	echo "motd=Minecraft Server" >> dev_minecraft/server.properties
	echo "paper-1.21.4-193" > dev_minecraft/VERSION
	echo "eula=true" > dev_minecraft/eula.txt
	echo "" > dev_minecraft/logs/latest.log
	touch dev_minecraft/world/level.dat
	@echo "Dev environment ready. Run 'make dev' to start."

dev:
	MCM_DEV_MODE=true \
	MCM_MINECRAFT_DIR=./dev_minecraft \
	MCM_BACKUP_DIR=./dev_backups \
	MCM_VERSIONS_DIR=./dev_versions \
	MCM_STDIN_PIPE=./dev_minecraft/stdin.pipe \
	uvicorn minecraft_manager.main:app --reload --host 0.0.0.0 --port 8000

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check minecraft_manager/ tests/
