"""This file contains helpers for data read and write.

DATABASE DETAILS
================
board
- board_num (int) - KEY
- mines (json - [(x, y)])

board_position
- board_num (int) - KEY
- position_hash (uuid) - KEY
- revealed_squares (json - [(x,y)])

simulations
- board_num (int) - KEY
- position_hash (uuid) - KEY
- sim_id (uuid)
- coords (json - [(x, y)])
"""

import functools
import json
import os
import sqlite3
from typing import List, Optional

import attr
from pypika import Table, Query

import minesweeper_lib as m

DATA_DIR = "data"


@attr.s()
class BoardValue(object):
    mines: List[m.Coord] = attr.ib()


functools.lru_cache(1)


def connection() -> sqlite3.Connection:
    return sqlite3.connect(os.path.join(DATA_DIR, "db.sql"), isolation_level=None)


def coords_from_json(j: str) -> List[m.Coord]:
    return [m.Coord(x=t[0], y=t[1]) for t in json.loads(j)]


def json_from_coords(cs: List[m.Coord]) -> str:
    return json.dumps([(t.x, t.y) for t in cs])


def make_tables() -> None:
    cur = connection().cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS board (
            board_num INT PRIMARY KEY,
            mines VARCHAR NOT NULL
        );
    """)


def read_board(board_num: int) -> Optional[BoardValue]:
    """Will return None if board_num is not found"""
    board = Table("board")
    query = (
        Query.from_(board)
        .select(board.mines)
        .where(board.board_num == board_num)
        .get_sql()
    )
    res = connection().cursor().execute(query)
    if one := res.fetchone():
        return BoardValue(
            mines=coords_from_json(one[0]),
        )


def write_board(board_num: int, value: BoardValue) -> None:
    board = Table("board")
    query = (
        Query.into(board)
        .columns(board.board_num, board.mines)
        .insert(board_num, json_from_coords(value.mines))
        .get_sql()
    )
    _ = connection().cursor().execute(query)
