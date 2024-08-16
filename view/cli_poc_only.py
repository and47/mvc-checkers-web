from model.engine import GameRound
from model.gridlike import PieceChar, Owner
from string import digits, ascii_uppercase
from collections import namedtuple
from time import sleep
import os


class CheckersCLI:
    rc_coords_named = namedtuple('rowcol', ['r', 'c'])
    n_letters = len(ascii_uppercase)

    def __init__(self, board_info: GameRound):
        self.board = board_info.board
        self.moves = []

    @classmethod
    def use_as_ux(cls, board_info: GameRound) -> tuple:
        server = None
        daemon_thread = None
        cli = cls(board_info=board_info)
        return server, daemon_thread, cli

    @staticmethod
    def show_winner(winner: int):
        print(f"Winner {Owner(winner).name}: {PieceChar.get_char(winner)}")

    def update_board(self, updated_board: GameRound):
        os.system('cls||clear')
        print(updated_board.board)
        player_symbol = PieceChar.get_char(updated_board.current_player)
        if (piece_rc := updated_board.state.selection_piece_rc) is None:
            print(f"Enter a square to select a piece e.g. A1, player: {player_symbol}:")
        else:
            print(f"Enter a square to the move piece from {self.rc_to_chess_coord(piece_rc)} to destination" +
                  f" (or select a new piece), player {player_symbol}:")
        while not updated_board.over:
            board_colrow_user_str = input()
            sleep(0.1)  # poll user (not bot) "selection" every second
            if board_colrow_user_str:
                rowcol = self.parse_chess_str_as_coord_rc(board_colrow_user_str)
                if rowcol in self.board.set_rc_coordinates:
                    self.moves.append(CheckersCLI.rc_coords_named(*rowcol))
                    break

    def parse_chess_str_as_coord_rc(self, s: str) -> tuple[int, int]:
        s = s.upper()  # to-do: validate user input, also could be put into Board class
        col = s.rstrip(digits)
        row = s[len(col):]
        row_int = self.board.h - int(row)  # upside-down compared to numpy ndarray
        col_int = CheckersCLI.n_letters * (len(col) - 1)  # to handle e.g. AB column on > 26x26 board
        for letter in col:
            col_int += ascii_uppercase.index(letter)
        return row_int, col_int

    def rc_to_chess_coord(self, rowcol: tuple[int, int]) -> str:
        row = self.board.h - rowcol[0]
        col = rowcol[1]
        decimal_number, remainder = divmod(col, CheckersCLI.n_letters)
        chars = [ascii_uppercase[remainder]]
        while decimal_number > 0:
            decimal_number -= 1  # 0-based for new starting to be 'A' not 'B'
            decimal_number, remainder = divmod(decimal_number, CheckersCLI.n_letters)
            chars.insert(0, ascii_uppercase[remainder])

        return ''.join(chars) + str(row)
