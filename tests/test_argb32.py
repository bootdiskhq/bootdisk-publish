import unittest
from io import BytesIO
from PIL import Image
from bootdisk_publish.embedded import decode_argb32

class DirectColorTests(unittest.TestCase):
    layout={'width':2,'height':2,'row_stride':8,'encoding':'argb32-d6-rle257-or-raw'}
    def test_raw_interleaved_and_compressed_planar_have_same_colors(self):
        raw=bytes([0,255,0,0,0,0,255,0,0,0,0,255,0,255,255,255])
        planar=bytes([0,0,255,0,0,255,0,0,0,0,0,255,0,255,255,255])
        packed=bytes([15])+planar
        for data in (raw,packed):
            im=Image.open(BytesIO(decode_argb32(data,self.layout)))
            self.assertEqual(list(im.getdata()),[(255,0,0),(0,255,0),(0,0,255),(255,255,255)])
    def test_bad_runs_and_layouts_fail(self):
        for data in (b'',b'\x0f\x00',b'\x80\x00',b'\xff'):
            with self.assertRaises(ValueError):decode_argb32(data,self.layout)
        with self.assertRaises(ValueError):decode_argb32(bytes(16),{**self.layout,'row_stride':9})
