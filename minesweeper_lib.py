import enum
import functools
import itertools
import platform
import random
import tkinter as tk
from typing import Callable, Dict, List, Optional

import attr


SIZE_X = 30
SIZE_Y = 16
N_MINES = 99

BTN_CLICK = "<Button-1>"
BTN_FLAG = "<Button-2>" if platform.system() == 'Darwin' else "<Button-3>"

N_SIMS = 10


class State(enum.Enum):
    HIDDEN = 0
    CLICKED = 1
    FLAGGED = 2
    MISCLICKED = 3


@attr.s(frozen=True)
class Coord(object):
    x: int = attr.ib()
    y: int = attr.ib()


class ActionType(enum.Enum):
    UNKNOWN = 0
    CLEAR = 1
    FLAG = 2


@attr.s(frozen=True)
class Action(object):
    type: ActionType = attr.ib()
    coord: Coord = attr.ib()


@attr.s()
class Cell(object):
    coord: Coord = attr.ib()
    is_mine: bool = attr.ib(default=False)
    state: State = attr.ib(default=State.HIDDEN)
    n_adj_mines: int = attr.ib(default=0)

    def __eq__(self, other: 'Cell') -> bool:
        if self.is_mine != other.is_mine:
            return False
        if self.state != other.state:
            return False
        if self.n_adj_mines != other.n_adj_mines:
            return False
        return True

    def copy(self) -> 'Cell':
        return Cell(
            coord=self.coord,
            is_mine=self.is_mine,
            state=self.state,
            n_adj_mines=self.n_adj_mines,
        )


@attr.s()
class BoardState(object):
    grid: Dict[Coord, Optional[Cell]] = attr.ib(
        factory=lambda: {c: None for c in grid_coords()})
    probs: Dict[Coord, int] = attr.ib(factory=lambda: {c: None for c in grid_coords()})
    n_mines: Optional[int] = attr.ib(default=None)
    n_flags: Optional[int] = attr.ib(default=None)
    lost: bool = attr.ib(default=False)


class _Display(object):
    def __init__(self, tk_obj, click_callback, right_click_callback):
        # import images
        self.images = {
            "plain": tk.PhotoImage(file="images/tile_plain.gif"),
            "mine": tk.PhotoImage(file="images/tile_mine.gif"),
            "flag": tk.PhotoImage(file="images/tile_flag.gif"),
            "wrong": tk.PhotoImage(file="images/tile_wrong.gif"),
            "numbers": [tk.PhotoImage(file="images/tile_clicked.gif")],
        }
        for i in range(1, 9):
            self.images["numbers"].append(
                tk.PhotoImage(file=f"images/tile_{i}.gif"))

        # set up frame
        self.tk = tk_obj
        self.frame = tk.Frame(self.tk)
        self.frame.pack()

        # set up labels/UI
        self.mines = tk.Label(self.frame)
        self.flags = tk.Label(self.frame)
        self.mines.grid(row=SIZE_Y+1, column=0,
                        columnspan=int(SIZE_X/2))  # bottom left
        self.flags.grid(row=SIZE_Y+1, column=int(SIZE_X/2)-1,
                        columnspan=int(SIZE_X/2))  # bottom right

        self.cell_buttons: Dict[Coord, tk.Button] = dict()
        self.cell_texts: Dict[Coord, str] = dict()
        for coord in grid_coords():
            self.cell_texts[coord] = ""
            cell_button = tk.Button(
                self.frame, text="", compound="center", font=("Helvetica", 8))
            cell_button.bind(BTN_CLICK, click_callback(coord))
            cell_button.bind(BTN_FLAG, right_click_callback(coord))
            cell_button.grid(row=coord.y, column=coord.x)
            self.cell_buttons[coord] = cell_button

        self.restart_button = tk.Button(self.frame)
        self.restart_button.grid(row=SIZE_Y+1, column=SIZE_X//2)
        self.restart_button.config(image=self.images["mine"])

        # Minesweeper has to update this for the first time, will need to check None-ness
        self.state = BoardState()

    def update(self, state: BoardState) -> None:
        for coord, prob in state.probs.items():
            if prob is None:
                continue
            self.cell_texts[coord] = str(prob)

        for coord, cell in state.grid.items():
            if self.state.grid[coord] == cell and self.state.lost == state.lost and self.state.probs[coord] == state.probs[coord]:
                # Nothing to update.  Whole board gets updated when lost changes; minimal inefficiency
                continue

            self.state.grid[coord] = cell.copy()

            if cell.state == State.MISCLICKED:
                self.cell_texts[coord] = ""
                self.cell_buttons[coord].config(image=self.images["wrong"],
                                                text=self.cell_texts[coord],
                                                )
                continue

            if state.lost and cell.is_mine:
                self.cell_texts[coord] = ""
                self.cell_buttons[coord].config(
                    image=self.images["mine"],
                    text=self.cell_texts[coord],
                )
                continue

            if cell.state == State.HIDDEN:
                self.cell_buttons[coord].config(
                    image=self.images["plain"],
                    text=self.cell_texts[coord],
                )
            if cell.state == State.CLICKED:
                self.cell_texts[coord] = ""
                self.cell_buttons[coord].config(
                    image=self.images["numbers"][cell.n_adj_mines],
                    text=self.cell_texts[coord],
                )
            if cell.state == State.FLAGGED:
                self.cell_texts[coord] = ""
                self.cell_buttons[coord].config(
                    image=self.images["flag"],
                    text=self.cell_texts[coord],
                )

        if self.state.n_mines != state.n_mines:
            self.state.n_mines = state.n_mines
            self.mines.config(text=f"Mines: {state.n_mines}")

        if self.state.n_flags != state.n_flags:
            self.state.n_flags = state.n_flags
            self.flags.config(text=f"Flags: {state.n_flags}")

        if self.state.lost != state.lost:
            if state.lost:
                self.restart_button.config(image=self.images["wrong"])
            else:
                self.restart_button.config(image=self.images["plain"])
        self.state.lost = state.lost


@functools.lru_cache(1)
def Display(*args, **kwargs) -> _Display:
    return _Display(*args, **kwargs)


class Neighbors(object):
    def __init__(self, coords: List[Coord]):
        self.coords = coords
        self.filters = [lambda n: 0 <= n.x < SIZE_X and 0 <= n.y < SIZE_Y]

    def filter(self, f: Callable) -> "Neighbors":
        self.filters.append(f)
        return self

    def __iter__(self):
        for c in self.coords:
            for filter in self.filters:
                if not filter(c):
                    break
            else:
                yield c


def grid_coords() -> Neighbors:
    result = []
    for x, y in itertools.product(range(SIZE_X), range(SIZE_Y)):
        result.append(Coord(x, y))
    return Neighbors(result)


def get_neighbors(coord: Coord) -> Neighbors:
    x, y = coord.x, coord.y
    neighbors = []
    for dx, dy in itertools.product(range(-1, 2), range(-1, 2)):
        if dx == 0 and dy == 0:
            continue
        neighbors.append(Coord(x+dx, y+dy))
    return Neighbors(neighbors)


class Minesweeper(object):
    def __init__(self, display, mines: List[Coord]):
        self.display = display

        # Initialize state
        self.clicked_count = 0
        self.lost = False
        self.grid = {coord: Cell(coord=coord) for coord in grid_coords()}
        self.probs = {coord: None for coord in grid_coords()}
        self.n_mines = N_MINES
        self.n_flags = 0

        # Assign mines
        for coord in mines:
            self.grid[coord].is_mine = True

        # Count adjacent mines
        for coord in grid_coords():
            self.grid[coord].n_adj_mines = len(
                list(get_neighbors(coord).filter(lambda n: self.grid[n].is_mine)))

        self.display_update()

    def display_update(self) -> None:
        """More shorthand"""
        self.display.update(BoardState(
            grid=self.grid,
            probs=self.probs,
            n_mines=self.n_mines,
            n_flags=self.n_flags,
            lost=self.lost,
        ))
