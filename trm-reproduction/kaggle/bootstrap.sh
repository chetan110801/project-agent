#!/usr/bin/env bash
# Kaggle notebook bootstrap for the TRM reproduction (Sudoku-Extreme track).
# DRAFT — written 2026-07-21 before the first Kaggle run; expect to adjust.
# Usage in a Kaggle notebook cell:   !bash bootstrap.sh
set -euo pipefail

# 1. Code. Upstream is archived (read-only) — switch this URL to Chetan's fork
#    once it exists, so the dependency can't vanish.
TRM_REPO="${TRM_REPO:-https://github.com/SamsungSAILMontreal/TinyRecursiveModels.git}"
if [ ! -d TinyRecursiveModels ]; then
  git clone "$TRM_REPO"
fi
cd TinyRecursiveModels

# 2. Dependencies. Kaggle images ship a recent torch+CUDA; try the repo's
#    requirements against it before pulling the nightly wheel the README suggests.
pip install -q -r requirements.txt
pip install -q --no-cache-dir --no-build-isolation adam-atan2

# 3. No W&B account on the free path — keep runs local.
export WANDB_MODE=offline

# 4. Sudoku-Extreme dataset, exactly the paper's build (README-verbatim):
python dataset/build_sudoku_dataset.py \
  --output-dir data/sudoku-extreme-1k-aug-1000 \
  --subsample-size 1000 --num-aug 1000

echo "Bootstrap done. Training command comes from the repo README (Sudoku section),"
echo "with single-GPU/T4x2 adjustments recorded in trm-reproduction/README.md."
# Deliberately not guessing the train command here: copy it from the forked repo's
# README at run time, then freeze it into this script once it has actually worked.
