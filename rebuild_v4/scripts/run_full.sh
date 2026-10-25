#!/bin/zsh
# Full v4 run over 10,000 reviews. Resumable (extract.py skips finished rows).
set -e
cd /Users/liliu/SER-DB/rebuild_v4
python3 scripts/extract.py --workers 40 --out data/raw_extractions_v4.jsonl
python3 scripts/check.py data/raw_extractions_v4.jsonl
python3 scripts/ground.py data/raw_extractions_v4.jsonl data/grounded_v4.jsonl
python3 scripts/verify.py data/grounded_v4.jsonl data/verified_v4.jsonl
echo DONE
