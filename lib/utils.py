import subprocess

# import os
from pathlib import Path
import urllib.request


def shell_exec(*_args, **kwargs):
    result = subprocess.run(_args, stdout=subprocess.PIPE)

    if kwargs.get("verbose", False):
        print(f"Shell output: {result.stdout}")

    if result.returncode != 0:
        print(f"Error? f{result}")

    return result.stdout.decode().rstrip()


def average_by_index(two_d_array):
    sums = two_d_array[0]
    for a in two_d_array[1:]:
        for ind, v in enumerate(a):
            sums[ind] += v

    averages = [s / len(two_d_array) for s in sums]
    return averages


def format_float(f):
    return "{:10.2f}".format(f)


def local_application_file(app, path):
    local_path = f"/tmp/srt/{app}/{path}"

    url = (
        "https://raw.githubusercontent.com"
        "/NYPL/search-relevance-tests/refs/heads/main"
        f"/applications/{app}/{path}"
    )
    print(f"Loading {path} from {url}")
    download_file(
        url,
        local_path,
    )
    return local_path


def download_file(url, local_path):
    path = Path(local_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    source = urllib.request.urlopen(url)
    with open(local_path, "wb") as f:
        f.write(source.read())
