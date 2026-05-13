"""
Tetris
  ← →     : move
  ↑ / Z   : rotate
  ↓       : soft drop
  Space   : hard drop
  R       : restart
  Q / ESC : quit
"""

import sys
import random
from copy import deepcopy
from dataclasses import dataclass

import pygame


# ═══════════════════════════ Config ════════════════════════════

@dataclass(frozen=True)
class Config:
    cols: int   = 10
    rows: int   = 20
    cell: int   = 36          # cell size px
    sidebar: int = 220        # right panel width
    fps: int    = 60

    # timing (frames)
    fall_interval: int  = 48  # normal fall speed
    lock_delay: int     = 30  # frames before piece locks after landing
    das_delay: int      = 10  # delayed auto-shift delay
    das_repeat: int     = 2   # DAS repeat rate

    # colors
    bg: tuple         = (15,  15,  25)
    board_bg: tuple   = (22,  22,  38)
    grid: tuple       = (35,  35,  55)
    text: tuple       = (220, 220, 220)
    text_dim: tuple   = (120, 120, 140)
    ghost: tuple      = (60,  60,  80)

CFG = Config()

BOARD_W = CFG.cols * CFG.cell
BOARD_H = CFG.rows * CFG.cell
SCREEN_W = BOARD_W + CFG.sidebar
SCREEN_H = BOARD_H


# ═══════════════════════════ Pieces ════════════════════════════

# Each piece: list of 4 rotation states, each state = list of (row, col) offsets
PIECES = {
    "I": {
        "color": (0, 220, 220),
        "shapes": [
            [(0,0),(0,1),(0,2),(0,3)],
            [(0,2),(1,2),(2,2),(3,2)],
            [(1,0),(1,1),(1,2),(1,3)],
            [(0,1),(1,1),(2,1),(3,1)],
        ],
    },
    "O": {
        "color": (240, 220, 0),
        "shapes": [
            [(0,0),(0,1),(1,0),(1,1)],
        ] * 4,
    },
    "T": {
        "color": (160, 0, 220),
        "shapes": [
            [(0,1),(1,0),(1,1),(1,2)],
            [(0,1),(1,1),(2,1),(1,2)],
            [(1,0),(1,1),(1,2),(2,1)],
            [(0,1),(1,0),(1,1),(2,1)],
        ],
    },
    "S": {
        "color": (0, 220, 80),
        "shapes": [
            [(0,1),(0,2),(1,0),(1,1)],
            [(0,1),(1,1),(1,2),(2,2)],
            [(1,1),(1,2),(2,0),(2,1)],
            [(0,0),(1,0),(1,1),(2,1)],
        ],
    },
    "Z": {
        "color": (220, 50, 50),
        "shapes": [
            [(0,0),(0,1),(1,1),(1,2)],
            [(0,2),(1,1),(1,2),(2,1)],
            [(1,0),(1,1),(2,1),(2,2)],
            [(0,1),(1,0),(1,1),(2,0)],
        ],
    },
    "J": {
        "color": (40, 80, 220),
        "shapes": [
            [(0,0),(1,0),(1,1),(1,2)],
            [(0,1),(0,2),(1,1),(2,1)],
            [(1,0),(1,1),(1,2),(2,2)],
            [(0,1),(1,1),(2,0),(2,1)],
        ],
    },
    "L": {
        "color": (220, 130, 0),
        "shapes": [
            [(0,2),(1,0),(1,1),(1,2)],
            [(0,1),(1,1),(2,1),(2,2)],
            [(1,0),(1,1),(1,2),(2,0)],
            [(0,0),(0,1),(1,1),(2,1)],
        ],
    },
}

PIECE_NAMES = list(PIECES.keys())


# ═══════════════════════════ Board ═════════════════════════════

class Board:
    def __init__(self):
        self.grid: list[list[Optional[tuple]]] = [
            [None] * CFG.cols for _ in range(CFG.rows)
        ]

    def is_valid(self, cells: list[tuple[int,int]]) -> bool:
        for r, c in cells:
            if c < 0 or c >= CFG.cols:
                return False
            if r >= CFG.rows:
                return False
            if r >= 0 and self.grid[r][c] is not None:
                return False
        return True

    def lock(self, cells: list[tuple[int,int]], color: tuple) -> None:
        for r, c in cells:
            if r >= 0:
                self.grid[r][c] = color

    def clear_lines(self) -> int:
        full = [r for r in range(CFG.rows) if all(self.grid[r])]
        for r in full:
            del self.grid[r]
            self.grid.insert(0, [None] * CFG.cols)
        return len(full)

    def is_topped_out(self) -> bool:
        return any(self.grid[0][c] is not None for c in range(CFG.cols))


# ═══════════════════════════ Piece ═════════════════════════════

from typing import Optional


class Piece:
    def __init__(self, name: str):
        self.name   = name
        self.color  = PIECES[name]["color"]
        self.shapes = PIECES[name]["shapes"]
        self.rot    = 0
        # spawn centered, 2 rows above top
        self.row    = -2
        self.col    = CFG.cols // 2 - 2

    def cells(self, row=None, col=None, rot=None) -> list[tuple[int,int]]:
        r = self.row if row is None else row
        c = self.col if col is None else col
        rt = self.rot if rot is None else rot
        return [(r + dr, c + dc) for dr, dc in self.shapes[rt % len(self.shapes)]]


# ═══════════════════════════ Bag ═══════════════════════════════

class Bag:
    """7-bag randomizer — guarantees every piece appears once per cycle."""
    def __init__(self):
        self._bag: list[str] = []

    def next(self) -> str:
        if not self._bag:
            self._bag = random.sample(PIECE_NAMES, len(PIECE_NAMES))
        return self._bag.pop()

    def peek(self, n: int = 3) -> list[str]:
        while len(self._bag) < n:
            self._bag = random.sample(PIECE_NAMES, len(PIECE_NAMES)) + self._bag
        return list(reversed(self._bag[-n:]))


# ═══════════════════════════ Scoring ═══════════════════════════

LINE_SCORES = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}


# ═══════════════════════════ Game ══════════════════════════════

class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_lg  = pygame.font.SysFont("consolas", 32, bold=True)
        self.font_md  = pygame.font.SysFont("consolas", 22, bold=True)
        self.font_sm  = pygame.font.SysFont("consolas", 18)
        self._new_game()

    def _new_game(self) -> None:
        self.board     = Board()
        self.bag       = Bag()
        self.piece     = Piece(self.bag.next())
        self.held: Optional[str] = None
        self.can_hold  = True
        self.score     = 0
        self.level     = 1
        self.lines     = 0
        self.game_over = False

        # Timers (in frames)
        self._fall_timer  = 0
        self._lock_timer  = 0
        self._locking     = False

        # DAS (delayed auto-shift)
        self._das_dir    = 0
        self._das_timer  = 0
        self._das_active = False

    # ── Helpers ────────────────────────────────────────────────

    def _fall_interval(self) -> int:
        return max(2, CFG.fall_interval - (self.level - 1) * 4)

    def _ghost_row(self) -> int:
        r = self.piece.row
        while self.board.is_valid(self.piece.cells(row=r + 1)):
            r += 1
        return r

    def _try_move(self, dr: int, dc: int) -> bool:
        if self.board.is_valid(self.piece.cells(row=self.piece.row + dr,
                                                col=self.piece.col + dc)):
            self.piece.row += dr
            self.piece.col += dc
            return True
        return False

    def _try_rotate(self, delta: int) -> None:
        new_rot = (self.piece.rot + delta) % len(self.piece.shapes)
        # Wall kicks: try offsets
        for dc in (0, -1, 1, -2, 2):
            if self.board.is_valid(self.piece.cells(rot=new_rot,
                                                    col=self.piece.col + dc)):
                self.piece.rot = new_rot
                self.piece.col += dc
                return

    def _lock_piece(self) -> None:
        self.board.lock(self.piece.cells(), self.piece.color)
        cleared = self.board.clear_lines()
        self.lines += cleared
        self.score += LINE_SCORES[cleared] * self.level
        self.level  = self.lines // 10 + 1

        if self.board.is_topped_out():
            self.game_over = True
            return

        self.piece    = Piece(self.bag.next())
        self.can_hold = True
        self._locking = False
        self._lock_timer = 0

    def _hold(self) -> None:
        if not self.can_hold:
            return
        if self.held is None:
            self.held  = self.piece.name
            self.piece = Piece(self.bag.next())
        else:
            self.held, name = self.piece.name, self.held
            self.piece = Piece(name)
        self.can_hold = False

    def _hard_drop(self) -> None:
        dropped = 0
        while self._try_move(1, 0):
            dropped += 1
        self.score += dropped * 2
        self._lock_piece()

    # ── Main loop ──────────────────────────────────────────────

    def run(self) -> None:
        clock = pygame.time.Clock()
        while True:
            clock.tick(CFG.fps)
            self._handle_events()
            if not self.game_over:
                self._update()
            self._draw()

    # ── Events ─────────────────────────────────────────────────

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                self._on_keydown(event.key)
            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self._das_dir = 0
                    self._das_active = False

    def _on_keydown(self, key: int) -> None:
        if key in (pygame.K_q, pygame.K_ESCAPE):
            pygame.quit(); sys.exit()
        if key == pygame.K_r:
            self._new_game(); return

        if self.game_over:
            return

        if key == pygame.K_LEFT:
            self._try_move(0, -1)
            self._das_dir = -1; self._das_timer = 0; self._das_active = False
        elif key == pygame.K_RIGHT:
            self._try_move(0, 1)
            self._das_dir = 1; self._das_timer = 0; self._das_active = False
        elif key == pygame.K_DOWN:
            if self._try_move(1, 0):
                self.score += 1
        elif key in (pygame.K_UP, pygame.K_z, pygame.K_x):
            self._try_rotate(1 if key != pygame.K_z else -1)
        elif key == pygame.K_SPACE:
            self._hard_drop()
        elif key == pygame.K_c or key == pygame.K_LSHIFT:
            self._hold()

    # ── Update ─────────────────────────────────────────────────

    def _update(self) -> None:
        # DAS
        if self._das_dir != 0:
            self._das_timer += 1
            if not self._das_active and self._das_timer >= CFG.das_delay:
                self._das_active = True
                self._das_timer  = 0
            if self._das_active and self._das_timer % CFG.das_repeat == 0:
                self._try_move(0, self._das_dir)

        # Soft drop held
        keys = pygame.key.get_pressed()
        if keys[pygame.K_DOWN]:
            if self._try_move(1, 0):
                self.score += 1

        # Gravity
        self._fall_timer += 1
        if self._fall_timer >= self._fall_interval():
            self._fall_timer = 0
            if not self._try_move(1, 0):
                self._locking = True

        # Lock delay
        if self._locking:
            self._lock_timer += 1
            if self._lock_timer >= CFG.lock_delay:
                self._lock_piece()
            # Reset lock if piece moved off ground
            if self.board.is_valid(self.piece.cells(row=self.piece.row + 1)):
                self._locking = False
                self._lock_timer = 0

    # ── Draw ───────────────────────────────────────────────────

    def _draw(self) -> None:
        self.screen.fill(CFG.bg)
        self._draw_board()
        self._draw_ghost()
        self._draw_piece(self.piece)
        self._draw_sidebar()
        if self.game_over:
            self._draw_game_over()
        pygame.display.flip()

    def _cell_rect(self, row: int, col: int) -> pygame.Rect:
        return pygame.Rect(col * CFG.cell, row * CFG.cell, CFG.cell, CFG.cell)

    def _draw_board(self) -> None:
        pygame.draw.rect(self.screen, CFG.board_bg,
                         pygame.Rect(0, 0, BOARD_W, BOARD_H))
        # Grid lines
        for c in range(CFG.cols + 1):
            pygame.draw.line(self.screen, CFG.grid,
                             (c * CFG.cell, 0), (c * CFG.cell, BOARD_H))
        for r in range(CFG.rows + 1):
            pygame.draw.line(self.screen, CFG.grid,
                             (0, r * CFG.cell), (BOARD_W, r * CFG.cell))
        # Locked cells
        for r in range(CFG.rows):
            for c in range(CFG.cols):
                color = self.board.grid[r][c]
                if color:
                    self._draw_cell(r, c, color)

    def _draw_cell(self, row: int, col: int, color: tuple, alpha: int = 255,
                   offset_x: int = 0) -> None:
        rect = pygame.Rect(
            col * CFG.cell + offset_x + 1,
            row * CFG.cell + 1,
            CFG.cell - 2,
            CFG.cell - 2,
        )
        if alpha < 255:
            s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            s.fill((*color[:3], alpha))
            self.screen.blit(s, rect.topleft)
        else:
            pygame.draw.rect(self.screen, color, rect, border_radius=3)
            # Highlight
            hi = tuple(min(255, v + 60) for v in color[:3])
            pygame.draw.line(self.screen, hi, rect.topleft,
                             (rect.right - 2, rect.top), 2)

    def _draw_ghost(self) -> None:
        ghost_r = self._ghost_row()
        for dr, dc in self.piece.shapes[self.piece.rot % len(self.piece.shapes)]:
            r, c = ghost_r + dr, self.piece.col + dc
            if 0 <= r < CFG.rows and 0 <= c < CFG.cols:
                rect = pygame.Rect(c * CFG.cell + 1, r * CFG.cell + 1,
                                   CFG.cell - 2, CFG.cell - 2)
                pygame.draw.rect(self.screen, CFG.ghost, rect, border_radius=3,
                                 width=2)

    def _draw_piece(self, piece: Piece) -> None:
        for r, c in piece.cells():
            if r >= 0:
                self._draw_cell(r, c, piece.color)

    # ── Sidebar ────────────────────────────────────────────────

    def _draw_sidebar(self) -> None:
        ox = BOARD_W + 16

        def label(text, y, font=None, color=None):
            f = font or self.font_sm
            c = color or CFG.text_dim
            self.screen.blit(f.render(text, True, c), (ox, y))

        # Score / Level / Lines
        label("SCORE", 20)
        label(str(self.score), 42, self.font_md, CFG.text)
        label("LEVEL", 90)
        label(str(self.level), 112, self.font_md, CFG.text)
        label("LINES", 160)
        label(str(self.lines), 182, self.font_md, CFG.text)

        # Next pieces
        label("NEXT", 240)
        next_names = self.bag.peek(3)
        for i, name in enumerate(next_names):
            self._draw_mini_piece(name, ox, 268 + i * 80, scale=0.6)

        # Hold
        label("HOLD", 520)
        if self.held:
            color = PIECES[self.held]["color"] if self.can_hold \
                    else tuple(v // 2 for v in PIECES[self.held]["color"])
            self._draw_mini_piece(self.held, ox, 548, scale=0.6,
                                  override_color=color)

        # Controls
        label("← → : move",    680)
        label("↑ Z  : rotate", 700)
        label("↓    : drop",   720)
        label("SPC  : hard",   740)
        label("C    : hold",   760)
        label("R    : restart",780)

    def _draw_mini_piece(self, name: str, ox: int, oy: int, scale: float = 1.0,
                         override_color: Optional[tuple] = None) -> None:
        shape  = PIECES[name]["shapes"][0]
        color  = override_color or PIECES[name]["color"]
        cs     = int(CFG.cell * scale)
        min_r  = min(r for r, c in shape)
        min_c  = min(c for r, c in shape)
        for r, c in shape:
            rect = pygame.Rect(ox + (c - min_c) * cs + 4,
                               oy + (r - min_r) * cs,
                               cs - 2, cs - 2)
            pygame.draw.rect(self.screen, color, rect, border_radius=3)

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        for text, font, dy, color in [
            ("GAME OVER",      self.font_lg, -50, (220, 60, 60)),
            (f"Score: {self.score}", self.font_md, 10,  CFG.text),
            ("R to restart",   self.font_sm,  55, CFG.text_dim),
        ]:
            surf = font.render(text, True, color)
            rect = surf.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + dy))
            self.screen.blit(surf, rect)


# ═══════════════════════════ Entry ═════════════════════════════

def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Tetris")
    Game(screen).run()


if __name__ == "__main__":
    main()
