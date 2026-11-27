from functools import cache
from pathlib import Path

import pygame


ART = Path(__file__).resolve().parent / "assets" / "PixelUIpack" / "9-Slice"
INK = "#e6f2ef"
MUTED = "#bacdce"
MINT = "#66ead3"


@cache
def panel_image(name: str, size: tuple[int, int], tint: str) -> pygame.Surface:
    source = pygame.image.load(ART / name).convert_alpha()
    source.fill(tint, special_flags=pygame.BLEND_RGBA_MULT)
    width, height = size
    image = pygame.Surface(size, pygame.SRCALPHA)
    # The 48 px source contains nine 16 px tiles. Keep the borders at native size.
    for row, (y, h) in enumerate(((0, 16), (16, height - 32), (height - 16, 16))):
        for column, (x, w) in enumerate(((0, 16), (16, width - 32), (width - 16, 16))):
            tile = source.subsurface((column * 16, row * 16, 16, 16))
            image.blit(pygame.transform.scale(tile, (w, h)), (x, y))
    return image


def draw_panel(screen: pygame.Surface, rect: pygame.Rect) -> None:
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((4, 9, 14, 190))
    screen.blit(shade, (0, 0))
    screen.blit(panel_image("space.png", rect.size, "#4b686e"), rect)


class Menu:
    VISIBLE = 4

    def __init__(self, title: str, options: tuple[str, ...], volume: float | None = None):
        self.title = title
        self.options = options
        self.volume = volume
        self.selected = 0
        self.first = 0
        self.dragging = False

    def layout(self, screen: pygame.Surface) -> tuple[pygame.Rect, list[pygame.Rect]]:
        count = min(len(self.options), self.VISIBLE)
        card = pygame.Rect(0, 0, 408, 124 + count * 52)
        card.center = screen.get_rect().center
        rows = [
            pygame.Rect(card.left + 30, card.top + 73 + i * 52, card.width - 60, 42)
            for i in range(count)
        ]
        return card, rows

    def focus(self, index: int) -> None:
        self.selected = max(0, min(index, len(self.options) - 1))
        self.first = min(self.first, self.selected)
        self.first = max(self.first, self.selected - self.VISIBLE + 1)

    @staticmethod
    def volume_track(row: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(row.left + 112, row.centery - 4, row.width - 174, 8)

    def set_volume_at(self, x: int, row: pygame.Rect) -> None:
        track = self.volume_track(row)
        self.volume = max(0.0, min(1.0, (x - track.left) / track.width))

    def handle(self, event: pygame.event.Event, screen: pygame.Surface) -> int | None:
        _, rows = self.layout(screen)
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                self.focus(self.selected + (1 if event.key == pygame.K_DOWN else -1))
            elif self.volume is not None and self.selected == 0 and event.key in (
                pygame.K_LEFT, pygame.K_RIGHT,
            ):
                step = 0.1 if event.key == pygame.K_RIGHT else -0.1
                self.volume = max(0.0, min(1.0, round(self.volume + step, 2)))
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return self.selected
        elif event.type == pygame.MOUSEWHEEL and len(self.options) > self.VISIBLE:
            self.focus(self.selected - event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, row in enumerate(rows, self.first):
                if row.collidepoint(event.pos):
                    self.focus(index)
                    if index == 0 and self.volume is not None:
                        if self.volume_track(row).inflate(14, 20).collidepoint(event.pos):
                            self.dragging = True
                            self.set_volume_at(event.pos[0], row)
                    else:
                        return index
                    break
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.set_volume_at(event.pos[0], rows[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.dragging = False
        return None

    def draw(self, screen, heading, body, small, hint: str = "") -> None:
        card, rows = self.layout(screen)
        draw_panel(screen, card)
        title = heading.render(self.title, True, MINT)
        screen.blit(title, title.get_rect(center=(card.centerx, card.top + 38)))
        for index, row in enumerate(rows, self.first):
            selected = index == self.selected
            tint = "#5c9aab" if selected else "#3a5965"
            screen.blit(panel_image("Colored/blue.png", row.size, tint), row)
            label = body.render(self.options[index], True, INK)
            if index == 0 and self.volume is not None:
                screen.blit(label, label.get_rect(midleft=(row.left + 17, row.centery)))
                track = self.volume_track(row)
                pygame.draw.rect(screen, "#172c34", track)
                fill = track.copy()
                fill.width = round(track.width * self.volume)
                pygame.draw.rect(screen, MINT, fill)
                pygame.draw.rect(screen, INK, (fill.right - 3, track.top - 4, 6, 16))
                value = small.render(f"{self.volume:.0%}", True, INK)
                screen.blit(value, value.get_rect(midright=(row.right - 15, row.centery)))
            else:
                screen.blit(label, label.get_rect(center=row.center))
        if len(self.options) > self.VISIBLE:
            hint = f"{self.selected + 1} / {len(self.options)}    |    Use arrows or scroll"
        if hint:
            footer = small.render(hint, True, MUTED)
            screen.blit(footer, footer.get_rect(center=(card.centerx, card.bottom - 23)))
