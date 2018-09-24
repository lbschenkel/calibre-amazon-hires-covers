#!/bin/sh
set -e

VERSION=$(git describe --tags --dirty)
ZIP="Kindle hi-res covers (${VERSION}).zip"

mkdir -p out
zip -9q out/"${ZIP}" *.py *.md
echo Generated ${ZIP}
