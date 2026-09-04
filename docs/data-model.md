# Modèle de données

Les modèles Pydantic sont définis dans `src/bulkinout/core/models/case.py`.

## Provenance : `ClinicalField`

Une donnée clinique n'est pas stockée comme une valeur nue. Elle transporte :

- `value` : valeur extraite ;
- `status` : `observed`, `inferred`, `unknown` ou `conflicting` ;
- `sources` : liste de `SourceRef` (`filename`, page éventuelle, extrait) ;
- `confidence` : score entre 0 et 1 ;
- `validated` : booléen de validation humaine, `False` par défaut.

L'absence de mention ne vaut donc jamais automatiquement `False`.

## `ClinicalCase`

Le contexte clinique est réparti en dictionnaires de `ClinicalField` : `patient`, `current_problem`, `history`, `medications`, `allergies`, `labs`, `imaging_safety`, plus `prior_imaging` et `metadata`.

Les noms de champs internes sont extensibles : par exemple `current_problem.location` correspond à la clé `location` du dictionnaire `current_problem`.

## `RadiologyCase`

`RadiologyCase` est le conteneur longitudinal commun. Dans la v0, les zones principalement utilisées sont :

- `workflow` ;
- `clinical` ;
- `artifacts` ;
- `referral` ;
- `audit`.

Les zones `acquisition`, `ai_results`, `radiologist_observations`, `findings`, `impression` et `final_report` sont réservées au futur workflow post-examen.

## Décision Request

`ImagingDecision` contient : `decision_status`, `candidates`, `discriminating_questions`, `primary`, `secondary`, `clinician_call_required`, ses raisons et `decision_ready_for_human_approval`.

Les statuts possibles sont `selected`, `insufficient_information`, `no_imaging_recommended` et `safety_blocked`.

`TeleradiologyRequest.status` vaut `draft`, `ready_for_human_approval` ou `blocked`. Aucun de ces statuts ne signifie une prescription autonome : `validated_by_clinician` reste `False` tant qu'une validation externe n'est pas implémentée.
