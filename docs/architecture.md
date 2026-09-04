# Architecture

## Vue d'ensemble

```text
                     BULKINOUT
                        │
                 ┌──────┴──────┐
                 │             │
               Core         Workflows
                 │        ┌────┴────┐
                 │      Request   Report
                 │        v0      standby
                 ↓
           RadiologyCase
```

### Core

Le Core ne décide pas quel examen prescrire. Il collecte les fichiers supportés, les envoie à un extracteur LLM à sortie structurée, convertit cette extraction en `ClinicalCase`, puis construit un `RadiologyCase` avec la liste des artefacts et un premier événement d'audit.

### Request

Request consomme `RadiologyCase.clinical`. Il ajoute les contrôles génériques, construit un contexte à partir des scénarios YAML, demande au LLM de comparer les candidats, applique un garde déterministe aux questions discriminantes et ajoute des contrôles de sécurité dépendant de la modalité. Il construit enfin `TeleradiologyRequest` et stocke les sorties dans `RadiologyCase.referral`.

### Report

`bulkinout/report/` est volontairement en standby. Aucun traitement post-examen, résultat de computer vision, dictée ou génération de compte rendu n'est implémenté dans la v0.

## Dépendances entre couches

`core` ne dépend pas de `request`. `request` importe les modèles de `core`. Cette direction de dépendance est volontaire : le même `RadiologyCase` pourra plus tard être consommé par `report` sans dépendre de la logique de pertinence pré-examen.
