"""更新日志管理 CLI（014）：免 SQL 维护 release_notes。

用法::

    python -m app.cli.release_notes add --title "标题" --type feature \
        --released-at 2026-07-18 [--detail "详情 Markdown"]
    python -m app.cli.release_notes list [--limit 20]
    python -m app.cli.release_notes delete <id>     # 软删除
    python -m app.cli.release_notes restore <id>    # 恢复

type 取值：feature / bugfix / improvement / notice。
"""

import argparse
from datetime import UTC, date, datetime

from sqlalchemy import select

from ..database import SessionLocal
from ..models.release_note import ReleaseNote

_VALID_TYPES = {"feature", "bugfix", "improvement", "notice"}


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def cmd_add(args: argparse.Namespace) -> None:
    if args.type not in _VALID_TYPES:
        print(f"非法 type：{args.type}（允许：{', '.join(sorted(_VALID_TYPES))}）")
        raise SystemExit(2)
    with SessionLocal() as db:
        note = ReleaseNote(
            title=args.title,
            type=args.type,
            detail=args.detail,
            released_at=args.released_at,
            is_deleted=0,
            created_at=datetime.now(UTC),
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        print(f"created id={note.id}  {note.released_at}  [{note.type}] {note.title}")


def cmd_list(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(ReleaseNote)
                .order_by(ReleaseNote.released_at.desc(), ReleaseNote.id.desc())
                .limit(args.limit)
            )
            .scalars()
            .all()
        )
        if not rows:
            print("(空)")
            return
        for r in rows:
            flag = "[del]" if r.is_deleted else "     "
            print(f"{r.id}\t{r.released_at}\t{flag}\t{r.type:11s}\t{r.title}")


def _set_deleted(note_id: int, deleted: int) -> None:
    with SessionLocal() as db:
        r = db.get(ReleaseNote, note_id)
        if r is None:
            print(f"未找到 id={note_id}")
            raise SystemExit(1)
        r.is_deleted = deleted
        db.commit()
        print(f"{'soft-deleted' if deleted else 'restored'} id={r.id}")


def cmd_delete(args: argparse.Namespace) -> None:
    _set_deleted(args.id, 1)


def cmd_restore(args: argparse.Namespace) -> None:
    _set_deleted(args.id, 0)


def main() -> None:
    p = argparse.ArgumentParser(prog="release_notes", description="更新日志管理")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="新增一条")
    a.add_argument("--title", required=True)
    a.add_argument("--type", required=True)
    a.add_argument("--released-at", required=True, type=_parse_date, dest="released_at")
    a.add_argument("--detail", default=None)
    a.set_defaults(func=cmd_add)

    lst = sub.add_parser("list", help="列出最近 N 条")
    lst.add_argument("--limit", type=int, default=20)
    lst.set_defaults(func=cmd_list)

    d = sub.add_parser("delete", help="软删除")
    d.add_argument("id", type=int)
    d.set_defaults(func=cmd_delete)

    rs = sub.add_parser("restore", help="恢复软删除")
    rs.add_argument("id", type=int)
    rs.set_defaults(func=cmd_restore)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
