import unittest
import zlib
from bootdisk_publish.embedded import resource_slice

class ResourceSliceTests(unittest.TestCase):
    def setUp(self):
        self.body=b'header pixels palette tail'
        self.packed=zlib.compress(self.body)
        self.container=b'prefix'+self.packed+b'suffix'
        self.spec=dict(offset=6,size=6,compression='zlib',compressed_size=len(self.packed),expanded_size=len(self.body),payload_offset=7)

    def test_reads_exact_decoded_subrange(self):
        self.assertEqual(resource_slice(self.container,self.spec),b'pixels')
        self.assertEqual(resource_slice(b'prefixpixels',dict(offset=6,size=6)),b'pixels')

    def test_rejects_boundaries_and_codec(self):
        for field,value in [('offset',-1),('offset',True),('compressed_size',999),('expanded_size',128*1024*1024+1),('expanded_size',len(self.body)-1),('payload_offset',999),('compression','other')]:
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                resource_slice(self.container,dict(self.spec,**{field:value}))

    def test_rejects_truncated_trailing_or_corrupt_stream(self):
        for body in [self.packed[:-1],self.packed+b'junk',b'x'*len(self.packed)]:
            with self.subTest(body=body),self.assertRaises(ValueError):
                resource_slice(b'prefix'+body,dict(self.spec,compressed_size=len(body)))
