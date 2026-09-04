# CLI

Le point d'entrée est défini par `bulkinout = "bulkinout.cli:main"` dans `pyproject.toml`.

## `bulkinout core structure`

Arguments : `--input`, `--output`, `--model`. Requiert `OPENAI_API_KEY` et un modèle via `--model` ou `BULKINOUT_MODEL`. Produit `radiology_case.json` et `llm_extraction.json`.

## `bulkinout request run`

Arguments : `--input`, `--output`, `--answers`, `--reference`, `--model`. Requiert les mêmes paramètres LLM. Produit `radiology_case.json`, `llm_extraction.json`, `case.json`, `reference_context.json`, `missing_questions.json`, `imaging_decision.json`, `teleradiology_request.json` et `answers.template.json`.

## `bulkinout request catalog`

Liste les scénarios YAML, leurs versions, nombres de candidats/questions et statut. Aucun appel LLM.

## `bulkinout request golden`

Exécute les golden cases YAML. Aucun appel LLM.

## `bulkinout report`

Affiche seulement que le workflow Report est réservé à une étape ultérieure. Aucun traitement post-examen n'est effectué dans la v0.
