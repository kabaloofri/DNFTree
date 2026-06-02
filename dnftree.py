#!/usr/bin/env python3
"""
dnftree - Display DNF packages and their dependencies as a tree.
Uses the dnf Python API directly — no subprocess calls.
"""

import sys

# ── ANSI colours ─────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"

# Tree drawing chars
TEE   = "├── "
LAST  = "└── "
PIPE  = "│   "
BLANK = "    "

# ── Help ──────────────────────────────────────────────────────────────────────
HELP = f"""
{BOLD}{CYAN}dnftree{RESET} — show DNF packages and their dependencies as a tree

{BOLD}USAGE{RESET}
  dnftree <command> [options]

{BOLD}COMMANDS{RESET}
  {GREEN}-a{RESET}, {GREEN}--all{RESET}                  List every installed package
  {GREEN}-u{RESET}, {GREEN}--user{RESET}, {GREEN}--userinstalled{RESET}
                            List only user-installed packages
  {GREEN}-p{RESET}, {GREEN}--package{RESET} <name>       Show a specific package (fuzzy match)
  {GREEN}-h{RESET}, {GREEN}--help{RESET}                 Show this help message
"""


# ── DNF sack loader ───────────────────────────────────────────────────────────
def load_base():
    """Return an initialised dnf.Base with the installed-packages sack loaded."""
    try:
        import dnf
    except ImportError:
        print(f"{RED}Error:{RESET} the 'dnf' Python module is not available.\n"
              f"  Install it with:  {CYAN}sudo dnf install python3-dnf{RESET}")
        sys.exit(1)

    base = dnf.Base()
    # Only load the local RPM database — fast, no network needed
    base.fill_sack(load_system_repo=True, load_available_repos=False)
    return base


# ── Package queries ───────────────────────────────────────────────────────────
def all_installed(base) -> list:
    """All installed package objects, deduplicated by name."""
    seen = {}
    for pkg in base.sack.query().installed():
        if pkg.name not in seen:
            seen[pkg.name] = pkg
    return sorted(seen.values(), key=lambda p: p.name)


def user_installed(base) -> list:
    """
    Packages the user explicitly requested (not auto-installed as deps).

    Strategy (in order):
      1. base.iter_userinstalled()  — the proper dnf4 API
      2. pkg.reason attribute       — set by libdnf on each package object
      3. dnf repoquery subprocess   — last resort, works on dnf4 and dnf5
    """
    # ── Strategy 1: iter_userinstalled (dnf4 official API) ────────────────
    if hasattr(base, "iter_userinstalled"):
        try:
            pkgs = sorted(base.iter_userinstalled(), key=lambda p: p.name)
            if pkgs:
                return pkgs
        except Exception:
            pass

    # ── Strategy 2: pkg.reason attribute ─────────────────────────────────
    # libdnf stores reason as a string: "user", "dep", "weak", "group", etc.
    try:
        user_pkgs = [
            pkg for pkg in base.sack.query().installed()
            if getattr(pkg, "reason", None) in ("user", 1)
        ]
        if user_pkgs:
            return sorted(user_pkgs, key=lambda p: p.name)
    except Exception:
        pass

    # ── Strategy 3: subprocess fallback (dnf repoquery --userinstalled) ──
    import subprocess
    try:
        result = subprocess.run(
            ["dnf", "repoquery", "--userinstalled", "--queryformat", "%{name}"],
            capture_output=True, text=True, timeout=30
        )
        names = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        if names:
            pkg_map = {p.name: p for p in base.sack.query().installed()}
            return sorted(
                (pkg_map[n] for n in names if n in pkg_map),
                key=lambda p: p.name
            )
    except Exception:
        pass

    return []



def pkg_deps_in_set(pkg, pkg_name_set: set, sack) -> list:
    """
    Return the names of packages in pkg_name_set that pkg directly requires.
    Uses dnf sack to resolve each requirement to an installed provider.
    """
    deps = set()
    for req in pkg.requires:
        req_str = str(req)
        # Skip virtual/internal capabilities
        if req_str.startswith("rpmlib(") or req_str.startswith("config("):
            continue
        providers = sack.query().installed().filter(provides=req)
        for provider in providers:
            if provider.name != pkg.name and provider.name in pkg_name_set:
                deps.add(provider.name)
    return sorted(deps)


def fuzzy_match(query: str, pkg_list: list) -> list:
    """Return packages whose name contains query (case-insensitive)."""
    q = query.lower()
    return [p for p in pkg_list if q in p.name.lower()]


# ── Dep-map & tree ────────────────────────────────────────────────────────────
def build_dep_map(pkgs: list, sack) -> dict[str, list[str]]:
    """
    Build {name: [dep_name, …]} for every package in pkgs,
    only counting deps that are also in the pkgs set.
    """
    pkg_name_set = {p.name for p in pkgs}
    pkg_by_name  = {p.name: p for p in pkgs}

    print(f"{DIM}Resolving dependencies for {len(pkgs)} packages…{RESET}",
          file=sys.stderr)

    dep_map: dict[str, list[str]] = {}
    for i, pkg in enumerate(pkgs):
        dep_map[pkg.name] = pkg_deps_in_set(pkg, pkg_name_set, sack)

    return dep_map


def find_roots(dep_map: dict[str, list[str]]) -> list[str]:
    """Names that are not listed as a dependency of any other package."""
    all_deps: set[str] = set()
    for deps in dep_map.values():
        all_deps.update(deps)
    return sorted(n for n in dep_map if n not in all_deps)


def print_tree(name: str, dep_map: dict, visited: set,
               prefix: str = "", is_last: bool = True) -> None:
    connector = LAST if is_last else TEE
    already   = name in visited

    colour = YELLOW if already else GREEN
    print(f"{prefix}{connector}{colour}{BOLD}{name}{RESET}")

    if already:
        return
    visited.add(name)

    children     = dep_map.get(name, [])
    child_prefix = prefix + (BLANK if is_last else PIPE)
    for i, child in enumerate(children):
        print_tree(child, dep_map, visited, child_prefix, i == len(children) - 1)


def display_tree(pkgs: list, label: str, sack) -> None:
    if not pkgs:
        print(f"{RED}No packages found.{RESET}")
        return

    dep_map = build_dep_map(pkgs, sack)
    roots   = find_roots(dep_map)
    visited: set[str] = set()

    print(f"\n{BOLD}{CYAN}{label}{RESET}  {DIM}({len(pkgs)} packages, {len(roots)} roots){RESET}\n")
    for i, root in enumerate(roots):
        print_tree(root, dep_map, visited, prefix="", is_last=(i == len(roots) - 1))
    print()


# ── Single-package mode ───────────────────────────────────────────────────────
def display_single(query: str, base) -> None:
    all_pkgs = list(base.sack.query().installed())
    matches  = fuzzy_match(query, all_pkgs)

    if not matches:
        print(f"{RED}No installed package matching '{query}' found.{RESET}")
        sys.exit(1)

    if len(matches) == 1:
        root_pkg = matches[0]
    else:
        print(f"{YELLOW}Multiple matches for '{query}':{RESET}")
        for i, m in enumerate(matches):
            print(f"  {i+1:2}. {m.name}")
        try:
            choice   = int(input(f"\n{BOLD}Pick a number (1-{len(matches)}): {RESET}")) - 1
            root_pkg = matches[choice]
        except (ValueError, IndexError):
            print(f"{RED}Invalid choice.{RESET}")
            sys.exit(1)

    # Build the full dep closure starting from root_pkg
    closure:  dict[str, object] = {}   # name -> pkg

    def expand(pkg) -> None:
        if pkg.name in closure:
            return
        closure[pkg.name] = pkg
        for req in pkg.requires:
            req_str = str(req)
            if req_str.startswith("rpmlib(") or req_str.startswith("config("):
                continue
            for provider in base.sack.query().installed().filter(provides=req):
                if provider.name != pkg.name:
                    expand(provider)

    print(f"{DIM}Building dependency closure for {root_pkg.name}…{RESET}",
          file=sys.stderr)
    expand(root_pkg)

    pkg_list = list(closure.values())
    dep_map  = build_dep_map(pkg_list, base.sack)
    visited: set[str] = set()

    n_deps = len(closure) - 1
    print(f"\n{BOLD}{CYAN}{root_pkg.name}{RESET}  "
          f"{DIM}(+ {n_deps} dependenc{'y' if n_deps == 1 else 'ies'}){RESET}\n")
    print_tree(root_pkg.name, dep_map, visited)
    print()


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    args = sys.argv[1:]

    if not args:
        print(HELP)
        sys.exit(0)

    command = args[0].lower()

    if command in ("-h", "--help"):
        print(HELP)
        sys.exit(0)

    # Load DNF base (shared by all modes)
    base = load_base()

    if command in ("-a", "--all"):
        pkgs = all_installed(base)
        display_tree(pkgs, "All Installed Packages", base.sack)

    elif command in ("-u", "--user", "--userinstalled"):
        pkgs = user_installed(base)
        if not pkgs:
            print(f"{RED}No user-installed packages found.{RESET}\n"
                  f"{DIM}Try running with sudo.{RESET}")
            sys.exit(1)
        display_tree(pkgs, "User-Installed Packages", base.sack)

    elif command in ("-p", "--package"):
        if len(args) < 2:
            print(f"{RED}Error:{RESET} --package requires a package name.\n"
                  f"  Example: {CYAN}dnftree -p python{RESET}\n")
            sys.exit(1)
        display_single(args[1], base)

    else:
        print(f"{RED}Unknown option:{RESET} {args[0]}")
        print(HELP)
        sys.exit(1)


if __name__ == "__main__":
    main()
