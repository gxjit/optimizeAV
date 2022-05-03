from argparse import ArgumentParser
from functools import partial
from os import environ
from pathlib import Path
from platform import machine, system
from shutil import make_archive
from subprocess import run
from tempfile import TemporaryDirectory


def parseArgs():
    parser = ArgumentParser()
    buildSelect = parser.add_mutually_exclusive_group(required=True)
    buildSelect.add_argument("-pi", "--pyinst", action="store_true")
    buildSelect.add_argument("-n", "--nuitka", action="store_true")
    parser.add_argument("-o", "--onefile", action="store_true")

    return parser.parse_args()


pargs = parseArgs()

platformStr = f"{system()}_{machine()}".lower()

if pargs.nuitka:
    platformStr = f"n_{platformStr}"

if pargs.onefile:
    platformStr = f"o_{platformStr}"


rootPath = Path.cwd()
appEntry = rootPath.joinpath("optimizeAV.py")
td = TemporaryDirectory(ignore_cleanup_errors=False)
tempRoot = Path(td.name)
buildPath = tempRoot.joinpath("build")
tempPath = tempRoot.joinpath("tmp")
distDir = (
    Path(environ.get("dist_dir")) if environ.get("dist_dir") else rootPath
).joinpath("dist")
zipPath = distDir.joinpath(f"{appEntry.stem}_{platformStr}").with_suffix(".zip")

runP = partial(run, shell=True, check=True)


if system() == "Linux":
    if pargs.pyinst:
        aptDeps = "upx"
        runP(f"sudo apt-get install -y {aptDeps}")

# if pargs.pyinst:
#     if system() == "Windows":
#         runP("choco install upx")

if pargs.pyinst:
    pipDeps = "pyinstaller"
elif pargs.nuitka:
    pipDeps = "nuitka zstandard"

runP(f"pip install -U --user {pipDeps}")

if pargs.pyinst:
    cmd = (
        f"pyinstaller -y --distpath {buildPath} --workpath {tempPath} "
        f"--specpath {tempPath} --clean --onedir {appEntry}"
    )
elif pargs.nuitka:
    cmd = (
        "python -m nuitka --standalone --assume-yes-for-downloads "
        f"--output-dir={buildPath} --remove-output {appEntry}"
    )


if pargs.onefile and pargs.pyinst:
    cmd = cmd.replace("--onedir", "--onefile")
elif pargs.onefile and pargs.nuitka:
    cmd = cmd.replace("--standalone", "--onefile")

if zipPath.exists():
    zipPath.unlink()

runP(cmd)

if pargs.nuitka and not pargs.onefile:
    buildPath.joinpath(f"{appEntry.stem}.dist").rename(
        buildPath.joinpath(f"{appEntry.stem}")
    )

distDir.mkdir()

make_archive(zipPath.with_suffix(""), "zip", buildPath)

td.cleanup()

# build log
