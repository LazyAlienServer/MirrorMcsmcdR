from mirror_mcsmcdr.mirror_manager import MultiMirrorManager

def on_load(server, prev_module):
    manager = MultiMirrorManager(server)