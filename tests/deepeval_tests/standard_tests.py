import json
import pytest
from typing import Dict, Any
from pathlib import Path
import sys
import datetime
from deepeval.test_case import LLMTestCase
from deepeval.metrics.answer_relevancy.answer_relevancy import AnswerRelevancyMetric
from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
)

sys.path.insert(0, str(Path(__file__).parent.parent))
from mocks.dummy_llm_orchestrator import process_query


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
    """Test suite for RAG system evaluation using DeepEval metrics."""

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
        self, data_item: Dict[str, Any], provider: str = "anthropic"
    ) -> LLMTestCase:
        """Create a DeepEval test case from data item."""
        # Generate actual output using the dummy orchestrator
        result = process_query(
            question=data_item["input"], provider=provider, include_contexts=True
        )

        llm_test_case = LLMTestCase(
            input=data_item["input"],
            actual_output=result["response"],
            expected_output=data_item["expected_output"],
            retrieval_context=result["retrieval_context"],
        )
        return llm_test_case

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
    def test_all_metrics(self, test_item: Dict[str, Any]):
        """Test all metrics for each test case and collect results."""
        test_case = self.create_test_case(test_item)

        # Get test case index for consistent numbering
        test_case_num = self.test_data.index(test_item) + 1

        print(f"\nTesting case {test_case_num}: {test_item['input'][:50]}...")

        # Initialize metrics results
        metrics_results = {}
        failed_assertions = []

        # Define all metrics to test
        metrics = [
            ("contextual_precision", self.contextual_precision),
            ("contextual_recall", self.contextual_recall),
            ("contextual_relevancy", self.contextual_relevancy),
            ("answer_relevancy", self.answer_relevancy),
            ("faithfulness", self.faithfulness),
        ]

        # Test each metric and collect results
        for metric_name, metric in metrics:
            try:
                metric.measure(test_case)
                score = metric.score
                passed = score >= 0.7
                reason = metric.reason

                metrics_results[metric_name] = {
                    "score": score,
                    "passed": passed,
                    "reason": reason,
                }

                print(f"  {metric_name}: {score:.3f} ({'PASS' if passed else 'FAIL'})")

                # Collect failed assertions but don't raise immediately
                if not passed:
                    failed_assertions.append(
                        f"{metric_name} failed for query: '{test_item['input']}'. "
                        f"Score: {score}, Reason: {reason}"
                    )

            except Exception as e:
                metrics_results[metric_name] = {
                    "score": 0.0,
                    "passed": False,
                    "reason": f"Error: {str(e)}",
                }
                failed_assertions.append(f"{metric_name} error: {str(e)}")

        # Always add results to collector, regardless of pass/fail
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

        # Now raise assertion if any metrics failed (for pytest reporting)
        if failed_assertions:
            # Just raise the first failure to keep pytest output clean
            raise AssertionError(failed_assertions[0])
