"""
Integration Test — Agentic Loop Multi-Turn Parameter Collection
==============================================================

Tests the full end-to-end agentic loop via the /orchestrate endpoint.

Scenarios covered:
  1. Single-turn complete    — all params in first message (vehicle tax)
  2. Multi-turn (EN)         — no params upfront, answered across 2 turns (public holidays)
  3. Multi-turn (ET)         — same flow in Estonian (school holidays)
  4. No-params fast-path     — endpoint with no required params (parliament votings)
  5. Address search          — single required param, 2-turn
  6. Electricity prices      — 2 required datetime params, 2-turn
  7. Session isolation       — after completing one flow, a NEW query for the same chatId must NOT reuse old session values
  8. AWAITING_CONTINUATION_DECISION — hits continuation threshold, user says "yes", loop resumes
  9. MAX_TURNS_REACHED → loop falls back to RAG/OOD, does NOT return collected_params JSON

Usage:
    # Service running locally on port 8100
    uv run python tests/api_tool_eval/integration_test_agentic_loop.py

    # Against a different host/port
    uv run python tests/api_tool_eval/integration_test_agentic_loop.py --url http://localhost:8100

    # Keep going even after failures
    uv run python tests/api_tool_eval/integration_test_agentic_loop.py --no-fail-fast

    # Save results to JSON
    uv run python tests/api_tool_eval/integration_test_agentic_loop.py --output results-integration.json
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
AUTHOR_ID = "integration-test-user"
REQUEST_TIMEOUT = 30  # seconds per turn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_chat_id(label: str) -> str:
    """Unique chatId per test run so Redis sessions never collide across runs."""
    return f"integration-test-{label}-{uuid.uuid4().hex[:8]}"


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
    """Return True if the response looks like a clarifying question (not JSON)."""
    try:
        json.loads(content)
        return False  # valid JSON → completed or error
    except (json.JSONDecodeError, TypeError):
        return bool(content.strip())


# ---------------------------------------------------------------------------
# Result tracking
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


def scenario_1_single_turn_vehicle_tax(base_url: str) -> ScenarioResult:
    """
    Scenario 1: Single-turn complete
    --------------------------------
    User provides the required param (registrationNumber) in the first message.
    Expected: response is immediately a completed JSON with collected_params.
    """
    name = "1 — Single-turn complete (vehicle tax with reg number)"
    chat_id = make_chat_id("s1")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    message = "Calculate vehicle tax for registration number 123ABC"
    resp = send_turn(base_url, chat_id, message, history)
    content = resp.get("content", "")

    passed = is_completed(content)
    if passed:
        data = json.loads(content)
        collected = data.get("collected_params", {})
        passed = collected.get("registrationNumber") == "123ABC"
        note = f"collected_params={collected}"
    else:
        note = f"Expected completed JSON, got: {content[:120]}"

    turns.append(TurnResult(1, message, content, passed, note))
    return ScenarioResult(name, passed, turns)


def scenario_2_multiturn_public_holidays_en(base_url: str) -> ScenarioResult:
    """
    Scenario 2: Multi-turn — public holidays (English)
    ---------------------------------------------------
    Turn 1: vague query — bot asks for country + date range
    Turn 2: user provides all params — bot returns completed JSON
    """
    name = "2 — Multi-turn EN (public holidays, params across 2 turns)"
    chat_id = make_chat_id("s2")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    # Turn 1
    msg1 = "What are the public holidays in Estonia this year?"
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    turn1_pass = is_clarifying_question(content1)
    turns.append(
        TurnResult(
            1,
            msg1,
            content1,
            turn1_pass,
            "Expected clarifying question" if not turn1_pass else "",
        )
    )

    if not turn1_pass:
        return ScenarioResult(
            name, False, turns, "Turn 1 did not return a clarifying question"
        )

    # Turn 2
    history = append_to_history(history, msg1, content1)
    msg2 = "EE, from 2025-01-01 to 2025-12-31"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    turn2_pass = is_completed(content2)
    note2 = ""
    if turn2_pass:
        data = json.loads(content2)
        collected = data.get("collected_params", {})
        expected_keys = {"countryIsoCode", "validFrom", "validTo"}
        missing = expected_keys - collected.keys()
        turn2_pass = not missing
        note2 = (
            f"collected_params={collected}"
            if not missing
            else f"missing keys: {missing}"
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:120]}"

    turns.append(TurnResult(2, msg2, content2, turn2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_3_multiturn_school_holidays_et(base_url: str) -> ScenarioResult:
    """
    Scenario 3: Multi-turn — school holidays (Estonian)
    ----------------------------------------------------
    Turn 1: Estonian query, no params
    Turn 2: provides date range in Estonian
    """
    name = "3 — Multi-turn ET (school holidays in Estonian)"
    chat_id = make_chat_id("s3")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = "Millal on Eesti koolide koolivaheajad 2025. aastal?"
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    turn1_pass = is_clarifying_question(content1)
    turns.append(
        TurnResult(
            1,
            msg1,
            content1,
            turn1_pass,
            "Expected clarifying question" if not turn1_pass else "",
        )
    )

    if not turn1_pass:
        return ScenarioResult(
            name, False, turns, "Turn 1 did not return a clarifying question"
        )

    history = append_to_history(history, msg1, content1)
    msg2 = "EE, alguskuupäev 2025-01-01, lõppkuupäev 2025-12-31"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    turn2_pass = is_completed(content2)
    note2 = ""
    if turn2_pass:
        data = json.loads(content2)
        collected = data.get("collected_params", {})
        expected_keys = {"countryIsoCode", "validFrom", "validTo"}
        missing = expected_keys - collected.keys()
        turn2_pass = not missing
        note2 = (
            f"collected_params={collected}"
            if not missing
            else f"missing keys: {missing}"
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:120]}"

    turns.append(TurnResult(2, msg2, content2, turn2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_4_no_params_fast_path(base_url: str) -> ScenarioResult:
    """
    Scenario 4: No-params fast-path (parliament votings)
    -----------------------------------------------------
    Endpoint has no required params → should return completed JSON on turn 1
    without asking any clarifying questions.
    """
    name = "4 — No-params fast-path (parliament votings)"
    chat_id = make_chat_id("s4")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    message = "Show me the latest parliament voting records in Estonia"
    resp = send_turn(base_url, chat_id, message, history)
    content = resp.get("content", "")

    passed = is_completed(content)
    note = ""
    if passed:
        data = json.loads(content)
        note = f"endpoint={data.get('endpoint')}, collected_params={data.get('collected_params')}"
    else:
        note = f"Expected fast-path completed JSON, got: {content[:120]}"

    turns.append(TurnResult(1, message, content, passed, note))
    return ScenarioResult(name, passed, turns)


def scenario_5_address_search(base_url: str) -> ScenarioResult:
    """
    Scenario 5: Address search — single required param
    ---------------------------------------------------
    Turn 1: vague — "search for an address" → bot asks which address
    Turn 2: user provides address → completed
    """
    name = "5 — Multi-turn (address search, 2 turns)"
    chat_id = make_chat_id("s5")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = "Search for an address in Estonia"
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    turn1_pass = is_clarifying_question(content1)
    turns.append(
        TurnResult(
            1,
            msg1,
            content1,
            turn1_pass,
            "Expected clarifying question" if not turn1_pass else "",
        )
    )

    if not turn1_pass:
        return ScenarioResult(
            name, False, turns, "Turn 1 did not return a clarifying question"
        )

    history = append_to_history(history, msg1, content1)
    msg2 = "Viru 4, Tallinn"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    turn2_pass = is_completed(content2)
    note2 = ""
    if turn2_pass:
        data = json.loads(content2)
        collected = data.get("collected_params", {})
        turn2_pass = "address" in collected
        note2 = f"collected_params={collected}"
    else:
        note2 = f"Expected completed JSON, got: {content2[:120]}"

    turns.append(TurnResult(2, msg2, content2, turn2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_6_electricity_prices(base_url: str) -> ScenarioResult:
    """
    Scenario 6: Electricity prices — 2 required datetime params
    ------------------------------------------------------------
    Turn 1: "What are the electricity prices?" → bot asks for start/end
    Turn 2: user provides both datetimes → completed
    """
    name = "6 — Multi-turn (electricity prices, datetime params)"
    chat_id = make_chat_id("s6")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    msg1 = "What are the electricity market prices in Estonia?"
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    turn1_pass = is_clarifying_question(content1)
    turns.append(
        TurnResult(
            1,
            msg1,
            content1,
            turn1_pass,
            "Expected clarifying question" if not turn1_pass else "",
        )
    )

    if not turn1_pass:
        return ScenarioResult(
            name, False, turns, "Turn 1 did not return a clarifying question"
        )

    history = append_to_history(history, msg1, content1)
    msg2 = "From 2025-01-01T00:00:00 to 2025-01-07T23:59:59"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    turn2_pass = is_completed(content2)
    note2 = ""
    if turn2_pass:
        data = json.loads(content2)
        collected = data.get("collected_params", {})
        expected_keys = {"start", "end"}
        missing = expected_keys - collected.keys()
        turn2_pass = not missing
        note2 = (
            f"collected_params={collected}"
            if not missing
            else f"missing keys: {missing}"
        )
    else:
        note2 = f"Expected completed JSON, got: {content2[:120]}"

    turns.append(TurnResult(2, msg2, content2, turn2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_7_session_isolation(base_url: str) -> ScenarioResult:
    """
    Scenario 7: Session isolation after completion
    -----------------------------------------------
    Uses the SAME chatId across two separate API tool flows to verify that
    completing one flow does not leak params into the next query.

    Flow:
      Turn 1: "Calculate vehicle tax for 777XYZ"  → COMPLETED (session deleted)
      Turn 2: "What are public holidays in Estonia?" → NEW session, asks for params
              (MUST NOT immediately complete with registrationNumber=777XYZ)
    """
    name = "7 — Session isolation (no param leak across flows)"
    chat_id = make_chat_id("s7")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    # First flow — complete it
    msg1 = "Calculate vehicle tax for registration number 777XYZ"
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")

    flow1_ok = is_completed(content1)
    turns.append(
        TurnResult(
            1,
            msg1,
            content1,
            flow1_ok,
            "First flow should complete immediately" if not flow1_ok else "",
        )
    )

    if not flow1_ok:
        return ScenarioResult(
            name, False, turns, "First flow did not complete — cannot test isolation"
        )

    # Second flow on the same chatId — must start fresh
    history = append_to_history(history, msg1, content1)
    msg2 = "What are the public holidays in Estonia this year?"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")

    # It must NOT immediately return collected_params (that would mean param leak)
    turn2_pass = is_clarifying_question(content2)
    note2 = (
        "Correctly started new session and asked for params"
        if turn2_pass
        else f"BAD: returned completed JSON immediately (param leak?): {content2[:150]}"
    )
    turns.append(TurnResult(2, msg2, content2, turn2_pass, note2))
    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def scenario_8_awaiting_continuation(base_url: str) -> ScenarioResult:
    """
    Scenario 8: AWAITING_CONTINUATION_DECISION flow
    ------------------------------------------------
    The loop hits CONTINUATION_TURN (3) without all params collected.
    The bot must ask a yes/no "keep going?" question.

    We then answer "yes" to continue — the bot should resume asking for the
    remaining params (not immediately complete and not fall back to RAG).

    Uses get_public_holidays which has 3 required params (countryIsoCode,
    validFrom, validTo). We deliberately give unhelpful answers on turns 2 and 3
    to reach the continuation threshold.

    Turn flow (CONTINUATION_TURN=3, max_turns=5):
      run_turn #1 (turn 0→1): opening question
      run_turn #2 (turn 1→2): unhelpful reply → another clarifying question
      run_turn #3 (turn 2→3): still unhelpful → AWAITING_CONTINUATION_DECISION
      run_turn #4 (turn 3→4): user says "yes" → loop resumes, asks again
    """
    name = "8 — AWAITING_CONTINUATION_DECISION (yes → loop resumes)"
    chat_id = make_chat_id("s8")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    # Turn 1 — trigger the flow with no params
    msg1 = "I want to see public holidays"
    resp1 = send_turn(base_url, chat_id, msg1, history)
    content1 = resp1.get("content", "")
    t1_pass = is_clarifying_question(content1)
    turns.append(
        TurnResult(
            1,
            msg1,
            content1,
            t1_pass,
            "Expected opening clarifying question" if not t1_pass else "",
        )
    )
    if not t1_pass:
        return ScenarioResult(
            name, False, turns, "Turn 1 did not return a clarifying question"
        )

    # Turn 2 — deliberately unhelpful
    history = append_to_history(history, msg1, content1)
    msg2 = "I'm not sure"
    resp2 = send_turn(base_url, chat_id, msg2, history)
    content2 = resp2.get("content", "")
    t2_pass = is_clarifying_question(content2) and not is_completed(content2)
    turns.append(
        TurnResult(
            2,
            msg2,
            content2,
            t2_pass,
            "Expected follow-up clarifying question" if not t2_pass else "",
        )
    )
    if not t2_pass:
        return ScenarioResult(
            name, False, turns, "Turn 2 did not return a clarifying question"
        )

    # Turn 3 — still unhelpful → should trigger continuation check
    history = append_to_history(history, msg2, content2)
    msg3 = "I don't know"
    resp3 = send_turn(base_url, chat_id, msg3, history)
    content3 = resp3.get("content", "")
    # Continuation question contains "yes" or "no" and is not a completed JSON
    is_continuation_prompt = not is_completed(content3) and (
        "yes" in content3.lower()
        or "no" in content3.lower()
        or "jah" in content3.lower()
    )
    t3_pass = is_continuation_prompt
    turns.append(
        TurnResult(
            3,
            msg3,
            content3,
            t3_pass,
            "Expected yes/no continuation question"
            if not t3_pass
            else "Got continuation prompt",
        )
    )
    if not t3_pass:
        return ScenarioResult(
            name, False, turns, "Turn 3 did not trigger continuation check"
        )

    # Turn 4 — user says "yes" → loop should resume with another clarifying question
    history = append_to_history(history, msg3, content3)
    msg4 = "yes"
    resp4 = send_turn(base_url, chat_id, msg4, history)
    content4 = resp4.get("content", "")
    # After "yes" the bot must ask for params again, not complete
    t4_pass = is_clarifying_question(content4) and not is_completed(content4)
    note4 = (
        "Loop resumed correctly after 'yes'"
        if t4_pass
        else f"Expected resumed clarifying question, got: {content4[:150]}"
    )
    turns.append(TurnResult(4, msg4, content4, t4_pass, note4))

    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


def scenario_9_max_turns_reached(base_url: str) -> ScenarioResult:
    """
    Scenario 9: MAX_TURNS_REACHED — loop falls back to RAG/OOD
    -----------------------------------------------------------
    Keep giving unhelpful answers through the continuation "yes" and beyond
    until max_turns (5) is exhausted. The final response must NOT be a
    params-collected JSON — it should be a natural-language RAG/OOD answer.

    Turn flow (CONTINUATION_TURN=3, max_turns=5):
      run_turn #1 (turn 0→1): opening question
      run_turn #2 (turn 1→2): unhelpful → clarifying question
      run_turn #3 (turn 2→3): unhelpful → AWAITING_CONTINUATION_DECISION
      run_turn #4 (turn 3→4): "yes" → loop resumes, asks again
      run_turn #5 (turn 4→5): unhelpful → MAX_TURNS_REACHED → fallback
    """
    name = "9 — MAX_TURNS_REACHED (loop exhausted, falls back to RAG)"
    chat_id = make_chat_id("s9")
    history: List[Dict[str, str]] = []
    turns: List[TurnResult] = []

    unhelpful_replies = [
        "I want to see public holidays",  # turn 1 — trigger
        "hmm not sure",  # turn 2 — still missing
        "I have no idea",  # turn 3 — continuation check
        "yes",  # turn 4 — continue
        "I still don't know",  # turn 5 — max turns
    ]

    last_content = ""
    for i, msg in enumerate(unhelpful_replies, start=1):
        resp = send_turn(base_url, chat_id, msg, history)
        content = resp.get("content", "")
        history = append_to_history(history, msg, content)

        if i < len(unhelpful_replies):
            # Intermediate turns: should be asking questions or continuation prompt
            intermediate_pass = not is_completed(content)
            turns.append(
                TurnResult(
                    i,
                    msg,
                    content,
                    intermediate_pass,
                    "Still in loop"
                    if intermediate_pass
                    else f"Unexpectedly completed at turn {i}",
                )
            )
            if not intermediate_pass:
                return ScenarioResult(
                    name, False, turns, f"Loop completed unexpectedly at turn {i}"
                )
        else:
            last_content = content

    # Final turn: must NOT be params-collected JSON (loop fell back to RAG/OOD)
    final_pass = not is_completed(last_content) and bool(last_content.strip())
    note = (
        "Correctly fell back to RAG/OOD after max turns"
        if final_pass
        else f"BAD: got params-collected JSON after max turns: {last_content[:150]}"
    )
    turns.append(
        TurnResult(
            len(unhelpful_replies),
            unhelpful_replies[-1],
            last_content,
            final_pass,
            note,
        )
    )

    overall = all(t.passed for t in turns)
    return ScenarioResult(name, overall, turns)


SCENARIOS = [
    scenario_1_single_turn_vehicle_tax,
    scenario_2_multiturn_public_holidays_en,
    scenario_4_no_params_fast_path,
    scenario_5_address_search,
    scenario_6_electricity_prices,
    scenario_7_session_isolation,
    scenario_8_awaiting_continuation,
    scenario_9_max_turns_reached,
]


def run_all(
    base_url: str, fail_fast: bool = True
) -> Tuple[List[ScenarioResult], int, int]:
    results: List[ScenarioResult] = []
    passed = 0
    failed = 0

    print(f"\n{'=' * 70}")
    print(f"  Agentic Loop Integration Tests  |  {base_url}")
    print(f"{'=' * 70}\n")

    for fn in SCENARIOS:
        print(f"Running: {fn.__name__} ...", flush=True)
        try:
            result = fn(base_url)
        except requests.exceptions.ConnectionError:
            result = ScenarioResult(
                fn.__name__, False, error="Connection refused — is the service running?"
            )
        except requests.exceptions.Timeout:
            result = ScenarioResult(
                fn.__name__, False, error=f"Request timed out after {REQUEST_TIMEOUT}s"
            )
        except Exception as exc:
            result = ScenarioResult(fn.__name__, False, error=str(exc))

        results.append(result)
        status_icon = "✅" if result.passed else "❌"
        print(f"  {status_icon}  {result.name}")

        for t in result.turns:
            turn_icon = "  ✓" if t.passed else "  ✗"
            print(f"    {turn_icon}  Turn {t.turn}: {t.message_sent[:60]!r}")
            if t.note:
                print(f"           → {t.note}")
            if not t.passed:
                print(f"           Response: {t.response_content[:200]}")

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
    parser = argparse.ArgumentParser(description="Agentic loop integration tests")
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
