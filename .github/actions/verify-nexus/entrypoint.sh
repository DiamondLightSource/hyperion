#!/bin/sh -l
echo "Contents of /github/workspace:"
ls /github/workspace
echo "current dir: $(pwd)"
echo "Running imginfo on $1"
/imginfo/imginfo  $1 >> imginfo_out_file 2>> imginfo_err_file
{ echo "imginfo_output<<EOF"
  cat imginfo_out_file
  echo EOF
} >> "$GITHUB_OUTPUT"
{ echo "imginfo_output<<EOF"
  cat imginfo_err_file
  echo EOF
} >> "$GITHUB_OUTPUT"
echo "imginfo_exit_code=$?" >> "$GITHUB_OUTPUT"
echo "------------- IMGINFO STDOUT -------------"
cat imginfo_out_file
echo "------------- IMGINFO STDERR -------------"
cat imginfo_err_file
echo "------------------------------------------"
if [ -s imginfo_err_file ]; then
  echo "ERRORS IN IMGINFO PROCESSING"
  exit 1
fi