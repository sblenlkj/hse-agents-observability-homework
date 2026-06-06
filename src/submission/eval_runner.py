"""Evaluation runner for HSE Agents homework, Part 2.

The runner evaluates the observable baseline agent on ``golden_cases.yaml`` and
writes ``metrics_baseline.json`` in the same directory.

It is intentionally small and deterministic: checks are based on trace tool calls
and simple substring assertions, matching the seminar approach.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json
import statistics
from typing import Any

import yaml

from submission.agent_observable import run_agent_observable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = BASE_DIR / "golden_cases.yaml"
DEFAULT_METRICS_PATH = BASE_DIR / "metrics_baseline.json"


Metrics = dict[str, Any]
Case = dict[str, Any]


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[Case]:
    """Load and minimally validate golden cases from YAML."""
    with path.open(encoding="utf-8") as file:
        cases = yaml.safe_load(file)

    if not isinstance(cases, list):
        raise ValueError("golden_cases.yaml must contain a list of cases")

    required = {"id", "category", "input"}
    allowed_categories = {"happy", "edge", "adversarial"}

    for case in cases:
        if not isinstance(case, dict):
            raise ValueError(f"Case must be a mapping, got {type(case)!r}")
        missing = required - set(case)
        if missing:
            raise ValueError(f"Case {case!r} misses fields: {sorted(missing)}")
        if case["category"] not in allowed_categories:
            raise ValueError(f"Unknown category for {case['id']}: {case['category']!r}")

    return cases


def iter_spans(root_span: dict[str, Any]):
    """Yield a span tree depth-first."""
    yield root_span
    for child in root_span.get("children", []):
        yield from iter_spans(child)


def collect_called_tools(root_span: dict[str, Any]) -> list[str]:
    """Return tool names called by the agent, without the ``tool.`` prefix."""
    tools: list[str] = []
    for span in iter_spans(root_span):
        if span.get("kind") == "tool":
            attrs = span.get("attributes", {})
            tool_name = attrs.get("tool.name")
            if not tool_name:
                name = str(span.get("name", ""))
                tool_name = name.removeprefix("tool.")
            tools.append(str(tool_name))
    return tools


def collect_llm_spans(root_span: dict[str, Any]) -> list[dict[str, Any]]:
    return [span for span in iter_spans(root_span) if span.get("kind") == "llm"]


def trace_cost_usd(root_span: dict[str, Any]) -> float:
    total = 0.0
    for llm_span in collect_llm_spans(root_span):
        total += float(llm_span.get("attributes", {}).get("cost_usd", 0.0))
    return total


def _contains_any(answer: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    answer_lower = answer.lower()
    return any(str(pattern).lower() in answer_lower for pattern in patterns)


def _contains_none(answer: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    answer_lower = answer.lower()
    return not any(str(pattern).lower() in answer_lower for pattern in patterns)


def check_case(case: Case, answer: str, root_span: dict[str, Any]) -> dict[str, Any]:
    """Check one golden case against answer text and observable trace."""
    called_tools = collect_called_tools(root_span)
    expected_tool = case.get("must_call_tool", None)

    if expected_tool is None:
        tool_check = len(called_tools) == 0
    else:
        tool_check = str(expected_tool) in called_tools

    contains_check = _contains_any(answer, case.get("answer_contains_any"))
    not_contains_check = _contains_none(answer, case.get("answer_must_not_contain"))
    passed = tool_check and contains_check and not_contains_check

    return {
        "id": case["id"],
        "category": case["category"],
        "input": case["input"],
        "answer": answer,
        "called_tools": called_tools,
        "expected_tool": expected_tool,
        "tool_check": tool_check,
        "contains_check": contains_check,
        "not_contains_check": not_contains_check,
        "passed": passed,
        "cost_usd": trace_cost_usd(root_span),
        "llm_calls": len(collect_llm_spans(root_span)),
    }


def percentile(values: list[float], p: float) -> float:
    """Small deterministic percentile helper, nearest-rank style."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * p)))
    return ordered[index]


def run_eval(cases: list[Case] | None = None) -> Metrics:
    """Run observable baseline agent on golden cases and return aggregate metrics."""
    cases = cases or load_cases()
    results: list[dict[str, Any]] = []

    for case in cases:
        answer, root_span = run_agent_observable(str(case["input"]))
        results.append(check_case(case, answer, root_span))

    total_cases = len(results)
    passed_total = sum(1 for result in results if result["passed"])

    by_category: dict[str, dict[str, int]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[result["category"]].append(result)

    for category in ["happy", "edge", "adversarial"]:
        category_results = grouped.get(category, [])
        by_category[category] = {
            "passed": sum(1 for result in category_results if result["passed"]),
            "total": len(category_results),
        }

    costs = [float(result["cost_usd"]) for result in results]
    llm_calls = [int(result["llm_calls"]) for result in results]

    metrics: Metrics = {
        "task_success_rate": round(passed_total / total_cases, 4) if total_cases else 0.0,
        "by_category": by_category,
        "avg_cost_usd": round(statistics.mean(costs), 8) if costs else 0.0,
        "p95_cost_usd": round(percentile(costs, 0.95), 8),
        "avg_llm_calls": round(statistics.mean(llm_calls), 4) if llm_calls else 0.0,
        "total_cases": total_cases,
        "passed_cases": passed_total,
        "failed_cases": total_cases - passed_total,
        "results": results,
    }
    return metrics


def write_metrics(metrics: Metrics, path: Path = DEFAULT_METRICS_PATH) -> None:
    path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def print_summary(metrics: Metrics) -> None:
    print("Evaluation summary")
    print("=" * 60)
    print(f"task_success_rate: {metrics['task_success_rate']:.2%}")
    print(f"avg_cost_usd:      {metrics['avg_cost_usd']:.8f}")
    print(f"p95_cost_usd:      {metrics['p95_cost_usd']:.8f}")
    print(f"avg_llm_calls:     {metrics['avg_llm_calls']}")
    print(f"total_cases:       {metrics['total_cases']}")
    print()
    for category, values in metrics["by_category"].items():
        total = values["total"]
        passed = values["passed"]
        rate = passed / total if total else 0.0
        print(f"{category:12s}: {passed}/{total} ({rate:.0%})")

    failed = [result for result in metrics["results"] if not result["passed"]]
    if failed:
        print("\nFailed cases:")
        for result in failed:
            preview = str(result["answer"]).replace("\n", " ")[:120]
            print(
                f"- {result['id']} [{result['category']}] "
                f"tools={result['called_tools']} expected={result['expected_tool']!r} "
                f"tool={result['tool_check']} contains={result['contains_check']} "
                f"not_contains={result['not_contains_check']} :: {preview}"
            )


def main() -> None:
    metrics = run_eval()
    write_metrics(metrics)
    print_summary(metrics)
    print(f"\nWrote metrics to {DEFAULT_METRICS_PATH}")


if __name__ == "__main__":
    main()
