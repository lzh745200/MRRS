#!/usr/bin/env bash
# W24 本地最终验证：复跑 CI 6 段后端测试（与 pr-checks.yml 同口径）
set -uo pipefail
cd "/c/military-Rural Revitalization-system/backend"
export PATH="/c/military-Rural Revitalization-system/backend/.venv/Scripts:$PATH"
export RUNNER_TEMP="/tmp/w24segs"
mkdir -p "$RUNNER_TEMP"

runseg() {
  local name="$1" mode="$2"; shift 2
  echo "===== SEGMENT $name start $(date -u +%H:%M:%S) args=$# ====="
  bash "../scripts/ci_backend_test_segment.sh" --name "$name" --mode "$mode" "$@"
  local code=$?
  echo "===== SEGMENT $name done exit=$code $(date -u +%H:%M:%S) ====="
  if [ $code -ne 0 ]; then echo "BACKEND_FAILED_SEGMENT=$name"; exit $code; fi
}

runseg seg1-integration first tests/integration tests/security
runseg seg2-unit-api partial tests/unit/api
runseg seg3-unit-services partial tests/unit/services tests/unit/middleware tests/unit/interfaces tests/unit/utils
runseg seg4-unit-root-a partial tests/unit/test_{a,e,f,i,n,o,p,t,u,w,y,z}*.py
runseg seg5-unit-root-b partial tests/unit/test_{b,d,g,h,j,l,m,q,s}*.py
runseg seg6-unit-root-c final tests/unit/test_{c,r,v}*.py
echo "BACKEND_ALL_SEGMENTS_PASSED"
