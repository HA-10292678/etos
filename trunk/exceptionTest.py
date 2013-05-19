#!/usr/bin/env python3

from Etos import *
import Pause

registerModule(Pause)

sim = Simulation()
#sim.disableLog()
sim.start("""
<transaction>
    <try_catch exception="z">
        <exception type="z"/>
        <counted_loop restart="crash">
                <count>5</count>
                <pause><duration>0:01</duration></pause>
                <trace text="pass"/>
                <with>
                        <probability>0.5</probability>
                        <exception type="crash"/>
                </with>
                <trace text="post-exception"/>
        </counted_loop>
    </try_catch>
    <trace text="exit"/>
</transaction>
""")


