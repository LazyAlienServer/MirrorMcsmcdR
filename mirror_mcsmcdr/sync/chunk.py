import os
from typing import List, Union

DIMENSION = {
    "overworld": "region",
    "the_nether": "DIM1",
    "the_end": "DIM-1"
}

class Region:
    
    def __init__(self, region_x: int, region_y: int, dimension_path: str, world_path: str):
        self.file = os.path.join(world_path, f"{dimension_path}/r.{region_x}.{region_y}.mca")
        with open(self.file, "rb") as file:
            pre4ksector = file.read(4096)
        self.pre4ksector = [(pre4ksector[index:index+3], pre4ksector[index+3]) for index in range(0, 4096, 4)]
        self.pre4ksector_changed = False
        self.region_changed = False
        self.init_chunks()
    
    def init_chunks(self):
        self.chunks: List[Union[bytes, None]] = [None]*1024
    
    def get_chunk(self, chunk_x, chunk_z) -> bytes:
        chunk = self.chunks[index := chunk_z*32 + chunk_x]
        if chunk:
            return chunk
        starter, size = self.pre4ksector[chunk_z*32 + chunk_x]
        with open(self.file, "rb") as file:
            file.seek(int.from_bytes(starter)*4096)
            chunk = file.read(size*4096)
        self.chunks[index] = chunk
        return chunk
    
    def replace_chunk(self, chunk_x: int, chunk_z: int, content: bytes):
        if not len(content)%4096 == 0:
            raise AttributeError(f"Wrong chunk content format with length `{len(content)}`.")
        new_size = len(content)//4096
        starter, size = self.pre4ksector[index := chunk_z*32 + chunk_x]
        self.chunks[index] = content
        self.region_changed = True
        if new_size == size:
            return
        size_change = new_size - size
        self.pre4ksector = [i if i[0] <= starter else ((int.from_bytes(i[0]) + size_change).to_bytes(3), i[1]) for i in self.pre4ksector]
        self.pre4ksector_changed = True
    
    def save(self):
        if not self.region_changed:
            return
        with open(self.file, "rb") as file, open(self.file+".temp", "wb+") as temp:
            if self.pre4ksector_changed:
                file.seek(4096)
                pre4ksector = bytes()
                for i in self.pre4ksector:
                    pre4ksector += i[0] + i[1].to_bytes()
                temp.write(pre4ksector)
            else:
                temp.write(file.read(4096))
            temp.write(file.read(4096))
            chunks = {int.from_bytes(self.pre4ksector[index][0]):(self.pre4ksector[index][1], chunk) for index, chunk in enumerate(self.chunks) if chunk}
            current_starter = 2
            while True:
                if current_starter not in chunks.keys():
                    buffer = file.read(4096)
                    if not buffer:
                        break
                    temp.write(buffer)
                    current_starter += 1
                    continue
                size, chunk_content = chunks[current_starter]
                file.seek(size*4096, 1)
                temp.write(chunk_content)
                current_starter += size
                
        os.remove(self.file)
        os.rename(self.file+".temp", self.file)

class World:

    def __init__(self, world_path: str) -> None:
        self.loaded_region = {}
        self.world_path = world_path
    
    def get_region(self, region_x: int, region_z: int, dimension: str) -> Region:
        if (key := (region_x, region_z, dimension)) not in self.loaded_region.keys():
            region = Region(region_x, region_z, DIMENSION[dimension], self.world_path)
            self.loaded_region[key] = region
        else:
            region = self.loaded_region[key]
        return region

    def get_region_by_pos(self, x: int, z: int, dimension: str) -> Region:
        return self.get_region(x//16//32, z//16//32, dimension)
    
    def get_chunk_by_index(self, chunk_x: int, chunk_z: int, dimension: str) -> bytes:
        return self.get_region(chunk_x // 32, chunk_z // 32, dimension).get_chunk(chunk_x % 32, chunk_z % 32)
    
    def get_chunk_by_pos(self, x: int, y: int, dimension: str) -> bytes:
        return self.get_region_by_pos(x, y, dimension).get_chunk(x//16%32, y//16%32)
    
    def replace_chunk_by_pos(self, x: int, y: int, dimension: str, content: bytes):
        self.get_region_by_pos(x, y, dimension).replace_chunk(x//16%32, y//16%32, content)
    
    def clear_all(self):
        self.loaded_region.clear()
    
    def save_all(self):
        for region in self.loaded_region.values():
            region.save()
        self.clear_all()