"""
Validates data/raw/wikidata_companies.json against the Company entity schema.

Company schema (ontology_schema.md):
   ticker          string PK   required
   name            string      required
   founded_date    date    required (ISO 8601 YYYY-MM-DD)

Flags:
  - missing required fields
  - founding_date 
"""