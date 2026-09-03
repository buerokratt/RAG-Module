"""
Retrieval Evaluation Script — tests semantic search accuracy across 40+ queries.

Usage:
    python eval_search.py
    python eval_search.py --ruuter-url http://localhost:8086
    python eval_search.py --output results.json   # also save detailed JSON results

What it does:
    1. Sends each query to POST /rag-search/api-tools/search
    2. Checks if the top result matches the expected endpoint name
    3. Prints a detailed pass/fail table
    4. Outputs accuracy %, average cosine score, and a list of failures
"""

import argparse
import json
import time
from pathlib import Path
from typing import Optional

import requests

DEFAULT_RUUTER_URL = "http://localhost:8086"
SEARCH_ENDPOINT = "/rag-search/api-tools/search"

# ============================================================================
# Evaluation Dataset — aligned with test-endpoints.json (15 endpoints)
# Format: (query, expected_endpoint_name or None for "no match expected")
# ============================================================================
EVAL_QUERIES = [
    # --- get_public_holidays ---
    ("What are the public holidays in Estonia this year?", "get_public_holidays"),
    ("List official public holidays in Estonia for 2025", "get_public_holidays"),
    ("When are the national public holidays in Estonia?", "get_public_holidays"),
    (
        "Show me all public days off in Estonia between January and June",
        "get_public_holidays",
    ),
    ("What are the official non-working days in Estonia?", "get_public_holidays"),
    # Estonian
    ("Millised on Eesti riigipühad sel aastal?", "get_public_holidays"),
    ("Millal on Eestis ametlikud riigipühad 2025. aastal?", "get_public_holidays"),
    ("Näita mulle Eesti riigipühi jaanuarist juunini", "get_public_holidays"),
    # --- get_school_holidays ---
    ("When are the school holidays in Estonia?", "get_school_holidays"),
    ("What are the school term breaks in Estonia this year?", "get_school_holidays"),
    ("When does school summer break start in Estonia in 2025?", "get_school_holidays"),
    (
        "Show me school holiday periods in Estonia for spring 2025",
        "get_school_holidays",
    ),
    # Estonian
    ("Millal on Eesti koolide koolivaheajad?", "get_school_holidays"),
    ("Millal algab koolide suvepuhkus Eestis 2025. aastal?", "get_school_holidays"),
    ("Näita mulle kevadise koolivaheaja aegu Eestis", "get_school_holidays"),
    # --- get_electricity_prices ---
    ("What are the electricity market prices in Estonia?", "get_electricity_prices"),
    (
        "Show me electricity prices for the past week in Estonia",
        "get_electricity_prices",
    ),
    (
        "Fetch energy market prices between January and March 2025",
        "get_electricity_prices",
    ),
    (
        "What was the electricity spot price in Estonia last month?",
        "get_electricity_prices",
    ),
    # Estonian
    ("Millised on elektrituruhinnad Eestis?", "get_electricity_prices"),
    ("Näita elektrihindu eelmise nädala kohta Eestis", "get_electricity_prices"),
    ("Mis oli elektrihind Eestis eelmisel kuul?", "get_electricity_prices"),
    # --- get_vehicle_tax_info ---
    ("Calculate vehicle tax for registration number 123ABC", "get_vehicle_tax_info"),
    (
        "How much is the vehicle tax for my car with plate 456XYZ?",
        "get_vehicle_tax_info",
    ),
    ("What is the car tax based on my registration number?", "get_vehicle_tax_info"),
    # Estonian
    ("Arvuta sõidukimaks registreerimisnumbri 123ABC alusel", "get_vehicle_tax_info"),
    ("Kui suur on minu auto maks numbrimärgi 456XYZ järgi?", "get_vehicle_tax_info"),
    (
        "Mis on mootorsõidukimaks minu auto registreerimisnumbri alusel?",
        "get_vehicle_tax_info",
    ),
    # --- get_parliament_votings ---
    (
        "Show me the latest parliament voting records in Estonia",
        "get_parliament_votings",
    ),
    ("What did the Riigikogu vote on recently?", "get_parliament_votings"),
    (
        "Retrieve parliamentary voting decisions from the Estonian parliament",
        "get_parliament_votings",
    ),
    ("What laws were voted on in the Estonian parliament?", "get_parliament_votings"),
    # Estonian
    ("Näita Riigikogu viimaseid hääletusprotokolle", "get_parliament_votings"),
    ("Mille üle hääletas Riigikogu hiljuti?", "get_parliament_votings"),
    ("Milliseid seadusi hääletati Eesti parlamendis?", "get_parliament_votings"),
    # --- get_parliament_participation_stats ---
    (
        "How often do Estonian parliament members attend sessions?",
        "get_parliament_participation_stats",
    ),
    (
        "Show me parliament member attendance statistics",
        "get_parliament_participation_stats",
    ),
    (
        "Which MPs have the best attendance record in the Riigikogu?",
        "get_parliament_participation_stats",
    ),
    # Estonian
    (
        "Kui tihti osalevad Riigikogu liikmed istungitel?",
        "get_parliament_participation_stats",
    ),
    (
        "Näita Riigikogu liikmete kohaloleku statistikat",
        "get_parliament_participation_stats",
    ),
    (
        "Millistel saadikutel on Riigikogu parim kohalolekurekord?",
        "get_parliament_participation_stats",
    ),
    # --- get_initiatives ---
    ("Show me a list of active citizen initiatives in Estonia", "get_initiatives"),
    ("What public initiatives are currently available?", "get_initiatives"),
    ("List all citizen initiatives on rahvaalgatus.ee", "get_initiatives"),
    # Estonian
    ("Näita mulle aktiivsete kodanike algatuste nimekirja Eestis", "get_initiatives"),
    ("Millised rahvaalgatused on praegu saadaval?", "get_initiatives"),
    ("Loetle kõik algatused rahvaalgatus.ee lehel", "get_initiatives"),
    # --- get_initiative_details ---
    ("Get details about citizen initiative with ID abc123", "get_initiative_details"),
    (
        "Show me more information about a specific public initiative",
        "get_initiative_details",
    ),
    ("Fetch the details of initiative ID xyz789", "get_initiative_details"),
    # Estonian
    ("Too andmed kodanike algatuse ID abc123 kohta", "get_initiative_details"),
    ("Näita mulle üksikasju konkreetse rahvaalgatuse kohta", "get_initiative_details"),
    ("Too algatuse ID xyz789 üksikasjad", "get_initiative_details"),
    # --- get_initiative_events ---
    (
        "What are the latest events related to citizen initiatives?",
        "get_initiative_events",
    ),
    ("Show me updates and events for public initiatives", "get_initiative_events"),
    (
        "Are there any new events for citizen initiatives in Estonia?",
        "get_initiative_events",
    ),
    # Estonian
    (
        "Millised on viimased kodanike algatustega seotud sündmused?",
        "get_initiative_events",
    ),
    ("Näita rahvaalgatuste uuendusi ja sündmusi", "get_initiative_events"),
    ("Kas Eestis on uusi sündmusi kodanike algatuste kohta?", "get_initiative_events"),
    # --- search_address ---
    ("Search for the address Viru 4 in Tallinn", "search_address"),
    ("Find the location of Kadriorg Park in Tallinn", "search_address"),
    ("Look up an address or place name in Estonia", "search_address"),
    ("Search for a street address in Tartu", "search_address"),
    # Estonian
    ("Otsi aadressi Viru 4 Tallinnas", "search_address"),
    ("Leia Kadrioru pargi asukoht Tallinnas", "search_address"),
    ("Otsi tänavaaadress Tartus", "search_address"),
    # --- get_population_statistics ---
    ("What is the population of Estonia?", "get_population_statistics"),
    ("Show me population statistics data for Estonia", "get_population_statistics"),
    ("Fetch demographic statistics for Estonia", "get_population_statistics"),
    (
        "What is the population breakdown by age group in Estonia?",
        "get_population_statistics",
    ),
    # Estonian
    ("Milline on Eesti rahvaarv?", "get_population_statistics"),
    ("Näita mulle Eesti rahvastikustatistika andmeid", "get_population_statistics"),
    (
        "Milline on Eesti rahvastiku jaotus vanuserühmade kaupa?",
        "get_population_statistics",
    ),
    # --- get_economic_statistics ---
    ("Show me economic statistics for Estonia", "get_economic_statistics"),
    ("What is the GDP and economic output of Estonia?", "get_economic_statistics"),
    (
        "Fetch economic data for Estonia from the statistics office",
        "get_economic_statistics",
    ),
    # Estonian
    ("Näita mulle Eesti majandusstatistikat", "get_economic_statistics"),
    ("Mis on Eesti SKP ja majanduslik toodang?", "get_economic_statistics"),
    ("Too majandusandmed Eesti statistikaametist", "get_economic_statistics"),
    # --- get_labor_statistics ---
    ("What is the unemployment rate in Estonia?", "get_labor_statistics"),
    ("Show me labor and employment statistics for Estonia", "get_labor_statistics"),
    ("How many people are employed in Estonia?", "get_labor_statistics"),
    ("Fetch workforce and jobless statistics for Estonia", "get_labor_statistics"),
    # Estonian
    ("Milline on töötuse määr Eestis?", "get_labor_statistics"),
    ("Näita mulle Eesti tööjõu ja tööhõive statistikat", "get_labor_statistics"),
    ("Kui palju inimesi töötab Eestis?", "get_labor_statistics"),
    # --- get_current_weather ---
    ("What is the current weather in Tallinn?", "get_current_weather"),
    ("Show me the current weather conditions in Estonia", "get_current_weather"),
    (
        "What is the temperature right now at the Tallinn weather station?",
        "get_current_weather",
    ),
    # Estonian
    ("Milline on praegune ilm Tallinnas?", "get_current_weather"),
    ("Näita mulle praeguseid ilmastikuolusid Eestis", "get_current_weather"),
    ("Mis on praegune temperatuur Tallinna ilmajaamas?", "get_current_weather"),
    # --- get_weather_forecast ---
    ("What is the weather forecast for Tallinn tomorrow?", "get_weather_forecast"),
    ("Show me the upcoming weather forecast for Tartu", "get_weather_forecast"),
    ("What will the weather be like in Estonia next week?", "get_weather_forecast"),
    (
        "Give me a weather forecast for the next few days in Estonia",
        "get_weather_forecast",
    ),
    # Estonian
    ("Milline on ilmaprognoos Tallinnas homme?", "get_weather_forecast"),
    ("Näita mulle Tartu eelseisvat ilmaprognoosi", "get_weather_forecast"),
    ("Milline on ilm Eestis järgmisel nädalal?", "get_weather_forecast"),
    # --- NEGATIVE queries — should return NO matching results ---
    ("Who is the Prime Minister of Estonia?", None),
    ("What is the best restaurant in Tallinn?", None),
    ("Tell me a random fact about Estonia", None),
    ("What is the meaning of life?", None),
    ("Book me a flight to London", None),
    ("Can you translate this text to Estonian?", None),
    ("What are the visa requirements to visit Estonia?", None),
    ("How do I apply for an Estonian e-Residency?", None),
    ("What is the history of Tallinn Old Town?", None),
    ("Give me a poem about Estonia", None),
    # Estonian negatives
    ("Kes on Eesti peaminister?", None),
    ("Mis on parim restoran Tallinnas?", None),
    ("Mis on elu mõte?", None),
]


def search(ruuter_url: str, query: str, top_k: int = 3) -> Optional[dict]:
    """Send a search query and return the parsed response."""
    url = f"{ruuter_url}{SEARCH_ENDPOINT}"
    try:
        response = requests.post(
            url,
            json={"query": query, "top_k": top_k, "environment": "production"},
            timeout=30,
        )
        if response.status_code == 200:
            body = response.json()
            # Handle Ruuter wrapper: body may be {"response": {...}}
            return body.get("response", body)
        return None
    except Exception:
        return None


def evaluate(ruuter_url: str, delay: float = 0.5) -> list:
    """Run all evaluation queries and return results."""
    results = []
    for query, expected in EVAL_QUERIES:
        response = search(ruuter_url, query)

        if response is None:
            results.append(
                {
                    "query": query,
                    "expected": expected,
                    "got": "ERROR",
                    "cosine_score": None,
                    "rrf_score": None,
                    "confidence": None,
                    "pass": False,
                    "error": "Request failed",
                }
            )
            time.sleep(delay)
            continue

        top_results = response.get("results", [])
        top = top_results[0] if top_results else None

        got_name = top["name"] if top else None
        cosine_score = top["cosine_score"] if top else None
        rrf_score = top["rrf_score"] if top else None
        confidence = top["confidence"] if top else None

        # Determine pass/fail
        if expected is None:
            # Negative query: should return no HIGH confidence result
            passed = got_name is None or confidence != "high"
        else:
            passed = got_name == expected

        results.append(
            {
                "query": query,
                "expected": expected,
                "got": got_name,
                "cosine_score": cosine_score,
                "rrf_score": rrf_score,
                "confidence": confidence,
                "pass": passed,
            }
        )

        time.sleep(delay)

    return results


def print_report(results: list) -> None:
    """Print evaluation results table and summary."""
    pass_icon = "✅"
    fail_icon = "❌"

    print(f"\n{'=' * 100}")
    print(f"{'RETRIEVAL EVALUATION REPORT':^100}")
    print(f"{'=' * 100}")
    print(
        f"{'#':<4} {'Query':<48} {'Expected':<28} {'Got':<28} {'Cosine':>7} {'RRF':>9}  {'Result'}"
    )
    print(f"{'-' * 100}")

    for i, r in enumerate(results, 1):
        query = r["query"][:46] + ".." if len(r["query"]) > 46 else r["query"]
        expected = (r["expected"] or "(none)")[:26]
        got = (r["got"] or "(none)")[:26]
        cosine = (
            f"{r['cosine_score']:.4f}" if r["cosine_score"] is not None else "  -   "
        )
        rrf = f"{r['rrf_score']:.6f}" if r["rrf_score"] is not None else "    -    "
        verdict = pass_icon if r["pass"] else fail_icon

        # Highlight negative query failures
        if r["expected"] is None and r["got"] is not None and r["confidence"] == "high":
            verdict = fail_icon + " FALSE POSITIVE"

        print(
            f"{i:<4} {query:<48} {expected:<28} {got:<28} {cosine:>7} {rrf:>9}  {verdict}"
        )

    # Summary stats
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    failed = total - passed

    positives = [r for r in results if r["expected"] is not None]
    negatives = [r for r in results if r["expected"] is None]
    positive_pass = sum(1 for r in positives if r["pass"])
    negative_pass = sum(1 for r in negatives if r["pass"])

    scores = [
        r["cosine_score"]
        for r in results
        if r["cosine_score"] is not None and r["pass"]
    ]
    avg_cosine = sum(scores) / len(scores) if scores else 0.0
    rrf_scores = [
        r["rrf_score"] for r in results if r["rrf_score"] is not None and r["pass"]
    ]
    avg_rrf = sum(rrf_scores) / len(rrf_scores) if rrf_scores else 0.0

    print(f"\n{'=' * 100}")
    print("SUMMARY")
    print(f"{'=' * 100}")
    print(f"  Overall Accuracy:       {passed}/{total}  ({100 * passed / total:.1f}%)")
    print(
        f"  Positive Queries:       {positive_pass}/{len(positives)}  ({100 * positive_pass / len(positives):.1f}%)"
    )
    print(
        f"  Negative Queries:       {negative_pass}/{len(negatives)}  ({100 * negative_pass / len(negatives):.1f}%)"
    )
    print(
        f"  Avg Cosine (correct):   {avg_cosine:.4f}  (threshold: min={0.40}, high={0.60})"
    )
    print(f"  Avg RRF    (correct):   {avg_rrf:.6f}")
    print("\n  Target: >90% overall accuracy, avg cosine >0.55")

    if failed > 0:
        print(f"\n  FAILURES ({failed}):")
        for r in results:
            if not r["pass"]:
                print(f"     '{r['query']}'")
                print(
                    f"       Expected: {r['expected']}  |  Got: {r['got']}  |  Cosine: {r['cosine_score']}  |  RRF: {r['rrf_score']}"
                )

    print(f"{'=' * 100}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate semantic search retrieval accuracy"
    )
    parser.add_argument("--ruuter-url", default=DEFAULT_RUUTER_URL)
    parser.add_argument(
        "--delay", type=float, default=0.5, help="Seconds between requests"
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Save results to JSON file"
    )
    args = parser.parse_args()

    print(f"\nStarting evaluation — {len(EVAL_QUERIES)} queries")
    print(f"Target: {args.ruuter_url}{SEARCH_ENDPOINT}\n")

    results = evaluate(args.ruuter_url, args.delay)
    print_report(results)

    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Detailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
