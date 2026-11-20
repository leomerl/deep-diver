# Interview guide

Everything needed to defend this system in an interview. It describes the code as it is now and changes with it.

| File | What's in it |
|---|---|
| [stack.md](stack.md) | How each technology works inside, as far as an interviewer will probe, and why it's here |
| [decisions.md](decisions.md) | One entry per area: what, why, rejected alternatives, failure modes, what changes at scale |
| [questions.md](questions.md) | Likely interview questions with strong answers, including the hostile ones |

The product and architecture themselves are in [../../DESIGN.md](../../DESIGN.md).

**The 30-second pitch:** *"You add a repo URL. An async worker clones it at one pinned commit and groups the code into a tree of areas. You expand the tree, and on any node you can ask for an AI deep dive. The gateway only writes to Redis Streams, so there's no dual write. Workers are at-least-once with leases, a reaper and a dead-letter queue, and every final write is insert-once, so a retry or a zombie worker can't overwrite anything. Postgres is the source of truth, and its schema is generated from typed models."*
