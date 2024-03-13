import collections
import functools
import itertools
import math
import random
import tkinter as tk
from typing import List, Tuple

from minesweeper_lib import *


window = None


def left_click(coord: Coord):
    return lambda _: solve(Action(type=ActionType.CLEAR, coord=coord))


def right_click(coord: Coord):
    return lambda _: solve(Action(type=ActionType.FLAG, coord=coord))


@functools.lru_cache(1)
def ms() -> Minesweeper:
    display = Display(
        window,
        left_click,
        right_click,
    )
    return Minesweeper(display, list(random.sample(list(grid_coords()), N_MINES)))


def get_variables_constraint(coord: Coord) -> Tuple[List[Coord], int]:
    variables = list(get_neighbors(coord).filter(
        lambda n: ms().grid[n].state == State.HIDDEN))
    showing_num = ms().grid[coord].n_adj_mines
    flagged_mines = len(list(get_neighbors(coord).filter(
        lambda n: ms().grid[n].state == State.FLAGGED)))
    constraint = showing_num - flagged_mines
    return variables, constraint


def solve_constraint(coord: Coord) -> List[Action]:
    variables, constraint = get_variables_constraint(coord)

    if constraint == 0:
        return [Action(type=ActionType.CLEAR, coord=c) for c in variables]

    if constraint == len(variables):
        return [Action(type=ActionType.FLAG, coord=c) for c in variables]

    return []


def powerset(iterable):
    """Recipe from itertools

    powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)
    """
    s = list(iterable)
    return itertools.chain.from_iterable(itertools.combinations(s, r) for r in range(len(s)+1))


def solve_pair_of_constraints(x: Coord, y: Coord) -> List[Action]:
    vx, cx = get_variables_constraint(x)
    vy, cy = get_variables_constraint(y)
    v = list(set(vx) | set(vy))

    # We can make this part more efficient later if we need to
    valid = []
    for s in powerset(v):
        # s represents all the 1s, or mines
        meet_x = len([t for t in vx if t in s]) == cx
        meet_y = len([t for t in vy if t in s]) == cy
        if meet_x and meet_y:
            valid.append(s)

    result = []
    for t in v:
        if all([t in s for s in valid]):
            result.append(Action(type=ActionType.FLAG, coord=t))
        if not any([t in s for s in valid]):
            result.append(Action(type=ActionType.CLEAR, coord=t))

    return result


def solve_variable(coord: Coord) -> List[Action]:
    constraint_neighbors = list(get_neighbors(coord).filter(
        lambda c: ms().grid[c].state == State.CLICKED))

    vcs = [get_variables_constraint(x) for x in constraint_neighbors]
    v_set = set()
    for v, _ in vcs:
        v_set |= set(v)

    # We can make this part more efficient later if we need to
    valid = []
    for s in powerset(v_set):
        # s represents all the 1s, or mines
        for v, c in vcs:
            if len([t for t in v if t in s]) != c:
                break
        else:
            valid.append(s)

    result = []
    for t in v_set:
        if all([t in s for s in valid]):
            result.append(Action(type=ActionType.FLAG, coord=t))
        if not any([t in s for s in valid]):
            result.append(Action(type=ActionType.CLEAR, coord=t))

    return result


def do(action: Action) -> bool:
    """Returns true iff the game ends."""
    cell = ms().grid[action.coord]
    if cell.state in (State.CLICKED, State.FLAGGED):
        return False

    if action.type == ActionType.CLEAR:
        if cell.is_mine:
            cell.state = State.MISCLICKED
            ms().lost = True
            return True

        cell.state = State.CLICKED
        ms().clicked_count += 1

    elif action.type == ActionType.FLAG:
        if not cell.is_mine:
            cell.state = State.MISCLICKED
            ms().lost = True
            return True

        cell.state = State.FLAGGED
        ms().n_flags += 1

    else:
        raise NotImplementedError(f"Unknown action type: {action.type}")

    return False


def my_append(queue, element):
    """Won't append if duplicate"""
    if element in queue:
        return
    queue.append(element)


def calc_prob() -> None:
    all_hidden = list(grid_coords().filter(
        lambda c: ms().grid[c].state == State.HIDDEN))
    all_constraints = [get_variables_constraint(c) for c in grid_coords().filter(
        lambda c: ms().grid[c].state == State.CLICKED)]
    all_constraints = [(set(v), c) for v, c in all_constraints if len(v) > 0]
    all_constraints.sort(key=lambda x: -len(x[0]))
    all_variables = set()
    for x in all_constraints:
        for xi in x[0]:
            all_variables.add(xi)

    out = ms().n_mines - ms().n_flags
    tot = len(all_hidden)
    sz = len(all_variables)
    prob_mines = list()
    for i in range(sz+1):
        prob_mines.append(math.comb(sz, i) * math.comb(tot -
                          sz, out-i) / math.comb(tot, out))

    nums = {c: 0 for c in all_variables}
    den = 0
    while den < N_SIMS:
        n = random.choices(list(range(sz+1)), weights=prob_mines)[0]
        mines = set(random.sample(all_variables, n))
        for v, c in all_constraints:
            if len(mines & v) != c:
                break
        else:
            den += 1
            for c in mines:
                nums[c] += 1
    for c, p in nums.items():
        ms().probs[c] = round(100 * p / den)


def solve(starting_action: Action) -> None:
    """Handles a click, then proceeds to clear as much of the board as it knows how."""
    if ms().lost:
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
                my_append(constraint_solvers, coord)
                for c in get_neighbors(coord).filter(lambda n: ms().grid[n].state == State.CLICKED):
                    my_append(constraint_solvers, c)
                for c in get_neighbors(coord).filter(lambda n: ms().grid[n].state == State.HIDDEN):
                    my_append(variable_solvers, c)
            if action.type == ActionType.FLAG:
                for c in get_neighbors(coord).filter(lambda n: ms().grid[n].state == State.CLICKED):
                    my_append(constraint_solvers, c)

        # ms().display_update()
        # ms().tk.update()
        # time.sleep(2)

        if game_over:
            break

        if constraint_solvers:
            coord = constraint_solvers.popleft()
            actions += solve_constraint(coord)
        elif variable_solvers:
            coord = variable_solvers.popleft()
            actions += solve_variable(coord)

    if ms().clicked_count == (SIZE_X * SIZE_Y) - N_MINES:
        # This is the win condition, but currently we don't do anything.  Sorry.
        pass

    # calc_prob()

    ms().display_update()


if __name__ == "__main__":
    random.seed(100)
    # create Tk instance
    window = tk.Tk()
    # set program title
    window.title("Minesweeper")
    # create game instance
    _ = ms()
    # run event loop
    window.mainloop()
