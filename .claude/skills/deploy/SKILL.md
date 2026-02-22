# Deploy SYNAPSE

Deploy changes from repo source to Houdini prefs via the installer.

## Workflow

1. **Verify source**: Confirm all changes are in the repo source (`~/.synapse/houdini/`) — NOT in deployed copies (`~/houdini21.0/`)
2. **Run installer**: Execute `python ~/.synapse/install.py` to redeploy shelf, panel, toolbar, and icons
3. **Confirm deployment**: Check file timestamps in `~/houdini21.0/` match the source
4. **Report**: List what changed and whether Houdini needs to be restarted to pick up the changes

## Notes

- Use `--dry-run` to preview what would be copied without making changes
- Use `--verify` to check current deployment matches source
- Use `--uninstall` to remove all Synapse files from Houdini prefs
- Panel changes require closing and reopening the Python Panel tab in Houdini
- Shelf changes require restarting Houdini
