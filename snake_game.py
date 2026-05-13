"""Snake Game — arrow keys to move, R to restart, Q to quit."""

import random
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import pygame


# ──────────────────────────── Config ────────────────────────────

@dataclass(frozen=True)
class Config:
    cell_size: int = 24
    cols: int = 25
    rows: int = 20
    fps: int = 10
    initial_length: int = 4

    # Colors
    bg_color: tuple = (15, 20, 30)
    grid_color: tuple = (25, 32, 48)
    snake_head_color: tuple = (80, 220, 120)
    snake_body_color: tuple = (50, 160, 80)
    food_color: tuple = (240, 80, 80)
    text_color: tuple = (220, 220, 220)
    overlay_color: tuple = (0, 0, 0, 160)

    @property
    def width(self) -> int:
        return self.cols * self.cell_size

    @property
    def height(self) -> int:
        return self.rows * self.cell_size


CFG = Config()


# ──────────────────────────── Direction ─────────────────────────

class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()


OPPOSITE = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}

DELTA = {
    Direction.UP:    (0, -1),
    Direction.DOWN:  (0,  1),
    Direction.LEFT:  (-1, 0),
    Direction.RIGHT: (1,  0),
}

KEY_MAP = {
    pygame.K_UP:    Direction.UP,
    pygame.K_DOWN:  Direction.DOWN,
    pygame.K_LEFT:  Direction.LEFT,
    pygame.K_RIGHT: Direction.RIGHT,
    pygame.K_w:     Direction.UP,
    pygame.K_s:     Direction.DOWN,
    pygame.K_a:     Direction.LEFT,
    pygame.K_d:     Direction.RIGHT,
}


# ──────────────────────────── Snake ─────────────────────────────

class Snake:
    def __init__(self):
        mid_x = CFG.cols // 2
        mid_y = CFG.rows // 2
        self.body: list[tuple[int, int]] = [
            (mid_x - i, mid_y) for i in range(CFG.initial_length)
        ]
        self.direction = Direction.RIGHT
        self._queued_direction: Optional[Direction] = None

    @property
    def head(self) -> tuple[int, int]:
        return self.body[0]

    def queue_direction(self, new_dir: Direction) -> None:
        if new_dir != OPPOSITE[self.direction]:
            self._queued_direction = new_dir

    def step(self) -> tuple[int, int]:
        """Move one step and return the tail cell that was removed."""
        if self._queued_direction:
            self.direction = self._queued_direction
            self._queued_direction = None

        dx, dy = DELTA[self.direction]
        new_head = (self.head[0] + dx, self.head[1] + dy)
        self.body.insert(0, new_head)
        return self.body.pop()

    def grow(self, tail_cell: tuple[int, int]) -> None:
        self.body.append(tail_cell)

    def collides_with_self(self) -> bool:
        return self.head in self.body[1:]

    def out_of_bounds(self) -> bool:
        x, y = self.head
        return not (0 <= x < CFG.cols and 0 <= y < CFG.rows)

    def occupies(self) -> set[tuple[int, int]]:
        return set(self.body)


# ──────────────────────────── Food ──────────────────────────────

class Food:
    def __init__(self, blocked: set[tuple[int, int]]):
        self.pos = self._random_pos(blocked)

    def _random_pos(self, blocked: set[tuple[int, int]]) -> tuple[int, int]:
        all_cells = {(x, y) for x in range(CFG.cols) for y in range(CFG.rows)}
        free = list(all_cells - blocked)
        return random.choice(free) if free else (0, 0)

    def respawn(self, blocked: set[tuple[int, int]]) -> None:
        self.pos = self._random_pos(blocked)


# ──────────────────────────── Game ──────────────────────────────

class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_big   = pygame.font.SysFont("consolas", 40, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 22)
        self.font_score = pygame.font.SysFont("consolas", 26, bold=True)
        self._new_game()

    def _new_game(self) -> None:
        self.snake = Snake()
        self.food  = Food(self.snake.occupies())
        self.score = 0
        self.game_over = False

    # ── Main loop ──

    def run(self) -> None:
        clock = pygame.time.Clock()
        while True:
            self._handle_events()
            if not self.game_over:
                self._update()
            self._draw()
            clock.tick(CFG.fps)

    # ── Events ──

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                self._handle_key(event.key)

    def _handle_key(self, key: int) -> None:
        if key in (pygame.K_q, pygame.K_ESCAPE):
            pygame.quit()
            sys.exit()
        if key == pygame.K_r:
            self._new_game()
            return
        if not self.game_over and key in KEY_MAP:
            self.snake.queue_direction(KEY_MAP[key])

    # ── Update ──

    def _update(self) -> None:
        removed_tail = self.snake.step()

        if self.snake.out_of_bounds() or self.snake.collides_with_self():
            self.game_over = True
            return

        if self.snake.head == self.food.pos:
            self.snake.grow(removed_tail)
            self.score += 10
            self.food.respawn(self.snake.occupies())

    # ── Draw ──

    def _draw(self) -> None:
        self.screen.fill(CFG.bg_color)
        self._draw_grid()
        self._draw_food()
        self._draw_snake()
        self._draw_score()
        if self.game_over:
            self._draw_game_over()
        pygame.display.flip()

    def _draw_grid(self) -> None:
        for x in range(0, CFG.width, CFG.cell_size):
            pygame.draw.line(self.screen, CFG.grid_color, (x, 0), (x, CFG.height))
        for y in range(0, CFG.height, CFG.cell_size):
            pygame.draw.line(self.screen, CFG.grid_color, (0, y), (CFG.width, y))

    def _draw_snake(self) -> None:
        for i, (cx, cy) in enumerate(self.snake.body):
            color = CFG.snake_head_color if i == 0 else CFG.snake_body_color
            rect = pygame.Rect(
                cx * CFG.cell_size + 2,
                cy * CFG.cell_size + 2,
                CFG.cell_size - 4,
                CFG.cell_size - 4,
            )
            pygame.draw.rect(self.screen, color, rect, border_radius=5)

    def _draw_food(self) -> None:
        fx, fy = self.food.pos
        center = (
            fx * CFG.cell_size + CFG.cell_size // 2,
            fy * CFG.cell_size + CFG.cell_size // 2,
        )
        pygame.draw.circle(self.screen, CFG.food_color, center, CFG.cell_size // 2 - 3)

    def _draw_score(self) -> None:
        label = self.font_score.render(f"Score: {self.score}", True, CFG.text_color)
        self.screen.blit(label, (8, 6))

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface((CFG.width, CFG.height), pygame.SRCALPHA)
        overlay.fill(CFG.overlay_color)
        self.screen.blit(overlay, (0, 0))

        for text, font, dy in [
            ("GAME OVER",          self.font_big,   -50),
            (f"Score: {self.score}", self.font_small, 10),
            ("[R] Restart  [Q] Quit", self.font_small, 50),
        ]:
            surf = font.render(text, True, CFG.text_color)
            rect = surf.get_rect(center=(CFG.width // 2, CFG.height // 2 + dy))
            self.screen.blit(surf, rect)


# ──────────────────────────── Entry ─────────────────────────────

def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((CFG.width, CFG.height))
    pygame.display.set_caption("Snake")
    Game(screen).run()


if __name__ == "__main__":
    main()
