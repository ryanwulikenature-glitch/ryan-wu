# Directed road proxy

Routing source: OSRM project public driving table service, https://router.project-osrm.org/ . Road database: © OpenStreetMap contributors, https://www.openstreetmap.org/copyright , ODbL 1.0. Derived road matrix is provided subject to the applicable ODbL database terms. This notice does not relicense project software or independent Citi Bike snapshots.

The retained matrix has directed durations (seconds), distances (meters) and snapped endpoints. It is a current driving-profile proxy; it does not establish 2025 traffic, legal truck routes, vehicle height/weight restrictions or historical closures. Station order and request URL are recorded in source.json. The maximum endpoint snapping displacement is about 21.91 meters.

Refresh only explicitly with scripts/download_roads.py --refresh, then rerun the transport experiment and reconciliation. Existing matrices are preserved by default.
