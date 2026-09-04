# BULKINOUT

![python](https://img.shields.io/badge/python-%E2%89%A53.11-blue)
[![license](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE.md)
[![CI](https://img.shields.io/github/actions/workflow/status/Thibescobar/bulkinout/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white)](https://github.com/Thibescobar/bulkinout/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-47%20passed-brightgreen)
![coverage](https://img.shields.io/badge/coverage-96%25-brightgreen)
![linting](https://img.shields.io/badge/linting-ruff-7f54b3)

**Bulk in. Intelligence out.** BULKINOUT transforme des documents cliniques hétérogènes en un dossier radiologique structuré, puis utilise un référentiel radiologique et un LLM pour préparer une proposition d'imagerie et un bon de téléradiologie.

> **v0 = POC de décision assistée.** Le référentiel est marqué `needs_local_validation` et toute prescription/transmission reste soumise à validation humaine.

## Ce qui fonctionne dans la v0

```text
PDF / TXT / images
        ↓
BULKINOUT Core
        ↓
RadiologyCase structuré + provenance
        ↓
BULKINOUT Request
        ↓
scénarios + questions discriminantes
        ↓
proposition / abstention / clarification
        ↓
brouillon de demande de téléradiologie
```

`Report` (workflow post-examen) est réservé pour une version ultérieure.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # ou exportez les variables manuellement
export OPENAI_API_KEY="..."
export BULKINOUT_MODEL="<modele-compatible>"
```

Le modèle n'est volontairement pas figé dans la v0 : utilisez `BULKINOUT_MODEL` ou `--model`.

## Utilisation

Structurer les documents sans exécuter le workflow Request :

```bash
bulkinout core structure --input input --output output_core
```

Exécuter le workflow pré-examen complet :

```bash
bulkinout request run   --input input   --output output   --reference reference/scenarios
```

Si une clarification est nécessaire, compléter le `answers.template.json` produit puis relancer :

```bash
bulkinout request run   --input input   --answers answers.json   --output output_after_answers
```

Inspecter le référentiel ou lancer les tests métier déterministes :

```bash
bulkinout request catalog
bulkinout request golden
pytest -q
```

## Sorties principales

| Fichier | Rôle |
|---|---|
| `radiology_case.json` | Objet longitudinal principal. |
| `case.json` | Contexte clinique structuré extrait des documents. |
| `reference_context.json` | Scénarios, candidats, questions et règles issus du référentiel. |
| `imaging_decision.json` | Décision assistée, candidats, justification et statut de clarification. |
| `teleradiology_request.json` | Brouillon destiné à la validation humaine. |
| `answers.template.json` | Questions discriminantes à compléter si nécessaire. |

## Tests fournis

- `tests/golden/` : tests rapides du référentiel, **sans LLM**.
- `tests/e2e/` : 3 dossiers patients synthétiques réalistes pour tester manuellement la chaîne complète.
- `review/` : grille de revue radiologue.

## Documentation

Commencer par **[`docs/README.md`](docs/README.md)**. Elle décrit l'architecture, le modèle de données, le Core, Request, le référentiel, les tests et chaque fonction/module de la v0.

## Limites connues

La normalisation terminologique avancée, la réconciliation dédiée, la timeline clinique et le workflow `Report` sont encore des emplacements architecturaux. Le Core actuel s'appuie principalement sur l'extraction structurée du LLM et sur la provenance fournie par les documents. Le référentiel v0 doit être revu et validé localement avant tout usage clinique réel.
