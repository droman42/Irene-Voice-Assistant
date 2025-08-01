# UV Migration Guide

This project has been migrated from pip to UV for faster and more reliable dependency management.

## What Changed

- ✅ **Replaced** `requirements.txt` → `pyproject.toml` with organized dependency groups
- ✅ **Added** virtual environment management with UV
- ✅ **Organized** dependencies into logical groups (core, web, ui, minimal, dev)
- ✅ **Improved** dependency resolution and installation speed

## Installation Options

### 1. **Core Installation** (Basic functionality)
```bash
uv sync  # Installs core dependencies
```
Includes: vosk, pyttsx3, sounddevice, termcolor, openai, elevenlabs, etc.

### 2. **With Web API Support**
```bash
uv sync --extra web
```
Adds: fastapi, uvicorn, starlette for web server functionality

### 3. **With UI Support** (Gradio for settings)
```bash
uv sync --extra ui
```
Adds: gradio for web-based settings manager

### 4. **Minimal Installation** (Lightweight)
```bash
uv sync --extra minimal
```
Only essential dependencies for basic voice assistant functionality

### 5. **Development Setup**
```bash
uv sync --extra dev
```
Adds: pytest, black, isort, flake8, mypy for development tools

### 6. **Multiple Groups**
```bash
uv sync --extra web --extra ui --extra dev
```

## Running the Application

### With UV Virtual Environment
```bash
# Activate the environment and run
uv run python runva_vosk.py

# Or activate manually then run normally
source .venv/bin/activate  # Linux/Mac
python runva_vosk.py
```

### Common Commands
```bash
# Install new dependency
uv add package_name

# Remove dependency  
uv remove package_name

# Update all dependencies
uv sync --upgrade

# Show installed packages
uv pip list

# Export to requirements.txt (if needed)
uv pip freeze > requirements.txt
```

## Benefits of UV

- 🚀 **10-100x faster** than pip for dependency resolution
- 📦 **Better dependency resolution** - catches conflicts early  
- 🔒 **Deterministic builds** with lockfile (uv.lock)
- 🎯 **Project isolation** with automatic virtual environments
- ⚡ **Parallel downloads** and installations
- 🛠️ **Modern tool** built in Rust for performance

## Migration Details

### Dependency Groups
- **Core**: Essential voice assistant functionality
- **Web**: FastAPI web server for remote access
- **UI**: Gradio for web-based configuration
- **Minimal**: Lightweight subset for limited environments  
- **Dev**: Development and testing tools

### Removed Problematic Dependencies
- Temporarily removed `docker` group due to `lingua-franca` conflicts
- Can be added back with manual resolution if needed

### Files
- ✅ `pyproject.toml` - New unified configuration
- ⚠️  `requirements*.txt` - Legacy files (can be removed after testing)
- ✅ `.venv/` - UV-managed virtual environment
- ✅ `uv.lock` - Dependency lockfile for reproducible builds

## Troubleshooting

### If you get dependency conflicts:
```bash
uv sync --resolution lowest-direct  # Try older compatible versions
uv sync --no-deps  # Skip dependency resolution
```

### To use specific Python version:
```bash
uv python install 3.10
uv sync --python 3.10
```

### To reset environment:
```bash
rm -rf .venv uv.lock
uv sync
```

## Legacy Compatibility

The old pip-based installation still works:
```bash
pip install -r requirements.txt
```

But UV is recommended for:
- Faster installations
- Better dependency management  
- Modern Python workflow
- Reproducible environments

## Next Steps

1. ✅ Test core functionality: `uv run python runva_vosk.py`
2. ✅ Test web API: `uv sync --extra web && uv run python runva_webapi.py`  
3. ✅ Remove old requirements files after verification
4. ✅ Update CI/CD to use UV instead of pip
5. ✅ Consider adding more dependency groups as needed 