"""Post-run evaluator: how well did the mentor's gate catch bluffs?

Compares the mentor's `advance_decision` verdicts (from a run's meta.json)
against the ground-truth `bluff_schedule` and reports precision / recall / F1
for the "BLUFF_SUSPECTED" label. Deterministic and dependency-free — no LLM —
which keeps it trustworthy and unit-testable. Upgrade to an LLM judge later if
you want it to grade answer *quality* rather than just detection.

    python judge.py --run courses/prompt-engineering/logs/run_001
"""
import argparse
import json
from pathlib import Path


def evaluate(verdicts: dict, bluff_schedule: dict) -> dict:
    """Precision/recall of BLUFF_SUSPECTED, scored only over the lessons actually run."""
    run_lessons = list(verdicts)
    predicted = {n for n in run_lessons if verdicts[n] == "BLUFF_SUSPECTED"}
    actual = {n for n in run_lessons if bluff_schedule.get(n)}

    tp = len(predicted & actual)
    fp = len(predicted - actual)
    fn = len(actual - predicted)
    tn = len(set(run_lessons) - predicted - actual)

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "caught": sorted(predicted & actual, key=int),
        "missed_bluffs": sorted(actual - predicted, key=int),
        "false_alarms": sorted(predicted - actual, key=int),
        "lessons_scored": len(run_lessons),
    }


def evaluate_run(run_dir) -> dict:
    meta = json.loads((Path(run_dir) / "meta.json").read_text(encoding="utf-8"))
    return evaluate(meta["verdicts"], meta["bluff_schedule"])


def _format(report: dict) -> str:
    return (
        f"bluff-detection precision={report['precision']}  recall={report['recall']}  "
        f"f1={report['f1']}\n"
        f"  TP={report['tp']} FP={report['fp']} FN={report['fn']} TN={report['tn']} "
        f"(over {report['lessons_scored']} lessons)\n"
        f"  caught={report['caught'] or '-'}  missed={report['missed_bluffs'] or '-'}  "
        f"false_alarms={report['false_alarms'] or '-'}"
    )


def main():
    ap = argparse.ArgumentParser(description="Score bluff detection for a run.")
    ap.add_argument("--run", required=True, help="path to a logs/run_NNN directory")
    args = ap.parse_args()
    report = evaluate_run(args.run)
    print(_format(report))


if __name__ == "__main__":
    main()
