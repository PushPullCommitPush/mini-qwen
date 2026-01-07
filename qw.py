#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "qwen2.5-coder:0.5b-instruct"
API_URL = "http://127.0.0.1:11434/api/generate"


def run(cmd, stdin_text=None):
    return subprocess.run(
        cmd,
        input=stdin_text,
        text=True,
        capture_output=True,
        check=False,
    )


def get_prompt(args):
    if args.prompt:
        return " ".join(args.prompt).strip()
    data = sys.stdin.read()
    if data.strip():
        return data.strip()
    print("qw: provide a prompt as args or stdin", file=sys.stderr)
    sys.exit(1)


def ensure_bins(bins):
    missing = [b for b in bins if shutil.which(b) is None]
    if missing:
        print("qw: missing required command(s): " + ", ".join(missing), file=sys.stderr)
        sys.exit(1)


def load_sys_prompt(path_str):
    if not path_str:
        return ""
    path = Path(path_str).expanduser()
    try:
        return path.read_text()
    except Exception as e:
        print(f"qw: failed to read system prompt file: {e}", file=sys.stderr)
        sys.exit(1)


def maybe_auto_pull(model):
    res = run(["ollama", "pull", model])
    if res.returncode != 0:
        print(res.stderr or res.stdout or "qw: ollama pull failed", file=sys.stderr)
        sys.exit(res.returncode or 1)


def run_qwen(
    prompt,
    model,
    temp=None,
    top_p=None,
    max_tokens=None,
    system="",
    seed=None,
    stop=None,
):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
    }
    if system:
        payload["system"] = system
    if temp is not None:
        payload["temperature"] = temp
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if seed is not None:
        payload["seed"] = seed
    if stop:
        payload["stop"] = stop

    data = json.dumps(payload).encode()
    req = urllib.request.Request(API_URL, data=data, headers={"Content-Type": "application/json"})
    chunks = []
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            for line in resp:
                if not line.strip():
                    continue
                msg = json.loads(line)
                if msg.get("error"):
                    raise RuntimeError(msg["error"])
                if "response" in msg:
                    chunks.append(msg["response"])
                if msg.get("done"):
                    break
    except Exception as e:
        print(f"qw: qwen request failed: {e}", file=sys.stderr)
        sys.exit(1)
    return "".join(chunks).strip()


def log_run(path_str, prompt, qwen_reply, codex_reply, claude_reply):
    path = Path(path_str).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "prompt": prompt,
            "qwen": qwen_reply,
            "codex": codex_reply,
            "claude": claude_reply,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"qw: failed to log run: {e}", file=sys.stderr)


def run_shell(cmd):
    res = run(["/bin/sh", "-c", cmd])
    if res.stdout:
        print("\n--- execute stdout ---\n" + res.stdout.strip())
    if res.stderr:
        print("\n--- execute stderr ---\n" + res.stderr.strip(), file=sys.stderr)
    if res.returncode != 0:
        sys.exit(res.returncode)


def main():
    p = argparse.ArgumentParser(description="Mini Qwen wizard: local Qwen with optional Codex/Claude pass")
    p.add_argument("prompt", nargs="*", help="prompt text (or pass via stdin)")
    p.add_argument("--codex", action="store_true", help="pipe Qwen reply into codex exec")
    p.add_argument("--claude", action="store_true", help="pipe Qwen reply into claude CLI")
    p.add_argument("--model", default=DEFAULT_MODEL, help="ollama model name (default: %(default)s)")
    p.add_argument("--timeout", default="180", help="codex/claude timeout seconds (string)")
    p.add_argument("--temp", type=float, help="sampling temperature for Qwen")
    p.add_argument("--top-p", type=float, help="nucleus sampling top_p for Qwen")
    p.add_argument("--max-tokens", type=int, help="limit Qwen tokens")
    p.add_argument("--sys", dest="sys_path", help="path to system prompt text to prepend")
    p.add_argument("--quiet", action="store_true", help="suppress Qwen stdout (still runs)")
    p.add_argument("--json", action="store_true", help="print JSON: {qwen, codex?, claude?}")
    p.add_argument("--seed", type=int, help="set seed for deterministic sampling (if supported)")
    p.add_argument("--stop", action="append", help="add a stop token (repeatable)")
    p.add_argument("--auto-pull", action="store_true", help="(danger) run `ollama pull <model>` before generation")
    p.add_argument(
        "--execute",
        action="store_true",
        help="(danger) execute the best available reply as a shell command (/bin/sh -c)",
    )
    p.add_argument(
        "--log-file",
        help="(danger) append prompt/output JSONL to this file (may leak sensitive content)",
    )
    args = p.parse_args()

    ensure_bins((["codex"] if args.codex else []) + (["claude"] if args.claude else []))

    prompt = get_prompt(args)
    system_prompt = load_sys_prompt(args.sys_path)

    if args.auto_pull:
        maybe_auto_pull(args.model)

    qwen_reply = run_qwen(
        prompt,
        args.model,
        temp=args.temp,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        system=system_prompt,
        seed=args.seed,
        stop=args.stop,
    )

    codex_reply = None
    claude_reply = None

    if not args.quiet and not args.json:
        print(qwen_reply)

    if args.codex:
        c = run(["codex", "exec", "--timeout", args.timeout, qwen_reply])
        if c.returncode != 0:
            print(c.stderr or c.stdout or "qw: codex failed", file=sys.stderr)
            sys.exit(c.returncode)
        codex_reply = c.stdout.strip()
        if not args.json:
            print("\n--- codex ---\n" + codex_reply)

    if args.claude:
        cl = run(["claude", "-t", args.timeout, qwen_reply])
        if cl.returncode != 0:
            print(cl.stderr or cl.stdout or "qw: claude failed", file=sys.stderr)
            sys.exit(cl.returncode)
        claude_reply = cl.stdout.strip()
        if not args.json:
            print("\n--- claude ---\n" + claude_reply)

    if args.json:
        out = {"qwen": qwen_reply}
        if codex_reply is not None:
            out["codex"] = codex_reply
        if claude_reply is not None:
            out["claude"] = claude_reply
        print(json.dumps(out, ensure_ascii=False))

    if args.log_file:
        log_run(args.log_file, prompt, qwen_reply, codex_reply, claude_reply)

    if args.execute:
        to_run = codex_reply or claude_reply or qwen_reply
        if not to_run:
            print("qw: nothing to execute", file=sys.stderr)
            sys.exit(1)
        run_shell(to_run)


if __name__ == "__main__":
    main()
