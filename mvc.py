from view.web import run_local_webserver
from model.engine import GameRound
from typing import Callable
from time import sleep
import sys


class CheckersController:

    def __init__(self, game_settings: dict | None = None, game_model: 'GameRound' = GameRound,
                 ux: 'View' | Callable = run_local_webserver):
        self.game_model = game_model() if game_settings is None else game_model(**game_settings)
        ux_server = ux(board_info=self.game_model)  # View and User inputs
        self.server, self.server_thread, self.ux_state = ux_server
        self.player_clicks = self.ux_state.moves
        self.board_view = self.ux_state.board

    def start_game(self, bot_strategy: Callable | None = None):
        game = self.game_model
        self.ux_state.update_board(game)
        get_action = self.get_user_click if bot_strategy is None else self._feed(bot_strategy)

        while not game.over:  # make a generator loop?
            try:
                input_action = get_action()
                if square_rowcol := input_action:
                    ui_updates = game.action(square_rowcol=square_rowcol)
                    if (ui_updates and ui_updates.pop()) or self.server is None:
                        self.ux_state.update_board(game)
            except KeyboardInterrupt:
                print("Shutting down server...")
                self.server.should_exit = True
                self.server_thread.join()
                print("Server shut down. Killing PID")
                sys.exit(4)
            except Exception as e:
                import traceback
                self.server.should_exit = True
                self.server_thread.join()
                print(f"An error occurred: {e}")
                traceback.print_exc()
                sys.exit(4)

        self.ux_state.show_winner(game.over)  # show winner top-left
        return

    def _feed(self, bot_strategy: Callable) -> Callable:
        pass

    def get_user_click(self) -> tuple[int, int] | None:
        """Checks for and returns a valid user input (i.e. click of a cell on the grid/board)"""
        try:
            sleep(0.1)  # poll user (not bot) "selection" every second
            if self.player_clicks:
                board_square = self.player_clicks.pop()
                rowcol = board_square.r, board_square.c
            else:
                rowcol = None
            return rowcol
        except Exception as e:
            raise
