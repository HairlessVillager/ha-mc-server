from pathlib import PurePath
import os
import shutil

import requests
from loguru import logger


class SeaweedfsClientError(Exception):
    pass


class NotFound(SeaweedfsClientError):
    pass


class SeaweedfsClient:
    def __init__(self, base_url: str):
        self._base_url = base_url

        # Test base_url
        self.list("/")

        logger.info(f"SeaweedfsClient initialized with base URL: {base_url}")

    def _build_url(self, remote_path: str):
        return self._base_url + remote_path

    def _raise_error_from_response(self, response: requests.Response):
        if response.content:
            j = response.json()
            if "error" in j:
                msg = j['error']
                logger.error(f"Error in response: {msg}")
                raise SeaweedfsClientError(msg)

    def upload(
        self,
        local_path: str,
        remote_path: str,
        *,
        append: bool = False,
        use_put: bool = False,
    ):
        logger.info(
            f"Uploading file from '{local_path}' to remote path '{remote_path}'"
        )
        url = self._build_url(remote_path)
        params = {}
        if append:
            params["op"] = "append"

        with open(local_path, "rb") as f:
            files = {"file": f}
            if use_put:
                response = requests.put(url, data=f, params=params)
            else:
                response = requests.post(url, files=files, params=params)
        logger.debug(f"Upload response: {response.json()}")
        return response.json()

    def delete(
        self,
        remote_path: str,
        *,
        recursive: bool = False,
    ):
        logger.info(f"Deleting remote path '{remote_path}' (recursive={recursive})")
        params = {
            "recursive": "true" if recursive else "false",
        }
        url = self._build_url(remote_path)
        response = requests.delete(url, params=params)
        self._raise_error_from_response(response)

    def download(
        self,
        remote_path: str,
        local_path: str,
    ):
        logger.info(
            f"Downloading file from remote path '{remote_path}' to '{local_path}'"
        )
        url = self._build_url(remote_path)
        response = requests.get(url)
        with open(local_path, "wb") as f:
            f.write(response.content)

    def move(
        self,
        src_path: str,
        dst_path: str,
    ):
        logger.info(f"Moving remote path '{src_path}' to '{dst_path}'")
        url = self._build_url(dst_path)
        params = {
            "mv.from": src_path,
        }
        response = requests.post(url, params=params)
        self._raise_error_from_response(response)

    def list(
        self,
        remote_path: str,
    ):
        logger.info(f"Listing remote path '{remote_path}'")
        url = self._build_url(remote_path)
        headers = {
            "Accept": "application/json",
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            logger.warning(f"Remote path '{remote_path}' not found")
            raise NotFound()
        elif response.headers["Content-Type"] == "application/json":
            logger.debug(f"List response: {response.json()}")
            return response.json()
        elif "text/plain" in response.headers["Content-Type"]:
            parent_path = str(PurePath(remote_path).parent)
            logger.debug(
                f"Received text/plain response, retrying with parent path '{parent_path}'"
            )
            return self.list(parent_path)
        else:
            logger.error(f"Unknown response headers: {response.headers}")
            logger.error(f"Unknown response content: {response.content}")
            raise Exception("Unknown error")

    def exists(
        self,
        remote_path: str,
    ):
        logger.info(f"Checking if remote path '{remote_path}' exists")
        is_exists = True
        try:
            self.list(remote_path)
        except NotFound:
            logger.debug(f"Remote path '{remote_path}' does not exist")
            is_exists = False
        return is_exists

    def metadata(
        self,
        remote_path: str,
    ):
        logger.info(f"Fetching metadata for remote path '{remote_path}'")
        url = self._build_url(remote_path)
        params = {
            "metadata": "true",
        }
        response = requests.get(url, params=params)
        logger.debug(f"Metadata response: {response.json()}")
        return response.json()


class _SeaweedfsSyncerL2R:
    def __init__(self, client: SeaweedfsClient):
        self._client = client
        logger.info("SeaweedfsSyncerL2R initialized with client")

    def sync(self, local_path: str, remote_path: str):
        logger.info(
            f"Starting sync from local path '{local_path}' to remote path '{remote_path}'"
        )
        self._backup(remote_path)
        try:
            for local_file_path in self._get_local_files(local_path):
                local_file_relpath = os.path.relpath(local_file_path, local_path)
                remote_file_path = os.path.join(remote_path, local_file_relpath)
                logger.debug(
                    f"Uploading local file '{local_file_path}' to remote path '{remote_file_path}'"
                )
                self._client.upload(
                    local_path=local_file_path, remote_path=remote_file_path
                )
            backup_path = self._build_backup_path(remote_path)
            self._client.delete(backup_path, recursive=True)
            logger.info("Sync completed successfully")
        except Exception as e:
            logger.error(f"Sync failed with exception: {e}")
            self._restore(remote_path)
            raise

    def _build_backup_path(self, origin_path: str):
        backup_path = origin_path + ".backup"
        logger.debug(f"Backup path constructed: {backup_path}")
        return backup_path

    def _backup(self, remote_path: str):
        origin_path = remote_path
        backup_path = self._build_backup_path(origin_path)
        logger.info(f"Backing up remote path '{origin_path}' to '{backup_path}'")
        if self._client.exists(origin_path):
            if self._client.exists(backup_path):
                logger.error(f"Backup directory already exists at '{backup_path}'")
                raise Exception("A backup dir exists")
            else:
                self._client.move(origin_path, backup_path)
                logger.info("Backup created successfully")
        else:
            logger.warning(
                f"Remote path '{origin_path}' does not exist, no backup needed"
            )

    def _restore(self, remote_path: str):
        origin_path = remote_path
        backup_path = self._build_backup_path(origin_path)
        logger.info(
            f"Restoring remote path '{origin_path}' from backup '{backup_path}'"
        )
        if self._client.exists(backup_path):
            self._client.move(backup_path, origin_path)
            logger.info("Restore completed successfully")
        else:
            logger.error(f"No backup directory found at '{backup_path}'")
            raise Exception("No backup dir exists")

    def _get_local_files(self, local_path: str):
        logger.info(f"Fetching local files from path '{local_path}'")
        for root, dirs, files in os.walk(local_path):
            for file in files:
                file_path = os.path.join(root, file)
                logger.debug(f"Found local file: {file_path}")
                yield file_path


class _SeaweedfsSyncerR2L:
    def __init__(self, client: SeaweedfsClient):
        self._client = client
        logger.info("SeaweedfsSyncerR2L initialized with client")

    def sync(self, remote_path: str, local_path: str):
        logger.info(
            f"Starting sync from remote path '{remote_path}' to local path '{local_path}'"
        )
        self._backup_local(local_path)
        try:
            os.makedirs(local_path, exist_ok=True)
            logger.info(f"Created local directory '{local_path}'")
            for remote_file in self._get_remote_files(remote_path):
                remote_rel = PurePath(remote_file).relative_to(remote_path)
                local_file = PurePath(local_path) / remote_rel
                local_dir = local_file.parent
                os.makedirs(str(local_dir), exist_ok=True)
                logger.debug(
                    f"Downloading remote file '{remote_file}' to local file '{local_file}'"
                )
                self._client.download(remote_file, str(local_file))
            self._delete_local_backup(local_path)
            logger.info("Sync completed successfully")
        except Exception as e:
            logger.error(f"Sync failed with exception: {e}")
            self._restore_local(local_path)
            raise

    def _get_remote_files(self, remote_path: str):
        logger.info(f"Fetching remote files from path '{remote_path}'")
        try:
            list_result = self._client.list(remote_path)
            for entry in list_result.get("Entries", []):
                child_path = entry["FullPath"]
                is_file = "chunks" in entry
                if is_file:
                    logger.debug(f"Found remote file: {child_path}")
                    yield child_path
                else:
                    logger.debug(f"Found remote directory: {child_path}")
                    yield from self._get_remote_files(child_path)
        except NotFound:
            if self._client.exists(remote_path):
                logger.warning(
                    f"Remote path '{remote_path}' exists but is not a directory"
                )
                yield remote_path
            else:
                logger.error(f"Remote path '{remote_path}' not found")
                raise FileNotFoundError(f"Remote path '{remote_path}' not found")

    def _build_local_backup_path(self, path: str):
        return f"{path}.backup"

    def _backup_local(self, local_path: str):
        backup_path = self._build_local_backup_path(local_path)
        logger.info(f"Backing up local path '{local_path}' to '{backup_path}'")
        if os.path.exists(local_path):
            if os.path.exists(backup_path):
                logger.warning(f"Removing existing backup path '{backup_path}'")
                shutil.rmtree(backup_path)
            shutil.copytree(local_path, backup_path)

            def rmtree_onexc(func, path, err):
                logger.warning(f"An error occured when remove {path}: {err}")
                if path == local_path:
                    pass
                else:
                    raise err

            shutil.rmtree(local_path, onexc=rmtree_onexc)
            logger.info("Backup completed successfully")

    def _restore_local(self, local_path: str):
        backup_path = self._build_local_backup_path(local_path)
        logger.info(f"Restoring local path '{local_path}' from backup '{backup_path}'")
        if os.path.exists(backup_path):
            if os.path.exists(local_path):
                logger.warning(
                    f"Removing existing local path '{local_path}' before restore"
                )
                shutil.rmtree(local_path)
            shutil.copytree(backup_path, local_path)
            logger.info("Restore completed successfully")
        else:
            logger.error(f"No local backup found at '{backup_path}'")
            raise FileNotFoundError("No local backup to restore")

    def _delete_local_backup(self, local_path: str):
        backup_path = self._build_local_backup_path(local_path)
        logger.info(f"Deleting local backup at '{backup_path}'")
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
            logger.info("Backup deleted successfully")


class SeaweedfsSyncer:
    def __init__(self, client: SeaweedfsClient):
        self._client = client

    @classmethod
    def from_url(cls, base_url: str):
        client = SeaweedfsClient(base_url)
        return cls(client)

    def local2remote(self, local_path: str, remote_path: str):
        l2r = _SeaweedfsSyncerL2R(self._client)
        l2r.sync(local_path, remote_path)

    def remote2local(self, remote_path: str, local_path: str):
        r2l = _SeaweedfsSyncerR2L(self._client)
        r2l.sync(remote_path, local_path)


if __name__ == "__main__":
    syncer = SeaweedfsSyncer.from_url("http://localhost:52663")
    syncer.local2remote("./k8s", "/test")
    syncer.remote2local("/test", "./k8s2")
