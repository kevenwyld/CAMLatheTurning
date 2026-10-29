# CAM Lathe Turning (fork)

| :warning: WARNING: CAM Lathe Turning is experimental. Check every program in a simulator, and with care on the machine, before cutting. |

A FreeCAD CAM addon for CNC turning: facing, drilling, roughing, profiling
and boring, chamfering, grooving and groove turning, threading and parting,
with a LinuxCNC lathe post processor.

This is a fork of [FreeCAD_Turning_Addon](https://github.com/dubstar-04/FreeCAD_Turning_Addon)
by **Daniel Wood** ([dubstar-04](https://github.com/dubstar-04)), who created
the addon and its geometry library, [LibLathe](https://github.com/dubstar-04/LibLathe).
It uses its own fork of LibLathe ([kevenwyld/LibLathe](https://github.com/kevenwyld/LibLathe))
as a submodule, and the same Python module names as the original, so the two
cannot be installed side by side. This repository was previously named TurningAddon.

<img width="1954" height="1048" alt="Screenshot_2026-10-21_17-16-55" src="https://github.com/user-attachments/assets/551bcb13-87cb-45fe-8ed0-61427d220ebd" />

The addon adds its operations to the CAM workbench, in the CAM menu and on a
**Turning** toolbar. A proof of concept simulator for them is
[CAM Rotary Simulator](https://github.com/kevenwyld/CAMRotarySim).

## Features
* Turning operations: Face, Drill, Rough, Profile (outside and boring),
  Chamfer, Groove, Groove-Turn, Thread (G33 passes or a G76 cycle) and Partoff
* Tool shapes: ISO turning insert, grooving / parting insert, full radius
  insert, threading insert, with example bits and optional holders
* Constant surface speed (G96) from CAM's feeds and speeds data
* Collision checks of the insert's outline, and refusals that can be waived
* A LinuxCNC lathe post processor

## Requirements
* FreeCAD 1.1 or later; developed on FreeCAD 27 development builds (the post
  processor is found automatically only on builds whose CAM scans addons for
  posts; on others, copy `Posts/linuxcnc_lathe_post.py` into your macro folder)
* CAM tool bits (legacy tools are not supported)
* Python 3, Qt 6

## Installation
1. `git clone --recurse-submodules` this repository, or download its `.zip`,
   into your [FreeCAD `Mod/` directory](https://wiki.freecad.org/Installing_more_workbenches).
2. Restart FreeCAD.

If the `LibLathe` folder inside the addon is empty, run
`git submodule update --init --recursive` in the addon's folder.

## Operations
Every operation works between **Front (Z)** and **Back (Z)** (the Z range, set
on its Z Range page from the selection or by hand) and between **Min** and
**Max Diameter** (the Diameters page: worked out unless ticked). It starts and
ends at a safe position outside the stock. Each option has a tooltip.

| Operation | Tool | What it does |
|---|---|---|
| Turn Face | ISO insert | Faces from the stock's front down to Back, in to Min Diameter; a selected flat face is the plane faced to |
| Turn Drill | CAM drill | Drills the selected hole on the spindle axis: peck (G83), chip break (G73), drill (G81) or dwell (G82), canned or written out |
| Turn Rough | ISO insert | Roughing passes at the step over, then a cleanup pass along the part at the stock to leave |
| Turn Profile | ISO insert | Finish passes along the part's outline, with a spring pass; leaves the front face to Turn Face unless asked |
| Turn Chamfer | ISO insert | A chamfer or fillet at the selected circular edges (sharp outside corners) |
| Turn Groove | Grooving / full radius insert | Plunges (or side-turns, level by level), then finishes down one wall, across and up the other |
| Turn Groove-Turn | Grooving / full radius insert | Groove (plunge) turning along the whole profile in both directions |
| Turn Thread | Threading insert | A single-point thread on the selected cylindrical face, external or internal |
| Turn Partoff | Grooving / full radius insert | One plunge at the part's back face, past the centreline (or Min Diameter) by the overtravel |

Notes on particular options:

* **Side = Internal** (Rough, Profile) bores: tick Min Diameter and set it to
  the hole bored from (boring from solid is not possible); Max Diameter
  defaults to the bore's largest diameter. The insert is programmed to the
  mirror of its turning reference point (largest radius, chuck-side flank).
* **Min Diameter**, ticked: Rough, Profile and Turn Groove turn to it across
  the Z range (into the model where it is bigger, left at it where smaller);
  Face and Partoff stop at it (a tube's bore).
* **Stock to leave X / Z**: radial (per side) and axial. Negative values cut
  under the model's size, e.g. -0.075 turns a 12 mm model to 11.85.
* **Break edges** (Rough, Profile, Face): chamfer every sharp outside corner
  the finishing pass goes over; inside corners, modelled chamfers and fillets,
  corners on the axis and the part's back end are left alone.
* **Lead-in** (Rough, Profile), **Retract** and **Radial clearance**: worked
  out and shown greyed unless ticked.
* **Peck** (Groove, Groove-Turn, Partoff): plunges feed in by the peck depth,
  backing off or retracting fully between pecks.
* **Feeds**: the tool controller's horizontal feed is the cutting feed; the
  vertical feed is for plunges and entries (with none set, the horizontal
  feed is used and CAM Sanity says so). Turn Thread is fed by the pitch.
* **Constant surface speed** (Spindle group): G96 with the surface speed from
  the tool's Feeds & Speeds preset for the stock material, else the material's
  machinability, and the Job's machine's maximum rpm; G97 after the operation.
  Tick Set to give either by hand. The turning tools carry a Chipload, which
  with one cutting edge is the feed per revolution.

## Threading
**Turn Thread** selects the cylindrical face to thread on its Z Range page; a
bore is an internal thread. Standards: ISO metric coarse and fine, UNC, UNF,
or Custom (pitch and depth as entered). Tolerance classes (6g, 4g6g, 6H, 2A,
3A, 2B, 3B, or Basic) come from the thread tables CAM ships for Thread
Milling; a standard thread is cut so its pitch diameter is in the middle of
the class's range. The report on the page gives the diameter to turn or bore
first, the pitch diameter and measurement over wires, the root, the passes
and the Z range. Passes, first pass depth, lead-in, thread length and run-out
are worked out unless ticked. Output is explicit **G33** passes, or one
**G76** cycle with Use G76 cycle (CAM's own posts drop G76's Q word; the
addon's post keeps it).

The insert is kept clear of the part: nothing in front of the thread may
stand above its root (a chamfer or a relief groove), and a shoulder behind
it must clear the insert's flank. Where the part is held is not assumed from
the stock.

TODO: take the thread sizes from CAM's tables as well. Not yet: CAM's metric
internal table has few fine pitches, its internal Unified files misname the
large sizes, and a few metric pitches are not ISO ones.

## Tools
FreeCAD's tool library has no turning shapes, so the addon provides four
(ISO turning insert, Grooving, Full Radius, Threading) and example bits.
In the CAM workbench run **Install Turning Tools** (CAM menu or Turning
toolbar) to add them to your CAM tool assets, then add the bits to a tool
library or make your own from the shapes. Running it again after an update
adds new example bits; bits you already have are never changed. The shapes
themselves are brought up to date in your store whenever the CAM workbench
loads; a copy of yours that differs is kept in
`Backup/CAMLatheTurning` in your CAM asset folder (the Report view says where).

Tools already in a document keep the 3D model they were made with. **Rebuild
Turning Tool Models** (CAM menu, at the end of the turning commands; no
toolbar button) rebuilds them from the current shapes, keeping their values:
the selected tool controllers or tools, every tool of a selected Job, or with
nothing selected every turning tool in the document. Tool controllers,
operations and paths are unchanged.

* **ISO turning insert**: TipAngle, EdgeLength, TipRadius (the nose radius),
  Rotation. Programmed to the imaginary tip.
* **Grooving**: Width, CornerRadius (at most half the width), GroovingDepth
  (La max), TurningDepth (T). **Full Radius**: Width (the end is a radius of
  half of it), NeckWidth (less than Width: a lollipop groove-turn insert),
  SideRelief. Both are programmed to the cutting edge's point closest to the
  axis and the chuck-side flank.
* **Threading**: ProfileAngle, TipRadius, Width; programmed to the profile's
  theoretical sharp point.
* Shanks and boring bars can be drawn with the insert, for a simulation to
  show the whole tool (visual only): ISO B x H, DCON, LF and WF parameters.

Every shape also has a Diameter, which CAM requires but turning does not use.

## Post processor
The **linuxcnc_lathe** post (in `Posts/`, found through package.xml) is CAM's
LinuxCNC post with what a lathe program needs. Choose it in the Job or as the
machine's post in CAM's machine editor. A copy in your macro folder hides the
addon's own.

* **G18 G8** at the start: the XZ plane and radius mode (X is a radius).
* **G33 and G76** accepted, with G76's Q (infeed angle) and E (run-out) kept.
* **G96 and G97** accepted; G96's surface speed in ft/min for an inch program.
* **No up-and-back between operations**: consecutive rapids at the same safe
  X are reduced to the first and the last.

On a mill used as a lathe, CAM's LinuxCNC post is the one to use.
Diameter-mode output (G7) is not offered yet.

## Refusals, and Generate anyway
Some checks refuse a path the operation can make because they find it wrong.
Each can be waived per operation: the op's page shows the reason with a
**Generate anyway** button; waived checks are listed there (with **Restore**),
kept in the **Ignored Checks** property and reported at every recompute.

| Check | Refuses when | Waived, the op |
|---|---|---|
| `path-intersects-part` | Rough, Profile or Groove's path cuts into the model | uses the path as calculated |
| `part-defeaturing-failed` | the outline the op can follow cuts into the part | uses that outline |
| `face-cuts-part` | Turn Face would cut into the part in front of the plane | faces to the plane and diameter set |
| `thread-front-clearance` | the part stands above the root right in front of the thread | uses the lead-in as set, or three pitches |
| `thread-lead-in-too-long` | the lead-in set doesn't fit in front of the thread | uses the lead-in as set |
| `thread-hits-behind-end` | the insert would hit the part behind the thread's end | ends the thread where it is set |
| `groove-narrower-than-blade` | the Z range is narrower than the blade | cuts the blade's width |
| `css-no-max-rpm` | constant surface speed has no maximum spindle speed | posts G96 without D (the machine's own limit) |

Where there is no sensible path (a zero pitch, the wrong kind of tool, Min
Diameter above Max, Front behind Back), the operation still refuses.

## Limits
* **Z range selection**: faces, edges or whole objects selected on the Z
  Range page set Front and Back to the range they span; everything in that
  range is turned. Tick either end to set it by hand; the arrow buttons take
  the Z of the feature selected in the 3D view. Back is a hard stop toward
  the chuck: set it short of the jaws.
* **Models**: all the Job's models are turned as one. A model or stock off
  the spindle axis is reported as an error by every operation; **Turning >
  Put on Spindle Axis** moves them (X and Y only) exactly onto it. Stock made
  from the model's bounding box (Create from base) cannot be moved: use
  cylinder stock.
* **Boring**: the boring bar's diameter and reach are not checked, only the
  insert's outline; Radial clearance and Retract default to 0.5 mm there.
* **Collision checks**: Rough, Profile and Face sweep the insert's outline
  along the path and report where an edge or the body would enter the part;
  the path is still made. Holders and the chuck are not checked.
* The limits apply to the tool tip: at Front the nose may reach one nose
  diameter past the limit; at Back and Min Diameter the whole nose stays inside.

## CAM integration
CAM recognises operations by their module name, so the addon extends CAM's
check at start-up to include its own (context menu, dressups, Array / Copy,
Inspect, Post Selected); a lathe path is offered only the Axis Map and Path
Boundary dressups.

## Credits
* **Daniel Wood** ([dubstar-04](https://github.com/dubstar-04)): original
  author of the Turning Addon and LibLathe.
* **Brett Parker**: contributions to LibLathe.
* **Keven Wyld** ([kevenwyld](https://github.com/kevenwyld)): maintainer of
  this fork.

Turning in FreeCAD CAM has a discussion thread on the
[FreeCAD forum](https://forum.freecad.org/viewtopic.php?f=15&t=30563).

## Licence
LGPL-2.1, as the original (see LICENSE). LibLathe is GPL-2. The original
authors' copyright notices are kept in the files they wrote.

## Disclaimer
This is an experimental tool for development purposes and must be used at your own risk. Machine tools are dangerous and the authors of this tool will not be responsible for any damage or personal injury caused by using incorrect tool paths or machining parameters.
