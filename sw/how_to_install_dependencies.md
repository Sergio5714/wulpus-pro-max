# How to install Python requirements

The software project uses `uv` for Python dependency management.

1. Install `uv`: https://docs.astral.sh/uv/getting-started/installation/
2. Open a terminal in the `sw` folder.
3. Create the local environment and install dependencies:

```bash
uv sync
```

4. Start Jupyter from the same folder:

```bash
uv run jupyter notebook
```

5. Open `wulpus_pro_example.ipynb` in the browser and follow its instructions. Older notebook variants are archived under `legacy/`.
