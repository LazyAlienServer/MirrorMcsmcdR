import shutil, os, xxhash
from concurrent.futures import ThreadPoolExecutor, wait


class ClassicWorldSynchronizer:
    

    def __init__(self, world: list, ignore_inexistent_target_path: bool, concurrency: int, ignore_files: list) -> None:
        self.world = world
        self.ignore_inexistent_target_path = ignore_inexistent_target_path
        self.concurrency = concurrency
        self.ignore_files = ignore_files
    

    def _get_md5(self, filename):
        m = xxhash.xxh128()
        with open(filename, "rb") as file:
            data = file.read(1000000) # 1MB
            m.update(data)
            while data: # python doesn't have "do while" !!!  :-(
                data = file.read(1000000)
                m.update(data)
            file.close()
        return m.digest()


    def _copyfile_task(self, filename, src_path, dst_path) -> bool:
        src_file = os.path.join(src_path, filename)
        dst_file = os.path.join(dst_path, filename)
        if os.path.basename(filename) not in self.ignore_files and (not os.path.exists(dst_file) or not self._get_md5(src_file) == self._get_md5(dst_file)):
            shutil.copyfile(src_file, dst_file)
            return True
        return False
    

    def copy_tree(self, src, dst):
        for src_path, dst_path in ((os.path.join(src, path), os.path.join(dst, path)) for path in os.listdir(src)):
            if os.path.isdir(src_path):
                if not os.path.exists(dst_path):
                    os.makedirs(dst_path)
                self.copy_tree(src_path, dst_path)


    def overlapping(self, source: str, target_paths: list[str]) -> list[tuple[str, str]]:
        """
        The pairs of a source world and a target world that are one directory, or one inside the other:
        syncing them would delete or overwrite the very files it copies from.
        """
        sources = [os.path.join(source, world) for world in self.world]
        targets = [os.path.join(target, world) for target in target_paths for world in self.world]
        return [(source_world, target_world) for source_world in sources for target_world in targets if _overlap(source_world, target_world)]

    def sync(self, source: str, target_paths: list[str]):
        source = os.path.normpath(source)

        changed_files_count = 0
        paths_notfound = []

        for target_path in target_paths:
            target_path = os.path.normpath(target_path)

            if not os.path.exists(target_path):
                if not self.ignore_inexistent_target_path:
                    paths_notfound.append(target_path)
                    continue
                os.makedirs(target_path)

            for single_world in self.world:

                src_path = os.path.join(source, single_world)
                dst_path = os.path.join(target_path, single_world)

                src_files = [os.path.join(path, file_name)[len(src_path)+1:] for path, dir_lst, file_lst in os.walk(src_path) for file_name in file_lst]
                dst_files = [os.path.join(path, file_name)[len(dst_path)+1:] for path, dir_lst, file_lst in os.walk(dst_path) for file_name in file_lst]
                
                for filename in set(dst_files) - set(src_files):
                    os.remove(os.path.join(dst_path, filename))
                
                # a target that never held this world has no directory for it yet
                os.makedirs(dst_path, exist_ok=True)
                self.copy_tree(src_path, dst_path)

                with ThreadPoolExecutor(max_workers=self.concurrency) as t:
                    tasklist = [t.submit(lambda filename: self._copyfile_task(filename, src_path, dst_path), filename) for filename in src_files]
                    wait(tasklist)
                    changed_files_count += sum([task.result() for task in tasklist])
        
        return changed_files_count, paths_notfound


def _overlap(a: str, b: str) -> bool:
    a, b = (os.path.normcase(os.path.realpath(path)) for path in (a, b))
    try:
        return os.path.commonpath([a, b]) in (a, b)
    except ValueError:
        # on different drives
        return False