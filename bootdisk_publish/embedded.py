"""Publish explicitly observed embedded rasters; never discover CD resources."""
from __future__ import annotations
import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from PIL import Image


def require(condition, message):
    if not condition: raise ValueError(message)


def decode_indexed(raw, palette, layout):
    """Bounded declared codec. RLE high byte n repeats the next byte 257-n times."""
    require(layout.get('encoding') == 'indexed8-rle257-or-raw' and layout.get('palette_encoding') == 'rgb16be-high-byte', 'unsupported raster codec')
    w,h,stride = (layout.get(k) for k in ('width','height','row_stride'))
    require(all(type(v) is int for v in (w,h,stride)) and 0<w<=stride<=4096 and 0<h<=4096 and stride*h<=16*1024*1024,'invalid raster dimensions')
    require(len(palette)==1536,'invalid palette size')
    needed=stride*h
    require(len(raw)<=2*needed,'oversized raster input')
    if len(raw)==needed:
        pixels=raw
    else:
        pixels=bytearray();pos=0
        while pos<len(raw):
            n=raw[pos];pos+=1
            count=n+1 if n<128 else 257-n
            require(len(pixels)+count<=needed,'raster expansion exceeds dimensions')
            if n<128:
                require(pos+count<=len(raw),'truncated literal run')
                pixels.extend(raw[pos:pos+count]);pos+=count
            else:
                require(pos<len(raw),'truncated repeated run')
                pixels.extend([raw[pos]]*count);pos+=1
        require(len(pixels)==needed,'truncated raster')
    packed=b''.join(pixels[y*stride:y*stride+w] for y in range(h))
    im=Image.frombytes('P',(w,h),packed);im.putpalette(palette[::2])
    out=BytesIO();im.convert('RGB').save(out,format='PNG')
    return out.getvalue()


def publish(images_path, ingest_path, output):
    images_path=Path(images_path);root=images_path.parent.resolve()
    report_raw=images_path.read_bytes();report=json.loads(report_raw)
    ingest_raw=Path(ingest_path).read_bytes();ingest=json.loads(ingest_raw)
    manifest='sha256:'+hashlib.sha256(ingest_raw).hexdigest()
    require(report.get('schema')=='bootdisk-embedded-images-1' and report.get('manifest')==manifest,'image report manifest mismatch')
    inventory={i['path']:i for i in ingest['file_inventory']};entries={e['source_id'] for e in ingest['entries']}
    containers={};objects={};assets=[];seen=set()
    def read_object(path,size,digest):
        require(type(size) is int and 0<=size<=128*1024*1024 and isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest),'invalid resource identity')
        target=(root/path).resolve()
        require(target.is_relative_to(root) and target.is_file() and target.stat().st_size==size,'missing/invalid preserved object')
        data=target.read_bytes()
        require(hashlib.sha256(data).hexdigest()==digest,'preserved object hash mismatch')
        return data
    def read_resource(resource):
        container=resource['container'];record=inventory.get(container['path'])
        require(record is not None and all(record[k]==container[k] for k in ('size','sha256')),'container differs from inventory')
        digest=container['sha256']
        if digest not in containers: containers[digest]=read_object('containers/'+digest,container['size'],digest)
        require(resource.get('object_path')=='resources/'+resource['sha256'],'invalid resource path')
        data=read_object(resource['object_path'],resource['size'],resource['sha256'])
        offset=resource.get('offset')
        require(type(offset) is int and offset>=0 and containers[digest][offset:offset+len(data)]==data,'resource does not match container slice')
        return data
    def store(data,kind,extension=''):
        digest=hashlib.sha256(data).hexdigest()
        key=f'{kind}/sha256/{digest[:2]}/{digest[2:4]}/{digest}{extension}'
        objects[key]=data
        return {'sha256':digest,'size':len(data),'object_key':key}
    for item in report['assets']:
        entry=item['entry_source_id'];kind=item['kind'];identity=(entry,kind)
        require(entry in entries and kind in ('icon','screenshot') and identity not in seen,'unknown/duplicate image association')
        seen.add(identity)
        require(item.get('source_ref')=={'manifest':manifest,'entry':entry},'image entry mismatch')
        pixels=read_resource(item['pixels']);palette=read_resource(item['palette']);read_resource(item['metadata'])
        png=decode_indexed(pixels,palette,item['raster'])
        original=store(pixels,'assets');derivative=store(png,'derivatives/embedded/png','.png')
        derivative.update({'kind':'thumbnail','media_type':'image/png','width':item['raster']['width'],'height':item['raster']['height'],
                           'source_sha256':original['sha256'],'palette_sha256':item['palette']['sha256'],
                           'generator':{'name':'bootdisk-publish-indexed8','version':'1'}})
        assets.append({'entry_source_id':entry,'entry_title':item['entry_title'],'kind':kind,
                       'source_path':item['pixels']['container']['path']+'#BITD:'+str(item['pixels']['resource_id']),
                       'original':original,'derivatives':[derivative],
                       'source_ref':item['source_ref'],'image_report_sha256':hashlib.sha256(report_raw).hexdigest()})
    result={'schema_version':'bootdisk-publish-1','ingest':{'manifest_sha256':manifest[7:]},'assets':assets}
    output=Path(output).absolute()
    require(not output.exists() and not output.is_symlink(),'output must be new')
    output.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.publish-images-',dir=output.parent))
    try:
        for key,data in objects.items():
            path=stage/'store'/key;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        (stage/'publish-manifest.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        os.rename(stage,output)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('images');p.add_argument('manifest');p.add_argument('--output',required=True)
    a=p.parse_args();r=publish(a.images,a.manifest,a.output);print(f"published embedded assets: {len(r['assets'])}")
if __name__=='__main__':main()
