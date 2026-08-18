from typing import Tuple, List
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
    
    @abstractmethod
    def include(self, region_idx: RegionIndex) -> bool:
        '''Determine whether the given region is totally included by the specified predicate, which means that all the chunks satisfy the specified predicate.'''
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
    
    def include(self, region_idx: RegionIndex) -> bool:
        x1, x2, z1, z2 = self._region_to_corners(region_idx)
        return x1 <= self.x1 and z1 <= self.z1 and x2 >= self.x2 and z2 >= self.z2

class SubstractAreaChunkPredicate(AddAreaChunkPredicate):

    def match(self, chunk_idx: ChunkIndex) -> bool:
        return not super().match(chunk_idx)

    def exist(self, region_idx: RegionIndex) -> bool:
        x1, x2, z1, z2 = self._region_to_corners(region_idx)
        return not (self.x1 <= x1 <= x2 <= self.x2 and self.z1 <= z1 <= z2 <= self.z2)

    def include(self, region_idx: RegionIndex) -> bool:
        return not super().exist(region_idx)

class AddDistanceChunkPredicate(AbstractChunkPredicate):

    def __init__(self, chunk_idx: ChunkIndex, distance: int) -> None:
        self.x, self.z = chunk_idx
        self.distance = distance
    
    def match(self, chunk_idx: ChunkIndex) -> bool:
        x, z = chunk_idx
        return (x - self.x)**2 + (z - self.z)**2 <= self.distance**2

    def exist(self, region_idx: RegionIndex) -> bool:
        x1, x2, z1, z2 = self._region_to_corners(region_idx)
        x, z, distance = self.x, self.z, self.distance
        if (x1-distance <= x <= x2+distance and z1 <= z <= z2) or (x1 <= x <= x2 and z1-distance <= z <= z2+distance):
            return True
        elif x < x1:
            if z < z1:
                return self.match((x1, z1))
            else:
                return self.match((x1, z2))
        else:
            if z < z1:
                return self.match((x2, z1))
            else:
                return self.match((x2, z2))

    def include(self, region_idx: RegionIndex) -> bool:
        x1, x2, z1, z2 = self._region_to_corners(region_idx)
        x, z, distance = self.x, self.z, self.distance
        return x1 <= x - distance and x2 >= x + distance and z1 <= z - distance and z2 >= z + distance

class SubstractDistanceChunkPredicate(AddDistanceChunkPredicate):

    def match(self, chunk_idx: ChunkIndex) -> bool:
        return not super().match(chunk_idx)

    def exist(self, region_idx: RegionIndex) -> bool:
        x1, x2, z1, z2 = self._region_to_corners(region_idx)
        return self.match((x1, z1)) or self.match((x1, z2)) or self.match((x2, z1)) or self.match((x2, z2))

    def include(self, region_idx: RegionIndex) -> bool:
        return not super().exist(region_idx)

class ComplexChunkPredicate(AbstractChunkPredicate):

    def __init__(self, predicates: List[AbstractChunkPredicate]) -> None:
        self.predicates = predicates

    def match(self, chunk_idx: ChunkIndex) -> bool:
        return sum([predicate.match(chunk_idx) for predicate in self.predicates]) == len(self.predicates)

    def exist(self, region_idx: RegionIndex) -> bool:
        start_chunk_x, end_chunk_x, start_chunk_z, end_chunk_z = region_idx[0]*32, (region_idx[0]+1)*32, region_idx[1]*32, (region_idx[1]+1)*32
        for z in range(start_chunk_z, end_chunk_z):
            for x in range(start_chunk_x, end_chunk_x):
                if self.match((x, z)):
                    return True
        return False

    def include(self, region_idx: RegionIndex) -> bool:
        return sum([predicate.include(region_idx) for predicate in self.predicates]) == len(self.predicates)