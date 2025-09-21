# Web Assets

This directory contains web-related assets for the Irene Voice Assistant WebAPI runner, following the established donation/template pattern used throughout the project.

## Structure

```
assets/web/
├── templates/          # HTML templates
│   ├── index.html      # Main web interface
│   └── asyncapi.html   # AsyncAPI documentation page
├── static/             # Static assets (for future use)
│   ├── css/           # CSS stylesheets
│   └── js/            # JavaScript files
├── localization/       # Web UI translations (for future use)
└── README.md          # This file
```

## Templates

### Variable Substitution

Templates support Python format string syntax for variable substitution:

```html
<p>Modern async voice assistant API - v{version}</p>
```

The web asset loader automatically handles safe variable substitution without interfering with CSS braces.

### Available Templates

- **index.html**: Main web interface with command input form
- **asyncapi.html**: Interactive AsyncAPI WebSocket documentation

## Integration

The web assets are loaded by the `IntentAssetLoader` class in `/irene/core/intent_asset_loader.py` and used by the WebAPI runner in `/irene/runners/webapi_runner.py`.

### Loading Process

1. Asset loader scans `assets/web/templates/` for HTML files
2. Templates are cached in memory during startup
3. WebAPI endpoints retrieve templates with variable substitution
4. Fallback to inline HTML if templates are unavailable

### Benefits

- **Separation of Concerns**: HTML/CSS/JS separated from Python code
- **Easy Maintenance**: Non-developers can modify UI without touching Python
- **Version Control**: Cleaner diffs for UI vs business logic changes
- **Asset Management Consistency**: Follows project's established patterns
- **Development Workflow**: Frontend changes don't require Python restart

## Future Enhancements

- CSS/JS extraction to separate files in `static/` directory
- Multi-language support via `localization/` directory
- Template inheritance and includes
- Asset versioning and caching headers
