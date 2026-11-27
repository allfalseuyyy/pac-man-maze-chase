from collections import deque
from dataclasses import dataclass
from pathlib import Path


Tile = tuple[int, int]
DIRECTIONS = ((0, -1), (-1, 0), (0, 1), (1, 0))


def move(tile: Tile, direction: Tile) -> Tile:
    return tile[0] + direction[0], tile[1] + direction[1]


@dataclass(frozen=True)
class Level:
    width: int
    height: int
    floor: frozenset[Tile]
    pellets: frozenset[Tile]
    start: Tile
    exit: Tile
    chaser: Tile | None
    patrol: tuple[Tile, Tile] | None

    @classmethod
    def load(cls, path: Path) -> "Level":
        rows = path.read_text(encoding="utf-8-sig").splitlines()
        if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("The map must be a nonempty rectangle.")
        if len(rows) > 32 or len(rows[0]) > 55:
            raise ValueError("Use a map no larger than 55 columns by 32 rows.")

        tiles: dict[str, set[Tile]] = {symbol: set() for symbol in "#_.PECGO"}
        for y, row in enumerate(rows):
            for x, symbol in enumerate(row):
                if symbol not in tiles:
                    raise ValueError(f"Unknown tile {symbol!r} at row {y + 1}, column {x + 1}.")
                tiles[symbol].add((x, y))

        if len(tiles["P"]) != 1 or len(tiles["E"]) != 1 or not tiles["."]:
            raise ValueError("Use one P, one E, and at least one pellet (.).")
        if len(tiles["C"]) > 1 or len(tiles["G"]) != len(tiles["O"]) or len(tiles["G"]) > 1:
            raise ValueError("Use at most one C and either one G/O pair or neither.")

        floor = frozenset().union(*(cells for symbol, cells in tiles.items() if symbol != "#"))
        start = next(iter(tiles["P"]))
        if reachable(start, floor) != floor:
            raise ValueError("Every walkable tile must be reachable from P.")

        patrol = (next(iter(tiles["G"])), next(iter(tiles["O"]))) if tiles["G"] else None
        return cls(
            len(rows[0]), len(rows), floor, frozenset(tiles["."]), start,
            next(iter(tiles["E"])), next(iter(tiles["C"]), None), patrol,
        )


def reachable(start: Tile, floor: frozenset[Tile]) -> set[Tile]:
    seen = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for direction in DIRECTIONS:
            neighbor = move(current, direction)
            if neighbor in floor and neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def next_step(start: Tile, target: Tile, floor: frozenset[Tile]) -> Tile:
    first_steps = {start: start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == target:
            return first_steps[current]
        for direction in DIRECTIONS:
            neighbor = move(current, direction)
            if neighbor in floor and neighbor not in first_steps:
                first_steps[neighbor] = neighbor if current == start else first_steps[current]
                queue.append(neighbor)
    return start


class Round:
    def __init__(self, level: Level):
        self.level = level
        self.player = level.start
        self.player_facing_left = False
        self.pellets = set(level.pellets)
        self.chaser = level.chaser
        self.guard = level.patrol[0] if level.patrol else None
        self.chaser_facing_left = False
        self.guard_facing_left = False
        self.guard_goal = 1
        self.ticks = 0
        self.result: str | None = None

    def tick(self, direction: Tile) -> None:
        if self.result:
            return
        self.ticks += 1
        destination = move(self.player, direction)
        if destination in self.level.floor:
            self.player = destination
            if direction[0]:
                self.player_facing_left = direction[0] < 0
        if self.caught():
            self.result = "caught"
            return

        self.pellets.discard(self.player)
        if not self.pellets and self.player == self.level.exit:
            self.result = "escaped"
            return

        if self.chaser is not None and (self.ticks - 1) * 8 % 15 < 8:
            step = next_step(self.chaser, self.player, self.level.floor)
            if step[0] != self.chaser[0]:
                self.chaser_facing_left = step[0] < self.chaser[0]
            self.chaser = step
        if self.guard is not None and self.level.patrol and self.ticks % 2 == 0:
            goal = self.level.patrol[self.guard_goal]
            step = next_step(self.guard, goal, self.level.floor)
            if step[0] != self.guard[0]:
                self.guard_facing_left = step[0] < self.guard[0]
            self.guard = step
            if self.guard == goal:
                self.guard_goal = 1 - self.guard_goal
        if self.caught():
            self.result = "caught"

    def caught(self) -> bool:
        return self.player in (self.chaser, self.guard)
