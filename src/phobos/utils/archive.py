import datetime
import os
import sys
import shutil
import subprocess
from pathlib import Path

import yaml

try:
    import git  # type: ignore
except Exception:  # pragma: no cover
    git = None

number = None

def next_number(path):
    global number
    max_num = 0
    for file in os.listdir(path):
        if "_" in file: file = file.split("_")[0]
        try:
            if int(file) > max_num: max_num = int(file)
        except: pass
    number = max_num + 1
    return number

def _try_get_git_commit(root_dir: Path | None = None) -> str | None:
    """Return the short git commit hash if available, otherwise None."""
    try:
        cwd = str(root_dir) if root_dir is not None else None
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
        ).decode("ascii").strip()
        return commit or None
    except Exception:
        return None


def _resolve_archive_base_path(user_path: str | os.PathLike | None) -> Path | None:
    """Resolve the base archive path.

    Priority:
    1) user_path if provided
    2) config['archive_path'] if present
    3) None (meaning: current directory)
    """
    if user_path is not None:
        return Path(user_path).expanduser()

    try:
        import phobos

        cfg_path = phobos.config.get("archive_path", None)
        if cfg_path:
            return Path(cfg_path).expanduser()
    except Exception:
        # phobos import may fail in some contexts; silently fallback.
        pass

    return None


def new(
    name: str | None = None,
    base_path: str | os.PathLike | None = None,
    verbose: bool = False,
    **kwargs,
) -> Path:
    """Create a new archive folder and return its path.

    Parameters
    ----------
    name : str or None, optional
        Optional suffix to include in the archive folder name.
    base_path : str | os.PathLike | None, optional
        Base directory where archives are created.
        If None, uses ``config/bench.yml`` key ``archive_path`` when defined.
        If not defined, creates the archive in the current directory.
    verbose : bool, optional
        If True, prints the created archive path.
    **kwargs
        Extra metadata used to build a description suffix.

    Returns
    -------
    pathlib.Path
        Path to the created archive folder.
    """
    global number

    base_dir = _resolve_archive_base_path(base_path)

    if kwargs:
        if name is None:
            name = description(**kwargs)
        else:
            name = name + "-" + description(**kwargs)

    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    # Keep compatibility with previous behavior: include commit suffix in date folder.
    sha_suffix = ""
    repo_root = None
    if git is not None:
        try:
            repo = git.Repo(search_parent_directories=True)
            sha_suffix = "_" + repo.head.object.hexsha[:7]
            repo_root = Path(repo.working_tree_dir)
        except Exception:
            sha_suffix = ""
            repo_root = None

    if base_dir is None:
        day_dir = Path("./archives") / f"{date_str}{sha_suffix}"
    else:
        day_dir = base_dir / f"{date_str}{sha_suffix}"

    day_dir.mkdir(parents=True, exist_ok=True)

    next_number(str(day_dir))

    suffix = f"_{name}" if name else ""
    archive_dir = day_dir / f"{number}{suffix}"
    archive_dir.mkdir(parents=True, exist_ok=False)

    # Copy the bench.yml used by the repo into the archive when available.
    bench_src = None
    if repo_root is not None:
        candidate = repo_root / "config" / "bench.yml"
        if candidate.exists():
            bench_src = candidate
    else:
        candidate = Path.cwd() / "config" / "bench.yml"
        if candidate.exists():
            bench_src = candidate

    if bench_src is not None:
        shutil.copy2(bench_src, archive_dir / "bench.yml")

    # Create metadata.yml
    metadata = {
        "created_at": now.isoformat(timespec="seconds"),
        "git_commit": _try_get_git_commit(repo_root),
        "script": getattr(sys.modules.get("__main__"), "__file__", None),
    }

    with open(archive_dir / "metadata.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump(metadata, f, sort_keys=False)

    if verbose:
        print(f"Archive created at {archive_dir}")

    return archive_dir

def description(**kwargs):
    desc = ""
    for key,value in kwargs.items():
        if type(value) in [int, str, float, bool] : desc += f",{key}={value}"
        else: print(f"⚠️ Your archive description contain a non-supported type: {type(value)}")
    return desc[1:]
