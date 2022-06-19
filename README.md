## Organization name disambiguation

A simple organization name parser to map organization names in free text to standardized GRID affiliations with identifiers.

## Example

You could map a raw organization name to (a) valid GRID id(s). For example:

```python
from grid_matcher.matcher import GridMatcher
matcher = GridMatcher()
result = matcher.match("Computer Laboratory University of Cambridge, Cambridge, England")
print(result)
```

The output is a tuple of standard organization name, the corresponding GRID id(s) and country info:
```python
('University of Cambridge', ['grid.5335.0'], ['United Kingdom'])
```

If the branch of is unknown, it would be mapped into the default parent branch. For example:
```python
from grid_matcher.matcher import GridMatcher
matcher = GridMatcher()
result = matcher.match("Microsoft Research")
print(result)
```
The output is:
```python
('Microsoft Research', ['grid.419815.0'], ['United States'])
```