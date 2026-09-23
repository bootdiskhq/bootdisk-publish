# Embedded image publication

`python -m bootdisk_publish.embedded IMAGES_JSON INGEST_MANIFEST --output NEW_ROOT`
consumes Ingest's `bootdisk-embedded-images-1` preservation bundle. It does not
search the media, open executables or discover resources in Director files.

Before decoding, it checks the exact original ingest manifest, entry association,
container inventory identity, whole preserved container hash, every resource hash
and the resource's exact byte slice within its container. The declared indexed
raster codec is bounded to 4096 rows/stride and 16 MiB expanded data; truncation,
overflow and unsupported palettes fail. Padding is removed by row. All 256 palette
colors use the high bytes of their original 16-bit RGB channels. Original BITD
bytes stay immutable; PNG derivatives retain both pixel and palette hashes.

Output is staged and published only to a new directory. The public store contains
selected pixel resources and PNG derivatives, not the full source archives.
Palette/metadata/container preservation stays in the local Ingest bundle. Identical
pixel bytes remain one object even when several menu entries reference them.
No software identity, version, edition or approval is inferred from an image.
