#!/usr/bin/env python3
"""Drop-in Codex launcher: codex_traced.py <any codex args>.

TRACE-TRUTH-20261016: use the owner-proven OTLP/HTTP binary recipe. Credentials
come from ~/.agents/tools/connectors/langfuse_otel_headers.py through a captured
pipe with --no-cache, never argv, a file or the header cache. Only the exec'd Codex receives the header env vars.
Helper/config failure disables tracing, records a fixed safe failure, and still
starts Codex. Success has no extra log row: exported spans are the evidence.

CODEX_BIN selects the actual binary (default: codex on PATH). CODEX_HOME selects
the config home (default: ~/.codex). CODEX_OTEL_ENVIRONMENT (codex-worker) and
CODEX_OTEL_SERVICE_NAME (codex) configure the OTel resource attributes. Their
Langfuse environment mapping is experimental, NOT live-verified by these tests.

As of 2026-10-16, Langfuse v4 maps sessions only from span attributes. Set both
session keys via otel.span_attributes, using a valid CODEX_TRACE_SESSION_ID or a
generated codex-<UTC>-<hex> ID.

Codex 0.160.0's local --help describes -c as replacing the specified TOML value,
not appending an array. Merge global, selected-profile and caller excludes in
memory, then supply the combined array. Codex 0.160.0 also supports native
filters (pattern = include|exclude) and rejects mixing filters with legacy
exclude/include_only. Preserve native filters when present and add exact-name
exclude rules there instead. Never rewrite the user's config file. Shell
exclusion tests exercise that contract with a fake Codex, not live Codex.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
from urllib.parse import quote

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None  # Python < 3.11 must still launch Codex safely, without tracing.

HEADER_NAMES = ("OTEL_EXPORTER_OTLP_TRACES_HEADERS", "OTEL_EXPORTER_OTLP_HEADERS")
# The local collector is the one door for this Mac: it reads the SigNoz key, drops
# anything with no service.name, refuses the ChatGPT app's codex-worker, and rate
# guards each service, so no agent holds a vendor key and policy lives in one place.
# This wrapper already sets service.name (default "codex") through
# OTEL_RESOURCE_ATTRIBUTES below, so its spans arrive named.
# Port 4320 is the standalone collector (LaunchAgent com.alex.signoz-collector), NOT
# the old relay on 4319, which stays running with no clients until Alex cancels
# Langfuse. Changed 2026-10-20, play absence-alarms-20261020-p4-apply. To send direct
# again, restore the Langfuse URL on the line below.
ENDPOINT = "http://127.0.0.1:4320/v1/traces"
LANGFUSE_DIRECT_ENDPOINT = "https://us.cloud.langfuse.com/api/public/otel/v1/traces"
HELPER_TIMEOUT = 10
RECORD_TIMEOUT = 3
EXCLUDE_KEY = "shell_environment_policy.exclude"
FILTER_KEY = "shell_environment_policy.filters"


def config_arguments(args):
    """Yield each config expression and its last argv index; ignore literal args after --."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            break
        if arg in ("-c", "--config") and i + 1 < len(args):
            i += 1
            yield args[i], i
        elif arg.startswith("--config="):
            yield arg.split("=", 1)[1], i
        elif arg.startswith("-c") and len(arg) > 2:
            yield arg[2:], i
        i += 1


def config_value(raw):
    return tomllib.loads("value=" + raw)["value"]


def config_path(key):
    """Normalize quoted TOML key components without inspecting any value."""
    try:
        node = tomllib.loads(key + "=0")
        parts = []
        while isinstance(node, dict) and len(node) == 1:
            part, node = next(iter(node.items()))
            parts.append(part)
        return parts
    except ValueError:
        # Invalid caller options are still Codex's to diagnose; fail no work.
        return key.strip().split(".")


def policy_excludes(policy):
    values = policy.get("exclude", [])
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ValueError("invalid exclude list")
    return values


def merged_shell_policy(args, env):
    if tomllib is None:
        raise ValueError("TOML support unavailable")
    home = Path(env.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    try:
        with (home / "config.toml").open("rb") as f:
            config = tomllib.load(f)
    except FileNotFoundError:
        config = {}
    policies = [config.get("shell_environment_policy", {})]
    profile = config.get("profile")
    # The CLI profile wins over the default. Don't inspect prompt text after --.
    for i, arg in enumerate(args):
        if arg == "--":
            break
        if arg in ("-p", "--profile") and i + 1 < len(args):
            profile = args[i + 1]
        elif arg.startswith("--profile="):
            profile = arg.split("=", 1)[1]
        elif arg.startswith("-p") and len(arg) > 2:
            profile = arg[2:]
    for expr, _ in config_arguments(args):
        key, sep, raw = expr.partition("=")
        if sep and config_path(key) == ["profile"]:
            profile = config_value(raw)
    if profile:
        selected = config.get("profiles", {}).get(profile, {})
        policies.append(selected.get("shell_environment_policy", {}))
    # A leaf override cannot remove an old exclude/include_only config key.
    configured_legacy = any("exclude" in p or "include_only" in p for p in policies)
    for expr, _ in config_arguments(args):
        key, sep, raw = expr.partition("=")
        path = config_path(key)
        if sep and path == ["shell_environment_policy", "exclude"]:
            policies.append({"exclude": config_value(raw)})
        elif sep and path == ["shell_environment_policy", "filters"]:
            policies.append({"filters": config_value(raw)})
        elif sep and path[:2] == ["shell_environment_policy", "filters"] and len(path) == 3:
            policies.append({"filters": {path[2]:config_value(raw)}})
        elif sep and path == ["shell_environment_policy"]:
            policies.append(config_value(raw))
    values = [value for policy in policies for value in policy_excludes(policy)]
    if not any("filters" in policy for policy in policies):
        return EXCLUDE_KEY, list(dict.fromkeys([*values, *HEADER_NAMES]))
    if configured_legacy or any("include_only" in p for p in policies):
        raise ValueError("cannot safely mix shell policy formats")
    filters = {}
    for policy in policies:
        current = policy.get("filters", {})
        if not isinstance(current, dict) or not all(
            isinstance(k, str) and v in ("include", "exclude") for k, v in current.items()
        ):
            raise ValueError("invalid native filters")
        for name, action in current.items():
            # An inherited exclusion remains an exclusion, even if a later
            # profile/CLI layer tries to include the same pattern.
            if filters.get(name) != "exclude":
                filters[name] = action
    filters.update({name:"exclude" for name in [*values, *HEADER_NAMES]})
    return FILTER_KEY, filters


def toml_value(value):
    """Serialize only the override and shell-policy types we own, never a complete config."""
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k) + "=" + toml_value(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(toml_value(v) for v in value) + "]"
    return json.dumps(value)


def fetch_headers(env):
    helper = Path.home() / ".agents/tools/connectors/langfuse_otel_headers.py"
    # Own this request's process group, not an existing shared vault daemon.
    with subprocess.Popen([sys.executable, "-B", str(helper), "--no-cache"], env=env,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, start_new_session=True) as process:
        try:
            output, _ = process.communicate(timeout=HELPER_TIMEOUT)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()  # Drain the pipe and reap the direct helper.
            raise
        if process.returncode:
            raise ValueError("header helper failed")
    headers = json.loads(output)
    if not isinstance(headers, dict) or not headers:
        raise ValueError("empty headers")
    for key, value in headers.items():
        if not isinstance(key, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key):
            raise ValueError("invalid header name")
        if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\0"):
            raise ValueError("invalid header value")
    if not any(key.lower() == "authorization" for key in headers):
        raise ValueError("missing auth header")
    return ",".join(f"{key}={quote(value, safe='')}" for key, value in headers.items())


def record_failure(env):
    # runs.py is best-effort and can exit zero without persisting a row.
    # Always leave visible, fixed feedback; never print exception/helper text.
    print("codex_traced: tracing disabled; launching Codex without tracing", file=sys.stderr)
    recorder = Path.home() / ".agents/tools/jobs/runs.py"
    try:
        subprocess.run(
            [sys.executable, "-B", str(recorder), "record", "--job", "tracing:codex", "--status", "fail",
             "--error", "tracing setup unavailable; Codex launched without tracing"],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=RECORD_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        pass


def guarded_arguments(args, overrides, shell_policy=None):
    """Keep caller args, restoring owned overrides after conflicting caller -c values."""
    otel_args = [part for key, value in overrides.items() for part in ("-c", key + "=" + toml_value(value))]
    if tomllib is None:
        # Without a parser we cannot identify every escaped/quoted TOML key.
        # Last-value wins: force disabled exporters after ALL caller config,
        # but before -- (whose remaining arguments are literal prompt data).
        boundary = args.index("--") if "--" in args else len(args)
        return [*args[:boundary], *otel_args, *args[boundary:]]
    shell_args = [] if shell_policy is None else ["-c", shell_policy[0] + "=" + toml_value(shell_policy[1])]
    after = {}
    replace = {}
    skip = set()
    for expr, index in config_arguments(args):
        key, _, raw = expr.partition("=")
        path = config_path(key)
        if path[:1] == ["otel"]:
            after[index] = otel_args
        elif path[:1] == ["shell_environment_policy"]:
            after[index] = shell_args
            if shell_policy and shell_policy[0] == FILTER_KEY and path in (
                ["shell_environment_policy"], ["shell_environment_policy", "exclude"]
            ):
                start = index - 1 if index and args[index - 1] in ("-c", "--config") else index
                if path == ["shell_environment_policy", "exclude"]:
                    replace[start] = shell_args
                else:
                    policy = config_value(raw)
                    policy.pop("exclude", None)
                    replace[start] = ["-c", "shell_environment_policy=" + toml_value(policy)]
                skip.update(range(start + 1, index + 1))
    result = [*otel_args, *shell_args]
    for i, arg in enumerate(args):
        if i not in skip:
            result.extend(replace.get(i, [arg]))
        result.extend(after.get(i, []))
    return result


def sessionless_command(args):
    """Recognize local CLI commands/flags, never prompt text or option values."""
    command = None
    value_flags = {"-c", "--config", "-p", "--profile", "-m", "--model", "-s", "--sandbox",
                   "-C", "--cd", "--add-dir", "--enable", "--disable", "--local-provider",
                   "-i", "--image", "-o", "--output-last-message", "--output-schema"}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            break
        if arg in ("--help", "-h", "--version", "-V"):
            return True
        if arg in value_flags:
            i += 2
            continue
        if command is None and not arg.startswith("-"):
            command = arg
        i += 1
    return command in {"help", "completion", "login", "logout", "mcp", "features", "apply", "app"}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    # Never mutate os.environ, and never pass inherited header vars to helpers or the recorder.
    child_env = {k:v for k, v in os.environ.items() if k not in HEADER_NAMES}
    environment = child_env.get("CODEX_OTEL_ENVIRONMENT", "codex-worker")
    service = child_env.get("CODEX_OTEL_SERVICE_NAME", "codex")
    overrides = {
        "otel.environment": environment,
        "otel.exporter": "none",
        "otel.log_user_prompt": False,
        "otel.trace_exporter.otlp-http.endpoint": ENDPOINT,
        "otel.trace_exporter.otlp-http.protocol": "binary",
    }
    untraced = {"otel.exporter":"none", "otel.trace_exporter":"none"}
    if sessionless_command(args):
        launch_args = guarded_arguments(args, untraced)
    else:
        try:
            shell_policy = merged_shell_policy(args, child_env)
            sid = child_env.get("CODEX_TRACE_SESSION_ID", "")
            if not re.fullmatch(r"[A-Za-z0-9._:@/-]{1,200}", sid):
                sid = f"codex-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
            overrides["otel.span_attributes"] = {"session.id": sid, "langfuse.session.id": sid}
            launch_args = guarded_arguments(args, overrides, shell_policy)
            encoded_headers = fetch_headers(child_env)
        except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
            # Exceptions (including JSON parse messages and helper stderr) may contain secrets.
            # Never stringify them. Only fixed failure diagnostics are permitted.
            record_failure(child_env)
            launch_args = guarded_arguments(args, untraced)
        else:
            owned_resources = {"deployment.environment": environment, "service.name": service}
            # OTel uses comma-separated key=value pairs, with percent-encoded values.
            # Split only at the first '='; do not decode/re-encode unrelated entries.
            resources = [pair for pair in child_env.get("OTEL_RESOURCE_ATTRIBUTES", "").split(",")
                         if pair.strip() and pair.partition("=")[0].strip() not in owned_resources]
            resources.extend(key + "=" + quote(value, safe="") for key, value in owned_resources.items())
            child_env["OTEL_RESOURCE_ATTRIBUTES"] = ",".join(resources)
            child_env.update({name:encoded_headers for name in HEADER_NAMES})
    binary = child_env.get("CODEX_BIN", "codex")
    try:
        # Process replacement passes stdin/out/err and exit status/signals through unchanged.
        # It also keeps codex_review's timeout aimed at Codex, not a waiting Python parent.
        os.execvpe(binary, [binary, *launch_args], child_env)
    except OSError:
        print("codex_traced: could not start Codex", file=sys.stderr)
        return 127


if __name__ == "__main__":
    sys.exit(main())
