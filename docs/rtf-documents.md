# Supplemental original RTF documents

This delivery keeps immutable ingest manifests and existing Catalog decisions
unchanged. Additional source observations are separate, content-bound documents.
It does not migrate review state or replace menu descriptions.

1. Ingest: `python -m bootdisk_ingest.rtf_documents MANIFEST SOURCE_ROOT --output OBSERVATIONS`.
   Only explicit `files.discovered.description_rtf` bindings are used, checked
   against inventory, path containment and actual SHA-256/size. No directory-name
   identity guesses. Sources over 1 MiB or unreadable files become issues. Changed
   bytes fail the operation. Unsupported text retains original bytes and a warning.
2. Catalog: `python -m bootdisk_catalog.source_documents MANIFEST OBSERVATIONS`.
   Validates the original manifest binding, entry, pointer, inventory and bytes,
   and includes the immutable observation-document hash. Text is an Ingest
   observation, not approved editorial content or an independently re-decoded fact.
3. Publish: `python -m bootdisk_publish.documents PROJECTION --output ROOT --manifest-output JSON`.
   Verifies and writes originals to store/documents/sha256/xx/<hash>.rtf, reuses only
   matching bytes and never executes content. Public projection omits base64 bytes.
4. Web: `scripts/attach-source-documents.py DATA PUBLICATION... --output NEW_DATA`.
   Exact manifest+entry joins; mismatch/duplicates fail. Original description,
   software identities and status remain unchanged. The public build includes
   referenced originals, and HTTP verification checks their hashes.

Schema names: bootdisk-rtf-observations-1, bootdisk-source-documents-1,
bootdisk-published-documents-1. Source fields: key {manifest,entry}, pointer, path,
sha256, size, method, text (string|null), warning. Original bytes remain authoritative.
The text method rtf-ansi-text-terminal-nul-1 accepts a single terminal NUL after
an otherwise complete ANSI RTF stream; it does not interpret embedded objects,
external links or binary content. Original bytes are never trimmed in storage.

Qualification on existing 2001 media: 103 bound RTF documents, 102 readable text
observations and one unsupported font charset. 102 unique original files because
two source bindings share bytes. Menu wording and existing source identity remain
unchanged. Files without an explicit binding are outside this delivery.

Frontend is a draft for Claude's reading/accessibility pass. No public deployment,
version bump or video player. Video courses wait for newer discs containing them.
