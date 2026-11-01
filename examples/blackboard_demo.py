"""Offline shared-environment example; no paid calls or code execution."""
import asyncio
from tempfile import TemporaryDirectory
from pathlib import Path
from pluralforge import EventWorker, SharedBlackboard


async def main():
    with TemporaryDirectory() as workdir:
        db = Path(workdir) / 'demo.sqlite'
        explorer = SharedBlackboard(db, 'demo-session')
        critic = SharedBlackboard(db, 'demo-session')
        explorer.put('proposal:1', 'idea', {'hypothesis': 'cache repeated calls'},
                     actor='explorer', expected_version=0)
        explorer.publish('benchmark.completed',
                         {'proposal': 'proposal:1', 'quality_change': -0.12},
                         actor='tester', dedupe_key='benchmark-run-1')

        async def on_benchmark(event, board):
            if event.payload['quality_change'] < 0:
                board.put('critique:1', 'risk',
                          {'proposal': event.payload['proposal'],
                           'reason': 'Quality regression; test a conditional router',
                           'source_event_id': event.id},
                          actor='critic', expected_version=0, caused_by=event.id)

        worker = EventWorker(critic, 'critic', {'benchmark.completed': on_benchmark})
        processed = await worker.step(max_events=2)
        print('events processed:', processed)
        print('shared risk:', explorer.get('critique:1').value)
        print('unresolved evidence status:', explorer.get('critique:1').evidence_status)


if __name__ == '__main__':
    asyncio.run(main())
