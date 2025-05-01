from pathlib import PurePath
import os
import shutil

import requests

class SeaweedfsClientError(Exception):
    pass

class NotFound(SeaweedfsClientError):
    pass

class SeaweedfsClient:

    def __init__(self, base_url: str):
        self._base_url = base_url

    def _build_url(self, remote_path: str):
        return self._base_url + remote_path

    def _raise_error_from_response(self, response: requests.Response):
        if response.content:
            j = response.json()
            if "error" in j:
                raise SeaweedfsClientError(j["error"])

    def upload(
        self,
        local_path: str,
        remote_path: str,
        *,
        append: bool = False,
        use_put: bool = False,
    ):
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
        return response.json()

    def delete(
        self,
        remote_path: str,
        *,
        recursive: bool = False,
    ):
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
        url = self._build_url(remote_path)
        response = requests.get(url)
        with open(local_path, "wb") as f:
            f.write(response.content)

    def move(
        self,
        src_path: str,
        dst_path: str,
    ):
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
        url = self._build_url(remote_path)
        headers = {
            "Accept": "application/json",
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            raise NotFound()
        elif response.headers["Content-Type"] == "application/json":
            return response.json()
        elif "text/plain" in response.headers["Content-Type"]:
            parent_path = str(PurePath(remote_path).parent)
            return self.list(parent_path)
        else:
            print(response.headers)
            print(response.content)
            raise Exception("unknown error")

    def exists(
        self,
        remote_path: str,
    ):
        is_exists = True
        try:
            self.list(remote_path)
        except NotFound:
            is_exists = False
        return is_exists

    def metadata(
        self,
        remote_path: str,
    ):
        url = self._build_url(remote_path)
        params = {
            "metadata": "true",
        }
        response = requests.get(url, params=params)
        return response.json()

class SeaweedfsSyncer:

    def __init__(self, base_url: str):
        self._client = SeaweedfsClient(base_url)

    def sync_to_remote(self, local_path: str, remote_path: str):
        self._backup(remote_path)
        try:
            for local_file_path in self._get_local_files(local_path):
                local_file_relpath = os.path.relpath(local_file_path, local_path)
                remote_file_path = os.path.join(remote_path, local_file_relpath)
                self._client.upload(
                    local_path=local_file_path,
                    remote_path=remote_file_path
                )
            backup_path = self._build_backup_path(remote_path)
            self._client.delete(backup_path, recursive=True)
        except:
            self._restore(remote_path)
            raise

    def _build_backup_path(self, origin_path: str):
        return origin_path + ".backup"

    def _backup(self, remote_path: str):
        origin_path = remote_path
        backup_path = self._build_backup_path(origin_path)

        if self._client.exists(origin_path):
            if self._client.exists(backup_path):
                raise Exception("a backup dir exists")
            else:
                self._client.move(origin_path, backup_path)
        else:
            pass

    def _restore(self, remote_path: str):
        origin_path = remote_path
        backup_path = self._build_backup_path(origin_path)

        if self._client.exists(backup_path):
            self._client.move(backup_path, origin_path)
        else:
            raise Exception("no backup dir exists")

    def _get_local_files(self, local_path: str):
        for root, paths, files in os.walk(local_path):
            for file in files:
                file_path = os.path.join(root, file)
                yield file_path

    def sync_from_remote(self, remote_path: str, local_path: str):
        self._backup_local(local_path)
        try:
            os.makedirs(local_path, exist_ok=True)
            for remote_file in self._get_remote_files(remote_path):
                remote_rel = PurePath(remote_file).relative_to(remote_path)
                local_file = PurePath(local_path) / remote_rel
                local_dir = local_file.parent
                os.makedirs(str(local_dir), exist_ok=True)
                self._client.download(remote_file, str(local_file))
            self._delete_local_backup(local_path)
        except Exception:
            self._restore_local(local_path)
            raise

    def _get_remote_files(self, remote_path: str):
        try:
            items = self._client.list(remote_path)
            for item in items.get("Entries", []):
                child_path = str(PurePath(remote_path).joinpath(item["Name"]))
                yield from self._get_remote_files(child_path)
        except NotFound:
            if self._client.exists(remote_path):
                yield remote_path
            else:
                raise FileNotFoundError(f"Remote path '{remote_path}' not found")

    def _build_local_backup_path(self, path: str):
        return f"{path}.backup"

    def _backup_local(self, local_path: str):
        backup_path = self._build_local_backup_path(local_path)
        if os.path.exists(local_path):
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            shutil.move(local_path, backup_path)

    def _restore_local(self, local_path: str):
        backup_path = self._build_local_backup_path(local_path)
        if os.path.exists(backup_path):
            if os.path.exists(local_path):
                shutil.rmtree(local_path)
            shutil.move(backup_path, local_path)
        else:
            raise FileNotFoundError("No local backup to restore")

    def _delete_local_backup(self, local_path: str):
        backup_path = self._build_local_backup_path(local_path)
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
            
if __name__ == "__main__":
    syncer = SeaweedfsSyncer("http://localhost:8888")
    syncer.sync_to_remote("../k8s", "/test-k8s")
    breakpoint()
    syncer.sync_from_remote("/test-k8s", "../k8s2")
