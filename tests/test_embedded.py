import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from bootdisk_publish.embedded import decode_indexed,publish

class EmbeddedTests(unittest.TestCase):
    def setUp(self):
        self.layout={'width':3,'height':2,'row_stride':4,'encoding':'indexed8-rle257-or-raw','palette_encoding':'rgb16be-high-byte'}
        self.palette=bytes(v for i in range(256) for v in (i,i,0,0,0,0))

    def test_raw_padding_and_rle_have_exact_same_pixels(self):
        raw=bytes([1,2,3,0,4,5,6,0]);rle=bytes([7])+raw
        first=decode_indexed(raw,self.palette,self.layout)
        self.assertEqual(first,decode_indexed(rle,self.palette,self.layout))
        im=Image.open(BytesIO(first));self.assertEqual(im.size,(3,2))
        self.assertEqual([im.getpixel((x,y)) for y in range(2) for x in range(3)],[(i,0,0) for i in range(1,7)])

    def test_repeat_and_invalid_runs(self):
        png=decode_indexed(bytes([249,7]),self.palette,self.layout)
        self.assertEqual(Image.open(BytesIO(png)).getpixel((2,1)),(7,0,0))
        for raw in (b'',bytes([8,1]),bytes([255]),bytes([248,7]),bytes([255,7])):
            with self.assertRaises(ValueError):decode_indexed(raw,self.palette,self.layout)
        with self.assertRaises(ValueError):decode_indexed(bytes([249,7]),b'',self.layout)
        with self.assertRaises(ValueError):decode_indexed(bytes([249,7]),self.palette,{**self.layout,'height':1000000})

    def test_palette_affects_derivative_and_does_not_change_original(self):
        raw=bytes([249,7]);p1=decode_indexed(raw,self.palette,self.layout)
        palette=bytes([255])*1536;p2=decode_indexed(raw,palette,self.layout)
        self.assertNotEqual(p1,p2);self.assertEqual(raw,bytes([249,7]))

    def fixture(self,root):
        raw=bytes([249,7]);objects={'pixels':raw,'palette':self.palette,'metadata':b'metadata'}
        container=b'header'+b''.join(objects.values());sha=lambda b:hashlib.sha256(b).hexdigest()
        source={'path':'menu.cxt','sha256':sha(container),'size':len(container)}
        manifest={'entries':[{'source_id':'K1'}],'file_inventory':[source]};mp=root/'ingest.json';mp.write_text(json.dumps(manifest))
        ref='sha256:'+sha(mp.read_bytes());item={'entry_source_id':'K1','entry_title':'Example','kind':'icon','source_ref':{'manifest':ref,'entry':'K1'},'raster':self.layout}
        (root/'containers').mkdir();(root/'containers'/source['sha256']).write_bytes(container);(root/'resources').mkdir();offset=6
        for kind,data in objects.items():
            digest=sha(data);(root/'resources'/digest).write_bytes(data)
            item[kind]={'container':source,'sha256':digest,'size':len(data),'object_path':'resources/'+digest,'offset':offset,'resource_id':1};offset+=len(data)
        report={'schema':'bootdisk-embedded-images-1','manifest':ref,'assets':[item]};rp=root/'images.json';rp.write_text(json.dumps(report));return rp,mp,report

    def test_container_slice_and_manifest_binding_are_required(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rp,mp,report=self.fixture(root)
            r=publish(rp,mp,root/'out');self.assertEqual(len(r['assets']),1)
            with self.assertRaisesRegex(ValueError,'new'):publish(rp,mp,root/'out')
            report['assets'][0]['pixels']['offset']+=1;rp.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'container slice'):publish(rp,mp,root/'bad')
            self.assertFalse((root/'bad').exists())
            report['manifest']='sha256:'+'0'*64;rp.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'manifest mismatch'):publish(rp,mp,root/'bad')

    def test_resource_tampering_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rp,mp,report=self.fixture(root)
            target=root/report['assets'][0]['pixels']['object_path'];target.write_bytes(b'00')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):publish(rp,mp,root/'bad')
            self.assertFalse((root/'bad').exists())
