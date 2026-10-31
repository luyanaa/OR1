# Copyright 2026 OR1 PDK contributors
#
# librelane plugin for the OR1 (OpenRule1um) PDK.
#
# Two things are wired here that LibreLane's stock Classic flow does not run:
#
#   * OR1.KLayoutLVS  -- the PDK's KLayout LVS deck
#                        (libs.tech/klayout/lvs/OR1.lvs).  LibreLane's own
#                        KLayout.LVS step is hard-coded to the IHP PDKs, so the
#                        OR1 deck is driven through the same wrapper that the
#                        PDK ships (run_lvs.sh) and reported as a metric.
#
#   * ClassicOR1      -- the stock Classic flow plus:
#                          Magic.RCX     (full R+C magic extraction, .rcx.spice)
#                          OR1.KLayoutLVS (KLayout LVS)
#
# Usage:
#
#   PYTHONPATH=<this directory> librelane --flow ClassicOR1 ...
#
# (LibreLane discovers any importable ``librelane_plugin_*`` package on
#  PYTHONPATH at start-up, so the flow and the step become available everywhere
#  the ``--flow`` choice list is built.)

import os
from os.path import join
from typing import Tuple

from librelane.common import Path, mkdirp
from librelane.config import Variable
from librelane.state import DesignFormat, State
from librelane.steps.step import Step, MetricsUpdate, ViewsUpdate
from librelane.steps import KLayout, Magic, OpenROAD
from librelane.flows.classic import Classic
from librelane.flows.flow import Flow


@Step.factory.register()
class OR1KLayoutLVS(Step):
    """
    Runs the OR1 KLayout LVS deck on the streamed-out GDS and reports the
    result as ``design__lvs_error__count``.
    """

    id = "OR1.KLayoutLVS"
    name = "KLayout LVS (OR1)"
    long_name = "Layout Versus Schematic (KLayout, OR1 deck)"

    inputs = [DesignFormat.GDS, DesignFormat.CDL]
    outputs = []

    config_vars = Step.config_vars + [
        Variable(
            "OR1_LVS_RUNNER",
            str,
            "Path to the OR1 KLayout LVS wrapper "
            "(default: <pdk>/libs.tech/klayout/lvs/run_lvs.sh).",
            default="",
        ),
    ]

    def run(self, state_in: State, **kwargs) -> Tuple[ViewsUpdate, MetricsUpdate]:
        kwargs, env = self.extract_env(kwargs)

        gds = state_in[DesignFormat.GDS]
        cdl = state_in[DesignFormat.CDL]

        runner = self.config["OR1_LVS_RUNNER"] or join(
            self.config["PDK_ROOT"],
            self.config["PDK"],
            "libs.tech/klayout/lvs/run_lvs.sh",
        )

        reports_dir = join(self.step_dir, "reports")
        mkdirp(reports_dir)
        prefix = join(reports_dir, "lvs.klayout.or1")

        # One schematic file: design CDL + the standard-cell CDLs.
        extra = [cdl]
        for key in ("CELL_CDLS", "EXTRA_CDLS"):
            value = self.config[key]
            if value:
                extra.extend(value)

        schematic = join(self.step_dir, "schematic.cdl")
        with open(schematic, "w") as out:
            for path in extra:
                if path is None:
                    continue
                with open(path) as fh:
                    out.write(fh.read())
                out.write("\n")

        result = self.run_subprocess(
            [
                "bash",
                runner,
                str(gds),
                self.config["DESIGN_NAME"],
                schematic,
                prefix,
            ],
            env=env,
        )

        ok = False
        with open(result["log_path"]) as fh:
            for line in fh:
                if "INFO : Congratulations! Netlists match" in line:
                    ok = True
                    break
                if "ERROR : Netlists don't match" in line:
                    ok = False
                    break

        return {}, {"design__lvs_error__count": 0 if ok else 1}


@Step.factory.register()
class OR1MagicPEX(Step):
    """
    Full R+C extraction through the PDK's magic entry point
    (libs.tech/magic/OR1_pex.sh).

    LibreLane's Magic.RCX uses its own spice_rcx.tcl, which calls
    `extract style`, resetting magic's extresist threshold back to the 10 ohm
    default -- every on-chip metal resistor is then below the cutoff and the
    netlist comes out with zero R elements.  The PDK script sets
    `extresist threshold 0` / `minres 0` (see OR1.magicrc) and yields the full
    resistor network.
    """

    id = "OR1.MagicPEX"
    name = "Magic full R+C extraction (OR1)"
    long_name = "Full Parasitics Extraction (magic, OR1 model)"

    inputs = [DesignFormat.GDS]
    outputs = [DesignFormat.SPICE_RCX]

    config_vars = Step.config_vars + [
        Variable(
            "OR1_PEX_RUNNER",
            str,
            "Path to the OR1 magic PEX wrapper "
            "(default: <pdk>/libs.tech/magic/OR1_pex.sh).",
            default="",
        ),
    ]

    def run(self, state_in: State, **kwargs) -> Tuple[ViewsUpdate, MetricsUpdate]:
        kwargs, env = self.extract_env(kwargs)

        gds = state_in[DesignFormat.GDS]
        design = self.config["DESIGN_NAME"]

        runner = self.config["OR1_PEX_RUNNER"] or join(
            self.config["PDK_ROOT"],
            self.config["PDK"],
            "libs.tech/magic/OR1_pex.sh",
        )

        out = join(self.step_dir, f"{design}.{DesignFormat.SPICE_RCX.value.extension}")
        self.run_subprocess(
            ["bash", runner, str(gds), design, out],
            env=env,
        )

        return {DesignFormat.SPICE_RCX: Path(out)}, {}


def _insert_after(steps, target, new_steps):
    out = []
    for step in steps:
        out.append(step)
        if step is target:
            out.extend(new_steps)
    return out


_OR1_STEPS = list(Classic.Steps)
_OR1_STEPS = _insert_after(_OR1_STEPS, KLayout.DRC, [OR1MagicPEX])
_OR1_STEPS = _insert_after(
    _OR1_STEPS, Magic.DRC, [OpenROAD.WriteCDL, OR1KLayoutLVS]
)


@Flow.factory.register()
class ClassicOR1(Classic):
    """
    Classic flow plus magic full-RC extraction and KLayout LVS.
    """

    Steps = _OR1_STEPS

    config_vars = Classic.config_vars + [
        Variable(
            "RUN_MAGIC_RCX",
            bool,
            "Enables the OR1.MagicPEX step (full R+C extraction).",
            default=True,
        ),
        Variable(
            "RUN_KLAYOUT_LVS",
            bool,
            "Enables the OR1.KLayoutLVS step (KLayout LVS deck).",
            default=True,
        ),
    ]

    gating_config_vars = dict(Classic.gating_config_vars)
    gating_config_vars["OR1.MagicPEX"] = ["RUN_MAGIC_RCX"]
    gating_config_vars["OR1.KLayoutLVS"] = ["RUN_KLAYOUT_LVS"]
