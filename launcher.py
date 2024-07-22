from engine import Board
from web import run_local_webserver
from mvc import CheckersController


def run_testcase():
    import numpy as np

    case = np.array(
        [
            [3, 9, 0, 9],
            [9, 0, 9, 1],
            [0, 9, 2, 9],
            [9, 0, 9, 0]
        ]
    )

    continued_situation = CheckersController(game_settings={'test_board': case})
    continued_situation.start_game()


if __name__ == "__main__":

    launched_instance = CheckersController(game_model=Board, ux=run_local_webserver)
    launched_instance.start_game()
