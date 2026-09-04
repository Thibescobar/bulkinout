# Tests

## Pytest

```bash
pytest -q
```

La suite couvre les modèles, l'ingestion, l'extraction avec clients simulés, les règles, la garde de décision, le moteur de référentiel, le catalogue, la CLI et les golden cases. `pytest-cov` mesure automatiquement `bulkinout` et impose un minimum de 95 %.

Vérifier également le lint avant chaque contribution :

```bash
ruff check src tests
```

## Golden cases

`tests/golden/*.yaml` teste le référentiel sans LLM. `case_from_facts()` transforme un dictionnaire `section.champ → valeur` en `ClinicalCase`; `run_golden_case()` compare ensuite scénario, règles, questions et résultats attendus. Ces tests sont rapides et déterministes.

```bash
bulkinout request golden --cases tests/golden --reference reference/scenarios
```

## End-to-end

`tests/e2e/` contient trois dossiers synthétiques multi-documents. Ils appellent réellement le Core/LLM puis Request et ne font pas partie du `pytest` par défaut. Chaque cas possède un `expected.json` pour la comparaison manuelle.

La revue peut être consignée dans `review/radiologist_review_template.csv` avec les catégories d'erreur définies dans `review/README.md`.

## Transformer une erreur en test

Lorsqu'une revue manuelle identifie une erreur de référentiel, créer ou modifier un golden case avant de changer la règle. Lorsqu'elle identifie une erreur d'extraction, conserver le cas E2E et son `expected.json` pour mesurer les versions ultérieures du Core.
