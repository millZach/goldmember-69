class_name Layers
## Physics layer bit values shared by all gameplay code.

const WORLD := 1
const PLAYER := 2
const GUARDS := 4
const INTERACT := 8
const PICKUPS := 16

## What bullets can hit.
const SHOT_MASK := WORLD | GUARDS
