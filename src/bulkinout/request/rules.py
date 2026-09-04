from __future__ import annotations

from ..core.models import ClinicalCase, FieldStatus, MissingQuestion


def _unknown(section: dict, key: str) -> bool:
    field = section.get(key)
    return field is None or field.status in {FieldStatus.unknown, FieldStatus.conflicting}


def generic_missing_questions(case: ClinicalCase) -> list[MissingQuestion]:
    """
    Generic completeness/safety checks. These are intentionally limited and are not
    a substitute for a validated local radiology protocol matrix.
    """
    out: list[MissingQuestion] = []

    if _unknown(case.current_problem, "indication"):
        out.append(MissingQuestion(
            field="current_problem.indication",
            question="Quelle est l'indication clinique précise et la question diagnostique ?",
            importance="critical",
            reason="Without a clinical question, exam selection and interpretation lack focus.",
            blocking=True,
        ))

    if _unknown(case.current_problem, "symptoms") and _unknown(case.current_problem, "known_diagnosis"):
        out.append(MissingQuestion(
            field="current_problem.symptoms",
            question="Quels sont les symptômes/signes actuels motivant l'imagerie ?",
            importance="high",
            reason="Required to select the modality, body region, and urgency.",
            blocking=False,
        ))

    return out


def recommendation_specific_questions(case: ClinicalCase, decision) -> list[MissingQuestion]:
    """
    Add safety/completeness questions AFTER the LLM proposes an exam.
    This avoids asking every patient every modality-specific question.
    """
    out: list[MissingQuestion] = []
    primary = decision.primary
    modality = (primary.modality or "").upper()
    contrast = primary.contrast

    if modality in {"CT", "SCANNER"} and contrast in {"yes", "conditional"}:
        if _unknown(case.allergies, "iodinated_contrast_reaction"):
            out.append(MissingQuestion(
                field="allergies.iodinated_contrast_reaction",
                question="Antécédent de réaction au produit de contraste iodé ? Si oui, préciser le type et la gravité.",
                importance="high",
                reason="May change contrast administration or the protocol.",
                blocking=False,
            ))
        if _unknown(case.labs, "egfr_ml_min_1_73m2"):
            out.append(MissingQuestion(
                field="labs.egfr_ml_min_1_73m2",
                question="Fonction rénale récente (DFG/eGFR) disponible si nécessaire selon le contexte/protocole local ?",
                importance="high",
                reason="May change the injection strategy under local procedures and clinical context.",
                blocking=False,
            ))

    if modality in {"MRI", "IRM"}:
        if _unknown(case.imaging_safety, "pacemaker"):
            out.append(MissingQuestion(
                field="imaging_safety.pacemaker",
                question="Pacemaker/stimulateur ou défibrillateur implantable ?",
                importance="critical",
                reason="May require a specific procedure or change MRI feasibility.",
                blocking=True,
            ))
        if _unknown(case.imaging_safety, "implant_or_metal"):
            out.append(MissingQuestion(
                field="imaging_safety.implant_or_metal",
                question="Implant, matériel métallique, clip, stent ou autre dispositif à caractériser avant IRM ?",
                importance="high",
                reason="MRI compatibility must be verified, not assumed.",
                blocking=False,
            ))

    # Pregnancy relevance is intentionally broad for ionizing modalities.
    if modality in {"CT", "SCANNER", "XRAY", "RADIOGRAPHY"}:
        sex = case.patient.get("sex")
        age = case.patient.get("age")
        relevant = True
        if sex and sex.status == FieldStatus.observed and str(sex.value).upper() in {"M", "MALE", "HOMME"}:
            relevant = False
        if age and age.status == FieldStatus.observed:
            try:
                a = int(age.value)
                if a < 10 or a > 60:
                    relevant = False
            except (TypeError, ValueError):
                relevant = True
        if relevant and _unknown(case.imaging_safety, "pregnancy"):
            out.append(MissingQuestion(
                field="imaging_safety.pregnancy",
                question="Une grossesse est-elle possible ou en cours ?",
                importance="high",
                reason="Safety information for an examination using ionizing radiation.",
                blocking=False,
            ))

    return out
