from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional
import heapq

# ---------------------------------------------------------------------------
# Constants & types
# ---------------------------------------------------------------------------

MIN_LAYOVER_MINUTES: int = 60
Cabin = Literal["economy", "business", "first"]


@dataclass(frozen=True)
class Flight:
    origin: str
    dest: str
    flight_number: str
    depart: int  # minutes since midnight
    arrive: int  # minutes since midnight
    economy: int
    business: int
    first: int

    def price_for(self, cabin: Cabin) -> int:
        if cabin == "economy":
            return self.economy
        elif cabin == "business":
            return self.business
        elif cabin == "first":
            return self.first
        else:
            raise ValueError(f"Unknown cabin: {cabin}")


@dataclass
class Itinerary:
    flights: List[Flight]

    def is_empty(self) -> bool:
        return not self.flights

    @property
    def origin(self) -> Optional[str]:
        return self.flights[0].origin if self.flights else None

    @property
    def dest(self) -> Optional[str]:
        return self.flights[-1].dest if self.flights else None

    @property
    def depart_time(self) -> Optional[int]:
        return self.flights[0].depart if self.flights else None

    @property
    def arrive_time(self) -> Optional[int]:
        return self.flights[-1].arrive if self.flights else None

    def total_price(self, cabin: Cabin) -> int:
        return sum(f.price_for(cabin) for f in self.flights)

    def num_stops(self) -> int:
        return max(0, len(self.flights) - 1)


Graph = Dict[str, List[Flight]]


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def parse_time(hhmm: str) -> int:
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {hhmm}")
    hour, minute = parts
    try:
        hour = int(hour)
        minute = int(minute)
    except ValueError:
        raise ValueError(f"Invalid hour/minute in time: {hhmm}")
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"Hour or minute out of range: {hhmm}")
    return hour * 60 + minute


def format_time(minutes: int) -> str:
    hour = minutes // 60
    minute = minutes % 60
    return f"{hour:02d}:{minute:02d}"


# ---------------------------------------------------------------------------
# Loading flights from files
# ---------------------------------------------------------------------------

def parse_flight_line_txt(line: str) -> Optional[Flight]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split()
    if len(parts) != 8:
        raise ValueError(f"Expected 8 fields, got {len(parts)}: {line}")
    origin, dest, num, depart, arrive, econ, biz, first = parts
    depart_min = parse_time(depart)
    arrive_min = parse_time(arrive)
    if arrive_min <= depart_min:
        raise ValueError(f"Arrival must be after departure: {line}")
    return Flight(
        origin=origin,
        dest=dest,
        flight_number=num,
        depart=depart_min,
        arrive=arrive_min,
        economy=int(econ),
        business=int(biz),
        first=int(first),
    )


def load_flights_txt(path: str) -> List[Flight]:
    flights: List[Flight] = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            try:
                flight = parse_flight_line_txt(line)
                if flight:
                    flights.append(flight)
            except ValueError as e:
                raise ValueError(f"{path}:{lineno}: {e}")
    return flights


def load_flights_csv(path: str) -> List[Flight]:
    flights: List[Flight] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required_cols = {"origin","dest","flight_number","depart","arrive","economy","business","first"}
        if not required_cols.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing required CSV columns: {required_cols}")
        for row in reader:
            depart = parse_time(row["depart"])
            arrive = parse_time(row["arrive"])
            if arrive <= depart:
                raise ValueError(f"Arrival must be after departure: {row}")
            flights.append(
                Flight(
                    origin=row["origin"],
                    dest=row["dest"],
                    flight_number=row["flight_number"],
                    depart=depart,
                    arrive=arrive,
                    economy=int(row["economy"]),
                    business=int(row["business"]),
                    first=int(row["first"]),
                )
            )
    return flights


def load_flights(path: str) -> List[Flight]:
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return load_flights_csv(path)
    return load_flights_txt(path)


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph(flights: Iterable[Flight]) -> Graph:
    g: Graph = {}
    for f in flights:
        g.setdefault(f.origin, []).append(f)
    return g


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------

def find_earliest_itinerary(
    graph: Graph,
    start: str,
    dest: str,
    earliest_departure: int,
) -> Optional[Itinerary]:

    heap = [(earliest_departure, start, [])]  # (current_time, airport, path)
    visited: Dict[str, int] = {}

    while heap:
        current_time, airport, path = heapq.heappop(heap)
        if airport == dest and path:
            return Itinerary(path)
        if airport in visited and visited[airport] <= current_time:
            continue
        visited[airport] = current_time
        for f in graph.get(airport, []):
            layover_ok = f.depart >= current_time if not path else f.depart >= current_time + MIN_LAYOVER_MINUTES
            if layover_ok:
                heapq.heappush(heap, (f.arrive, f.dest, path + [f]))
    return None


def find_cheapest_itinerary(
    graph: Graph,
    start: str,
    dest: str,
    earliest_departure: int,
    cabin: Cabin,
) -> Optional[Itinerary]:

    heap = [(0, earliest_departure, start, [])]  # (total_price, current_time, airport, path)
    visited: Dict[str, int] = {}

    while heap:
        total_price, current_time, airport, path = heapq.heappop(heap)
        if airport == dest and path:
            return Itinerary(path)
        if airport in visited and visited[airport] <= total_price:
            continue
        visited[airport] = total_price
        for f in graph.get(airport, []):
            layover_ok = f.depart >= current_time if not path else f.depart >= current_time + MIN_LAYOVER_MINUTES
            if layover_ok:
                heapq.heappush(heap, (total_price + f.price_for(cabin), f.arrive, f.dest, path + [f]))
    return None


# ---------------------------------------------------------------------------
# Formatting the comparison table
# ---------------------------------------------------------------------------

@dataclass
class ComparisonRow:
    mode: str
    cabin: Optional[Cabin]
    itinerary: Optional[Itinerary]
    note: str = ""


def format_comparison_table(
    origin: str,
    dest: str,
    earliest_departure: int,
    rows: List[ComparisonRow],
) -> str:
    lines = []
    # Include route and earliest departure info so output is self-contained.
    lines.append(f"Route: {origin} -> {dest}  Earliest: {format_time(earliest_departure)}")
    lines.append("")
    header = f"{'Mode':20} {'Cabin':10} {'Dep':6} {'Arr':6} {'Duration':10} {'Stops':5} {'Total Price':12} {'Note'}"
    lines.append(header)
    lines.append("-" * len(header))

    for row in rows:
        itin = row.itinerary
        if itin is None:
            dep = arr = dur = stops = price = "N/A"
        else:
            dep = format_time(itin.depart_time)
            arr = format_time(itin.arrive_time)
            duration_min = itin.arrive_time - itin.depart_time
            dur = f"{duration_min // 60}h{duration_min % 60}m"
            stops = str(itin.num_stops())
            price = str(itin.total_price(row.cabin)) if row.cabin else "N/A"

        cabin_str = row.cabin if row.cabin else "-"
        line = f"{row.mode:20} {cabin_str:10} {dep:6} {arr:6} {dur:10} {stops:5} {price:12} {row.note}"
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def run_compare(args: argparse.Namespace) -> None:
    earliest_departure = parse_time(args.departure_time)
    flights = load_flights(args.flight_file)
    graph = build_graph(flights)

    rows: List[ComparisonRow] = []

    earliest_itin = find_earliest_itinerary(graph, args.origin, args.dest, earliest_departure)
    rows.append(ComparisonRow(mode="Earliest arrival", cabin=None, itinerary=earliest_itin, note="" if earliest_itin else "(no valid itinerary)"))

    for cabin in ["economy", "business", "first"]:
        cheapest_itin = find_cheapest_itinerary(graph, args.origin, args.dest, earliest_departure, cabin)
        rows.append(ComparisonRow(mode=f"Cheapest ({cabin.capitalize()})", cabin=cabin, itinerary=cheapest_itin, note="" if cheapest_itin else "(no valid itinerary)"))

    table = format_comparison_table(args.origin, args.dest, earliest_departure, rows)
    print(table)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="FlyWise — Flight Route & Fare Comparator (Project 3)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare itineraries for a route (earliest arrival, cheapest per cabin).",
    )
    compare_parser.add_argument("flight_file", help="Path to the flight schedule file (.txt or .csv).")
    compare_parser.add_argument("origin", help="Origin airport code (e.g., ICN).")
    compare_parser.add_argument("dest", help="Destination airport code (e.g., SFO).")
    compare_parser.add_argument("departure_time", help="Earliest allowed departure time (HH:MM, 24-hour).")
    compare_parser.set_defaults(func=run_compare)
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()