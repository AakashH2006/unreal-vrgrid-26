"""What produced this export -- recorded, not reconstructed later.

A baked scene outlives the shell it was baked in. Six weeks on, "which vrgrid
built this?" and "did Patchwork++ actually run, or did it fall back?" are the
two questions that decide whether a scene can be shown, and neither is
answerable from the `.vrgf` files. So they go in the manifest at bake time.

⚑ NOTHING HERE GUESSES. Every field is read from the running process or from
  the checkout on disk. Where a fact cannot be established -- vrgrid installed
  from a wheel rather than a git checkout, `git` not on PATH, `pypatchworkpp`
  absent -- the value is `null` and `note` says why. A plausible-looking SHA
  that was inferred rather than read is worse than no SHA at all: it would be
  believed.

This module deliberately imports nothing from `vrgrid` at module scope, so it
can be tested (and can report its own failure) on a machine where the pipeline
is not installed.
"""

import os
import subprocess
import sys


def _run_git(root, *args, timeout=15):
    """`(stdout, None)` or `(None, reason)`. Never raises."""
    try:
        proc = subprocess.run(
            ["git", "-C", root, *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        return None, "git is not on PATH"
    except (subprocess.SubprocessError, OSError) as exc:
        return None, f"git failed: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or "").strip() or \
            f"git exited {proc.returncode}"
    return proc.stdout.strip(), None


def _vrgrid_checkout():
    """Where the IMPORTED vrgrid package's source lives, or `(None, reason)`.

    The package is laid out by owner and remapped through
    `[tool.setuptools.package-dir]`, so `vrgrid.__file__` is
    `<checkout>/include/vrgrid/__init__.py` in an editable install. Rather
    than assume that depth, hand the directory to `git -C` and let git walk up
    to whatever repository contains it -- which also means a non-editable
    install simply reports "not a git checkout" instead of a wrong answer.
    """
    try:
        import vrgrid
    except Exception as exc:                                # pragma: no cover
        return None, f"vrgrid is not importable: {type(exc).__name__}: {exc}"
    path = getattr(vrgrid, "__file__", None)
    if not path:
        return None, "vrgrid has no __file__ (namespace package?)"
    return os.path.dirname(os.path.abspath(path)), None


def _vrgrid_git():
    source, reason = _vrgrid_checkout()
    block = {"commit": None, "dirty": None, "source": source, "note": None}
    if source is None:
        block["note"] = reason
        return block

    top, reason = _run_git(source, "rev-parse", "--show-toplevel")
    if top is None:
        block["note"] = f"not a git checkout ({reason})"
        return block
    block["source"] = os.path.abspath(top)

    commit, reason = _run_git(source, "rev-parse", "HEAD")
    if commit is None:
        block["note"] = f"could not read HEAD ({reason})"
        return block
    block["commit"] = commit

    # `--untracked-files=no`: a build artefact or a stray scratch file sitting
    # beside the source is not a difference in the code that ran, and marking
    # every bake dirty for one would make the flag mean nothing.
    status, reason = _run_git(source, "status", "--porcelain", "--untracked-files=no")
    if status is None:
        block["note"] = f"commit read, but working tree state unknown ({reason})"
        return block
    block["dirty"] = bool(status)
    return block


def _distribution_version(dist_name, module_name=None):
    """Installed version of a distribution, or `(None, reason)`."""
    try:
        from importlib import metadata
    except ImportError:                                     # pragma: no cover
        return None, "importlib.metadata is unavailable"
    try:
        return metadata.version(dist_name), None
    except metadata.PackageNotFoundError:
        return None, f"{dist_name} is not installed"
    except Exception as exc:                                # pragma: no cover
        return None, f"{dist_name} version unreadable: {type(exc).__name__}: {exc}"


def _patchworkpp(use_patchworkpp):
    """Requested, available, and therefore actually used.

    Three fields rather than one, because they fail apart: asking for
    Patchwork++ on a machine that does not have it is silent at the call site
    -- `ground.segment_ground_or_fallback` swaps in the semantic proxy, which
    is NOT equivalent (it admits raised terrain the geometric segmenter
    rejects). A scene baked that way is still a valid scene; it is just not
    the same ground, and the manifest has to say which one it was.
    """
    version, version_note = _distribution_version("pypatchworkpp")
    block = {
        "requested": bool(use_patchworkpp),
        "available": None,
        "used": None,
        "pypatchworkpp_version": version,
        "note": version_note,
    }
    try:
        from vrgrid.perception import ground
    except Exception as exc:
        block["note"] = f"vrgrid.perception.ground not importable: " \
                        f"{type(exc).__name__}: {exc}"
        return block
    block["available"] = bool(ground._HAVE_PATCHWORKPP)
    block["used"] = bool(use_patchworkpp) and bool(ground._HAVE_PATCHWORKPP)
    return block


#: The parameter has been spelled both ways upstream, and the two are live at
#: the same time: `vrgrid-26` main carries `semantic_source`, while the branch
#: installed on this machine at the time of writing (`jp/p99-alloc-fixes`)
#: carries `semantics_source`. Both default to "gt". Try them in that order and
#: record WHICH one was found, so the manifest never leaves it ambiguous.
_SEMANTIC_SOURCE_PARAMS = ("semantic_source", "semantics_source")


def semantic_source_in_use(override=None):
    """`(value, note, parameter_name)` -- what `iter_pipeline` will label with.

    `export_scene.py` does not pass the argument, so the value is
    `iter_pipeline`'s own default -- read out of the live signature rather
    than written down here. Hardcoding "gt" would be right today and silently
    wrong the day upstream changes the default, which is exactly the class of
    drift this block exists to catch.
    """
    if override is not None:
        return str(override), None, "explicit argument"
    try:
        import inspect

        from vrgrid.run.__main__ import iter_pipeline
    except Exception as exc:
        return None, f"iter_pipeline not importable: {type(exc).__name__}: {exc}", None
    try:
        params = inspect.signature(iter_pipeline).parameters
    except (ValueError, TypeError) as exc:
        return None, f"iter_pipeline signature unreadable: {exc}", None
    for name in _SEMANTIC_SOURCE_PARAMS:
        param = params.get(name)
        if param is None:
            continue
        if param.default is inspect.Parameter.empty:
            return None, f"{name} has no default and none was passed", name
        return str(param.default), None, name
    return None, ("iter_pipeline has none of "
                  + "/".join(_SEMANTIC_SOURCE_PARAMS)), None


def collect(*, use_patchworkpp=True, semantic_source=None, rrd=False, argv=None):
    """The `provenance` block for `scene.json`.

    `rrd` says whether this bake also wrote a Rerun recording; the rerun-sdk
    version is only meaningful when it did, because that is the only case in
    which the SDK touched the output.
    """
    source, source_note, source_param = semantic_source_in_use(semantic_source)

    rerun_version = None
    rerun_note = "no .rrd written by this bake"
    if rrd:
        rerun_version, rerun_note = _distribution_version("rerun-sdk")

    return {
        "vrgrid": _vrgrid_git(),
        "patchworkpp": _patchworkpp(use_patchworkpp),
        "semantic_source": source,
        "semantic_source_param": source_param,
        "semantic_source_note": source_note,
        "rerun_sdk": rerun_version,
        "rerun_sdk_note": rerun_note,
        "rrd": bool(rrd),
        "python": sys.version.split()[0],
        "argv": list(argv) if argv is not None else list(sys.argv),
    }
