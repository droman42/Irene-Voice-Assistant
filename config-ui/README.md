# Irene Donation Editor

A small React (Vite) app that edits Irene donation JSON files without exposing JSON syntax. It validates live against the provided JSON Schema.

## Quick start

```bash
# 1) Install dependencies
npm install

# 2) Start the dev server
npm run dev

# 3) Open the printed local URL

# 4) (Optional) Load the full Irene schema:
#    - In the app, go to "Schema settings"
#    - Import the file: schemas/donation/v1.0.json from your Irene project
#    - Or use the included irene-schema.json for testing
```

## Build

```bash
npm run build
npm run preview
```

## Features
- Form-based UI for all schema fields (no raw JSON editing required)
- Live validation with AJV (errors shown inline)
- Import donation JSON (your data) and export back out
- Dynamic schema loading: import your own schema JSON or use the built-in default
- No hardcoded schema dependencies - fully configurable

## Tech
- Vite + React
- Tailwind for styling
- AJV + ajv-formats for schema validation
- lucide-react for icons

All logic runs locally in the browser.
