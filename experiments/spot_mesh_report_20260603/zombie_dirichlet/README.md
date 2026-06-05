# Zombie Bunny Baseline

This run uses Zombie WalkOnSpheres as the baseline solver.

## Configuration

- mesh: C:\THU\projects\WoSt_Final_project-1\spot\spot_triangulated.obj
- vertices: 2930
- faces: 5856
- cube half extent: 1.1
- query points: 500
- grid resolution: 16^3
- seed: 54321
- PDE: Delta u = 0, u(x,y,z)=x+y+z on all boundaries

## Bunny Bounds

- min: [-0.4715520143508911, -0.7367839813232422, -0.6689090132713318]
- max: [0.4715520143508911, 0.9536460041999817, 1.0490000247955322]

## Notes

Zombie exposes TBB parallel/default execution and single-threaded execution through the Python API, but not an explicit 1/2/4/8 thread sweep. This baseline therefore focuses on the PDE accuracy and grid diagnostics.
