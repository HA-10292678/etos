#!/usr/bin/env python3

from Etos import *

sim = Simulation()
#sim.disableLog()
sim.start("""
<transaction>
    <try_catch exception="z">
        <transaction>
            <exception type="z"/>
        </transaction>
        <transaction>
            <counted_loop>
                <count>3</count>
                <transaction>
                    <trace text="exception"/>
                </transaction>
            </counted_loop>    
        </transaction>
    </try_catch>
    <trace text="exit"/>
</transaction>
""")


