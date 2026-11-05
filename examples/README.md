# Plexus Live

One click starts ComfyUI with your models, and then a Plexus session you drive from a terminal.

```
python examples/plexus_live.py
```

Or double-click `Plexus Live` on the desktop.

## What it does

1. It rebuilds the Rust core if it is older than the crates. The build stays in the repo's own `target/`, never in the harness's.
2. It starts `G:\COMFY\ComfyUI` in its own window, unless ComfyUI already answers on 8188, and waits for `/system_stats`.
3. It checks the checkpoints ComfyUI lists sit under `G:\COMFYUI_Database\Models`.
4. It opens a new session folder under `%LOCALAPPDATA%\Plexus\sessions` and gives you a prompt.

## The session

Two projects, one exchange, one neuron watching `/Exchange/LookState.temperature`.

| Command | What it does |
|---|---|
| `temp 1.5` | Project A writes the temperature, and the neuron wakes if it moved more than 0.2 |
| `status` | ComfyUI, the neuron and what project B reads |
| `help` | The list |
| `quit` | Stops the neuron and leaves ComfyUI running |

Run it without the prompt: `python examples/plexus_live.py --script "temp 1.5; status; quit"`.

## What it does not do yet

It never queues a ComfyUI job, because the organ does not exist until phase 2. The neuron's action is a grade hint for now, and the organ joins here when phase 2 has one.

## Why it does not use comfyui_launcher.bat

That file's countdown calls `choice /c " qo"`. Windows rejects the space with "Invalid choice", so the file always stops at its Options menu waiting for a key. The launcher runs the file's Stable command with the file's environment instead, so `COMFYUI_ENV` in `plexus_live.py` has to follow that file by hand.

## Flags

| Flag | What it does |
|---|---|
| `--minimized` | ComfyUI's window starts minimized and never takes the focus |
| `--stop-comfyui-on-exit` | Stops ComfyUI when the session ends, only if this launcher started it |
| `--script "a; b"` | Runs commands instead of the prompt |
| `--timeout 300` | Seconds to wait for ComfyUI to answer |
| `--comfyui-root`, `--models-root`, `--url`, `--sessions-root` | Point it somewhere else |
