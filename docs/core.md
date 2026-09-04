# BULKINOUT Core

## Ingestion

`core.ingestion.files.collect_files(input_dir)` parcourt récursivement le dossier et conserve les extensions : `.pdf`, `.txt`, `.md`, `.png`, `.jpg`, `.jpeg`, `.webp`. Les JSON de test et autres fichiers sont donc ignorés.

## Extraction LLM

`OpenAICoreExtractor` utilise le SDK OpenAI. Le modèle doit être fourni par `--model` ou `BULKINOUT_MODEL`. Les TXT/Markdown sont injectés comme texte ; les images sont envoyées en `input_image` via data URL ; les autres fichiers supportés, notamment les PDF, sont téléversés comme `input_file`.

La réponse est contrainte par le schéma Pydantic `LLMExtraction`. Le prompt impose notamment : ne pas inventer une information absente, conserver la provenance, distinguer `observed` et `inferred`, détecter les contradictions et ne pas inférer la compatibilité IRM d'un dispositif.

## Conversion en cas clinique

`extraction_to_case()` mappe les faits dont le nom suit `section.champ` vers les dictionnaires de `ClinicalCase`. Les sections reconnues sont `patient`, `current_problem`, `history`, `medications`, `allergies`, `labs` et `imaging_safety`. Les antériorités structurées par le LLM sont converties en objets `PriorImaging`.

## Service Core

`build_radiology_case()` orchestre ingestion → extraction → conversion. Il retourne un tuple `(RadiologyCase, LLMExtraction, paths)`. Le `RadiologyCase` contient les artefacts d'entrée et un événement `core_structuring_completed` dans `audit`.

## Pas encore implémenté

Les packages `normalization`, `reconciliation` et `timeline` sont vides dans la v0. La réconciliation actuelle repose donc sur la sortie structurée du LLM, ses `contradictions`, la provenance des faits et le comportement des moteurs Request ; il n'existe pas encore de moteur déterministe dédié de fusion longitudinale.
