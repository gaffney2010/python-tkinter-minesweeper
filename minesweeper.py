import collections
import enum
import functools
import itertools
import platform
import random
import tkinter as tk
from tkinter import messagebox
from typing import Dict, Iterator, Optional

import attr


# TODO: Switch X and Y
SIZE_X = 16
SIZE_Y = 30
N_MINES = 99

BTN_CLICK = "<Button-1>"
BTN_FLAG = "<Button-2>" if platform.system() == 'Darwin' else "<Button-3>"

window = None


class State(enum.Enum):
    HIDDEN = 0
    CLICKED = 1
    FLAGGED = 2
    MISCLICKED = 3


@attr.s(frozen=True)
class Coord(object):
    x: int = attr.ib()
    y: int = attr.ib()


def grid_coords() -> Iterator[Coord]:
    for x, y in itertools.product(range(SIZE_X), range(SIZE_Y)):
        yield Coord(x, y)


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
    n_mines: Optional[int] = attr.ib(default=None)
    n_flags: Optional[int] = attr.ib(default=None)
    game_over: bool = attr.ib(default=False)


class _Display(object):
    def __init__(self, tk_obj, click_callback, right_click_callback, restart_callback):
        # import images
        self.images = {
            "plain": tk.PhotoImage(file="images/tile_plain.gif"),
            "mine": tk.PhotoImage(file="images/tile_mine.gif"),
            "flag": tk.PhotoImage(file="images/tile_flag.gif"),
            "wrong": tk.PhotoImage(file="images/cell_wrong.gif"),
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
        self.mines.grid(row=SIZE_X+1, column=0,
                        columnspan=int(SIZE_Y/2))  # bottom left
        self.flags.grid(row=SIZE_X+1, column=int(SIZE_Y/2)-1,
                        columnspan=int(SIZE_Y/2))  # bottom right

        self.cell_buttons: Dict[Coord, tk.Button] = dict()
        for coord in grid_coords():
            cell_button = tk.Button(self.frame)
            cell_button.bind(BTN_CLICK, click_callback(coord))
            cell_button.bind(BTN_FLAG, right_click_callback(coord))
            cell_button.grid(row=coord.x, column=coord.y)
            self.cell_buttons[coord] = cell_button

        self.restart_button = tk.Button(self.frame)
        self.restart_button.bind(BTN_CLICK, restart_callback)
        self.restart_button.grid(row=SIZE_X+1, column=SIZE_Y//2)
        self.restart_button.config(image=self.images["mine"])

        # Minesweeper has to update this for the first time, will need to check None-ness
        self.state = BoardState()

    def update(self, state: BoardState) -> None:
        # TODO: Rewrite
        for coord, cell in state.grid.items():
            if self.state.grid[coord] == cell and self.state.game_over == state.game_over:
                # Nothing to update
                continue

            self.state.grid[coord] = cell.copy()

            if state.game_over and cell.is_mine:
                self.cell_buttons[coord].config(image=self.images["mine"])
                continue

            if cell.state == State.HIDDEN:
                self.cell_buttons[coord].config(image=self.images["plain"])
            if cell.state == State.CLICKED:
                self.cell_buttons[coord].config(
                    image=self.images["numbers"][cell.n_adj_mines])
            if cell.state == State.FLAGGED:
                self.cell_buttons[coord].config(image=self.images["flag"])
            if cell.state == State.MISCLICKED:
                self.cell_buttons[coord].config(image=self.images["wrong"])

        if self.state.n_mines != state.n_mines:
            self.state.n_mines = state.n_mines
            self.mines.config(text=f"Mines: {state.n_mines}")

        if self.state.n_flags != state.n_flags:
            self.state.n_flags = state.n_flags
            self.flags.config(text=f"Flags: {state.n_flags}")

        self.state.game_over = state.game_over

        # TODO: Do I need this?
        self.tk.update()


@functools.lru_cache(1)
def Display(*args, **kwargs) -> _Display:
    return _Display(*args, **kwargs)


class Minesweeper(object):
    def __init__(self, tk_obj):
        self.tk = tk_obj
        self.display = Display(
            tk_obj,
            self.on_click_wrapper,
            self.on_right_click_wrapper,
            lambda _: self.restart(),
        )
        self.restart()  # start game

    def restart(self):
        self.clickedCount = 0

        # Initialize State
        self.board_state = BoardState(
            grid={coord: Cell(coord=coord) for coord in grid_coords()},
            n_mines=N_MINES,
            n_flags=0,
        )

        # Assign mines
        for coord in random.sample(list(grid_coords()), N_MINES):
            self.board_state.grid[coord].is_mine = True

        # Assign mines
        for coord in grid_coords():
            self.board_state.grid[coord].n_adj_mines = len(
                [n for n in self.get_neighbors(coord) if n.is_mine])

        self.display.update(self.board_state)

    def game_over(self, won):
        self.board_state.game_over = True
        self.display.update(self.board_state)

    def get_neighbors(self, coord: Coord):
        x, y = coord.x, coord.y
        neighbors = []
        for dx, dy in itertools.product(range(-1, 2), range(-1, 2)):
            if dx == 0 and dy == 0:
                continue
            try:
                neighbors.append(self.board_state.grid[Coord(x+dx, y+dy)])
            except KeyError:
                pass
        return neighbors

    def on_click_wrapper(self, coord: Coord):
        return lambda _: self.on_click(self.board_state.grid[coord])

    def on_right_click_wrapper(self, coord: Coord):
        return lambda _: self.on_right_click(self.board_state.grid[coord])

    def on_click(self, cell):
        if cell.state in (State.CLICKED, State.FLAGGED):
            return

        if cell.is_mine:
            cell.state = State.MISCLICKED
            self.game_over(won=False)
            return

        cell.state = State.CLICKED
        self.clickedCount += 1
        if self.clickedCount == (SIZE_X * SIZE_Y) - N_MINES:
            self.game_over(True)

        autosolve(self, cell.coord)

        self.display.update(self.board_state)

    def on_right_click(self, cell):
        if cell.state in (State.CLICKED, State.FLAGGED):
            return

        if not cell.is_mine:
            cell.state = State.MISCLICKED
            self.game_over(won=False)
            return

        cell.state = State.FLAGGED
        self.board_state.n_flags += 1

        self.display.update(self.board_state)


def autosolve(ms: Minesweeper, start: Coord) -> None:
    if ms.board_state.grid[start].n_adj_mines > 0:
        return

    queue = collections.deque([start])

    while len(queue) != 0:
        coord = queue.popleft()

        for cell in ms.get_neighbors(coord):
            if cell.state != State.HIDDEN:
                continue

            if cell.n_adj_mines == 0:
                queue.append(cell.coord)

            cell.state = State.CLICKED
            ms.clickedCount += 1


def main():
    # create Tk instance
    window = tk.Tk()
    # set program title
    window.title("Minesweeper")
    # create game instance
    _ = Minesweeper(window)
    # run event loop
    window.mainloop()


if __name__ == "__main__":
    main()
