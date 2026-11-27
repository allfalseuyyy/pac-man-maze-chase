import argparse
import sys
from pathlib import Path

import pygame

from maze import Level, Round, Tile, move
from panels import Menu, draw_panel, panel_image


TITLE = "Pac-Man Maze Chase"
ROOT = Path(__file__).resolve().parent
DEFAULT_LEVEL = ROOT / "levels" / "config.txt"
KEY_ART = ROOT / "assets" / "kenney_input-prompts_1.5" / "Keyboard & Mouse" / "Double"
MAP_ART = ROOT / "assets" / "kenney_1-bit-pack" / "Tilesheet" / "monochrome-transparent_packed.png"
DUNGEON_PACK = "0x72_DungeonTilesetII_v1.7"
ACTOR_ART = ROOT / "assets" / DUNGEON_PACK / DUNGEON_PACK / "frames"
AUDIO_ART = ROOT / "assets" / "audio" / "Chisper 8-Bit Retro Game Sounds"
INSTRUCTIONS = "Collect every coin! and try to Escape successfully!"
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
        self.height = max(400, BOARD_TOP + level.height * self.tile + 64)
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

    def draw(self, run: Round) -> None:
        self.screen.fill("#0a1419")
        self.label(TITLE, self.heading, INK, topleft=(28, 25))
        self.label(f"PELLETS  {len(run.level.pellets) - len(run.pellets)} / {len(run.level.pellets)}",
                   self.small, GOLD, midleft=(28, 84))
        self.label("EXIT LOCKED" if run.pellets else "EXIT OPEN", self.small,
                   MUTED if run.pellets else MINT, midright=(self.width - 28, 84))
        self.board(run)
        self.key_prompts(self.height - 32, (MOVE_ICONS, "Move"), (("r",), "Restart"),
                         (("escape",), "Settings"))

    def overlay_button(self, has_detail: bool) -> pygame.Rect:
        button = pygame.Rect(0, 0, 220, 42)
        button.center = (self.width // 2, self.height // 2 + (33 if has_detail else 23))
        return button

    def overlay(self, headline: str, detail: str, action: str) -> None:
        x, y = self.width // 2, self.height // 2
        card = pygame.Rect(0, 0, 520, 156)
        card.center = (x, y)
        draw_panel(self.screen, card)
        self.label(headline, self.heading, MINT, center=(x, y - (34 if detail else 18)))
        if detail:
            self.label(detail, self.body, INK, center=(x, y - 3))
        button = self.overlay_button(bool(detail))
        self.screen.blit(panel_image("Colored/blue.png", button.size, "#5c9aab"), button)
        self.key_prompts(button.centery, (("return",), action))


class GameAudio:
    def __init__(self):
        self.volume = 0.7
        self.sounds = {}
        try:
            pygame.mixer.init()
        except pygame.error as error:
            print(f"Audio unavailable: {error}", file=sys.stderr)
            return
        for name in ("coin-pickup", "power-up", "lose-life", "level-complete",
                     "menu-select", "game-start"):
            file = AUDIO_ART / f"8-bit-{name}.wav"
            try:
                self.sounds[name] = pygame.mixer.Sound(file)
            except (pygame.error, OSError) as error:
                print(f"Could not load {file.name}: {error}", file=sys.stderr)
        self.set_volume(self.volume)

    def set_volume(self, value: float) -> None:
        self.volume = value
        for sound in self.sounds.values():
            sound.set_volume(value)

    def play(self, name: str) -> None:
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()


class Game:
    def __init__(self, levels: list[Level], direct: bool):
        self.levels = levels
        self.run = Round(levels[0])
        self.view = View(levels[0])
        self.audio = GameAudio()
        self.page = "intro" if direct else "home"
        self.previous_page = self.page
        level_options = tuple(f"Level {index + 1}" for index in range(len(levels)))
        self.menus = {
            "home": Menu(TITLE, ("Play", "Exit Game")),
            "levels": Menu("Select Level", (*level_options, "Back")),
            "settings": Menu("Settings", ("Volume", "Main Menu", "Exit Game"), self.audio.volume),
        }
        self.elapsed = 0
        self.held: dict[int, Tile] = {}
        self.pending_direction: Tile | None = None

    def change_page(self, page: str) -> None:
        self.page = page
        self.elapsed = 0
        self.pending_direction = None

    def open_level(self, level: Level) -> None:
        if level is not self.run.level:
            self.view = View(level)
        self.run = Round(level)
        self.change_page("intro")

    def handle_menu(self, event: pygame.event.Event, menu: Menu) -> None:
        option = menu.handle(event, self.view.screen)
        if menu.volume is not None and menu.volume != self.audio.volume:
            self.audio.set_volume(menu.volume)
            if event.type != pygame.MOUSEMOTION:
                self.audio.play("menu-select")
        if option is None:
            return
        if self.page == "settings":
            if option == 1:
                self.audio.play("menu-select")
                self.change_page("home")
            elif option == 2:
                self.change_page("quit")
        elif self.page == "home":
            self.audio.play("menu-select")
            self.change_page("levels" if option == 0 else "quit")
        else:
            self.audio.play("menu-select")
            if option == len(self.levels):
                self.change_page("home")
            else:
                self.open_level(self.levels[option])

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.change_page("quit")
            return
        if event.type == pygame.WINDOWFOCUSLOST:
            self.held.clear()
            self.pending_direction = None
        elif event.type == pygame.WINDOWFOCUSGAINED:
            pressed = pygame.key.get_pressed()
            self.held = {key: direction for key, direction in KEYS.items() if pressed[key]}
        elif event.type == pygame.KEYUP:
            self.held.pop(event.key, None)
        elif event.type == pygame.KEYDOWN and event.key in KEYS:
            direction = KEYS[event.key]
            self.held[event.key] = direction
            if self.page == "playing":
                self.pending_direction = direction
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            settings = self.menus["settings"]
            settings.dragging = False
            if self.page == "settings":
                self.change_page(self.previous_page)
            else:
                self.previous_page = self.page
                settings.focus(0)
                self.change_page("settings")
            return
        if self.page in self.menus:
            self.handle_menu(event, self.menus[self.page])
            return
        if self.page in ("intro", "result"):
            confirm = event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
            )
            click = (
                event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.view.overlay_button(self.page == "intro").collidepoint(event.pos)
            )
            if confirm or click:
                if self.page == "intro":
                    self.audio.play("game-start")
                    self.change_page("playing")
                else:
                    self.open_level(self.run.level)
                return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            if self.page in ("playing", "result"):
                self.open_level(self.run.level)

    def update(self, dt: int) -> None:
        if self.page != "playing":
            return
        self.elapsed += min(dt, TICK_MS)
        if self.elapsed < TICK_MS:
            return
        self.elapsed -= TICK_MS
        directions = (self.pending_direction, *reversed(self.held.values()))
        direction = next(
            (step for step in directions
             if step is not None and move(self.run.player, step) in self.run.level.floor),
            (0, 0),
        )
        self.pending_direction = None
        before = len(self.run.pellets)
        self.run.tick(direction)
        if self.run.result:
            self.audio.play("level-complete" if self.run.result == "escaped" else "lose-life")
            self.change_page("result")
        elif len(self.run.pellets) < before:
            self.audio.play("coin-pickup" if self.run.pellets else "power-up")

    def draw(self) -> None:
        view = self.view
        view.draw(self.run)
        if self.page in self.menus:
            hint = "Esc to go back" if self.page == "settings" else ""
            self.menus[self.page].draw(view.screen, view.heading, view.body, view.small, hint)
        elif self.page == "intro":
            view.overlay("How to Play", INSTRUCTIONS, "Start")
        elif self.page == "result":
            if self.run.result == "escaped":
                view.overlay("You escaped", "", "Play again")
            else:
                view.overlay("Caught", "", "Try again")
        pygame.display.flip()


def play(levels: list[Level], direct: bool = False) -> None:
    pygame.display.init()
    pygame.font.init()
    try:
        game = Game(levels, direct)
        clock = pygame.time.Clock()
        while game.page != "quit":
            dt = clock.tick(60)
            for event in pygame.event.get():
                game.handle(event)
                if game.page == "quit":
                    return
            game.update(dt)
            game.draw()
    finally:
        pygame.quit()


def available_levels() -> list[Level]:
    files = sorted(DEFAULT_LEVEL.parent.glob("*.txt"),
                   key=lambda file: (file != DEFAULT_LEVEL, file.name.casefold()))
    levels = []
    for file in files:
        try:
            levels.append(Level.load(file))
        except (OSError, ValueError) as error:
            print(f"Skipping {file.name}: {error}", file=sys.stderr)
    return levels


def main() -> None:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("level", nargs="?", type=Path, help="open a text map directly")
    args = parser.parse_args()
    try:
        levels = [Level.load(args.level)] if args.level else available_levels()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if not levels:
        parser.error(f"No valid maps in {DEFAULT_LEVEL.parent}")
    play(levels, direct=args.level is not None)


if __name__ == "__main__":
    main()
