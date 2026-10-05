#!/usr/bin/env python3
"""
Downloads LinTim datasets from the official OpenLinTim GitLab repository.
Datasets downloaded: toy, mandl, grid, sioux_falls, athens
"""

import os
import urllib.request
import ssl
import subprocess
import sys

BASE_URL = "https://gitlab.com/lintim/openlintim/-/raw/master/datasets"
DATASETS = ["toy", "mandl", "grid", "sioux_falls", "athens"]
COMMON_FILES = ["basis/Stop.giv", "basis/Edge.giv", "basis/OD.giv", "basis/Config.cnf"]
OPTIONAL_FILES = ["basis/Load.giv", "basis/Pool.giv", "basis/Pool-Cost.giv", "basis/Demand.giv"]

# SSL context for macOS system python
ssl_ctx = ssl._create_unverified_context()

def download_file(url: str, dest_path: str) -> bool:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ssl_ctx) as response:
            if response.status == 200:
                with open(dest_path, 'wb') as f:
                    f.write(response.read())
                return True
        return False
    except Exception:
        # Fallback to curl
        cmd = ["curl", "-s", "-f", "-o", dest_path, url]
        res = subprocess.run(cmd)
        return res.returncode == 0

def main():
    target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    print(f"Target data directory: {target_dir}")

    # Also download Global-Config.cnf
    global_cfg_url = f"{BASE_URL}/Global-Config.cnf"
    global_cfg_dest = os.path.join(target_dir, "Global-Config.cnf")
    if download_file(global_cfg_url, global_cfg_dest):
        print("  Downloaded Global-Config.cnf")

    for ds in DATASETS:
        print(f"\nProcessing dataset: {ds}")
        ds_dir = os.path.join(target_dir, ds)
        for rel_file in COMMON_FILES + OPTIONAL_FILES:
            url = f"{BASE_URL}/{ds}/{rel_file}"
            dest = os.path.join(ds_dir, rel_file)
            success = download_file(url, dest)
            if success:
                size = os.path.getsize(dest)
                print(f"  + {rel_file} ({size} bytes)")
            elif rel_file in COMMON_FILES:
                print(f"  - Missing expected file: {rel_file} from {url}")

    print("\nDownload complete!")

if __name__ == "__main__":
    main()
