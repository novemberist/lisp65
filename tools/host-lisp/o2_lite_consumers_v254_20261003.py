"""2.5.4 O2-lite consumer pin for live successors.

The immutable o2_lite_consumers_20260929 pins six Comfort-plane sources.  The
2.5.4 package card moves exactly three of them on purpose:

  lib/repl-comfort-v250.lisp   RP1: %lt-fit / %lt-write result guard in %repl-loop
  lib/lite-hot.lisp            HIST1: LF ends a comment in the recalled-form scan
  config/comfort-default-plane/libraries/repl-comfort-suite.json
                               functions += %lt-fit, %lt-write

install() verifies that the predecessor pin is exactly the sealed 2.5.3 world
(all six sources), that exactly these three moved, and then re-pins the
module's SOURCES so that its controls(), mutation controls, dated suite
declarations and finish() bindings run unchanged against the live 2.5.4
sources.  Consumers that witness historical artifacts do not use this pin;
they replay in the 2.5.3 era (era_replay_v254_20261003).
"""
import evidence_era as E
import o2_lite_consumers_20260929 as O
import c2_v254_r1_common as C

PREDECESSOR = dict(O.SOURCES)
MOVED = {'lib/repl-comfort-v250.lisp': '053fb998c2bdaa3051162def72eee5fe5183dfaf5a0d88459312d007efc691de',
         'lib/lite-hot.lisp': 'fe689dadc3071ab5f3617615b59bd2d0c5126e04aa7b4532d52d6b1f0fae3ba3',
         'config/comfort-default-plane/libraries/repl-comfort-suite.json':
             'c5e7a54832692b7595eb91fd1498c8fe22ce26f087f49a0f275f7d0009d67353'}
SOURCES = {**PREDECESSOR, **MOVED}


def controls():
    for path, digest in PREDECESSOR.items():
        C.require(E.era_bind(C.ERA_V253, path)['sha256'] == digest, 'O2-lite predecessor pin is not the 2.5.3 era: ' + path)
    C.require(set(MOVED) <= set(PREDECESSOR) and all(PREDECESSOR[p] != MOVED[p] for p in MOVED),
              'O2-lite v254 pin does not move exactly the three package sources')
    C.require({p for p in SOURCES if SOURCES[p] != PREDECESSOR[p]} == set(MOVED), 'O2-lite v254 pin population drift')


def install():
    controls()
    O.SOURCES = SOURCES
    O.controls()
    return O


CHILD = 'tools/host-lisp/o2_lite_consumers_20260929.py'
CHILD_V254 = 'tools/host-lisp/o2_lite_consumers_v254_20261003.py'


def route_children():
    """Child suite runs that O.suites() routes to the O2-lite main use this pin.

    o2_lite_consumers_20260929.suites() rewrites child bytecode_p0_stdlib.py
    commands to the O2-lite module's own main, which re-checks the immutable
    pin in a fresh process.  Those children run this module's main instead:
    the same suite routing and P.main(), controlled by the v254 pin.
    """
    import subprocess
    run = subprocess.run
    if getattr(run, 'o2_lite_v254', False):
        return
    def child(command, *args, **kwargs):
        command = list(command)
        if len(command) > 1 and command[1] == CHILD:
            command[1] = CHILD_V254
        return run(command, *args, **kwargs)
    child.o2_lite_v254 = True
    subprocess.run = child


if __name__ == '__main__':
    import bytecode_p0_stdlib as P
    route_children()
    install()
    with O.suites():
        raise SystemExit(P.main())
