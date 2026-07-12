import pytest

from src.eval.scorer import (
    graph_entity_recall, graph_precision,
    vector_entity_recall, vector_chain_recall,
    score_question
)

class FakeSnippet:
    def __init__(self, text):
        self.text = text

# --- graph_entity_recall ---
def test_graph_entity_recall_all_found(): 
    results = [{"ticker": "NVDA", "name": "Nvidia"}, {"ticker": "AMD"}]
    must_include = ["NVDA", "AMD"]
    assert graph_entity_recall(results, must_include) == 1.0

def test_graph_entity_recall_none_found():
    results = [{"ticker":  "NVDA"}]
    must_include = ["NVDA", "AMD"]
    assert graph_entity_recall(results, must_include) == 0.5

def test_graph_entity_recall_empty_must_include_returns_1():
    results = [{"ticker": "NVDA", "name": "Nvidia"}, {"ticker": "AMD"}]
    must_include = []
    assert graph_entity_recall(results, must_include) == 1.0

def test_graph_entity_recall_ignores_none_values():
    results = [{"ticker": "NVDA", "note": None}]
    assert graph_entity_recall(results, ["NVDA"]) == 1.0
    assert graph_entity_recall(results, ["None"]) == 0.0

def test_graph_entity_recall_duplicate_rows_dont_inflate():
    results = [{"ticker": "NVDA"}, {"ticker": "NVDA"}, {"ticker": "NVDA"}]
    must_include = ["NVDA"]
    assert graph_entity_recall(results, must_include) == 1.0

# --- graph_precision ---
def test_graph_precision_all_rows_relevant():
    results = [{"ticker": "NVDA", "name": "Nvidia"}, {"ticker": "AMD", "name": "AMD"}]
    must_include = ["NVDA", "AMD"]
    assert graph_precision(results, must_include) == 1.0

def test_graph_precision_some_rows_irrelevant():
    results = [{"ticker": "NVDA"}, {"ticker": "TSM"}]
    must_include = ["NVDA", "AMD"]
    assert graph_precision(results, must_include) == 0.5

def test_graph_precision_empty_results_returns_1():
    results = []
    must_include = ["NVDA", "AMD"]
    assert graph_precision(results, must_include) == 1.0

# --- vector_entity_recall / vector_chain_recall ---
def test_vector_entity_recall_case_insensitive():
    snippets = [FakeSnippet("nvidia supplies GPUs to microsoft azure.")]
    # tickers resolve to their name aliases (NVDA -> "nvidia", MSFT -> "microsoft")
    assert vector_entity_recall(snippets, ["NVDA", "MSFT"]) == 1.0
    assert vector_entity_recall(snippets, ["Nvidia", "MICROSOFT"]) == 1.0

def test_vector_entity_recall_ticker_matches_name_alias():
    snippets = [FakeSnippet("Nvidia supplies chips to Microsoft Azure.")]
    # neither ticker string appears literally, but both resolve via aliases_for()
    assert vector_entity_recall(snippets, ["NVDA", "MSFT"]) == 1.0

def test_vector_entity_recall_unknown_entity_falls_back_to_literal():
    snippets = [FakeSnippet("Some unrelated snippet about widgets.")]
    # entity not in ALIAS_TABLE -> aliases_for() falls back to the literal string
    assert vector_entity_recall(snippets, ["ZZZZ"]) == 0.0

def test_vector_chain_recall_single_snippet_has_all():
    snippets = [
        FakeSnippet("Nvidia supplies H100 GPUs to Microsoft Azure and AWS."),
        FakeSnippet("Some unrelated snippet about Salesforce."),
    ]
    assert vector_chain_recall(snippets, ["Nvidia", "Microsoft"]) == 1.0

def test_vector_chain_recall_split_across_snippets_is_zero():
    snippets = [
        FakeSnippet("Nvidia makes H100 GPUs."),
        FakeSnippet("Microsoft Azure is a cloud provider."),
    ]
    assert vector_chain_recall(snippets, ["Nvidia", "Microsoft"]) == 0.0

def test_vector_chain_recall_resolves_ticker_aliases():
    snippets = [FakeSnippet("Nvidia supplies H100 GPUs to Microsoft Azure.")]
    # must_include uses tickers; snippet uses company names -- should still match
    assert vector_chain_recall(snippets, ["NVDA", "MSFT"]) == 1.0


# --- score_question ---
def test_score_question_computes_deltas_correctly():
    question = {
        "id": "q-test",
        "query_key": "supply_chain_map",
        "hops": 1,
        "must_include_entities": ["NVDA", "AMD"],
        "expected_min_rows": 1,
        "vector_can_compose": True,
    }

    graph_results = [{"ticker": "NVDA"}, {"ticker": "AMD"}]  # g_recall = 1.0
    vector_hits = [FakeSnippet("NVDA supplies chips.")]       # v_recall = 0.5 ("NVDA" present, "AMD" is not)

    scored = score_question(question, graph_results, vector_hits)

    assert scored["id"] == "q-test"
    assert scored["hops"] == 1
    assert scored["graph_rows"] == 2
    assert scored["graph_entity_recall"] == 1.0
    assert scored["vector_entity_recall"] == 0.5
    assert scored["recall_delta"] == pytest.approx(0.5)      # 1.0 - 0.5
    assert scored["chain_gap"] == pytest.approx(1.0)          # 1.0 - 0.0, no single snippet has both

def test_score_question_rows_ok_flag():
    question = {
        "id": "q-test",
        "query_key": "supply_chain_map",
        "hops": 1,
        "must_include_entities": [],
        "expected_min_rows": 3,
        "vector_can_compose": False,
    }
    graph_results = [{"ticker": "NVDA"}]  # only 1 row, expected >= 3

    scored = score_question(question, graph_results, [])

    assert scored["rows_ok"] is False
    assert scored["graph_rows"] == 1
    assert scored["expected_min_rows"] == 3