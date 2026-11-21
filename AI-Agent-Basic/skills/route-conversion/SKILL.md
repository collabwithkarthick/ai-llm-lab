---
name: route-conversion
description: Read a route distance and convert it to another unit with a requested rounding precision.
---
When the task asks to convert the sample route distance:

1. Use `read_file` on `data/route_notes.txt` to find the distance and source unit.
2. Obtain the conversion factor from a relevant dispatched skill or verified observation; do not guess it.
3. Use `calculate` to convert and round to the precision requested by the user.
4. State the original distance, converted distance, and rounding precision.
5. If a source URL was provided by another skill, cite it in the final answer.
