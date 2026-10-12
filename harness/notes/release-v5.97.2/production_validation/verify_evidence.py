"""CPU-only published native evidence and source-closure verification."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify(repo):
    evidence=read(ROOT/'production-evidence.json')
    assert evidence['status']=='SCOPED_PRODUCTION_NATIVE_PASS'
    assert evidence['tested_commit']=='945df057aa1e6b3f4849d80332f762bf56911ca2'
    assert (repo/'VERSION').read_text().strip()=='5.97.2'
    for row in evidence['artifacts']:
        assert sha(ROOT/row['path'])==row['published_sha256'], 'Changed native artifact: '+row['path']
        if row.get('raw_bytes_unchanged'):assert row['raw_sha256']==row['published_sha256']
    for row in read(ROOT/'loaded-source-pins.json')['modules']:
        path=(repo/row['path']).resolve()
        assert path.is_relative_to(repo) and sha(path)==row['sha256'], 'Changed executed source: '+row['path']
    for a,b in (('baseline-before-preview.json','after-preview.json'),('after-apply.json','after-repeat.json'),('before-fault-saved-reference.json','after-artist-undo.json')):
        assert (ROOT/a).read_bytes()==(ROOT/b).read_bytes()
        assert read(ROOT/a)==read(ROOT/b)
    bad=read(ROOT/'after-failure-outer-group-closed.json');good=read(ROOT/'after-artist-undo.json')
    assert bad!=good
    key='/stage/production_bridge_fixture/inserted'
    assert bad['graph'][key]['inputs']['0']==['/stage/production_bridge_fixture/source',0]
    assert good['graph'][key]['inputs']['0']==['/stage/production_bridge_fixture/source',1]
    assert bad['usd']['sink']['/NativeMarker']['attributes']['test:output']==0
    assert good['usd']['sink']['/NativeMarker']['attributes']['test:output']==1
    native=read(ROOT/'production.json');gate=read(ROOT/'production-native-gate.json');control=read(ROOT/'controller.json')
    assert native['status']=='ASSERTIONS_PASSED' and native['private_update_mode_restored'] is True
    assert control['status']=='NATIVE_ASSERTIONS_COMPLETE' and control['children'][0]['exit_code']==0
    assert gate['status']=='PASSED' and gate['candidate_imported'] is False and gate['is_ui_available'] is True and gate['actual_main_thread'] is True
    assert gate['actual_build']=='22.0.400' and gate['actual_license_category']=='licenseCategoryType.Indie'
    assert [c['response']['success'] for c in native['calls']]==[True,True,True,False,True]
    assert native['bridge_stats']['operations_total']==5 and native['bridge_stats']['operations_verified']==4
    assert native['post_fault_verified_delta']==0
    assert read(ROOT/'04-artist-recovery.json')['labels_restored'] is True
    for name in ('worker','controller'):
        filename='production_probe.py' if name=='worker' else 'run_when_coordinated.ps1'
        assert sha(ROOT/filename)==evidence['public_reproduction'][name+'_sha256']
    assert sha(ROOT/'graphical_entry.py')==evidence['public_reproduction']['entry_sha256']
    assert sha(ROOT/'run_when_coordinated.ps1.txt')==evidence['executed_producer_hashes']['controller']
    return {'status':'CPU_NATIVE_EVIDENCE_AND_LOADED_SOURCE_EQUIVALENCE_PASS','native_processes':0,'module_origins':len(read(ROOT/'loaded-source-pins.json')['modules']),'native_tested_commit':evidence['tested_commit'],'public_reproduction_native':'UNRUN_ADAPTATION'}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(verify(args.repo.resolve())))
