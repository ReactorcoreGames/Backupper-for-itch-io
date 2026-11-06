"""Zip a release folder, keeping the folder itself as the zip's root.

    python tools/make_zip.py dist Backupper-for-itch-io
"""

import shutil
import sys
from pathlib import Path


def main():
    dist, name = Path(sys.argv[1]), sys.argv[2]
    archive = shutil.make_archive(str(dist / name), "zip", root_dir=dist, base_dir=name)
    print(f"Wrote {archive}")


if __name__ == "__main__":
    main()
