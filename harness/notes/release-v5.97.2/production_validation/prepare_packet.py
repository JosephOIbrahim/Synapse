"""CPU-only seal for a NEW owned graphical reproduction packet; no native launch."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args]).decode('utf-8').strip()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True);parser.add_argument('--packet-root',type=Path,required=True)
    args=parser.parse_args();repo=args.repo.resolve();out=args.packet_root.resolve()
    assert not out.exists(), 'Use a new owned directory'
    dirty=git(repo,'status','--porcelain')
    assert not any(line and not line.startswith('??') for line in dirty.splitlines()), 'Tracked-clean source required'
    assert (repo/'VERSION').read_text().strip()=='5.97.2'
    head=git(repo,'rev-parse','HEAD')
    for row in read(ROOT/'loaded-source-pins.json')['modules']:
        path=(repo/row['path']).resolve()
        assert path.is_relative_to(repo) and sha(path)==row['sha256'], 'Native input source differs: '+row['path']
    runtime=read(ROOT/'runtime-pins.json')['files']
    for row in runtime:assert sha(Path(row['path']))==row['sha256'], 'Installed runtime differs: '+row['path']
    for row in read(ROOT/'vendor-dependencies.json')['packages']:
        assert Path(row['hpath']).is_dir()
        assert read(Path(row['manifest']))=={'hpath':'$HFS/packages/'+row['package']}
    out.mkdir(parents=True)
    for name in ('production_probe.py','graphical_entry.py','run_when_coordinated.ps1','slot-template.json','vendor-dependencies.json'):
        shutil.copyfile(ROOT/name,out/name)
    original='945df057aa1e6b3f4849d80332f762bf56911ca2'
    for name in ('production_probe.py','run_when_coordinated.ps1','slot-template.json'):
        path=out/name;path.write_text(path.read_text().replace(original,head),encoding='utf-8')
    source=[]
    for rel in git(repo,'ls-files','-z').split('\0'):
        if not rel:continue
        path=(repo/rel).resolve();assert path.is_relative_to(repo)
        source.append({'path':rel,'sha256':sha(path)})
    (out/'source-manifest.json').write_text(json.dumps({'commit':head,'source_root':str(repo),'files':source},indent=2)+'\n')
    files=[{'path':name,'sha256':sha(out/name)} for name in ('production_probe.py','graphical_entry.py','run_when_coordinated.ps1','source-manifest.json','slot-template.json','vendor-dependencies.json')]
    pins={'schema':'synapse-production-native-seam/1','commit':head,'source_root':str(repo),'execution_mode':'production-seam','native':'UNRUN','files':files,'runtime_files':runtime,'limits':read(ROOT/'production-evidence.json')['limits']}
    (out/'prepared-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
    ready={'status':'CPU_PREPARED_NATIVE_UNRUN','commit':head,'native_tested_source_commit':original,'source_equivalence':'All200 loaded module origins match original native source','native_processes':0,'prepared_pins_sha256':sha(out/'prepared-pins.json'),'limits':pins['limits'],'required_free_memory_bytes':17179869184,'remaining':'New independent review and fresh graphical/licence/desktop/resource owner receipt required; no historical receipt reuse'}
    (out/'READY.json').write_text(json.dumps(ready,indent=2)+'\n');print(json.dumps(ready))
if __name__=='__main__':main()
