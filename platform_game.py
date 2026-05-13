"""
Platform Jumper
  Arrow / WASD : move & jump
  R            : restart
  Q / ESC      : quit
"""

import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import pygame


# ═══════════════════════════ Config ════════════════════════════

@dataclass(frozen=True)
class Config:
    # Window
    screen_w: int = 960
    screen_h: int = 540
    fps: int = 60
    tile: int = 40          # tile size in pixels

    # Physics
    gravity: float = 0.6
    jump_force: float = -13.0
    move_speed: float = 4.5
    max_fall: float = 18.0

    # Colors
    bg_top: tuple    = (20,  24,  50)
    bg_bot: tuple    = (10,  12,  30)
    tile_color: tuple = (80, 110, 160)
    tile_edge: tuple  = (120, 160, 210)
    spike_color: tuple = (200, 60, 60)
    player_color: tuple = (100, 220, 130)
    player_eye: tuple   = (20,  20,  20)
    enemy_color: tuple  = (220, 90,  80)
    enemy_eye: tuple    = (20,  20,  20)
    coin_color: tuple   = (255, 210, 50)
    hud_color: tuple    = (230, 230, 230)
    dead_color: tuple   = (200, 60,  60)
    clear_color: tuple  = (100, 220, 130)

CFG = Config()


# ═══════════════════════════ Camera ════════════════════════════

class Camera:
    def __init__(self, level_w: int, level_h: int):
        self.x = 0.0
        self.y = 0.0
        self.level_w = level_w
        self.level_h = level_h

    def follow(self, target: pygame.Rect) -> None:
        cx = target.centerx - CFG.screen_w // 2
        cy = target.centery - CFG.screen_h // 2
        self.x += (cx - self.x) * 0.12
        self.y += (cy - self.y) * 0.12
        self.x = max(0, min(self.x, self.level_w  - CFG.screen_w))
        self.y = max(0, min(self.y, self.level_h  - CFG.screen_h))

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        return rect.move(-int(self.x), -int(self.y))


# ═══════════════════════════ Tile ══════════════════════════════

class TileKind(Enum):
    SOLID = auto()
    SPIKE = auto()
    COIN  = auto()


@dataclass
class Tile:
    rect: pygame.Rect
    kind: TileKind
    collected: bool = False   # only used by COIN


# ════════════════════════════ Level ════════════════════════════

# Map legend:
#   '#' = solid tile   '^' = spike   'C' = coin
#   'P' = player spawn  'E' = enemy   ' ' = empty

LEVEL_MAP = [
    "                                                                        ",
    "                                                                        ",
    "                                C    C    C                             ",
    "                           #########                                    ",
    "                  C                                  C    C             ",
    "            ############                        ##########              ",
    "                                    C   C                               ",
    "  C    C               ##########                                       ",
    "##########                                                   C    C     ",
    "         ####    C   C            E              ###########            ",
    "                #######      ##########                        C        ",
    "   E                                      C  C       #####             ",
    "#######    C  C        ####                        #########            ",
    "                                  ####    E                             ",
    "  C              ####                          ##########               ",
    "######    E             C    C                                   C   C  ",
    "                   #########       ###    E                 ########    ",
    "    C   C                                        C   C                  ",
    "P            ####          E    ######                  ####            ",
    "##########        ######                  #########           ##########",
    "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^",
]

T = CFG.tile


def load_level(layout: list[str]) -> tuple[
    list[Tile], list["Enemy"], pygame.Rect, int, int
]:
    tiles: list[Tile] = []
    enemies: list[Enemy] = []
    spawn = pygame.Rect(2 * T, 2 * T, 1, 1)

    rows = len(layout)
    cols = max(len(row) for row in layout)

    for r, row in enumerate(layout):
        for c, ch in enumerate(row):
            rect = pygame.Rect(c * T, r * T, T, T)
            if ch == "#":
                tiles.append(Tile(rect, TileKind.SOLID))
            elif ch == "^":
                tiles.append(Tile(rect, TileKind.SPIKE))
            elif ch == "C":
                tiles.append(Tile(rect, TileKind.COIN))
            elif ch == "P":
                spawn = pygame.Rect(c * T, r * T - T, T, T)
            elif ch == "E":
                enemies.append(Enemy(c * T, r * T - T + 8))

    return tiles, enemies, spawn, cols * T, rows * T


# ═══════════════════════════ Player ════════════════════════════

class Player:
    W, H = 32, 36

    def __init__(self, spawn: pygame.Rect):
        self.rect = pygame.Rect(spawn.x, spawn.y, self.W, self.H)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.alive = True
        self.coins = 0
        self.facing = 1   # 1=right, -1=left

    def handle_input(self, keys) -> None:
        if not self.alive:
            return
        left  = keys[pygame.K_LEFT]  or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        jump  = keys[pygame.K_UP]    or keys[pygame.K_w] or keys[pygame.K_SPACE]

        if left:
            self.vx = -CFG.move_speed
            self.facing = -1
        elif right:
            self.vx = CFG.move_speed
            self.facing = 1
        else:
            self.vx = 0.0

        if jump and self.on_ground:
            self.vy = CFG.jump_force
            self.on_ground = False

    def update(self, tiles: list[Tile]) -> None:
        if not self.alive:
            return

        self.vy = min(self.vy + CFG.gravity, CFG.max_fall)
        self.on_ground = False

        # Horizontal movement + collision
        self.rect.x += int(self.vx)
        for tile in tiles:
            if tile.kind not in (TileKind.SOLID,) or not self.rect.colliderect(tile.rect):
                continue
            if self.vx > 0:
                self.rect.right = tile.rect.left
            elif self.vx < 0:
                self.rect.left = tile.rect.right
            self.vx = 0

        # Vertical movement + collision
        self.rect.y += int(self.vy)
        for tile in tiles:
            if tile.kind not in (TileKind.SOLID,) or not self.rect.colliderect(tile.rect):
                continue
            if self.vy > 0:
                self.rect.bottom = tile.rect.top
                self.on_ground = True
            elif self.vy < 0:
                self.rect.top = tile.rect.bottom
            self.vy = 0

        # Coin collection
        for tile in tiles:
            if tile.kind == TileKind.COIN and not tile.collected:
                if self.rect.colliderect(tile.rect):
                    tile.collected = True
                    self.coins += 1

        # Spike / fall death
        for tile in tiles:
            if tile.kind == TileKind.SPIKE and self.rect.colliderect(tile.rect):
                self.alive = False
        from platform_game import LEVEL_MAP
        level_h = len(LEVEL_MAP) * T
        if self.rect.top > level_h:
            self.alive = False

    def draw(self, surface: pygame.Surface, cam: Camera) -> None:
        r = cam.apply(self.rect)
        color = CFG.player_color if self.alive else CFG.dead_color
        pygame.draw.rect(surface, color, r, border_radius=6)

        # Eyes
        eye_y = r.top + 8
        if self.facing == 1:
            eye_x = r.left + 18
        else:
            eye_x = r.left + 8
        pygame.draw.circle(surface, CFG.player_eye, (eye_x, eye_y), 4)


# ═══════════════════════════ Enemy ═════════════════════════════

class Enemy:
    W, H = 32, 32
    SPEED = 1.8
    PATROL = 120   # pixels each side

    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(x, y, self.W, self.H)
        self.origin_x = x
        self.vx = self.SPEED
        self.alive = True

    def update(self, tiles: list[Tile]) -> None:
        if not self.alive:
            return

        self.rect.x += int(self.vx)

        # Reverse at patrol boundary
        if abs(self.rect.x - self.origin_x) >= self.PATROL:
            self.vx *= -1

        # Solid tile bounce
        for tile in tiles:
            if tile.kind == TileKind.SOLID and self.rect.colliderect(tile.rect):
                if self.vx > 0:
                    self.rect.right = tile.rect.left
                else:
                    self.rect.left = tile.rect.right
                self.vx *= -1

    def check_player(self, player: Player) -> None:
        if not self.alive or not player.alive:
            return
        if self.rect.colliderect(player.rect):
            # Stomp from above kills enemy, else kills player
            if player.rect.bottom <= self.rect.top + 12 and player.vy > 0:
                self.alive = False
                player.vy = CFG.jump_force * 0.7
                player.coins += 3
            else:
                player.alive = False

    def draw(self, surface: pygame.Surface, cam: Camera) -> None:
        if not self.alive:
            return
        r = cam.apply(self.rect)
        pygame.draw.rect(surface, CFG.enemy_color, r, border_radius=5)
        # Eyes (always facing movement direction)
        eye_y = r.top + 7
        eye_x = r.left + (18 if self.vx > 0 else 8)
        pygame.draw.circle(surface, CFG.enemy_eye, (eye_x, eye_y), 4)


# ═══════════════════════════ Game ══════════════════════════════

class Game:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_hud   = pygame.font.SysFont("consolas", 24, bold=True)
        self.font_big   = pygame.font.SysFont("consolas", 48, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 22)
        self._load()

    def _load(self) -> None:
        self.tiles, self.enemies, spawn, lw, lh = load_level(LEVEL_MAP)
        self.player  = Player(spawn)
        self.camera  = Camera(lw, lh)
        self.level_w = lw
        self.level_h = lh
        self.total_coins = sum(1 for t in self.tiles if t.kind == TileKind.COIN)

    # ── Main loop ──────────────────────────────────────────────

    def run(self) -> None:
        clock = pygame.time.Clock()
        while True:
            dt = clock.tick(CFG.fps)
            self._handle_events()
            self._update()
            self._draw()

    # ── Events ─────────────────────────────────────────────────

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    pygame.quit(); sys.exit()
                if event.key == pygame.K_r:
                    self._load()

    # ── Update ─────────────────────────────────────────────────

    def _update(self) -> None:
        keys = pygame.key.get_pressed()
        self.player.handle_input(keys)
        self.player.update(self.tiles)

        for enemy in self.enemies:
            enemy.update(self.tiles)
            enemy.check_player(self.player)

        self.camera.follow(self.player.rect)

    # ── Draw ───────────────────────────────────────────────────

    def _draw(self) -> None:
        self._draw_background()
        self._draw_tiles()
        for enemy in self.enemies:
            enemy.draw(self.screen, self.camera)
        self.player.draw(self.screen, self.camera)
        self._draw_hud()

        if not self.player.alive:
            self._draw_overlay("GAME OVER", CFG.dead_color)
        elif self.player.coins >= self.total_coins:
            self._draw_overlay("YOU WIN!", CFG.clear_color)

        pygame.display.flip()

    def _draw_background(self) -> None:
        # Vertical gradient
        for y in range(CFG.screen_h):
            t = y / CFG.screen_h
            r = int(CFG.bg_top[0] + (CFG.bg_bot[0] - CFG.bg_top[0]) * t)
            g = int(CFG.bg_top[1] + (CFG.bg_bot[1] - CFG.bg_top[1]) * t)
            b = int(CFG.bg_top[2] + (CFG.bg_bot[2] - CFG.bg_top[2]) * t)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (CFG.screen_w, y))

    def _draw_tiles(self) -> None:
        for tile in self.tiles:
            sr = self.camera.apply(tile.rect)
            # Cull off-screen
            if sr.right < 0 or sr.left > CFG.screen_w:
                continue
            if sr.bottom < 0 or sr.top > CFG.screen_h:
                continue

            if tile.kind == TileKind.SOLID:
                pygame.draw.rect(self.screen, CFG.tile_color, sr)
                pygame.draw.rect(self.screen, CFG.tile_edge, sr, 2)

            elif tile.kind == TileKind.SPIKE:
                # Draw triangle spike
                pts = [
                    (sr.left + T // 2, sr.top),
                    (sr.left,          sr.bottom),
                    (sr.right,         sr.bottom),
                ]
                pygame.draw.polygon(self.screen, CFG.spike_color, pts)

            elif tile.kind == TileKind.COIN and not tile.collected:
                cx = sr.centerx
                cy = sr.centery
                pygame.draw.circle(self.screen, CFG.coin_color, (cx, cy), T // 3)
                pygame.draw.circle(self.screen, (200, 160, 20), (cx, cy), T // 3, 2)

    def _draw_hud(self) -> None:
        collected = sum(1 for t in self.tiles if t.kind == TileKind.COIN and t.collected)
        text = f"Coins: {collected}/{self.total_coins}"
        surf = self.font_hud.render(text, True, CFG.hud_color)
        self.screen.blit(surf, (12, 10))

        hint = self.font_small.render("[R] Restart  [Q] Quit", True, (120, 120, 140))
        self.screen.blit(hint, (12, CFG.screen_h - 30))

    def _draw_overlay(self, msg: str, color: tuple) -> None:
        overlay = pygame.Surface((CFG.screen_w, CFG.screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        for text, font, dy in [
            (msg,               self.font_big,   -40),
            ("Press R to retry", self.font_small,  30),
        ]:
            surf = font.render(text, True, color)
            rect = surf.get_rect(center=(CFG.screen_w // 2, CFG.screen_h // 2 + dy))
            self.screen.blit(surf, rect)


# ═══════════════════════════ Entry ═════════════════════════════

def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((CFG.screen_w, CFG.screen_h))
    pygame.display.set_caption("Platform Jumper")
    Game(screen).run()


if __name__ == "__main__":
    main()
