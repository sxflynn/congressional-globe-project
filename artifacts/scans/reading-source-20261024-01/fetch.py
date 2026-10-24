"""Bounded two-crop source check. No inference; all transfers share a12MB cap."""
import json
from pathlib import Path
from congressional_globe import scan_fetch
from congressional_globe.scan_geometry import prepare_target
from congressional_globe.reading_contracts import ReadingCandidate
base=Path('artifacts/scans/reading-source-20261024-01')
units=[ReadingCandidate.model_validate_json(line) for line in Path('artifacts/reading-prepare-20261024-03/candidates.jsonl').read_text().splitlines()]
source={p.source_id:p for u in units for p in u.target}
remaining=12_000_000
original=scan_fetch.download
receipts=[]
def bounded(url,path,limit):
 global remaining
 if remaining<=0: raise ValueError('shared image budget exhausted')
 receipt=original(url,path,min(limit,remaining))
 remaining-=receipt.bytes
 receipts.append(receipt.model_dump(mode='json'))
 return receipt
scan_fetch.download=bounded
for label,item,leaf,paragraph_id in [
 ('structured','congressionalg7391unit',207,'par_000207_000040'),
 ('long','congressionalglo7393unit',126,'par_000126_000010'),
]:
 target=prepare_target(Path('.'),item,leaf,paragraph_id,padding=32,max_width=1600)
 expected=source[f'{item}:{leaf}:{paragraph_id}']
 assert target.raw_sha256==expected.raw_sha256 and target.raw_text==expected.raw
 assert len(target.regions)==1
 bundle=scan_fetch.fetch_bundle(base/label,target)
 print(label,bundle.images[0].receipt.bytes,flush=True)
(base/'transfer-report.json').write_text(json.dumps(dict(provider_calls=0,cap_bytes=12_000_000,
 bytes=12_000_000-remaining,image_files=2,receipts=receipts),indent=2)+'\n')
