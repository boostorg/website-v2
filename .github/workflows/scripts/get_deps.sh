#!/bin/bash
# Expected to be run from within the boost super-repo
# Loop through all the boost-x.x.0 tags and run `dist/bin/boostdep --list-dependencies --track-sources` on it.
#   Append output to a file given by the user from the command line
#
# Ex: get_deps.sh /tmp/output.txt

# Exit on any error
set -e

# Exit on undefined variable
set -u

# Print commands as they execute (debug mode)
set -x

# Exit on pipe failures
set -o pipefail

output_file=$1
echo "Creating $output_file"
> $output_file
# Loop through all tags of the form "boost-x.x.0"
for tag in $(git tag | grep -E 'boost-[0-9]+\.[0-9]+\.0$'); do
    git checkout $tag --force
    git submodule update --init --force
    git clean -dff -e dist  # -d recurses through directories, -ff 2 f's to delete files in submodules, do not delete boostdep executable
    echo "Dependencies for version $tag" | tee -a $output_file
    dist/bin/boostdep --list-dependencies --track-sources | tee -a $output_file || continue
done
