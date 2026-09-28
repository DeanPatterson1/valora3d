"""The source files a sim block's bake depends on (phase 6; the lane R / lane P finding on T98's block_sha).

A bake's output is decided by the block's bake.py and every engine module it imports (engine/blender/pieces.py,
engine/physics/scatter.py, engine/blender/gn_sim.py, ...), directly or through another engine module, at module
level or inside a function. `bake_sources` finds them by reading the import statements (ast, no import runs),
so an edited helper is a new bake key without anyone bumping a hand-kept revision number.

- Followed: `import engine.a.b`, `from engine.a import b` (b a module or a name in engine.a), `from engine.a.b
  import c`, and relative imports inside engine packages. The package __init__.py files on the way are included
  (they run on import).
- Not followed: bpy / mathutils / stdlib / third-party (the Blender version is its own key field), and
  `engine.bake.*`, the stage-4b plumbing (key, store, run, window): a build.py imports BakeMissing from
  engine.bake.run, and the runner's own code does not decide what a block simulates. The bake entry and the
  collision proxy builder are keyed separately (PINNED_BLENDER; engine/physics/proxy.proxy_key).
- build.py is hashed too (T98: a changed reader re-bakes), but its imports are not followed: they change how a
  cache is read, not what it holds."""
import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]          # the engine package directory
SKIP = ("engine.bake",)                               # stage-4b plumbing, see the docstring


def _module_file(name, engine_dir):
    """engine.a.b -> engine_dir/a/b.py or engine_dir/a/b/__init__.py; None when it is not an engine module."""
    parts = name.split(".")
    if parts[0] != "engine":
        return None
    base = engine_dir.joinpath(*parts[1:]) if len(parts) > 1 else engine_dir
    if base.with_suffix(".py").is_file() and len(parts) > 1:
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def _skipped(name):
    return any(name == s or name.startswith(s + ".") for s in SKIP)


def _package_of(path, engine_dir):
    rel = path.resolve().relative_to(engine_dir).with_suffix("")
    parts = ["engine", *rel.parts]
    return ".".join(parts[:-1]) if parts[-1] != "__init__" else ".".join(parts[:-1])


def imported_modules(path, engine_dir=ENGINE, package=None):
    """Engine module names one file imports anywhere in it (function-level imports included)."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=str(path))
    if package is None:
        try:
            package = _package_of(Path(path), engine_dir)
        except ValueError:
            package = None                               # a block file outside the engine tree
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if not package:
                    continue
                base = package.split(".")
                base = base[:len(base) - (node.level - 1)] if node.level > 1 else base
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            out.append(mod)
            out += [f"{mod}.{a.name}" for a in node.names if a.name != "*"]
    return [m for m in out if m.split(".")[0] == "engine"]


def _with_parents(name):
    parts = name.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts) + 1)]


def module_closure(files, engine_dir=ENGINE):
    """Every engine source file the given files import, transitively (sorted, the given files excluded)."""
    engine_dir = Path(engine_dir).resolve()
    seen, todo = {}, [(Path(f), None) for f in files]
    first = {Path(f).resolve() for f in files}
    while todo:
        f, _ = todo.pop()
        for name in imported_modules(f, engine_dir):
            for n in _with_parents(name):
                if _skipped(n) or n in seen:
                    continue
                p = _module_file(n, engine_dir)
                seen[n] = p
                if p is not None:
                    todo.append((p, n))
    return sorted({p.resolve() for p in seen.values() if p is not None} - first)


def bake_sources(block_dir, engine_dir=ENGINE):
    """The files a block's bake key hashes, in a stable order: bake.py, build.py, then the engine modules
    bake.py imports (transitively), sorted by their path relative to the engine directory."""
    block_dir, engine_dir = Path(block_dir), Path(engine_dir).resolve()
    own = [block_dir / "bake.py", block_dir / "build.py"]
    deps = module_closure([own[0]], engine_dir)
    return own + sorted(deps, key=lambda p: p.relative_to(engine_dir).as_posix())
