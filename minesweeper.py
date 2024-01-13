import collections
import enum
import itertools
import platform
import random
import tkinter as tk
from tkinter import messagebox
from typing import Iterator

import attr


SIZE_X = 16
SIZE_Y = 30
N_MINES = 99

BTN_CLICK = "<Button-1>"
BTN_FLAG = "<Button-2>" if platform.system() == 'Darwin' else "<Button-3>"

window = None


class State(enum.Enum):
    DEFAULT = 0
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
    button: tk.Button = attr.ib()
    is_mine: bool = attr.ib(default=False)
    state: State = attr.ib(default=State.DEFAULT)
    mines: int = attr.ib(default=0)


class Minesweeper(object):
    def __init__(self, tk_obj):

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
                tk.PhotoImage(file="images/tile_"+str(i)+".gif"))

        # set up frame
        self.tk = tk_obj
        self.frame = tk.Frame(self.tk)
        self.frame.pack()

        # set up labels/UI
        self.labels = {
            "mines": tk.Label(self.frame, text="Mines: 0"),
            "flags": tk.Label(self.frame, text="Flags: 0")
        }
        self.labels["mines"].grid(
            row=SIZE_X+1, column=0, columnspan=int(SIZE_Y/2))  # bottom left
        self.labels["flags"].grid(
            row=SIZE_X+1, column=int(SIZE_Y/2)-1, columnspan=int(SIZE_Y/2))  # bottom right

        # create buttons
        self.tiles = dict()
        self.mines = N_MINES
        for coord in grid_coords():
            tile = Cell(
                coord=coord,
                button=tk.Button(self.frame, image=self.images["plain"]),
            )
            tile.button.bind(BTN_CLICK, self.on_click_wrapper(coord))
            tile.button.bind(BTN_FLAG, self.on_right_click_wrapper(coord))
            tile.button.grid(row=coord.x, column=coord.y)
            self.tiles[coord] = tile

        self.restart()  # start game

    def restart(self):
        # reset flag and clicked tile variables
        self.flagCount = 0
        self.correctFlagCount = 0
        self.clickedCount = 0

        # Draw as unclicked
        for coord in grid_coords():
            tile = self.tiles[coord]
            tile.button.config(image=self.images["plain"])
            tile.is_mine = False
            tile.state = State.DEFAULT
            tile.mines = 0

        # Assign mines now
        for coord in random.sample(list(grid_coords()), N_MINES):
            self.tiles[coord].is_mine = True

        # loop again to find nearby mines and display number on tile
        for coord in grid_coords():
            mc = 0
            for n in self.get_neighbors(coord):
                mc += 1 if n.is_mine else 0
            self.tiles[coord].mines = mc

        self.refresh_labels()

    def refresh_labels(self):
        self.labels["flags"].config(text="Flags: "+str(self.flagCount))
        self.labels["mines"].config(text="Mines: "+str(self.mines))

    def game_over(self, won):
        for coord in grid_coords():
            if self.tiles[coord].is_mine == False and self.tiles[coord].state == State.FLAGGED:
                self.tiles[coord].button.config(
                    image=self.images["wrong"])
            if self.tiles[coord].is_mine == True and self.tiles[coord].state != State.FLAGGED:
                self.tiles[coord].button.config(
                    image=self.images["mine"])

        self.tk.update()

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
                neighbors.append(self.tiles[coord])
            except KeyError:
                pass
        return neighbors

    def on_click_wrapper(self, coord: Coord):
        return lambda _: self.on_click(self.tiles[coord])

    def on_right_click_wrapper(self, coord: Coord):
        return lambda _: self.on_right_click(self.tiles[coord])

    def on_click(self, tile):
        if tile.is_mine == True:
            # end game
            self.game_over(False)
            return

        # change image
        tile.button.config(image=self.images["numbers"][tile.mines])
        if tile.mines == 0:
            self.clear_surrounding_tiles(tile.coord)
        # if not already set as clicked, change state and count
        if tile.state != State.CLICKED:
            tile.state = State.CLICKED
            self.clickedCount += 1
        if self.clickedCount == (SIZE_X * SIZE_Y) - self.mines:
            self.game_over(True)

    def on_right_click(self, tile):
        # if not clicked
        if tile.state == State.DEFAULT:
            tile.button.config(image=self.images["flag"])
            tile.state = State.FLAGGED
            tile.button.unbind(BTN_CLICK)
            # if a mine
            if tile.is_mine == True:
                self.correctFlagCount += 1
            self.flagCount += 1
            self.refresh_labels()
        # if flagged, unflag
        elif tile.state == 2:
            tile.button.config(image=self.images["plain"])
            tile.state = 0
            tile.button.bind(BTN_CLICK, self.on_click_wrapper(
                tile.coord.x, tile.coord.y))
            # if a mine
            if tile.is_mine == True:
                self.correctFlagCount -= 1
            self.flagCount -= 1
            self.refresh_labels()

    def clear_surrounding_tiles(self, coord: Coord):
        queue = collections.deque([coord])

        while len(queue) != 0:
            coord = queue.popleft()

            for tile in self.get_neighbors(coord):
                self.clear_tile(tile, queue)

    def clear_tile(self, tile, queue):
        if tile.state != State.DEFAULT:
            return

        tile.button.config(image=self.images["numbers"][tile.mines])
        if tile.mines == 0:
            queue.append(tile.coord)

        tile.state = State.CLICKED
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
