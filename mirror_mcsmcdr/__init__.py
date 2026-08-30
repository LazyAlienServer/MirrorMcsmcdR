from mirror_mcsmcdr.mirror_manager import MultiMirrorManager

def on_load(server, prev_module):
    global manager
    manager = MultiMirrorManager(server)

def on_unload(server):
    if "manager" in globals():
        manager.on_unload(server)
