from pathlib import Path

import click
import uvicorn

from .capture import run as run_capture
from .cards import build_index
from .config import load
from .db import DB
from .server import make_app


@click.group()
@click.option("--config", default="config/default.yaml", show_default=True)
@click.pass_context
def cli(ctx, config):
    ctx.ensure_object(dict)
    ctx.obj["cfg"] = load(config)


@cli.command()
@click.pass_context
def serve(ctx):
    """Run the Linux-side receiver: ROI gate -> VLM -> diff -> SQLite."""
    cfg = ctx.obj["cfg"]
    app = make_app(cfg)
    uvicorn.run(app, host=cfg.server.host, port=cfg.server.port)


@cli.command()
@click.pass_context
def capture(ctx):
    """Run on the Windows PC. Capture MTGO frames at fps and POST to server."""
    cfg = ctx.obj["cfg"]
    run_capture(cfg)


@cli.command(name="build-index")
@click.option("--sets", default=None, help="comma-separated set codes (limits scope; faster)")
@click.option("--max-cards", default=None, type=int)
@click.pass_context
def build_index_cmd(ctx, sets, max_cards):
    """Build the optional Scryfall phash index used to verify card names."""
    cfg = ctx.obj["cfg"]
    set_list = [s.strip() for s in sets.split(",")] if sets else None
    out = build_index(Path(cfg.scryfall.cache_dir), sets=set_list, max_cards=max_cards)
    click.echo(f"index written to {out}")


@cli.command()
@click.pass_context
def games(ctx):
    """List recorded games."""
    cfg = ctx.obj["cfg"]
    db = DB(Path(cfg.server.data_dir) / "analyst.db")
    with db.conn() as c:
        rows = c.execute(
            "SELECT id, started_at, ended_at, result FROM games ORDER BY started_at DESC"
        ).fetchall()
    for r in rows:
        click.echo(
            f"{r['id']}  {r['started_at']}  -> {r['ended_at'] or 'in-progress':<26}  "
            f"{r['result'] or ''}"
        )


@cli.command()
@click.argument("game_id")
@click.pass_context
def replay(ctx, game_id):
    """Print the event timeline for a recorded game."""
    cfg = ctx.obj["cfg"]
    db = DB(Path(cfg.server.data_dir) / "analyst.db")
    with db.conn() as c:
        rows = c.execute(
            """SELECT ts, turn, phase, type, actor, target, payload_json
               FROM events WHERE game_id = ? ORDER BY id""",
            (game_id,),
        ).fetchall()
    for r in rows:
        click.echo(
            f"T{r['turn']} {r['phase']:<22} {r['type']:<22} "
            f"{r['actor'] or '':<6} {r['target'] or ''}"
        )


if __name__ == "__main__":
    cli()
