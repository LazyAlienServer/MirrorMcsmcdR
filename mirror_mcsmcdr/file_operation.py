import shutil, os, xxhash
from concurrent.futures import ThreadPoolExecutor, wait
from mirror_mcsmcdr.constants import TITLE


class WorldSync:
    

    def __init__(self, world: list, source: str, target: str, ignore_files: list, concurrency: int) -> None:
        self.world, self.source, self.target, self.ignore_files, self.concurrency = world, os.path.normpath(source), os.path.normpath(target), ignore_files, concurrency
    

    def _get_md5(self, filename):
        m = xxhash.xxh128()
        with open(filename, "rb") as file:
            data = file.read(1000000) # 1MB
            m.update(data)
            while data: # python has no "do while" !!! :-(
                data = file.read(1000000)
                m.update(data)
            file.close()
        return m.digest()
    

    def _file_compare(self, src, dst):
        return self._get_md5(src) == self._get_md5(dst)
    

    def _copyfile_task(self, filename, src_path, dst_path):
        src_file = os.path.join(src_path, filename)
        dst_file = os.path.join(dst_path, filename)
        if os.path.split(filename)[1] not in self.ignore_files and not self._file_compare(src_file, dst_file):
            shutil.copyfile(src_file, dst_file)
            return True
        else:
            return False


    def sync(self):

        changed_files_count = 0

        for single_world in self.world:

            src_path = os.path.join(self.source, single_world)
            dst_path = os.path.join(self.target, single_world)

            src_files = [os.path.join(path, file_name)[len(src_path)+1:] for path, dir_lst, file_lst in os.walk(src_path) for file_name in file_lst]
            dst_files = [os.path.join(path, file_name)[len(dst_path)+1:] for path, dir_lst, file_lst in os.walk(dst_path) for file_name in file_lst]
            
            for filename in set(dst_files) - set(src_files):
                os.remove(os.path.join(dst_path, filename))

            with ThreadPoolExecutor(max_workers=self.concurrency) as t:
                tasklist = [t.submit(lambda filename: self._copyfile_task(filename, src_path, dst_path), filename) for filename in set(src_files) & set(dst_files)]
                wait(tasklist)
                changed_files_count += sum([task.result() for task in tasklist])
        
        return changed_files_count