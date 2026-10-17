"""CLI entry points for the Tawarruq engine."""

import argparse
import asyncio
import logging

import uvicorn

from tawarruq.amanah.worker import AmanahWorker
from tawarruq.config import get_settings
from tawarruq.database import init_db
from tawarruq.services.application_service import get_or_create_default_institution


def main() -> None:
    parser = argparse.ArgumentParser(description="Buruuj Tawarruq Engine")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Run the API server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    worker_cmd = sub.add_parser("worker", help="Run Amanah worker standalone")
    worker_cmd.add_argument("--read-only", action="store_true")

    init_cmd = sub.add_parser("init-db", help="Initialize database")

    args = parser.parse_args()
    logging.basicConfig(level=get_settings().log_level)

    if args.command == "serve":
        uvicorn.run("tawarruq.main:app", host=args.host, port=args.port, reload=args.reload)
    elif args.command == "worker":
        init_db()
        worker = AmanahWorker(write_enabled=not args.read_only)
        asyncio.run(worker.run_forever())
    elif args.command == "init-db":
        init_db()
        from tawarruq.database import SessionLocal

        db = SessionLocal()
        get_or_create_default_institution(db)
        from tawarruq.services.seed_service import seed_kenya_defaults

        seed_kenya_defaults(db)
        db.commit()
        db.close()
        print("Database initialized with Kenya defaults.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
