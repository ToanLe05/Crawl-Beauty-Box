#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Can Python 3.10 tro len"'
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
./.venv/bin/python -m pip install -r requirements.txt
mode="${1:-run}"
if [[ "$mode" == "check" ]]; then
  ./.venv/bin/python -u crawl_all_beautybox.py --check --output beautybox_check --resume
else
  ./.venv/bin/python -u crawl_all_beautybox.py --output beautybox_browser --resume
fi
