import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
from bootdisk_publish.documents import publish

class DocumentsTests(unittest.TestCase):
    def test_original_bytes_reused_and_corruption_rejected(self):
        raw=b'{\\rtf1 Original}\x00';digest=hashlib.sha256(raw).hexdigest()
        doc={'raw_base64':base64.b64encode(raw).decode(),'sha256':digest,'size':len(raw),'text':'Original'}
        projection={'schema':'bootdisk-source-documents-1','manifest':'sha256:'+'a'*64,'documents':[doc]}
        with tempfile.TemporaryDirectory() as d:
            result=publish(projection,d);item=result['documents'][0]
            p=Path(d)/item['original']['public_path'];self.assertEqual(p.read_bytes(),raw)
            self.assertNotIn('raw_base64',item);self.assertEqual(publish(projection,d),result)
            p.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'conflicting'): publish(projection,d)
            doc['sha256']='b'*64
            with self.assertRaisesRegex(ValueError,'mismatch'): publish(projection,d)
