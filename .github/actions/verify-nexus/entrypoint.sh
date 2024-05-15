#!/bin/sh -l
echo "$1,$2,$3,$4,$5,$6"
/imginfo/imginfo  $1
echo "imginfo_exit_code=$?" >> "$GITHUB_OUTPUT"