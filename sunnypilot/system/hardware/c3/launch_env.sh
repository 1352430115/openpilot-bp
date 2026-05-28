#!/usr/bin/env bash

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1

# BluePilot: C3 default AGNOS 16 (same target as C3X)
if [ -z "$AGNOS_VERSION" ]; then
  export AGNOS_VERSION="16"
fi
# End BluePilot

export STAGING_ROOT="/data/safe_staging"
