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

# Notebook firmware flashing with esptool
uv sync --locked --group flash

# Desktop development, formatting, tests, and packaging
uv sync --locked --group desktop --group dev
```

Launch the desktop application from the `sw` folder:

```powershell
uv run --locked --group desktop python -m desktop_gui.main
```

The desktop application uses an external `espflash` executable for ESP32-C6
updates. Release builds embed it in the one-file executable; source runs find it
on `PATH` or through `WULPUS_ESPFLASH_EXECUTABLE`. The separate `flash` group
retains esptool for the notebook and development workflows.

For an explicit source-run selection, launch with `--esp32-flasher espflash`
and optionally `--espflash PATH`, or install the `flash` group and launch with
`--esp32-flasher esptool`.
