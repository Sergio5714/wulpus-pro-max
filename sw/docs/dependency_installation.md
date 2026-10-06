# Dependency installation

The software project uses `uv` for Python dependency management.

1. Install `uv`: https://docs.astral.sh/uv/getting-started/installation/
2. Open a terminal in the `sw` folder.
3. Create the local environment and install the standard notebook dependencies:

```bash
uv sync
```

4. Start Jupyter from the same folder:

```bash
uv run jupyter notebook
```

5. Open `wulpus_pro_example.ipynb` for acquisition and configuration, or
   `wulpus_pro_firmware_update.ipynb` for firmware updates.

## Optional dependency groups

Run these commands from the `sw` folder:

```powershell
# Desktop application
uv sync --locked --group desktop

# Desktop application with firmware flashing
uv sync --locked --group desktop --group flash

# Development, formatting, tests, and packaging
uv sync --locked --group desktop --group flash --group dev
```

Launch the desktop application from the `sw` folder:

```powershell
uv run --locked --group desktop --group flash python -m desktop_gui.main
```
