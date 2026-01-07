# mini-qwen

Lightweight CLI wrapper around the tiny **qwen2.5-coder:0.5b-instruct** model (via Ollama). It runs a local Qwen pass first, then can optionally hand the result to Codex or Claude CLI for a second-pass rewrite/tooling. No cloud calls, no secrets.

## What it does
- Streams from the local Ollama HTTP API and prints the Qwen reply.
- Optional `--codex` flag: pipe the Qwen reply into `codex exec`.
- Optional `--claude` flag: pipe the Qwen reply into `claude` CLI.
- Tunables: model, temperature, top_p, max_tokens, timeout.
- Output modes: plain (default), quiet, or JSON blob.
- System prompts: `--sys presets/concise.md` (examples included).

## Requirements
- Python 3.8+
- Ollama running locally with `qwen2.5-coder:0.5b-instruct` pulled
  - `ollama pull qwen2.5-coder:0.5b-instruct`
- Optional: `codex` CLI and/or `claude` CLI on `PATH` if you use the flags.

## Install
```bash
# from repo root
cp qw.py /usr/local/bin/qw
chmod +x /usr/local/bin/qw
```

## Usage
```bash
# direct Qwen
qw "write a bash snippet that prints disk usage"

# Qwen then Codex (tools, shell, etc.)
qw --codex "list files modified in the last day"

# Qwen then Claude polish
qw --claude "tighten this release note: ..."

# swap model or timeout
qw --model qwen2.5-coder:0.5b --timeout 300 "draft a unit test"

# tune sampling and system prompt
qw --temp 0.2 --top-p 0.9 --sys presets/concise.md "summarize the diff"

# machine-readable output
qw --json --codex "list files modified in the last day"

# stdin works too
echo "summarize: $(cat log.txt)" | qw --codex
```

Output format:
```
<qwen reply>
--- codex ---
<codex reply>        # only when --codex
--- claude ---
<claude reply>       # only when --claude
```

## Notes
- Designed for local/offline use; points at `http://127.0.0.1:11434`.
- Keeps dependencies minimal (stdlib only).
- Avoids embedding any host-specific paths or secrets; customize locally as needed.

## OpenWebUI / proxy usage
If you have an OpenAI-compatible proxy in front of this (e.g., Claude proxy), expose `qwen2.5-coder:0.5b-instruct` through that proxy and register it in OpenWebUI as a fast local model. Keep keys and hostnames out of this repo; configure them on the host.
