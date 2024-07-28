import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from model.gridlike import Board, PieceType, Owner
from itertools import cycle
from functools import partial
from typing import Container, Iterable  #, Self  # later python versions, tested on 3.10
from collections import defaultdict


game_over = IntEnum('winner', ['unknown', 'p1', 'p2'], start=0)


@dataclass
class GameRound:
    state: 'GameState' = field(init=False)
    board: Board = field(default_factory=Board)
    over: game_over = game_over.unknown
    players: Iterable[int] = Owner
    current_player: int = Owner.P1  # change starting player
    view_update_signals: list[bool] = field(default_factory=list)  # alt. True/False

    def __post_init__(self):
        self.players = cycle(self.players)

        if self.current_player not in self.players:
            raise ValueError(f"Current player {self.current_player} is not in the list of players.")

        for player in self.players:
            if player == self.current_player:
                break

        self.state = SelectingPiece(context=self)

    def action(self, square_rowcol: tuple[int, int]) -> list[bool]:
        self.state = self.state.action(square_rowcol=square_rowcol)
        return self.view_update_signals

    def switch_current_player(self) -> int:
        self.current_player = next(self.players)
        return self.current_player

    def declare_winner(self, player: int):
        self.over = player  # game over and winner
        self.current_player = PieceType.crown(player)

    def boardview_aslist(self) -> list[list[int]]:
        """in each row, each column value as int (not np.int) for JS + optional selection 'overlay'"""
        return [ [int(v) if (r, col) != self.state.selection_piece_rc else PieceType.select(v)
                  for col, v in enumerate(rowvals)] for r, rowvals in enumerate(self.board.val_arr) ]


@dataclass
class GameState(ABC):
    context: GameRound  # current_game
    selection_piece_rc: tuple[int, int] | None = None
    selection_piece_value: int | None = None
    avail_pieces: list[int] = field(init=False)
    allowed_destinations: set = field(init=False)
    enemies_encountered: defaultdict = field(default_factory=partial(defaultdict, list))

    def __post_init__(self):
        self.avail_pieces = PieceType.get_owner_pieces(self.context.current_player)

    @abstractmethod
    def action(self, square_rowcol: tuple[int, int]) -> 'GameState':
        pass

    def got_destination(self, square_val: int) -> bool:
        return square_val == PieceType.EMPTY_DARK and \
            self.selection_piece_rc is not None

    def allowed_moves(self, piece_val: int, piece_rc: tuple[int, int], jump_only: bool = False,
                      enemies_already_jumped_over: Container[tuple[int, int]] = frozenset()):
        self.enemies_encountered = defaultdict(list)
        self.allowed_destinations = set()
        self._update_allowed_moves(piece_val, piece_rc, jump_only, enemies_already_jumped_over)

    def _update_allowed_moves(self, piece_val: int, piece_rc: tuple[int, int], jump_only: bool,
                              enemies_already_jumped_over: Container[tuple[int, int]]):
        if PieceType.is_king(piece_val):  # is crowned piece
            self._handle_king_moves(piece_val, piece_rc, jump_only, enemies_already_jumped_over)
        else:
            self._handle_non_king_moves(piece_val, piece_rc, jump_only, enemies_already_jumped_over)

    def _handle_non_king_moves(self, piece_val: int, piece_rc: tuple[int, int], jump_only: bool,
                               enemies_already_jumped_over: Container[tuple[int, int]]):
        enemy_man_king = PieceType.get_enemy_pieces(self.context.current_player)
        nearbies = self.context.board.get_diags_neighbors(piece_rc)
        enemies_nearby = {rc for rc in nearbies if (self.context.board[rc] in enemy_man_king) and
                          (rc not in enemies_already_jumped_over)}

        if not jump_only:
            fronts = Board.filter_frontal_squares(origin=piece_rc, destinations=nearbies,
                                                  player=self.context.current_player)
            empty_fronts = {rc for rc in fronts if self.context.board[rc] == PieceType.EMPTY_DARK}
            self.allowed_destinations.update(empty_fronts)

        for enemy_rc in enemies_nearby:
            _jump_dir = enemy_rc[0] - piece_rc[0], enemy_rc[1] - piece_rc[1]
            jump_sq = enemy_rc[0] + _jump_dir[0], enemy_rc[1] + _jump_dir[1]

            if jump_sq in self.context.board.set_rc_coordinates and \
                    self.context.board[jump_sq] == PieceType.EMPTY_DARK:
                if not jump_only:
                    self.allowed_moves(jump_only=True, piece_val=piece_val, piece_rc=piece_rc)
                    return
                self.allowed_destinations.add(jump_sq)
                self.enemies_encountered[jump_sq].append(enemy_rc)

    def _handle_king_moves(self, piece_val: int, piece_rc: tuple[int, int], jump_only: bool,
                           enemies_already_jumped_over: Container[tuple[int, int]]):
        dirs = Board.get_directions()
        enemy_man_king = PieceType.get_enemy_pieces(self.context.current_player)
    
        for dr, dc in dirs:
            ri, ci = r, c = piece_rc
            enemies_this_direction = set()
            enemy_encountered_last = False
    
            while True:  # traversing one of 4 directions
                new_rc = ri, ci = ri + dr, ci + dc
                if self.context.board.is_out_of_board_or_own_piece(new_rc, self.context.current_player):
                    break
                elif self.context.board[new_rc] in enemy_man_king:
                    if enemy_encountered_last or new_rc in enemies_already_jumped_over:
                        break  # second enemy piece in a row or already jumped over piece
                    enemy_encountered_last = True
                    enemies_this_direction.add(new_rc)
                else:  # empty dark square
                    self.enemies_encountered[new_rc].extend(enemies_this_direction)
                    if enemy_encountered_last:
                        if not jump_only:
                            self.allowed_moves(jump_only=True, piece_val=piece_val, piece_rc=piece_rc)
                            return
                    if jump_only:
                        if enemies_this_direction:
                            self.allowed_destinations.add(new_rc)
                    else:
                        self.allowed_destinations.add(new_rc)
                    enemy_encountered_last = False


@dataclass
class SelectingPiece(GameState):

    def action(self, square_rowcol: tuple[int, int]) -> 'GameState':
        square_val = self.context.board[square_rowcol]

        if square_val in self.avail_pieces:  # (new) piece selection; player can still change it before the move
            if threatening_pieces := self.player_attacking_pieces():  # if any of player's pieces can attack
                if square_rowcol not in threatening_pieces:
                    return self  # state unchanged, player is required to select an attacking piece
            self.selection_piece_value, self.selection_piece_rc = square_val, square_rowcol  # valid piece choice to show
            self.context.view_update_signals.append(True)
        elif self.got_destination(square_val=square_val) and self.selection_piece_value is not None:
            self = MakingMove(context=self.context,
                              selection_piece_rc=self.selection_piece_rc,
                              selection_piece_value=self.selection_piece_value,
                              ).action(square_rowcol=square_rowcol)
        return self  # pass with creation immutable self.selection_piece_value, self.selection_piece_rc?

    def player_attacking_pieces(self) -> set[tuple[int, int]]:
        threatening = set()
        own_pieces_coords = self.context.board.get_coords_for_all_own_pieces(self.context.current_player)
        for rowcol in own_pieces_coords:
            self.allowed_moves(jump_only=True, piece_val=self.context.board[rowcol], piece_rc=rowcol)
            if self.allowed_destinations:
                threatening.add(rowcol)
        return threatening


@dataclass
class MakingMove(GameState):
    enemies_to_remove: set = field(default_factory=set)  # restrict 2nd and further moves (removed after a complete move)
    restricted_selection: bool = False
    allowed_destinations: set = field(init=False)
    enemies_encountered: defaultdict = field(init=False)

    def __post_init__(self):
        self.allowed_moves(piece_val=self.selection_piece_value, piece_rc=self.selection_piece_rc)
        super().__post_init__()

    def action(self, square_rowcol: tuple[int, int]) -> 'GameState':
        if square_rowcol in self.allowed_destinations:
            self.context.view_update_signals.append(True)  # board pieces layout changes
            return self.make_move(to=square_rowcol)
        elif self.restricted_selection or self.got_destination(square_val=self.context.board[square_rowcol]):
            return self  # invalid selection (not allowed different piece) or invalid destination: no update, wait
        return SelectingPiece(context=self.context,
                              selection_piece_rc=self.selection_piece_rc,
                              selection_piece_value=self.selection_piece_value,
                              ).action(square_rowcol=square_rowcol)  # process new selection

    def _can_move(self, player: int) -> bool:
        own_pieces_coords = self.context.board.get_coords_for_all_own_pieces(self.context.current_player)
        for rowcol in own_pieces_coords:
            self.allowed_moves(piece_val=self.context.board[rowcol], piece_rc=rowcol)
            if self.allowed_destinations:
                return True
        return False

    def piece_reaches_last_row(self, at: tuple[int, int]) -> bool:
        return (at[0] == 0 and self.context.current_player == Owner.P1) or \
                (at[0] == self.context.board.h - 1 and self.context.current_player == Owner.P2)

    def make_move(self, to: tuple[int, int]):
        piece_val, piece_rc = self.selection_piece_value, self.selection_piece_rc  # piece's type+player and rowcol coords
        if self.piece_reaches_last_row(at=to) and not PieceType.is_king(piece_val):
            piece_val = self.context.board[piece_rc] = PieceType.crown(piece_val)  # promotes piece
        self.context.board[piece_rc] = PieceType.EMPTY_DARK  # moving from
        self.context.board[to] = piece_val  # moving to
        self.selection_piece_value, self.selection_piece_rc = piece_val, to  # move selection too
        if self.enemies_encountered[to]:
            self.enemies_to_remove.update(self.enemies_encountered[to])  # jumped_over_enemies_coords
            self.allowed_moves(jump_only=True, piece_val=piece_val, piece_rc=to,
                               enemies_already_jumped_over=self.enemies_to_remove)
            # enemies remain to jump over, expect player to perform those jumps with that piece (can be multiple paths):
            if self.allowed_destinations:
                self.restricted_selection = True  # same player continues (can capture at least 1 more enemy with the piece)
                return self
        return self.finish_move()

    def finish_move(self):
        old_player = self.context.current_player
        new_player = self.context.switch_current_player()
        if self.enemies_to_remove:
            self.context.board.remove_enemies(self.enemies_to_remove)
            self.enemies_to_remove.clear()
            if not self.context.board.any_pieces_left(new_player):
                self.context.declare_winner(old_player)
                return self
        if not self._can_move(new_player):
            self.context.declare_winner(old_player)
            return self
        return SelectingPiece(context=self.context)
