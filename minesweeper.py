import collections
import enum
import functools
import itertools
import platform
import random
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, Iterator, List, Optional

import attr


SIZE_X = 30
SIZE_Y = 16
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


class ActionType(enum.Enum):
    UNKNOWN = 0
    CLEAR = 1
    FLAG = 2


@attr.s(frozen=True)
class Action(object):
    type: ActionType = attr.ib()
    coord: Coord = attr.ib()


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
    lost: bool = attr.ib(default=False)


class _Display(object):
    def __init__(self, tk_obj, click_callback, right_click_callback, restart_callback):
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
        for coord in grid_coords():
            cell_button = tk.Button(self.frame)
            cell_button.bind(BTN_CLICK, click_callback(coord))
            cell_button.bind(BTN_FLAG, right_click_callback(coord))
            cell_button.grid(row=coord.y, column=coord.x)
            self.cell_buttons[coord] = cell_button

        self.restart_button = tk.Button(self.frame)
        self.restart_button.bind(BTN_CLICK, restart_callback)
        self.restart_button.grid(row=SIZE_Y+1, column=SIZE_X//2)
        self.restart_button.config(image=self.images["mine"])

        # Minesweeper has to update this for the first time, will need to check None-ness
        self.state = BoardState()

    def update(self, state: BoardState) -> None:
        for coord, cell in state.grid.items():
            if self.state.grid[coord] == cell and self.state.lost == state.lost:
                # Nothing to update.  Whole board gets updated when lost changes; minimal inefficiency
                continue

            self.state.grid[coord] = cell.copy()

            if cell.state == State.MISCLICKED:
                self.cell_buttons[coord].config(image=self.images["wrong"])
                continue

            if state.lost and cell.is_mine:
                self.cell_buttons[coord].config(image=self.images["mine"])
                continue

            if cell.state == State.HIDDEN:
                self.cell_buttons[coord].config(image=self.images["plain"])
            if cell.state == State.CLICKED:
                self.cell_buttons[coord].config(
                    image=self.images["numbers"][cell.n_adj_mines])
            if cell.state == State.FLAGGED:
                self.cell_buttons[coord].config(image=self.images["flag"])

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
        self.lost = False

        # Initialize State
        self.board_state = BoardState(
            grid={coord: Cell(coord=coord) for coord in grid_coords()},
            n_mines=N_MINES,
            n_flags=0,
        )

        # Assign mines
        for coord in random.sample(list(grid_coords()), N_MINES):
            self.board_state.grid[coord].is_mine = True

        # Count adjacent mines
        for coord in grid_coords():
            self.board_state.grid[coord].n_adj_mines = len(list(self.get_neighbors(coord).filter(lambda n: self.board_state.grid[n].is_mine)))

        self.display_update()

    def grid(self, coord: Coord) -> Cell:
        """Just shorthand"""
        return self.board_state.grid[coord]
    
    def display_update(self) -> None:
        """More shorthand"""
        self.display.update(self.board_state)

    # TODO: Delete or move out of Minesweeper
    def game_over(self, won):
        if not won:
            # If they won, then we don't have to change any behavior
            self.board_state.lost = True
        self.display_update()

    # TODO: Delete or move out of Minesweeper
    def get_neighbors(self, coord: Coord) -> Neighbors:
        x, y = coord.x, coord.y
        neighbors = []
        for dx, dy in itertools.product(range(-1, 2), range(-1, 2)):
            if dx == 0 and dy == 0:
                continue
            neighbors.append(Coord(x+dx, y+dy))
        return Neighbors(neighbors)

    def on_click_wrapper(self, coord: Coord):
        return lambda _: solve(Action(type=ActionType.CLEAR, coord=coord))

    def on_right_click_wrapper(self, coord: Coord):
        return lambda _: solve(Action(type=ActionType.FLAG, coord=coord))


@functools.lru_cache(1)
def ms() -> Minesweeper:
    return Minesweeper(window)


def solve_constraint(coord: Coord) -> List[Action]:
    result = []
    if ms().grid(coord).n_adj_mines == 0:
        for c in ms().get_neighbors(coord).filter(lambda n: ms().grid(n).state == State.HIDDEN):
            result.append(Action(type=ActionType.CLEAR, coord=c))
    return result


def solve_variable(coord: Coord) -> List[Action]:
    return []


def do(action: Action) -> bool:
    """Returns true iff the game ends."""
    cell = ms().grid(action.coord)
    if cell.state in (State.CLICKED, State.FLAGGED):
        return False
    
    if action.type == ActionType.CLEAR:
        if cell.is_mine:
            cell.state = State.MISCLICKED
            ms().game_over(won=False)
            return True

        cell.state = State.CLICKED
        # TODO: Move to board_state
        ms().clickedCount += 1

    elif action.type == ActionType.FLAG:
        if not cell.is_mine:
            cell.state = State.MISCLICKED
            ms().game_over(won=False)
            return True

        cell.state = State.FLAGGED
        ms().board_state.n_flags += 1

    else:
        raise NotImplementedError(f"Unknown action type: {action.type}")
    
    return False


def solve(starting_action: Action) -> None:
    """Handles a click, then proceeds to clear as much of the board as it knows how."""
    if ms().board_state.lost:
        return

    actions = [starting_action]
    constraint_solvers = collections.deque()
    variable_solvers = collections.deque()

    while actions or constraint_solvers or variable_solvers:
        game_over = False
        while actions:
            action = actions.pop()
            coord = action.coord
            game_over |= do(action)
            if action.type == ActionType.CLEAR:
                constraint_solvers.append(coord)
                for c in ms().get_neighbors(coord).filter(lambda n: ms().grid(n).state == State.HIDDEN):
                    variable_solvers.append(c)
            if action.type == ActionType.FLAG:
                for c in ms().get_neighbors(coord).filter(lambda n: ms().grid(n).state == State.CLICKED):
                    constraint_solvers.append(c)

        if game_over:
            break

        if constraint_solvers:
            coord = constraint_solvers.popleft()
            actions += solve_constraint(coord)
        elif variable_solvers:
            coord = variable_solvers.popleft()
            actions += solve_variable(coord)      

    if ms().clickedCount == (SIZE_X * SIZE_Y) - N_MINES:
        ms().game_over(True)

    ms().display_update()


if __name__ == "__main__":    
    # create Tk instance
    window = tk.Tk()
    # set program title
    window.title("Minesweeper")
    # create game instance
    _ = ms()
    # run event loop
    window.mainloop()
