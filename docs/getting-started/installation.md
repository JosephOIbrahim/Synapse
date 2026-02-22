# Installation

## From Source (Development)

```bash
git clone https://github.com/JosephOIbrahim/Synapse.git
cd Synapse
pip install -e ".[dev]"
```

## With All Features

```bash
pip install -e ".[dev,websocket,mcp,routing,encryption]"
```

## Houdini Integration

Install the shelf tools and panel into Houdini:

```bash
python ~/.synapse/install.py
```

Options:

- `--dry-run` -- Show what would be installed without making changes
- `--verify` -- Check existing installation
- `--uninstall` -- Remove Synapse from Houdini

## Verify Installation

```bash
python -m pytest tests/ -v
```

Expected: ~777 tests passing (no Houdini required).
