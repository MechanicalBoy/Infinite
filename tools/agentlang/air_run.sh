#!/bin/bash
# Pro side: ship the NEWEST app build and this branch to the Air, check them, then start a harness job there.
#   air_run.sh <jobname> <harness args...>        e.g. air_run.sh pilot2 --arms ... (the loop is in the job script)
# Pins the snapshot by sha256; the harness refuses any other app. Needs the Air's ~/.claude-remote-token.
set -e
JOB="$1"; shift
SSHO="ssh -o BatchMode=yes -o IdentitiesOnly=yes -i $HOME/.ssh/id_ed25519"
AIR=namansoni@Namans-MacBook-Air.local
BR=$(git rev-parse --abbrev-ref HEAD)
rm -rf /tmp/al-snap && mkdir -p /tmp/al-snap && cp -R "$HOME/infinte/build/Infinite.app" /tmp/al-snap/
SHA=$(shasum -a 256 /tmp/al-snap/Infinite.app/Contents/MacOS/Infinite | cut -c1-12)
rsync -aq --delete -e "$SSHO" /tmp/al-snap/Infinite.app/ $AIR:al-bin/Infinite.app/
GIT_SSH_COMMAND="$SSHO" git push -qf $AIR:infinte "$BR:refs/heads/pro/agent-language-p2" >/dev/null 2>&1
$SSHO $AIR bash -s -- "$JOB" "$SHA" "$@" <<'REMOTE'
JOB=$1; SHA=$2; shift 2
export PATH=$HOME/.local/bin:$PATH
cd ~/infinte-wt/agent-language-pilot && git stash -q 2>/dev/null; git merge -q --ff-only pro/agent-language-p2; git stash pop -q 2>/dev/null
export INFINITE_APP=$HOME/al-bin/Infinite.app/Contents/MacOS/Infinite INFINITE_APP_SHA=$SHA
[ "$(shasum -a 256 $INFINITE_APP | cut -c1-12)" = "$SHA" ] || { echo "sha mismatch on the Air"; exit 1; }
python3 tools/agentlang/freeze.py check | tail -1
python3 tools/agentlang/validate_all.py | tail -1 | grep -q '"failed": 0' || { echo "validate_all failed on the pinned app"; exit 1; }
export CLAUDE_CODE_OAUTH_TOKEN=$(cat $HOME/.claude-remote-token)
mkdir -p tools/agentlang/out
nohup bash tools/agentlang/jobs/$JOB.sh "$@" > tools/agentlang/out/$JOB.log 2>&1 < /dev/null &
echo "pinned app $SHA; job $JOB started"
REMOTE
