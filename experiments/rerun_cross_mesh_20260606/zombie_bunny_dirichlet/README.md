# Zombie Bunny Baseline

This run uses Zombie WalkOnSpheres as the baseline solver.

## Configuration

- mesh: C:\THU\projects\WoSt_Final_project-1\obj\Bunny.obj
- vertices: 35292
- faces: 70580
- cube half extent: 0.22
- query points: 500
- grid resolution: 16^3
- seed: 12345
- PDE: Delta u = 0, u(x,y,z)=x+y+z on all boundaries

## Bunny Bounds

- min: [-0.09468989819288254, 0.03333070129156113, -0.061873599886894226]
- max: [0.06100910156965256, 0.1873210072517395, 0.05879969894886017]

## Notes

Zombie exposes TBB parallel/default execution and single-threaded execution through the Python API, but not an explicit 1/2/4/8 thread sweep. This baseline therefore focuses on the PDE accuracy and grid diagnostics.
