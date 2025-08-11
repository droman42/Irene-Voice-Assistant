#!/bin/bash
# ============================================================
# IRENE VOICE ASSISTANT - UNIVERSAL INSTALLATION SCRIPT
# ============================================================
# Installs Irene Voice Assistant with profile-based configuration
# Supports Ubuntu, Debian, CentOS, macOS with automatic platform detection
# Integrates with runtime build analyzer for precise dependency installation
#
# Usage:
#   ./install-irene.sh                    # Install minimal profile
#   ./install-irene.sh voice              # Install voice profile
#   ./install-irene.sh full --system      # Install full profile as system service
#   ./install-irene.sh development --user # Install development profile for user

set -e

# ============================================================
# CONFIGURATION AND CONSTANTS
# ============================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script metadata
SCRIPT_VERSION="1.0.0"
IRENE_VERSION="13.0.0"

# Default configuration
DEFAULT_PROFILE="minimal"
INSTALL_TYPE="user"  # user | system
SKIP_DEPS=false
FORCE_INSTALL=false
DRY_RUN=false
VERBOSE=false

# Installation paths
INSTALL_DIR=""
CONFIG_DIR=""
SERVICE_DIR=""
LOG_DIR=""

# Platform detection
PLATFORM=""
PACKAGE_MANAGER=""
INIT_SYSTEM=""

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${CYAN}[INFO]${NC}  $message" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC}  $message" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" >&2 ;;
        DEBUG) [[ "$VERBOSE" == "true" ]] && echo -e "${PURPLE}[DEBUG]${NC} $message" ;;
        SUCCESS) echo -e "${GREEN}[SUCCESS]${NC} $message" ;;
    esac
    
    # Log to file if available
    if [[ -n "$LOG_DIR" && -d "$LOG_DIR" ]]; then
        echo "[$timestamp] [$level] $message" >> "$LOG_DIR/irene-install.log"
    fi
}

show_header() {
    echo -e "${BLUE}"
    echo "============================================================"
    echo "🎙️  IRENE VOICE ASSISTANT - UNIVERSAL INSTALLER v$SCRIPT_VERSION"
    echo "============================================================"
    echo -e "${NC}"
    echo "Installing Irene Voice Assistant v$IRENE_VERSION"
    echo "Profile: $PROFILE | Install Type: $INSTALL_TYPE | Platform: Auto-detect"
    echo ""
}

show_usage() {
    cat << EOF
Usage: $0 [PROFILE] [OPTIONS]

PROFILES:
  minimal        Ultra-lightweight, text-only (default)
  voice          Full voice assistant capabilities
  api-only       Web API server without audio
  embedded-armv7 Raspberry Pi/embedded optimized
  full           Complete feature set
  development    All features + debugging tools

OPTIONS:
  --system       Install as system service (requires sudo)
  --user         Install for current user only (default)
  --skip-deps    Skip system dependency installation
  --force        Force installation over existing installation
  --dry-run      Show what would be installed without doing it
  --verbose      Enable verbose logging
  --help         Show this help message

EXAMPLES:
  $0                                    # Install minimal profile for user
  $0 voice --system                     # Install voice profile as system service
  $0 development --user --verbose       # Install dev profile with verbose output
  $0 full --dry-run                     # Preview full profile installation

REQUIREMENTS:
  - Python 3.11+ 
  - UV package manager (will be installed if missing)
  - sudo access (for system installation or system dependencies)

For more information, visit: https://github.com/irene-voice-assistant
EOF
}

# ============================================================
# PLATFORM DETECTION
# ============================================================

detect_platform() {
    log INFO "Detecting platform and package manager..."
    
    # Detect OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [[ -f /etc/os-release ]]; then
            source /etc/os-release
            case $ID in
                ubuntu|debian)
                    PLATFORM="debian"
                    PACKAGE_MANAGER="apt-get"
                    ;;
                centos|rhel|fedora)
                    PLATFORM="redhat"
                    PACKAGE_MANAGER="yum"
                    [[ -x "$(command -v dnf)" ]] && PACKAGE_MANAGER="dnf"
                    ;;
                arch)
                    PLATFORM="arch"
                    PACKAGE_MANAGER="pacman"
                    ;;
                alpine)
                    PLATFORM="alpine"
                    PACKAGE_MANAGER="apk"
                    ;;
                *)
                    PLATFORM="linux"
                    PACKAGE_MANAGER="unknown"
                    ;;
            esac
        else
            PLATFORM="linux"
            PACKAGE_MANAGER="unknown"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        PLATFORM="macos"
        PACKAGE_MANAGER="brew"
        [[ ! -x "$(command -v brew)" ]] && PACKAGE_MANAGER="unknown"
    else
        PLATFORM="unknown"
        PACKAGE_MANAGER="unknown"
    fi
    
    # Detect init system
    if [[ -d /run/systemd/system ]]; then
        INIT_SYSTEM="systemd"
    elif [[ -f /sbin/openrc ]]; then
        INIT_SYSTEM="openrc"
    elif [[ "$PLATFORM" == "macos" ]]; then
        INIT_SYSTEM="launchd"
    else
        INIT_SYSTEM="unknown"
    fi
    
    log INFO "Platform: $PLATFORM | Package Manager: $PACKAGE_MANAGER | Init System: $INIT_SYSTEM"
    
    if [[ "$PACKAGE_MANAGER" == "unknown" ]]; then
        log WARN "Unknown package manager. System dependencies must be installed manually."
    fi
}

# ============================================================
# PATH CONFIGURATION
# ============================================================

setup_paths() {
    log INFO "Setting up installation paths for $INSTALL_TYPE installation..."
    
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        INSTALL_DIR="/opt/irene"
        CONFIG_DIR="/etc/irene"
        LOG_DIR="/var/log/irene"
        
        case $INIT_SYSTEM in
            systemd)
                SERVICE_DIR="/etc/systemd/system"
                ;;
            openrc)
                SERVICE_DIR="/etc/init.d"
                ;;
            launchd)
                SERVICE_DIR="/Library/LaunchDaemons"
                ;;
            *)
                SERVICE_DIR="/etc/init.d"
                ;;
        esac
    else
        # User installation
        INSTALL_DIR="$HOME/.local/share/irene"
        CONFIG_DIR="$HOME/.config/irene"
        LOG_DIR="$HOME/.local/share/irene/logs"
        
        case $INIT_SYSTEM in
            systemd)
                SERVICE_DIR="$HOME/.config/systemd/user"
                ;;
            launchd)
                SERVICE_DIR="$HOME/Library/LaunchAgents"
                ;;
            *)
                SERVICE_DIR="$HOME/.config/irene/services"
                ;;
        esac
    fi
    
    log DEBUG "Install Directory: $INSTALL_DIR"
    log DEBUG "Config Directory: $CONFIG_DIR"
    log DEBUG "Log Directory: $LOG_DIR"
    log DEBUG "Service Directory: $SERVICE_DIR"
}

# ============================================================
# PREREQUISITE VALIDATION
# ============================================================

check_prerequisites() {
    log INFO "Checking prerequisites..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        log ERROR "Python 3 is not installed. Please install Python 3.11+ first."
        exit 1
    fi
    
    local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local required_version="3.11"
    
    if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
        log ERROR "Python $python_version detected. Python $required_version+ is required."
        exit 1
    fi
    
    log SUCCESS "Python $python_version detected (>= $required_version)"
    
    # Check UV package manager
    if ! command -v uv &> /dev/null; then
        log WARN "UV package manager not found. Installing UV..."
        install_uv
    else
        log SUCCESS "UV package manager found"
    fi
    
    # Check sudo for system installation
    if [[ "$INSTALL_TYPE" == "system" ]] && [[ $EUID -ne 0 ]]; then
        if ! command -v sudo &> /dev/null; then
            log ERROR "System installation requires sudo access, but sudo is not available."
            exit 1
        fi
        log INFO "System installation will require sudo privileges"
    fi
    
    # Check if profile exists
    if [[ ! -f "configs/${PROFILE}.toml" ]]; then
        log ERROR "Configuration profile '${PROFILE}' not found in configs/ directory"
        log INFO "Available profiles:"
        if command -v uv &> /dev/null && [[ -f "irene/tools/build_analyzer.py" ]]; then
            uv run python -m irene.tools.build_analyzer --list-profiles 2>/dev/null || true
        else
            ls configs/*.toml 2>/dev/null | sed 's/configs\///g; s/\.toml//g' | sed 's/^/  - /' || echo "  (none found)"
        fi
        exit 1
    fi
    
    log SUCCESS "Configuration profile '${PROFILE}' found"
}

install_uv() {
    log INFO "Installing UV package manager..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would install UV package manager"
        return
    fi
    
    if command -v curl &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget &> /dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        log ERROR "Neither curl nor wget available. Cannot install UV automatically."
        log INFO "Please install UV manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
    
    # Ensure UV is in PATH
    source "$HOME/.cargo/env" 2>/dev/null || true
    export PATH="$HOME/.cargo/bin:$PATH"
    
    if command -v uv &> /dev/null; then
        log SUCCESS "UV package manager installed successfully"
    else
        log ERROR "UV installation failed. Please install manually."
        exit 1
    fi
}

# ============================================================
# DEPENDENCY ANALYSIS AND INSTALLATION
# ============================================================

analyze_dependencies() {
    log INFO "Analyzing dependencies for profile: $PROFILE"
    
    # Run build analyzer to get dependency requirements
    local analyzer_output
    if ! analyzer_output=$(uv run python -m irene.tools.build_analyzer --config "configs/${PROFILE}.toml" --json 2>/dev/null); then
        log ERROR "Failed to analyze dependencies for profile: $PROFILE"
        log INFO "Ensure you're running this script from the Irene Voice Assistant project root directory"
        exit 1
    fi
    
    # Validate intent JSON configurations if intents are enabled
    local intent_files=$(echo "$analyzer_output" | jq -r '.intent_json_files[]?' 2>/dev/null | wc -l)
    if [[ "$intent_files" -gt 0 ]]; then
        log INFO "Found $intent_files intent JSON files, validating..."
        if ! uv run python -m irene.tools.intent_validator --validate-all --quiet 2>/dev/null; then
            log ERROR "Intent JSON validation failed"
            log INFO "Please check your intent handler JSON configurations for errors"
            if [[ "$FORCE_INSTALL" != "true" ]]; then
                exit 1
            fi
            log WARN "Continuing due to --force flag"
        else
            log SUCCESS "Intent JSON validation passed"
        fi
    else
        log INFO "No intent handlers enabled, skipping JSON validation"
    fi
    
    # Parse JSON output
    echo "$analyzer_output" > /tmp/irene-build-analysis.json
    
    # Extract system packages
    if command -v jq &> /dev/null; then
        local sys_packages=$(echo "$analyzer_output" | jq -r '.system_packages[]?' 2>/dev/null | tr '\n' ' ')
        local py_deps=$(echo "$analyzer_output" | jq -r '.python_dependencies[]?' 2>/dev/null | tr '\n' ' ')
        local modules=$(echo "$analyzer_output" | jq -r '.python_modules | length' 2>/dev/null)
        local valid=$(echo "$analyzer_output" | jq -r '.validation.valid' 2>/dev/null)
    else
        log WARN "jq not available. Using fallback dependency parsing."
        local sys_packages=$(uv run python -m irene.tools.build_analyzer --config "configs/${PROFILE}.toml" --system-install 2>/dev/null | grep "sudo apt-get install -y" | sed 's/sudo apt-get install -y //' || echo "")
        local py_deps=$(uv run python -m irene.tools.build_analyzer --config "configs/${PROFILE}.toml" --python-deps 2>/dev/null | grep "uv sync --extra" | sed 's/uv sync --extra //' || echo "")
        local modules="unknown"
        local valid="true"
    fi
    
    log INFO "Analysis complete:"
    log INFO "  📦 Python modules: $modules"
    log INFO "  🖥️  System packages: $(echo $sys_packages | wc -w)"
    log INFO "  🐍 Python dependencies: $(echo $py_deps | wc -w)"
    
    # Store for later use
    echo "$sys_packages" > /tmp/irene-system-packages.txt
    echo "$py_deps" > /tmp/irene-python-deps.txt
    
    if [[ "$valid" != "true" && "$valid" != "null" ]]; then
        log WARN "Build profile validation had warnings. Installation will continue."
    fi
}

install_system_dependencies() {
    local sys_packages=$(cat /tmp/irene-system-packages.txt 2>/dev/null || echo "")
    
    if [[ -z "$sys_packages" || "$SKIP_DEPS" == "true" ]]; then
        log INFO "No system dependencies to install or skipping dependency installation"
        return
    fi
    
    log INFO "Installing system dependencies: $sys_packages"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would install system packages: $sys_packages"
        return
    fi
    
    local install_cmd=""
    local update_cmd=""
    
    case $PACKAGE_MANAGER in
        apt-get)
            update_cmd="sudo apt-get update"
            install_cmd="sudo apt-get install -y $sys_packages"
            ;;
        yum)
            update_cmd="sudo yum check-update || true"
            install_cmd="sudo yum install -y $sys_packages"
            ;;
        dnf)
            update_cmd="sudo dnf check-update || true"
            install_cmd="sudo dnf install -y $sys_packages"
            ;;
        pacman)
            update_cmd="sudo pacman -Sy"
            install_cmd="sudo pacman -S --noconfirm $sys_packages"
            ;;
        apk)
            update_cmd="sudo apk update"
            install_cmd="sudo apk add $sys_packages"
            ;;
        brew)
            # Convert Linux packages to macOS equivalents
            local macos_packages=""
            for pkg in $sys_packages; do
                case $pkg in
                    libportaudio2) macos_packages="$macos_packages portaudio" ;;
                    libsndfile1) macos_packages="$macos_packages libsndfile" ;;
                    ffmpeg) macos_packages="$macos_packages ffmpeg" ;;
                    espeak*) macos_packages="$macos_packages espeak" ;;
                    *) macos_packages="$macos_packages $pkg" ;;
                esac
            done
            update_cmd="brew update"
            install_cmd="brew install $macos_packages"
            ;;
        *)
            log WARN "Unknown package manager. System dependencies must be installed manually:"
            log INFO "Required packages: $sys_packages"
            return
            ;;
    esac
    
    # Update package lists
    log INFO "Updating package lists..."
    if ! eval "$update_cmd"; then
        log WARN "Package list update failed, continuing with installation..."
    fi
    
    # Install packages
    log INFO "Installing system dependencies..."
    if ! eval "$install_cmd"; then
        log ERROR "System dependency installation failed"
        log INFO "You may need to install these packages manually: $sys_packages"
        if [[ "$FORCE_INSTALL" != "true" ]]; then
            exit 1
        fi
        log WARN "Continuing due to --force flag"
    else
        log SUCCESS "System dependencies installed successfully"
    fi
}

# ============================================================
# IRENE INSTALLATION
# ============================================================

create_directories() {
    log INFO "Creating installation directories..."
    
    local dirs=("$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR" "$SERVICE_DIR")
    
    for dir in "${dirs[@]}"; do
        if [[ "$DRY_RUN" == "true" ]]; then
            log INFO "[DRY RUN] Would create directory: $dir"
            continue
        fi
        
        if [[ "$INSTALL_TYPE" == "system" ]]; then
            sudo mkdir -p "$dir"
            sudo chown root:root "$dir"
            sudo chmod 755 "$dir"
        else
            mkdir -p "$dir"
        fi
        log DEBUG "Created directory: $dir"
    done
}

install_irene() {
    log INFO "Installing Irene Voice Assistant..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would install Irene to: $INSTALL_DIR"
        return
    fi
    
    # Copy application files
    log INFO "Copying application files..."
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        sudo cp -r irene/ "$INSTALL_DIR/"
        sudo cp -r configs/ "$INSTALL_DIR/"
        sudo cp -r schemas/ "$INSTALL_DIR/"
        sudo cp pyproject.toml uv.lock "$INSTALL_DIR/"
        sudo chown -R root:root "$INSTALL_DIR"
    else
        cp -r irene/ "$INSTALL_DIR/"
        cp -r configs/ "$INSTALL_DIR/"
        cp -r schemas/ "$INSTALL_DIR/"
        cp pyproject.toml uv.lock "$INSTALL_DIR/"
    fi
    
    # Install Python dependencies
    local py_deps=$(cat /tmp/irene-python-deps.txt 2>/dev/null | tr -d '\n')
    
    log INFO "Installing Python dependencies with UV..."
    cd "$INSTALL_DIR"
    
    # Always install jsonschema for intent validation
    log INFO "Installing base requirements including jsonschema for intent validation..."
    uv add jsonschema
    
    if [[ -n "$py_deps" ]]; then
        log INFO "Installing with extra dependencies: $py_deps"
        uv sync --extra $py_deps
    else
        log INFO "Installing base dependencies only"
        uv sync
    fi
    
    cd - > /dev/null
    
    # Copy configuration
    local config_file="$CONFIG_DIR/irene.toml"
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        sudo cp "configs/${PROFILE}.toml" "$config_file"
        sudo chown root:root "$config_file"
    else
        cp "configs/${PROFILE}.toml" "$config_file"
    fi
    
    log SUCCESS "Irene Voice Assistant installed successfully"
}

# ============================================================
# SERVICE CONFIGURATION
# ============================================================

generate_systemd_service() {
    local service_file="$SERVICE_DIR/irene.service"
    local service_content=""
    
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        service_content="[Unit]
Description=Irene Voice Assistant
After=network.target
Wants=network.target

[Service]
Type=simple
User=irene
Group=irene
WorkingDirectory=$INSTALL_DIR
Environment=IRENE_CONFIG_FILE=$CONFIG_DIR/irene.toml
Environment=PYTHONPATH=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/python -m irene.runners.cli --config $CONFIG_DIR/irene.toml
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=irene

[Install]
WantedBy=multi-user.target"
    else
        service_content="[Unit]
Description=Irene Voice Assistant (User)
After=default.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
Environment=IRENE_CONFIG_FILE=$CONFIG_DIR/irene.toml
Environment=PYTHONPATH=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/python -m irene.runners.cli --config $CONFIG_DIR/irene.toml
Restart=always
RestartSec=10

[Install]
WantedBy=default.target"
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would create systemd service file: $service_file"
        return
    fi
    
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        echo "$service_content" | sudo tee "$service_file" > /dev/null
        sudo chmod 644 "$service_file"
        
        # Create irene user if system installation
        if ! id "irene" &>/dev/null; then
            sudo useradd -r -s /bin/false -d "$INSTALL_DIR" irene
            sudo chown -R irene:irene "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR"
        fi
    else
        echo "$service_content" > "$service_file"
        chmod 644 "$service_file"
    fi
    
    log SUCCESS "Systemd service file created: $service_file"
}

generate_launchd_service() {
    local service_file=""
    local service_content=""
    
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        service_file="$SERVICE_DIR/com.irene.voiceassistant.plist"
        service_content="<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
    <key>Label</key>
    <string>com.irene.voiceassistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/.venv/bin/python</string>
        <string>-m</string>
        <string>irene.runners.cli</string>
        <string>--config</string>
        <string>$CONFIG_DIR/irene.toml</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>IRENE_CONFIG_FILE</key>
        <string>$CONFIG_DIR/irene.toml</string>
        <key>PYTHONPATH</key>
        <string>$INSTALL_DIR</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/irene.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/irene.log</string>
</dict>
</plist>"
    else
        service_file="$SERVICE_DIR/com.irene.voiceassistant.plist"
        service_content="<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
    <key>Label</key>
    <string>com.irene.voiceassistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/.venv/bin/python</string>
        <string>-m</string>
        <string>irene.runners.cli</string>
        <string>--config</string>
        <string>$CONFIG_DIR/irene.toml</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>IRENE_CONFIG_FILE</key>
        <string>$CONFIG_DIR/irene.toml</string>
        <key>PYTHONPATH</key>
        <string>$INSTALL_DIR</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>"
    fi
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would create launchd service file: $service_file"
        return
    fi
    
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        echo "$service_content" | sudo tee "$service_file" > /dev/null
        sudo chmod 644 "$service_file"
    else
        echo "$service_content" > "$service_file"
        chmod 644 "$service_file"
    fi
    
    log SUCCESS "Launchd service file created: $service_file"
}

setup_service() {
    log INFO "Setting up system service..."
    
    case $INIT_SYSTEM in
        systemd)
            generate_systemd_service
            if [[ "$DRY_RUN" != "true" ]]; then
                if [[ "$INSTALL_TYPE" == "system" ]]; then
                    sudo systemctl daemon-reload
                    log INFO "Service installed. Use 'sudo systemctl start irene' to start"
                    log INFO "Use 'sudo systemctl enable irene' to start automatically on boot"
                else
                    systemctl --user daemon-reload
                    log INFO "Service installed. Use 'systemctl --user start irene' to start"
                    log INFO "Use 'systemctl --user enable irene' to start automatically on login"
                fi
            fi
            ;;
        launchd)
            generate_launchd_service
            if [[ "$DRY_RUN" != "true" ]]; then
                if [[ "$INSTALL_TYPE" == "system" ]]; then
                    log INFO "Service installed. Use 'sudo launchctl load $SERVICE_DIR/com.irene.voiceassistant.plist' to start"
                else
                    log INFO "Service installed. Use 'launchctl load $SERVICE_DIR/com.irene.voiceassistant.plist' to start"
                fi
            fi
            ;;
        *)
            log WARN "Unknown init system ($INIT_SYSTEM). Service files not created."
            log INFO "You can run Irene manually with:"
            log INFO "cd $INSTALL_DIR && .venv/bin/python -m irene.runners.cli --config $CONFIG_DIR/irene.toml"
            ;;
    esac
}

# ============================================================
# POST-INSTALLATION TASKS
# ============================================================

create_wrapper_script() {
    local wrapper_path=""
    
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        wrapper_path="/usr/local/bin/irene"
    else
        wrapper_path="$HOME/.local/bin/irene"
        mkdir -p "$HOME/.local/bin"
    fi
    
    local wrapper_content="#!/bin/bash
# Irene Voice Assistant Wrapper Script
# Generated by install-irene.sh

export IRENE_CONFIG_FILE=\"$CONFIG_DIR/irene.toml\"
export PYTHONPATH=\"$INSTALL_DIR\"

cd \"$INSTALL_DIR\"
exec .venv/bin/python -m irene.runners.cli \"\$@\"
"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "[DRY RUN] Would create wrapper script: $wrapper_path"
        return
    fi
    
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        echo "$wrapper_content" | sudo tee "$wrapper_path" > /dev/null
        sudo chmod +x "$wrapper_path"
    else
        echo "$wrapper_content" > "$wrapper_path"
        chmod +x "$wrapper_path"
    fi
    
    log SUCCESS "Wrapper script created: $wrapper_path"
}

show_completion_summary() {
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}🎉 IRENE VOICE ASSISTANT INSTALLATION COMPLETE!${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo -e "${BLUE}Installation Summary:${NC}"
    echo "  📦 Profile: $PROFILE"
    echo "  🏠 Install Type: $INSTALL_TYPE"
    echo "  📂 Install Directory: $INSTALL_DIR"
    echo "  ⚙️  Config Directory: $CONFIG_DIR"
    echo "  📝 Log Directory: $LOG_DIR"
    echo ""
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}This was a dry run. No actual installation was performed.${NC}"
        echo ""
        return
    fi
    
    echo -e "${BLUE}Quick Start:${NC}"
    
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        echo "  # Start Irene service"
        case $INIT_SYSTEM in
            systemd)
                echo "  sudo systemctl start irene"
                echo "  sudo systemctl enable irene  # Start on boot"
                echo ""
                echo "  # Check status"
                echo "  sudo systemctl status irene"
                echo "  sudo journalctl -u irene -f"
                ;;
            launchd)
                echo "  sudo launchctl load $SERVICE_DIR/com.irene.voiceassistant.plist"
                ;;
            *)
                echo "  # Run manually"
                echo "  cd $INSTALL_DIR && .venv/bin/python -m irene.runners.cli --config $CONFIG_DIR/irene.toml"
                ;;
        esac
    else
        echo "  # Start Irene service"
        case $INIT_SYSTEM in
            systemd)
                echo "  systemctl --user start irene"
                echo "  systemctl --user enable irene  # Start on login"
                echo ""
                echo "  # Check status"
                echo "  systemctl --user status irene"
                echo "  journalctl --user -u irene -f"
                ;;
            launchd)
                echo "  launchctl load $SERVICE_DIR/com.irene.voiceassistant.plist"
                ;;
            *)
                echo "  # Run manually"
                echo "  cd $INSTALL_DIR && .venv/bin/python -m irene.runners.cli --config $CONFIG_DIR/irene.toml"
                ;;
        esac
    fi
    
    echo ""
    echo "  # Or use the wrapper script"
    if [[ "$INSTALL_TYPE" == "system" ]]; then
        echo "  irene --help"
    else
        echo "  $HOME/.local/bin/irene --help"
        echo "  # Add $HOME/.local/bin to your PATH for easier access"
    fi
    
    echo ""
    echo -e "${BLUE}Configuration:${NC}"
    echo "  📝 Edit config: $CONFIG_DIR/irene.toml"
    echo "  📋 Available profiles: configs/ directory"
    echo "  🔧 Build analyzer: uv run python -m irene.tools.build_analyzer --help"
    
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "  1. Review and customize the configuration file"
    echo "  2. Set up any required API keys (OpenAI, ElevenLabs, etc.)"
    echo "  3. Start the service and check the logs"
    echo "  4. Test with your first voice command!"
    
    echo ""
    echo -e "${CYAN}For help and documentation:${NC}"
    echo "  🌐 GitHub: https://github.com/irene-voice-assistant"
    echo "  📚 Docs: README-DOCKER.md, docs/"
    echo "  🐛 Issues: Report any problems on GitHub"
    
    echo ""
    log SUCCESS "Installation completed successfully! 🎉"
}

# ============================================================
# MAIN INSTALLATION FLOW
# ============================================================

main() {
    # Parse command line arguments
    local profile_set=false
    
    # Check for help first
    for arg in "$@"; do
        if [[ "$arg" == "--help" || "$arg" == "-h" ]]; then
            show_usage
            exit 0
        fi
    done
    
    # Parse remaining arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --system)
                INSTALL_TYPE="system"
                shift
                ;;
            --user)
                INSTALL_TYPE="user"
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --force)
                FORCE_INSTALL=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -*)
                log ERROR "Unknown option: $1"
                show_usage
                exit 1
                ;;
            *)
                if [[ "$profile_set" == "false" ]]; then
                    PROFILE="$1"
                    profile_set=true
                else
                    log ERROR "Multiple profiles specified: $PROFILE and $1"
                    show_usage
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # Set default profile if none specified
    if [[ "$profile_set" == "false" ]]; then
        PROFILE="$DEFAULT_PROFILE"
    fi
    
    # Main installation flow
    show_header
    detect_platform
    setup_paths
    check_prerequisites
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "DRY RUN MODE - No actual changes will be made"
    fi
    
    analyze_dependencies
    create_directories
    install_system_dependencies
    install_irene
    setup_service
    create_wrapper_script
    show_completion_summary
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 