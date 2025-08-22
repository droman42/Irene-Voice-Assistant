#!/usr/bin/env python3
"""
JSON Schema Generator for Intent Donation System

Automatically generates JSON Schema files from Pydantic models to ensure
validation consistency between Python code and JSON donation files.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any

def generate_donation_schema() -> Dict[str, Any]:
    """Generate JSON Schema from HandlerDonation Pydantic model"""
    try:
        from irene.core.donations import HandlerDonation
        
        # Generate schema using Pydantic v2 method
        schema = HandlerDonation.model_json_schema()
        
        # Add additional metadata
        schema.update({
            "$id": "https://irene-voice-assistant.org/schemas/donation/v1.0.json",
            "title": "Irene Voice Assistant - Intent Handler Donation Schema",
            "description": "Schema for JSON donation files used by intent handlers in the Irene Voice Assistant system",
            "version": "1.0"
        })
        
        return schema
        
    except Exception as e:
        print(f"❌ Error generating schema: {e}")
        raise

def write_schema_file(schema: Dict[str, Any], output_path: Path) -> None:
    """Write schema to JSON file with pretty formatting"""
    try:
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write schema with pretty formatting
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Schema written to: {output_path}")
        
    except Exception as e:
        print(f"❌ Error writing schema file: {e}")
        raise

def validate_existing_json_files(schema: Dict[str, Any]) -> bool:
    """Validate all existing JSON donation files against the generated schema"""
    try:
        import jsonschema
        
        # Find all JSON donation files
        donations_dir = Path("assets/donations")
        json_files = list(donations_dir.glob("*.json"))
        
        if not json_files:
            print("⚠️  No JSON donation files found to validate")
            return True
        
        print(f"\n🧪 Validating {len(json_files)} JSON donation files...")
        
        all_valid = True
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validate against schema
                jsonschema.validate(instance=data, schema=schema)
                print(f"  ✅ {json_file.name}: Valid")
                
            except jsonschema.ValidationError as e:
                print(f"  ❌ {json_file.name}: Invalid - {e.message}")
                all_valid = False
            except Exception as e:
                print(f"  ❌ {json_file.name}: Error reading file - {e}")
                all_valid = False
        
        return all_valid
        
    except ImportError:
        print("⚠️  jsonschema library not available - skipping validation")
        return True
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        return False

def main():
    """Main schema generation function"""
    print("🔧 JSON Schema Generator for Intent Donation System")
    print("=" * 60)
    
    try:
        # Generate schema from Pydantic model
        print("📋 Generating schema from HandlerDonation model...")
        schema = generate_donation_schema()
        
        # Write v1.0 schema file
        schema_path = Path("assets/v1.0.json")
        print(f"💾 Writing schema to {schema_path}...")
        write_schema_file(schema, schema_path)
        
        # Show schema info
        print(f"\n📊 Schema Information:")
        print(f"  - Title: {schema.get('title', 'N/A')}")
        print(f"  - Version: {schema.get('version', 'N/A')}")
        print(f"  - Required properties: {len(schema.get('required', []))}")
        print(f"  - Total properties: {len(schema.get('properties', {}))}")
        
        # Validate existing JSON files
        print(f"\n🔍 Validating existing JSON donation files...")
        validation_success = validate_existing_json_files(schema)
        
        if validation_success:
            print(f"\n🎉 Schema generation completed successfully!")
            print(f"   - Schema file: {schema_path}")
            print(f"   - All existing JSON files are valid")
        else:
            print(f"\n⚠️  Schema generated but some JSON files have validation errors")
            print(f"   - Schema file: {schema_path}")
            print(f"   - Please fix the invalid JSON files")
            
        return 0 if validation_success else 1
        
    except Exception as e:
        print(f"\n❌ Schema generation failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
