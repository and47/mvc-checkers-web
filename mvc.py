from engine import Board
from web import run_local_webserver
from typing import Callable
from time import sleep, time


class CheckersController:

    def __init__(self, game_settings = None, game_model: 'Board' = Board, ux: 'View' | Callable = run_local_webserver):
        self.game_model = game_model()
        ux_server = ux(board_info=self.game_model.as_list())  # View and User inputs
        self.server, self.server_thread, self.ux_state = ux_server
        self.players_moves = self.ux_state.moves
        self.board_view = self.ux_state.board

    def start_game(self, bot_strategy: Callable | None = None):

        game, moves = self.game_model, self.players_moves  # shorten names
        get_move = self.get_user_move if bot_strategy is None else self._feed(bot_strategy)
        starting_time = time()

        while not game.game_over:  # make a generator loop?
            try:
                move = get_move()
                if move:
                    square_rowcol = move
                    affected_cells = game.action(square_rowcol=square_rowcol)
                    if affected_cells:  # universal engine, in other games may be used, in minesweeper always True
                        self.ux_state.update_board(game.as_list())
                        # print(self.board_view)
                        # print(game)
                # view.clock = time() - starting_time  # display time passed for the player
            except KeyboardInterrupt:
                print("Shutting down server...")
                self.server.should_exit = True
                self.server_thread.join()
                print("Server shut down.")
            except Exception as e:
                import traceback
                self.server.should_exit = True
                self.server_thread.join()
                print(f"An error occurred: {e}")
                traceback.print_exc()

        self.ux_state.update_board([[game.winner]])  # show winner top-left
        return

    def _feed(self, bot_strategy: Callable) -> Callable:
        pass

    def get_user_move(self) -> tuple[int, int] | None:
        """Checks for and returns a valid user input (i.e. change in a cell on the grid/minefield range)"""
        try:
            sleep(0.1)  # poll user (not bot) "move" every second
            if self.players_moves:
                move = self.players_moves.pop()
                move = move.r, move.c
            else:
                move = None
            return move
        except Exception as e:
            raise
