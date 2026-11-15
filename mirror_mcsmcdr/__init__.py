from typing import Optional

from mirror_mcsmcdr.manager import MultiMirrorManager

# not named "manager": that is the submodule, which the import above already binds in this namespace
_mirrors: Optional[MultiMirrorManager] = None


def on_load(server, prev_module):
    global _mirrors
    _mirrors = MultiMirrorManager(server)


def on_unload(server):
    if _mirrors is not None:
        _mirrors.on_unload()
