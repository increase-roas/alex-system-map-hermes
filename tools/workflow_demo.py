"""Generate a synthetic correction/recovery packet, using a temporary database."""
import json
import tempfile
from pathlib import Path
from workflow_engine import Engine

def run():
    with tempfile.TemporaryDirectory() as directory:
        engine=Engine(str(Path(directory)/'demo.sqlite'))
        def apply(action,payload):
            revision=0 if action=='create' else engine.job('synthetic-lamp-audit')['revision']
            return engine.apply('synthetic-lamp-audit',revision,f'demo-operation-{revision+1}',action,payload)
        apply('create',dict(goal='Demonstrate correction recovery on synthetic lamps',scope=['synthetic sample only'],constraints=['no services','no real job certification'],owner='demo-builder',acceptance=['synthetic proof only']))
        apply('add_task',dict(id='synthetic-inspect',goal='Inspect mock fixture',owner='demo-builder',deps=[],acceptance=['contains:synthetic-report::fixture'],next_action='inspect mock fixture'))
        apply('add_task',dict(id='synthetic-report',goal='Summarize mock fixture',owner='demo-builder',deps=['synthetic-inspect'],acceptance=['file:synthetic-report non-empty'],next_action='write mock report'))
        apply('update',dict(task_id='synthetic-inspect',attempt='First synthetic inspection',outputs=['mock fixture notes']))
        apply('verify',dict(task_id='synthetic-inspect',id='synthetic-checkpoint-1',verifier='demo-reviewer',evidence=['synthetic fixture observation'],checks={'contains:synthetic-report::fixture':True}))
        apply('correct',dict(id='synthetic-correction-1',task_id='synthetic-inspect',reason='Mock fixture version changed'))
        engine.close()
        engine=Engine(str(Path(directory)/'demo.sqlite'))
        packet=engine.recover('synthetic-lamp-audit'); engine.close(); return packet
if __name__=='__main__': print(json.dumps(run(),indent=2))
