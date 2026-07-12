from src.query.entity_seeder import seed_entities
import pytest 

def test_seed_entities_resolves_named_company():
    anchors = seed_entities("Who supplies chips to Microsoft?")
    assert "MSFT" in anchors

def test_seed_entities_resolves_via_alias():
    anchors = seed_entities("What events hit Google recently?")
    assert "GOOGL" in anchors   # "Google" → GOOGL via alias table
