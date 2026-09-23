# Username normalization fixture
Normalize strings by stripping leading/trailing whitespace and applying Unicode
case-folding. Do not remove internal whitespace. Non-string input is an error.
The current implementation mishandles both whitespace and German sharp-s.
