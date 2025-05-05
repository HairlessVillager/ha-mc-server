from migrater.base import Migrater
from .api import SeaweedfsSyncer


class TrivialMigrater(Migrater):
    def __init__(
        self,
        local_path: str,
        remote_path: str,
        filer_url: str,
    ):
        self._local_path = local_path
        self._remote_path = remote_path
        self._syncer = SeaweedfsSyncer.from_url(filer_url)

    def pull(self):
        self._syncer.remote2local(self._remote_path, self._local_path)

    def push(self):
        self._syncer.local2remote(self._local_path, self._remote_path)
