#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import urllib.request

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


def run_qwen(prompt, model):
    payload = {"model": model, "prompt": prompt, "stream": True}
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


def main():
    p = argparse.ArgumentParser(description="Mini Qwen wizard: local Qwen with optional Codex/Claude pass")
    p.add_argument("prompt", nargs="*", help="prompt text (or pass via stdin)")
    p.add_argument("--codex", action="store_true", help="pipe Qwen reply into codex exec")
    p.add_argument("--claude", action="store_true", help="pipe Qwen reply into claude CLI")
    p.add_argument("--model", default=DEFAULT_MODEL, help="ollama model name (default: %(default)s)")
    p.add_argument("--timeout", default="180", help="codex/claude timeout seconds (string)")
    args = p.parse_args()

    ensure_bins((["codex"] if args.codex else []) + (["claude"] if args.claude else []))

    prompt = get_prompt(args)
    qwen_reply = run_qwen(prompt, args.model)
    print(qwen_reply)

    if args.codex:
        c = run(["codex", "exec", "--timeout", args.timeout, qwen_reply])
        if c.returncode != 0:
            print(c.stderr or c.stdout or "qw: codex failed", file=sys.stderr)
            sys.exit(c.returncode)
        print("\n--- codex ---\n" + c.stdout.strip())

    if args.claude:
        cl = run(["claude", "-t", args.timeout, qwen_reply])
        if cl.returncode != 0:
            print(cl.stderr or cl.stdout or "qw: claude failed", file=sys.stderr)
            sys.exit(cl.returncode)
        print("\n--- claude ---\n" + cl.stdout.strip())


if __name__ == "__main__":
    main()
