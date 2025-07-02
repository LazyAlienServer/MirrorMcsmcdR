from typing import Tuple
from abc import ABC, abstractmethod
from mirror_mcsmcdr.utils.sync.types import ChunkIndex, RegionIndex

class AbstractChunkPredicate(ABC):

    @abstractmethod
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def match(self, chunk_idx: ChunkIndex) -> bool:
        '''Determine whether the given chunk satisfies the specified predicate.'''
        return False
    
    @abstractmethod
    def exist(self, region_idx: RegionIndex) -> bool:
        '''Determine whether the given region includes a chunk/chunks that satisfies the specified predicate.'''
        return False

    def _region_to_corners(self, region_idx: RegionIndex) -> Tuple[int, int, int, int]:
        region_x, region_z = region_idx
        x1, x2 = region_x*32, (region_x+1)*32-1
        z1, z2 = region_z*32, (region_z+1)*32-1
        return x1, x2, z1, z2

class AddAreaChunkPredicate(AbstractChunkPredicate):

    def __init__(self, chunk_idx_1: ChunkIndex, chunk_idx_2: ChunkIndex) -> None:
        x1x2 = (chunk_idx_1[0], chunk_idx_2[0])
        z1z2 = (chunk_idx_1[1], chunk_idx_2[1])
        self.x1, self.x2, self.z1, self.z2 = min(x1x2), max(x1x2), min(z1z2), max(z1z2)
    
    def match(self, chunk_idx: ChunkIndex) -> bool:
        x, z = chunk_idx
        return self.x1 <= x <= self.x2 and self.z1 <= z <= self.z2
    
    def exist(self, region_idx: RegionIndex) -> bool:
        x1, x2, z1, z2 = self._region_to_corners(region_idx)
        return x1 <= self.x2 and z1 <= self.z2 and x2 >= self.x1 and z2 >= self.z2

class SubstractAreaChunkPredicate(AddAreaChunkPredicate):

    def match(self, chunk_idx: ChunkIndex) -> bool:
        return not super().match(chunk_idx)
    
    def exist(self, region_idx: RegionIndex) -> bool:
        x1, x2, z1, z2 = self._region_to_corners(region_idx)
        return not (self.x1 <= x1 <= x2 <= self.x2 and self.z1 <= z1 <= z2 <= self.z2)