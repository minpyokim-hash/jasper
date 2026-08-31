# claude-hud:setup

Verify that the Claude HUD statusline plugin is correctly installed and the script is executable.

## Steps

1. Check that `statusline.sh` exists at `$CLAUDE_PLUGIN_ROOT/statusline.sh`.
2. Ensure it is executable (`chmod +x`).
3. Confirm that `settings.json` contains a valid `statusLine` block pointing to the script.
4. Print a confirmation message with the resolved script path.

## Expected output

```
✓ Claude HUD plugin is installed.
  Script : <resolved path>/statusline.sh
  Refresh: every 2 seconds
  Padding: 1
```

If anything is missing, print a clear error message and the fix command.
