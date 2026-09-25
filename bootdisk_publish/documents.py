"""Publish verified original RTF documents from Catalog's separate source projection."""
import argparse
import base64
import hashlib
import json
from pathlib import Path


def publish(projection, output):
    if projection.get('schema') != 'bootdisk-source-documents-1': raise ValueError('unsupported document projection')
    output = Path(output); documents = []
    for doc in projection['documents']:
        raw = base64.b64decode(doc['raw_base64'], validate=True)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != doc['sha256'] or len(raw) != doc['size']: raise ValueError('RTF hash/size mismatch')
        key = f'documents/sha256/{digest[:2]}/{digest}.rtf'
        target = output/'store'/key; target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != raw: raise ValueError('conflicting original object')
        else:
            with target.open('xb') as f: f.write(raw)
        documents.append({k:v for k,v in doc.items() if k != 'raw_base64'} | {
            'original': {'sha256': digest, 'size': len(raw), 'object_key': key,
                         'public_path': 'store/'+key, 'media_type': 'application/rtf'}})
    return {'schema': 'bootdisk-published-documents-1', 'manifest': projection['manifest'],
            'documents': documents, 'issues': projection.get('issues', [])}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('projection');p.add_argument('--output',required=True);p.add_argument('--manifest-output',required=True);a=p.parse_args()
    result=publish(json.loads(Path(a.projection).read_text()),a.output)
    with Path(a.manifest_output).open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')

if __name__ == '__main__': main()
