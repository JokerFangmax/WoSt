# Bunny Benchmark Report

本文档整理本次基于 `obj/Bunny.obj` 的 Walk-on-Stars / Walk-on-Spheres benchmark 实验设置、输出结果和汇报展示要点。内容可以直接用于课程项目汇报中的 Benchmarks & Results 部分。

## 1. 实验目标

本次 benchmark 的目标是验证 solver 在复杂三角网格内边界上的：

- 解析解精度。
- Monte Carlo 收敛趋势。
- epsilon 边界层参数对步数和误差的影响。
- ParaView 可视化诊断能力。
- adaptive sampling 的样本节省效果。
- OpenMP 多线程加速效果。
- tiny_bvh 几何查询加速效果。

## 2. 测试模型与几何设置

使用高复杂度 Bunny OBJ 作为内部障碍物边界：

```text
mesh: obj/Bunny.obj
vertices: 35,292
faces: 70,580
```

几何域定义为：

```text
Omega = outer AABB cube - inner Bunny triangle mesh
```

Bunny 原始坐标范围约为：

```text
x = [-0.0947, 0.0610]
y = [ 0.0333, 0.1873]
z = [-0.0619, 0.0588]
```

由于 Bunny 模型在默认 `[-1,1]^3` cube 中太小，本次实验使用更紧的外边界：

```text
cube half extent = 0.22
outer cube = [-0.22, 0.22]^3
```

这样 ParaView 中的 validity mask、inner boundary 附近的 `mean_steps` 分布会更明显。

## 3. PDE Benchmark 设置

本次主精度测试使用 Dirichlet-only Laplace benchmark。

解析解：

```text
u(x,y,z) = x + y + z
```

PDE：

```text
Delta u = 0
```

源项：

```text
f(x) = 0
```

边界条件：

```text
g_inner(p) = p.x + p.y + p.z
g_outer(p) = p.x + p.y + p.z
```

Neumann 区域：

```text
disabled
```

选择该 benchmark 的原因：

- 有明确解析解。
- 内外 Dirichlet 边界条件一致。
- 避免 Neumann 法向方向歧义。
- 适合做主 accuracy benchmark。

## 4. 实际运行配置

本次完整实验使用的是展示友好的中等规模配置：

```text
queries = 500
grid = 16^3
threads = 8
seed = 12345
cube half extent = 0.22
```

运行命令等价于：

```powershell
.\build\Release\wost.exe --mode convergence --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode epsilon --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode grid --obj .\obj\Bunny.obj --grid 16 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode adaptive --obj .\obj\Bunny.obj --queries 500 --grid 16 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode threads --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode geometry --obj .\obj\Bunny.obj --queries 3000 --threads 8 --seed 12345 --cube 0.22
```

说明：`queries=500` 和 `grid=16` 是为了在本地机器上可控地完成完整实验流程。如果时间充足，可以将其提升到：

```text
queries = 5000
grid = 32
```

## 5. 生成的结果文件

CSV：

```text
results/benchmark_summary.csv
results/geometry_benchmark.csv
```

VTK：

```text
results/linear_dirichlet_pointcloud.vtk
results/linear_dirichlet_grid.vtk
results/adaptive_sampling_grid.vtk
```

PNG plots：

```text
results/rmse_vs_walks.png
results/epsilon_tradeoff.png
results/adaptive_vs_fixed.png
results/thread_speedup.png
results/bvh_vs_bruteforce.png
```

## 6. 精度收敛结果

Convergence benchmark 固定：

```text
epsilon = 1e-4
maxSteps = 512
```

改变每点 random walks 数量：

```text
M = 16, 64, 256, 1024
```

结果：

| Walks per point M | RMSE | MAE | Max abs error | Mean std error |
|---:|---:|---:|---:|---:|
| 16 | 0.03042 | 0.02275 | 0.10116 | 0.02858 |
| 64 | 0.01570 | 0.01168 | 0.05063 | 0.01485 |
| 256 | 0.00778 | 0.00568 | 0.03143 | 0.00757 |
| 1024 | 0.00399 | 0.00299 | 0.01511 | 0.00379 |

观察：

- `M` 每增加 4 倍，RMSE 大约减半。
- 该趋势符合 Monte Carlo 理论收敛速度：

```text
RMSE ~ O(1 / sqrt(M))
```

汇报时可以展示：

```text
results/rmse_vs_walks.png
```

推荐讲法：

```text
The RMSE decreases consistently as the number of walks per point increases.
The observed slope matches the expected O(1/sqrt(M)) Monte Carlo convergence trend.
```

中文讲法：

```text
随着每点随机游走次数 M 增加，RMSE 稳定下降。M 每增加 4 倍，误差大约减半，符合蒙特卡洛方法 O(1/sqrt(M)) 的理论收敛趋势。
```

## 7. Epsilon Sweep 结果

Epsilon benchmark 固定：

```text
walksPerPoint = 256
maxSteps = 512
```

改变 boundary absorption threshold：

```text
epsilon = 1e-2, 1e-3, 1e-4, 1e-5
```

结果：

| Epsilon | RMSE | MAE | Mean steps |
|---:|---:|---:|---:|
| 1e-2 | 0.00857 | 0.00665 | 6.24 |
| 1e-3 | 0.00806 | 0.00572 | 13.79 |
| 1e-4 | 0.00781 | 0.00588 | 21.39 |
| 1e-5 | 0.00765 | 0.00569 | 28.83 |

观察：

- epsilon 越小，walk 越接近边界才停止，因此 `mean_steps` 明显增加。
- RMSE 只有轻微变化，因为当前误差主要仍受 Monte Carlo 采样噪声影响。

汇报时可以展示：

```text
results/epsilon_tradeoff.png
```

推荐讲法：

```text
Smaller epsilon leads to longer walks, showing the expected accuracy-runtime tradeoff near the boundary shell.
```

中文讲法：

```text
epsilon 越小，边界吸收壳层越薄，粒子需要更多步才能终止，因此 mean steps 明显增加。这展示了边界精度与运行成本之间的权衡。
```

## 8. Structured VTK 可视化结果

Structured grid：

```text
grid resolution = 16^3 = 4096 points
valid domain points = 4018
invalid points = 78
RMSE = 0.00730
mean steps = 15.39
```

ParaView 打开：

```text
results/linear_dirichlet_grid.vtk
```

推荐展示字段：

```text
solution
exact
abs_error
is_valid
mean_steps
std_error
samples_used
```

预期画面：

- `solution` 与 `exact` 都应呈现平滑线性变化。
- `abs_error` 大部分区域较小。
- `is_valid = 0` 区域对应 Bunny 内部或 PDE 域外。
- `mean_steps` 在复杂内边界附近通常更高。

汇报时可以这样说：

```text
The structured VTK output allows direct inspection of the solution field, validity mask, Monte Carlo uncertainty, and walk length distribution in ParaView.
```

中文讲法：

```text
结构化 VTK 输出可以直接导入 ParaView，检查解场、有效区域掩膜、蒙特卡洛标准误差和平均游走步数分布。
```

## 9. Adaptive Sampling 结果

Adaptive sampling 设置：

```text
minSamples = 32
maxSamples = 1024
batchSize = 32
targetStdErr = 1e-3
```

Point benchmark 对比：

| Mode | RMSE | Mean samples used | Runtime |
|---|---:|---:|---:|
| Fixed 1024 | 0.00398 | 1024.00 | 55.85 s |
| Adaptive | 0.00399 | 997.71 | 54.38 s |

Structured adaptive grid：

```text
RMSE = 0.00371
mean samples used = 689.90
mean std error = 0.00290
```

观察：

- 随机 query point benchmark 中 adaptive 节省不多，因为许多点仍需要接近最大样本数。
- structured grid 中 adaptive 效果明显，平均样本数从 1024 降到约 690，同时保持较低 RMSE。

汇报时展示：

```text
results/adaptive_vs_fixed.png
results/adaptive_sampling_grid.vtk
```

ParaView 推荐 coloring：

```text
samples_used
std_error
abs_error
```

推荐讲法：

```text
Adaptive sampling estimates standard error online and stops early in lower-variance regions.
On the structured grid, it reduces the average sample count from 1024 to about 690 while preserving comparable accuracy.
```

中文讲法：

```text
自适应采样在线估计标准误差，在低方差区域提前停止。对于 structured grid，平均样本数从 1024 降到约 690，同时保持相近精度。
```

## 10. OpenMP 多线程加速

Thread scaling benchmark 固定：

```text
queries = 500
walksPerPoint = 256
epsilon = 1e-4
```

结果：

| Threads | Runtime | Speedup |
|---:|---:|---:|
| 1 | 83.44 s | 1.00x |
| 2 | 42.46 s | 1.97x |
| 4 | 23.84 s | 3.50x |
| 8 | 13.62 s | 6.13x |

汇报时展示：

```text
results/thread_speedup.png
```

推荐讲法：

```text
The query evaluations are independent, so the solver parallelizes naturally with OpenMP.
The 8-thread run reaches about 6.1x speedup over the single-thread baseline.
```

中文讲法：

```text
每个查询点的随机游走相互独立，因此算法天然适合 OpenMP 并行。实验中 8 线程相对单线程获得约 6.1 倍加速。
```

## 11. tiny_bvh vs Brute Force 几何查询

Geometry microbenchmark 测试最近边界距离查询。

配置：

```text
queries = 3000
triangles = 70580
threads = 8
```

结果：

| Backend | Queries/sec | Checksum |
|---|---:|---:|
| tiny_bvh | 794,428 | 471.342 |
| brute_force | 6,169 | 471.342 |

加速比：

```text
tiny_bvh / brute_force ≈ 129x
```

checksum 一致，说明两种方法在该 query set 上得到相同的 aggregate distance result。

汇报时展示：

```text
results/bvh_vs_bruteforce.png
```

推荐讲法：

```text
The tiny_bvh backend provides about 129x higher closest-distance query throughput than brute-force triangle traversal on the 70k-face Bunny mesh.
```

中文讲法：

```text
在 7 万面 Bunny 模型上，tiny_bvh 最近距离查询吞吐量约为暴力遍历的 129 倍，说明 BVH 对复杂几何查询非常关键。
```

## 12. 汇报推荐展示顺序

建议按下面顺序讲：

1. 展示 Bunny 模型和 domain setup。
2. 说明解析解 benchmark：`u=x+y+z`。
3. 展示 `rmse_vs_walks.png`，证明 Monte Carlo 收敛。
4. 展示 `epsilon_tradeoff.png`，说明 epsilon 与步数/runtime 的权衡。
5. 打开 `linear_dirichlet_grid.vtk`，展示 `solution`、`abs_error`、`is_valid`、`mean_steps`。
6. 展示 `adaptive_vs_fixed.png` 和 `adaptive_sampling_grid.vtk` 的 `samples_used`。
7. 展示 `thread_speedup.png`，说明 OpenMP 并行收益。
8. 展示 `bvh_vs_bruteforce.png`，说明 tiny_bvh 的必要性。

## 13. 一页总结

可以放在汇报最后：

```text
We evaluated the solver on a 70,580-face Bunny mesh inside an AABB domain.
Using the analytic linear Dirichlet solution u=x+y+z, the solver shows the expected O(1/sqrt(M)) Monte Carlo convergence.
The epsilon sweep confirms the boundary accuracy/runtime tradeoff through increasing mean walk steps.
VTK outputs provide direct ParaView visualization of solution, error, validity mask, uncertainty and walk statistics.
Adaptive sampling reduces average grid samples from 1024 to about 690 while preserving accuracy.
OpenMP gives about 6.1x speedup on 8 threads.
tiny_bvh gives about 129x higher closest-distance query throughput than brute-force traversal.
```

中文版本：

```text
我们在 70,580 面 Bunny 网格模型上完成了完整 benchmark。在线性 Dirichlet 解析解 u=x+y+z 下，RMSE 随每点游走次数增加呈现 O(1/sqrt(M)) 的蒙特卡洛收敛趋势。epsilon sweep 展示了边界精度与平均步数之间的权衡。VTK 输出可以在 ParaView 中直接检查解场、误差、有效区域、标准误差和平均步数。自适应采样在 structured grid 上将平均样本数从 1024 降到约 690，同时保持低误差。OpenMP 在 8 线程下获得约 6.1 倍加速，tiny_bvh 最近距离查询吞吐量约为暴力遍历的 129 倍。
```

