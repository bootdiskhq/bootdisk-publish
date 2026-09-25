# Workshop artwork resources

Embedded publication accepts an explicit `compression: zlib` resource locator with `offset`, `compressed_size`, `expanded_size` and `payload_offset`. The original container must match the ingest inventory; the bounded, fully consumed zlib stream must produce exactly the declared bytes, and its subrange must match the preserved resource hash. Hashes are never calculated from recompressed containers.

The new `argb32-d6-rle257-or-raw` raster encoding supports D6 BITD artwork with no palette. Uncompressed bytes are interleaved ARGB; compressed bytes expand into planar A/R/G/B rows. The reserved first channel is discarded and output is opaque RGB, following the qualified D6 format. Dimensions, runs, expansion, truncation and stream boundaries are validated before any output is committed. Existing indexed8 encoding is unchanged.

Validation: 52 unit tests passed; six mounted-CD reports published 162 original shelf artworks (146 indexed8, 16 direct color). All 16 direct-color derivatives were visually inspected in a contact sheet. These are menu artwork, not application screenshots. Original bytes and derivative provenance remain separate. No historical application was executed.
