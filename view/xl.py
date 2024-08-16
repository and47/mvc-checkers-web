from model.engine import GameRound
from model.gridlike import PieceChar, PieceType, Owner, Board
from collections import namedtuple
from time import sleep
from functools import wraps

import sys  # without this Excel complains of "Unlicensed product"
import clr  # provide own path (may depend on your Excel installation):
clr.AddReference(r"C:\Program Files (x86)\Microsoft Office\root\Office16\DCF\Microsoft.Office.Interop.Excel.dll")
from System import Activator, Type, Reflection
from Microsoft.Office.Interop import Excel


class CheckersExcel:
    rc_coords_named = namedtuple('rowcol', ['r', 'c'])

    def __init__(self, board_info: GameRound):
        self.start_rowcol, self.end_rowcol = (0, 0), (board_info.board.w-1, board_info.board.h-1)
        self.y0, self.x0 = self.start_rowcol

        self.game = board_info
        self.board = board_info.board  # list of lists of ints
        self.moves = []  # user moves are appended here

        excel_type = Type.GetTypeFromProgID("Excel.Application")
        self.excel = Activator.CreateInstance(excel_type)
        workbook = self.excel.Workbooks.Add()
        self.ws = Excel.Worksheet(workbook.Worksheets[1])
        self.grid_range = self.excel_grid = None

        self.format_grid(board_info.board)

    @staticmethod
    def retry_on_errors(wrapped_f) -> callable:
        @wraps(wrapped_f)
        def wrapped(self, *args, **kwargs):
            retries, max_retries = 0, 60

            while retries < max_retries:

                while not self.excel.Ready:
                    sleep(0.1)
                try:
                    return wrapped_f(self, *args, **kwargs)  # operation in Excel
                except Exception as e:
                    print(f"Attempt {retries + 1}: An error occurred on {wrapped_f, args, kwargs}: {e}")
                    retries += 1
                    sleep(1)  # wait more before retrying, user could be e.g. editing cell
            raise RuntimeError(f"Couldn't {wrapped_f} on Excel cell value")
        return wrapped

    @classmethod
    def use_as_ux(cls, board_info: GameRound) -> tuple:
        server = daemon_thread = None
        instance_self = cls(board_info=board_info)
        return server, daemon_thread, instance_self  # for compatibility with other UIs (e.g. async web servers)

    def update_board(self, updated_board: GameRound):
        self.put_all_content_on_grid()
        if not self.game.over:  # get input from Excel:
            board_square_index = self.get_user_move()
            rowcol = self.board.rc_coordinates.flatten()[board_square_index]
            self.moves.append(CheckersExcel.rc_coords_named(*rowcol))

    def show_winner(self, winner: int):
        below_board_1x1 = self.get_xl_range(rc_coord=(self.end_rowcol[0] + 1, 0))
        self.set_xl_value(below_board_1x1, f"Winner {Owner(winner).name}: {PieceChar.get_char(winner)}")

    def get_user_move(self) -> int | None:
        """Checks for and returns a valid user input (i.e. change in a cell on the grid/board range)"""
        chgs, prior_values = 0, self.excel_grid  # contains state (cell values/contents) prior to user input
        while not self.game.over:
            sleep(0.5)  # poll user "move" every half-second
            new_values = self.read_grid()  # use self.excel.ActiveCell and self.ws.OnEntry instead?
            for i, (old_val, new_val) in enumerate(zip(prior_values, new_values)):
                if old_val != new_val:
                    chgs += 1
                    changed_cell_idx, changed_cell_val = i, str(new_val)
            if chgs:
                if chgs == 1:
                    return changed_cell_idx
                else:
                    self.set_grid(prior_values)  # invalid input (e.g. multiple moves)
            # no changes: continue loop (re-check for user input)

    @retry_on_errors
    def set_grid(self, values: "Value2"):
        self.grid_range.Value2 = values

    def read_grid(self) -> tuple:
        return tuple(self.grid_range.Value2)  # element is a cell's content

    @staticmethod
    def rgb_to_excel_color(r, g, b):
        """Converts RGB values to an Excel color integer."""
        return (b << 16) | (g << 8) | r

    def format_grid(self, board: Board) -> "Value2":  # to-do: center value inside each cell
        start_cell = self.get_xl_cell(*self.start_rowcol)  # ws.get_Cells or ws.Cells error
        end_cell = self.get_xl_cell(*self.end_rowcol)

        self.grid_range = grid = self.get_xl_range(top_left=start_cell, bottom_right=end_cell)
        grid.set_ColumnWidth(2.14)  # default row height (20 px)

        borders = grid.Borders
        borders.LineStyle = Excel.XlLineStyle.xlContinuous
        thicker = 4  # Excel.XlBorderWeight.xlThick == 4
        edges = [Excel.XlBordersIndex.xlEdgeTop, Excel.XlBordersIndex.xlEdgeRight,
                 Excel.XlBordersIndex.xlEdgeBottom, Excel.XlBordersIndex.xlEdgeLeft]
        for outer_border in edges:
            borders.get_Item(outer_border).set_Weight(thicker)
        self.excel.Visible = True
        grid.HorizontalAlignment = Excel.XlHAlign.xlHAlignCenter
        grid.VerticalAlignment = Excel.XlVAlign.xlVAlignCenter

        for rc in board.set_rc_coordinates:
            if board.val_arr[rc] != PieceType.EMPTY_LIGHT:  # checkerboard look (dark square if non-zero)
                cell = self.get_xl_range(rc_coord=rc)
                green_excel = self.rgb_to_excel_color(135, 186, 83)
                cell.Interior.Color = green_excel  # to-do: .Font.Color? Use bold?

        self.ws.Application.ActiveWindow.Zoom = 300  # %
        self.excel_grid = self.read_grid()

    @retry_on_errors
    def set_xl_value(self, cell_range: "Range", value: int | str):
        cell_range.Value2 = value

    @retry_on_errors
    def get_xl_cell(self, row: int, col: int) -> "Cells":
        xl_cell = self.ws.GetType().InvokeMember("Cells", Reflection.BindingFlags.GetProperty, None, self.ws,
                                                 [row + 1, col + 1])  # type int only not numpy!
        return xl_cell

    def get_xl_range(self, top_left: "Cells" = None, bottom_right: "Cells" = None,
                     rc_coord: tuple[int, int] | None = None) -> "Range":
        if rc_coord is not None and top_left is None and bottom_right is None:
            single_cell_from_coords = self.get_xl_cell(col=rc_coord[1], row=rc_coord[0])
            return self.ws.get_Range(single_cell_from_coords, single_cell_from_coords)
        elif rc_coord is None:  # to-do? @retry_on_errors? decorate?
            if bottom_right is None:
                return self.ws.get_Range(top_left, top_left)  # single cell range from Cells obj
            return self.ws.get_Range(top_left, bottom_right)  # rectangular multi-cell Range

    def put_all_content_on_grid(self, cells_coords: list[tuple] | None = None):
        """Set each affected cell value in Spreadsheet one at a time and return the whole grid"""
        if cells_coords is None:
            cells_coords = self.board.set_rc_coordinates
        for rc in cells_coords:
            # if sum(rc) % 2:  # skips white squares (empty in checkers), only valid for e.g. 8x8 board
            self._reveal_content_in_cell(rc)
        self.excel_grid = self.read_grid()

    def _reveal_content_in_cell(self, rc: tuple[int, int]) -> None:
        range1x1 = self.get_xl_range(rc_coord=rc).Cells[self.y0, self.x0]  # adjust for grid loc.
        char = str(self.board.pretty[rc])
        if not PieceType.is_piece(PieceType[PieceChar(char).name]):  # if PieceType.is_piece(self.board.val_arr[rc]):
            char = ' '
        self.set_xl_value(range1x1, char)
