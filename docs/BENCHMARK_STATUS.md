# Benchmark Status and Next Steps

本文档整理当前 Walk-on-Stars / Walk-on-Spheres C++ 项目的 benchmark 完成情况、预期结果，以及仍需补充的实验。目标是帮助 Column 3: Benchmarks & Results 在报告和展示中表达清楚：哪些结论已经由当前代码支持，哪些还只是后续计划，不能过度宣称。

## 1. Benchmark Setup

### 要求

- 测试场景：内部放置复杂 OBJ 网格模型，例如 Stanford Bunny、Armadillo 等，外部包裹标准 AABB 立方体。
- 可视化输出：通过 VTK 输出 `solution`、`is_valid`、`std_error`、`mean_steps` 等标量，导入 ParaView。

### 当前已完成

当前代码已经支持：

- 外部 AABB cube。
- 内部三角网格 OBJ。
- 默认 OBJ 为 `spot/spot_triangulated.obj`。
- 通过 `--obj` 参数切换其他 OBJ。
- VTK point cloud 输出：
  - `results/linear_dirichlet_pointcloud.vtk`
- VTK structured grid 输出：
  - `results/linear_dirichlet_grid.vtk`
  - `results/adaptive_sampling_grid.vtk`
- VTK 字段：
  - `solution`
  - `std_error`
  - `mean_steps`
  - `samples_used`
  - `exact`
  - `abs_error`
  - `is_valid`

### 当前不足

默认模型 `spot/spot_triangulated.obj` 约为数千三角形，不属于数万至百万面片的高复杂度模型。因此，当前结果可以说明代码支持 OBJ 网格与 BVH 查询，但不能直接声称已经完成了高复杂度模型 benchmark。

### 期望结果

在 ParaView 中打开 structured grid VTK 后，应看到：

- `solution` 和 `exact` 都是平滑的线性场。
- `abs_error` 大部分区域较小。
- `is_valid = 1` 表示 PDE 域内点，`is_valid = 0` 表示无效区域。
- 内部 mesh 所占区域应被 mask 或标记为 invalid。

### 如何补充

准备更复杂的 OBJ，例如：

```text
models/bunny.obj
models/armadillo.obj
```

然后运行：

```powershell
.\build\Release\wost.exe --mode convergence --obj .\models\bunny.obj --queries 5000 --threads 8
.\build\Release\wost.exe --mode grid --obj .\models\bunny.obj --grid 32 --threads 8
```

如果模型尺寸不在 `[-1,1]^3` 内，需要先归一化 OBJ，或者后续修改 geometry loader 增加自动 normalize 功能。

## 2. Accuracy Evaluation

### 要求

- 使用解析解作为 ground truth。
- 计算 RMSE。
- 展示随着每点游走次数 `M` 增加，误差符合 Monte Carlo 理论收敛趋势 `O(1/sqrt(M))`。
- 展示复杂内边界附近的解仍然连续、无明显锯齿。

### 当前已完成

当前主 benchmark 使用 Dirichlet-only Laplace test：

```text
u(x,y,z) = x + y + z
Delta u = 0
f(x) = 0
g_inner(p) = p.x + p.y + p.z
g_outer(p) = p.x + p.y + p.z
Neumann predicate = false
```

这比旧的 `u=x^2+y^2+z^2` mixed-boundary setup 更干净，因为：

- 内外边界条件一致。
- 没有 Neumann 法向方向歧义。
- 解析解明确。
- 适合作为主 accuracy benchmark。

当前 CSV 已输出：

```text
rmse
mae
max_abs_error
mean_std_error
mean_steps
diverged_count
```

### 期望结果

对 convergence benchmark：

```text
M = 16, 64, 256, 1024
```

预期：

- `walks_per_point` 增大时，`rmse` 总体下降。
- `M` 增加 4 倍时，RMSE 理论上约下降到原来的 1/2。
- 单次实验中不保证严格单调，因为 Monte Carlo 采样有随机波动。

推荐报告表述：

```text
RMSE follows the expected O(1/sqrt(M)) Monte Carlo convergence trend up to sampling noise.
```

中文表述：

```text
RMSE 整体符合 O(1/sqrt(M)) 的蒙特卡洛收敛趋势，但由于随机采样误差，单次实验中不保证严格单调。
```

### 如何运行

```powershell
.\build\Release\wost.exe --mode convergence --queries 5000 --threads 8 --seed 12345
```

生成 plot：

```powershell
python .\scripts\plot_benchmarks.py
```

查看：

```text
results/rmse_vs_walks.png
```

### 当前不足

“边界贴合度”目前主要是 qualitative visualization，还不是定量指标。可以在 ParaView 中通过 `solution`、`exact`、`abs_error` 观察内边界附近是否连续，但目前没有专门的 near-boundary error metric。

### 如何补充边界贴合度

可选补充方案：

1. 对每个 query point 计算到 inner boundary 的距离。
2. 只统计距离小于阈值的点，例如：

```text
dist_to_inner < 0.02
```

3. 输出额外 CSV 指标：

```text
near_boundary_rmse
near_boundary_mae
near_boundary_max_abs_error
```

4. 或输出 VTK 字段：

```text
dist_to_inner
```

然后在 ParaView 中筛选靠近 `Gamma_inner` 的区域。

## 3. Convergence Analysis

### 要求

- 展示 mean steps distribution。
- 展示 epsilon shell robustness，即不同 `epsilon` 下精度和步数/runtime 的权衡。

### 当前已完成

当前代码支持 epsilon sweep：

```text
epsilon = 1e-2, 1e-3, 1e-4, 1e-5
walksPerPoint = 256
maxSteps = 512
```

当前 VTK 输出包含：

```text
mean_steps
std_error
abs_error
```

### 期望结果

对 epsilon sweep，预期：

- `epsilon` 越小，`mean_steps` 通常越大。
- `epsilon` 越小，runtime 通常越长。
- RMSE 不一定严格下降，因为误差可能主要由 Monte Carlo sample count 控制。

合理现象：

```text
epsilon = 1e-2   mean_steps 较小，速度较快
epsilon = 1e-5   mean_steps 较大，速度较慢
```

对 `mean_steps` VTK，可视化时预期：

- 远离边界的区域 mean steps 较低，因为大球可以快速跨越空间。
- 靠近复杂内边界或几何细节处 mean steps 较高。

### 如何运行

```powershell
.\build\Release\wost.exe --mode epsilon --queries 5000 --threads 8 --seed 12345
.\build\Release\wost.exe --mode grid --grid 32 --threads 8 --seed 12345
```

生成 plot：

```powershell
python .\scripts\plot_benchmarks.py
```

查看：

```text
results/epsilon_tradeoff.png
results/linear_dirichlet_grid.vtk
```

ParaView 推荐 coloring：

```text
mean_steps
abs_error
std_error
solution
```

## 4. Adaptive Sampling Innovation

### 当前已完成

当前代码新增了 adaptive sampling：

```cpp
bool adaptiveSampling = false;
int minSamples = 32;
int maxSamples = 1024;
int batchSize = 32;
float targetStdErr = 1e-3f;
```

当 adaptive sampling 开启时，solver 会分批运行 random walks，并在线估计 standard error。达到 `minSamples` 后，如果 `stdErr < targetStdErr`，则提前停止。

输出中包含：

```text
samples_used
mean_samples_used
```

### 期望结果

对 adaptive benchmark，预期：

- adaptive 的 `mean_samples_used` 小于或接近 fixed 1024。
- adaptive 的 runtime 小于或接近 fixed。
- adaptive 的 RMSE 接近 fixed，不应明显变差。
- 在 `adaptive_sampling_grid.vtk` 中，`samples_used` 会随空间位置变化。

注意：对线性解 `u=x+y+z`，adaptive sampling 不一定节省很多，因为不同区域方差差异可能不够强。它仍然可以作为算法创新点展示。

### 如何运行

```powershell
.\build\Release\wost.exe --mode adaptive --queries 5000 --grid 32 --threads 8 --seed 12345
```

查看：

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

## 5. Computational Speed and Scalability

### 要求

- BVH 加速对比：brute force traversal vs tiny_bvh backend。
- 展示模型三角形数量从 `10^3` 到 `10^6` 增加时，tiny_bvh 后端具有更好的扩展性。
- 多核并行加速比曲线：展示 thread count 增加时 runtime 下降，speedup 接近线性。

### 当前已完成

当前代码已经：

- 使用 tiny_bvh 作为几何查询后端。
- 使用 OpenMP 对 query points 和 grid points 并行。
- 支持命令行设置线程数：

```text
--threads 1
--threads 2
--threads 4
--threads 8
```

CSV 中已有：

```text
num_threads
elapsed_seconds
points_per_second
walks_per_second
```

### 当前不足

目前还没有：

- brute-force geometry backend。
- BVH vs brute-force 的自动 benchmark。
- 不同 mesh triangle count 的自动 sweep。
- thread sweep mode。
- speedup plot。

因此，当前不能严谨宣称：

```text
Compared with brute force, tiny_bvh gives X times speedup.
```

也不能严谨宣称：

```text
The solver achieves near-perfect linear speedup.
```

除非补充对应实验数据。

### 如何补充 thread sweep

最小实现方式：手动运行多次。

```powershell
Move-Item results\benchmark_summary.csv results\benchmark_summary_previous.csv

.\build\Release\wost.exe --mode convergence --queries 5000 --threads 1 --seed 12345
.\build\Release\wost.exe --mode convergence --queries 5000 --threads 2 --seed 12345
.\build\Release\wost.exe --mode convergence --queries 5000 --threads 4 --seed 12345
.\build\Release\wost.exe --mode convergence --queries 5000 --threads 8 --seed 12345
```

然后从 CSV 中取每个 thread count 对应的 `elapsed_seconds`。定义：

```text
speedup(N) = time(1 thread) / time(N threads)
parallel_efficiency(N) = speedup(N) / N
```

更好的后续代码补充：

- 新增 `--mode threads`。
- 固定 `queries`、`walks_per_point`、`epsilon`。
- 自动 sweep：

```text
threads = {1, 2, 4, 8, 16}
```

- CSV 行使用：

```text
benchmark_name = thread_scaling
```

- plotting script 增加：

```text
results/thread_speedup.png
```

### 如何补充 BVH vs brute force

建议实现一个独立的 geometry query microbenchmark，而不是把 brute force 塞进主 solver。

可行方案：

1. 在 `WoStGeometryBackend` 旁边增加一个 slow baseline，仅用于 benchmark。
2. 对同一批随机点，分别测试：

```text
ClosestPoint
IntersectRay
FastBoundaryDistance
```

3. 对不同 mesh triangle count 运行：

```text
N = 1e3, 1e4, 1e5
```

4. 输出：

```text
geometry_backend
triangle_count
num_queries
elapsed_seconds
queries_per_second
```

5. 画柱状图或 log-log 曲线。

注意：百万面片 brute-force 可能非常慢，不建议在正式 demo 中强行运行。可以只对较小 N 做 brute-force，对大 N 标注为 extrapolated 或 omitted due to impractical runtime。

## 6. Recommended Official Benchmark Workflow

正式跑 benchmark 前，建议先清理 sanity check 数据：

```powershell
Move-Item results\benchmark_summary.csv results\benchmark_summary_sanity.csv
```

或者删除：

```powershell
Remove-Item results\benchmark_summary.csv
```

然后运行较稳妥的正式配置：

```powershell
.\build\Release\wost.exe --mode convergence --queries 5000 --threads 8 --seed 12345
.\build\Release\wost.exe --mode epsilon --queries 5000 --threads 8 --seed 12345
.\build\Release\wost.exe --mode grid --grid 32 --threads 8 --seed 12345
.\build\Release\wost.exe --mode adaptive --queries 5000 --grid 32 --threads 8 --seed 12345
python .\scripts\plot_benchmarks.py
```

如果机器性能足够，再使用更大的配置：

```powershell
.\build\Release\wost.exe --mode all --queries 20000 --grid 48 --threads 8 --seed 12345
```

## 7. Summary Table

| Requirement | Status | Evidence / Output | Notes |
|---|---|---|---|
| AABB outer boundary + OBJ inner boundary | Done | `--obj`, `spot/spot_triangulated.obj` | Still need larger OBJ for high-complexity claim |
| VTK visualization | Done | `.vtk` files in `results/` | ParaView compatible |
| Solution field | Done | `solution` | Point cloud and structured grid |
| Validity mask | Done | `is_valid` | Structured grid |
| Standard error | Done | `std_error` | Point cloud and grid |
| Mean steps | Done | `mean_steps` | Point cloud and grid |
| Samples used | Done | `samples_used` | Added for adaptive sampling |
| Analytic ground truth | Done | `exact = x+y+z` | Clean Dirichlet-only Laplace test |
| Mixed Neumann benchmark | Done | `--mode neumann`, `neumann_mixed_grid.vtk` | Inner Bunny Neumann, outer cube Dirichlet |
| RMSE / MAE / max error | Done | `benchmark_summary.csv` | Quantitative accuracy |
| Convergence over M | Done | `benchmark_name=convergence` | Expect `O(1/sqrt(M))` trend |
| Epsilon sweep | Done | `benchmark_name=epsilon` | Expect smaller epsilon -> more steps |
| Adaptive sampling | Done | `benchmark_name=adaptive`, `adaptive_sampling_grid.vtk` | Small innovation |
| Boundary fitting metric | Partial | ParaView qualitative visualization | Could add near-boundary error metric |
| High-complexity mesh benchmark | Done for Bunny | `obj/Bunny.obj`, `--obj .\obj\Bunny.obj` | Bunny has 70,580 faces |
| BVH vs brute force | Done as microbenchmark | `--mode geometry`, `results/geometry_benchmark.csv` | Compares distance-query throughput |
| Thread speedup curve | Done | `--mode threads`, `results/thread_speedup.png` | Uses OpenMP thread sweep |

## 8. What Can Be Claimed Now

Safe claims:

```text
The benchmark uses a clean linear Dirichlet Laplace problem with known analytic solution.
The solver outputs quantitative error metrics and ParaView-compatible VTK diagnostics.
RMSE decreases with more random walks per point, matching the expected Monte Carlo convergence trend.
Smaller epsilon increases mean walk length, showing the expected boundary-accuracy/runtime tradeoff.
Adaptive sampling records per-point samples used and can reduce unnecessary sampling in low-variance regions.
```

Claims to avoid until more data is added:

```text
The solver has been benchmarked on million-triangle meshes.
tiny_bvh is X times faster than brute force.
The method achieves near-perfect linear speedup on all core counts.
Boundary fitting is quantitatively proven near sharp features.
```
