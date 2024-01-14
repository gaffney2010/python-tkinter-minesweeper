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
    mines: int = attr.ib(default=0)

    def __eq__(self, other: 'Cell') -> bool:
        if self.is_mine != other.is_mine:
            return False
        if self.state != other.state:
            return False
        if self.mines != other.mines:
            return False
        return True
    
    def copy(self) -> 'Cell':
        return Cell(
            coord=self.coord,
            is_mine=self.is_mine,
            state=self.state,
            mines=self.mines,
        )


@attr.s()
class BoardState(object):
    grid: Dict[Coord, Optional[Cell]] = attr.ib(
        factory=lambda: {c: None for c in grid_coords()})
    n_mines: Optional[int] = attr.ib(default=None)
    n_flags: Optional[int] = attr.ib(default=None)
    game_over: bool = attr.ib(default=False)


class _Display(object):
    def __init__(self, tk_obj, click_callback, right_click_callback):
        # import images
        self.images = {
            "plain": tk.PhotoImage(file="images/tile_plain.gif"),
            "mine": tk.PhotoImage(file="images/tile_mine.gif"),
            "flag": tk.PhotoImage(file="images/tile_flag.gif"),
            # TODO: Use for misplace flag
            # "wrong": tk.PhotoImage(file="images/cell_wrong.gif"),
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
                self.cell_buttons[coord].config(image=self.images["numbers"][cell.mines])
            if cell.state == State.FLAGGED:
                self.cell_buttons[coord].config(image=self.images["flag"])

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
            tk_obj, self.on_click_wrapper, self.on_right_click_wrapper)
        self.restart()  # start game

    def restart(self):
        self.clickedCount = 0

        # Initialize State
        self.board_state = BoardState(
            grid={coord: Cell(coord=coord) for coord in grid_coords()},
            n_mines=N_MINES,
            n_flags=0,
        )

        # Assign mines now
        for coord in random.sample(list(grid_coords()), N_MINES):
            self.board_state.grid[coord].is_mine = True

        # loop again to find nearby mines and display number on cell
        for coord in grid_coords():
            mc = 0
            for n in self.get_neighbors(coord):
                mc += 1 if n.is_mine else 0
            self.board_state.grid[coord].mines = mc

        self.display.update(self.board_state)

    def game_over(self, won):
        self.board_state.game_over = True
        self.display.update(self.board_state)

        msg = "You Win! Play again?" if won else "You Lose! Play again?"
        res = messagebox.askyesno("Game Over", msg)
        if res:
            self.restart()
        else:
            self.tk.quit()

    def get_neighbors(self, coord: Coord):
        x, y = coord.x, coord.y
        neighbors = []
        coords = [
            Coord(x-1, y-1),
            Coord(x-1, y),
            Coord(x-1, y+1),
            Coord(x, y-1),
            Coord(x, y+1),
            Coord(x+1, y-1),
            Coord(x+1, y),
            Coord(x+1, y+1),
        ]
        for coord in coords:
            try:
                neighbors.append(self.board_state.grid[coord])
            except KeyError:
                pass
        return neighbors

    def on_click_wrapper(self, coord: Coord):
        return lambda _: self.on_click(self.board_state.grid[coord])

    def on_right_click_wrapper(self, coord: Coord):
        return lambda _: self.on_right_click(self.board_state.grid[coord])

    def on_click(self, cell):
        if cell.state in (State.CLICKED, State.FLAGGED):
            # Nothing to do here
            return

        if cell.is_mine:
            # end game
            self.game_over(False)
            return

        cell.state = State.CLICKED
        if cell.mines == 0:
            self.clear_surrounding_cells(cell.coord)

        self.clickedCount += 1
        if self.clickedCount == (SIZE_X * SIZE_Y) - N_MINES:
            self.game_over(True)

        self.display.update(self.board_state)

    def on_right_click(self, cell):
        if cell.state in (State.CLICKED, State.FLAGGED):
            # Nothing to do here
            return

        if not cell.is_mine:
            # end game
            self.game_over(False)
            return

        cell.state = State.FLAGGED
        self.board_state.n_flags += 1

        self.display.update(self.board_state)

    def clear_surrounding_cells(self, coord: Coord):
        queue = collections.deque([coord])

        while len(queue) != 0:
            coord = queue.popleft()

            for cell in self.get_neighbors(coord):
                self.clear_cell(cell, queue)

    def clear_cell(self, cell, queue):
        if cell.state != State.HIDDEN:
            return

        cell.state = State.CLICKED
        if cell.mines == 0:
            queue.append(cell.coord)
        self.clickedCount += 1


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
