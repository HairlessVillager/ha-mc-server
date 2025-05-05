import argparse
from os import getenv
from time import time

import uvicorn
from fastapi import FastAPI, HTTPException
from loguru import logger
from mcrcon import MCRcon

from migrater.seaweedfs import TrivialMigrater

app = FastAPI()

migrater_instance = None


@app.post("/saving")
async def saving():
    time0 = time()
    logger.info("Saving: save-all from game")
    with MCRcon(host="mc-server", port=25575, password="rcon123") as client:
        try:
            client.command("say Saving the game...")
            response = client.command("save-all flush")
            logger.debug(f"RCON response: {response}")
            time1 = time()
            client.command(f"say Saving the game...flushed in {time1 - time0:.3f}s")
            logger.info("Saving: push to the remote")
            if migrater_instance:
                migrater_instance.push()
                time2 = time()
                client.command(f"say Saving the game...pushed in {time2 - time1:.3f}s")
                client.command("say Saving the game...done")
                return
            else:
                raise HTTPException(status_code=500, detail="Migrater not initialized")
        except Exception:
            client.command("say Saving the game...failed")


def start_server(host: str, port: int):
    uvicorn.run(app, host=host, port=port)


def main():
    parser = argparse.ArgumentParser(description="Saving Agent")

    subparsers = parser.add_subparsers(dest="operation", required=True)

    # push
    push_parser = subparsers.add_parser("push", help="Push data to SeaweedFS")
    push_parser.add_argument(
        "--local-path",
        default=getenv("MIGRATER_LOCAL_PATH"),
        help="Local path for migration (default: value from MIGRATER_LOCAL_PATH)",
    )
    push_parser.add_argument(
        "--remote-path",
        default=getenv("MIGRATER_REMOTE_PATH"),
        help="Remote path for migration (default: value from MIGRATER_REMOTE_PATH)",
    )
    push_parser.add_argument(
        "--filer-url",
        default=getenv("SEAWEEDFS_FILER_URL"),
        help="SeaweedFS Filer URL (default: value from SEAWEEDFS_FILER_URL)",
    )

    # pull
    pull_parser = subparsers.add_parser("pull", help="Pull data from SeaweedFS")
    pull_parser.add_argument(
        "--local-path",
        default=getenv("MIGRATER_LOCAL_PATH"),
        help="Local path for migration (default: value from MIGRATER_LOCAL_PATH)",
    )
    pull_parser.add_argument(
        "--remote-path",
        default=getenv("MIGRATER_REMOTE_PATH"),
        help="Remote path for migration (default: value from MIGRATER_REMOTE_PATH)",
    )
    pull_parser.add_argument(
        "--filer-url",
        default=getenv("SEAWEEDFS_FILER_URL"),
        help="SeaweedFS Filer URL (default: value from SEAWEEDFS_FILER_URL)",
    )

    # server
    server_parser = subparsers.add_parser("server", help="Start migration server")
    server_parser.add_argument(
        "--local-path",
        default=getenv("MIGRATER_LOCAL_PATH"),
        help="Local path for migration (default: value from MIGRATER_LOCAL_PATH)",
    )
    server_parser.add_argument(
        "--remote-path",
        default=getenv("MIGRATER_REMOTE_PATH"),
        help="Remote path for migration (default: value from MIGRATER_REMOTE_PATH)",
    )
    server_parser.add_argument(
        "--filer-url",
        default=getenv("SEAWEEDFS_FILER_URL"),
        help="SeaweedFS Filer URL (default: value from SEAWEEDFS_FILER_URL)",
    )
    server_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Server host (default: 0.0.0.0)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=9000,
        help="Server port (default: 9000)",
    )
    server_parser.add_argument(
        "--pull-first",
        action="store_true",
        help="Try to pull before serving (default: true)",
    )

    args = parser.parse_args()

    migrater = TrivialMigrater(
        local_path=args.local_path,
        remote_path=args.remote_path,
        filer_url=args.filer_url,
    )

    global migrater_instance

    if args.operation == "server":
        if args.pull_first:
            try:
                logger.info("Pulling...")
                migrater.pull()
            except Exception as e:
                logger.warning(f"Pulling...failed with error: {e}")
        migrater_instance = migrater
        logger.info("Starting server...")
        start_server(args.host, args.port)
    elif args.operation == "push":
        migrater.push()
    elif args.operation == "pull":
        migrater.pull()


if __name__ == "__main__":
    main()
