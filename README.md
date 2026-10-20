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

## Grooving and parting inserts
Grooving and parting inserts use the **Grooving** tool shape:

* **Width** (S in most catalogs), **CornerRadius** (R; half the width makes a
  full radius insert), **CuttingDepth** (La max: the deepest the blade can go
  before the holder would touch), **TurningDepth** (T: the largest sideways
  depth of cut), and **Diameter** (required by CAM; set it to the width).
* The tool is programmed to its reference point: X at the cutting edge's
  point closest to the axis, Z at the chuck-side flank. Touch it off the same
  way: X on a turned diameter, Z on a faced end with the chuck-side flank.

**Turn Groove** cuts with these inserts in both directions. It plunges
straight in to rough (at most Step Over apart along Z), leaving Finish
Allowance, then follows the profile front to back with the finish passes. It
works within the Z Range and the diameter limits like the other operations;
the blade may reach up to its width past Start Depth, never past Final Depth.
The cutting depth is measured from Max Diameter (default: the stock), which is
also where plunges start; if the surface has already been turned smaller, set
Max Diameter to that diameter.

Rough, Profile and Face need a turning insert, and Turn Groove a grooving
insert; each refuses the other kind with a message.

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
example bit, and a grooving / parting insert shape with two example inserts.
To add them to your CAM tool assets, switch to the CAM workbench and run
**Install Turning Tools** from the CAM menu. Existing files
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
