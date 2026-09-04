# Tests end-to-end

Ces dossiers synthétiques testent la chaîne complète **documents → Core → Request** avec un appel réel au LLM.
Ils ne sont pas lancés par `pytest` : la v0 les utilise pour une revue manuelle et reproductible.

## Cas inclus

| Cas | Intention de test |
|---|---|
| `case_001_rlq_complete` | Dossier complet : une proposition d'imagerie doit pouvoir être préparée sans rappel clinique. |
| `case_002_right_sided_pain_ambiguous` | Dossier ambigu : BULKINOUT doit demander les informations discriminantes au lieu de forcer un examen. |
| `case_003_suspected_pe_conflicting_allergy` | Données dispersées et contradiction sur une réaction iodée antérieure. |

Chaque dossier contient un `expected.json`. Ce fichier est un oracle de test et n'est pas ingéré par le Core : `collect_files()` ne collecte que PDF, TXT, Markdown et images prises en charge.

## Exécuter un cas

```bash
bulkinout request run   --input tests/e2e/case_001_rlq_complete   --output output_e2e/case_001
```

Comparer ensuite `output_e2e/case_001/` au fichier `expected.json` du cas et consigner la revue dans `review/radiologist_review_template.csv`.

Pour le cas 002, `answers_after_call.example.json` montre le format d'un second passage après clarification :

```bash
bulkinout request run   --input tests/e2e/case_002_right_sided_pain_ambiguous   --answers tests/e2e/case_002_right_sided_pain_ambiguous/answers_after_call.example.json   --output output_e2e/case_002_after_answers
```
