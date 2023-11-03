# remove this file
import asyncio

from ophyd_async.core import save_to_yaml
from ophyd_async.panda import PandA


async def test():
    panda = PandA("I03-PANDA")
    await panda.connect()
    save_to_yaml()
    # thing = await panda.ttlout[1].val.read()  # or set to ONE
    # await panda.ttlout[1].val.set("ONE")  # or set to ONE
    # print("hi")


asyncio.run(test())
