from argparse import ArgumentParser

# from functools import partial
from itertools import islice
from os import environ
from pathlib import Path
from platform import machine, system
from shlex import split
from shutil import make_archive, which, copytree
from subprocess import run as r
from sys import version_info
from tempfile import TemporaryDirectory
from zipapp import create_archive as zipapp


def parseArgs():
    parser = ArgumentParser()
    buildSelect = parser.add_mutually_exclusive_group(required=True)
    buildSelect.add_argument(
        "-p", "--pyinst", action="store_true", help="PyInstaller standalone build."
    )
    buildSelect.add_argument(
        "-n",
        "--nuitka",
        action="store_true",
        help="Nuitka ahead of time compiled standalone build.",
    )
    buildSelect.add_argument(
        "-z", "--zipapp", action="store_true", help="Zipapp bundle."
    )
    parser.add_argument(
        "-o",
        "--onefile",
        action="store_true",
        help="Onefile build for nuitka and PyInstaller.",
    )
    parser.add_argument(
        "-i",
        "--python",
        action="store_true",
        help="Builds that requires python interpreter to be installed on host system.",
    )
    parser.add_argument(
        "-d", "--deps", action="store_true", help="Install dependencies only and exit."
    )

    return parser.parse_args()


pargs = parseArgs()


def take(n, itr):
    return list(islice(itr, n))


def head(itr):
    return list(islice(itr, 1))[0]


run = lambda c: r(split(c), check=True)


def addNotWhich(dep, altCheck=None):
    if altCheck:
        return dep if not which(altCheck) else ""
    else:
        return dep if not which(dep) else ""


def mkdirNotExists(pth: Path):
    if not pth.exists():
        pth.mkdir()


acceptedExts = (".py", ".pyc")


def zipFilter(pth: Path):
    if pth.suffix in acceptedExts:
        if not any(
            [(p.name.startswith("_") or p.name.startswith(".")) for p in pth.parents]
        ):
            return True
        else:
            return False
    else:
        return False


def copyFilter(pth, names):
    """Returns a list of files to ignore"""
    pth = Path(pth)
    if pth.is_dir():
        if pth.name.startswith("_") or pth.name.startswith("."):
            return [str(p.relative_to(pth)) for p in pth.glob("*")]
        else:
            return [
                str(f.relative_to(pth))
                for f in pth.glob("*.*")
                if f.suffix not in acceptedExts
            ]
    else:
        []


# Install deps

if system() == "Linux":
    if which("apt-get"):
        if pargs.pyinst:
            aptDeps = (
                f'{addNotWhich("python3")} {addNotWhich("python-is-python3", "python")}'
                f' {addNotWhich("upx")}'
            )
            run(f"sudo apt-get install -y {aptDeps}")

elif system() == "Windows":
    if which("choco"):
        chocoDeps = f'{addNotWhich("python3", "python")}'
        if pargs.pyinst:
            chocoDeps = f'{chocoDeps} {addNotWhich("upx")}'
        chocoDeps = chocoDeps.strip()
        if chocoDeps:
            run(f"choco install {chocoDeps}")
else:
    print("Unsupported target.")
    exit(1)

if pargs.pyinst:
    pipDeps = "pyinstaller"
elif pargs.nuitka:
    pipDeps = "nuitka zstandard"
else:
    pipDeps = ""

if pipDeps:
    run(f"python -m pip install -U --user {pipDeps}")

if pargs.deps:
    exit()

# Build Setup

distRoot = Path.cwd()
td = TemporaryDirectory(ignore_cleanup_errors=True)
buildRoot = Path(td.name)
appEntry = buildRoot / "optimizeAV.py"  # Entry point
entryFunc = "optimizeAV:exe"  # mod:fn / pkg.mod:fn
buildPath = buildRoot / "build"
tempPath = buildRoot / "tmp"
distDir = (
    Path(environ.get("dist_dir")) if environ.get("dist_dir") else distRoot / "dist"
)

platformStr = f"{system()}_{machine()}".lower()

if pargs.python:
    vmj, vmi, *_ = version_info
    if pargs.zipapp:
        platformStr = f"py{vmj}{vmi}"
    else:
        platformStr = f"py{vmj}{vmi}_{platformStr}"

if pargs.nuitka:
    platformStr = f"aot_{platformStr}"

if pargs.onefile:
    platformStr = f"onefile_{platformStr}"


zipPath = (distDir / f"{appEntry.stem}_{platformStr}").with_suffix(".zip")

sfx = ".exe" if system() == "Windows" else ""

if pargs.pyinst:
    cmd = (
        f"python -m PyInstaller -y --strip "
        f'--distpath "{buildPath}" --workpath "{tempPath}" '
        f'--specpath "{tempPath}" --clean --onedir "{appEntry}"'
    )
    if pargs.onefile:
        cmd = cmd.replace("--onedir", "--onefile")

elif pargs.nuitka:
    cmd = (
        "python -m nuitka --standalone --assume-yes-for-downloads "
        f'--output-dir="{buildPath}" --remove-output "{appEntry}"'
    )
    if pargs.onefile:
        cmd = cmd.replace("--standalone", "--onefile")
    if pargs.python:
        cmd = cmd.replace("--standalone", "")
    if pargs.onefile or pargs.python:
        exePath = buildPath / f"{appEntry.stem}{sfx}"
        cmd = f'{cmd} -o "{exePath}"'

elif pargs.zipapp:
    # cmd = (
    #     f'python -m zipapp "{buildRoot}" '
    #     f'-o "{buildPath / appEntry.stem}.pyz" -m {entryFunc}'
    # )
    build = lambda: zipapp(
        buildRoot,
        (buildPath / appEntry.stem).with_suffix(".pyz"),
        main=entryFunc,
        filter=zipFilter,
    )


if zipPath.exists():
    zipPath.unlink()

# Build

copytree(Path.cwd(), buildRoot, dirs_exist_ok=True, ignore=copyFilter)

for d in [distDir, buildPath, tempPath]:
    mkdirNotExists(d)

if pargs.zipapp:
    build()
else:
    run(cmd)

if len(take(1, buildPath.iterdir())) < 1:
    print("Build directory is empty.")
    exit(1)

if pargs.nuitka and not (pargs.onefile or pargs.python):
    nPath = head(buildPath.glob("*.dist"))
    nPath = nPath.rename(buildPath / f"{appEntry.stem}")

    # exePath = head(nPath.glob(f'{appEntry.stem}{sfx}'))
    # exePath.rename(nPath / f"{data.appTitle}{sfx}")


make_archive(zipPath.with_suffix(""), "zip", buildPath)

td.cleanup()

# build log
# 7zip compression?
# sudo in docker?
