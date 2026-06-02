# Mixed Neumann Boundary Benchmark Report

本文档整理本次新增的 Neumann boundary benchmark。它可以和之前的 Dirichlet-only Bunny benchmark 一起用于汇报，说明代码不仅支持纯 Dirichlet 问题，也支持内边界 Neumann / 外边界 Dirichlet 的 mixed-boundary PDE 测试。

## 1. 实验目的

之前主 benchmark 使用的是 Dirichlet-only Laplace problem：

```text
inner boundary: Dirichlet
outer boundary: Dirichlet
```

本次新增 benchmark 测试：

```text
inner Bunny boundary: Neumann
outer AABB boundary: Dirichlet
```

目标是验证：

- Neumann callback 在 solver 中可以正常工作。
- mixed-boundary setting 下仍然可以和解析解比较。
- RMSE 随 random walks 数量增加而下降。
- epsilon 变小时，Neumann 反射/边界处理导致 mean steps 增加。
- Neumann 结果可以输出为 CSV、PNG plot 和 ParaView VTK。

## 2. 测试模型和几何域

使用同一个 Bunny 高复杂度网格：

```text
mesh: obj/Bunny.obj
vertices: 35,292
faces: 70,580
```

几何域：

```text
Omega = outer AABB cube - inner Bunny triangle mesh
outer cube = [-0.22, 0.22]^3
```

使用较紧的 cube 是为了让 Bunny 内边界在 structured grid 中更明显。

## 3. Mixed Neumann PDE 设置

解析解仍然使用线性函数：

```text
u(x,y,z) = x + y + z
```

PDE：

```text
Delta u = 0
f(x) = 0
```

外边界 Dirichlet：

```text
g_outer(p) = p.x + p.y + p.z
```

内边界 Neumann：

```text
h_inner(p) = grad(u) · n_mesh
           = (1,1,1) · n_mesh
```

其中 `n_mesh` 是 `WoStGeometryBackend` 返回的 Bunny mesh normal。当前 kernel 的 Neumann 处理也使用该 normal 将粒子推回 mesh 外部的计算域，因此 benchmark 使用同一 normal 约定。

说明：

- `g_inner` 仍然传入解析值，但在正常 Neumann 命中时不会作为吸收边界使用。
- 如果某条 walk 达到 `maxSteps`，solver 会 fallback 到最近边界值，因此保留 `g_inner` 作为安全兜底。

## 4. 代码和输出文件

新增命令行模式：

```text
--mode neumann
```

该模式会运行：

- `neumann_convergence`
- `neumann_epsilon`
- `neumann_mixed_grid`

生成文件：

```text
results/neumann_mixed_pointcloud.vtk
results/neumann_mixed_grid.vtk
results/neumann_rmse_vs_walks.png
results/neumann_epsilon_tradeoff.png
```

CSV 结果追加到：

```text
results/benchmark_summary.csv
```

## 5. 实际运行配置

本次正式 Neumann run 使用：

```text
queries = 100
grid = 8^3
threads = 8
seed = 32345
cube half extent = 0.22
maxSteps = 2048
```

运行命令：

```powershell
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

为什么 Neumann 使用 `maxSteps = 2048`：

- 纯 Dirichlet walk 一旦命中边界就吸收终止。
- Neumann inner boundary 会反射/继续行走，因此更容易出现长路径。
- 将 `maxSteps` 从 512 提高到 2048 能显著减少 fallback divergence。

## 6. Neumann Convergence 结果

固定：

```text
epsilon = 1e-4
maxSteps = 2048
```

改变每点 random walks 数量：

```text
M = 16, 64, 256, 1024
```

结果：

| Walks per point M | RMSE | MAE | Max abs error | Mean std error | Diverged points |
|---:|---:|---:|---:|---:|---:|
| 16 | 0.04140 | 0.02923 | 0.13797 | 0.03039 | 0 |
| 64 | 0.02497 | 0.01758 | 0.10761 | 0.01662 | 0 |
| 256 | 0.01308 | 0.00862 | 0.06754 | 0.00841 | 0 |
| 1024 | 0.01141 | 0.00580 | 0.06939 | 0.00422 | 0 |

观察：

- RMSE 随 `M` 增加总体下降。
- 从 `M=16` 到 `M=256` 的收敛趋势很明显。
- `M=1024` 继续下降，但下降幅度变小，说明 Neumann boundary handling 的 bias / geometry effects 开始与 Monte Carlo noise 一起影响误差。

展示图：

```text
results/neumann_rmse_vs_walks.png
```

推荐汇报表述：

```text
The mixed Neumann benchmark also shows decreasing RMSE as the number of walks increases.
Compared with the Dirichlet-only case, the convergence is less ideal because Neumann reflection introduces longer paths and additional boundary approximation error.
```

中文表述：

```text
Mixed Neumann benchmark 中，RMSE 仍然随着每点随机游走次数增加而下降。相比纯 Dirichlet 问题，Neumann 边界需要反射并继续行走，因此路径更长，边界近似误差也更明显，收敛曲线没有 Dirichlet-only 情况那么理想。
```

## 7. Neumann Epsilon Sweep 结果

固定：

```text
walksPerPoint = 256
maxSteps = 2048
```

改变：

```text
epsilon = 1e-2, 1e-3, 1e-4, 1e-5
```

结果：

| Epsilon | RMSE | MAE | Mean steps | Diverged points |
|---:|---:|---:|---:|---:|
| 1e-2 | 0.15294 | 0.07613 | 6.75 | 0 |
| 1e-3 | 0.02676 | 0.01489 | 15.90 | 0 |
| 1e-4 | 0.01249 | 0.00871 | 32.21 | 0 |
| 1e-5 | 0.01398 | 0.00970 | 48.88 | 1 |

观察：

- epsilon 从 `1e-2` 降到 `1e-4` 时，RMSE 明显下降。
- mean steps 从 `6.75` 增加到 `48.88`，说明更小的 absorption shell 导致 walk 更长。
- `epsilon=1e-5` 时出现 1 个 diverged point，说明 Neumann 反射问题在过小 epsilon 下更容易出现长路径。

展示图：

```text
results/neumann_epsilon_tradeoff.png
```

推荐汇报表述：

```text
The Neumann epsilon sweep clearly shows the boundary accuracy/runtime tradeoff.
Reducing epsilon improves accuracy until Monte Carlo noise and long reflected paths dominate.
```

中文表述：

```text
Neumann epsilon sweep 清楚展示了边界精度和运行成本之间的权衡。epsilon 从 1e-2 减小到 1e-4 时误差明显下降，但 mean steps 大幅增加；当 epsilon 进一步减小到 1e-5 时，长路径和 Monte Carlo 噪声开始占主导。
```

## 8. Structured Grid VTK 结果

Structured grid 配置：

```text
grid = 8^3 = 512 points
valid points = 508
walksPerPoint = 256
epsilon = 1e-4
maxSteps = 2048
```

结果：

```text
RMSE = 0.01196
MAE = 0.00541
max_abs_error = 0.08391
mean_std_error = 0.00476
mean_steps = 19.62
diverged_count = 0
```

ParaView 文件：

```text
results/neumann_mixed_grid.vtk
```

字段：

```text
solution
is_valid
std_error
mean_steps
samples_used
exact
abs_error
```

推荐 ParaView coloring：

```text
solution
abs_error
mean_steps
std_error
is_valid
```

Point cloud 文件：

```text
results/neumann_mixed_pointcloud.vtk
```

包含 99 个 valid query points。

## 9. 和 Dirichlet Benchmark 的区别

Dirichlet-only benchmark：

- 命中边界即吸收终止。
- 路径通常更短。
- convergence 更接近理想 Monte Carlo 行为。

Mixed Neumann benchmark：

- 命中 inner boundary 后不会直接终止。
- 需要用 Neumann value 贡献边界项，并反射/推回域内继续行走。
- 路径更长。
- 对 epsilon 和 maxSteps 更敏感。
- 更适合作为“功能覆盖”和“复杂边界条件能力”的展示。

因此报告中建议这样定位：

```text
Dirichlet-only benchmark is the primary clean accuracy benchmark.
Mixed Neumann benchmark demonstrates support for Neumann boundary handling and validates it against the same analytic solution.
```

中文：

```text
纯 Dirichlet benchmark 是最干净的主精度测试；Mixed Neumann benchmark 则用于展示 solver 对 Neumann 边界条件的支持，并用同一个解析解进行验证。
```

## 10. 汇报展示建议

建议展示顺序：

1. 先讲 Dirichlet-only benchmark，说明主 accuracy test。
2. 再引出 Neumann benchmark：inner Bunny boundary 改为 Neumann，outer cube 保持 Dirichlet。
3. 展示 `neumann_rmse_vs_walks.png`，说明 RMSE 随 M 增加总体下降。
4. 展示 `neumann_epsilon_tradeoff.png`，说明 epsilon 越小 mean steps 越大，并指出 Neumann 反射使问题更难。
5. 打开 `neumann_mixed_grid.vtk`，展示 `solution`、`abs_error`、`mean_steps`。
6. 强调 Neumann benchmark 是对功能完整性的补充，而 Dirichlet benchmark 是更干净的主精度 benchmark。

## 11. 一页总结

英文：

```text
In addition to the Dirichlet-only benchmark, we added a mixed-boundary Neumann test on the Bunny mesh.
The outer AABB uses exact Dirichlet data, while the inner Bunny boundary uses Neumann data derived from the analytic solution u=x+y+z.
The Neumann convergence benchmark shows decreasing RMSE as the number of walks increases.
The epsilon sweep shows a clear boundary accuracy/runtime tradeoff: smaller epsilon improves accuracy but increases mean walk steps.
Compared with the Dirichlet-only test, Neumann paths are longer and more sensitive to maxSteps, so we use maxSteps=2048 for robustness.
```

中文：

```text
除了纯 Dirichlet benchmark，我们新增了 Bunny 网格上的 mixed-boundary Neumann 测试。外部 AABB 使用解析 Dirichlet 条件，内部 Bunny 边界使用由解析解 u=x+y+z 推导出的 Neumann 条件。实验显示，随着每点游走次数增加，Neumann benchmark 的 RMSE 总体下降；epsilon sweep 则展示了边界精度与平均步数之间的权衡。相比 Dirichlet-only 测试，Neumann 反射会产生更长路径，对 maxSteps 更敏感，因此本实验使用 maxSteps=2048 保证鲁棒性。
```

