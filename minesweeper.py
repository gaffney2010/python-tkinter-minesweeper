import argparse
import collections
import functools
import itertools
import math
import random
import tkinter as tk
from typing import Callable, List, Tuple

from minesweeper_lib import *
import data_lib


window = None


def click(_, action_type: ActionType, coord: Coord, ms: Minesweeper, display_updater: Callable, board_num: int) -> None:
    solve(Action(type=action_type, coord=coord), ms)
    data_lib.write_board_position(
        board_num=board_num,
        position_hash=data_lib.position_hash(ms),
        value=data_lib.board_position_from_ms(ms),
    )
    display_updater()


def get_variables_constraint(coord: Coord, ms: Minesweeper) -> Tuple[List[Coord], int]:
    variables = list(get_neighbors(coord).filter(
        lambda n: ms.grid[n].state == State.HIDDEN))
    showing_num = ms.grid[coord].n_adj_mines
    flagged_mines = len(list(get_neighbors(coord).filter(
        lambda n: ms.grid[n].state == State.FLAGGED)))
    constraint = showing_num - flagged_mines
    return variables, constraint


def solve_constraint(coord: Coord, ms: Minesweeper) -> List[Action]:
    variables, constraint = get_variables_constraint(coord, ms)

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


def solve_variable(coord: Coord, ms: Minesweeper) -> List[Action]:
    constraint_neighbors = list(get_neighbors(coord).filter(
        lambda c: ms.grid[c].state == State.CLICKED))

    vcs = [get_variables_constraint(x, ms) for x in constraint_neighbors]
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


def do(action: Action, ms: Minesweeper) -> bool:
    """Returns true iff the game ends."""
    cell = ms.grid[action.coord]
    if cell.state in (State.CLICKED, State.FLAGGED):
        return False

    if action.type == ActionType.CLEAR:
        if cell.is_mine:
            cell.state = State.MISCLICKED
            ms.lost = True
            return True

        cell.state = State.CLICKED
        ms.clicked_count += 1

    elif action.type == ActionType.FLAG:
        if not cell.is_mine:
            cell.state = State.MISCLICKED
            ms.lost = True
            return True

        cell.state = State.FLAGGED
        ms.n_flags += 1

    else:
        raise NotImplementedError(f"Unknown action type: {action.type}")

    return False


def my_append(queue, element):
    """Won't append if duplicate"""
    if element in queue:
        return
    queue.append(element)


def calc_prob(ms: Minesweeper) -> None:
    all_hidden = list(grid_coords().filter(
        lambda c: ms.grid[c].state == State.HIDDEN))
    all_constraints = [get_variables_constraint(c, ms) for c in grid_coords().filter(
        lambda c: ms.grid[c].state == State.CLICKED)]
    all_constraints = [(set(v), c) for v, c in all_constraints if len(v) > 0]
    all_constraints.sort(key=lambda x: -len(x[0]))
    all_variables = set()
    for x in all_constraints:
        for xi in x[0]:
            all_variables.add(xi)

    out = ms.n_mines - ms.n_flags
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
    for c, p in nums.items:
        ms.probs[c] = round(100 * p / den)


def solve(starting_action: Action, ms: Minesweeper) -> Minesweeper:
    """Handles a click, then proceeds to clear as much of the board as it knows how."""
    if ms.lost:
        return

    actions = [starting_action]
    constraint_solvers = collections.deque()
    variable_solvers = collections.deque()

    while actions or constraint_solvers or variable_solvers:
        game_over = False
        while actions:
            action = actions.pop()
            coord = action.coord
            game_over |= do(action, ms)
            if action.type == ActionType.CLEAR:
                my_append(constraint_solvers, coord)
                for c in get_neighbors(coord).filter(lambda n: ms.grid[n].state == State.CLICKED):
                    my_append(constraint_solvers, c)
                for c in get_neighbors(coord).filter(lambda n: ms.grid[n].state == State.HIDDEN):
                    my_append(variable_solvers, c)
            if action.type == ActionType.FLAG:
                for c in get_neighbors(coord).filter(lambda n: ms.grid[n].state == State.CLICKED):
                    my_append(constraint_solvers, c)

        # ms.tk.update()
        # time.sleep(2)

        if game_over:
            break

        if constraint_solvers:
            coord = constraint_solvers.popleft()
            actions += solve_constraint(coord, ms)
        elif variable_solvers:
            coord = variable_solvers.popleft()
            actions += solve_variable(coord, ms)

    if ms.clicked_count == (SIZE_X * SIZE_Y) - N_MINES:
        # This is the win condition, but currently we don't do anything.  Sorry.
        pass

    # calc_prob(ms)

    return ms


if __name__ == "__main__":
    data_lib.make_tables()

    parser = argparse.ArgumentParser()
    parser.add_argument('--board_num')
    args = vars(parser.parse_args())
    board_num = args["board_num"]

    bv = data_lib.read_board(board_num)
    if not bv:
        bv = data_lib.BoardValue(
            mines=list(random.sample(list(grid_coords()), N_MINES)),
        )
        data_lib.write_board(board_num, bv)

    # create Tk instance
    window = tk.Tk()
    # set program title
    window.title("Minesweeper")

    ms = Minesweeper(bv.mines)
    _ = Display(
        window,
        ms,
        functools.partial(click, action_type=ActionType.CLEAR, board_num=board_num),
        functools.partial(click, action_type=ActionType.FLAG, board_num=board_num),
    )

    # run event loop
    window.mainloop()
