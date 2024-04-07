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
- flagged_squares (json - [(x,y)])

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
from typing import List, Optional, Tuple

import attr
from pypika import MySQLQuery, Table, Query

from minesweeper_lib import *

DATA_DIR = "data"


functools.lru_cache(1)


def connection() -> sqlite3.Connection:
    return sqlite3.connect(os.path.join(DATA_DIR, "db.sql"), isolation_level=None)


def coord_hash(coord: Coord) -> int:
    def mini_hash(x):
        return hash(x) % 2^16
    return mini_hash(coord.x) * 2**16 + mini_hash(coord.y)


def position_hash(ms: Minesweeper) -> int:
    result = 0
    for coord in grid_coords():
        if ms.grid[coord].state == State.CLICKED:
            result ^= coord_hash(coord) * 2**32
        if ms.grid[coord].state == State.FLAGGED:
            result ^= coord_hash(coord)
    return result


def coords_from_json(j: str) -> List[Coord]:
    return [Coord(x=t[0], y=t[1]) for t in json.loads(j)]


def json_from_coords(cs: List[Coord]) -> str:
    return json.dumps([(t.x, t.y) for t in cs])


def make_tables() -> None:
    cur = connection().cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS board (
            board_num INT PRIMARY KEY,
            mines VARCHAR NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS board_position (
            board_num INT,
            position_hash INT,
            revealed_squares VARCHAR NOT NULL,
            flagged_squares VARCHAR NOT NULL,
            PRIMARY KEY (board_num, position_hash)
        )
    """)


@attr.s()
class BoardValue(object):
    mines: List[Coord] = attr.ib()


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


@attr.s()
class BoardPositionValue(object):
    revealed_squares: List[Coord] = attr.ib()
    flagged_squares: List[Coord] = attr.ib()


def board_position_from_ms(ms: Minesweeper) -> BoardPositionValue:
    return BoardPositionValue(
        revealed_squares = [c for c in grid_coords() if ms.grid[c].state == State.CLICKED],
        flagged_squares = [c for c in grid_coords() if ms.grid[c].state == State.FLAGGED],
    )


def read_board_position(board_num: int, position_hash: int) -> BoardPositionValue:
    board_position = Table("board_position")
    query = (
        Query.from_(board_position)
        .select(board_position.revealed_squares, board_position.flagged_squares)
        .where(board_position.board_num == board_num)
        .where(board_position.position_hash == position_hash)
        .get_sql()
    )
    res = connection().cursor().execute(query)
    vals = res.fetchone()
    return BoardPositionValue(
        revealed_squares=coords_from_json(vals[0]),
        flagged_squares=coords_from_json(vals[1]),
    )


def all_positions() -> List[Tuple[int, int]]:
    board_position = Table("board_position")
    query = (
        Query.from_(board_position)
        .select(board_position.board_num, board_position.position_hash)
        .get_sql()
    )
    res = connection().cursor().execute(query)
    return res.fetchall()


def write_board_position(board_num: int, position_hash: int, value: BoardPositionValue) -> None:
    board_position = Table("board_position")
    query = (
        MySQLQuery.into(board_position)
        .columns(board_position.board_num, board_position.position_hash, board_position.revealed_squares, board_position.flagged_squares)
        .insert(board_num, position_hash, json_from_coords(value.revealed_squares), json_from_coords(value.flagged_squares))
        .ignore()
        .get_sql()
    )
    query = query.replace("INSERT IGNORE", "INSERT OR IGNORE")
    _ = connection().cursor().execute(query)
