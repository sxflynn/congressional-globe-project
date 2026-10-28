import json, runpy, time, signal, hashlib
from pathlib import Path
from congressional_globe.productive_ocr_runner import code_identity
h=runpy.run_path('tests/test_productive_ocr_live.py')
root=Path('artifacts/owned-ocr-transport-20261028-03').resolve()
root.mkdir(exist_ok=False)
def save(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
base=root/'synthetic-success';base.mkdir()
started=time.time()
result=h['_execute'](base,started=started)
assert result['statuses']['valid']==1
assert h['_execute'](base,started=started)==result
save(base/'result.json',result)
prepared,registry,bounds,client,approval,ready=h['_job'](base,started)
save(base/'prepared.json',prepared.model_dump(mode='json'))
save(base/'bounds.json',bounds.model_dump(mode='json'))
save(base/'readiness.json',json.loads(registry.files[ready]))
files=base/'registered-bytes';files.mkdir()
for sha,data in registry.files.items():(files/sha).write_bytes(data)
cases=[]
for checkpoint in ['after_transport_spool','after_raw_before_observation','after_raw','after_terminal']:
    case=root/checkpoint;case.mkdir();(case/'started.txt').write_text(str(time.time()))
    killed=h['_process'](case,checkpoint)
    resumed=h['_process'](case,'resume')
    assert killed.returncode==-signal.SIGKILL,(checkpoint,killed.stderr)
    assert resumed.returncode==0,(checkpoint,resumed.stderr)
    count=len(list((case/'spool').glob('*/request.bin')))
    assert count==1
    result=json.loads((case/'result.json').read_bytes());assert result['statuses']['valid']==1
    cases.append(dict(checkpoint=checkpoint,killed_returncode=killed.returncode,resumed_returncode=resumed.returncode,requests=count,status=result['statuses']))
save(root/'recovery.json',dict(scope='Synthetic fake HTTP/process proof only; no model inference or historical reading',cases=cases))
save(root/'code-identity.json',code_identity())
save(root/'limits.json',dict(real_inference_calls=0,source_fetches=0,retries=0,model_downloads=0,historical_grades=0,readiness='blocked',remaining=['R1: S3/S4 crops absent','R3: actual native preprocessing fit producer/evidence absent','R4: real model process stopping and backend compatibility unproved'],R2='HTTP adapter/export implemented and fake-server tested; actual server behavior unproved'))
# Do not preserve machine-specific executable scripts or SQLite transient files as portable evidence.
for p in root.rglob('*'):
    if p.is_file() and (p.name.startswith('fake-') or p.name.endswith(('-wal','-shm'))):p.unlink()
manifest={str(p.relative_to(root)):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in root.rglob('*') if p.is_file()}
save(root/'manifest.json',manifest)
print(json.dumps(dict(cases=cases,files=len(manifest),bytes=sum(v['bytes'] for v in manifest.values()))))
