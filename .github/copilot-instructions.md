# Copilot Instructions for FlyWise Flight Planner (Project 3)

## Project Overview
FlyWise is a CLI-based flight route & fare comparison engine. Given a flight schedule, it finds and compares optimal itineraries under different criteria (earliest arrival, cheapest per cabin class).

## Architecture & Data Structures

### Core Components
- **Flight** (dataclass): immutable flight record with origin, destination, times (minutes since midnight), and per-cabin prices
- **Graph** (Dict[str, List[Flight]]): adjacency list mapping airport codes → outbound flights
- **Itinerary** (dataclass): sequence of flights with helper methods for total price, duration, stops
- **ComparisonRow**: output row for the comparison table

### Critical Design Pattern: Time Representation
All times are stored as **integer minutes since midnight (0-1439)**. This enables:
- Direct comparison without timezone complexity
- Easy layover calculations: `next_depart >= prev_arrive + MIN_LAYOVER_MINUTES`
- Roundtrip parsing via `parse_time("HH:MM")` ↔ `format_time(minutes)`

### Graph Construction
`build_graph(flights)` creates adjacency list by grouping flights by origin airport using dict.setdefault().
Space: O(E) where E = number of flights. No isolated airports are stored.

## Critical Business Rules

### Layover Constraint (MIN_LAYOVER_MINUTES = 60)
- First flight: can depart anytime at or after `earliest_departure`
- Subsequent flights: must depart **at or after** `(previous_arrival + 60 minutes)`
- This is enforced in **both** search functions via: `f.depart >= current_time + MIN_LAYOVER_MINUTES`

### Search Ordering
- **Earliest-arrival**: optimize arrival time; use Dijkstra with heap keyed by `(arrival_time, airport, path)`
- **Cheapest-per-cabin**: optimize total price; use Dijkstra with heap keyed by `(total_price, current_time, airport, path)`
  - Must still track `current_time` to enforce layover constraints even though cost is price

### Visited State Tracking
Both searches use `visited: Dict[str, int]` to track best-known value per airport:
- Earliest-arrival: `visited[airport] = arrival_time`
- Cheapest: `visited[airport] = total_price`
- Skip if we've seen this airport with equal/better value to prune duplicate exploration

## File I/O Patterns

### Dual Format Support (Plain Text + CSV)
`load_flights(path)` dispatches based on file extension:
- `.txt`: space-separated fields, ignore blank lines and `#` comments
- `.csv`: header row, comma-separated fields
Both parse into identical `Flight` objects. Tests verify both loaders work.

### Error Handling During Parsing
- Invalid time format → ValueError with line number
- Wrong field count → ValueError with line number
- Arrival ≤ Departure → ValueError (same-day constraint)
- Missing CSV columns → ValueError

## Testing Patterns

Tests are organized into three files:
1. **test_time_and_parsing.py**: time conversions, file loading
2. **test_graph_and_search.py**: graph construction, both search algorithms with edge cases
3. **test_itinerary_and_output.py**: output formatting, end-to-end CLI test

Key assertion helper: `assert_valid_itinerary_times()` verifies all connections respect layover rules.

Tests use a **flight builder helper** `f()` that accepts HH:MM strings for readability.

## Search Algorithm Details

### Common Pattern
Both searches use a min-heap and visited set to avoid re-exploring airports with worse values.

**Earliest-arrival** (Dijkstra by time):
- Heap tuple: `(current_arrival_time, airport, path_flights)`
- State: best arrival time per airport
- Termination: first time we pop the destination

**Cheapest-per-cabin** (Dijkstra by cost):
- Heap tuple: `(total_price, current_arrival_time, airport, path_flights)`
- State: best price per airport
- Must track current_time alongside price to enforce layover timing

### Path Construction
Paths are built by appending flights: `path + [flight]`. This is O(n) per extension but acceptable for small itineraries (typically < 5 flights).

## CLI Structure
`main(argv)` → arg parser → `run_compare()` → orchestrate searches → `format_comparison_table()` → print

The compare command takes 4 positional args: flight_file, origin, dest, departure_time.

## Output Format
`format_comparison_table()` produces aligned text output with:
- Header row with route & earliest departure time
- Column headers: Mode, Cabin, Dep, Arr, Duration, Stops, Total Price, Note
- One row per search mode (1 earliest + 3 cabin cheapests)
- "N/A" for missing itineraries; note field explains why

## Common Pitfalls & Solutions

**Pitfall**: Comparing airports as destination without checking if reachable
- **Solution**: Search returns `None` if destination never popped from heap

**Pitfall**: First flight layover check differs from connection layover
- **Solution**: Use conditional: `f.depart >= current_time if not path else f.depart >= current_time + MIN_LAYOVER_MINUTES`

**Pitfall**: Building path as a list copy on every iteration
- **Solution**: Append and concatenate: `path + [flight]` (small lists only)

**Pitfall**: Not returning None explicitly when search exhausts heap without finding destination
- **Solution**: Explicit `return None` outside while loop

## Complexity Analysis (for README)

- **Build graph from N flights**: O(N) time, O(V + E) space (V ≤ airports, E = N)
- **Earliest-arrival search (V airports, E flights)**: O(E log V) time (each flight pushed once), O(V + E) space
- **Cheapest-per-cabin search**: O(E log V) time, O(V + E) space (same heap-based Dijkstra)

Justification: Each flight added to heap at most once; heap operations are O(log V). Visited dict prunes redundant work.

