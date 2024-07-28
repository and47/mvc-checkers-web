from model.engine import GameRound
from view.web import run_local_webserver
from view.cli_poc_only import Checkers_CLI
from mvc import CheckersController


def run_testcase_4x4():
    """Example of a game situation (e.g. continuing existing/saved one or a hypothetical custom game)"""
    import numpy as np
    from model.gridlike import Board

    case = np.array(
        [
            [3, 9, 0, 9],  # 0 and 9 for black and white squares.  3 is P1's "king piece"
            [9, 0, 9, 2],  # 1 is P1's piece
            [0, 9, 1, 9],  # 2 is P2's piece
            [9, 0, 9, 0]
        ]
    )
    case_board = Board(test_board=case)
    # print(case_board)

    move_by = 2  # P1 or P2 (here)
    continued_situation = CheckersController(game_settings={'board': case_board,
                                                            'current_player': move_by},
                                             # ux=Checkers_CLI.use_as_ux  # defaults to webui
                                             )
    continued_situation.start_game()


def run_8x8_cli():
    launched_cli_instance = CheckersController(game_model=GameRound, ux=Checkers_CLI.use_as_ux)
    launched_cli_instance.start_game()


if __name__ == "__main__":
    # run_8x8_cli()
    launched_instance = CheckersController(game_model=GameRound, ux=run_local_webserver)
    launched_instance.start_game()
    # run_testcase_4x4()
