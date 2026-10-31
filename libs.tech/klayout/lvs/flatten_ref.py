#!/usr/bin/env python3
"""Build a flattened SPICE reference netlist from a cell CDL + a design Verilog.

Used to give the KLayout LVS deck (OR1.lvs) a device-level schematic for
full-chip comparison: the OpenRule1um CDL describes the standard cells, the
Verilog netlist produced by the flow describes the instance/pin wiring.

Usage:
    flatten_ref.py <cells.cdl> <design.v> <top> <out.spice>
"""
import re
import sys


def parse_cdl(path):
    """Return {cell: (pins, [device_lines])}."""
    cells = {}
    cur = None
    for raw in open(path):
        line = raw.rstrip('\n')
        s = line.strip()
        if s.lower().startswith('.subckt'):
            parts = s.split()
            cur = parts[1]
            cells[cur] = (parts[2:], [])
            continue
        if s.lower().startswith('.ends'):
            cur = None
            continue
        if cur and s.startswith('M'):
            cells[cur][1].append(s)
    return cells


def parse_verilog(path):
    """Return (ports, [(cell, inst, {pin: net})])."""
    text = open(path).read()
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'//[^\n]*', '', text)
    m = re.search(r'module\s+(\w+)\s*\((.*?)\);(.*?)endmodule', text, re.S)
    if not m:
        raise SystemExit("no module found in verilog")
    ports = [p.strip() for p in m.group(2).replace('\n', ' ').split(',') if p.strip()]
    body = m.group(3)
    # expand vector ports ([3:0] q -> q[3] ... q[0])
    buses = {}
    for bm in re.finditer(r'\b(?:input|output|inout)\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*([A-Za-z_]\w*)', body):
        hi, lo, name = int(bm.group(1)), int(bm.group(2)), bm.group(3)
        buses[name] = list(range(hi, lo - 1, -1)) if hi >= lo else list(range(hi, lo + 1))
    expanded = []
    for p in ports:
        if p in buses:
            expanded.extend('%s[%d]' % (p, i) for i in buses[p])
        else:
            expanded.append(p)
    ports = expanded
    insts = []
    # CELL inst ( .PIN(net), .PIN2(net2) );
    for mm in re.finditer(r'\b([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*;', body, re.S):
        cell, inst, conns = mm.group(1), mm.group(2), mm.group(3)
        if cell in ('input', 'output', 'inout', 'wire', 'reg', 'assign'):
            continue
        pins = {}
        for pm in re.finditer(r'\.(\w+)\s*\(\s*([^)]*?)\s*\)', conns):
            pins[pm.group(1)] = pm.group(2).strip()
        insts.append((cell, inst, pins))
    return ports, insts


def main(cdl_path, v_path, top, out_path):
    cells = parse_cdl(cdl_path)
    ports, insts = parse_verilog(v_path)
    out = ["* flattened reference for %s" % top, ".subckt %s %s" % (top, " ".join(ports))]
    seen = 0
    for cell, inst, pins in insts:
        if cell not in cells:
            continue
        cpins, devs = cells[cell]
        amap = {}
        for p in cpins:
            amap[p] = pins.get(p, "%s.%s" % (inst, p))
        for d in devs:
            toks = d.split()
            # M<name> d g s b model ...
            new = list(toks)
            new[0] = "M%d" % seen
            for i in (1, 2, 3, 4):
                if toks[i] in amap:
                    new[i] = amap[toks[i]]
            out.append(" ".join(new))
            seen += 1
    out.append(".ends")
    open(out_path, 'w').write("\n".join(out) + "\n")
    print("wrote %s: %d devices, %d instances" % (out_path, seen, len(insts)))


if __name__ == '__main__':
    main(*sys.argv[1:5])
