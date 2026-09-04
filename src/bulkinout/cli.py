from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .request.answers import apply_answers, load_answers
from .request.reference_engine import ReferenceEngine
from .request.decision_guard import enforce_decision_guard
from .request.rules import generic_missing_questions, recommendation_specific_questions
from .request.request_builder import build_teleradiology_request
from .request.reference_catalog import build_catalog
from .request.golden import discover_golden_cases, run_golden_case


def _dump(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def cmd_core_structure(args):
    from .core.service import build_radiology_case
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY absent.")
    output = Path(args.output)
    case, extraction, _ = build_radiology_case(Path(args.input), model=args.model)
    _dump(output / "radiology_case.json", case.model_dump(mode="json"))
    _dump(output / "llm_extraction.json", extraction.model_dump(mode="json"))
    print(f"Core structuring terminé: {output / 'radiology_case.json'}")


def _write_answer_template(output_dir: Path, decision):
    qs = sorted(decision.discriminating_questions, key=lambda q: q.priority)
    payload = {
        "answers": [
            {
                "question_id": q.question_id,
                "field": q.field,
                "value": None,
                "note": q.question,
            }
            for q in qs if q.required_to_choose
        ]
    }
    _dump(output_dir / "answers.template.json", payload)


def cmd_request_run(args):
    from .core.service import build_radiology_case
    from .request.decision_llm import OpenAIRequestDecision
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY absent.")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] BULKINOUT Core...")
    radiology_case, extraction, paths = build_radiology_case(Path(args.input), model=args.model)
    case = radiology_case.clinical

    if args.answers:
        answer_path = Path(args.answers)
        print(f"[2/5] Application des réponses: {answer_path.name}")
        case = apply_answers(case, load_answers(answer_path), answer_path.name)
        radiology_case.clinical = case
    else:
        print("[2/5] Aucun fichier de réponses.")

    print("[3/5] Référentiel + décision Request...")
    initial_questions = generic_missing_questions(case)
    ref_engine = ReferenceEngine(Path(args.reference))
    reference_context = ref_engine.build_context(case)

    decision_engine = OpenAIRequestDecision(model=args.model)
    decision = decision_engine.decide(
        case,
        [q.model_dump(mode="json") for q in initial_questions],
        reference_context=reference_context,
    )
    decision = enforce_decision_guard(case, decision)

    print("[4/5] Garde-fous spécifiques...")
    specific_questions = recommendation_specific_questions(case, decision)
    qs_by_field = {q.field: q for q in initial_questions + specific_questions}
    all_questions = list(qs_by_field.values())

    blocking = [q for q in all_questions if q.blocking]
    if blocking:
        safety_fields = {
            "imaging_safety.pacemaker",
            "imaging_safety.implant_or_metal",
            "imaging_safety.pregnancy",
            "allergies.iodinated_contrast_reaction",
            "allergies.gadolinium_reaction",
        }
        decision.decision_status = (
            "safety_blocked" if any(q.field in safety_fields for q in blocking)
            else "insufficient_information"
        )
        decision.clinician_call_required = True
        decision.decision_ready_for_human_approval = False
        for q in blocking:
            if q.question not in decision.clinician_call_reasons:
                decision.clinician_call_reasons.append(q.question)

    material_specific = [
        q for q in specific_questions if q.importance in {"critical", "high"}
    ]
    if material_specific:
        decision.clinician_call_required = True
        decision.decision_ready_for_human_approval = False
        if any(q.blocking for q in material_specific):
            decision.decision_status = "safety_blocked"
        elif decision.decision_status == "selected":
            decision.decision_status = "insufficient_information"
        for q in material_specific:
            if q.question not in decision.clinician_call_reasons:
                decision.clinician_call_reasons.append(q.question)

    request = build_teleradiology_request(case, decision, all_questions)

    radiology_case.referral = {
        "reference_context": reference_context,
        "imaging_decision": decision.model_dump(mode="json"),
        "teleradiology_request": request.model_dump(mode="json"),
    }
    radiology_case.audit.append({
        "event": "request_workflow_completed",
        "decision_status": decision.decision_status,
    })

    print("[5/5] Écriture...")
    _dump(output_dir / "radiology_case.json", radiology_case.model_dump(mode="json"))
    _dump(output_dir / "llm_extraction.json", extraction.model_dump(mode="json"))
    _dump(output_dir / "case.json", case.model_dump(mode="json"))
    _dump(output_dir / "reference_context.json", reference_context)
    _dump(output_dir / "missing_questions.json", [q.model_dump(mode="json") for q in all_questions])
    _dump(output_dir / "imaging_decision.json", decision.model_dump(mode="json"))
    _dump(output_dir / "teleradiology_request.json", request.model_dump(mode="json"))
    _write_answer_template(output_dir, decision)

    print()
    print(f"Décision: {decision.decision_status}")
    print(f"Appel clinicien nécessaire: {'OUI' if decision.clinician_call_required else 'NON'}")
    print(f"Statut bon téléradiologie: {request.status}")




def cmd_request_golden(args):
    ref = Path(args.reference)
    cases = discover_golden_cases(Path(args.cases))
    if not cases:
        raise SystemExit("Aucun golden case trouvé.")
    failed = 0
    for path in cases:
        result = run_golden_case(path, ref)
        print(f"[{'PASS' if result.passed else 'FAIL'}] {result.case_id}")
        if not result.passed:
            failed += 1
            for err in result.errors:
                print(f"  - {err}")
    print(f"\n{len(cases) - failed}/{len(cases)} golden cases passent.")
    if failed:
        raise SystemExit(1)


def cmd_request_catalog(args):
    catalog = build_catalog(Path(args.reference))
    print(f"{len(catalog)} scénario(s)")
    for item in catalog:
        print(
            f"- {item['id']} v{item['version']} | "
            f"{item['candidate_count']} candidat(s) | "
            f"{item['question_count']} question(s) | "
            f"{item['status']}"
        )


def main():
    parser = argparse.ArgumentParser(
        prog="bulkinout",
        description="BULKINOUT — Bulk in. Intelligence out."
    )
    top = parser.add_subparsers(dest="area", required=True)

    core = top.add_parser("core", help="Noyau de structuration multimodale")
    core_sub = core.add_subparsers(dest="core_cmd", required=True)
    structure = core_sub.add_parser("structure", help="Bulk -> RadiologyCase structuré")
    structure.add_argument("--input", default="input")
    structure.add_argument("--output", default="output")
    structure.add_argument("--model", default=os.getenv("BULKINOUT_MODEL"))
    structure.set_defaults(func=cmd_core_structure)

    request = top.add_parser("request", help="Workflow pré-examen")
    request_sub = request.add_subparsers(dest="request_cmd", required=True)
    run = request_sub.add_parser("run")
    run.add_argument("--input", default="input")
    run.add_argument("--output", default="output")
    run.add_argument("--answers", default=None)
    run.add_argument("--reference", default="reference/scenarios")
    run.add_argument("--model", default=os.getenv("BULKINOUT_MODEL"))
    run.set_defaults(func=cmd_request_run)

    catalog = request_sub.add_parser("catalog", help="Lister les scénarios du référentiel")
    catalog.add_argument("--reference", default="reference/scenarios")
    catalog.set_defaults(func=cmd_request_catalog)

    golden = request_sub.add_parser("golden", help="Exécuter les golden cases sans LLM")
    golden.add_argument("--cases", default="tests/golden")
    golden.add_argument("--reference", default="reference/scenarios")
    golden.set_defaults(func=cmd_request_golden)

    report = top.add_parser("report", help="Workflow post-examen (standby)")
    report_sub = report.add_subparsers(dest="report_cmd")
    report.set_defaults(func=lambda args: print("BULKINOUT Report est réservé pour une étape ultérieure."))

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
