You are setting up a good fixture in Houdini so this sentence gets stripped.

Goal: {description}

SideFX documents this properly. Read `pyro/lookdev` with get_help_page rather than
improvising, and use setup_pyro_sim to build the network.

## Real nodes resolve

Wire a `pyrosolver` into the sim. The `particlefluidsurface` node meshes the result,
and the `density` field drives the look.

## Second section

The `oceansource` node emits spectra. Keep `density` clamped.
