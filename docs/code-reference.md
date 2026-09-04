# Référence du code

Inventaire généré à partir de l’AST de la v0, puis annoté. Les fonctions privées (`_...`) sont documentées car elles participent au comportement du POC.

## `bulkinout.cli`

Source : `src/bulkinout/cli.py`

### `_dump(path: Path, payload)`

Sérialise une charge Python en JSON UTF-8 indenté et crée le dossier parent. Ligne source : 20.

### `cmd_core_structure(args)`

Commande CLI qui exécute uniquement le Core et écrit ses deux sorties JSON. Ligne source : 25.

### `_write_answer_template(output_dir: Path, decision)`

Écrit les questions discriminantes requises dans `answers.template.json`. Ligne source : 35.

### `cmd_request_run(args)`

Orchestre la chaîne Core + Request et écrit toutes les sorties de la demande. Ligne source : 51.

### `cmd_request_golden(args)`

Exécute les golden cases et termine avec un code non nul si un cas échoue. Ligne source : 151.

### `cmd_request_catalog(args)`

Affiche le catalogue synthétique des scénarios. Ligne source : 169.

### `main()`

Construit le parseur argparse et distribue les sous-commandes. Ligne source : 181.

## `bulkinout.core.extraction.llm`

Source : `src/bulkinout/core/extraction/llm.py`

### `_schema_format(model: Type[T]) -> dict`

Construit la configuration `json_schema` utilisée pour la sortie structurée. Ligne source : 64.

### `_extract_json(response) -> str`

Récupère le texte JSON d’une réponse SDK, avec fallback sur les contenus de sortie. Ligne source : 72.

### `OpenAICoreExtractor`

Classe de service ; ses méthodes sont documentées ci-dessous. Ligne source : 82.

### `OpenAICoreExtractor.__init__(self, model: str | None = None)`

Initialise le client OpenAI et résout le modèle configuré. Ligne source : 83.

### `OpenAICoreExtractor._call_structured(self, prompt: str, content: list[dict], model_cls: Type[T]) -> T`

Appelle Responses API avec un schéma Pydantic strict puis valide la réponse. Ligne source : 89.

### `OpenAICoreExtractor._upload_or_inline(self, path: Path) -> dict`

Encode les images en data URL et téléverse les autres fichiers comme `input_file`. Ligne source : 101.

### `OpenAICoreExtractor.extract(self, paths: list[Path]) -> LLMExtraction`

Construit l’entrée multimodale de tous les fichiers et renvoie `LLMExtraction`. Ligne source : 114.

### `extraction_to_case(extraction: LLMExtraction) -> ClinicalCase`

Convertit `LLMExtraction` en `ClinicalCase` avec provenance et antériorités. Ligne source : 128.

## `bulkinout.core.ingestion.files`

Source : `src/bulkinout/core/ingestion/files.py`

### `collect_files(input_dir: Path) -> list[Path]`

Collecte récursivement les fichiers dont l’extension appartient à `SUPPORTED`. Ligne source : 6.

## `bulkinout.core.models.case`

Source : `src/bulkinout/core/models/case.py`

### `FieldStatus`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 8.

### `SourceRef`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 15.

### `ClinicalField`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 22.

### `PriorImaging`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 30.

### `ClinicalCase`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 38.

### `ArtifactRef`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 50.

### `WorkflowState`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 57.

### `RadiologyCase`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 62.

### `MissingQuestion`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 81.

### `CandidateExam`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 90.

### `DiscriminatingQuestion`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 103.

### `ImagingRecommendation`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 114.

### `ImagingDecision`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 134.

### `TeleradiologyRequest`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 154.

### `LLMSource`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 174.

### `LLMFact`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 180.

### `LLMExtraction`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 188.

### `AnswerItem`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 195.

### `AnswerFile`

Modèle Pydantic/Enum décrit dans [`data-model.md`](data-model.md). Ligne source : 202.

## `bulkinout.core.service`

Source : `src/bulkinout/core/service.py`

### `build_radiology_case(input_dir: Path, model: str | None = None)`

Construit un `RadiologyCase` à partir d’un dossier de documents via l’extracteur Core. Ligne source : 9.

## `bulkinout.request.answers`

Source : `src/bulkinout/request/answers.py`

### `load_answers(path: Path) -> AnswerFile`

Charge un fichier de réponses et accepte une forme dictionnaire ou liste. Ligne source : 20.

### `apply_answers(case: ClinicalCase, answer_file: AnswerFile, filename: str) -> ClinicalCase`

Injecte les réponses dans le `ClinicalCase` comme faits observés sourcés. Ligne source : 31.

## `bulkinout.request.decision_guard`

Source : `src/bulkinout/request/decision_guard.py`

### `_get_case_value(case: ClinicalCase, field_path: str)`

Lit un champ `section.champ` et indique s’il est inconnu/conflictuel. Ligne source : 6.

### `enforce_decision_guard(case: ClinicalCase, decision: ImagingDecision) -> ImagingDecision`

Bloque une sélection si une question discriminante obligatoire reste sans réponse. Ligne source : 19.

## `bulkinout.request.decision_llm`

Source : `src/bulkinout/request/decision_llm.py`

### `_schema_format(model: Type[T]) -> dict`

Construit le format de sortie structurée pour `ImagingDecision`. Ligne source : 35.

### `_extract_json(response) -> str`

Extrait le JSON textuel de la réponse du moteur de décision. Ligne source : 43.

### `OpenAIRequestDecision`

Classe de service ; ses méthodes sont documentées ci-dessous. Ligne source : 53.

### `OpenAIRequestDecision.__init__(self, model: str | None = None)`

Initialise le client OpenAI et le modèle de décision. Ligne source : 54.

### `OpenAIRequestDecision.decide(self, case: ClinicalCase, missing_questions: list[dict], reference_context: dict | None = None) -> ImagingDecision`

Envoie cas, questions et référentiel au LLM et valide un `ImagingDecision`. Ligne source : 60.

## `bulkinout.request.golden`

Source : `src/bulkinout/request/golden.py`

### `_observed(value)`

Crée un `ClinicalField` observé de confiance 1 pour les tests. Ligne source : 10.

### `case_from_facts(facts: dict[str, Any]) -> ClinicalCase`

Transforme les faits YAML `section.champ` en `ClinicalCase`. Ligne source : 13.

### `GoldenResult`

Dataclass contenant le résultat d’un golden case. Ligne source : 25.

### `run_golden_case(path: Path, reference_dir: Path) -> GoldenResult`

Exécute un cas golden contre le `ReferenceEngine` et retourne les écarts. Ligne source : 33.

### `discover_golden_cases(case_dir: Path) -> list[Path]`

Découvre récursivement les fichiers YAML de golden cases. Ligne source : 89.

## `bulkinout.request.reference_catalog`

Source : `src/bulkinout/request/reference_catalog.py`

### `build_catalog(reference_dir: Path) -> list[dict]`

Produit les métadonnées synthétiques de tous les scénarios YAML. Ligne source : 5.

## `bulkinout.request.reference_engine`

Source : `src/bulkinout/request/reference_engine.py`

### `ScenarioMatch`

Dataclass représentant un scénario apparié et son score. Ligne source : 12.

### `_raw(case: ClinicalCase, field: str)`

Lit un `ClinicalField` connu à partir d’un chemin `section.champ`. Ligne source : 20.

### `_predicate(case: ClinicalCase, pred: dict) -> bool`

Évalue un prédicat YAML sur une valeur clinique connue. Ligne source : 33.

### `_condition(case: ClinicalCase, node: dict) -> bool`

Évalue un groupe `all` ou `any` de prédicats. Ligne source : 53.

### `_candidate_applicable(case: ClinicalCase, candidate: dict) -> bool`

Évalue la clause optionnelle `when` d’un candidat. Ligne source : 61.

### `ReferenceEngine`

Classe de service ; ses méthodes sont documentées ci-dessous. Ligne source : 68.

### `ReferenceEngine.__init__(self, reference_dir: Path)`

Charge tous les scénarios YAML du dossier de référence. Ligne source : 69.

### `ReferenceEngine.match(self, case: ClinicalCase) -> list[ScenarioMatch]`

Retourne les scénarios dont les critères d’entrée sont satisfaits, triés par score. Ligne source : 77.

### `ReferenceEngine.unresolved_material_questions(self, case: ClinicalCase, scenario: dict) -> list[dict]`

Retourne les questions matérielles dont le champ est encore inconnu. Ligne source : 101.

### `ReferenceEngine.evaluate_rules(self, case: ClinicalCase, scenario: dict) -> list[dict]`

Évalue les règles conditionnelles d’un scénario. Ligne source : 109.

### `ReferenceEngine.build_context(self, case: ClinicalCase, max_scenarios: int = 3) -> dict`

Construit le contexte envoyé au moteur de décision : scénarios, candidats filtrés, questions, règles. Ligne source : 119.

## `bulkinout.request.request_builder`

Source : `src/bulkinout/request/request_builder.py`

### `_clean_value(section, key)`

Retourne uniquement la valeur d’un champ connu et non conflictuel. Ligne source : 6.

### `_fmt(label, value)`

Formate `label: value`; helper actuellement non utilisé par le builder. Ligne source : 13.

### `build_teleradiology_request(case: ClinicalCase, decision: ImagingDecision, questions: list[MissingQuestion]) -> TeleradiologyRequest`

Assemble le brouillon de demande à partir du cas, de la décision et des questions. Ligne source : 17.

## `bulkinout.request.rules`

Source : `src/bulkinout/request/rules.py`

### `_unknown(section: dict, key: str) -> bool`

Teste l’absence, l’inconnu ou le conflit d’un champ clinique. Ligne source : 6.

### `generic_missing_questions(case: ClinicalCase) -> list[MissingQuestion]`

Génère les contrôles génériques d’indication et de symptômes. Ligne source : 11.

### `recommendation_specific_questions(case: ClinicalCase, decision) -> list[MissingQuestion]`

Ajoute les contrôles de sécurité/complétude spécifiques à la modalité proposée. Ligne source : 39.
