"""
Command line interface.

Commands
--------
``audit``   audit one or more configuration files
``fix``     show or apply automatic fixes
``diff``    semantic diff between two configurations
``gen``     generate a best-practice configuration from a template
``fmt``     re-indent a configuration (with ``--check`` for CI)
``parse``   dump the parsed tree (debugging)
``rules``   list / explain the built-in rules
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Sequence

from . import __version__
from .engine import (
    RULES,
    AuditOptions,
    discover_configs,
    audit,
    load_default_rules,
    should_fail,
)
from .fixer import apply_to_config, build_plan, total_changes, unified_diff
from .generator import DEFAULTS, generate, list_templates
from .model import ConfigFile
from .parser import parse, parse_file
from .reporters import MACHINE_FORMATS, formats, render as render_report
from .reporters.text import set_color
from .semdiff import compare, render_canonical

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _load_configs(paths: Sequence[str]) -> List[ConfigFile]:
    files = discover_configs(list(paths))
    if not files:
        raise SystemExit(f"nginxforge: no configuration files found in {list(paths)}")
    configs: List[ConfigFile] = []
    for path in files:
        try:
            configs.append(parse_file(path))
        except OSError as exc:
            print(f"nginxforge: cannot read {path}: {exc}", file=sys.stderr)
    return configs


def _options_from_args(args: argparse.Namespace) -> AuditOptions:
    options = AuditOptions()
    if getattr(args, "config", None):
        options.load_file(args.config)
    for name in ("select", "ignore"):
        values = getattr(args, name, None)
        if values:
            getattr(options, name).update(v for v in values if v)
    if getattr(args, "min_severity", None):
        options.min_severity = args.min_severity
    if getattr(args, "fail_on", None):
        options.fail_on = args.fail_on
    if getattr(args, "set", None):
        for item in args.set:
            if "=" in item:
                key, value = item.split("=", 1)
                try:
                    options.settings[key.strip()] = json.loads(value)
                except ValueError:
                    options.settings[key.strip()] = value
    return options


def _emit(text: str, out: Optional[str]) -> None:
    if out:
        directory = os.path.dirname(os.path.abspath(out))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"nginxforge: report written to {out}")
    else:
        sys.stdout.write(text + ("" if text.endswith("\n") else "\n"))


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_audit(args: argparse.Namespace) -> int:
    load_default_rules()
    set_color(not args.no_color and sys.stdout.isatty()
              and args.format not in MACHINE_FORMATS)
    configs = _load_configs(args.paths)
    options = _options_from_args(args)
    result = audit(configs, options)

    if args.summary and args.format == "text":
        counts = result.counts()
        print(f"{len(result.findings)} finding(s): "
              f"{counts.get('error', 0)} error, "
              f"{counts.get('warning', 0)} warning, "
              f"{counts.get('info', 0)} info")
        return EXIT_FINDINGS if should_fail(result, options.fail_on) else EXIT_OK

    _emit(render_report(args.format, result, __version__), args.output)
    return EXIT_FINDINGS if should_fail(result, options.fail_on) else EXIT_OK


def cmd_fix(args: argparse.Namespace) -> int:
    load_default_rules()
    configs = _load_configs(args.paths)
    options = _options_from_args(args)
    result = audit(configs, options)

    rule_filter = set(args.rule) if args.rule else None
    plans = build_plan(result.findings, safe_only=args.safe,
                       rule_filter=rule_filter)
    if not plans:
        print("nginxforge: no automatic fixes available "
              "(run 'audit' for the full list of findings)")
        return EXIT_OK

    by_file = {config.path: config for config in configs}
    total = total_changes(plans.values())
    for file_name, plan in sorted(plans.items()):
        config = by_file.get(file_name)
        if config is None:
            continue
        if args.apply:
            new_text = apply_to_config(config, plan.changes)
            with open(file_name, "w", encoding="utf-8") as handle:
                handle.write(new_text)
            print(f"nginxforge: applied {plan.count} fix(es) to {file_name}")
        else:
            print(unified_diff(config, plan.changes))

    if not args.apply:
        print(f"nginxforge: {total} fix(es) pending - re-run with --apply to "
              "write them")
    return EXIT_OK


def cmd_diff(args: argparse.Namespace) -> int:
    left = parse_file(args.left)
    right = parse_file(args.right)
    result = compare(left, right)

    if args.format == "json":
        payload = {
            "identical": result.identical,
            "summary": result.summary(),
            "added": [e.render() for e in result.added],
            "removed": [e.render() for e in result.removed],
            "changed": [[a.render(), b.render()] for a, b in result.changed],
            "unified": result.text,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"# {result.left_label} -> {result.right_label}")
        print(f"# {result.summary()}")
        print()
        if not result.identical:
            for entry in result.added:
                print(f"+ {entry.render()}")
            for entry in result.removed:
                print(f"- {entry.render()}")
            for before, after in result.changed:
                print(f"~ {before.render()}")
                print(f"  -> {after.render()}")
            print()
            if args.unified:
                print(result.text)
    return EXIT_OK if result.identical else EXIT_FINDINGS


def cmd_gen(args: argparse.Namespace) -> int:
    if args.list:
        print(f"{'TEMPLATE':<16} {'TITLE':<24} DESCRIPTION")
        for tpl in list_templates():
            params = ", ".join(sorted(tpl.params)) or "-"
            print(f"{tpl.name:<16} {tpl.title:<24} {tpl.description}")
            print(f"{'':<16} {'':<24} params: {params}")
        return EXIT_OK

    if not args.template:
        print("nginxforge: --template is required (or use --list)",
              file=sys.stderr)
        return EXIT_USAGE

    params: Dict[str, str] = {}
    for key in ("domain", "upstream", "root", "port", "name", "tls"):
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    for item in getattr(args, "set", None) or []:
        if "=" in item:
            key, value = item.split("=", 1)
            params[key.strip()] = value.strip()

    try:
        text = generate(args.template, **params)
    except KeyError:
        print(f"nginxforge: unknown template '{args.template}' - "
              f"available: {', '.join(t.name for t in list_templates())}",
              file=sys.stderr)
        return EXIT_USAGE

    if args.audit:
        load_default_rules()
        config = parse(text, args.out or f"<{args.template}>")
        result = audit([config], AuditOptions())
        if result.findings:
            print(render_report("text", result, __version__))
            return EXIT_FINDINGS
        print("nginxforge: generated configuration passes all rules ✔")

    if args.out:
        directory = os.path.dirname(os.path.abspath(args.out))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"nginxforge: wrote {args.out}")
    elif not args.audit:
        sys.stdout.write(text)
    return EXIT_OK


def _render_with_comments(tree, indent: str = "    ", level: int = 0) -> str:
    out: List[str] = []
    pad = indent * level
    for node in tree:
        if node.comment:
            out.append(pad + "# " + node.comment)
        out.append(pad + node.source_line())
        if node.block is not None:
            out.append(_render_with_comments(node.block, indent, level + 1))
            out.append(pad + "}")
    return "\n".join(out)


def cmd_fmt(args: argparse.Namespace) -> int:
    configs = _load_configs(args.paths)
    changed = 0
    for config in configs:
        formatted = _render_with_comments(config.tree, args.indent)
        if formatted.strip() != config.text.strip():
            changed += 1
            if args.check:
                print(f"{config.path}: not formatted")
            elif args.in_place:
                with open(config.path, "w", encoding="utf-8") as handle:
                    handle.write(formatted + "\n")
                print(f"{config.path}: reformatted")
            else:
                sys.stdout.write(formatted + "\n")
    if args.check:
        if changed:
            print(f"nginxforge: {changed} file(s) need formatting")
            return EXIT_FINDINGS
        print("nginxforge: all files are formatted")
    return EXIT_OK


def cmd_parse(args: argparse.Namespace) -> int:
    config = parse_file(args.path)
    if args.format == "json":
        def dump(node):
            return {
                "name": node.name,
                "args": node.args,
                "line": node.line,
                "col": node.col,
                "context": node.context,
                "path": node.path_label(),
                "block": [dump(child) for child in node.block] if node.block else None,
            }
        print(json.dumps({
            "file": config.path,
            "errors": [str(e) for e in config.errors],
            "tree": [dump(node) for node in config.tree],
        }, indent=2, ensure_ascii=False))
        return EXIT_OK

    def walk(node, depth=0):
        print("  " * depth + node.source_line() +
              (" {" if node.block is not None else ""))
        for child in node.block or []:
            walk(child, depth + 1)
        if node.block is not None:
            print("  " * depth + "}")

    for node in config.tree:
        walk(node)
    for err in config.errors:
        print(f"! {err}", file=sys.stderr)
    return EXIT_OK if config.ok else EXIT_FINDINGS


def cmd_rules(args: argparse.Namespace) -> int:
    load_default_rules()
    if args.rule:
        obj = next((r for r in RULES if r.id == args.rule), None)
        if obj is None:
            print(f"nginxforge: unknown rule '{args.rule}'", file=sys.stderr)
            return EXIT_USAGE
        print(f"{obj.id}  [{obj.severity}/{obj.category}]")
        print(f"  title      : {obj.title}")
        print(f"  remediation: {obj.remediation or '-'}")
        return EXIT_OK

    if args.format == "json":
        print(json.dumps([{
            "id": r.id, "title": r.title, "severity": r.severity,
            "category": r.category, "remediation": r.remediation,
        } for r in RULES], indent=2, ensure_ascii=False))
        return EXIT_OK

    print(f"{'RULE':<9} {'SEVERITY':<9} {'CATEGORY':<14} TITLE")
    for rule_obj in sorted(RULES, key=lambda r: r.id):
        print(f"{rule_obj.id:<9} {rule_obj.severity:<9} "
              f"{rule_obj.category:<14} {rule_obj.title}")
    print(f"\n{len(RULES)} rule(s) available "
          f"(filter with --select/--ignore, tune with --set key=value)")
    return EXIT_OK


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nginxforge",
        description="Zero-dependency, offline-first nginx configuration "
                    "parser, auditor, fixer and generator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  nginxforge audit /etc/nginx/nginx.conf
  nginxforge audit ./conf.d --format sarif --output report.sarif
  nginxforge audit nginx.conf --select security --fail-on warning
  nginxforge fix nginx.conf --safe --apply
  nginxforge diff old.conf new.conf
  nginxforge gen --template reverse-proxy --domain example.com --out nginx.conf
  nginxforge fmt nginx.conf --check
""",
    )
    parser.add_argument("--version", action="version",
                        version=f"nginxforge {__version__}")
    sub = parser.add_subparsers(dest="command")

    # -- audit -----------------------------------------------------------
    p = sub.add_parser("audit", help="audit configuration files")
    p.add_argument("paths", nargs="+", help="files or directories")
    p.add_argument("-f", "--format", default="text", choices=formats())
    p.add_argument("-o", "--output", help="write the report to a file")
    p.add_argument("--select", action="append", default=[],
                   help="only run these rules/categories (repeatable)")
    p.add_argument("--ignore", action="append", default=[],
                   help="skip these rules/categories (repeatable)")
    p.add_argument("--min-severity", default="info",
                   choices=("error", "warning", "info"))
    p.add_argument("--fail-on", default="error",
                   choices=("error", "warning", "info", "never"),
                   help="exit 1 when a finding of this severity exists")
    p.add_argument("--config", help="JSON settings file")
    p.add_argument("--set", action="append", default=[],
                   help="override one setting: --set max_keepalive_timeout=60")
    p.add_argument("--summary", action="store_true",
                   help="print only the one-line summary")
    p.add_argument("--no-color", action="store_true")
    p.set_defaults(func=cmd_audit)

    # -- fix -------------------------------------------------------------
    p = sub.add_parser("fix", help="show or apply automatic fixes")
    p.add_argument("paths", nargs="+")
    p.add_argument("--apply", action="store_true",
                   help="write the fixes back to disk (default is a dry run)")
    p.add_argument("--safe", action="store_true",
                   help="only rewrite existing lines, never add or delete")
    p.add_argument("--rule", action="append", default=[],
                   help="limit fixes to these rule ids")
    p.add_argument("--select", action="append", default=[])
    p.add_argument("--ignore", action="append", default=[])
    p.add_argument("--min-severity", default="info",
                   choices=("error", "warning", "info"))
    p.add_argument("--fail-on", default="never",
                   choices=("error", "warning", "info", "never"))
    p.add_argument("--config")
    p.add_argument("--set", action="append", default=[])
    p.set_defaults(func=cmd_fix)

    # -- diff ------------------------------------------------------------
    p = sub.add_parser("diff", help="semantic diff between two configurations")
    p.add_argument("left")
    p.add_argument("right")
    p.add_argument("-f", "--format", default="text", choices=("text", "json"))
    p.add_argument("--unified", action="store_true",
                   help="also print a unified diff of the canonical form")
    p.set_defaults(func=cmd_diff)

    # -- gen -------------------------------------------------------------
    p = sub.add_parser("gen", help="generate a configuration from a template")
    p.add_argument("-t", "--template")
    p.add_argument("--list", action="store_true", help="list templates")
    p.add_argument("--domain")
    p.add_argument("--upstream")
    p.add_argument("--root")
    p.add_argument("--port")
    p.add_argument("--name", help="upstream group name")
    p.add_argument("--tls", choices=("on", "off"))
    p.add_argument("--set", action="append", default=[],
                   help="extra template parameter: --set key=value")
    p.add_argument("-o", "--out", help="write to a file instead of stdout")
    p.add_argument("--audit", action="store_true",
                   help="audit the generated configuration immediately")
    p.set_defaults(func=cmd_gen)

    # -- fmt -------------------------------------------------------------
    p = sub.add_parser("fmt", help="re-indent a configuration")
    p.add_argument("paths", nargs="+")
    p.add_argument("--indent", default="    ")
    p.add_argument("--in-place", action="store_true")
    p.add_argument("--check", action="store_true",
                   help="exit 1 when a file is not formatted (CI mode)")
    p.set_defaults(func=cmd_fmt)

    # -- parse -----------------------------------------------------------
    p = sub.add_parser("parse", help="dump the parsed configuration tree")
    p.add_argument("path")
    p.add_argument("-f", "--format", default="tree", choices=("tree", "json"))
    p.set_defaults(func=cmd_parse)

    # -- rules -----------------------------------------------------------
    p = sub.add_parser("rules", help="list or explain rules")
    p.add_argument("rule", nargs="?", help="explain a single rule id")
    p.add_argument("-f", "--format", default="text", choices=("text", "json"))
    p.set_defaults(func=cmd_rules)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return args.func(args)
    except KeyboardInterrupt:  # pragma: no cover
        print("nginxforge: interrupted", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"nginxforge: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
