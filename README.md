# CariCue

**Teach. Check. Understand. Adapt.**

CariCue is a teacher-first formative-assessment tool. A teacher launches a
short check, students answer on their phones without accounts, and the teacher
gets participation, correctness, and confidence figures plus a place to record
what they will do next lesson.

It is not a gradebook and not a Moodle replacement. The whole product exists to
shorten the gap between *checking* understanding and *deciding* what to teach.

---

## Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Quick start with Docker](#quick-start-with-docker)
- [Local development without Docker](#local-development-without-docker)
- [Demonstration data](#demonstration-data)
- [Running the checks](#running-the-checks)
- [API reference](#api-reference)
- [Insights and AI suggestions](#insights-and-ai-suggestions)
- [Production deployment](#production-deployment)
- [HTTPS through a reverse proxy](#https-through-a-reverse-proxy)
- [Backup and restore](#backup-and-restore)
- [Privacy and security](#privacy-and-security)
- [MVP scope and extension points](#mvp-scope-and-extension-points)

---

## What it does

**Teacher (needs an account)**

1. Create a class and add students by hand or by CSV import.
2. Build an activity of one to five questions: multiple choice, short text, or
   a 1–5 confidence scale, with optional confidence collection per question.
3. Preview the student view, save as a draft, or launch immediately.
4. Project a QR code and a six-character code.
5. Watch results arrive on a dashboard that polls every few seconds.
6. Close the session and record the gap they saw and the action they will take.

**Student (needs nothing)**

1. Scan the QR code or type the code at `/join`.
2. Enter a display name or the roster identifier the teacher assigned.
3. Answer the questions on one screen.
4. Submit once and see a confirmation.

---

## Architecture

```
ClassSortie/
├── backend/                  Django 5.2 + DRF, PostgreSQL, Gunicorn
│   └── caricue/
│       ├── core/             health, config, permissions, throttles, errors
│       ├── accounts/         Teacher (email login), session auth endpoints
│       ├── classroom/        Classroom, Student, Enrollment, CSV import
│       ├── activities/       Activity, Question, Choice, launch rules
│       ├── live/             LiveSession, Participant, Response, Reflection
│       └── insights/         deterministic insight service + AI providers
├── frontend/                 React 18 + TypeScript + Vite + Chakra UI
│   └── src/
│       ├── api/              RTK Query client, CSRF handling, API types
│       ├── components/       layout, insight panels, question editor
│       ├── pages/            teacher screens + public student screens
│       └── utils/            insight formatting, activity-draft validation
├── deploy/
│   ├── nginx/caricue.conf    production reverse proxy + SPA fallback
│   ├── backup.sh             pg_dump helper
│   └── restore.sh            pg_restore helper
├── docker-compose.yml        development stack
├── docker-compose.prod.yml   production-oriented stack
└── .env.example              every environment variable, documented
```

Decisions worth knowing about:

- **Session cookies, not tokens.** Teachers authenticate with Django's
  server-side sessions and CSRF. That requires the SPA and the API to share an
  origin, which is why Vite proxies `/api` in development and Nginx does the
  same in production. No CORS configuration exists, by design.
- **Polling, not WebSockets.** A classroom check runs for a few minutes with a
  handful of devices. `GET /api/sessions/{id}/dashboard/` every few seconds
  survives flaky networks and simple proxies with no extra infrastructure. The
  server advertises the cadence via `poll_interval_seconds`.
- **Facts and suggestions are different types.** The dashboard payload carries
  `facts` (`kind: "fact"`, arithmetic over stored responses) and `suggestions`
  (`kind: "suggestion"`, advisory). The UI badges them differently and never
  mixes them.
- **The short code is not the credential.** Codes are for reading aloud;
  QR links and every subsequent request use an unguessable public token. Code
  lookup is rate limited.
- **A missing number is not zero.** When a figure cannot honestly be computed
  the API returns `null` and the UI prints `—`. "Nobody answered yet" and "0%
  correct" mean very different things to a teacher.

---

## Quick start with Docker

```bash
git clone <this repository> ClassSortie
cd ClassSortie
docker compose up --build
```

Then open:

| What | Where |
| --- | --- |
| Teacher app | <http://localhost:5173> |
| Student join page | <http://localhost:5173/join> |
| API health check | <http://localhost:8000/api/health/> |
| Django admin | <http://localhost:8000/django-admin/> |

The development stack runs PostgreSQL, Django with autoreload, and the Vite dev
server with hot reload. It seeds the demonstration data on first start
(`CARICUE_SEED_DEMO=1`); sign in with the credentials below.

**Testing on real phones.** QR codes are built from `PUBLIC_BASE_URL`, so
`localhost` only works on the machine running Docker. Set your LAN address
before starting:

```bash
PUBLIC_BASE_URL=http://192.168.1.20:5173 docker compose up --build
```

Useful commands:

```bash
docker compose logs -f api                       # follow API logs
docker compose exec api python manage.py migrate # apply migrations by hand
docker compose exec api python manage.py seed_demo --reset
docker compose exec api python manage.py createsuperuser
docker compose down                              # stop
docker compose down -v                           # stop and delete the database
```

---

## Local development without Docker

Requires Python 3.12 and Node 20+. PostgreSQL is the supported database;
SQLite is available as a zero-infrastructure escape hatch.

**Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements-dev.txt

# SQLite, no server needed:
$env:DJANGO_DEBUG="1"; $env:DJANGO_DB_ENGINE="sqlite"     # PowerShell
# export DJANGO_DEBUG=1 DJANGO_DB_ENGINE=sqlite           # bash

python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

**Frontend**

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api to localhost:8000
```

Point the proxy somewhere else with `VITE_API_PROXY_TARGET`.

---

## Demonstration data

```bash
python manage.py seed_demo            # idempotent
python manage.py seed_demo --reset    # delete and rebuild the demo teacher
```

It creates one teacher, one IT class with ten fictional students, a five-question
activity on hardware and networking, a **baseline closed** session with eight
submissions and a reflection, a **follow-up closed** session (linked via
`follow_up_of_session`) with improved scores for comparison demo, and one
**open** session for demonstrating the QR flow.

> **Development credentials** — for local use only.
>
> | | |
> | --- | --- |
> | Email | `teacher@caricue.demo` |
> | Password | `CariCueDemo2026` |
>
> Every student name and response is invented. Never enable `CARICUE_SEED_DEMO`
> on a real deployment.

The command prints both session codes and the open session's join URL when it
finishes.

---

## Running the checks

**Backend** (from `backend/`, with the virtualenv active)

```bash
python -m pytest                  # 232 tests
python -m ruff check .            # lint
python -m ruff format --check .   # formatting
```

Tests use `caricue.settings_test`: in-memory SQLite and fast password hashing.
No PostgreSQL server is required to run them.

**Frontend** (from `frontend/`)

```bash
npm test              # 82 tests (Vitest + React Testing Library)
npm run typecheck     # tsc --noEmit
npm run lint          # ESLint
npm run build         # production build (type-checks, then bundles)
npm run format:check  # Prettier
```

---

## API reference

Everything lives under `/api/`. Responses are JSON. Errors use one envelope:

```json
{ "detail": "Human-readable message.", "code": "machine_code", "errors": { "field": ["…"] } }
```

### Public — no account, throttled, validated

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health/` | Liveness plus a database check |
| `GET` | `/api/config/` | Client limits, poll cadence, whether AI is on |
| `GET` | `/api/public/sessions/lookup/?code=ABC123` | Short code → public token (30/min) |
| `GET` | `/api/public/sessions/{token}/` | The activity as a student sees it |
| `POST` | `/api/public/sessions/{token}/join/` | Join with a name or roster id (20/min) |
| `POST` | `/api/public/sessions/{token}/submit/` | Submit all answers, once (20/min) |

The public session payload deliberately omits `is_correct` and
`accepted_answers`: the answer key never reaches a student's device.

### Authentication

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/auth/csrf/` | Sets the CSRF cookie |
| `POST` | `/api/auth/register/` | Create a teacher account |
| `POST` | `/api/auth/login/` | Start a session (10/min) |
| `POST` | `/api/auth/logout/` | End the session |
| `GET` `PATCH` | `/api/auth/me/` | Read or update the current teacher |

### Teacher resources — session required, owner-scoped

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/overview/` | Dashboard: classes, activities, open sessions, recent results, pending follow-ups |
| `GET` `POST` | `/api/classrooms/` | List and create classes |
| `GET` `PATCH` `DELETE` | `/api/classrooms/{id}/` | Retrieve, edit, delete a class |
| `GET` | `/api/classrooms/{id}/roster/` | Enrolments for one class |
| `GET` | `/api/classrooms/{id}/topic-timeline/` | Closed sessions grouped by normalised topic |
| `POST` | `/api/classrooms/{id}/students/` | Add a student and enrol them |
| `POST` | `/api/classrooms/{id}/import-roster/` | CSV roster import (multipart) |
| `GET` | `/api/roster-template.csv` | Sample CSV to fill in |
| `GET` `POST` | `/api/students/` | Student CRUD across classes |
| `GET` `DELETE` | `/api/enrollments/{id}/` | Manage one enrolment |
| `GET` `POST` | `/api/activities/` | List and create activities (nested questions) |
| `GET` `PUT` `DELETE` | `/api/activities/{id}/` | Retrieve, replace, delete an activity |
| `GET` | `/api/activities/{id}/preview/` | The student view, for checking wording |
| `POST` | `/api/activities/{id}/launch/` | Publish and open a live session |
| `GET` | `/api/activities/{id}/sessions/` | Sessions launched from an activity |
| `GET` `POST` | `/api/questions/`, `/api/choices/` | Question and choice management |
| `GET` | `/api/sessions/?status=open` | List sessions, filterable |
| `POST` | `/api/sessions/{id}/close/` | Close a session; blocks further submissions |
| `GET` | `/api/sessions/{id}/dashboard/` | **Poll this**: facts, suggestions, misconception cards; comparison when closed |
| `GET` | `/api/sessions/{id}/results/` | Full results, participants, reflection, misconception cards, comparison |
| `GET` | `/api/sessions/{id}/misconceptions/` | Misconception cards only (lighter poll) |
| `POST` | `/api/sessions/{id}/follow-up-activity/` | Create a draft follow-up activity from weak areas |
| `GET` | `/api/sessions/{id}/participants/` | Per-participant responses |
| `GET` `POST` | `/api/reflections/` | Record what happens next lesson |
| `PATCH` | `/api/reflections/{id}/` | Edit a reflection |

Owner isolation is enforced on the queryset, so another teacher's object
returns `404`, not `403` — the existence of the row is not disclosed.

**Calling it from a script.** Fetch `/api/auth/csrf/`, keep the cookie jar, and
send the `caricue_csrftoken` value as an `X-CSRFToken` header on every unsafe
request.

---

## Insights and AI suggestions

`caricue/insights/service.py` computes, from stored responses only:

participation and submission counts · completion rate against the roster ·
correctness per question · overall auto-scored performance · confidence
distribution and average · the weakest questions · high-confidence incorrect
answers · low-confidence correct answers · common normalised short-text answers
· participants who may need attention.

Short-text scoring is deliberately dull: trim whitespace, collapse runs of
spaces, compare case-insensitively against the teacher's accepted answers. No
fuzzy matching, no spelling correction, no LLM grading. A question with no
accepted answers is reported as unscored rather than wrong.

Suggestions come from a provider interface:

- `BaseInsightProvider` — the contract, plus `build_redacted_prompt_payload`,
  the only data a provider may send outside the server.
- `RuleBasedInsightProvider` — **the default**. Transparent rules over the
  figures above. No API key, no network access, deterministic output.
- `LLMInsightProvider` — optional, driven by an injected client (a mock client
  ships with it). Receives only the redacted payload: aggregates and anonymous
  answer text, never names, emails, or roster identifiers.

Whatever the provider, suggestions are labelled as suggestions, carry
`requires_teacher_review: true`, and cannot assign a grade, change a student
record, or trigger anything on their own.

Switch providers with `CARICUE_INSIGHT_PROVIDER`.

---

## Adapt loop (Teach → Check → Understand → Adapt)

After a session closes, CariCue closes the instructional loop in three steps:

1. **Misconception cards** — deterministic cards from weak auto-scored questions
   (top distractor or common wrong answer, high-confidence-wrong counts). Each
   card separates measured **facts** from templated **suggestions** the teacher
   must review.
2. **Follow-up draft** — `POST /api/sessions/{id}/follow-up-activity/` generates a
   draft activity (never auto-launched) with lineage fields linking back to the
   source session and questions.
3. **Session comparison** — when a follow-up session closes, results include a
   `comparison` block: baseline reflection quote, overall delta, per-question
   deltas (by `source_question` lineage or position), and optional student
   movement when both sessions used **roster identifier** join mode.

The dashboard surfaces **pending follow-ups** when a closed session has a
reflection with `plan_impact=changed`, no newer closed session on the same topic,
and at least `CARICUE_FOLLOWUP_NUDGE_DAYS` days have passed (default 2).

Class detail pages show a **topic timeline** grouping closed sessions by
normalised topic so teachers can see whether scores improved over time.

---

## Production deployment

```bash
cp .env.example .env
# Edit .env: DJANGO_SECRET_KEY, POSTGRES_PASSWORD, DJANGO_ALLOWED_HOSTS,
# DJANGO_CSRF_TRUSTED_ORIGINS, PUBLIC_BASE_URL
docker compose -f docker-compose.prod.yml up --build -d
```

That starts three containers:

- **db** — PostgreSQL 16 with a named volume (`caricue_db`) and `pg_isready`
  health checks.
- **api** — Gunicorn with three workers. Its entrypoint waits for the database,
  runs `migrate`, runs `collectstatic`, then starts. Health check:
  `GET /api/health/`.
- **web** — Nginx serving the built SPA, proxying `/api`, `/django-admin` and
  `/static` to the API, and falling back to `index.html` so `/join` and
  `/s/<token>` work on a hard refresh. Health check: `GET /healthz`.

Only **web** publishes a port (`HTTP_PORT`, default `8080`).

Settings refuse to start with an insecure configuration: a missing
`DJANGO_SECRET_KEY`, or the development key, raises `ImproperlyConfigured`
whenever `DJANGO_DEBUG` is off.

Static files are collected on every start and served by WhiteNoise behind
Nginx, so a deploy needs no manual static step.

```bash
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml exec api python manage.py migrate
docker compose -f docker-compose.prod.yml exec api python manage.py createsuperuser
docker compose -f docker-compose.prod.yml up -d --build   # redeploy
```

---

## HTTPS through a reverse proxy

The bundled Nginx speaks HTTP on port 80 inside the network. Terminate TLS in
front of it — with Caddy, Traefik, a second Nginx, or a cloud load balancer —
and forward to `web`.

The proxy must send:

```
X-Forwarded-Proto  https
X-Forwarded-Host   caricue.example.edu
X-Forwarded-For    <client ip>
```

`deploy/nginx/caricue.conf` already forwards these to the API, and Django is
configured to trust them (`DJANGO_TRUST_PROXY_SSL_HEADER=1`,
`DJANGO_USE_X_FORWARDED_HOST=1`). Without them Django will believe the request
arrived over plain HTTP and secure cookies will not be set.

Then set, in `.env`:

```env
PUBLIC_BASE_URL=https://caricue.example.edu
DJANGO_ALLOWED_HOSTS=caricue.example.edu
DJANGO_CSRF_TRUSTED_ORIGINS=https://caricue.example.edu
DJANGO_SECURE_COOKIES=1
DJANGO_SECURE_HSTS_SECONDS=31536000
```

Leave `DJANGO_SECURE_SSL_REDIRECT=0` and let the TLS terminator handle the
HTTP→HTTPS redirect; enabling both causes redirect loops.

A minimal Caddy front end:

```caddyfile
caricue.example.edu {
    reverse_proxy localhost:8080
}
```

Caddy obtains the certificate and sets the forwarding headers itself.

---

## Backup and restore

Dumps contain student names. Keep them encrypted at rest and off version
control — `.gitignore` already excludes `deploy/backups/`.

```bash
./deploy/backup.sh                                    # → deploy/backups/caricue-<timestamp>.dump
./deploy/restore.sh deploy/backups/caricue-2026….dump # destructive, prompts first
```

`backup.sh` writes a `pg_dump` custom-format archive and keeps the fourteen
most recent. Schedule it from cron:

```cron
15 2 * * * cd /srv/caricue && ./deploy/backup.sh >> /var/log/caricue-backup.log 2>&1
```

`restore.sh` stops the API, runs `pg_restore --clean`, and starts the API again,
which reapplies any migrations newer than the dump. Rehearse a restore into a
throwaway stack before you need one.

Doing it by hand:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U caricue --format=custom caricue > backup.dump

docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U caricue -d caricue --clean --if-exists < backup.dump
```

---

## Privacy and security

- **Students have no accounts.** A participant is a display name or a roster
  identifier the teacher already had. No email, no device identifier, no
  tracking.
- **Minimal student data.** A student row is a display name plus an *optional*
  school identifier and *optional* email.
- **The roster is never public.** Roster-identifier join validates against the
  class list without echoing it, and the failure message is identical whether
  or not the identifier exists, so the roster cannot be enumerated.
- **Owner-based authorisation everywhere.** Every teacher queryset is filtered
  by owner before object lookup.
- **CSRF on every unsafe request**, with `SameSite=Lax` cookies and
  `Secure` outside `DEBUG`.
- **Throttled public endpoints**: code lookup, join, submit, and login all have
  configurable rate limits.
- **Submit-once enforcement** is a database constraint on
  `(participant, question)` plus a `SELECT … FOR UPDATE` on the participant
  row, so two racing devices cannot both succeed.
- **Closed sessions reject joins and submissions** in the service layer, not
  just the UI.
- **Safe errors.** A single exception handler formats every failure; unexpected
  exceptions are logged server-side and returned as a generic message.
- **Secrets come from the environment.** Nothing sensitive is committed, and
  `.env` is git-ignored.

---

## MVP scope and extension points

Deliberately **not** in this MVP: Moodle or Google Classroom integration,
gradebook sync, native apps, email or push notifications, billing, admin roles
beyond a single teacher, WebSockets, AI grading, advanced analytics, parent
accounts, multi-school tenancy, gamification.

Where to add them:

| Capability | Where it belongs |
| --- | --- |
| Moodle / Classroom roster sync | Alongside `classroom/csv_import.py`, which already normalises and dedupes roster rows behind one function |
| Gradebook export | A read-only serializer over `live/insights` — nothing in the schema needs to change |
| Real-time dashboard | Swap the poll in `SessionLivePage` for a subscription; the dashboard payload is already a single self-contained snapshot |
| A real LLM | Implement the client that `LLMInsightProvider` takes, and set `CARICUE_INSIGHT_PROVIDER` |
| Extra question types | Add to `QuestionType`, then extend `score_answer` and the insight aggregation — both switch on the type in one place |
| Notifications | New app subscribing to session close; keep it out of the request path |
| Multi-school tenancy | `Teacher` gains an organisation FK; owner filtering already funnels through `OwnedQuerysetMixin` |

---

## Licence

Not yet specified. Add one before distributing.
