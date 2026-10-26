# CAM Lathe Turning (fork)

| :warning: WARNING: CAM Lathe Turning is experimental. Check every program in a simulator, and with care on the machine, before cutting. |

A FreeCAD CAM addon for CNC turning: facing, drilling, roughing, profiling
and boring, grooving and groove turning, threading and parting, with a
LinuxCNC lathe post processor.

This is a fork of [FreeCAD_Turning_Addon](https://github.com/dubstar-04/FreeCAD_Turning_Addon)
by **Daniel Wood** ([dubstar-04](https://github.com/dubstar-04)), who created
the addon and its geometry library, [LibLathe](https://github.com/dubstar-04/LibLathe).
This fork builds on that work with new operations, boring, threading to
standard tolerance classes, collision checking and a reworked user
interface; see Features below. It uses its own fork of LibLathe
([kevenwyld/LibLathe](https://github.com/kevenwyld/LibLathe)) as a submodule.
It uses the same Python module names as the original, so the two cannot be
installed side by side. This repository was previously named TurningAddon.

<img width="1954" height="1048" alt="Screenshot_2026-10-21_17-16-55" src="https://github.com/user-attachments/assets/551bcb13-87cb-45fe-8ed0-61427d220ebd" />

## Description
Once installed, the addon adds its operations to the CAM workbench, in a
Turning toolbar and menu, for creating turning paths for a CNC lathe (or a
mill used as one).

A proof of concept simulator to help visualize these new operations is available [here](https://github.com/kevenwyld/CAMRotarySim)

## Features
* Turning operations: Face, Drill, Rough, Profile (both outside and boring),
  Chamfer, Groove, Groove-Turn, Thread (G33 passes or a G76 cycle) and
  Partoff
* Turning tool shapes: ISO turning insert, grooving / parting insert, full
  radius insert, threading insert, with example bits
* A LinuxCNC lathe post processor
* The commands in the CAM menu and on a **Turning** toolbar in the CAM
  workbench

## Requirements
* FreeCAD 1.1 or later; developed and tested on FreeCAD 27 development builds
  (the post processor is found automatically only on builds whose CAM scans
  addons for posts; on others, copy `Posts/linuxcnc_lathe_post.py` into your
  macro folder)
* CAM tool bits (legacy tools are not supported)
* Python3
* Qt6

## Installation
1. Use `git clone --recurse` or download the `.zip` file of this repo directly in to your [FreeCAD `Mod/` directory](https://wiki.freecad.org/Installing_more_workbenches).
2. Restart FreeCAD

Note: If the LibLathe folder inside the addon is empty or missing you may need to add the submodule manually: `git submodule update --init --recursive`

## Threading
**Turn Thread** cuts a single-point thread with a **Threading** insert
(ProfileAngle, TipRadius, Width; programmed to the profile's theoretical
sharp point). Select the cylindrical face to thread on the Z Range page: it
gives the thread's Z range and the diameter it is cut from, and a bore is
an internal thread (Type can also be set by hand).

* **Thread standard / Size:** ISO metric coarse and fine, UNC, UNF, or
  Custom (enter pitch and depth).
* **Tolerance class:** 6g or 4g6g (metric external), 6H (metric internal),
  2A or 3A / 2B or 3B (Unified), or Basic, from the thread tables CAM ships
  for Thread Milling (Mod/CAM/Data/Threads). A standard thread is cut so its
  pitch diameter is in the middle of the class's range (for M12x1.75 6g:
  10.754, the root at 9.744), whatever the surface was turned or bored to;
  Basic, or a size not in the tables, cuts the basic profile (root
  d - 1.22687 P external, major D internal).
* **The report** at the bottom of the page gives what the thread needs and
  how it is cut: the diameter to turn (external, the major) or bore
  (internal, the minor) first, against the selected diameter; the pitch
  diameter range and the one cut to; the measurement over three best-size
  wires (external); the root or major diameter and the depth; the passes;
  the Z range and lead-in. It warns in red when the selected diameter does
  not fit the size at all (e.g. M10 chosen for a 12 mm bar).
* **Run-out**: over this last length of the thread each pass tapers out to
  the crest, still synchronised with the spindle, instead of stopping dead
  at full depth: a tapered G33, or G76's E with L2. One pitch by default
  (shown greyed); tick it and set 0 to stop dead, for a thread that ends in
  a relief groove. The report says where full depth ends. Thread operations
  made before the run-out keep stopping dead (Run-out ticked, at 0), so
  their programs do not change.
* **Thread length** (the whole selected diameter), **Passes** (the
  recommended number for the pitch), **First pass depth** (from the passes
  and the degression) and **Lead-in** (three pitches, so Z is at speed) are
  worked out by the op and shown greyed out; tick one to set it by hand,
  starting from the value shown. Passes and First pass depth are
  alternatives: a first pass and the degression decide the number of
  passes. **Min pass depth**, **Degression** (1.5 by default: a gentle
  schedule with a light first pass; 2 removes the same area each pass, the
  first deepest), **Infeed** (modified flank 29.5 degrees by default, flank
  30, or radial), **Spring passes**.
* Output: explicit passes using **G33** (spindle-synchronized motion; works
  on a mill with a spindle encoder, such as PathPilot in mill mode), or one
  **G76** cycle with **Use G76 cycle** on controls that have it. Both are
  marked for CAM's posts to pass through. CAM's own posts drop G76's Q word
  (the infeed angle); the addon's linuxcnc_lathe post keeps it (see Post
  processor).
* The insert is kept clear of the part: nothing in front of the thread may
  stand above its root (every pass starts in front at depth, so the part
  there needs a chamfer or a relief groove), and a shoulder behind it must
  clear the insert's flank; the op says where the thread must end. Where the
  part is held (chuck, collet, fixture) is not assumed from the stock: keep
  the insert clear of it.

### Thread data, and a TODO
The sizes and pitches come from the addon's own tables (ISO 261/262 metric
coarse and fine, ASME B1.1 UNC and UNF); the tolerance ranges from the
tables CAM ships for Thread Milling. **TODO:** take the sizes from CAM's
tables too, so the data is shared with Thread Milling and grows with CAM.
Not yet, because CAM's metric internal (6H) table has few fine pitches
(most fine internal threads would need Custom), its internal Unified files
misname the large sizes ("11/2-12" for 1-1/2-12), and a few of its metric
pitches are not ISO ones (e.g. M10 x 1.12).

## Feeds
The tool controller's two feeds, whose names come from milling, mean for
the turning operations:

* **Horizontal feed**: the cutting feed, for turning, facing, profiling and
  finishing, in any direction.
* **Vertical feed**: plunges and moves into the material: Turn Rough's and
  Turn Profile's entries, Turn Groove's, Groove-Turn's and Partoff's plunges
  and step downs, and Turn Drill's drilling feed. With none set the
  horizontal feed is used, and CAM Sanity (the post dialog's warnings and
  the Sanity report) says so: a caution for a turning insert, a warning for
  a drill or a grooving or parting blade, which plunge with it.

Turn Thread is fed by the pitch. A tool controller with no horizontal feed
gets CAM's own warning, and the operations still make their paths.

## Facing
**Turn Face** faces from the stock's front down to Back (Z), at the Step
over, radially from outside the stock in to Min Diameter. With nothing
selected Back is the part's front. Select a flat face (square to the axis)
on its Z Range page to face down to that face instead, e.g. a shoulder.

* **Min Diameter** is worked out (shown greyed; tick to set): the selected
  face's inner edge when the part is there just in front of it (a shoulder
  behind a smaller diameter, so the passes stop at that diameter), the
  centre otherwise (a front face, including one round a hole that is not
  drilled yet).
* A facing pass that would cut into the part is refused, with the Min
  Diameter it needs (e.g. a shoulder faced with Min Diameter set too small).

## Edge breaking and chamfers
* **Break edges** (Turn Rough, Turn Profile, Turn Face): tick it and give a
  size (0.2 mm by default) to chamfer every sharp outside corner of the part
  the finishing pass goes over: the front corner, the outer edges of
  shoulders and grooves (45 degrees at a square corner). Inside corners are
  left alone (breaking them would add material), and so are corners already
  modelled with a chamfer or fillet, corners on the axis and the part's
  back end. Turn Rough breaks them in its cleanup pass; Turn Face with a
  short pass round the front corner. The Report view lists the corners
  broken.
* **Turn Chamfer**: a chamfer or a fillet at chosen corners only. Select the
  corners' circular edges on its Edges page, and set **Corner** (Chamfer, or
  Fillet: an arc tangent to both edges) and **Size** (the chamfer's leg along
  each edge, or the fillet's radius). Each is cut by a short contour pass
  round it with nose radius compensation. Only sharp outside corners between
  two straight edges can be; the others (inside corners, corners next to a
  curve, edges too short for the size) are reported and left alone.

## Drilling
**Turn Drill** drills on the spindle axis with a CAM drill bit (the Drill
shape: Diameter and TipAngle). It has only the settings drilling uses.

* The hole is the Z range, as for every operation: on the Z Range page
  **Front (Z)** is where it starts and **Back (Z)** where the drill's full
  diameter (or its tip, with Depth to the drill's tip) ends. Select the hole
  (its cylindrical face) and both come from it, shown greyed; tick either
  to set it. With nothing selected the hole starts at the part's front, and
  you set Back. Back is the same plane in every operation, so a hole
  drilled to Back -15 and bored to Back -15 end together.

* **Cycle:** Peck (G83, backing out of the hole after each peck), Chip
  break (G73, backing off a little), Drill (G81, straight to depth) or
  Dwell (G82, a dwell at the bottom); **Peck depth**, **Dwell**, and the
  **Retract height** in front of the hole (the R plane).
* **Depth to the drill's tip:** off (the default), the drill's full
  diameter reaches the bottom of the selected hole, so its point goes
  deeper by the point's length; on, the point reaches it.
* **Use a canned cycle:** the cycle as G81/G82/G83/G73 (canned cycles drill
  along the active plane's axis, so the program switches to G17 for the
  cycle and back to G18 after: drilling along Z on a lathe and on a mill
  used as a lathe alike); off, the same moves written out.
* The page reports the drill, the depths and the cycle, and warns when the
  drill is not the hole's size. The drill approaches along Z on the axis
  and leaves the hole along Z before moving away from it.

## Boring (internal)
Turn Rough and Turn Profile can bore: set **Side** to **Internal** on the
operation page.

* **Min Diameter** is the hole you are boring from (e.g. the drill size):
  tick it and set it; boring from solid is not possible. **Max Diameter**
  defaults to the bore's largest diameter, so nothing beyond the bore (such
  as the part's front face) is cut; tick it to set a limit of your own.
* The bore is the model's: the part of it open to the spindle axis
  (through or blind, stepped, with tapers and radii). The operation works
  between the hole and the bore: a blind bore's bottom is faced in to the
  hole's edge, not to the axis, and Stock to leave X / Z is left on the
  bore's wall and bottom.
* The tool is an ISO turning insert used as a boring tool, so its
  reference is the mirror of the turning one: the imaginary tip at the
  cutting edge's outermost point (largest radius) and its chuck-side
  flank. Set the tool offsets to that point.
* **Radial clearance** and **Retract** (see Diameters) default
  to 0.5 mm, or a quarter of the hole's radius if less: the safe position
  is that far inside the hole wall, and each pass lifts off that much, so
  the bar stays near the wall it cuts. A larger back-off moves the bar's
  back toward the opposite wall; in a small bore, set them smaller still.
* The insert's outline is checked as for turning (see Collision checks);
  the boring bar itself (its diameter and reach) is not checked yet.

Internally the operation is the external one in a mirror: radius r maps to
R - r (R the stock's radius), which turns the bore into an outer profile
and the hole into the stock's top; the paths are mapped back, arcs
reversed.

## Collision checks
The operations place the insert's imaginary tip on the path, keep its nose
off the part, and do not follow the part where it is steeper than the
insert's cutting angle. Turn Rough, Profile and Face also check the rest of
the insert: its outline (from TipAngle, Rotation, EdgeLength and TipRadius)
is swept along the path, and where an edge or the body (not the cutting
nose) would enter the part, the Report view says where and how deep, e.g.
an insert whose leading edge is swept back past 90 degrees reaching into a
square shoulder. The path is still made, as given: change the insert or the
operation's range there.

## Diameters
As with milling's depths, Min and Max Diameter are worked out to start with
and used as given when set. Each has a checkbox: unticked, the field is
greyed out and shows what the op uses (Min: none, the op follows the part;
Max: the stock's diameter); ticked, the op uses the value, however it
compares with the part.

* **Min Diameter**, set: Rough, Profile and Turn Groove turn to it across
  the Z range, cutting into the model where it is bigger and leaving it at
  Min Diameter where it is smaller (as a milling op leaves a floor at its
  final depth). For example, select a 12 mm diameter on the Z Range page
  and set 11.85 to turn it to the major diameter of an M12x1.75 6g thread.
  Face and Partoff stop at it (e.g. the bore of a tube: Face finishes the
  face to its edge, Partoff goes just past it).
* **Max Diameter**, set: where the material starts (e.g. a surface already
  turned smaller).

The Diameters page also has the radial distances, with a diagram of them
all (the boring diagram when Side is Internal), drawn as seen standing in
front of a manual lathe: the axis at the top, radii growing toward you.

* **Retract** (Rough, Profile, Face): the radial lift-off at the end of each
  pass, beyond the furthest the tool reached.
* **Radial clearance** (all but Turn Thread): the safe position's radial
  distance from the stock (or from the hole, boring), also used for radial
  approaches.

Each is worked out unless ticked, and shown greyed: outside, Retract is
step over x finish passes and Radial clearance the Setup Sheet's safe
height offset; boring, both are 0.5 mm or a quarter of the hole's radius.
The clearance along Z (lead-ins in front of the cut) stays the Setup
Sheet's.

The arrow buttons take the diameter of the selected circular edge,
cylindrical face or vertex (a flat ring-shaped face, such as the end of a
tube, gives its inner diameter for Min and its outer for Max), and tick the
box.

## Operation settings
* **Lead-in** (Rough, Profile): how far in front of the Z range's start the
  passes begin, along Z; 0 enters them radially. Unticked it is worked out
  and shown greyed: a clearance in front; when the range starts inside the
  stock with only stock in front (e.g. a diameter selected up to the part's
  front, the stock longer), a clearance in front of the stock, cutting
  through that stock; radially when part of the model is in front.
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
  A negative value takes that much off every diameter (and face) of the
  model, like a negative offset in CAM's milling ops: for example -0.075
  turns a bar modelled at 12 mm to 11.85. To turn to a given diameter, set
  Min Diameter instead (see Diameters).
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

## Groove roughing strategies, pecking, groove turning
* **Strategy** (Turn Groove): **Plunge** roughs with full-depth plunges
  side by side; **Side-turn** plunges one **Step down**, turns along Z at
  that depth, steps down and turns back, level by level, for less tool
  pressure in wide grooves. Step down defaults to 90% of the insert's
  Turning depth (shown greyed; tick to set). Stretches too short to
  traverse (grooves under about 1.5 blade widths) are plunged.
* **Peck** (Turn Groove, Groove-Turn, Partoff): plunges feed in **Peck
  depth** at a time, backing off by **Back-off** between pecks to break the
  chip, or out of the cut with **Retract fully between pecks**.
* **Turn Groove-Turn**: groove turning (plunge turning) along the whole
  profile with a grooving or full radius insert, in both directions: Turn
  Groove with Side-turn roughing, the whole part as its range by default,
  and the finish passes down walls, across and up walls.
* The Full Radius insert has a **Neck width** (ISO BW): its width gives
  tangent flanks; less is a lollipop groove-turn insert, a full circle on a
  narrower neck, straight behind the head (only the head cuts). **Side
  relief** (α) leans tangent flanks inward from the head, as on
  tangent-relieved inserts. The tool's 3D model follows both (and so
  does a simulation that cuts with it). The turning operations see the part
  from outside (its largest radius at each Z), so neither changes paths yet;
  they will once undercut geometry is modelled.

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
* **Models.** All the Job's models are turned as one (their union), e.g. a
  shaft and a separate collar body, or two parts end to end on one bar. A
  model off the spindle axis gets a warning.
* **Z Range selection.** Selecting faces, edges or whole objects (for
  example a sketch or Draft wire drawn to mark the range) on the operation's
  Z Range page sets Start and Final Depth to the Z range they span.
  Everything in that range is turned. A selection with no length along Z,
  such as a single shoulder face or circular edge, is rejected.
  Under the selection, **Front (Z)** and **Back (Z)** show the range the op
  uses, greyed: the selection's, or without one the op's own (the stock's
  front, the part's back). Tick either end to set it by hand, whatever is
  selected (e.g. "from the selection's front, but stop at Z -15"); untick
  to go back. Turn Partoff has only Back (where it parts off); Turn Thread
  and Turn Drill have their own length and depth instead.
* **Min Diameter**, when set (see Diameters): Rough, Profile and Turn
  Groove turn to it across the Z range; no op cuts below it.
* **Max Diameter.** The outer diameter cutting starts from (default: the
  stock diameter).

The limits apply to the tool tip. At Start Depth the round nose of the insert
can reach up to one nose diameter past the limit; at Final Depth and Min
Diameter the whole nose stays inside.

## Turning tools
The turning operations need a turning tool bit. FreeCAD's tool library has no
turning shape, so the addon provides an ISO turning insert shape and an
example bit, plus the Grooving, Full Radius and Threading shapes with an
example insert each. The Full Radius shape has two: a tangent-flank insert
(Full radius 4 mm) and a lollipop groove-turn insert (Groove-turn 4 mm, a
4 mm head on a 2.8 mm neck). To add them to your CAM tool assets, switch to
the CAM workbench and run **Install Turning Tools** from the CAM menu or the
Turning toolbar. Running it again after an update brings the shapes up to
date and adds any new example bits; tool bits you already have are never
changed. Then add the example bits to a tool library, or create your own
bits from the shapes.

To install them by hand instead, copy the shapes in `Assets/Shape` (each
`.fcstd` with its `.svg`: isoshape, grooving, fullradius, threading) into the
`Tools/Shape` folder of your CAM asset directory, and import the example bits
in `Assets/Bit` from the tool library.

Set TipRadius to your insert's nose radius. Rotation must be greater than 0
and TipAngle less than 90 degrees.

## Post processor
The addon brings a **linuxcnc_lathe** post (in `Posts/`, found by CAM
through the addon's package.xml): CAM's LinuxCNC post, with what a lathe
program needs. Choose it in the Job or the machine setup.

* **G18 G8** at the start: the XZ plane and radius mode. The turning
  operations program X as a radius, and many LinuxCNC lathe
  configurations start in diameter mode (G7), so the program says so. A
  G17 in the machine's preamble becomes G18.
* **G33 and G76** accepted, and G76's **Q** (infeed angle) kept; CAM's
  LinuxCNC post drops Q from G76, which makes it infeed radially.
* **No up-and-back between operations**: each operation ends at the safe
  position and the next starts from it; consecutive rapids along Z at the
  same safe X are reduced to the first and the last (the cutting moves are
  unchanged). A tool change, spindle or coolant command between them stops
  this.

On a mill used as a lathe (e.g. PathPilot in mill mode), CAM's LinuxCNC post
is the one to use: the program is already in the XZ plane (G18) and needs no
lathe modes. Diameter-mode output (G7, X words doubled) is not offered yet.

## CAM integration
The turning operations are CAM operations, but CAM recognises operations by
the module their code is in, so an addon's are left out of the context
menu (Active toggle, dressups, Array / Copy, Inspect, Post Selected). The
addon extends CAM's check at start-up to include them. **TODO** (upstream):
CAM's `Path.Dressup.Utils.isOp()` should check the class
(`Path.Op.Base.ObjectOp`) instead; then the addon can drop this. For
turning operations the menu offers only the dressups that make sense on a
lathe path: Axis Map (which can help on a mill used as a lathe) and Path
Boundary.

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
