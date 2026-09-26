import tempfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
import app
ns={'t':'http://schemas.microsoft.com/windows/2004/02/mit/task'}
r=ET.fromstring(app.task_xml('C:/apps/A & B/CodexQuotaResume.exe',5,'--monitor --backup'))
assert r.find('t:Actions/t:Exec/t:Command',ns).text=='C:/apps/A & B/CodexQuotaResume.exe'
assert r.find('t:Settings/t:ExecutionTimeLimit',ns).text=='PT0S'
assert r.find('t:Settings/t:DisallowStartIfOnBatteries',ns).text=='false'
assert r.find('t:Principals/t:Principal/t:LogonType',ns).text=='InteractiveToken'
assert r.find('t:Triggers/t:TimeTrigger/t:Repetition/t:Interval',ns).text=='PT5M'
with tempfile.TemporaryDirectory() as folder:
 with patch.object(app.w,'APP_DIR',Path(folder)),patch.object(app,'run_command') as run:
  app.pause()
  assert run.call_count==2 and (Path(folder)/'paused.flag').exists()
  assert all(c.args[0][-1]=='/DISABLE' for c in run.call_args_list)
print('APP_TASKS_OK: XML escaping, interactive session, battery, unlimited execution, pause both layers')

for states,expected in [(('true','true'),True),(('false','false'),False),(('true','false'),False)]:
 with patch.object(app,'run_command',return_value='['+','.join(states)+']'):
  text,color,enabled=app.monitor_indicator()
  assert enabled is expected
  if expected:assert color=='#43c77a'
with patch.object(app,'run_command',side_effect=RuntimeError('unavailable')):
 assert app.monitor_indicator()[2] is False
print('MONITOR_INDICATOR_OK: green only when both real tasks are enabled; paused, partial and unknown stay non-green')
