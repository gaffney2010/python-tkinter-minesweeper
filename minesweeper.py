import collections
from datetime import datetime
import itertools
import platform
import random
import tkinter as tk
from tkinter import messagebox


SIZE_X = 16
SIZE_Y = 30
N_MINES = 99

STATE_DEFAULT = 0
STATE_CLICKED = 1
STATE_FLAGGED = 2

BTN_CLICK = "<Button-1>"
BTN_FLAG = "<Button-2>" if platform.system() == 'Darwin' else "<Button-3>"

window = None


class Minesweeper(object):
    def __init__(self, tk_obj):

        # import images
        self.images = {
            "plain": tk.PhotoImage(file="images/tile_plain.gif"),
            "clicked": tk.PhotoImage(file="images/tile_clicked.gif"),
            "mine": tk.PhotoImage(file="images/tile_mine.gif"),
            "flag": tk.PhotoImage(file="images/tile_flag.gif"),
            "wrong": tk.PhotoImage(file="images/tile_wrong.gif"),
            "numbers": []
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
            "time": tk.Label(self.frame, text="00:00:00"),
            "mines": tk.Label(self.frame, text="Mines: 0"),
            "flags": tk.Label(self.frame, text="Flags: 0")
        }
        self.labels["time"].grid(
            row=0, column=0, columnspan=SIZE_Y)  # top full width
        self.labels["mines"].grid(
            row=SIZE_X+1, column=0, columnspan=int(SIZE_Y/2))  # bottom left
        self.labels["flags"].grid(
            row=SIZE_X+1, column=int(SIZE_Y/2)-1, columnspan=int(SIZE_Y/2))  # bottom right

        self.restart()  # start game
        self.updateTimer()  # init timer

    def setup(self):
        # create flag and clicked tile variables
        self.flagCount = 0
        self.correctFlagCount = 0
        self.clickedCount = 0
        self.startTime = None

        # create buttons
        self.tiles = dict({})
        self.mines = N_MINES
        for x in range(0, SIZE_X):
            for y in range(0, SIZE_Y):
                if y == 0:
                    self.tiles[x] = {}

                id = str(x) + "_" + str(y)

                # tile image changeable for debug reasons:
                gfx = self.images["plain"]

                tile = {
                    "id": id,
                    "isMine": False,
                    "state": STATE_DEFAULT,
                    "coords": {
                        "x": x,
                        "y": y
                    },
                    "button": tk.Button(self.frame, image=gfx),
                    "mines": 0  # calculated after grid is built
                }

                tile["button"].bind(BTN_CLICK, self.onClickWrapper(x, y))
                tile["button"].bind(BTN_FLAG, self.onRightClickWrapper(x, y))
                # offset by 1 row for timer
                tile["button"].grid(row=x+1, column=y)

                self.tiles[x][y] = tile

        # Assign mines now
        for x, y in random.sample(list(itertools.product(range(SIZE_X), range(SIZE_Y))), N_MINES):
            self.tiles[x][y]["isMine"] = True

        # loop again to find nearby mines and display number on tile
        for x in range(0, SIZE_X):
            for y in range(0, SIZE_Y):
                mc = 0
                for n in self.getNeighbors(x, y):
                    mc += 1 if n["isMine"] else 0
                self.tiles[x][y]["mines"] = mc

    def restart(self):
        self.setup()
        self.refreshLabels()

    def refreshLabels(self):
        self.labels["flags"].config(text="Flags: "+str(self.flagCount))
        self.labels["mines"].config(text="Mines: "+str(self.mines))

    def gameOver(self, won):
        for x in range(0, SIZE_X):
            for y in range(0, SIZE_Y):
                if self.tiles[x][y]["isMine"] == False and self.tiles[x][y]["state"] == STATE_FLAGGED:
                    self.tiles[x][y]["button"].config(
                        image=self.images["wrong"])
                if self.tiles[x][y]["isMine"] == True and self.tiles[x][y]["state"] != STATE_FLAGGED:
                    self.tiles[x][y]["button"].config(
                        image=self.images["mine"])

        self.tk.update()

        msg = "You Win! Play again?" if won else "You Lose! Play again?"
        res = messagebox.askyesno("Game Over", msg)
        if res:
            self.restart()
        else:
            self.tk.quit()

    def updateTimer(self):
        ts = "00:00:00"
        if self.startTime != None:
            delta = datetime.now() - self.startTime
            ts = str(delta).split('.')[0]  # drop ms
            if delta.total_seconds() < 36000:
                ts = "0" + ts  # zero-pad
        self.labels["time"].config(text=ts)
        self.frame.after(100, self.updateTimer)

    def getNeighbors(self, x, y):
        neighbors = []
        coords = [
            {"x": x-1,  "y": y-1},  # top right
            {"x": x-1,  "y": y},  # top middle
            {"x": x-1,  "y": y+1},  # top left
            {"x": x,    "y": y-1},  # left
            {"x": x,    "y": y+1},  # right
            {"x": x+1,  "y": y-1},  # bottom right
            {"x": x+1,  "y": y},  # bottom middle
            {"x": x+1,  "y": y+1},  # bottom left
        ]
        for n in coords:
            try:
                neighbors.append(self.tiles[n["x"]][n["y"]])
            except KeyError:
                pass
        return neighbors

    def onClickWrapper(self, x, y):
        return lambda _: self.onClick(self.tiles[x][y])

    def onRightClickWrapper(self, x, y):
        return lambda _: self.onRightClick(self.tiles[x][y])

    def onClick(self, tile):
        if self.startTime == None:
            self.startTime = datetime.now()

        if tile["isMine"] == True:
            # end game
            self.gameOver(False)
            return

        # change image
        if tile["mines"] == 0:
            tile["button"].config(image=self.images["clicked"])
            self.clearSurroundingTiles(tile["id"])
        else:
            tile["button"].config(
                image=self.images["numbers"][tile["mines"]-1])
        # if not already set as clicked, change state and count
        if tile["state"] != STATE_CLICKED:
            tile["state"] = STATE_CLICKED
            self.clickedCount += 1
        if self.clickedCount == (SIZE_X * SIZE_Y) - self.mines:
            self.gameOver(True)

    def onRightClick(self, tile):
        if self.startTime == None:
            self.startTime = datetime.now()

        # if not clicked
        if tile["state"] == STATE_DEFAULT:
            tile["button"].config(image=self.images["flag"])
            tile["state"] = STATE_FLAGGED
            tile["button"].unbind(BTN_CLICK)
            # if a mine
            if tile["isMine"] == True:
                self.correctFlagCount += 1
            self.flagCount += 1
            self.refreshLabels()
        # if flagged, unflag
        elif tile["state"] == 2:
            tile["button"].config(image=self.images["plain"])
            tile["state"] = 0
            tile["button"].bind(BTN_CLICK, self.onClickWrapper(
                tile["coords"]["x"], tile["coords"]["y"]))
            # if a mine
            if tile["isMine"] == True:
                self.correctFlagCount -= 1
            self.flagCount -= 1
            self.refreshLabels()

    def clearSurroundingTiles(self, id):
        queue = collections.deque([id])

        while len(queue) != 0:
            key = queue.popleft()
            parts = key.split("_")
            x = int(parts[0])
            y = int(parts[1])

            for tile in self.getNeighbors(x, y):
                self.clearTile(tile, queue)

    def clearTile(self, tile, queue):
        if tile["state"] != STATE_DEFAULT:
            return

        if tile["mines"] == 0:
            tile["button"].config(image=self.images["clicked"])
            queue.append(tile["id"])
        else:
            tile["button"].config(
                image=self.images["numbers"][tile["mines"]-1])

        tile["state"] = STATE_CLICKED
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
