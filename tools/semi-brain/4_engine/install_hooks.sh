#!/bin/bash
# install_hooks.sh
# Installs non-blocking Git post-commit and post-merge hooks to keep the Semi-Brain continuously synchronized.

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_DIR" ]; then
  echo "Error: .git/hooks directory not found at $HOOKS_DIR"
  exit 1
fi

POST_COMMIT="$HOOKS_DIR/post-commit"
POST_MERGE="$HOOKS_DIR/post-merge"

cat << 'EOF' > "$POST_COMMIT"
#!/bin/bash
# Asynchronously trigger Semi-Brain incremental sync in background (non-blocking)
(
  python3 tools/semi-brain/4_engine/sync_brain.py --sync >/dev/null 2>&1
) &
EOF

cat << 'EOF' > "$POST_MERGE"
#!/bin/bash
# Asynchronously trigger Semi-Brain incremental sync in background (non-blocking)
(
  python3 tools/semi-brain/4_engine/sync_brain.py --sync >/dev/null 2>&1
) &
EOF

chmod +x "$POST_COMMIT"
chmod +x "$POST_MERGE"

echo "✅ Semi-Brain Git hooks installed successfully!"
echo "   - $POST_COMMIT (non-blocking background sync)"
echo "   - $POST_MERGE (non-blocking background sync)"
