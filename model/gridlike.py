import numpy as np
from string import ascii_uppercase
from itertools import product
from enum import IntEnum, Enum  # StrEnum since Python 3.11


class Grid:
    def __init__(self, w: int, h: int):
        self.dims = self.h, self.w = h, w
        self.rc_coordinates = self.generate_coords(w, h)  # rc is rowcol
        self.set_rc_coordinates = {c for c in self.rc_coordinates.flatten()}

    @staticmethod
    def generate_coords(w: int, h: int, convention: str = 'numpy') -> np.ndarray:
        """
        From specified width and height create rectangular grid of tuples encoding coordinates in
         order of a vertical and horizontal ones by default.
        NB: regardless of convention used output.flatten()[int_idx] also allows single value indexing.
        """
        dims = (h, w)
        coords = np.fromiter(np.ndindex(dims), dtype=object)
        if convention == 'numpy':
            rowcol_arr = coords.reshape(dims)
            return rowcol_arr
        else:
            if w == h:
                xycoord_arr = coords.reshape(dims, order='F')
            else:
                xycoord_arr = np.fromiter(np.ndindex(dims[::-1]), dtype=object).reshape(dims, order='F')
            return xycoord_arr


class Board(Grid):

    def __init__(self, w: int = 8, h: int = 8, test_board: np.ndarray | None = None):
        if test_board is None:
            super().__init__(w=w, h=h)
            filled = np.full(self.dims, fill_value=PieceType.EMPTY_LIGHT)

            for c in self.rc_coordinates.flatten():
                if sum(c) % 2:  # every second (vertically, horizontally) square is dark (val_arr):
                    filled[c] = PieceType.EMPTY_DARK

            self.val_arr = self.complete_init_placement(checkerboard=filled)
        else:
            super().__init__(*test_board.shape[::-1])
            self.val_arr = test_board  # checkerboard as array (values for pieces or squares)

    def __setitem__(self, key, value):
        if isinstance(key, tuple) and len(key) == 2:
            self.val_arr[key] = value

    def __getitem__(self, key):
        if isinstance(key, tuple) and len(key) == 2:
            return self.val_arr[key]

    @classmethod
    def complete_init_placement(cls, checkerboard: np.ndarray, init_rules: str = 'classic') -> np.ndarray:
        h = checkerboard.shape[0]
        mid = [h // 2]
        if h % 2 == 0:
            mid.append(mid[0] - 1)
        if init_rules == 'classic':
            for rc in zip(*np.where(checkerboard[:min(mid)] == PieceType.EMPTY_DARK)):
                checkerboard[rc] = PieceType.P2
            for rc_bottom in zip(*np.where(checkerboard[max(mid)+1:] == PieceType.EMPTY_DARK)):
                checkerboard[max(mid)+1:][rc_bottom] = PieceType.P1
        return checkerboard

    def __str__(self):
        indent = '  '
        top_panel = list(ascii_uppercase[:self.w])
        pretty_grid = np.fromiter(PieceChar.all_sorted(), dtype=object)[self.val_arr]
        out = ['', indent + '   ' + ' '.join(top_panel), indent + ' ' + ''.join(['--' for _ in top_panel]) + '--']
        for r in range(self.h):
            out.append(f'{self.h - r: <2}' + '|' + indent + ' '.join(pretty_grid[r, :]))
        return '\n'.join(out)

    def remove_enemies(self, enemies_to_remove: set[tuple[int, int]]):
        for enemy_rc in enemies_to_remove:
            self.val_arr[enemy_rc] = PieceType.EMPTY_DARK

    def get_coords_for_all_own_pieces(self, player: int) -> set[tuple[int, int]]:
        return self.rc_coordinates[np.isin(self.val_arr, PieceType.get_owner_pieces(player))]

    def any_pieces_left(self, player: int) -> bool:
        return np.isin(self.val_arr, PieceType.get_owner_pieces(player)).any()  # victory check (any enemies)

    def is_out_of_board_or_own_piece(self, new_rc: tuple[int, int], current_player: int) -> bool:
        return new_rc not in self.set_rc_coordinates or \
               self.val_arr[new_rc] in PieceType.get_owner_pieces(current_player)

    def get_diags_neighbors(self, coord: tuple[int, int]) -> set[tuple[int, int]]:
        neighbors00 = self.get_directions()  # row=0, col=0
        neighbors_of_coord = {(r + coord[0], c + coord[1]) for (r, c) in neighbors00}  # offsets
        valid_neighbors_of_coord = {(r, c) for (r, c) in neighbors_of_coord if
                                    (0 <= c < self.w and 0 <= r < self.h)}
        return valid_neighbors_of_coord

    @staticmethod
    def get_directions():  # can only move diagonally (4 pairs with -1 or 1)
        return product({-1, 1}, repeat=2)

    @staticmethod
    def filter_frontal_squares(origin: tuple[int, int], destinations: set[tuple[int, int]], player: int
                               ) -> set[tuple[int, int]]:  # p1's rows decreasing, p2's increasing
        rcs = {rc for rc in destinations if (rc[0] < origin[0] and player == Owner.P1) or
                                             (rc[0] > origin[0] and player == Owner.P2)}
        return rcs


from enum import IntEnum, Enum

class Owner(IntEnum):
    P1 = 1  # whites start but can switch color here, e.g. P2 playing whites
    P2 = 2

class PieceType(IntEnum):
    EMPTY_DARK = 0
    EMPTY_LIGHT = 9
    P1 = Owner.P1
    P2 = Owner.P2
    P1C = Owner.P1 + 2
    P2C = Owner.P2 + 2
    SELECTED_1 = 5  # not used; selection is now handled in Mediator (GameRound)
    SELECTED_2 = 6
    SELECTED_3 = 7
    SELECTED_4 = 8

    @classmethod
    def select(cls, value):
        return cls(value + 4) if value < cls.SELECTED_1 else value

    @classmethod
    def crown(cls, value):
        return cls(value + 2) if not cls.is_king(value) else value

    @classmethod
    def is_king(cls, value):
        return value in {cls.P1C, cls.P2C, cls.SELECTED_3, cls.SELECTED_4}

    @classmethod
    def get_owner_pieces(cls, owner):
        if owner == Owner.P1:
            return [cls.P1, cls.P1C, cls.SELECTED_1, cls.SELECTED_3]
        elif owner == Owner.P2:
            return [cls.P2, cls.P2C, cls.SELECTED_2, cls.SELECTED_4]

    @classmethod
    def get_enemy_pieces(cls, owner):
        if owner == Owner.P1:
            return [cls.P2, cls.P2C]
        elif owner == Owner.P2:
            return [cls.P1, cls.P1C]


class PieceChar(str, Enum):
    EMPTY_LIGHT = '\u25AE'  # ordering wrt. PieceType doesn't matter with .all_sorted() method
    EMPTY_DARK = ' '
    P1 = '\u25CF'  #'\u26AA'
    P2 = '\u25CB'  #'\u26AB'
    P1C = '\u25B2'
    P2C = '\u25B3'  #'\u26DB'
    SELECTED_1 = SELECTED_2 = SELECTED_3 = SELECTED_4 = ''  # not used; selection is now handled in Mediator (GameRound)


    @classmethod
    def get_char(cls, value):
        return cls[PieceType(value).name].value

    @classmethod
    def all_sorted(cls):
        ordered_types = sorted([i for i in PieceType], key=lambda i: i.value)
        return [cls[j.name].value for j in ordered_types]
