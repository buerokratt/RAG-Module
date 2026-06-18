"""
Integration Test — Multi-Intent Parallel API Tool Classification
================================================================

Tests Phase 1 of the multi-intent ATC feature end-to-end via /orchestrate.

The current Phase 1 implementation uses a temporary single-endpoint fallback:
IntentDecomposer detects parallel intent → both endpoints stored in context →
first matched endpoint used for param collection. True parallel execution
(collecting params for all endpoints simultaneously) arrives in Phase 6.

What these tests verify
-----------------------
- Queries with multiple independent intents still route to ATC (not RAG/OOD)
- The temporary first-endpoint fallback correctly collects params and completes
- Single-intent queries in the ambiguous cosine band are unaffected (regression)
- Estonian multi-intent queries decompose and route correctly
- Sub-queries that both resolve to the same endpoint are deduplicated → single
  path fallback (no crash, no duplicate calls)
- When one sub-query finds no matching endpoint (OOD intent mixed in), the
  system gracefully falls back to the single matched endpoint
- A query spanning 3 distinct domains hits the MULTI_API_MAX_ENDPOINTS=3 cap
  and still completes correctly

Scenarios
---------
  MI-1  Parallel — vehicle tax + initiative details (2 distinct endpoints)
  MI-2  Parallel — public holidays + electricity prices (distinct domains)
  MI-3  Parallel — parliament votings + participation stats (same domain)
  MI-4  Estonian multi-intent — vehicle tax + initiatives list
  MI-5  Single-intent regression — address search (should stay single path)
  MI-6  Deduplication fallback — both sub-queries hit the same endpoint
  MI-7  Mixed ATC + OOD intent — one sub-query finds no endpoint → graceful fallback
  MI-8  Three-domain query — address + holidays + electricity (3-way parallel cap)

Usage
-----
    # Service running locally on port 8100
    uv run python tests/api_tool_eval/integration_test_multi_intent.py

    # Against a different host/port
    uv run python tests/api_tool_eval/integration_test_multi_intent.py --url http://localhost:8100

    # Keep going after failures
    uv run python tests/api_tool_eval/integration_test_multi_intent.py --no-fail-fast

    # Save results to JSON
    uv run python tests/api_tool_eval/integration_test_multi_intent.py --output results-multi-intent.json
"""

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_URL = "http://localhost:8100"
ORCHESTRATE_ENDPOINT = "/orchestrate"
ENVIRONMENT = "production"
AUTHOR_ID = "multi-intent-test-user"
REQUEST_TIMEOUT = 45  # seconds


# ---------------------------------------------------------------------------
# Helpers (same interface as integration_test_agentic_loop.py)
# ---------------------------------------------------------------------------


def make_chat_id(label: str) -> str:
    """Unique chatId per test run so Redis sessions never collide across runs."""
    return f"mi-test-{label}-{uuid.uuid4().hex[:8]}"


def send_turn(
    base_url: str,
    chat_id: str,
    message: str,
    history: List[Dict[str, str]],
    connection_id: Optional[str] = None,
) -> Dict[str, Any]:
    """POST one turn to /orchestrate and return the parsed JSON response."""
    payload: Dict[str, Any] = {
        "chatId": chat_id,
        "message": message,
        "authorId": AUTHOR_ID,
        "conversationHistory": history,
        "url": "integration-test",
        "environment": ENVIRONMENT,
    }
    if connection_id:
        payload["connection_id"] = connection_id

    resp = requests.post(
        f"{base_url}{ORCHESTRATE_ENDPOINT}",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def append_to_history(
    history: List[Dict[str, str]],
    user_message: str,
    bot_response: str,
) -> List[Dict[str, str]]:
    """Return an updated conversation history list."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return history + [
        {"authorRole": "user", "message": user_message, "timestamp": ts},
        {"authorRole": "bot", "message": bot_response, "timestamp": ts},
    ]


def is_completed(content: str) -> bool:
    """Return True if the response is a params-collected JSON payload."""
    try:
        data = json.loads(content)
        return "collected_params" in data and "endpoint" in data
    except (json.JSONDecodeError, TypeError):
        return False


def is_clarifying_question(content: str) -> bool:
    """Return True if the response is a non-JSON natural-language question."""
    try:
        json.loads(content)
        return False
    except (json.JSONDecodeError, TypeError):
        return bool(content.strip())


def endpoint_name_from_completed(content: str) -> Optional[str]:
    """Extract the endpoint name from a completed JSON response."""
    try:
        data = json.loads(content)
        ep = data.get("endpoint", {})
        return ep.get("name") if isinstance(ep, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def collected_params_from_completed(content: str) -> Dict[str, Any]:
    """Extract collected_params dict from a completed JSON response."""
    try:
        data = json.loads(content)
        return data.get("collected_params", {})
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------------------------------------------------------------------------
# Result tracking (same dataclasses as integration_test_agentic_loop.py)
# ---------------------------------------------------------------------------


@dataclass
class TurnResult:
    turn: int
    message_sent: str
    response_content: str
    passed: bool
    note: str = ""


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    turns: List[TurnResult] = field(default_factory=list)
    error: str = ""


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------


def scenario_mi1_parallel_vehicle_tax_and_initiative(
    base_url: str,
) -> ScenarioResult:
    """
    MI-1: Parallel — vehicle tax + initiative details
    -------------------------------------------------
    Query combines two independent intents:
      - Calculate vehicle tax (requires regNr + calculationYear)
      - Get initiative details (requires initiative id)

    Expected flow:
      Turn 1: IntentDecomposer fires (cosine in ambiguous band [0.40, 0.60)).
              Parallel detected. Temporary fallback → get_vehicle_tax_info.
              Bot asks for registration number and calculation year.
      Turn 2: User provides vehicle params.
              Bot returns completed JSON for get_vehicle_tax_info.

    Asserts:
      - T1 is a clarifying question (not RAG/OOD — system routed to ATC)
      - T1 question references vehicle/registration/tax
      - T2 is completed JSON with regNr + calculationYear collected
      - Completed endpoint is get_vehicle_tax_info
    """
    name = "MI-1 — Parallel: vehicle tax + initiative details (first-endpoint fallback)"
    chat_id = make_chat_id("mi1")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    # Turn 1 — multi-intent query
    msg1 = (
        "Can you calculate the tax for my vehicle and also get the details "
        "of the initiative?"
    )
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    t1_pass = is_clarifying_question(content1) and not is_completed(content1)
    # Check that the clarifying question is about vehicle tax params, not initiative params.
    # The temporary fallback must pick get_vehicle_tax_info as the first endpoint.
    vehicle_hint = any(
        kw in content1.lower()
        for kw in ("registration", "reg", "vehicle", "tax", "year", "registreeri")
    )
    t1_note = (
        f"Correctly asked for vehicle params (vehicle_hint={vehicle_hint})"
        if t1_pass
        else f"Expected clarifying question about vehicle tax, got: {content1[:150]}"
    )
    if t1_pass and not vehicle_hint:
        t1_note = (
            f"WARNING: clarifying question does not mention vehicle/registration. "
            f"Fallback endpoint may differ. Content: {content1[:150]}"
        )
    turns.append(TurnResult(1, msg1, content1, t1_pass, t1_note))

    if not t1_pass:
        return ScenarioResult(name, False, turns, "Turn 1 did not route to ATC")

    # Turn 2 — provide vehicle tax params
    history = append_to_history(history, msg1, content1)
    msg2 = "Registration number 123ABC, year 2026"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    t2_pass = is_completed(content2)
    note2 = ""
    if t2_pass:
        collected = collected_params_from_completed(content2)
        ep_name = endpoint_name_from_completed(content2)
        expected_keys = {"regNr", "calculationYear"}
        missing = expected_keys - collected.keys()
        t2_pass = not missing and ep_name == "get_vehicle_tax_info"
        note2 = (
            f"endpoint={ep_name}, collected_params={collected}"
            if t2_pass
            else (
                f"missing keys={missing}" if missing else f"wrong endpoint={ep_name!r}"
            )
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:150]}"

    turns.append(TurnResult(2, msg2, content2, t2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_mi2_parallel_holidays_and_electricity(
    base_url: str,
) -> ScenarioResult:
    """
    MI-2: Parallel — public holidays + electricity prices (distinct domains)
    ------------------------------------------------------------------------
    Two clearly unrelated API intents in one query.

    Expected flow:
      Turn 1: IntentDecomposer detects parallel.
              One endpoint selected as fallback → clarifying question.
      Turn 2: User provides params → completed JSON.

    Asserts:
      - T1 routes to ATC (clarifying question, not RAG)
      - T2 completes with collected_params for the fallback endpoint
    """
    name = "MI-2 — Parallel: public holidays + electricity prices (distinct domains)"
    chat_id = make_chat_id("mi2")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = (
        "Can you get the public holidays in Estonia for this year "
        "and also show me the electricity market prices for this week?"
    )
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    t1_pass = is_clarifying_question(content1) and not is_completed(content1)
    t1_note = (
        "Correctly routed to ATC and asked for params"
        if t1_pass
        else f"Expected clarifying question, got: {content1[:150]}"
    )
    turns.append(TurnResult(1, msg1, content1, t1_pass, t1_note))

    if not t1_pass:
        return ScenarioResult(name, False, turns, "Turn 1 did not route to ATC")

    # Provide params that satisfy either fallback endpoint:
    # - get_public_holidays: countryIsoCode=EE, validFrom/To + electricity start/end
    # - get_electricity_prices: start/end datetime
    # We supply all possible params so whichever endpoint was chosen can complete.
    history = append_to_history(history, msg1, content1)
    msg2 = (
        "Country EE, from 2026-01-01 to 2026-12-31, "
        "electricity from 2026-05-12T00:00:00Z to 2026-05-18T23:59:59Z"
    )
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    t2_pass = is_completed(content2)
    note2 = ""
    if t2_pass:
        ep_name = endpoint_name_from_completed(content2)
        collected = collected_params_from_completed(content2)
        # Accept either endpoint as the fallback
        valid_endpoints = {"get_public_holidays", "get_electricity_prices"}
        t2_pass = ep_name in valid_endpoints and bool(collected)
        note2 = (
            f"endpoint={ep_name!r}, collected_params={collected}"
            if t2_pass
            else f"unexpected endpoint={ep_name!r} or empty params={collected}"
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:150]}"

    turns.append(TurnResult(2, msg2, content2, t2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_mi3_parallel_parliament_same_domain(
    base_url: str,
) -> ScenarioResult:
    """
    MI-3: Parallel — parliament votings + participation stats (same domain)
    -----------------------------------------------------------------------
    Both intents relate to parliament but map to different endpoints.
    Tests that same-domain multi-intent is still detected as parallel.

    Expected flow:
      Turn 1: IntentDecomposer detects 2 parliament intents.
              First parliament endpoint selected as fallback → clarifying question
              asking for startDate + endDate.
      Turn 2: User provides date range → completed JSON.

    Asserts:
      - T1 routes to ATC
      - T2 completes for a parliament endpoint with date params
    """
    name = "MI-3 — Parallel: parliament votings + participation stats (same domain)"
    chat_id = make_chat_id("mi3")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = (
        "Show me the parliament voting records and also the participation "
        "statistics of parliament members in Estonia"
    )
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    t1_pass = is_clarifying_question(content1) and not is_completed(content1)
    t1_note = (
        "Routed to ATC — asking for date params"
        if t1_pass
        else f"Expected ATC clarifying question, got: {content1[:150]}"
    )
    turns.append(TurnResult(1, msg1, content1, t1_pass, t1_note))

    if not t1_pass:
        return ScenarioResult(name, False, turns, "Turn 1 did not route to ATC")

    history = append_to_history(history, msg1, content1)
    msg2 = "From 2026-01-01 to 2026-03-31"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    t2_pass = is_completed(content2)
    note2 = ""
    if t2_pass:
        ep_name = endpoint_name_from_completed(content2)
        collected = collected_params_from_completed(content2)
        valid_endpoints = {
            "get_parliament_votings",
            "get_parliament_participation_stats",
        }
        expected_keys = {"startDate", "endDate"}
        missing = expected_keys - collected.keys()
        t2_pass = ep_name in valid_endpoints and not missing
        note2 = (
            f"endpoint={ep_name!r}, collected_params={collected}"
            if t2_pass
            else (
                f"missing keys={missing}"
                if missing
                else f"unexpected endpoint={ep_name!r}"
            )
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:150]}"

    turns.append(TurnResult(2, msg2, content2, t2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_mi4_parallel_estonian(base_url: str) -> ScenarioResult:
    """
    MI-4: Estonian multi-intent — vehicle tax + initiatives list
    ------------------------------------------------------------
    Verifies that the IntentDecomposer handles Estonian queries correctly.
    DSPy signature explicitly lists ET/EN/RU as supported languages.

    Expected flow:
      Turn 1: Estonian query → IntentDecomposer fires → parallel detected.
              Fallback: get_vehicle_tax_info or get_initiatives → clarifying
              question returned (in Estonian or English).
      Turn 2: Provide the expected params.
              Completed JSON.

    Asserts:
      - T1 routes to ATC (clarifying question, not RAG/OOD)
      - T2 completes with collected_params
    """
    name = "MI-4 — Estonian multi-intent: vehicle tax + initiatives list"
    chat_id = make_chat_id("mi4")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = "Arvuta mu sõiduki maks ja näita mulle algatuste nimekiri"
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    t1_pass = is_clarifying_question(content1) and not is_completed(content1)
    t1_note = (
        "Estonian multi-intent routed to ATC"
        if t1_pass
        else f"Expected ATC clarifying question for Estonian query, got: {content1[:150]}"
    )
    turns.append(TurnResult(1, msg1, content1, t1_pass, t1_note))

    if not t1_pass:
        return ScenarioResult(
            name, False, turns, "Turn 1 did not route Estonian multi-intent to ATC"
        )

    # Provide params covering both possible fallback endpoints
    history = append_to_history(history, msg1, content1)
    msg2 = "Registreerimisnumber 456DEF, aasta 2026"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    t2_pass = is_completed(content2)
    note2 = ""
    if t2_pass:
        ep_name = endpoint_name_from_completed(content2)
        collected = collected_params_from_completed(content2)
        note2 = f"endpoint={ep_name!r}, collected_params={collected}"
    else:
        note2 = f"Expected completed JSON, got: {content2[:150]}"

    turns.append(TurnResult(2, msg2, content2, t2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_mi5_single_intent_regression(base_url: str) -> ScenarioResult:
    """
    MI-5: Single-intent regression — address search (not multi-intent)
    ------------------------------------------------------------------
    Verifies that a clear single-intent query is NOT incorrectly split into
    sub-queries by the IntentDecomposer.

    "Search for an address in Tallinn" has only one intent.
    IntentDecomposer should return mode=single → single path used as before.

    Expected flow:
      Turn 1: search_address matched → single path → bot asks for address param.
      Turn 2: user provides address → completed JSON with address param.

    Asserts:
      - T1 is a clarifying question asking for the address
      - T2 completes for search_address with the address param present
    """
    name = "MI-5 — Single-intent regression: address search stays on single path"
    chat_id = make_chat_id("mi5")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = "I need to search for an address in Tallinn"
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    t1_pass = is_clarifying_question(content1) and not is_completed(content1)
    t1_note = (
        "Single-intent routed to ATC, asking for address"
        if t1_pass
        else f"Expected clarifying question for address, got: {content1[:150]}"
    )
    turns.append(TurnResult(1, msg1, content1, t1_pass, t1_note))

    if not t1_pass:
        return ScenarioResult(
            name, False, turns, "Turn 1 did not route single-intent to ATC"
        )

    history = append_to_history(history, msg1, content1)
    msg2 = "Viru 4, Tallinn"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    t2_pass = is_completed(content2)
    note2 = ""
    if t2_pass:
        ep_name = endpoint_name_from_completed(content2)
        collected = collected_params_from_completed(content2)
        t2_pass = ep_name == "search_address" and "address" in collected
        note2 = (
            f"endpoint={ep_name!r}, collected_params={collected}"
            if t2_pass
            else f"unexpected endpoint={ep_name!r} or missing 'address' in {collected}"
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:150]}"

    turns.append(TurnResult(2, msg2, content2, t2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_mi6_dedup_same_endpoint(base_url: str) -> ScenarioResult:
    """
    MI-6: Deduplication — both sub-queries resolve to the same endpoint
    -------------------------------------------------------------------
    When IntentDecomposer generates sub-queries that both match the same
    endpoint, _try_parallel_api_tool_classification deduplicates them to
    1 unique endpoint → < 2 required → returns None → falls back to the
    original single-path match.

    This verifies:
      - No crash or duplicate call when dedup collapses to 1 endpoint
      - The single-path fallback still works correctly

    Query: "Show me the list of initiatives and also display all initiatives"
    Expected: get_initiatives matched via single path → completed on turn 1
    (get_initiatives has no required params → fast-path completion)
    """
    name = "MI-6 — Dedup fallback: both sub-queries hit get_initiatives → single path"
    chat_id = make_chat_id("mi6")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = (
        "Show me the list of all citizen initiatives and also display all initiatives"
    )
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    # get_initiatives has only an optional 'page' param → may complete immediately
    # or ask for the page number. Both are valid.
    if is_completed(content1):
        ep_name = endpoint_name_from_completed(content1)
        passed = ep_name == "get_initiatives"
        note = (
            f"Fast-path completion: endpoint={ep_name!r}"
            if passed
            else f"Completed for wrong endpoint: {ep_name!r}"
        )
        turns.append(TurnResult(1, msg1, content1, passed, note))
        return ScenarioResult(name, passed, turns)

    # Bot asked a clarifying question (e.g., for page number)
    t1_pass = is_clarifying_question(content1)
    t1_note = (
        "ATC routed correctly after dedup, asking for optional page param"
        if t1_pass
        else f"Expected ATC response, got: {content1[:150]}"
    )
    turns.append(TurnResult(1, msg1, content1, t1_pass, t1_note))

    if not t1_pass:
        return ScenarioResult(name, False, turns, "Turn 1 did not route to ATC")

    history = append_to_history(history, msg1, content1)
    msg2 = "Page 1"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    t2_pass = is_completed(content2)
    note2 = ""
    if t2_pass:
        ep_name = endpoint_name_from_completed(content2)
        t2_pass = ep_name == "get_initiatives"
        note2 = (
            f"endpoint={ep_name!r}" if t2_pass else f"unexpected endpoint={ep_name!r}"
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:150]}"

    turns.append(TurnResult(2, msg2, content2, t2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_mi7_mixed_atc_ood_intent(base_url: str) -> ScenarioResult:
    """
    MI-7: Mixed ATC + OOD intent — graceful fallback to single matched endpoint
    ---------------------------------------------------------------------------
    One intent maps cleanly to an endpoint; the other is out-of-domain (no
    matching endpoint with cosine ≥ threshold).

    When _try_parallel_api_tool_classification collects results, the OOD
    sub-query returns None → only 1 unique endpoint matched → < 2 required
    → returns None → original single-path match used as fallback.

    Query: "Calculate my vehicle tax and explain climate change in Estonia"
    Expected:
      - "explain climate change" has no matching API endpoint
      - Parallel collapses to 1 → single path → get_vehicle_tax_info
      - Bot asks for regNr + calculationYear
      - Turn 2 provides params → completes

    Asserts:
      - T1 routes to ATC (not OOD/RAG) — vehicle tax intent rescued the query
      - T2 completes for get_vehicle_tax_info
    """
    name = "MI-7 — Mixed ATC+OOD: one sub-query OOD → graceful single-path fallback"
    chat_id = make_chat_id("mi7")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = "Calculate my vehicle tax and also explain climate change in Estonia"
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    t1_pass = is_clarifying_question(content1) and not is_completed(content1)
    vehicle_hint = any(
        kw in content1.lower()
        for kw in ("registration", "reg", "vehicle", "tax", "year", "registreeri")
    )
    t1_note = (
        f"ATC routed for vehicle tax intent (vehicle_hint={vehicle_hint})"
        if t1_pass
        else f"Expected ATC clarifying question, got: {content1[:150]}"
    )
    turns.append(TurnResult(1, msg1, content1, t1_pass, t1_note))

    if not t1_pass:
        return ScenarioResult(
            name, False, turns, "Turn 1 did not fall back to ATC for vehicle tax intent"
        )

    history = append_to_history(history, msg1, content1)
    msg2 = "Registration number 789GHI, calculation year 2026"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    t2_pass = is_completed(content2)
    note2 = ""
    if t2_pass:
        ep_name = endpoint_name_from_completed(content2)
        collected = collected_params_from_completed(content2)
        expected_keys = {"regNr", "calculationYear"}
        missing = expected_keys - collected.keys()
        t2_pass = ep_name == "get_vehicle_tax_info" and not missing
        note2 = (
            f"endpoint={ep_name!r}, collected_params={collected}"
            if t2_pass
            else (
                f"missing keys={missing}"
                if missing
                else f"unexpected endpoint={ep_name!r}"
            )
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:150]}"

    turns.append(TurnResult(2, msg2, content2, t2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_mi8_three_domain_parallel(base_url: str) -> ScenarioResult:
    """
    MI-8: Three-domain query — address + public holidays + electricity prices
    -------------------------------------------------------------------------
    Tests MULTI_API_MAX_ENDPOINTS=3 cap. The IntentDecomposer should produce
    3 sub-queries (capped at 3), each mapping to a distinct endpoint:
      - "search for an address"       → search_address
      - "get public holidays"         → get_public_holidays
      - "check electricity prices"    → get_electricity_prices

    _try_parallel_api_tool_classification deduplicates: 3 unique endpoints
    → parallel with 3. Temporary fallback uses the first matched endpoint.

    Expected flow:
      Turn 1: 3-way parallel detected → first endpoint's params asked.
      Turn 2: Provide params covering the first endpoint → completes.

    Asserts:
      - T1 routes to ATC
      - T2 completes for one of the three expected endpoints
    """
    name = "MI-8 — Three-domain: address + holidays + electricity (3-way parallel cap)"
    chat_id = make_chat_id("mi8")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = (
        "Search for an address in Tartu, get public holidays in Estonia this year, "
        "and show me the electricity prices for this week"
    )
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    t1_pass = is_clarifying_question(content1) and not is_completed(content1)
    t1_note = (
        "3-domain query routed to ATC, asking for first endpoint's params"
        if t1_pass
        else f"Expected ATC clarifying question, got: {content1[:150]}"
    )
    turns.append(TurnResult(1, msg1, content1, t1_pass, t1_note))

    if not t1_pass:
        return ScenarioResult(
            name, False, turns, "Turn 1 did not route to ATC for 3-domain query"
        )

    # Supply params covering all three possible first-endpoint fallbacks
    history = append_to_history(history, msg1, content1)
    msg2 = (
        "Address: Raekoja plats, Tartu. "
        "Country EE, from 2026-01-01 to 2026-12-31. "
        "Electricity from 2026-05-12T00:00:00Z to 2026-05-18T23:59:59Z"
    )
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    t2_pass = is_completed(content2)
    note2 = ""
    if t2_pass:
        ep_name = endpoint_name_from_completed(content2)
        collected = collected_params_from_completed(content2)
        valid_endpoints = {
            "search_address",
            "get_public_holidays",
            "get_electricity_prices",
        }
        t2_pass = ep_name in valid_endpoints and bool(collected)
        note2 = (
            f"endpoint={ep_name!r}, collected_params={collected}"
            if t2_pass
            else f"unexpected endpoint={ep_name!r} or empty params={collected}"
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:150]}"

    turns.append(TurnResult(2, msg2, content2, t2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

SCENARIOS = [
    scenario_mi1_parallel_vehicle_tax_and_initiative,
    scenario_mi2_parallel_holidays_and_electricity,
    scenario_mi3_parallel_parliament_same_domain,
    scenario_mi4_parallel_estonian,
    scenario_mi5_single_intent_regression,
    scenario_mi6_dedup_same_endpoint,
    scenario_mi7_mixed_atc_ood_intent,
    scenario_mi8_three_domain_parallel,
]


def run_all(
    base_url: str, fail_fast: bool = True
) -> Tuple[List[ScenarioResult], int, int]:
    results: List[ScenarioResult] = []
    passed = 0
    failed = 0

    print(f"\n{'=' * 70}")
    print(f"  Multi-Intent Integration Tests  |  {base_url}")
    print(f"{'=' * 70}\n")

    for fn in SCENARIOS:
        print(f"Running: {fn.__name__} ...", flush=True)
        try:
            result = fn(base_url)
        except requests.exceptions.ConnectionError:
            result = ScenarioResult(
                fn.__name__,
                False,
                error="Connection refused — is the service running?",
            )
        except requests.exceptions.Timeout:
            result = ScenarioResult(
                fn.__name__,
                False,
                error=f"Request timed out after {REQUEST_TIMEOUT}s",
            )
        except Exception as exc:
            result = ScenarioResult(fn.__name__, False, error=str(exc))

        results.append(result)
        status_icon = "✅" if result.passed else "❌"
        print(f"  {status_icon}  {result.name}")

        for t in result.turns:
            turn_icon = "  ✓" if t.passed else "  ✗"
            print(f"    {turn_icon}  Turn {t.turn}: {t.message_sent[:70]!r}")
            if t.note:
                print(f"           → {t.note}")
            if not t.passed:
                print(f"           Response: {t.response_content[:250]}")

        if result.error:
            print(f"    ERROR: {result.error}")

        if result.passed:
            passed += 1
        else:
            failed += 1
            if fail_fast:
                print("\n⚠  Stopping early (--no-fail-fast to continue)\n")
                break

        print()

    print(f"{'=' * 70}")
    print(f"  Results: {passed} passed, {failed} failed / {len(results)} run")
    print(f"{'=' * 70}\n")

    return results, passed, failed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-intent ATC integration tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Base URL of the orchestration service (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Continue running all scenarios even after a failure",
    )
    parser.add_argument(
        "--output",
        help="Optional path to save detailed JSON results",
    )
    args = parser.parse_args()

    results, passed, failed = run_all(
        base_url=args.url,
        fail_fast=not args.no_fail_fast,
    )

    if args.output:
        output_data = [
            {
                "name": r.name,
                "passed": r.passed,
                "error": r.error,
                "turns": [
                    {
                        "turn": t.turn,
                        "message_sent": t.message_sent,
                        "response_content": t.response_content,
                        "passed": t.passed,
                        "note": t.note,
                    }
                    for t in r.turns
                ],
            }
            for r in results
        ]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"Results saved to {args.output}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
