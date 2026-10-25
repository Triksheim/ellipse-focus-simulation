"""Ellipse reflection demo. Run: python ellipse_demo.py

Requires Pillow (python -m pip install Pillow). Particles are ideal points: no friction,
no particle-particle collisions, and perfectly elastic wall reflections.
"""

from __future__ import annotations

import argparse
import colorsys
import math
import time
from dataclasses import dataclass, field

DEFAULT_MAX_BALLS = 512
MAX_BALLS = 16384
MAX_LAUNCH_AMOUNT = 128
DEFAULT_ECCENTRICITY = 0.8
TRAIL_STEPS = 8
BASE_SPEED = 9 / 7
IMPACT_DURATION = 0.60


@dataclass(frozen=True)
class Trajectory:
    start: tuple[float, float]
    hit: tuple[float, float]
    outgoing: tuple[float, float]
    first_length: float
    second_length: float

    @property
    def total_length(self) -> float:
        return self.first_length + self.second_length

    def position(self, distance: float) -> tuple[float, float]:
        distance = max(0.0, min(distance, self.total_length))
        if distance <= self.first_length:
            fraction = distance / self.first_length
            return tuple(self.start[i] + fraction * (self.hit[i] - self.start[i])
                         for i in range(2))
        remaining = distance - self.first_length
        return tuple(self.hit[i] + remaining * self.outgoing[i] for i in range(2))


def make_trajectories(eccentricity: float, count: int, angle_offset: float = 0.0) -> list[Trajectory]:
    """Intersect rays with x²/a² + y²/b² = 1, then reflect about its normal.

    The semimajor axis a is 1; c = a*eccentricity and b² = a²-c².
    Reflected directions follow v' = v - 2(v dot n)n.
    """
    if not 0 <= eccentricity < 1:
        raise ValueError('Eccentricity must be at least 0 and below 1.')
    if count < 1:
        raise ValueError('At least one particle is required.')
    return [trace_trajectory(eccentricity, (-eccentricity, 0.0), angle+angle_offset)
            for angle in symmetric_angles(count)]


def symmetric_angles(count: int) -> list[float]:
    """Evenly spaced directions paired above and below the ellipse's long axis."""
    return [2 * math.pi * (index + 0.5) / count for index in range(count)]


def trace_trajectory(eccentricity: float, start: tuple[float, float],
                     angle: float) -> Trajectory:
    """Trace one pass from either focus, using the physical reflection law."""
    b2 = 1 - eccentricity**2
    vx, vy = math.cos(angle), math.sin(angle)
    qa = vx*vx + vy*vy / b2
    qb = 2 * start[0] * vx
    qc = start[0]**2 - 1
    discriminant = math.sqrt(qb*qb - 4*qa*qc)
    distance = (-2*qc / (qb + discriminant) if qb >= 0
                else (-qb + discriminant) / (2*qa))
    hit = (start[0] + distance*vx, distance*vy)
    nx, ny = hit[0], hit[1] / b2
    normal_length = math.hypot(nx, ny)
    nx, ny = nx / normal_length, ny / normal_length
    dot = vx*nx + vy*ny
    outgoing = (vx - 2*dot*nx, vy - 2*dot*ny)
    second_length = math.hypot(hit[0] + start[0], hit[1])
    return Trajectory(start, hit, outgoing, distance, second_length)


def aim_trajectory(eccentricity: float, target: tuple[float, float]):
    """Launch from the closest focus toward a point in ellipse coordinates."""
    start = min(((-eccentricity, 0.0), (eccentricity, 0.0)),
                key=lambda focus: math.dist(focus, target))
    dx, dy = target[0]-start[0], target[1]-start[1]
    if math.hypot(dx, dy) < 1e-10:
        return None
    return trace_trajectory(eccentricity, start, math.atan2(dy, dx))


def reverse_trajectory(ray):
    incoming = ((ray.hit[0]-ray.start[0])/ray.first_length,
                (ray.hit[1]-ray.start[1])/ray.first_length)
    return Trajectory((-ray.start[0], 0.0), ray.hit,
                      (-incoming[0], -incoming[1]), ray.second_length, ray.first_length)


def advance_clock(distance, arrival_hold, dt, speed):
    passes = 0
    while dt > 1e-12:
        if distance < 2:
            remaining = (2-distance)/(BASE_SPEED*speed)
            used = min(dt, remaining)
            distance = min(2.0, distance+used*BASE_SPEED*speed)
            dt -= used
            if used < remaining:
                break
            distance = 2.0
        used = min(dt, 0.45-arrival_hold)
        arrival_hold += used
        dt -= used
        if arrival_hold < 0.45-1e-12:
            break
        distance = arrival_hold = 0.0
        passes += 1
    return distance, arrival_hold, passes


@dataclass
class Shot:
    """An independently timed ball with cached outward and return paths."""

    ray: Trajectory
    eccentricity: float
    distance: float = 0.0
    arrival_hold: float = 0.0
    return_ray: Trajectory = field(init=False, repr=False)

    def __post_init__(self):
        self.return_ray = reverse_trajectory(self.ray)

    def advance(self, dt: float, speed: float) -> bool:
        self.distance, self.arrival_hold, passes = advance_clock(
            self.distance, self.arrival_hold, dt, speed)
        if passes % 2:
            # Alternate between the cached outward and return paths.
            self.ray, self.return_ray = self.return_ray, self.ray
        return passes > 0


@dataclass
class BallBatch:
    """A launch shares one clock; separate clicks retain independent clocks."""

    rays: list[Trajectory]
    eccentricity: float
    distance: float = 0.0
    arrival_hold: float = 0.0
    revision: int = 0
    completed_passes: int = 0

    def __post_init__(self):
        self.colors = rainbow_colors(self.rays)
        self.return_rays = [reverse_trajectory(ray) for ray in self.rays]

    def advance(self, dt, speed, duplicate=False, extra_capacity=0, collect_events=False):
        old_distance = self.distance
        self.distance, self.arrival_hold, passes = advance_clock(
            self.distance, self.arrival_hold, dt, speed)
        self.wall_hits = self.focus_launches = 0
        if collect_events:
            end = 2 if passes else self.distance
            self.wall_hits = sum(old_distance < ray.first_length <= end for ray in self.rays)
        limit = len(self.rays)+extra_capacity
        for pass_index in range(passes):
            if duplicate:
                self.rays = next_pass(self.eccentricity, self.rays, True, limit=limit)
                self.colors = rainbow_colors(self.rays)
                self.return_rays = [reverse_trajectory(ray) for ray in self.rays]
            else:
                self.rays, self.return_rays = self.return_rays, self.rays
            if collect_events:
                self.focus_launches += len(self.rays)
                self.wall_hits += (len(self.rays) if pass_index < passes-1 else
                                   sum(ray.first_length <= self.distance for ray in self.rays))
        if passes:
            self.revision += 1
            self.completed_passes += passes
        return passes > 0


class Simulation:
    """One shared simulation for Run launches, click shots and duplication."""

    def __init__(self, eccentricity=DEFAULT_ECCENTRICITY, limit=DEFAULT_MAX_BALLS):
        self.eccentricity = eccentricity
        self.set_limit(limit)
        self.batches = []
        self.launch_index = 0
        self.last_events = (0, 0)

    def set_limit(self, limit):
        if not isinstance(limit, int) or not 1 <= limit <= MAX_BALLS:
            raise ValueError(f'Ball limit must be between 1 and {MAX_BALLS}.')
        self.limit = limit

    @property
    def count(self):
        return sum(len(batch.rays) for batch in self.batches)

    def launch(self, count):
        count = min(count, self.limit-self.count)
        if count < 1:
            return False
        # Space successive launch fans using an irrational angular offset.
        spacing = 2*math.pi/count
        offset = (self.launch_index * ((3-math.sqrt(5))/2) * spacing) % (2*math.pi)
        rays = make_trajectories(self.eccentricity, count, angle_offset=offset)
        self.batches.append(BallBatch(rays, self.eccentricity))
        self.launch_index += 1
        return True

    def shoot(self, target):
        if self.count >= self.limit:
            return False
        ray = aim_trajectory(self.eccentricity, target)
        if ray is None:
            return False
        self.batches.append(BallBatch([ray], self.eccentricity))
        return True

    def advance(self, dt, speed, duplicate=False, collect_events=False):
        free = max(0, self.limit-self.count)
        changed = False
        wall_hits = focus_launches = 0
        for batch in self.batches:
            before = len(batch.rays)
            changed = batch.advance(dt, speed, duplicate, free, collect_events) or changed
            free -= len(batch.rays)-before
            if collect_events:
                wall_hits += batch.wall_hits
                focus_launches += batch.focus_launches
        self.last_events = (wall_hits, focus_launches)
        return changed

    def states(self):
        values = []
        for batch in self.batches:
            values.extend([(batch.distance, batch.arrival_hold)]*len(batch.rays))
        return values


def next_pass(eccentricity: float, rays: list[Trajectory], duplicate: bool,
              limit: int = DEFAULT_MAX_BALLS) -> list[Trajectory]:
    """Build a pass with symmetric splits around each parent's return heading.

    Each duplicated parent produces two children at equal opposite offsets from
    its retracing direction. Split offsets narrow as the population grows.
    At the count limit, balls retrace their paths.
    With duplication off, balls keep their physical arrival directions.
    """
    start = (-rays[0].start[0], 0.0)
    if duplicate:
        copies = min(len(rays), max(0, limit-len(rays)))
        if not copies:
            return [reverse_trajectory(ray) for ray in rays]
        # Select mirrored parents together where capacity permits; each split
        # itself remains exactly symmetric even when the global cap is partial.
        split = set()
        for index in range(len(rays)//2):
            if len(split)+2 <= copies:
                split.update((index, len(rays)-1-index))
        if len(split) < copies:
            middle = len(rays)//2
            split.add(middle if len(rays) % 2 else
                      next(index for index in range(len(rays)) if index not in split))
        offset = math.radians(28)/math.sqrt(len(rays))
        result = []
        for index, ray in enumerate(rays):
            if index in split:
                center = math.atan2(-ray.outgoing[1], -ray.outgoing[0])
                result.extend(trace_trajectory(eccentricity, start, center+sign*offset)
                              for sign in (-1, 1))
            else:
                result.append(reverse_trajectory(ray))
        return result
    else:
        angles = [math.atan2(ray.outgoing[1], ray.outgoing[0]) for ray in rays]
    return [trace_trajectory(eccentricity, start, angle) for angle in angles]


def rainbow_colors(rays: list[Trajectory]) -> list[str]:
    """Follow the color wheel around the launch directions."""
    colors = []
    for ray in rays:
        angle = math.atan2(ray.hit[1], ray.hit[0] - ray.start[0])
        hue = (angle / (2 * math.pi)) % 1.0
        rgb = colorsys.hsv_to_rgb(hue, 0.65, 1.0)
        colors.append('#' + ''.join(f'{round(channel * 255):02x}' for channel in rgb))
    return colors


def impact_progress(ray: Trajectory, distance: float, arrival_hold: float = 0.0):
    """Animation phase of a wall pulse, or None when no recent hit occurred."""
    age = (distance - ray.first_length) / BASE_SPEED + arrival_hold
    return age / IMPACT_DURATION if 0 <= age < IMPACT_DURATION else None


def trail_sections(ray: Trajectory, distance: float, length: float):
    """Compute fading-tail sections through a wall reflection.

    Distances beyond arrival drain the trail into the stationary endpoint.
    """
    sections = []
    for index in range(TRAIL_STEPS):
        start = distance - length + length * index / TRAIL_STEPS
        end = distance - length + length * (index + 1) / TRAIL_STEPS
        points = [ray.position(start)]
        if start < ray.first_length < end:
            points.append(ray.hit)
        points.append(ray.position(end))
        sections.append(points)
    return sections


def trail_color(color: str, background: str, opacity: float) -> str:
    """Blend a tail shade into the canvas; Tk lines do not support alpha."""
    channels = []
    for offset in (1, 3, 5):
        foreground = int(color[offset:offset + 2], 16)
        base = int(background[offset:offset + 2], 16)
        channels.append(round(base + (foreground - base) * opacity))
    return '#' + ''.join(f'{channel:02x}' for channel in channels)


class RasterRenderer:
    """Render balls, trails and wall impacts into a single image."""

    def __init__(self, background='#0b121a'):
        from PIL import Image, ImageDraw
        self.Image, self.ImageDraw = Image, ImageDraw
        self.background_color = background
        self.background = None
        self.rows = []

    def prepare(self, rays, colors, width, height, eccentricity):
        """Cache screen geometry and fade palettes once per pass or resize."""
        self.width, self.height = width, height
        b = math.sqrt(1 - eccentricity**2)
        scale = max(1, min((width-90)/2, (height-100)/(2*b)))
        cx, cy = width/2, height/2
        self.scale, self.center = scale, (cx, cy)
        self.eccentricity = eccentricity
        self.tail_length = 2.0
        self.background = self.Image.new('RGB', (width, height), self.background_color)
        draw = self.ImageDraw.Draw(self.background)
        draw.ellipse((cx-scale, cy-b*scale, cx+scale, cy+b*scale),
                     outline='#92adbf', width=2)
        self.foci = ((cx-eccentricity*scale, cy), (cx+eccentricity*scale, cy))
        self.rows = [self.prepare_ray(ray, color) for ray, color in zip(rays, colors)]
        # Cache flash shades for each animation phase.
        self.flash_palette = []
        rgb = lambda value: tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
        for step in range(64):
            phase = step / 63
            brightness = (1 - max(0.0, (phase-0.25)/0.75))**0.7
            self.flash_palette.append(tuple(
                rgb(trail_color(color, self.background_color, opacity*brightness))
                for color, opacity in (('#ffd83d', 0.28), ('#ffdf45', 0.7), ('#fff16a', 1.0))))

    def prepare_ray(self, ray, color):
        """Cache screen geometry and the fade palette for one path."""
        scale = self.scale
        cx, cy = self.center
        sx, sy = cx+ray.start[0]*scale, cy-ray.start[1]*scale
        hx, hy = cx+ray.hit[0]*scale, cy-ray.hit[1]*scale
        ix, iy = (hx-sx)/ray.first_length, (hy-sy)/ray.first_length
        ox, oy = ray.outgoing[0]*scale, -ray.outgoing[1]*scale
        nx, ny = ray.hit[0], ray.hit[1]/(1-self.eccentricity**2)
        norm = math.hypot(nx, ny)
        rgb = lambda value: tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
        palette = tuple(rgb(trail_color(color, self.background_color,
                                       0.04+0.66*(step/(TRAIL_STEPS-1))**1.2))
                        for step in range(TRAIL_STEPS))
        return (sx, sy, hx, hy, ix, iy, ox, oy, ray.first_length,
                -ny/norm, -nx/norm, rgb(color), palette)

    def world_point(self, x, y):
        return ((x-self.center[0])/self.scale, (self.center[1]-y)/self.scale)

    def render(self, distance, arrival_hold=0.0, states=None):
        """Draw all balls, fading trails and wall impacts."""
        frame = self.background.copy()
        draw = self.ImageDraw.Draw(frame)
        line, ellipse = draw.line, draw.ellipse
        length = self.tail_length
        head = distance + arrival_hold*length/0.45
        samples = tuple(max(0.0, min(2.0, head-length+length*i/TRAIL_STEPS))
                        for i in range(TRAIL_STEPS+1))
        balls, impacts = [], []
        previous_state = None
        for row_index, row in enumerate(self.rows):
            sx, sy, hx, hy, ix, iy, ox, oy, bounce, tx, ty, color, palette = row
            if states is not None:
                state = states[row_index]
                distance, arrival_hold = state
                if state != previous_state:
                    head = distance+arrival_hold*length/0.45
                    samples = tuple(max(0.0, min(2.0, head-length+length*i/TRAIL_STEPS))
                                    for i in range(TRAIL_STEPS+1))
                    previous_state = state
            # Evaluate shared sample positions once per ball.
            points = []
            for sample in samples:
                if sample <= bounce:
                    points.append((sx+ix*sample, sy+iy*sample))
                else:
                    remaining = sample-bounce
                    points.append((hx+ox*remaining, hy+oy*remaining))
            for index, shade in enumerate(palette):
                first, last = points[index], points[index+1]
                if first == last:
                    continue
                if samples[index] < bounce < samples[index+1]:
                    line((first, (hx, hy), last), fill=shade, width=1)
                else:
                    line((first, last), fill=shade, width=1)
            balls.append((*points[-1], color))
            age = (distance-bounce)/BASE_SPEED + arrival_hold
            if 0 <= age < IMPACT_DURATION:
                impacts.append((hx, hy, tx, ty, age/IMPACT_DURATION))
        for x, y in self.foci:
            ellipse((x-13, y-13, x+13, y+13), outline='#304a54', width=3)
            ellipse((x-8, y-8, x+8, y+8), fill=self.background_color,
                    outline='#ffdc82', width=2)
            ellipse((x-2.5, y-2.5, x+2.5, y+2.5), fill='#fff0bb')
        for x, y, color in balls:
            ellipse((x-3, y-3, x+3, y+3), fill=color)
        for x, y, tx, ty, phase in impacts:
            glow, ring, core = self.flash_palette[min(63, int(phase*63))]
            radius = 6+3*phase
            endpoints = (x-tx*radius, y-ty*radius, x+tx*radius, y+ty*radius)
            line(endpoints, fill=glow, width=10)
            ring_radius = 4+8*phase
            ellipse((x-ring_radius, y-ring_radius, x+ring_radius, y+ring_radius),
                    outline=ring, width=2)
            line(endpoints, fill=core, width=3)
        return frame


def self_test() -> None:
    """Check geometry, reflection and simultaneous arrival without opening a GUI."""
    checked = 0
    for eccentricity in (0.0, 0.01, 0.1, 0.5, 0.7, 0.9, 0.99):
        b2 = 1 - eccentricity**2
        for ray in make_trajectories(eccentricity, 181):
            x, y = ray.hit
            assert math.isclose(x*x + y*y / b2, 1, abs_tol=1e-10)
            assert math.isclose(math.hypot(*ray.outgoing), 1, abs_tol=1e-10)
            assert math.isclose(ray.total_length, 2, abs_tol=1e-10)
            end = ray.position(2)
            assert math.hypot(end[0] - eccentricity, end[1]) < 1e-9
            assert ray.position(-1) == ray.start
            assert ray.position(3) == ray.position(ray.total_length)
            # Incident and reflected normal components have opposite signs.
            normal = (x, y / b2)
            incoming = tuple((ray.hit[i] - ray.start[i]) / ray.first_length
                             for i in range(2))
            dot_in = sum(incoming[i] * normal[i] for i in range(2))
            dot_out = sum(ray.outgoing[i] * normal[i] for i in range(2))
            assert math.isclose(dot_in, -dot_out, abs_tol=1e-10)
            midpoint = ray.position(ray.first_length / 2)
            assert math.isclose(midpoint[0], (ray.start[0] + x) / 2, abs_tol=1e-10)
            checked += 1
    # Exercise several alternating passes, including duplication, its limit,
    # switching it off, and preserving velocity when duplication is disabled.
    rays = make_trajectories(0.7, 1)
    for expected in (2, 4, 8, 16, 17):
        previous = rays
        rays = next_pass(0.7, rays, True, limit=17)
        assert len(rays) == expected
        for ray in rays:
            assert ray.start == (-previous[0].start[0], 0.0)
            assert math.isclose(ray.total_length, 2, abs_tol=1e-10)
            end = ray.position(2)
            assert math.hypot(end[0] + ray.start[0], end[1]) < 1e-9
    assert len(next_pass(0.7, rays, True, limit=17)) == 17
    continued = next_pass(0.7, rays, False)
    assert len(continued) == 17
    for previous, ray in zip(rays, continued):
        incoming = tuple((ray.hit[i] - ray.start[i]) / ray.first_length
                         for i in range(2))
        assert math.dist(incoming, previous.outgoing) < 1e-10
    # Check distinct directions through duplication and passes at the count limit.
    rays = make_trajectories(0.7, 1)
    for pass_index in range(14):
        rays = next_pass(0.7, rays, True, limit=1024)
        assert len(rays) == min(2 ** (pass_index + 1), 1024)
        angles = sorted(math.atan2(ray.hit[1], ray.hit[0] - ray.start[0])
                        % (2 * math.pi) for ray in rays)
        assert len(set(round(angle, 11) for angle in angles)) == len(rays)
        for ray in rays:
            assert math.isclose(ray.total_length, 2, abs_tol=1e-10)
            assert math.dist(ray.position(2), (-ray.start[0], 0.0)) < 1e-9
    for count in (1, 2, MAX_BALLS):
        assert len(make_trajectories(0.7, count)) == count
    # Mirrored launch angles must stay mirrored through the wall bounce and
    # convergence, for both odd and even counts and either launch focus.
    for count in (1, 2, 3, 5, 34, 89, 1024):
        rays = make_trajectories(0.7, count)
        for _ in range(3):
            for ray, mirror in zip(rays, reversed(rays)):
                for distance in (0.1, 0.6, 1.2, 1.8):
                    x, y = ray.position(distance)
                    mx, my = mirror.position(distance)
                    assert math.isclose(x, mx, abs_tol=1e-10)
                    assert math.isclose(y, -my, abs_tol=1e-10)
            rays = next_pass(0.7, rays, True)
    ray = make_trajectories(0.7, 3)[0]
    sections = trail_sections(ray, ray.first_length + 0.025, 0.12)
    assert any(ray.hit in section for section in sections)
    assert sections[-1][-1] == ray.position(ray.first_length + 0.025)
    assert all(point == ray.start for section in trail_sections(ray, 0, 0.12)
               for point in section)
    assert all(point == ray.position(2) for section in trail_sections(ray, 2.2, 0.12)
               for point in section)
    assert impact_progress(ray, ray.first_length - 0.001) is None
    assert impact_progress(ray, ray.first_length) == 0
    assert math.isclose(impact_progress(ray, ray.first_length + BASE_SPEED * 0.30),
                        0.5, abs_tol=1e-10)
    assert impact_progress(ray, ray.first_length + BASE_SPEED * 0.7) is None
    assert impact_progress(ray, ray.first_length, arrival_hold=0.7) is None
    print(f'PASS: {checked} trajectories checked for wall contact, reflection, '
          'equal path length and arrival at the second focus; '
          'alternating passes, duplication, count limit, angular spread and '
          'mirrored paths, preserved velocity without duplication, '
          'tails across bounces and wall-pulse timing checked.')


def run_demo() -> None:
    if __package__:
        from .ellipse_app import run_demo as launch
    else:
        from ellipse_app import run_demo as launch
    launch()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true', help='Check physics without opening a window')
    arguments = parser.parse_args()
    if arguments.self_test:
        self_test()
    else:
        run_demo()
