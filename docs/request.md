# BULKINOUT Request

## Ordre d'exécution

`cmd_request_run()` réalise actuellement :

1. `build_radiology_case()` ;
2. application optionnelle d'un fichier de réponses ;
3. `generic_missing_questions()` ;
4. `ReferenceEngine.build_context()` ;
5. `OpenAIRequestDecision.decide()` ;
6. `enforce_decision_guard()` ;
7. `recommendation_specific_questions()` ;
8. blocage conservateur des questions de sécurité/complétude critiques ou hautes ;
9. `build_teleradiology_request()` ;
10. sérialisation des JSON de sortie.

## Questions génériques

`generic_missing_questions()` vérifie actuellement l'indication et, si nécessaire, les symptômes/signes motivant l'imagerie. Cette couche est volontairement courte : le référentiel porte les questions spécifiques aux scénarios.

## Décision LLM

`OpenAIRequestDecision.decide()` reçoit le cas structuré, les questions génériques non résolues et `reference_context`. Il doit comparer les candidats et produire un `ImagingDecision` strictement conforme au schéma Pydantic.

## Garde déterministe

`enforce_decision_guard()` empêche une décision `selected` lorsqu'une `DiscriminatingQuestion` marquée `required_to_choose=True` pointe encore vers un champ inconnu ou conflictuel. Dans ce cas, la décision devient `insufficient_information`, le candidat principal est marqué non recommandé et `clinician_call_required=True`.

## Contrôles dépendant de la modalité

`recommendation_specific_questions()` ajoute, selon la proposition : réaction iodée et fonction rénale pour CT injecté/conditionnel ; pacemaker et implant/métal pour IRM ; grossesse potentielle pour les modalités irradiantes selon les données patient disponibles.

Dans la v0, une question spécifique de niveau `critical` ou `high` non résolue empêche `decision_ready_for_human_approval` et entraîne un besoin de clarification. Les questions explicitement bloquantes de sécurité utilisent `safety_blocked`.

## Construction du bon

`build_teleradiology_request()` n'utilise pas les valeurs `unknown` ou `conflicting` comme faits fiables. Il rassemble le résumé patient, l'indication, l'examen/protocole proposés, les antécédents, allergies/traitements, biologie, sécurité, antériorités et questions non résolues.
