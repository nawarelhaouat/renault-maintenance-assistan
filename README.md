# Assistant de maintenance industrielle multimodal

![CI](https://github.com/nawarelhaouat/renault-maintenance-assistant/actions/workflows/ci.yml/badge.svg)

Assistant intelligent **hors ligne** pour opérateurs et techniciens de maintenance : on photographie une machine, le système l'identifie, affiche sa fiche et son historique, répond en **français ou en darija** à partir des manuels techniques (avec le fichier et la page cités) et estime le risque de panne à 30 jours.

Projet réalisé dans le cadre d'un stage de fin d'année à Renault Group Tanger (ENSA Tanger).

> **Données synthétiques.** Les manuels, la GMAO et les photographies de plaques de ce dépôt sont générés par des scripts. Aucun document ni aucune donnée de l'entreprise n'est inclus. Les résultats ci-dessous valident la chaîne de traitement, pas une performance industrielle.

![Assistant](docs/img/assistant.PNG)
![Dashboard](docs/img/dash1.PNG)
![         ](docs/img/dash2.PNG)
![         ](docs/img/dash3.PNG)
![         ](docs/img/dash4.PNG)

## Fonctionnalités

- **Questions-réponses sur les manuels** (français, darija en alphabet arabe ou latin), avec citation du fichier et de la page.
- **Identification d'une machine par photo** : QR code, lecture de la plaque signalétique (OCR), puis classification visuelle du type de machine en dernier recours. Une lecture incertaine demande toujours une confirmation.
- **Fiche et historique GMAO** : nombre d'interventions, dernières interventions, pannes fréquentes, pièces, stock et coûts, lus dans la base et jamais déduits par le modèle de langage.
- **Diagnostic de panne** : dernière panne d'une machine ou code d'erreur donné, procédure du manuel et pièces concernées.
- **Risque de panne à 30 jours** par machine, avec les facteurs qui l'expliquent, et **tableau de bord** du parc.
- **Authentification, rôles et historique des conversations** par utilisateur.
- **Web (React) et mobile (Flutter)** sur la même API.
- **Exécution entièrement locale** : modèles de langage via Ollama, aucune donnée envoyée à un service externe.

## Architecture

```mermaid
flowchart LR
    W["Web (React)"] --> API
    M["Mobile (Flutter)"] --> API
    API["API FastAPI<br/>JWT, rôles"] --> R{"Routeur<br/>déterministe"}
    R -->|"comptage, historique,<br/>pannes fréquentes"| DB[("PostgreSQL<br/>GMAO, utilisateurs,<br/>conversations")]
    R -->|"procédure, symptôme"| RAG["Recherche documentaire<br/>BGE-M3 + BM25 + reclassement"]
    RAG --> Q[("Qdrant")]
    RAG --> PDF["Manuels PDF"]
    RAG -.->|"manuel non structuré"| LLM["Ollama<br/>qwen2.5"]
    R -->|"risque de panne"| ML["XGBoost"]
    API --> V["Vision<br/>QR, OCR, CLIP"]
```

### Principes de fiabilité

Un premier agent à base de modèle de langage (7 milliards de paramètres, local) comptait mal, recopiait de mauvais arguments et inventait des étapes et des numéros de page. L'architecture a donc été renversée : **le modèle de langage n'intervient que là où il est indispensable**.

- **Routage déterministe** : les comptages, l'historique, les pannes fréquentes, le diagnostic et le risque sont traités par du code, sans modèle de langage.
- **Extraction directe** : lorsque le manuel est structuré en sections « Code Exxx », les étapes sont lues dans le PDF au lieu d'être réécrites.
- **Réponses ancrées** : sinon, le modèle recopie les étapes mot pour mot et toute étape dont les termes ne figurent pas dans les extraits est retirée.
- **Citations calculées** : la page citée vient du code, jamais du modèle.
- **Refus explicite** lorsque le meilleur passage reclassé est sous un seuil de pertinence.
- **Darija en entrée seulement** : la question est reformulée en français technique (glossaire de maintenance) ; les réponses restent en français.

## Stack technique

| Domaine | Technologies |
|---|---|
| Modèles de langage | Ollama, Qwen2.5 7B |
| Recherche | BGE-M3 (plongements), Qdrant, BM25, Reciprocal Rank Fusion, BGE-Reranker-v2-M3 |
| Vision | OpenCV (QR code), EasyOCR, CLIP |
| Prédiction | XGBoost, validation temporelle, suivi MLflow |
| Backend | FastAPI, PostgreSQL, JWT, scrypt |
| Interfaces | React (Vite), Flutter, Streamlit (développement seulement) |
| Déploiement | Docker Compose, NGINX, GitHub Actions, pytest, ruff |

## Démarrage rapide avec Docker

Prérequis : Docker et Docker Compose, 16 Go de mémoire recommandés, environ 15 Go d'espace disque pour les modèles.

**1. Configuration**

```bash
cp .env.example .env          # PowerShell : Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Colle la valeur obtenue dans `.env` après `JWT_SECRET=`.

**2. Démarrage**

```bash
docker compose up -d --build
docker compose logs -f ollama-pull
```

Le premier démarrage télécharge le modèle.

```bash
docker compose exec ollama ollama pull qwen2.5:7b
```

**3. Données et modèles** (une seule fois)

```bash
docker compose run --rm api python db/seed.py
docker compose run --rm api python db/simulate_history.py
docker compose run --rm api python data/generate_manuals.py
docker compose run --rm api python data/generate_plates.py
docker compose run --rm api python -m app.rag.ingest
docker compose run --rm api python ml/train.py
```

Le suivi MLflow n'est pas conservé en conteneur ; lance `ml/train.py` en local pour garder l'historique des entraînements.

**4. Premier compte administrateur**

```bash
docker compose run --rm api python db/create_user.py admin admin "Administrateur"
```

**5. Accès**

| Service | Adresse |
|---|---|
| Application web | http://localhost:8080 |
| API et documentation interactive | http://localhost:8000/docs |
| État des dépendances | http://localhost:8000/ready |

## Développement local

```bash
python -m venv .venv
source .venv/bin/activate     # PowerShell : .venv\Scripts\Activate.ps1
pip install -r requirements.txt

docker compose up -d db qdrant
ollama pull qwen2.5:7b && ollama pull qwen2.5:3b

python db/seed.py && python db/simulate_history.py
python data/generate_manuals.py && python data/generate_plates.py
python -m app.rag.ingest      # depuis le dossier backend : cd backend
python ml/train.py
python db/create_user.py admin admin "Administrateur"

uvicorn app.api:app --app-dir backend --port 8000 --env-file .env
```

Dans un autre terminal (Node.js 20.19 ou plus récent) :

```bash
cd web
npm install
npm run dev                   # http://localhost:5173
```

### Variables d'environnement

| Variable | Rôle | Défaut |
|---|---|---|
| `JWT_SECRET` | Clé de signature des sessions (obligatoire en Docker) | clé temporaire en local |
| `JWT_HOURS` | Durée de validité d'un jeton | 12 |
| `DATABASE_URL` | Connexion PostgreSQL | `postgresql://gmao:gmao@localhost:5432/gmao` |
| `QDRANT_URL` | Adresse de Qdrant | `http://localhost:6333` |
| `OLLAMA_HOST` | Adresse d'Ollama | `http://localhost:11434` |
| `CORS_ORIGINS` | Origines autorisées, séparées par des virgules | `http://localhost:5173` |
| `WARMUP` | `1` précharge les modèles au démarrage de l'API | désactivé |

## Comptes et rôles

Il n'y a pas d'inscription ouverte : les comptes sont créés par un administrateur (`db/create_user.py` ou `POST /admin/users`).

| Rôle | Assistant et historique personnel | Tableau de bord | Création de comptes |
|---|---|---|---|
| `operator` (opérateur) | oui | non | non |
| `technician` (technicien) | oui | oui | non |
| `manager` (responsable) | oui | oui | non |
| `admin` (administrateur) | oui | oui | oui |

Les droits sont vérifiés côté serveur. Après 5 échecs de connexion consécutifs sur un identifiant, la connexion est bloquée 5 minutes.

## Utiliser vos propres documents

1. Déposez les PDF dans `data/manuals/`, nommés comme la colonne `manual_file` de la table `machine_models`.
2. Relancez l'indexation : `python -m app.rag.ingest`.
3. Les manuels organisés en sections `Code Exxx : titre, Symptôme : …, Étape 1. …` bénéficient de l'extraction directe ; les autres passent par la génération ancrée, plus lente.
4. **Recalibrez** le seuil de refus (`MIN_RERANK_SCORE` dans `backend/app/config.py`, valeur actuelle `-4.0`) avec `eval/debug_query.py`, et faites relire le glossaire du darija (`backend/app/nlp/language.py`) par des techniciens.
5. Les PDF numérisés (sans texte) ne sont pas encore pris en charge : l'indexation les signale.

Ne publiez jamais de documents réels de l'entreprise : `data/manuals/*.pdf` et `data/private/` sont ignorés par `.gitignore`.

## Évaluation et résultats

Tous les résultats viennent de scripts du dépôt, sur des données synthétiques.

**Recherche documentaire** (`python eval/retrieval_eval.py`, 25 questions, recherche sur les 7 manuels sans filtre) :

| Mode | Français | Références exactes | Reformulations | Darija | MRR |
|---|---|---|---|---|---|
| Sémantique seule | 8/8 | 4/5 | 3/6 | 5/6 | 0,84 |
| Hybride | 8/8 | 5/5 | 3/6 | 4/6 | 0,88 |
| Hybride + reclassement | 8/8 | 5/5 | 5/6 | 6/6 | **0,97** |

Réponse correcte en première position. Avec 5 à 8 questions par groupe, les écarts sont des tendances.

**Bout en bout** (`python eval/e2e_eval.py`) : **16/16** cas réussis, dont 3 refus (questions hors manuel). Sur un poste sans carte graphique : médiane 52,3 s, 90e centile 110,3 s, maximum 177,8 s (le maximum inclut le chargement des modèles). Les réponses issues de la base sont immédiates, la prédiction prend moins d'une seconde et un refus 5 à 6 s ; les procédures générées et les questions en darija sont les plus lentes.

**Identification par image** (`python eval/vision_eval.py`, 120 photographies de plaques dégradées) : 60/60 avec QR code (médiane 0,1 s) et 60/60 sans QR code par lecture de la plaque (médiane 5,5 s), aucune erreur silencieuse. Les plaques synthétiques sont nettes : ce résultat est une borne supérieure.

**Risque de panne à 30 jours** (`python ml/train.py`, validation temporelle) :

| Métrique | Modèle | Référence |
|---|---|---|
| AUC | 0,600 | 0,513 (règle : retard de préventive) |
| Score de Brier | 0,1596 | 0,1559 (prédiction constante) |
| Pannes parmi les 10 % de machines les mieux classées | 25,5 % | 19,3 % (fréquence moyenne) |

Le gain de classement est modeste et les probabilités ne sont pas calibrées : la sortie doit être lue comme un **indice de risque relatif**, pas comme une probabilité exacte.

## API

La documentation interactive est sur `/docs`. Pour tester les routes protégées : `POST /auth/login`, copier `access_token`, puis **Authorize** (sans le mot « Bearer »).

| Fonction | Points d'accès |
|---|---|
| Authentification | `POST /auth/login`, `GET /auth/me`, `POST /admin/users` |
| Machines et image | `GET /machines`, `GET /machines/{étiquette}`, `POST /identify` |
| Assistant | `POST /chat`, `GET /risk/{étiquette}` |
| Historique | `GET /conversations`, `GET`, `PATCH`, `DELETE /conversations/{id}` |
| Tableau de bord | `GET /dashboard/summary`, `/fleet`, `/failures-monthly`, `/machines/{étiquette}` |
| Supervision | `GET /health`, `GET /ready` |

## Structure du dépôt

```text
renault-maintenance-assistant/
├── backend/app/
│   ├── api.py, auth.py, history.py, dashboard.py, db.py, config.py
│   ├── agents/graph.py          # routeur déterministe et agent restreint
│   ├── tools/                   # SQL, diagnostic, extraction, recherche manuels
│   ├── rag/                     # indexation et recherche hybride
│   ├── vision/identify.py       # QR, OCR, CLIP
│   ├── nlp/language.py          # détection de langue, reformulation du darija
│   └── ml/                      # variables et prédiction du risque
├── db/                          # schémas SQL, simulateur, création de comptes
├── data/                        # générateurs de manuels et de plaques
├── ml/train.py                  # entraînement du modèle de risque
├── eval/                        # évaluations reproductibles
├── web/                         # interface React (Vite)
├── frontend/                    # interface Streamlit de développement
├── mobile                       # application mobile
├── tests/                       # tests unitaires
├── docker-compose.yml, Dockerfile, requirements*.txt
└── .github/workflows/ci.yml
```

## Tests et qualité

```bash
pytest -q          # tests unitaires, sans base ni modèle de langage
ruff check .       # analyse statique
```

Les tests couvrent la détection de langue, l'ancrage des réponses et l'extraction de sections, l'absence de fuite d'information dans les variables du modèle prédictif, l'authentification et la protection des routes. L'intégration continue exécute `ruff`, `pytest` puis la construction de l'image Docker à chaque modification.

## Sécurité

- Mots de passe hachés avec scrypt et un sel aléatoire ; jetons JWT signés (HS256) à durée limitée ; droits relus en base à chaque requête, donc un compte désactivé perd immédiatement l'accès.
- Les photographies envoyées pour l'identification ne sont pas conservées.
- Chaque utilisateur n'accède qu'à ses propres conversations.
- Streamlit (`frontend/`) n'a pas d'authentification : à utiliser uniquement en local.

**Avant une mise en production** : HTTPS, jeton dans un cookie `HttpOnly` plutôt que dans le navigateur, ne publier que le port du serveur web (le fichier Compose publie aussi la base, Qdrant et l'API pour le développement), désactiver la documentation interactive, audit de sécurité.

## Limites connues

- Données synthétiques, régulières et de petite taille : les performances réelles seront plus faibles.
- Latence élevée sur un poste sans carte graphique pour les réponses générées ; l'exécution sur GPU est la solution de fond.
- Le darija est compris par reformulation, les réponses restent en français ; la qualité dépend du glossaire.
- La vérification d'ancrage est lexicale : elle détecte les étapes inventées, pas toutes les erreurs de sens.
- Le modèle de risque n'apporte qu'un gain modeste et ses probabilités ne sont pas calibrées.
- Les PDF numérisés ne sont pas pris en charge.

## Pistes d'amélioration

- Valider sur de vrais manuels et un vrai historique, puis recalibrer le seuil de refus et le glossaire.
- Reconnaissance de caractères pour les documents numérisés.
- Connexion en lecture seule à la GMAO de production.
- Retour d'utilisateur sur chaque réponse pour une amélioration continue.
- Calibration des probabilités du modèle de risque.
- QR code apposé sur chaque machine pour fiabiliser l'identification.

## Auteur

**Nawar El Haouat**, élève ingénieur en Génie Informatique (Data & AI), ENSA Tanger.
[LinkedIn](https://www.linkedin.com/in/nawarelhaouat/)
