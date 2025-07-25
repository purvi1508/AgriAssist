# Makefile to clean all temporary / chance files

.PHONY: clean

clean:
	@echo "Removing Python bytecode and cache files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +
	find . -type f -name "*.log" -delete
	find . -type f -name "*.tmp" -delete
	find . -type f -name "*.DS_Store" -delete
	find . -type d -name "build" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

	@echo "All temporary and cache files cleaned."
