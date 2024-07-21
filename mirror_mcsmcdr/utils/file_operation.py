import shutil, os, xxhash
from concurrent.futures import ThreadPoolExecutor, wait


class WorldSync:
    

    def __init__(self, world: list, source: str, target: str, ignore_inexistent_target_path: bool, concurrency: int, ignore_files: list) -> None:
        self.world, self.source, self.target = world, os.path.normpath(source), target
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


    def sync(self):

        changed_files_count = 0
        paths_notfound = []

        target_paths = [self.target] if type(self.target) == str else self.target

        for target_path in target_paths:
            target_path = os.path.normpath(target_path)

            if not os.path.exists(target_path):
                if not self.ignore_inexistent_target_path:
                    paths_notfound.append(target_path)
                else:
                    os.makedirs(target_path)

            for single_world in self.world:

                src_path = os.path.join(self.source, single_world)
                dst_path = os.path.join(target_path, single_world)

                src_files = [os.path.join(path, file_name)[len(src_path)+1:] for path, dir_lst, file_lst in os.walk(src_path) for file_name in file_lst]
                dst_files = [os.path.join(path, file_name)[len(dst_path)+1:] for path, dir_lst, file_lst in os.walk(dst_path) for file_name in file_lst]
                
                for filename in set(dst_files) - set(src_files):
                    os.remove(os.path.join(dst_path, filename))
                
                self.copy_tree(src_path, dst_path)

                with ThreadPoolExecutor(max_workers=self.concurrency) as t:
                    tasklist = [t.submit(lambda filename: self._copyfile_task(filename, src_path, dst_path), filename) for filename in src_files]
                    wait(tasklist)
                    changed_files_count += sum([task.result() for task in tasklist])
        
        return changed_files_count, paths_notfound