# CatchMe integration

Adem and CatchMe have separate responsibilities:

```text
Adem /proc reader ──read-only snapshot──> ~/.catchme/integrations/adem-processes.json ──> CatchMe local context
      └── review + SIGTERM (only after confirmation)
```

The snapshot schema is `adem.catchme.processes.v1`. It is deliberately bounded to the 20 largest groups that use at least 50 MiB RSS or 1% CPU. Each entry has `name`, `memoryBytes`, `cpuPercent`, `processCount`, `closable`, `protected` and `protectionReason`. The envelope has `capturedAt`, `hostname`, `scope`, `readOnly: true` and `actions: []`.

The systemd timer writes it every 15 seconds with mode `0600`. The write is atomic, and the destination directory is mode `0700`. It falls back to `~/.cache/adem/catchme-processes.json` when the CatchMe directory does not exist.

CatchMe should treat the file as untrusted, local evidence. It may answer “which process groups are expensive?” from the latest `capturedAt`; it must not infer focus, productivity, cause, duration or diagnosis. It must not use this file to signal processes. Use Adem’s review dialog for that.

On this workstation the local CatchMe MCP agent also exposes the same snapshot as the read-only `adem_processes` tool. Its live protocol check passed `initialize`, `tools/list` and `tools/call`. The tool is intentionally separate from CatchMe’s screen and activity tools. The open-source export contract works without that optional agent adapter, so other Linux users can consume the JSON from their own local integration.

To inspect it manually:

```bash
python3 -m json.tool ~/.catchme/integrations/adem-processes.json
systemctl --user status adem-catchme-export.timer
```

This integration does not send screenshots, screen summaries, window titles, URLs, command lines, paths, credentials or activity history to CatchMe.
