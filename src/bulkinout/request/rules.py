from __future__ import annotations

from ..core.models import ClinicalCase, ClinicalField, FieldStatus, ImagingDecision, MissingQuestion


def _unknown(section: dict[str, ClinicalField], key: str) -> bool:
    field = section.get(key)
    return field is None or field.status in {FieldStatus.unknown, FieldStatus.conflicting}


def generic_missing_questions(case: ClinicalCase) -> list[MissingQuestion]:
    """
    Generic completeness/safety checks. These are intentionally limited and are not
    a substitute for a validated local radiology protocol matrix.
    """
    out: list[MissingQuestion] = []

    if _unknown(case.current_problem, "indication"):
        out.append(
            MissingQuestion(
                field="current_problem.indication",
                question="Quelle est l'indication clinique précise et la question diagnostique ?",
                importance="critical",
                reason="Without a clinical question, exam selection and interpretation lack focus.",
                blocking=True,
            )
        )

    if _unknown(case.current_problem, "symptoms") and _unknown(
        case.current_problem, "known_diagnosis"
    ):
        out.append(
            MissingQuestion(
                field="current_problem.symptoms",
                question="Quels sont les symptômes/signes actuels motivant l'imagerie ?",
                importance="high",
                reason="Required to select the modality, body region, and urgency.",
                blocking=False,
            )
        )

    return out


def recommendation_specific_questions(
    case: ClinicalCase, decision: ImagingDecision
) -> list[MissingQuestion]:
    """
    Add safety/completeness questions AFTER the LLM proposes an exam.
    This avoids asking every patient every modality-specific question.
    """
    primary = decision.primary
    modality = (primary.modality or "").upper()
    questions: list[MissingQuestion] = []
    if modality in {"CT", "SCANNER"} and primary.contrast in {"yes", "conditional"}:
        questions.extend(_contrast_ct_questions(case))
    if modality in {"MRI", "IRM"}:
        questions.extend(_mri_questions(case))
    if modality in {"CT", "SCANNER", "XRAY", "RADIOGRAPHY"}:
        questions.extend(_ionizing_radiation_questions(case))
    return questions


def _contrast_ct_questions(case: ClinicalCase) -> list[MissingQuestion]:
    questions: list[MissingQuestion] = []
    if _unknown(case.allergies, "iodinated_contrast_reaction"):
        questions.append(
            MissingQuestion(
                field="allergies.iodinated_contrast_reaction",
                question="Antécédent de réaction au produit de contraste iodé ? Si oui, préciser le type et la gravité.",
                importance="high",
                reason="May change contrast administration or the protocol.",
                required_to_choose=True,
            )
        )
    if _unknown(case.labs, "egfr_ml_min_1_73m2"):
        questions.append(
            MissingQuestion(
                field="labs.egfr_ml_min_1_73m2",
                question="Fonction rénale récente (DFG/eGFR) disponible si nécessaire selon le contexte/protocole local ?",
                importance="high",
                reason="May change the injection strategy under local procedures and clinical context.",
                required_to_choose=True,
            )
        )
    return questions


def _mri_questions(case: ClinicalCase) -> list[MissingQuestion]:
    questions: list[MissingQuestion] = []
    if _unknown(case.imaging_safety, "pacemaker"):
        questions.append(
            MissingQuestion(
                field="imaging_safety.pacemaker",
                question="Pacemaker/stimulateur ou défibrillateur implantable ?",
                importance="critical",
                reason="May require a specific procedure or change MRI feasibility.",
                required_to_choose=True,
                blocking=True,
            )
        )
    if _unknown(case.imaging_safety, "implant_or_metal"):
        questions.append(
            MissingQuestion(
                field="imaging_safety.implant_or_metal",
                question="Implant, matériel métallique, clip, stent ou autre dispositif à caractériser avant IRM ?",
                importance="high",
                reason="MRI compatibility must be verified, not assumed.",
                required_to_choose=True,
            )
        )
    return questions


def _pregnancy_is_relevant(case: ClinicalCase) -> bool:
    sex = case.patient.get("sex")
    relevant = not (
        sex
        and sex.status == FieldStatus.observed
        and str(sex.value).upper() in {"M", "MALE", "HOMME"}
    )

    age = case.patient.get("age")
    if not age or age.status != FieldStatus.observed:
        return relevant
    try:
        raw_age = age.value
        if not isinstance(raw_age, (str, int, float)) or isinstance(raw_age, bool):
            raise TypeError
        age_value = int(raw_age)
        if age_value < 10 or age_value > 60:
            return False
    except (TypeError, ValueError):
        return True
    return relevant


def _ionizing_radiation_questions(case: ClinicalCase) -> list[MissingQuestion]:
    if not _pregnancy_is_relevant(case) or not _unknown(case.imaging_safety, "pregnancy"):
        return []
    return [
        MissingQuestion(
            field="imaging_safety.pregnancy",
            question="Une grossesse est-elle possible ou en cours ?",
            importance="high",
            reason="Safety information for an examination using ionizing radiation.",
            required_to_choose=True,
        )
    ]
