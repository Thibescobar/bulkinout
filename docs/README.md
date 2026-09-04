# Documentation BULKINOUT v0

Cette documentation décrit **le code réellement présent dans la v0**. Les composants non implémentés sont explicitement indiqués comme tels.

1. [Architecture](architecture.md) — responsabilités de Core, Request et Report.
2. [Modèle de données](data-model.md) — `RadiologyCase`, `ClinicalCase`, décisions et provenance.
3. [BULKINOUT Core](core.md) — ingestion, extraction LLM et construction du cas.
4. [BULKINOUT Request](request.md) — référentiel, décision, garde-fous et demande finale.
5. [Référentiel](reference.md) — format YAML et fonctionnement du moteur.
6. [Tests](testing.md) — pytest, golden cases et E2E synthétiques.
7. [CLI](cli.md) — commandes et fichiers produits.
8. [Référence du code](code-reference.md) — modules, classes, méthodes et fonctions de la v0.

## Frontières de la v0

`core/normalization/`, `core/reconciliation/`, `core/timeline/`, `core/audit/` et `report/` existent pour stabiliser l'architecture, mais ne contiennent pas encore de logique métier substantielle. L'audit actuellement utilisé est la liste `RadiologyCase.audit`, alimentée par `core.service` et la CLI Request.
