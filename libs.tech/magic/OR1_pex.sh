#!/bin/sh
# OR1 magic PEX wrapper:  OR1_pex.sh <gds-file> <top-cell> <out.spice>
#
# Magic writes <cell>.ext / <cell>.res.ext into the current directory and
# reuses them when their timestamps look current, so a shared directory (the
# old version used /tmp) leaks stale extraction data between runs and silently
# produces a netlist with no resistors.  Every invocation therefore gets a
# private scratch directory.
set -e
PDK_ROOT=${PDK_ROOT:-/grid/OpenRule1um/OR1PDK}
PDK=${PDK:-OR1}
HERE=$(cd "$(dirname "$0")" && pwd)
export PDK_ROOT PDK

# Magic's resistance extraction changed in 8.3.597: `extract do resistance`
# then produces <cell>.res.ext in sequence with the normal extraction.  The
# magic bundled with some librelane environments is 8.3.623/older builds whose
# extractor returns an empty .res.ext, so prefer an explicitly selected newer
# binary (OR1_MAGIC), else a system install, else whatever is on PATH.
MAGIC_BIN=${OR1_MAGIC:-}
if [ -z "$MAGIC_BIN" ] && [ -x /usr/local/bin/magic ]; then
    MAGIC_BIN=/usr/local/bin/magic
fi
if [ -z "$MAGIC_BIN" ]; then
    MAGIC_BIN=$(command -v magic)
fi

WORK=$(mktemp -d "${TMPDIR:-/tmp}/or1pex.XXXXXX")
cd "$WORK"
trap 'cd /; rm -rf "$WORK"' EXIT INT TERM

# magic returns non-zero on benign extraction warnings ("Total of N errors
# (check feedback entries)"), so judge success by the netlist itself.
set +e
"$MAGIC_BIN" -dnull -noconsole -rcfile "$HERE/OR1.magicrc" \
      "$HERE/OR1_pex.tcl" "$@"
set -e

if [ ! -s "$3" ]; then
    echo "OR1 PEX: no netlist produced" >&2
    exit 1
fi
exit 0
