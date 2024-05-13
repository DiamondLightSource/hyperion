#!/bin/sh -l
cp tests/test_data/ins_8_5.nxs gda_reference_test.h5
/imginfo/imginfo  gda_reference_test.h5
echo "imginfo_output=BLABLABLA" >> "$GITHUB_OUTPUT"