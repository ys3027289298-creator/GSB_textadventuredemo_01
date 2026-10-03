#! python3
"""Run textadventuredemo.py and every snippet in order, and verify them.

Usage: python3 run_all_snippets.py

The exit status is 0 only if every program passes. Any exception, traceback,
unexpected output, or invalid game state makes this script exit non-zero.

How each program's global state is cleaned up
---------------------------------------------
Every program keeps its game state in module-level global variables:
``location``, ``inventory``, ``showFullExits``, and the ``GROUND`` lists
inside ``worldRooms`` (which the take/drop commands mutate). This script runs
each program in a fresh Python subprocess, so those globals are created on
startup and discarded when the process exits. No snippet can leave leftover
items in a room, a moved player, or toggled flags behind for the next one,
and module-level setup (printing the banner, building the world) cannot be
re-triggered inside an already-running process. Each scenario is also run
twice and the two runs must produce byte-identical output, which proves that
no stale state leaks between runs and that the programs are deterministic.

Per-program notes:
- snippets/datastructures.py only defines the world data and has no game
  loop, so there is no runtime state to clean up. It is validated by
  importing it in a subprocess and checking the world data for consistency.
- snippets/movement.py uses a raw input() loop instead of cmd.Cmd; its state
  is the same module-level globals, cleaned up by process exit.
- All other programs (basiccmdloop.py, cmdmovement.py, takedrop.py,
  takedrop_complete.py, look.py, shops.py, textadventuredemo.py) use the
  cmd.Cmd loop and the same module-level globals, cleaned up by process exit.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

TIMEOUT = 30  # seconds per program run

# Python code run in a subprocess to validate the world data in
# snippets/datastructures.py. Exits non-zero if any invariant is violated.
WORLD_CHECK = r'''
import importlib.util
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('datastructures', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

errors = []
directions = (module.NORTH, module.SOUTH, module.EAST, module.WEST, module.UP, module.DOWN)
for roomName, room in module.worldRooms.items():
    if module.DESC not in room:
        errors.append('room %r has no DESC' % roomName)
    for direction in directions:
        if direction in room and room[direction] not in module.worldRooms:
            errors.append('room %r exit %s points at unknown room %r' % (roomName, direction, room[direction]))
    for item in room.get(module.GROUND, []) + room.get(module.SHOP, []):
        if item not in module.worldItems:
            errors.append('room %r references unknown item %r' % (roomName, item))
for itemName, item in module.worldItems.items():
    for key in (module.GROUNDDESC, module.SHORTDESC, module.LONGDESC):
        if key not in item:
            errors.append('item %r has no %s' % (itemName, key))
    if not item.get(module.DESCWORDS):
        errors.append('item %r has no DESCWORDS' % itemName)

if errors:
    print('\n'.join(errors))
    sys.exit(1)
print('world data OK')
'''

# Each scenario feeds a scripted session to one program and checks the
# combined stdout/stderr:
#   expect: substrings that must appear
#   counts: substrings that must appear an exact number of times
#   forbid: substrings that must not appear
SCENARIOS = [
    {
        'name': 'snippets/datastructures.py',
        'world_check': True,
    },
    {
        'name': 'snippets/basiccmdloop.py',
        'stdin': '\njump\n\nquit\n',
        'expect': ['Text Adventure Demo!', 'Thanks for playing!'],
        'counts': {'I do not understand that command. Type "help" for a list of commands.': 1},
    },
    {
        'name': 'snippets/movement.py',
        'stdin': 'north\n  South \nfoo\n\nquit\n',
        'expect': ['North Y Street', 'Town Square'],
        'counts': {'You move to the': 2},
    },
    {
        'name': 'snippets/cmdmovement.py',
        'stdin': '\nnorth\n\n  NORTH\nsouth\nquit\n',
        'expect': ['North Y Street'],
        'counts': {
            'You cannot move in that direction': 1,
            'You move to the north': 1,
            'You move to the south': 1,
            'I do not understand that command. Type "help" for a list of commands.': 0,
        },
    },
    {
        'name': 'snippets/takedrop.py',
        'stdin': 'north\ntake sign\ntake sign\ndrop\ndrop sign\ndrop xyz\nTAKE SIGN\nsouth\nquit\n',
        'expect': ['You do not have "xyz" in your inventory.'],
        'counts': {
            'You take a sign.': 2,
            'You drop a sign.': 1,
            'That is not on the ground.': 1,
            'Drop what?': 1,
        },
    },
    {
        'name': 'snippets/takedrop_complete.py',
        'stdin': 'north\ntake sign\ntake sign\ndrop\ndrop sign\ndrop xyz\nTAKE SIGN\nsouth\nquit\n',
        'expect': ['You do not have "xyz" in your inventory.'],
        'counts': {
            'You take a sign.': 2,
            'You drop a sign.': 1,
            'That is not on the ground.': 1,
            'Drop what?': 1,
        },
    },
    {
        'name': 'snippets/look.py',
        'stdin': 'look\nlook sign\n\nlook fountain\nlook xyz\nlook north\nlook exits\ntake sign\nnorth\ntake sign\nLOOK SIGN\nsouth\nquit\n',
        'expect': [
            'The welcome sign reads',
            'bright green',
            'You do not see that nearby.',
            'Do Not Take This Sign',
        ],
        'counts': {
            'The welcome sign reads': 1,
            'bright green': 1,
            'You cannot take "sign".': 1,
            'You take a sign.': 1,
            'I do not understand that command. Type "help" for a list of commands.': 0,
        },
    },
    {
        'name': 'snippets/shops.py',
        'stdin': 'inventory\nlist\nbuy pie\nnorth\neast\nlist\nbuy pie\ninventory\nsell pie\nsell pie\nbuy\nsell\nbuy anvil\nwest\nsouth\nquit\n',
        'expect': [
            'Meat Pie',
            'Buy what?',
            'Sell what?',
            '"anvil" is not sold here',
            'You do not have "pie". Type "inventory" or "inv" to see your inventory.',
        ],
        'counts': {
            'This is not a shop.': 2,
            'You have purchased a meat pie': 1,
            'You have sold a meat pie': 1,
        },
    },
    {
        'name': 'textadventuredemo.py',
        'stdin': '\ninventory\neat donut\neat sword\neat\nlook sign\ntake sign\ndrop\ndrop xyz\nnorth\neast\nbuy bagel\neat bagel\nexits\nexits\nwest\nsouth\nquit\n',
        'expect': [
            'The welcome sign reads',
            'You cannot take "sign".',
            'Drop what? Type "inventory" or "inv" to see your inventory.',
            'You do not have "xyz" in your inventory.',
            'You have purchased a bagel',
            'Eat what? Type "inventory" or "inv" to see your inventory.',
        ],
        'counts': {
            'You eat a donut': 1,
            'You cannot eat that.': 1,
            'You eat a bagel': 1,
            'Showing brief exit descriptions.': 1,
            'Showing full exit descriptions.': 1,
        },
    },
]

FORBIDDEN = ['Traceback (most recent call last)']


def run_program(path, stdin_text, seed='0'):
    """Run one program in a fresh subprocess; return (returncode, output)."""
    try:
        proc = subprocess.run(
            [sys.executable, path],
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=ROOT,
            env=dict(os.environ, PYTHONHASHSEED=seed),
        )
    except subprocess.TimeoutExpired:
        return None, 'TIMEOUT after %s seconds' % TIMEOUT
    return proc.returncode, proc.stdout + proc.stderr


def check_scenario(scenario):
    """Run one scenario twice and return a list of failure messages."""
    failures = []
    path = os.path.join(ROOT, scenario['name'])

    if scenario.get('world_check'):
        returncode, output = run_program(path, '')
        if returncode != 0:
            failures.append('exited with status %s\n%s' % (returncode, output))
        proc = subprocess.run(
            [sys.executable, '-c', WORLD_CHECK, path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=ROOT,
        )
        if proc.returncode != 0:
            failures.append('world data is invalid:\n%s%s' % (proc.stdout, proc.stderr))
        return failures

    outputs = []
    for run, seed in ((1, '1'), (2, '2')):
        returncode, output = run_program(path, scenario['stdin'], seed)
        if returncode is None:
            failures.append(output)
            return failures
        if returncode != 0:
            failures.append('run %s exited with status %s' % (run, returncode))
        outputs.append(output)

    if outputs[0] != outputs[1]:
        failures.append('two identical runs produced different output (stale global state?)')

    output = outputs[0]
    for text in FORBIDDEN + list(scenario.get('forbid', [])):
        if text in output:
            failures.append('output contains forbidden text: %r' % text)
    for text in scenario.get('expect', []):
        if text not in output:
            failures.append('output is missing expected text: %r' % text)
    for text, count in scenario.get('counts', {}).items():
        actual = output.count(text)
        if actual != count:
            failures.append('output contains %r %s times, expected %s' % (text, actual, count))
    return failures


def main():
    all_ok = True
    for scenario in SCENARIOS:
        failures = check_scenario(scenario)
        if failures:
            all_ok = False
            print('FAIL %s' % scenario['name'])
            for failure in failures:
                print('     %s' % failure)
        else:
            print('ok   %s' % scenario['name'])

    if not all_ok:
        print('\nSome programs failed.')
        return 1
    print('\nAll %s programs passed.' % len(SCENARIOS))
    return 0


if __name__ == '__main__':
    sys.exit(main())
