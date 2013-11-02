#!/usr/bin/env python3

from Etos import *
import Pause

registerModule(Pause)

sim = Simulation()
#sim.disableLog()
sim.start("""
<transaction>
    <trace text="start"/>
    <try_catch exception="z">
        <block>
            <trace text="enter try"/>
            <exception type="z"/>
        </block>
        <counted_loop restart="crash">
                <count>5</count>
                <pause><duration>0:01</duration></pause>
                <trace text="pass"/>
                <with>
                    <probability>0.5</probability>
                    <block>
                        <trace text="crash"/>
                        <exception type="crash"/>
                    </block>
                </with>
                <trace text="outer post-exception"/>
        </counted_loop>
    </try_catch>
    <trace text="exit"/>
</transaction>
""")


