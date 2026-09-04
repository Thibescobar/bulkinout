# Référentiel Request

Les scénarios sont des fichiers YAML dans `reference/scenarios/`. La v0 en contient 18, tous marqués `needs_local_validation`.

## Structure utilisée

```yaml
id: renal_colic
version: 0.1.0
title: Suspicion de colique néphrétique
status: needs_local_validation
sources: [...]
entry:
  any:
    - field: current_problem.location
      contains: flanc
questions: [...]
candidates: [...]
rules: [...]
```

## Matching

`ReferenceEngine.match()` évalue `entry.all` ou `entry.any`. Les prédicats supportés dans la v0 sont `equals`, `not_equals`, `contains` et `in`. Un champ `unknown` ou `conflicting` ne satisfait aucun prédicat.

## Questions matérielles

`unresolved_material_questions()` retourne uniquement les questions avec `material: true` dont le champ n'est pas connu. Leur ordre dépend de `priority`.

## Candidats

`build_context()` ne renvoie que les candidats dont la clause optionnelle `when:` est satisfaite. Sans clause `when:`, le candidat est inclus. Le même mini-langage `all`/`any` et les mêmes prédicats sont utilisés.

## Règles

`evaluate_rules()` applique les objets `rules[].if` et renvoie leur `result`. La v0 sait notamment encoder un candidat préféré ou `no_imaging_recommended` ; l'interprétation finale est envoyée au moteur Request via `reference_context`.

## Limite de chemin de champ

Le moteur de règles lit actuellement les dictionnaires de premier niveau de `ClinicalCase` sous la forme `section.champ`. Il ne navigue pas arbitrairement dans des listes ou objets imbriqués. Les scénarios v0 utilisent donc des champs questionnables/complétables dans ces sections pour leurs règles déterministes.
