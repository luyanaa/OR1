#!/usr/bin/env python3
"""Convert the OpenRule1um LTspice symbols (OR1LIB/*.asy) into xschem .sym files.

Usage: python3 mk_syms.py <OR1LIB dir> <out symbols dir>
"""
import os, re, sys

SCALE = 0.5          # LTspice 16-unit grid -> xschem 8-unit grid

def parse(path):
    lines, pins, attrs = [], [], {}
    cur = None
    for raw in open(path, errors="replace"):
        p = raw.split()
        if not p:
            continue
        if p[0] == "LINE" and len(p) >= 6:
            lines.append((float(p[2]), float(p[3]), float(p[4]), float(p[5])))
        elif p[0] == "PIN" and len(p) >= 5:
            cur = [float(p[1]), float(p[2]), "", 0]
            pins.append(cur)
        elif p[0] == "PINATTR" and cur is not None and len(p) >= 3:
            if p[1] == "PinName":
                cur[2] = p[2]
            elif p[1] == "SpiceOrder":
                cur[3] = int(p[2])
        elif p[0] == "SYMATTR" and len(p) >= 3:
            attrs[p[1]] = p[2]
    return lines, pins, attrs

def emit(name, lines, pins, attrs):
    prefix = attrs.get("Prefix", "X")
    value = attrs.get("Value", name)
    out = [f"v {{xschem version=3.4.0}}",
           f"G {{type={prefix}",
           f'format="@name @pinlist @symname"',
           f'template="name=X1"',
           f"spice_sym_name={value}}}"]
    for (x1, y1, x2, y2) in lines:
        out.append(f"L 4 {x1*SCALE:.2f} {y1*SCALE:.2f} {x2*SCALE:.2f} {y2*SCALE:.2f} {{}}")
    pins.sort(key=lambda p: p[3])
    for (x, y, pname, order) in pins:
        px, py = x * SCALE, y * SCALE
        out.append(f"P 4 {px:.2f} {py:.2f} {px+4:.2f} {py:.2f} {px+4:.2f} {py+4:.2f} {px:.2f} {py+4:.2f} {{{pname}}}")
    out.append(f"T {{@name}} 12 -14 0 0 0.3 0.3 {{}}")
    out.append(f"T {{{value}}} 12 16 0 0 0.25 0.25 {{}}")
    return "\n".join(out) + "\n"

def main():
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(src)):
        if not fn.endswith(".asy"):
            continue
        name = fn[:-4]
        lines, pins, attrs = parse(os.path.join(src, fn))
        if not pins:
            print("skip (no pins):", fn)
            continue
        open(os.path.join(dst, name + ".sym"), "w").write(emit(name, lines, pins, attrs))
        n += 1
    print(f"{n} symbols written to {dst}")

if __name__ == "__main__":
    main()
