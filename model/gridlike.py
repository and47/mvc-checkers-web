import numpy as np
from string import ascii_uppercase
from itertools import product, cycle
from collections import defaultdict
from enum import Enum


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

    def get_diags_neighbors(self, coord: tuple[int, int]) -> set[tuple[int, int]]:
        moves = {-1, 1}  # can only move diagonally (4 pairs with -1 or 1)
        neighbors00 = set(product(moves, repeat=2))  # row=0, col=0
        neighbors_of_coord = {(r + coord[0], c + coord[1]) for (r, c) in neighbors00}  # offsets
        valid_neighbors_of_coord = {(r, c) for (r, c) in neighbors_of_coord if (0 <= c < self.w and 0 <= r < self.h)}
        return valid_neighbors_of_coord


class Board(Grid):
    intmap = {
        'empty_dark':  0,
        'empty_light': 9,
        'p1': 1,  # uncrowned piece (man)
        'p2': 2,
        'p1c': 3,  # crowned piece (king)
        'p2c': 4,
        'selected': [5, 6, 7, 8]
    }
    actmap = {
        'select': lambda v: v+4 if v < min(Board.intmap['selected']) else v,
        'unselect': lambda v: v-4 if v >= min(Board.intmap['selected']) else v,
        'unselect_all': lambda v: v-4,
        'crown': lambda v: v+2 if v not in {3, 4, 7, 8} else v,
    }
    ownermap = {
        1: [1, 3, 5, 7],
        2: [2, 4, 6, 8],
    }
    enemymap = {
        1: [2, 4],
        2: [1, 3],
    }
    charmap = {
        0: ' ',  # dark
        1: 'o',
        2: '*',
        3: 'O',
        4: '\u26AB',
        5: '',
        6: '',
        7: '',
        8: '',
        # 9: f'\N{middle dot}',  # white
        # 9: f'\u25A0',  # white
        9: f'\u25AF',  # white
    }
    charmap1 = {
        0: '\u25A0',  # dark
        1: '\u25D8',
        2: '\u25D9',
        3: 'O',
        4: '\u26AB',
        5: '',
        6: '',
        7: '',
        8: '',
        9: f'\u25A1',  # white
    }

    def __init__(self, w: int = 8, h: int = 8, test_board: np.ndarray | None = None):
        if test_board is None:
            super().__init__(w=w, h=h)
            filled = np.full(self.dims, fill_value=Board.intmap['empty_light'])

            for c in self.rc_coordinates.flatten():
                if sum(c) % 2:  # every second (vertically, horizontally) square is dark (checkerboard):
                    filled[c] = Board.intmap['empty_dark']

            self.checkerboard = self.complete_init_placement(checkerboard=filled)
        else:
            super().__init__(*test_board.shape[::-1])
            self.checkerboard = test_board
        self.game_over_winner = False
        self.enemies_to_remove = set()
        self.restricted_selection = False  # if just jumped (captured), Player needs to continue with same piece
        self.selection_piece_rc = None
        self.players = cycle((Board.intmap['p1'], Board.intmap['p2']))
        self.current_player = self.switch_current_player()
        self.allowed_destinations = set()

    def switch_current_player(self) -> int:
        return next(self.players)

    @classmethod
    def complete_init_placement(cls, checkerboard: np.ndarray, init_rules: str = 'classic') -> np.ndarray:
        h = checkerboard.shape[0]
        mid = [h // 2]
        if h % 2 == 0:
            mid.append(mid[0] - 1)
        if init_rules == 'classic':
            for rc in zip(*np.where(checkerboard[:min(mid)] == Board.intmap['empty_dark'])):
                checkerboard[rc] = Board.intmap['p2']
            for rc_bottom in zip(*np.where(checkerboard[max(mid)+1:] == Board.intmap['empty_dark'])):
                checkerboard[max(mid)+1:][rc_bottom] = Board.intmap['p1']
        return checkerboard

    def __str__(self):
        indent = '  '
        top_panel = list(ascii_uppercase[:self.w])
        pretty_grid = np.fromiter(Board.charmap.values(), dtype=object)[self.checkerboard]
        out = ['', indent + '   ' + ' '.join(top_panel), indent + ' ' + ''.join(['--' for _ in top_panel]) + '--']
        for r in range(self.h):
            out.append(f'{self.h - r: <2}' + '|' + indent + ' '.join(pretty_grid[r, :]))
        return '\n'.join(out)

    def as_list(self) -> list[list]:
        return [[int(rc) for rc in r] for r in self.checkerboard]

    def action(self, square_rowcol: tuple[int, int]) -> bool:
        square_val = self.checkerboard[square_rowcol]
        by_player = self.current_player
        avail_pieces = Board.ownermap[by_player]

        if self.restricted_selection:  # another jump is required to continue/finish current move
            if square_rowcol in self.allowed_destinations:
                self._make_move(to=square_rowcol)
                return True
        elif square_val == Board.intmap['empty_dark'] and \
                np.isin(self.checkerboard, Board.intmap['selected']).any():
            # new selection, now expecting 'move' and processing it here, updating allowed_destinations:
            self._allowed_moves()
            if square_rowcol in self.allowed_destinations:
                self._make_move(to=square_rowcol)
                return True
        elif square_val in avail_pieces:
            # expect new piece selection; player can still change it before the move
            if threatening_pieces := self._can_attack(by_player):  # if any of player's pieces can attack
                if square_rowcol not in threatening_pieces:
                    return False  # player is required to select an attacking piece
            self._clear_selection()  # clear any existing selection
            self.selection_piece_rc = square_val, square_rowcol
            self.checkerboard[square_rowcol] = Board.actmap['select'](square_val)
            return True
        return False  # invalid action, thus nothing to draw/refresh in UI

    def _clear_selection(self):
        self.checkerboard = np.where(
            np.isin(self.checkerboard, Board.intmap['selected']),
                 Board.actmap['unselect_all'](self.checkerboard), self.checkerboard)

    def _can_attack(self, player) -> set[tuple[int, int]]:
        threatening = set()
        own_pieces_coords = self.rc_coordinates[np.isin(self.checkerboard, Board.ownermap[player])]
        for rowcol in own_pieces_coords:
            self._allowed_moves(jump_only=True, piece_val=self.checkerboard[rowcol], piece_rc=rowcol)
            if self.allowed_destinations:
                threatening.add(rowcol)
        return threatening

    def _can_move(self, player) -> bool:
        own_pieces_coords = self.rc_coordinates[np.isin(self.checkerboard, Board.ownermap[player])]
        for rowcol in own_pieces_coords:
            self._allowed_moves(piece_val=self.checkerboard[rowcol], piece_rc=rowcol)
            if self.allowed_destinations:
                return True
        return False

    def _allowed_moves(self, jump_only: bool = False, enemies_already_jumped_over: set[tuple[int, int]] = set(),
                       piece_val: int | None = None, piece_rc: tuple[int, int] | None = None):
        if piece_val is None and piece_rc is None:
            piece_val, piece_rc = self.selection_piece_rc  # piece_val is type+owner coded as int
        piece_val = Board.actmap['unselect'](piece_val)  # removes selection info
        crowned = self._is_crowned(piece_val)
        enemy_man_king = Board.enemymap[self.current_player]
        self.enemy_encountered = defaultdict(list)
        self.allowed_destinations = set()

        if crowned:
            dirs = product({-1, 1}, repeat=2)
            for dr, dc in dirs:
                ri, ci = r, c = piece_rc
                enemies_this_direction = set()
                enemy_encountered_last = False
                while True:  # traversing one of 4 directions
                    new_rc = ri, ci = ri + dr, ci + dc
                    # if (0 > ri >= self.h) or (0 > ci >= self.w) or \
                    if new_rc not in self.set_rc_coordinates or \
                        self.checkerboard[new_rc] in Board.ownermap[self.current_player]:  # own piece or out of board
                        break
                    elif self.checkerboard[new_rc] in enemy_man_king:
                        if enemy_encountered_last or new_rc in enemies_already_jumped_over:
                            break  # second enemy piece in a row or already jumped over piece
                        enemy_encountered_last = True
                        enemies_this_direction.add(new_rc)
                    else:  # empty black
                        self.enemy_encountered[new_rc].extend(enemies_this_direction)
                        if enemy_encountered_last:
                            if not jump_only:
                                # can capture, therefore require it (but allow other capture paths):
                                self._allowed_moves(jump_only=True, piece_val=piece_val, piece_rc=piece_rc)
                                return
                        if jump_only:
                            if enemies_this_direction:
                                self.allowed_destinations.add(new_rc)
                        else:
                            self.allowed_destinations.add(new_rc)
                        enemy_encountered_last = False
        else:
            nearbies = self.get_diags_neighbors(piece_rc)  # checks also for opportunities to attack backward (not in English/American rules)
            enemies_nearby = {rc for rc in nearbies if (self.checkerboard[rc] in enemy_man_king) and
                              (rc not in enemies_already_jumped_over)}  # only on 2nd+ (cont.) jump
            if not jump_only:
                fronts = self._get_forward_dirs(origin=piece_rc, destinations=nearbies)
                empty_fronts = {rc for rc in fronts if self.checkerboard[rc] == Board.intmap['empty_dark']}
                self.allowed_destinations.update(empty_fronts)
                # enemies_nearby = {rc for rc in fronts if (self.checkerboard[rc] in enemy_man_king)}  # for English draughts
            for enemy_rc in enemies_nearby:
                _jump_dir = enemy_rc[0] - piece_rc[0], enemy_rc[1] - piece_rc[1]
                jump_sq = enemy_rc[0] + _jump_dir[0], enemy_rc[1] + _jump_dir[1]
                if jump_sq in self.set_rc_coordinates and self.checkerboard[jump_sq] == Board.intmap['empty_dark']:
                    if not jump_only:  # USSR checkers rule
                        # can capture, therefore require it (but allow any other capture paths too):
                        self._allowed_moves(jump_only=True, piece_val=piece_val, piece_rc=piece_rc)
                        return
                    self.allowed_destinations.add(jump_sq)
                    # print(f"{enemies_nearby=}")
                    # print(f"{jump_sq=}")
                    self.enemy_encountered[jump_sq].append(enemy_rc)

    def _make_move(self, to: tuple[int, int]):
        piece_val, piece_rc = self.selection_piece_rc  # piece's type+player and rowcol coords
        if self._reaches_finish_line(to=to) and not self._is_crowned(piece_val):
            piece_val = Board.actmap['crown'](piece_val)  # promotes piece
            self.checkerboard[piece_rc] = Board.actmap['crown'](self.checkerboard[piece_rc])  # promote "selection" too

        current_selection = self.checkerboard[piece_rc]  # save for if move continues (more jumps)
        self.checkerboard[piece_rc] = Board.intmap['empty_dark']  # or use self._clear_selection() ?
        self.selection_piece_rc = piece_val, to
        if self.enemy_encountered[to]:
            jumped_over_enemies_coords = self.enemy_encountered[to]
            self.enemies_to_remove.update(jumped_over_enemies_coords)
            self._allowed_moves(jump_only=True, enemies_already_jumped_over=self.enemies_to_remove)
            # enemies remain to jump over, expect player to perform those jumps with that piece (can be multiple paths):
            if self.allowed_destinations:
                self.restricted_selection = True  # same player continues (can capture at least 1 more enemy with the piece)
                self.checkerboard[to] = current_selection  # move selection to where jumped
                return
        self.checkerboard[to] = piece_val  # is after "return" to keep same piece selected: hints player to continue (jump) with it
        self._finish_move()

    def _finish_move(self):
        old_player = self.current_player
        new_player = self.current_player = self.switch_current_player()
        if self.enemies_to_remove:
            self._remove_enemies()
            self.enemies_to_remove.clear()
            if not self._any_pieces_left(new_player):
                self.declare_winner(old_player)
        self.allowed_destinations.clear()
        self.selection_piece_rc = None
        self.restricted_selection = False
        if not self._can_move(new_player):
            self.declare_winner(old_player)

    def _remove_enemies(self):
        for enemy_rc in self.enemies_to_remove:
            self.checkerboard[enemy_rc] = Board.intmap['empty_dark']

    def _any_pieces_left(self, player: int) -> bool:
        return np.isin(self.checkerboard, Board.ownermap[player]).any()  # victory check (any enemies)

    def declare_winner(self, player: int):
        self.game_over_winner = Board.actmap['crown'](player)

    def _is_crowned(self, piece_val: int) -> bool:  # should be unselected piece
        return bool(piece_val - (self.current_player - 1) - 1)  # NB. P2 has +1 to val, crown adds +2, selection +4

    def _reaches_finish_line(self, to: tuple[int, int]) -> bool:
        return (to[0] == 0 and self.current_player == 1) or (to[0] == self.h - 1 and self.current_player == 2)

    def _get_forward_dirs(self, origin: tuple[int, int], destinations: set[tuple[int, int]]) -> set[tuple[int, int]]:
        # p1's rows decreasing, p2's increasing
        rcs = {rc for rc in destinations if (rc[0] < origin[0] and self.current_player == 1) or
                                             (rc[0] > origin[0] and self.current_player == 2)}
        return rcs
