# Irene Voice Assistant - Multi-Platform Docker Builds

This document describes the new multi-platform Docker build system for Irene Voice Assistant, which provides optimized builds for different platforms and use cases.

## 🐳 Available Docker Builds

### x86_64 Platform (Ubuntu-based)
- **File**: `Dockerfile.x86_64`
- **Base**: Python 3.11 on Ubuntu slim
- **Optimized for**: Desktop, server, and cloud deployments
- **Features**: Full system package support, ML model compatibility

### ARMv7 Platform (Alpine-based)
- **File**: `Dockerfile.armv7`
- **Base**: Python 3.11 on Alpine Linux
- **Optimized for**: Raspberry Pi, embedded devices, IoT deployments
- **Features**: Minimal size, cross-compilation, resource efficiency

## 🚀 Quick Start

### Build for x86_64 (Desktop/Server)
```bash
# Minimal build (text-only, ultra-lightweight)
docker build -f Dockerfile.x86_64 --build-arg CONFIG_PROFILE=minimal -t irene:minimal-x86 .

# Voice assistant build (full voice capabilities)
docker build -f Dockerfile.x86_64 --build-arg CONFIG_PROFILE=voice -t irene:voice-x86 .

# Development build (all features enabled)
docker build -f Dockerfile.x86_64 --build-arg CONFIG_PROFILE=development -t irene:dev-x86 .
```

### Build for ARMv7 (Raspberry Pi/Embedded)
```bash
# Embedded optimized build
docker buildx build --platform linux/arm/v7 -f Dockerfile.armv7 --build-arg CONFIG_PROFILE=embedded-armv7 -t irene:embedded-arm .

# Minimal build for ARM
docker buildx build --platform linux/arm/v7 -f Dockerfile.armv7 --build-arg CONFIG_PROFILE=minimal -t irene:minimal-arm .

# Voice build for ARM (requires sufficient RAM)
docker buildx build --platform linux/arm/v7 -f Dockerfile.armv7 --build-arg CONFIG_PROFILE=voice -t irene:voice-arm .
```

## 📋 Configuration Profiles

The Docker builds use configuration profiles from the `configs/` directory:

| Profile | Description | System Packages | Python Dependencies | Use Case |
|---------|-------------|-----------------|-------------------|----------|
| `minimal` | Ultra-lightweight, text-only | 0 | 0 | Testing, text processing |
| `voice` | Full voice capabilities | 6 | 6 | Voice assistant development |
| `api-only` | Web API server | Variable | Variable | API deployments |
| `embedded-armv7` | Raspberry Pi optimized | Variable | Variable | Embedded devices |
| `full` | Complete feature set | Variable | Variable | Full deployments |
| `development` | All features + debugging | Variable | Variable | Development work |

## 🔍 Build Analysis

The Docker builds use the runtime build analyzer to determine precisely which dependencies to install:

```bash
# Analyze what a specific profile requires
uv run python -m irene.tools.build_analyzer --config configs/voice.toml --docker

# List all available profiles
uv run python -m irene.tools.build_analyzer --list-profiles

# Validate all profiles
uv run python -m irene.tools.build_analyzer --validate-all-profiles
```

## 🏗️ Multi-Stage Build Architecture

Both Dockerfiles use a 3-stage build process:

### Stage 1: Build Analyzer
- Analyzes the selected configuration profile
- Generates precise dependency lists
- Maps system packages to platform-specific equivalents
- Creates build requirements for next stages

### Stage 2: Dependency Builder
- Installs UV package manager
- Installs only required system dependencies
- Installs only required Python dependencies
- Optimizes for the target platform

### Stage 3: Runtime
- Minimal runtime image
- Copies only analyzed dependencies
- Sets up non-root user for security
- Configures health checks and runtime environment

## 🎯 Platform Optimizations

### x86_64 Optimizations
- Ubuntu-based for full package compatibility
- Support for heavy ML models and frameworks
- Optimized layer caching for CI/CD
- Full system package availability

### ARMv7 Optimizations
- Alpine Linux for minimal image size
- Package mapping (Ubuntu → Alpine equivalents)
- Cross-compilation support
- Memory and resource constraints optimization
- Bytecode pre-compilation for performance

## 🔧 Configuration Options

### Build Arguments
- `CONFIG_PROFILE`: Selects which configuration profile to use (default: `minimal` for x86_64, `embedded-armv7` for ARMv7)

### Environment Variables (Runtime)
- `IRENE_CONFIG_FILE`: Path to configuration file (default: `/app/runtime-config.toml`)
- `PYTHONPATH`: Python module search path (default: `/app`)

### Exposed Ports
- `8000`: Web API (if enabled in profile)
- `9090`: Metrics endpoint (x86_64 only, if enabled)

## 🧪 Testing and Validation

### Test Build Analyzer
```bash
# Test all profiles with build analyzer
./test-build-analyzer.sh
```

### Test Docker Builds
```bash
# Test Docker build syntax (dry-run)
./test-docker-builds.sh
```

### Manual Testing
```bash
# Build and run minimal x86_64 image
docker build -f Dockerfile.x86_64 --build-arg CONFIG_PROFILE=minimal -t irene:test .
docker run --rm irene:test python -c "import irene; print('✅ Irene is working!')"

# Build and run embedded ARMv7 image
docker buildx build --platform linux/arm/v7 -f Dockerfile.armv7 --build-arg CONFIG_PROFILE=embedded-armv7 -t irene:test-arm .
docker run --rm --platform linux/arm/v7 irene:test-arm python -c "import irene; print('✅ Irene ARM is working!')"
```

## 📦 Image Sizes (Estimated)

| Profile | x86_64 Size | ARMv7 Size | Efficiency |
|---------|-------------|------------|------------|
| minimal | ~150 MB | ~80 MB | 47% reduction |
| voice | ~800 MB | ~400 MB | 50% reduction |
| full | ~1.2 GB | ~600 MB | 50% reduction |

## 🚀 Production Deployment

### Docker Compose Example
```yaml
version: '3.8'
services:
  irene-voice:
    image: irene:voice-x86
    build:
      context: .
      dockerfile: Dockerfile.x86_64
      args:
        CONFIG_PROFILE: voice
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
      - ./cache:/app/cache
    restart: unless-stopped
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: irene-voice-assistant
spec:
  replicas: 1
  selector:
    matchLabels:
      app: irene
  template:
    metadata:
      labels:
        app: irene
    spec:
      containers:
      - name: irene
        image: irene:voice-x86
        ports:
        - containerPort: 8000
        env:
        - name: IRENE_CONFIG_FILE
          value: "/app/runtime-config.toml"
```

## 🔄 Migration from Legacy Dockerfile

The legacy `Dockerfile` has been replaced with the new multi-platform system. To migrate:

1. **Choose platform**: Use `Dockerfile.x86_64` for most deployments
2. **Select profile**: Choose appropriate configuration profile
3. **Update commands**: Replace `docker build .` with `docker build -f Dockerfile.x86_64 --build-arg CONFIG_PROFILE=voice .`
4. **Test thoroughly**: Validate the new build meets your requirements

## 🛠️ Development

### Adding New Providers
New providers are automatically discovered via entry-points. No Docker file changes needed.

### Adding New Configuration Profiles
1. Create new `.toml` file in `configs/`
2. Test with build analyzer: `uv run python -m irene.tools.build_analyzer --config configs/newprofile.toml`
3. Build Docker image: `docker build -f Dockerfile.x86_64 --build-arg CONFIG_PROFILE=newprofile .`

### Platform Support
- **x86_64**: Native support, tested and optimized
- **ARMv7**: Cross-compilation, optimized for Raspberry Pi
- **ARM64**: Future enhancement (contributions welcome)
- **Windows containers**: Future enhancement

## 📖 Related Documentation

- [Build Analyzer Documentation](docs/BUILD_ANALYZER.md)
- [Configuration Guide](docs/configuration_guide.md)
- [Asset Management](docs/ASSET_MANAGEMENT.md)
- [Deployment Guide](docs/DEPLOYMENT.md) 