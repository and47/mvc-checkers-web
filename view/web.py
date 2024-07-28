from functools import partial
from time import sleep

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


class FastAPIView:
    def __init__(self, game_state):
        self.app = FastAPI()
        self.moves = game_state.moves
        self.board = game_state.board
        self.state = game_state

    def create_routes(self):
        # Mount the static directory to serve index.html and assets
        self.app.mount("/static", StaticFiles(directory="./view/static"), name="static")

        @self.app.get("/state")
        def get_state():
            sleep(0.3)  # longer sleep than in mvc.Checkers_Controller.get_user_move
            return self.state

        @self.app.post("/move")
        def make_move(move: Move):
            if not self.moves:
                self.moves.append(move)
                return {"status": "success", "move": move}

        @self.app.get("/", response_class=HTMLResponse)
        async def read_index():
            with open("view/static/index.html") as f:
                return HTMLResponse(content=f.read(), status_code=200)

    def get_app(self):
        self.create_routes()
        return self.app


def run_server(board_info: 'GameRound', **kwargs):
    game_state = Game(board_info.boardview_aslist())
    fastapi_view = FastAPIView(game_state)
    import uvicorn
    import threading
    import traceback
    config = uvicorn.Config(fastapi_view.get_app(), **kwargs)
    server = uvicorn.Server(config)

    def _start_server():
        try:
            server.run()
        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()

    server_thread = threading.Thread(target=_start_server)
    server_thread.start()
    return server, server_thread, game_state


run_local_webserver = partial(run_server, host="127.0.0.1", port=8000)


class Move(BaseModel):
    r: int  # row
    c: int  # column, => rc == cell (square)


class Game:
    def __init__(self, board_info: list[list[int]]):
        self.board = board_info
        self.moves = []
        self.is_async = True

    def update_board(self, updated_board: list[list[int]]):
        self.board = updated_board.boardview_aslist()  # get a list (not np.ndarray) consumable by JS

    def show_winner(self, winner: int):
        self.board = [[winner]]  # re-use same grid object for display
