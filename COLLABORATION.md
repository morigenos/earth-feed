# Working with two assistants on this project

Two assistants are contributing: **Claude** (globe, design, roadmap) and **ChatGPT**
(feed repository hardening). Neither can see the other's conversation. The repository
is the shared memory, so anything that matters is written into files here.

## Who can do what

| | Reads this repo | Writes to this repo |
|---|---|---|
| Claude (chat) | yes, public raw files, any time | no credentials; hands over files or drives the browser with approval |
| ChatGPT (Work/Codex) | yes | yes, if granted |
| Matej | yes | yes |

## Conventions

- **`FEED_CONTRACT.md` is the interface.** Change data shapes there first, in the same commit as the code.
- **`CURRENT_STATUS.md`** is rewritten by whoever last changed something, with real numbers from a real run.
- **`DECISIONS.md`** is append-only: one line per decision with the reason, especially for anything marked blocked.
- **`ROADMAP.md`** holds the staged plan and status words: implemented, partial, planned, research, blocked.
- Keep collector scripts independent: one file per source, failures isolated, no shared mutable state.
- Never commit secrets. Keys live in repository secrets and are read from the environment.

## Handover note

If one assistant changes a data shape, cadence or file name, say so in the commit
message and in `CURRENT_STATUS.md`. The globe fails quietly when a field disappears:
a layer simply shows nothing, which is the hardest kind of bug to notice.
