# remove this file
import asyncio

from bluesky import RunEngine
from ophyd_async.core import save_to_yaml
from ophyd_async.panda import PandA

from hyperion.utils.panda_utils import load_panda, save_panda


async def test():
    panda = PandA("I03-PANDA")
    await panda.connect()
    RE = RunEngine()
    RE(load_panda(panda))


asyncio.run(test())
