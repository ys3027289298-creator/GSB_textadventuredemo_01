textadventuredemo
=================

Text Adventure Demo

This is a simple text adventure game that demonstrates Python's cmd and textwrap modules.

The step-by-step tutorial for this program is at http://inventwithpython.com/blog/2014/12/11/making-a-text-adventure-game-with-the-cmd-and-textwrap-python-modules/

Running all the snippets
========================

Run `python3 run_all_snippets.py` to execute `textadventuredemo.py` and every
snippet in `snippets/` in order. The script feeds each program a scripted
session (covering empty commands, mixed case and extra whitespace, unknown
items, and rooms with duplicate item names) and exits non-zero if any program
raises an exception, prints a traceback, or produces output that shows an
invalid game state.

How each snippet cleans up its global state
-------------------------------------------

Every program keeps its game state in module-level globals (`location`,
`inventory`, `showFullExits`, and the `GROUND` lists inside `worldRooms`,
which the take/drop commands mutate). The runner executes each program in a
fresh Python subprocess, so those globals are created on startup and
discarded when the process exits: no snippet can leave leftover items in a
room, a moved player, or toggled flags behind for the next one, and
module-level setup cannot be re-triggered inside an already-running process.
Each scenario is run twice (with different hash seeds) and must produce
identical output, proving no stale state leaks between runs.

- `snippets/datastructures.py` only defines the world data and has no game
  loop, so there is no runtime state to clean up. The runner imports it in a
  subprocess and validates the world data (exits point at real rooms, ground
  and shop items exist, every item has descriptions and descwords).
- `snippets/movement.py` uses a raw `input()` loop instead of `cmd.Cmd`; its
  state is the same module-level globals, cleaned up by process exit.
- All other programs (`basiccmdloop.py`, `cmdmovement.py`, `takedrop.py`,
  `takedrop_complete.py`, `look.py`, `shops.py`, `textadventuredemo.py`) use
  the `cmd.Cmd` loop and the same module-level globals, cleaned up by process
  exit.
