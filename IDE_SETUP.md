# IDE Setup Guide for UV Environment

This guide helps you configure your IDE to work properly with the UV virtual environment.

## VS Code Setup

### ✅ **Automatic Configuration** (Already Done)
The `.vscode/settings.json` file has been created with optimal settings:

```json
{
    "python.defaultInterpreter": "./.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false, 
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.analysis.extraPaths": [
        "./plugins",
        "./utils", 
        "./mpcapi",
        "./lingua_franca",
        "./eng_to_ipa"
    ],
    "python.analysis.autoImportCompletions": true,
    "python.analysis.typeCheckingMode": "basic"
}
```

### 🔧 **Manual Setup** (If needed)

1. **Select Python Interpreter**:
   - Open Command Palette (`Ctrl+Shift+P`)
   - Type "Python: Select Interpreter"
   - Choose: `/home/droman42/development/Irene-Voice-Assistant/.venv/bin/python`

2. **Reload VS Code Window**:
   - Command Palette → "Developer: Reload Window"
   - This ensures all language services pick up the new interpreter

3. **Verify Setup**:
   - Open any `.py` file
   - Check bottom-left status bar shows: `Python 3.10.x ('.venv': venv)`
   - Try importing `termcolor` - it should resolve without errors

## PyCharm/IntelliJ Setup

### **Configure Project Interpreter**:
1. File → Settings → Project → Python Interpreter
2. Click gear icon → Add...
3. Choose "Existing environment"
4. Path: `/home/droman42/development/Irene-Voice-Assistant/.venv/bin/python`
5. Apply and restart IDE

## Other IDEs

### **Vim/Neovim with LSP**:
```bash
# Activate UV environment first
source .venv/bin/activate
# Then start vim/nvim
```

### **Emacs with Python LSP**:
```elisp
(setq lsp-pyright-venv-path "/home/droman42/development/Irene-Voice-Assistant/.venv")
```

### **Sublime Text**:
1. Tools → Build System → New Build System
2. Use this configuration:
```json
{
    "cmd": ["/home/droman42/development/Irene-Voice-Assistant/.venv/bin/python", "$file"],
    "selector": "source.python"
}
```

## Troubleshooting

### ❌ **"Import could not be resolved"**
**Cause**: IDE not using UV virtual environment

**Solutions**:
1. Restart VS Code completely
2. Manually select interpreter (see Manual Setup above)
3. Check `.vscode/settings.json` exists and is correct
4. Verify UV environment: `ls -la .venv/bin/python`

### ❌ **"No module named 'xyz'"**
**Cause**: Missing dependencies in UV environment

**Solutions**:
```bash
# Check if dependency is installed
uv pip list | grep xyz

# Install missing dependency
uv add xyz

# Sync all dependencies
uv sync
```

### ❌ **Linting/Formatting Not Working**
**Cause**: Development tools not installed

**Solutions**:
```bash
# Install development dependencies
uv sync --extra dev

# Or install individual tools
uv add black flake8 mypy --dev
```

### ❌ **Terminal Not Using UV Environment**
**Cause**: VS Code terminal not activating UV environment

**Solutions**:
1. Check `"python.terminal.activateEnvironment": true` in settings
2. Manually activate: `source .venv/bin/activate`
3. Use UV commands: `uv run python script.py`

## Testing Your Setup

### **Quick Test**:
```bash
# Test UV environment
uv run python -c "import termcolor; print('✅ UV environment works!')"

# Test imports in VS Code
# Open jaa.py and verify no import errors for termcolor
```

### **Full Test**:
```bash
# Test core functionality
uv run python -c "import vacore; print('✅ VACore imports')"

# Test audio dependencies
uv run python -c "import vosk, pyttsx3; print('✅ Audio deps work')"

# Test development tools
uv run black --check .
uv run flake8 --version
```

## Environment Information

- **Python Path**: `/home/droman42/development/Irene-Voice-Assistant/.venv/bin/python`
- **UV Lock File**: `uv.lock` (contains exact versions)
- **Configuration**: `pyproject.toml` (dependency groups)
- **VS Code Settings**: `.vscode/settings.json` (IDE configuration)

## Development Workflow

### **Recommended Workflow**:
```bash
# Activate environment (if needed)
source .venv/bin/activate

# Install new dependency
uv add package_name

# Run application  
uv run python runva_vosk.py

# Format code
uv run black .

# Check linting
uv run flake8 .

# Run tests
uv run pytest
```

### **VS Code Integrated Terminal**:
The UV environment should activate automatically in VS Code terminals. If not:
```bash
source .venv/bin/activate
```

## Next Steps

1. ✅ Restart VS Code to apply settings
2. ✅ Open `jaa.py` and verify `termcolor` import resolves
3. ✅ Test running a Python file with F5 or Ctrl+F5
4. ✅ Verify terminal activates UV environment
5. ✅ Test linting and formatting functionality 