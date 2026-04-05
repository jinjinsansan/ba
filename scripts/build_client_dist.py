"""LAPLACE Client Distribution Builder

Reads `.dist_excludes` at the repo root and produces a sanitised
`dist_client/` directory containing only the files that are safe to ship.

The build runs 3 automated checks:

    1. Pattern matcher. Every path in the source tree is tested against
       `.dist_excludes` patterns (filename globs, directory prefixes,
       full path globs). Matches are excluded.

    2. Canary file check. A hard-coded list of sensitive filenames
       (marubatsu_strategy.py etc.) must NOT appear in the output.
       If any slip through, the build fails.

    3. Canary string check. The output is scanned for a small set of
       forbidden strings (SEQ = [, compute_score, _compute_regularity,
       PLAYERS_PRIMARY =, etc.). If any are found, the build fails.

    4. Import smoke test. laplace_client and agent_api are imported
       from the output directory with nothing else on PYTHONPATH. Any
       ImportError for a server-only module means we forgot to make
       something lazy.

Usage:
    python scripts/build_client_dist.py
    python scripts/build_client_dist.py --out custom_dir
    python scripts/build_client_dist.py --verbose
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# =============================================================================
# Canaries — files and strings that MUST NOT appear in the output distribution
# =============================================================================

CANARY_FILES = [
    "marubatsu_strategy.py",
    "marubatsu_bet.py",
    "table_selector.py",
    "shoe.py",
    "strategy.py",
    "laplace_api.py",
    "laplace_bet_runner.py",
    "bot_manager.py",
]

CANARY_STRINGS = [
    # MaruBatsu core sequence (literal array start)
    "SEQ = [",
    # Regularity scoring
    "_compute_regularity",
    "def _compute_regularity",
    # Table selector scoring formula
    "def compute_score",
    "PLAYERS_PRIMARY =",
    "PLAYERS_RELAXED =",
    "DRAGON_LIMIT =",
    "EXCLUDE_TITLE_KEYWORDS",
    # MaruBatsu finalization
    "def finalize_set",
    "def calc_slashed",
    "def calc_next_unit_idx",
    # 1-2-3 strategy
    "class BetStrategy",
]

# Directories that are always pruned, even if not in .dist_excludes
HARD_PRUNE_DIRS = {
    ".git",
    ".claude",
    ".factory",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "dist_client",
    "dist_client_test",
    "build",
}


# =============================================================================
# Manifest parser
# =============================================================================


@dataclass
class ExcludePattern:
    raw: str
    is_dir: bool
    has_path_sep: bool

    @classmethod
    def from_line(cls, line: str) -> "ExcludePattern":
        is_dir = line.endswith("/")
        clean = line.rstrip("/")
        return cls(raw=clean, is_dir=is_dir, has_path_sep="/" in clean)


def parse_manifest(path: Path) -> list[ExcludePattern]:
    patterns: list[ExcludePattern] = []
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(ExcludePattern.from_line(line))
    return patterns


# =============================================================================
# Matcher
# =============================================================================


def match_exclude(rel_path: str, patterns: list[ExcludePattern]) -> ExcludePattern | None:
    """Return the first matching ExcludePattern, or None.

    `rel_path` is POSIX-style (forward slashes), relative to the repo root.
    Directory paths should NOT end with a trailing slash.
    """
    basename = rel_path.rsplit("/", 1)[-1]
    dir_head = rel_path.split("/", 1)[0]
    for p in patterns:
        if p.is_dir:
            # Directory pattern. Supports both literal names and globs.
            if p.has_path_sep:
                # Full path directory, e.g. "gui/node_modules"
                prefix = p.raw + "/"
                if rel_path == p.raw or rel_path.startswith(prefix):
                    return p
            else:
                # Bare directory name, e.g. "data" or "*_dumps".
                # Match if ANY path component matches the glob.
                for part in rel_path.split("/")[:-1] or [dir_head]:
                    if fnmatch.fnmatch(part, p.raw):
                        return p
                # Also handle the case where rel_path IS the directory itself
                if fnmatch.fnmatch(dir_head, p.raw):
                    return p
            continue
        if p.has_path_sep:
            # Full path file pattern
            if fnmatch.fnmatch(rel_path, p.raw):
                return p
            continue
        # Simple basename pattern (exact or glob)
        if fnmatch.fnmatch(basename, p.raw):
            return p
    return None


# =============================================================================
# Builder
# =============================================================================


@dataclass
class BuildReport:
    copied: list[str] = field(default_factory=list)
    excluded: list[tuple[str, str]] = field(default_factory=list)  # (path, pattern)
    canary_files_found: list[str] = field(default_factory=list)
    canary_strings_found: list[tuple[str, str]] = field(default_factory=list)  # (file, string)
    import_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            not self.canary_files_found
            and not self.canary_strings_found
            and not self.import_errors
        )


def build(src: Path, out: Path, verbose: bool = False) -> BuildReport:
    patterns = parse_manifest(src / ".dist_excludes")
    report = BuildReport()

    # Clean output
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    for root, dirs, files in os.walk(src):
        rel_root = Path(root).relative_to(src)
        # Prune directories in-place
        pruned: list[str] = []
        kept: list[str] = []
        for d in sorted(dirs):
            if d in HARD_PRUNE_DIRS:
                pruned.append(d)
                continue
            rel_d = (rel_root / d).as_posix()
            if rel_d.startswith("./"):
                rel_d = rel_d[2:]
            if rel_d == ".":
                rel_d = d
            m = match_exclude(rel_d, patterns)
            if m:
                pruned.append(d)
                report.excluded.append((rel_d + "/", m.raw + ("/" if m.is_dir else "")))
            else:
                kept.append(d)
        dirs[:] = kept
        if verbose:
            for d in pruned:
                print(f"  prune dir: {rel_root / d}")

        for f in files:
            rel_f = (rel_root / f).as_posix()
            if rel_f.startswith("./"):
                rel_f = rel_f[2:]
            m = match_exclude(rel_f, patterns)
            if m:
                report.excluded.append((rel_f, m.raw + ("/" if m.is_dir else "")))
                if verbose:
                    print(f"  exclude: {rel_f} <- {m.raw}")
                continue
            dst = out / rel_root / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(root) / f, dst)
            report.copied.append(rel_f)

    # --- Canary file check ---
    for canary in CANARY_FILES:
        for copied in report.copied:
            if copied == canary or copied.endswith("/" + canary):
                report.canary_files_found.append(copied)

    # --- Canary string check ---
    for copied in report.copied:
        if not copied.endswith(".py"):
            continue
        path = out / copied
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for needle in CANARY_STRINGS:
            if needle in text:
                report.canary_strings_found.append((copied, needle))

    # --- Import smoke test ---
    report.import_errors.extend(_import_smoke_test(out))

    return report


def _import_smoke_test(out: Path) -> list[str]:
    """Run laplace_client + agent_api import from a COPY of the output dir.

    We copy to a throwaway tempdir first because agent_api.py's module-level
    logging.FileHandler writes agent.log at import time, and the Python
    interpreter writes __pycache__/*.pyc, both of which would pollute the
    pristine build output.
    """
    import tempfile

    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="laplace_smoke_") as tmp:
        probe_dir = Path(tmp) / "dist"
        shutil.copytree(out, probe_dir)
        probe_str = str(probe_dir).replace("\\", "\\\\")
        agent_path = str(probe_dir / "agent_api.py").replace("\\", "\\\\")
        probe = (
            "import sys, importlib.util\n"
            f"sys.path.insert(0, '{probe_str}')\n"
            "import laplace_client\n"
            "assert hasattr(laplace_client, 'RemoteLaplaceSession')\n"
            "assert hasattr(laplace_client, 'RemoteTableSelector')\n"
            "assert hasattr(laplace_client, 'ClientSetData')\n"
            f"spec = importlib.util.spec_from_file_location('agent_api', '{agent_path}')\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "assert hasattr(mod, 'run_bet_session')\n"
            "print('IMPORT_SMOKE_OK')\n"
        )
        try:
            result = subprocess.run(
                [sys.executable, "-c", probe],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            errors.append("Import smoke test timed out")
            return errors
        if result.returncode != 0 or "IMPORT_SMOKE_OK" not in result.stdout:
            errors.append(
                f"Import smoke test failed:\n"
                f"  returncode: {result.returncode}\n"
                f"  stdout: {result.stdout.strip()}\n"
                f"  stderr: {result.stderr.strip()}"
            )
    return errors


def print_summary(report: BuildReport, out: Path) -> None:
    print("")
    print("=" * 72)
    print("LAPLACE Client Distribution Build -- Summary")
    print("=" * 72)
    print(f"Output directory: {out}")
    print(f"Files copied:     {len(report.copied)}")
    print(f"Files excluded:   {len(report.excluded)}")
    print("")
    if report.canary_files_found:
        print(f"[FAIL] Canary files leaked into output:")
        for f in report.canary_files_found:
            print(f"  - {f}")
    else:
        print(f"[PASS] Canary file audit ({len(CANARY_FILES)} entries checked)")
    print("")
    if report.canary_strings_found:
        print(f"[FAIL] Canary strings leaked into output:")
        for f, s in report.canary_strings_found[:20]:
            print(f"  - {f}: {s!r}")
        if len(report.canary_strings_found) > 20:
            print(f"  ... and {len(report.canary_strings_found) - 20} more")
    else:
        print(f"[PASS] Canary string audit ({len(CANARY_STRINGS)} entries checked)")
    print("")
    if report.import_errors:
        print("[FAIL] Import smoke test:")
        for e in report.import_errors:
            print(f"  {e}")
    else:
        print("[PASS] Import smoke test (laplace_client + agent_api)")
    print("")
    print("=" * 72)
    if report.ok:
        print("BUILD OK -- distribution is ready to ship")
    else:
        print("BUILD FAILED -- fix the above errors before shipping")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build sanitised LAPLACE client distribution"
    )
    parser.add_argument(
        "--out",
        default="dist_client",
        help="Output directory (relative to repo root)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print every excluded file"
    )
    args = parser.parse_args()

    src = Path(__file__).resolve().parent.parent
    out = src / args.out

    print(f"Source:      {src}")
    print(f"Destination: {out}")
    print("")

    report = build(src, out, verbose=args.verbose)
    print_summary(report, out)

    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
