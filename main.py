import argparse
from pathlib import Path

import pygame

from maze import Level, Round, Tile


TITLE = "Pac-Man Maze Chase"
ROOT = Path(__file__).resolve().parent
DEFAULT_LEVEL = ROOT / "levels" / "config.txt"
KEY_ART = ROOT / "assets" / "kenney_input-prompts_1.5" / "Keyboard & Mouse" / "Double"
MAP_ART = ROOT / "assets" / "kenney_1-bit-pack" / "Tilesheet" / "monochrome-transparent_packed.png"
DUNGEON_PACK = "0x72_DungeonTilesetII_v1.7"
ACTOR_ART = ROOT / "assets" / DUNGEON_PACK / DUNGEON_PACK / "frames"
MOVE_ICONS = ("arrow_up", "arrow_left", "arrow_down", "arrow_right")
TICK_MS = 145
BOARD_TOP = 116
INK = "#e6f2ef"
MUTED = "#9db3b3"
MINT = "#66ead3"
GOLD = "#ffc16c"
KEYS = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
}


def map_sprite(sheet, column, row, color, size):
    tile = sheet.subsurface((column * 16, row * 16, 16, 16)).copy()
    tile.fill(color, special_flags=pygame.BLEND_RGBA_MULT)
    return pygame.transform.scale(tile, (size, size))


def actor_frames(name, size):
    frames = [
        pygame.image.load(ACTOR_ART / f"{name}_idle_anim_f{index}.png").convert_alpha()
        for index in range(4)
    ]
    visible = frames[0].get_bounding_rect().unionall(
        [frame.get_bounding_rect() for frame in frames[1:]]
    )
    scale = (size - 4) / max(visible.size)
    dimensions = tuple(max(1, round(length * scale)) for length in visible.size)
    right = tuple(pygame.transform.scale(frame.subsurface(visible), dimensions) for frame in frames)
    left = tuple(pygame.transform.flip(frame, True, False) for frame in right)
    return right, left


class View:
    def __init__(self, level: Level):
        self.tile = min(32, 880 // level.width, 512 // level.height)
        board_width = level.width * self.tile
        self.width = max(600, board_width + 56)
        self.height = BOARD_TOP + level.height * self.tile + 64
        self.left = (self.width - board_width) // 2
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(f"吃豆人迷宫追逐 · {TITLE}")
        self.heading = pygame.font.Font(None, 42)
        self.body = pygame.font.Font(None, 24)
        self.small = pygame.font.Font(None, 20)
        self.key_icons = {}
        for name in (*MOVE_ICONS, "return", "r", "escape"):
            icon = pygame.image.load(KEY_ART / f"keyboard_{name}.png").convert_alpha()
            icon = icon.subsurface(icon.get_bounding_rect())
            self.key_icons[name] = pygame.transform.smoothscale(icon, (28, 28))

        sheet = pygame.image.load(MAP_ART).convert_alpha()
        self.wall = map_sprite(sheet, 7, 15, "#426773", self.tile)
        self.floor = map_sprite(sheet, 18, 3, "#243940", self.tile)
        self.pellet = map_sprite(sheet, 14, 5, GOLD, self.tile // 3)
        self.locked_gate = map_sprite(sheet, 0, 11, "#68838a", self.tile * 3 // 4)
        self.open_gate = map_sprite(sheet, 8, 10, MINT, self.tile * 3 // 4)
        self.player_art = actor_frames("knight_f", self.tile)
        self.guard_art = actor_frames("masked_orc", self.tile)
        self.chaser_art = actor_frames("imp", self.tile)

    def label(self, text, font, color, **position):
        image = font.render(text, True, color)
        self.screen.blit(image, image.get_rect(**position))

    def key_prompts(self, y: int, *groups: tuple[tuple[str, ...], str]) -> None:
        row = []
        for keys, action in groups:
            row.extend((self.key_icons[key], 4) for key in keys)
            row.append((self.small.render(action, True, INK), 22))
        width = sum(image.get_width() + gap for image, gap in row) - row[-1][1]
        x = (self.width - width) // 2
        for image, gap in row:
            self.screen.blit(image, image.get_rect(midleft=(x, y)))
            x += image.get_width() + gap

    def cell(self, tile: Tile) -> pygame.Rect:
        x, y = tile
        return pygame.Rect(self.left + x * self.tile, BOARD_TOP + y * self.tile, self.tile, self.tile)

    def draw_actor(self, frames, tile, frame, color, facing_left):
        x, y = self.cell(tile).center
        ring = pygame.Rect(0, 0, self.tile - 4, max(5, self.tile // 4))
        ring.center = (x, y + self.tile // 3)
        pygame.draw.ellipse(self.screen, color, ring, 1)
        right, left = frames
        image = (left if facing_left else right)[frame]
        self.screen.blit(image, image.get_rect(center=(x, y)))

    def board(self, run: Round) -> None:
        size = self.tile
        board = pygame.Rect(self.left, BOARD_TOP, run.level.width * size, run.level.height * size)
        pygame.draw.rect(self.screen, "#111e25", board.inflate(12, 12), border_radius=8)
        for y in range(run.level.height):
            for x in range(run.level.width):
                tile = x, y
                cell = self.cell(tile)
                if tile in run.level.floor:
                    color = "#101b21" if (x + y) % 2 else "#132027"
                    pygame.draw.rect(self.screen, color, cell)
                    self.screen.blit(self.floor, cell)
                else:
                    pygame.draw.rect(self.screen, "#273e48", cell)
                    self.screen.blit(self.wall, cell)

        for tile in run.pellets:
            self.screen.blit(self.pellet, self.pellet.get_rect(center=self.cell(tile).center))

        gate = self.locked_gate if run.pellets else self.open_gate
        self.screen.blit(gate, gate.get_rect(center=self.cell(run.level.exit).center))

        frame = run.ticks % 4
        if run.guard is not None:
            self.draw_actor(self.guard_art, run.guard, frame, "#bd98ff", run.guard_facing_left)
        if run.chaser is not None:
            self.draw_actor(self.chaser_art, run.chaser, frame, "#ff8278", run.chaser_facing_left)
        self.draw_actor(self.player_art, run.player, frame, MINT, run.player_facing_left)

    def draw(self, run: Round, started: bool) -> None:
        self.screen.fill("#0a1419")
        self.label(TITLE, self.heading, INK, topleft=(28, 25))
        self.label(f"PELLETS  {len(run.level.pellets) - len(run.pellets)} / {len(run.level.pellets)}",
                   self.small, GOLD, midleft=(28, 84))
        self.label("EXIT LOCKED" if run.pellets else "EXIT OPEN", self.small,
                   MUTED if run.pellets else MINT, midright=(self.width - 28, 84))
        self.board(run)
        self.key_prompts(self.height - 32, (MOVE_ICONS, "Move"), (("r",), "Restart"),
                         (("escape",), "Quit"))
        if not started or run.result:
            if run.result == "escaped":
                self.overlay("You escaped", "", "Play again")
            elif run.result == "caught":
                self.overlay("Caught", "", "Try again")
            else:
                self.overlay("Collect every pellet", "Reach the gate to escape", "Start")
        pygame.display.flip()

    def overlay(self, headline: str, detail: str, action: str) -> None:
        shade = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        shade.fill((4, 9, 14, 182))
        self.screen.blit(shade, (0, 0))
        x, y = self.width // 2, self.height // 2
        card = pygame.Rect(0, 0, 410, 132)
        card.center = (x, y)
        pygame.draw.rect(self.screen, "#15262d", card, border_radius=12)
        pygame.draw.rect(self.screen, "#385359", card, width=1, border_radius=12)
        self.label(headline, self.heading, MINT, center=(x, y - (34 if detail else 18)))
        if detail:
            self.label(detail, self.body, INK, center=(x, y - 3))
        self.key_prompts(y + (33 if detail else 23), (("return",), action))


def play(level: Level) -> None:
    pygame.display.init()
    pygame.font.init()
    try:
        view = View(level)
        clock = pygame.time.Clock()
        run = Round(level)
        started = False
        elapsed = 0
        held: dict[int, Tile] = {}
        pending_direction: Tile | None = None

        while True:
            elapsed += min(clock.tick(60), TICK_MS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.WINDOWFOCUSLOST:
                    held.clear()
                    pending_direction = None
                if event.type == pygame.KEYUP:
                    held.pop(event.key, None)
                if event.type != pygame.KEYDOWN:
                    continue
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key == pygame.K_r or (
                    event.key == pygame.K_RETURN and (not started or run.result)
                ):
                    run = Round(level)
                    started = True
                    elapsed = 0
                    pending_direction = None
                if event.key in KEYS:
                    pending_direction = KEYS[event.key]
                    held[event.key] = pending_direction

            if started and elapsed >= TICK_MS:
                elapsed -= TICK_MS
                direction = pending_direction or next(reversed(held.values()), (0, 0))
                run.tick(direction)
                pending_direction = None
            view.draw(run, started)
    finally:
        pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("level", nargs="?", type=Path, default=DEFAULT_LEVEL, help="path to a text map")
    args = parser.parse_args()
    try:
        level = Level.load(args.level)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    play(level)


if __name__ == "__main__":
    main()
