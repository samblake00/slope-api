#!/usr/bin/env bash
# Builds ./build: the service plus Linux arm64 dependencies and the Lambda handlers.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf build
mkdir build
python -m pip install -r service/requirements.txt --target build \
  --platform manylinux2014_aarch64 --implementation cp --python-version 3.12 \
  --only-binary=:all: --upgrade --quiet
cp -r service/app service/config.py build/
cp lambdas/lambda_handlers.py build/
find build -name '__pycache__' -type d -prune -exec rm -rf {} +