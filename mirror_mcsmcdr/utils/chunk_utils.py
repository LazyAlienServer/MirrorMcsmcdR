DIMENSION = {
    "overworld": "region",
    "the_nether": "DIM1",
    "the_end": "DIM-1"
}

class Region:
    
    def __init__(self, region_x: int, region_y: int, dimension_path: str):
        self.filename = f"{dimension_path}/r.{region_x}.{region_y}"
    
    def get_region_by_pos(x: int, y: int, dimension: str):
        return Region(x//16//32, y//16//32, DIMENSION[dimension])
    
    def load_region():
        pass