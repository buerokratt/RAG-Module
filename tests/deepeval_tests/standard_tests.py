import json
import pytest
from typing import Dict, Any
from pathlib import Path
import sys
import datetime
import requests
from deepeval.test_case import LLMTestCase
from deepeval.metrics.answer_relevancy.answer_relevancy import AnswerRelevancyMetric
from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)
import asyncio
import httpx


sys.path.insert(0, str(Path(__file__).parent.parent))


class StandardResultCollector:
    """Collects test results during execution for report generation."""

    def __init__(self):
        self.results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "test_start_time": datetime.datetime.now().isoformat(),
            "metric_scores": {
                "contextual_precision": [],
                "contextual_recall": [],
                "contextual_relevancy": [],
                "answer_relevancy": [],
                "faithfulness": [],
            },
            "detailed_results": [],
        }

    def add_test_result(
        self,
        test_case_num: int,
        test_input: str,
        category: str,
        language: str,
        metrics_results: Dict[str, Dict[str, Any]],
    ):
        """Add a test result to the collector."""

        test_result = {
            "test_case": test_case_num,
            "input": test_input,
            "category": category,
            "language": language,
            "metrics": metrics_results,
        }

        self.results["detailed_results"].append(test_result)

        # Count this as ONE test (not one per metric)
        self.results["total_tests"] += 1

        # Check if majority of metrics passed
        passed_metrics = sum(
            1 for result in metrics_results.values() if result["passed"]
        )
        if passed_metrics >= len(metrics_results) * 0.6:  # 60% of metrics must pass
            self.results["passed_tests"] += 1
        else:
            self.results["failed_tests"] += 1

        # Add scores to metric_scores for averaging
        for metric_name, metric_result in metrics_results.items():
            score = metric_result["score"]
            self.results["metric_scores"][metric_name].append(score)

        print(
            f"Added test {test_case_num}: Total tests = {self.results['total_tests']}"
        )

    def save_results(self, filepath: str = "pytest_captured_results.json"):
        """Save collected results to JSON file."""
        self.results["test_end_time"] = datetime.datetime.now().isoformat()
        self.results["total_duration"] = (
            datetime.datetime.fromisoformat(self.results["test_end_time"])
            - datetime.datetime.fromisoformat(self.results["test_start_time"])
        ).total_seconds()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"Test results saved to {filepath}")
        print(f"Total tests: {self.results['total_tests']}")
        print(f"Passed tests: {self.results['passed_tests']}")
        print(f"Failed tests: {self.results['failed_tests']}")


# Global results collector
standard_results_collector = StandardResultCollector()


@pytest.fixture(scope="session", autouse=True)
def save_results_fixture():
    """Ensure results are saved even if tests fail."""
    yield
    # This runs after all tests, even if they fail
    print("Saving results from pytest fixture...")
    standard_results_collector.save_results("pytest_captured_results.json")


class TestRAGSystem:
    """Test suite for RAG system evaluation using DeepEval metrics via API."""

    @classmethod
    def setup_class(cls):
        """Setup test class with metrics and test data."""
        print("Setting up TestRAGSystem...")

        # Initialize all DeepEval metrics
        cls.contextual_precision = ContextualPrecisionMetric(threshold=0.7)
        cls.contextual_recall = ContextualRecallMetric(threshold=0.7)
        cls.contextual_relevancy = ContextualRelevancyMetric(threshold=0.7)
        cls.answer_relevancy = AnswerRelevancyMetric(threshold=0.7)
        cls.faithfulness = FaithfulnessMetric(threshold=0.7)

        # Load test dataset
        data_path = Path(__file__).parent.parent / "data" / "test_dataset.json"
        with open(data_path, "r", encoding="utf-8") as f:
            cls.test_data = json.load(f)

        print(f"Loaded {len(cls.test_data)} test cases")

    def create_test_case(
        self, data_item: Dict[str, Any], orchestration_url: str
    ) -> LLMTestCase:
        """Create a DeepEval test case by calling the orchestration API."""

        # Prepare API request
        api_request = {
            "chatId": f"test-{data_item.get('id', 'unknown')}",
            "message": data_item["input"],
            "authorId": "deepeval-tester",
            "conversationHistory": [],
            "url": "https://test.example.com",
            "environment": "development",
            "connection_id": "evalconnection-1",
        }

        # Call the testing endpoint
        try:
            response = requests.post(
                f"{orchestration_url}/orchestrate-eval", json=api_request, timeout=60
            )
            response.raise_for_status()
            result = response.json()
            print("=" * 80)
            print("API RESPONSE DEBUG")
            print("=" * 80)
            print(f"Response keys: {list(result.keys())}")
            print(f"Full response: {json.dumps(result, indent=2)}")
            print("=" * 80)
            # Extract data from API response
            actual_output = result.get("content", "")
            retrieval_context = result.get("retrieval_context", [])
            if retrieval_context is None:
                retrieval_context = []

            # Convert retrieval context to strings for DeepEval
            retrieval_context_strings = []
            if retrieval_context and isinstance(retrieval_context, list):
                retrieval_context_strings = [
                    chunk.get("content", "") if isinstance(chunk, dict) else str(chunk)
                    for chunk in retrieval_context
                ]

            # Create DeepEval test case
            llm_test_case = LLMTestCase(
                input=data_item["input"],
                actual_output=actual_output,
                expected_output=data_item["expected_output"],
                retrieval_context=retrieval_context_strings,
            )

            return llm_test_case

        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            # Return a test case with error message
            return LLMTestCase(
                input=data_item["input"],
                actual_output=f"API Error: {str(e)}",
                expected_output=data_item["expected_output"],
                retrieval_context=[],
            )

    @pytest.mark.parametrize(
        "test_item",
        [
            item
            for item in json.load(
                open(
                    Path(__file__).parent.parent / "data" / "test_dataset.json",
                    "r",
                    encoding="utf-8",
                )
            )
        ],
    )
    @pytest.mark.asyncio
    async def test_all_metrics(self, test_item: Dict[str, Any], orchestration_client):
        """Async version of DeepEval test with parallel metric execution."""

        orchestration_url = orchestration_client.base_url
        test_case_num = self.test_data.index(test_item) + 1
        print(f"\nTesting case {test_case_num}: {test_item['input'][:50]}...")

        # --- Fetch orchestration result asynchronously ---
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                response = await client.post(
                    f"{orchestration_url}/orchestrate-eval",
                    json={
                        "chatId": f"test-{test_item.get('id', 'unknown')}",
                        "message": test_item["input"],
                        "authorId": "deepeval-tester",
                        "conversationHistory": [],
                        "url": "https://test.example.com",
                        "environment": "development",
                        "connection_id": "evalconnection-1",
                    },
                )
                response.raise_for_status()
                result = response.json()
            except httpx.RequestError as e:
                result = {"content": f"API Error: {str(e)}", "retrieval_context": []}
            except Exception as e:
                result = {"content": f"Unexpected error: {str(e)}", "retrieval_context": []}

        retrieval_context = result.get("retrieval_context") or []
        retrieval_context = [
            c.get("content", "") if isinstance(c, dict) else str(c)
            for c in retrieval_context
        ]

        llm_test_case = LLMTestCase(
            input=test_item["input"],
            actual_output=result.get("content", ""),
            expected_output=test_item["expected_output"],
            retrieval_context=retrieval_context,
        )

        # --- Run metrics concurrently ---
        metrics = [
            ("contextual_precision", self.contextual_precision),
            ("contextual_recall", self.contextual_recall),
            ("contextual_relevancy", self.contextual_relevancy),
            ("answer_relevancy", self.answer_relevancy),
            ("faithfulness", self.faithfulness),
        ]

        async def run_metric(metric_name, metric):
            try:
                # run metric.measure() in a thread pool to avoid blocking
                await asyncio.to_thread(metric.measure, llm_test_case)
                score = metric.score
                return metric_name, {
                    "score": score,
                    "passed": score >= 0.7,
                    "reason": metric.reason,
                }
            except Exception as e:
                return metric_name, {
                    "score": 0.0,
                    "passed": False,
                    "reason": f"Error: {str(e)}",
                }

        metric_results_list = await asyncio.gather(
            *(run_metric(name, metric) for name, metric in metrics)
        )
        metrics_results = dict(metric_results_list)

        # --- Collect results ---
        try:
            standard_results_collector.add_test_result(
                test_case_num=test_case_num,
                test_input=test_item["input"],
                category=test_item["category"],
                language=test_item.get("language", "en"),
                metrics_results=metrics_results,
            )
        except Exception as e:
            print(f"Error adding test result: {e}")

        # --- Assert ---
        failed = [name for name, res in metrics_results.items() if not res["passed"]]
        if failed:
            pytest.fail(f"Metrics failed: {', '.join(failed)} for input: {test_item['input'][:50]}")
