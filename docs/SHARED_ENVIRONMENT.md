# Shared Environment / 共享环境 — PluralForge AI v0.6

PluralForge AI v0.6 adds an **opt-in, local shared blackboard**. It is a durable
coordination substrate, not a new agent authority or a background AI service.

## Capabilities

- **Shared data/state:** versioned JSON artifacts in SQLite, scoped by workspace.
- **Events:** append-only events (for example, environment.changed,
  benchmark.completed and risk.flagged), with causal event references.
- **Subscriptions:** independent durable per-consumer offsets, filtered polling,
  async/sync handler dispatch, at-least-once delivery until acknowledgement.
- **Code sharing:** store Git branch, commit and content-hash references as
  code_reference artifacts; code is never fetched, merged or executed by the board.
- **Evidence boundary:** all agent-created artifacts are unverified. The *trusted
  host* may separately call verify() with an independent evidence reference.
  Changing the artifact version resets its verification label.

## Try it offline

    python -m examples.blackboard_demo
    python -m pytest tests/test_blackboard.py -q

### Example integration

    import asyncio
    from pluralforge import SharedBlackboard, EventWorker

    board = SharedBlackboard("team.sqlite", space="research-project")
    board.put("proposal:one", "idea", {"hypothesis": "cache results"},
              actor="explorer", expected_version=0)
    board.publish("benchmark.completed", {"proposal": "proposal:one", "delta": -0.12},
                  actor="tester", dedupe_key="run:001")

    async def critique(event, board):
        if event.payload["delta"] < 0:
            board.put(f"risk:{event.id}", "risk",
                      {"ref": event.payload["proposal"], "cause": event.id},
                      actor="critic", expected_version=0, caused_by=event.id)

    worker = EventWorker(board, "critic", {"benchmark.completed": critique})
    asyncio.run(worker.step(max_events=10))

Multiple agents opening the same database file and workspace share changes;
separate workspaces are isolated by key. Agents do **not** need to broadcast
messages to one another: they observe the environment and contribute new artifacts.

## Runtime and safety boundaries

1. **Not autonomous by itself.** The host invokes a bounded step(). There is
   no polling daemon, cloud persistence, scheduling, or live model call.
2. **One active worker per consumer ID.** Multiple workers reusing a consumer
   may race and duplicate work. Consumers are responsible for idempotent effects.
   After a crash, unacknowledged events may be delivered again.
3. **No direct code execution.** Code references are inert metadata. An
   independent sandbox/test executor and review workflow are future work.
4. **No authentication inside SQLite.** verify() is a *host-only convention*,
   not an access-control boundary. Do not expose board writes or verification
   directly to an untrusted Agent or HTTP client; enforce host-side authorization.
5. **Bounded JSON.** A single artifact/event payload is limited to 64 KiB;
   store large files out-of-band and record immutable hash/commit references.
6. **Do not store secrets.** A workspace is for trusted local processes, not
   general-purpose untrusted users. SQLite WAL is not a distributed event bus.
7. **Budgeting and consensus are unchanged.** The existing Brainstorm engine,
   information-value estimates, refusal to invent evidence, preserved dissent,
   and human-review boundaries still govern decision-making.

## Roadmap

- **v0.7 proposed:** sandboxed tool/code execution, Git patch lifecycle,
  test attestations and merge approval.
- **v0.8 proposed:** bounded event-to-task planner, novelty discovery and
  information-value-aware dispatch, with measured cost/quality benchmarks.

These roadmap features are not included in v0.6.
