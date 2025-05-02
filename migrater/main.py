import argparse
import sys
from os import getenv

import uvicorn
from fastapi import FastAPI, HTTPException
from loguru import logger

from migrater.seaweedfs import TrivialMigrater

app = FastAPI()

migrater_instance = None


@app.post("/push")
async def handle_push():
    if migrater_instance:
        migrater_instance.push()
        return
    else:
        raise HTTPException(status_code=500, detail="Migrater not initialized")


@app.post("/pull")
async def handle_pull():
    if migrater_instance:
        migrater_instance.pull()
        return
    else:
        raise HTTPException(status_code=500, detail="Migrater not initialized")


def start_server(host: str, port: int):
    uvicorn.run(app, host=host, port=port)


def main():
    parser = argparse.ArgumentParser(description="SeaweedFS Migration Tool")

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
        help="Do a pull before serving",
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
            logger.info("Pulling...")
            migrater.pull()
        migrater_instance = migrater
        logger.info("Starting server...")
        start_server(args.host, args.port)
    elif args.operation == "push":
        migrater.push()
    elif args.operation == "pull":
        migrater.pull()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
