# Security and privacy

## Naksha does not run AI-written code

There is no `exec`, no `eval`, and no "run this Python" tool. The agent can only call a
fixed set of QGIS operations and the Processing algorithms you already have installed —
it cannot invent new code to run. That is a deliberate limit, not an oversight: it is the
main risk in an AI plugin, and the plugin repository's scanner treats it as critical and
non-waivable.

The package also contains no subprocess calls, no shell invocation, no pickle or YAML
deserialisation, no bundled executables or binaries beyond the icon, and no third-party
dependencies at all — only the Python standard library and QGIS's own API. Every write to
your project is gated by the approval mode you choose, and logged to the "Naksha" tab.

# What leaves your machine

Naksha sends data to an AI model only when you send a message (or an MCP client app
calls a tool). What travels: your chat text, a compact project snapshot (layer names,
feature counts, field names, CRS codes — **never feature geometry or attribute data
unless a tool you approved returns it**), and tool results.

Where it goes depends on the provider **you** configured:

| Setup | Data goes to |
|---|---|
| Ollama (default) | **Nowhere.** Localhost only, works offline. |
| Your API key (any vendor) | That vendor, under their API terms. |
| AI Bridge (MCP) | The subscription app you connected — governed by that app's own privacy terms. |

The bridge itself is localhost-only (127.0.0.1, random port, per-session token) and off
by default. **Note:** the dock's approval modes govern the dock's own agent. A connected
MCP client calls tools directly, so its *own* approval prompts are what gate those calls —
turn the bridge off if you don't want that path open. Every tool call and result is logged locally to the "Naksha" tab in the QGIS
log panel. API keys live in QGIS's encrypted auth store, never in plain files. Naksha
has no telemetry, no accounts, and no servers of its own.
