# Contract

What other addons (CAM Rotary Sim) may read from CAM Lathe Turning. Renaming or changing
anything listed here is a breaking change; anything not listed may change without notice.

## Operations

Every turning operation's proxy is a `PathTurnScripts.PathTurnBase.ObjectOp`, defined in a
module under `PathTurnScripts`.

| Proxy attribute | Meaning |
|---|---|
| `uses_drill_tool` | Class attribute, True for Turn Drill (a drill on the spindle axis) |
| `is_internal(obj)` | True when the operation bores (`Side` is Internal) |
| `internal(obj)` | Turn Thread only: True for an internal thread (from `ThreadType`, or a bore selected) |

| Property | Type | Meaning |
|---|---|---|
| `Side` | Enumeration | `External` or `Internal`, on the operations that can bore |
| `ThreadType` | Enumeration | Turn Thread: `From the selection`, `External` or `Internal` |
| `MinDiameter` | Length | The inner limit; with `Internal`, the hole bored from |
| `SetMinDiameter` | Bool | `MinDiameter` set by hand (otherwise worked out) |
| `ThreadDiameter` | Length | Turn Thread: the selected diameter the thread is cut from |
| `ThreadDepth` | Length | Turn Thread: radial depth from `ThreadDiameter` to the root |
| `ThreadReport`, `DrillReport` | String | For people; the wording may change. Use the properties below |

## Structured thread data (Turn Thread)

Read-only `App::PropertyLength` properties in the `Thread dimensions` group, written on every
recompute. `.Value` is in mm. A value is 0 when the tolerance class has no data (Basic, Custom,
or a size missing from CAM's thread tables); all are 0 after a failed recompute, and on an
older document until its first recompute.

| Property | Meaning |
|---|---|
| `ThreadPitchDiaMin`, `ThreadPitchDiaMax` | The tolerance class's pitch diameter range |
| `ThreadMajorDiaMin`, `ThreadMajorDiaMax` | The class's major diameter range |
| `ThreadMinorDiaMin`, `ThreadMinorDiaMax` | The class's minor diameter range (external: the basic profile's flat root d1, not the root an insert cuts) |
| `ThreadRootDia` | The diameter the deepest pass reaches: the root (external) or the major diameter (internal) |

The ranges come from CAM's `Mod/CAM/Data/Threads` tables, converted to mm for Unified sizes.

## Tool shapes

Each shape is drawn with the insert's top (rake) face on the centre line, and the path is
programmed to its reference point.

| ShapeID | Shape | Reference point |
|---|---|---|
| `isoshape` | ISO turning insert | The imaginary tip (nose radius compensated by the path) |
| `grooving` | Grooving or parting insert | X: the cutting edge's point nearest the axis; Z: the chuck-side flank |
| `fullradius` | Full radius insert | As `grooving` |
| `threading` | Threading insert | The profile's theoretical sharp point |

Turn Drill takes CAM's own Drill shape, programmed to its tip on the axis.

## Path commands

* The XZ plane (`G18`), the spindle axis along Z. X is a radius (the post sets `G8`), never
  negative, in mm; internal operations are output in the same frame.
* Arcs are `G2`/`G3` with `I` (radial) and `K` (axial) centre offsets.
* Threading is `G33` (K the pitch) or one `G76` cycle (LinuxCNC's words); both carry the
  `allow_unsupported` annotation so CAM's posts pass them through.
* Constant surface speed wraps an operation in `G96 S<m/min> D<max rpm>` ... `G97 S<rpm>`.

## Private CAM API used

`Path.Tool.FeedsSpeeds.providers._score_preset` names the Feeds & Speeds preset a surface
speed came from (`SurfaceSpeedSource`). FreeCAD main has no public equivalent; without it the
preset's name is left out. Without `Path.Tool.FeedsSpeeds` at all, constant surface speed is
unavailable and an operation with it switched on reports why. The patches made to CAM's own
code are listed in `PathTurnScripts/cam_patches.py`.
