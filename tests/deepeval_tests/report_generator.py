import json
from typing import Dict, Any, List
import datetime


def load_captured_results(
    filepath: str = "pytest_captured_results.json",
) -> Dict[str, Any]:
    """Load test results captured during pytest execution."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "error": f"Results file {filepath} not found. Please run pytest tests first.",
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "metric_scores": {},
            "detailed_results": [],
        }
    except json.JSONDecodeError as e:
        return {
            "error": f"Invalid JSON in results file: {str(e)}",
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "metric_scores": {},
            "detailed_results": [],
        }


def calculate_average_scores(metric_scores: Dict[str, List[float]]) -> Dict[str, float]:
    """Calculate average scores for each metric."""
    averages = {}
    for metric, scores in metric_scores.items():
        if scores:
            averages[metric] = sum(scores) / len(scores)
        else:
            averages[metric] = 0.0
    return averages


def generate_summary_table(results: Dict[str, Any]) -> str:
    """Generate summary table with overall results."""
    if "error" in results:
        return f"## DeepEval Test Results Summary\n\n**ERROR:** {results['error']}\n\n"

    total_tests = results["total_tests"]
    passed_tests = results["passed_tests"]
    failed_tests = results["failed_tests"]
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    avg_scores = calculate_average_scores(results["metric_scores"])

    table = "## DeepEval Test Results Summary\n\n"
    table += "| Metric | Pass Rate | Avg Score | Status |\n"
    table += "|--------|-----------|-----------|--------|\n"

    overall_status = "PASS" if pass_rate >= 70 else "FAIL"
    table += f"| **Overall** | {pass_rate:.1f}% | - | **{overall_status}** |\n"

    metric_names = {
        "contextual_precision": "Contextual Precision",
        "contextual_recall": "Contextual Recall",
        "contextual_relevancy": "Contextual Relevancy",
        "answer_relevancy": "Answer Relevancy",
        "faithfulness": "Faithfulness",
    }

    for metric_key, metric_name in metric_names.items():
        scores = results["metric_scores"].get(metric_key, [])
        if scores:
            avg_score = avg_scores[metric_key]
            passed_count = sum(1 for score in scores if score >= 0.7)
            metric_pass_rate = passed_count / len(scores) * 100
            status = "PASS" if metric_pass_rate >= 70 else "FAIL"
            table += f"| {metric_name} | {metric_pass_rate:.1f}% | {avg_score:.3f} | {status} |\n"
        else:
            table += f"| {metric_name} | 0.0% | 0.000 | FAIL |\n"

    table += f"\n**Total Tests:** {total_tests} | **Passed:** {passed_tests} | **Failed:** {failed_tests}\n"

    if "total_duration" in results:
        duration_minutes = results["total_duration"] / 60
        table += f"**Test Duration:** {duration_minutes:.1f} minutes\n"

    table += "\n"
    return table


def generate_detailed_results_table(results: Dict[str, Any]) -> str:
    """Generate detailed results table for each test case."""
    if "error" in results or not results.get("detailed_results"):
        return "## Detailed Test Results\n\nNo detailed test data available.\n\n"

    table = "## Detailed Test Results\n\n"
    table += "| Test | Language | Category | CP | CR | CRel | AR | Faith | Status |\n"
    table += "|------|----------|----------|----|----|------|----|----- -|--------|\n"

    for result in results["detailed_results"]:
        test_num = result["test_case"]
        category = result["category"]
        language = result.get("language", "en").upper()

        # Get scores for each metric (abbreviated column names)
        metrics = result["metrics"]
        cp_score = metrics.get("contextual_precision", {}).get("score", 0.0)
        cr_score = metrics.get("contextual_recall", {}).get("score", 0.0)
        crel_score = metrics.get("contextual_relevancy", {}).get("score", 0.0)
        ar_score = metrics.get("answer_relevancy", {}).get("score", 0.0)
        faith_score = metrics.get("faithfulness", {}).get("score", 0.0)

        # Determine overall status for this test case
        all_scores = [cp_score, cr_score, crel_score, ar_score, faith_score]
        passed_metrics = sum(1 for score in all_scores if score >= 0.7)
        test_status = (
            "PASS" if passed_metrics >= 4 else "FAIL"
        )  # 4 out of 5 metrics need to pass

        table += f"| {test_num} | {language} | {category} | {cp_score:.2f} | {cr_score:.2f} | {crel_score:.2f} | {ar_score:.2f} | {faith_score:.2f} | {test_status} |\n"

    table += "\n**Legend:** CP = Contextual Precision, CR = Contextual Recall, CRel = Contextual Relevancy, AR = Answer Relevancy, Faith = Faithfulness\n"
    table += "**Languages:** EN = English, ET = Estonian, RU = Russian\n\n"
    return table


def generate_failure_analysis(results: Dict[str, Any]) -> str:
    """Generate analysis of failed tests."""
    if "error" in results:
        return f"## Analysis\n\nCannot generate failure analysis due to error: {results['error']}\n\n"

    failed_results = []

    for result in results.get("detailed_results", []):
        for metric_name, metric_result in result["metrics"].items():
            if not metric_result["passed"]:
                failed_results.append(
                    {
                        "test_case": result["test_case"],
                        "input": result["input"],
                        "category": result["category"],
                        "metric": metric_name,
                        "score": metric_result["score"],
                        "reason": metric_result["reason"],
                    }
                )

    if not failed_results:
        return (
            "## Analysis\n\nAll tests passed successfully! No failures to analyze.\n\n"
        )

    analysis = "## Failed Test Analysis\n\n"
    analysis += "| Test | Query | Metric | Score | Issue |\n"
    analysis += "|------|--------|--------|-------|-------|\n"

    for failure in failed_results:  # Limit to first 10 failures
        query_preview = (
            failure["input"][:50] + "..."
            if len(failure["input"]) > 50
            else failure["input"]
        )
        reason_preview = failure["reason"]

        analysis += f"| {failure['test_case']} | {query_preview} | {failure['metric']} | {failure['score']:.2f} | {reason_preview} |\n"

    analysis += "\n"
    return analysis


def generate_recommendations(results: Dict[str, Any]) -> str:
    """Generate recommendations based on test results."""
    if "error" in results:
        return f"## Recommendations\n\nCannot generate recommendations due to error: {results['error']}\n\n"

    recommendations = "## Recommendations\n\n"

    avg_scores = calculate_average_scores(results["metric_scores"])
    low_performing_metrics = [
        (metric, score) for metric, score in avg_scores.items() if score < 0.7
    ]

    if not low_performing_metrics:
        recommendations += (
            "All metrics are performing well above the threshold of 0.7. Great job!\n\n"
        )
        return recommendations

    metric_recommendations = {
        "contextual_precision": "Consider improving your reranking model or adjusting reranking parameters to better prioritize relevant documents.",
        "contextual_recall": "Review your embedding model choice and vector search parameters. Consider domain-specific embeddings.",
        "contextual_relevancy": "Optimize chunk size and top-K retrieval parameters to reduce noise in retrieved contexts.",
        "answer_relevancy": "Review your prompt template and LLM parameters to improve response relevance to the input query.",
        "faithfulness": "Strengthen hallucination detection and ensure the LLM stays grounded in the provided context.",
    }

    for metric, score in low_performing_metrics:
        metric_name = metric.replace("_", " ").title()
        recommendations += f"**{metric_name}** (Score: {score:.3f}): {metric_recommendations[metric]}\n\n"

    return recommendations


def generate_full_report(results: Dict[str, Any]) -> str:
    """Generate complete report for GitHub Actions comment."""
    report = "# RAG System Evaluation Report\n\n"

    # Add summary
    report += generate_summary_table(results)

    # Add detailed results
    report += generate_detailed_results_table(results)

    # Add failure analysis
    report += generate_failure_analysis(results)

    # Add recommendations
    report += generate_recommendations(results)

    report += "---\n"
    report += f"*Report generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by DeepEval automated testing pipeline*\n"

    return report


def save_report_to_file(
    results: Dict[str, Any], output_path: str = "test_report.md"
) -> str:
    """Save the report to a markdown file and return the content."""
    report_content = generate_full_report(results)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return report_content


def display_summary(results: Dict[str, Any]) -> None:
    """Display test summary to console."""
    if "error" in results:
        print(f"ERROR: {results['error']}")
        return

    print("=== DEEPEVAL TEST SUMMARY ===")
    print(f"Total Tests: {results['total_tests']}")
    print(f"Passed: {results['passed_tests']}")
    print(f"Failed: {results['failed_tests']}")

    if results["total_tests"] > 0:
        overall_pass_rate = results["passed_tests"] / results["total_tests"] * 100
        print(f"Overall Pass Rate: {overall_pass_rate:.1f}%")

        if overall_pass_rate >= 70:
            print("STATUS: RAG system performing well")
        else:
            print("STATUS: RAG system needs improvement - review test report")

    if "total_duration" in results:
        duration_minutes = results["total_duration"] / 60
        print(f"Test Duration: {duration_minutes:.1f} minutes")


def main():
    """Main function to generate report from captured results."""
    print("Generating DeepEval report from captured test results...")

    try:
        # Load results captured during pytest execution
        results = load_captured_results("pytest_captured_results.json")

        # Generate and save report
        report_content = save_report_to_file(results, "test_report.md")

        print("DeepEval report generated successfully!")
        print("Report saved to test_report.md")
        print()

        # Display summary
        display_summary(results)

        return report_content

    except Exception as e:
        error_message = f"Failed to generate DeepEval report: {str(e)}"
        print(error_message)

        # Create minimal error report
        error_report = (
            f"# RAG System Evaluation Report\n\n## Error\n\n{error_message}\n\n"
        )
        with open("test_report.md", "w", encoding="utf-8") as f:
            f.write(error_report)

        return error_report


if __name__ == "__main__":
    main()
