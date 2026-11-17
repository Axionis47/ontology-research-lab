import subprocess,sys
from pathlib import Path
p=Path(__file__).resolve()
raise SystemExit(subprocess.call([sys.executable,str(p.parents[1]/"run.py"),"--experiment",p.parent.name[:2],*sys.argv[1:]]))
