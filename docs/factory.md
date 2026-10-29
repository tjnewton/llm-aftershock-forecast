# Software factory

How code changes reach this repository during the Seismica phase of the project. It covers
review and implementation of engineering tickets only. Live forecasting is a separate scheduled
workflow, and the Windows RTX 5090 machine stays a queue-driven GPU
worker (`ops/windows-queue.md`); neither is a factory task.

Vocabulary follows the "software factory" framing of tasks, triggers, services and brakes
(mattpocock/skills, PR 1316).

## Problems it solves, in order

1. Pull requests waiting for review.
2. The engineering backlog (tickets).
3. A daily ratchet (a small recurring improvement task). Deferred until the implementer has
   produced 10 clean pull requests.

## Services

| Role | Service |
|---|---|
| Git host | GitHub |
| Ticket tracker | public GitHub Issues |
| Orchestrator | GitHub Actions |
| Runners | GitHub-hosted |
| Observability | none |
| Ticket sources | none at first; later, failures of the live pipeline open issues |

Tickets are public. They never contain keys, budget figures, personal data, or anything learned
from looking at outcomes of confirmatory data.

The implementer runs on my Claude subscription token and the reviewer on my ChatGPT plan, both
as repository secrets. Neither ever uses the API key that pays for scored model calls, and no
scored-call key exists in the factory's environment.

## Tasks

### Review (live now)
- Trigger: a new commit on a pull request into `post-submission` from a branch in this
  repository. Pull requests from forks are ignored.
- Codex reviews automatically and comments only. It never pushes or merges.
- One review per head commit.
- I merge.

### Implementer (after hackathon judging ends)
Issue-triggered workflows run only from the default branch, which stays frozen until judging
ends, so this task starts then. Until it exists, tickets are implemented in interactive sessions,
still through pull requests.
- Trigger: I add the label `ready-for-agent` to an issue.
- `claude-code-action` implements the ticket on a branch `factory/<issue number>` and opens a
  pull request into `post-submission`; the label switches to `agent-working`.
- One pull request per issue; one implementer run at a time.
- Rework happens when I re-label the issue, at most two rounds; after that the ticket comes back
  to a human.

## Brakes

- Existing CI on every push and pull request: `ruff format --check`, `ruff check`, `pyright`,
  `pytest -m "not network"`, `laf verify`.
- Path guard:
  - flags direct pushes that touch `src/`, `tests/`, `notebooks/`, `prompts/` or `config/`
    (code reaches those paths through pull requests);
  - fails pull requests that touch frozen files or `prompts/` unless I add an override label.
- Codex review on every pull request.
- I review every pull request.
- Pull requests that change only docs or tests may get a lighter process after 10 clean merges.
  Scoring, analysis, prompts, data handling and the snooping guard never loosen.

Code written in my own interactive sessions follows the same route: a pull request into
`post-submission`. Data, run outputs and `ops/` files may be pushed directly.

## Never a factory task

- Scored API calls (there are no scored-call keys in the factory's environment).
- Preregistration freezes and tags.
- `main` and `gh-pages`.
- Frozen files.
- Deletions or history rewrites.
- Secrets.
- Posting anywhere outside the repository.
- Science decisions. Prompt wording changes only through a ticket that quotes text I approved.
- Network fetches (ComCat, USGS products, literature).

## Tickets

I write tickets in a session with Claude and file them with `gh issue create`. Each ticket has:
- the goal;
- acceptance criteria written as tests;
- files in scope and out of scope;
- links to the decisions it depends on (ADRs, this file);
- forbidden actions (from the list above, plus anything specific).

## Setup steps

- [x] Codex automatic review enabled for the repository.
- [ ] Check whether Codex review can skip pull requests from forks.
- [ ] Labels `ready-for-agent`, `agent-working` and the path-guard override label.
- [ ] `claude setup-token` stored as a repository secret (after judging).
- [ ] Implementer workflow on the default branch (after judging).
