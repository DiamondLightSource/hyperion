Test files for nexus reading
---
This folder contains test files for the test_nexgen system test.

Each folder contains:
* A text file with the expected output from `imginfo`
* A gzipped meta file that has been run through the `utility_scripts/strip_metafile.py` program.

The metafiles have the `/mask` and `/flatfield` datasets compressed and removed respectively.
The file is then gzipped to compress it further.
