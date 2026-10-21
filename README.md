# FreeCAD Turning Addon ![Python package](https://github.com/dubstar-04/FreeCAD_Turning_Addon/workflows/Python%20package/badge.svg?branch=master)
A FreeCAD Path Addon to encourage the development of CNC turning functionality for the PATH workbench.

| :warning: WARNING: Turning Addon is currently experimental / proof of concept and only suitable for testing. |

## Description
This addon when installed will appear in the Path Workbench toolbar menu and will allow the creation of turning paths for use with a CNC lathe. This addon includes [LibLathe](https://github.com/dubstar-04/LibLathe) as a submodule.

## Features
* Turning Roughing operation
* Turning Facing operation
* Turning Profiling operation
* Turning Parting operation

## Requirements
* FreeCAD v0.21
* Path Toolbits (Legacy tools are not supported)
* Python3
* Qt5

## Installation
1. Use `git clone --recurse` or download the `.zip` file of this repo directly in to your [FreeCAD `Mod/` directory](https://www.freecadweb.org/wiki/Installing_more_workbenches).
2. Restart FreeCAD

Note: If the LibLathe folder inside the addon is empty or missing you may need to add the submodule manually: `git submodule update --init --recursive`

## Threading
**Turn Thread** cuts a single-point thread with a **Threading** insert
(ProfileAngle, TipRadius, Width; programmed to the profile's theoretical
sharp point). Select the cylindrical face to thread on the Z Range page: it
gives the thread's Z range and the diameter it is cut from, and a bore is
an internal thread (Type can also be set by hand).

* **Thread standard / Size:** ISO metric coarse and fine, UNC, UNF, or
  Custom (enter pitch and depth). A standard thread is cut to the standard's
  root diameter (external, d - 1.22687 P) or major diameter (internal),
  whatever the surface was turned or bored to, so turn the crests to their
  tolerance first (e.g. 11.701-11.966 for M12x1.75 6g). The page shows the
  pass schedule, and warns in red when the selected diameter does not fit
  the size (over the major diameter, or well under it).
* **Thread length** (0: the whole selected diameter), **Passes** (0: the recommended
  number for the pitch), **First / Min pass depth**, **Degression** (1.5 by default: a gentle schedule
  with a light first pass; 2 removes the same area each pass, the first deepest), **Infeed** (modified
  flank 29.5 degrees by default, flank 30, or radial), **Spring passes**,
  **Lead-in** (0: three pitches, so Z is at speed).
* Output: explicit passes using **G33** (spindle-synchronized motion; works
  on a mill with a spindle encoder, such as PathPilot in mill mode), or one
  **G76** cycle with **Use G76 cycle** on controls that have it. Both are
  marked for CAM's posts to pass through. CAM's posts currently drop G76's
  Q word (the infeed angle), so check a posted G76 line or use the explicit
  passes.
* The insert is kept clear of the part: nothing in front of the thread may
  stand above its root (every pass starts in front at depth, so the part
  there needs a chamfer or a relief groove), and a shoulder behind it must
  clear the insert's flank; the op says where the thread must end. Where the
  part is held (chuck, collet, fixture) is not assumed from the stock: keep
  the insert clear of it.

## Diameter limits
The **Diameters** page limits every operation: **Min Diameter** (e.g. the
bore of a tube: Face finishes the face to its edge, Partoff goes just past
it) and **Max Diameter** (the outside the material already has). The arrow buttons beside
them take the diameter of the selected circular edge, cylindrical face or
vertex; a flat ring-shaped face, such as the end of a tube, gives its inner
diameter for Min and its outer for Max.

## Operation settings
* **Step over**: Rough, the depth of cut per pass (per side); Profile, the
  spacing of the finish passes; Face, the step along Z; Turn Groove, the
  spacing of the plunges. Turn Groove's defaults to 0.7 x the insert width
  (Sandvik recommends 0.5 to 0.8 x for the cuts after the first), as an
  expression that follows the tool; clear the expression (the fx button) to
  set it by hand.
* **Stock to leave X / Z**: material left radially (per side, on diameters)
  and axially (on faces and shoulders). With equal values the offset is exact;
  with different values corners stay sharp instead of being rounded by the
  stock. Documents with the older single Stock to leave are converted when
  opened.
* **Finish passes**, **Finish step over** (their spacing) and **Spring
  pass** (repeat the last one once more, with no step over): Profile and
  Turn Groove.
* **Profile** follows the part's outline but leaves the front face to Turn
  Face; turn on **Finish front face** to include it.
* **Turn Groove** plunges across each stretch the blade can reach, then
  finishes. **Finish direction**: *In, across and out* (default: down one
  wall, along the bottom and up the other, for the best finish) or *From
  each wall to the middle*. It never takes a cut more than the insert's
  Turning Depth deep over more than the Turning Depth of length: where the
  plunges leave more (e.g. a flat blade over a fillet, or a groove no plunge
  fits), it adds short side-turning passes, and says so in the Report view.

## Grooving, parting and full radius inserts
Two tool shapes cover these inserts:

* **Grooving**: a flat-bottomed blade with a radius on each corner. Width
  (S in most catalogs), CornerRadius (R, at most half the width),
  GroovingDepth (La max: the deepest the blade can go before the holder
  would touch), TurningDepth (T: the largest sideways depth of cut).
* **Full Radius**: a blade ending in a semicircle of half its width. Width,
  GroovingDepth and TurningDepth.

Both also have a Diameter, which CAM requires but turning does not use; it
follows the width and is not shown in the tool editor. The tool
is programmed to its reference point: X at the cutting edge's point closest
to the axis, Z at the chuck-side flank. Touch it off the same way: X on a
turned diameter, Z on a faced end with the chuck-side flank.

**Turn Groove** cuts with these inserts in both directions. It plunges
straight in to rough (at most Step Over apart along Z), leaving Finish
Allowance, then follows the profile front to back with the finish passes.
The whole blade stays inside the Z Range, so it never touches the part
outside it; to finish a wall right up to its top, include a little of the
part beyond the wall in the range. The grooving depth is measured from Max
Diameter (default: the stock), which is also where plunges start; if the
surface has already been turned smaller, set Max Diameter to that diameter.

**Turn Partoff** parts off with a Grooving or Full Radius insert: one plunge
with the blade's part-side flank on the part's back face (the model's, or
the back of a selection on the Z Range page), Overtravel (default 0.2 mm)
past the centreline so no pip is left, or past Min Diameter if one is set
(the bore of a tube). It warns when the insert's grooving depth cannot
reach. Where the part is held is not assumed from the stock: the blade may
reach past the stock's end, so keep it clear of the fixture.

Rough, Profile and Face need a turning insert, and Turn Groove and Turn
Partoff a grooving
or full radius insert; each refuses the other kind with a message.

## Roughing
Rough finishes with a cleanup pass: a contour along the part at the stock to
leave, so the finishing pass meets an even amount of material instead of the
staircase the roughing passes leave on tapers and curves. Turn it off with the
operation's CleanupPass property.

Every operation starts and ends at a safe position outside the stock diameter
and a clearance in front of the stock, and only moves straight in X or along
Z outside the stock to get there.

## Limits
Rough and Profile only cut inside the operation's limits:

* **Start Depth / Final Depth** (Z). Final Depth is a hard stop toward the
  chuck: no tool move goes past it, so set it short of the jaws. If Start
  Depth is behind the front of the stock, passes are entered radially from
  outside the stock instead of along Z (this assumes the tool can plunge).
* **Z Range selection.** Selecting faces, edges or whole objects (for
  example a sketch or Draft wire drawn to mark the range) on the operation's
  Z Range page sets Start and Final Depth to the Z range they span.
  Everything in that range is turned. A selection with no length along Z,
  such as a single shoulder face or circular edge, is rejected.
* **Min Diameter.** No cutting below this diameter. Rough skips passes below
  it and Profile stops at it, re-entering at feed where the profile comes
  back above it.
* **Max Diameter.** The outer diameter roughing starts from (default: the
  stock diameter).

The limits apply to the tool tip. At Start Depth the round nose of the insert
can reach up to one nose diameter past the limit; at Final Depth and Min
Diameter the whole nose stays inside.

## Turning tools
The turning operations need a turning tool bit. FreeCAD's tool library has no
turning shape, so the addon provides an ISO turning insert shape and an
example bit, plus the Grooving, Full Radius and Threading shapes with an
example insert each. To add them to your CAM tool assets, switch to the CAM workbench and
run **Install Turning Tools** from the CAM menu. Running it again after an
update brings the shapes up to date; tool bits you have are never changed. Existing files
are never overwritten. Then add the example bit to a tool library, or create
your own bits from the **ISO Turning Insert** shape.

To install them by hand instead, copy `Assets/Shape/isoshape.fcstd` and
`Assets/Shape/isoshape.svg` into the `Tools/Shape` folder of your CAM asset
directory, and import `Assets/Bit/CCMT060204R.fctb` from the tool library.

Set TipRadius to your insert's nose radius. Rotation must be greater than 0
and TipAngle less than 90 degrees.

## Feedback
If you have feedback or need to report bugs please participate on the related [Path Forum](https://forum.freecadweb.org/viewtopic.php?f=15&t=30563&start=0).

## Disclaimer
This is an experimental tool for development purposes and must be used at your own risk. Machine tools are dangerous and the author of this tool will not be responsible for any damage or personal injury caused by using incorrect tool paths or machining parameters.
