# Bunny Benchmark Workflow

本文档说明如何基于 `obj/Bunny.obj` 从头导出全部 benchmark 和可视化结果，并补充之前缺少的线程加速比和 BVH 对比实验。

当前 Bunny 模型信息：

```text
obj/Bunny.obj
vertices: 35292
faces: 70580
bounds:
  x = [-0.0947, 0.0610]
  y = [ 0.0333, 0.1873]
  z = [-0.0619, 0.0588]
```

这比默认 `spot/spot_triangulated.obj` 更适合作为高复杂度网格 benchmark。

由于 Bunny 原始坐标只占默认 `[-1,1]^3` cube 的很小一部分，推荐 Bunny 实验使用更紧的外边界：

```text
--cube 0.22
```

这样 structured VTK 中的 `is_valid` mask 和内边界附近的 `mean_steps` 更容易在 ParaView 中观察。

## 1. Build

Windows / Visual Studio build:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_cpp.ps1
```

生成的可执行文件通常位于：

```text
build\Release\wost.exe
```

## 2. Clean Old Sanity Results

如果之前跑过 quick sanity check，建议先把旧结果归档，避免 CSV 混入小规模测试数据。

```powershell
if (Test-Path results) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Move-Item results "results_sanity_$stamp"
}
New-Item -ItemType Directory -Force results
```

也可以只删除 CSV：

```powershell
Remove-Item results\benchmark_summary.csv -ErrorAction SilentlyContinue
Remove-Item results\geometry_benchmark.csv -ErrorAction SilentlyContinue
```

## 3. Recommended Full Bunny Run

`--mode all` 会运行所有 solver benchmark、grid VTK、adaptive benchmark、thread sweep 和 geometry benchmark。Bunny 有 70580 faces，因此完整运行可能比较久。

推荐先用中等规模配置：

```powershell
.\build\Release\wost.exe --mode all --obj .\obj\Bunny.obj --queries 5000 --grid 32 --threads 8 --seed 12345 --cube 0.22
```

如果机器性能足够，再提高到：

```powershell
.\build\Release\wost.exe --mode all --obj .\obj\Bunny.obj --queries 20000 --grid 48 --threads 8 --seed 12345 --cube 0.22
```

## 4. Safer Staged Run

如果不想一次跑很久，建议分阶段运行。每一步完成后都会向 CSV 追加结果。

### Accuracy convergence

```powershell
.\build\Release\wost.exe --mode convergence --obj .\obj\Bunny.obj --queries 5000 --threads 8 --seed 12345 --cube 0.22
```

输出：

```text
results/benchmark_summary.csv
results/linear_dirichlet_pointcloud.vtk
```

预期：

- `walks_per_point` 从 16、64、256、1024 增加。
- `rmse` 整体下降。
- 下降趋势接近 `O(1/sqrt(M))`。

### Epsilon tradeoff

```powershell
.\build\Release\wost.exe --mode epsilon --obj .\obj\Bunny.obj --queries 5000 --threads 8 --seed 12345 --cube 0.22
```

输出：

```text
results/benchmark_summary.csv
```

预期：

- `epsilon` 越小，`mean_steps` 通常越大。
- runtime 通常增加。
- RMSE 不一定严格下降，因为 Monte Carlo noise 仍然存在。

### Structured VTK grid

```powershell
.\build\Release\wost.exe --mode grid --obj .\obj\Bunny.obj --grid 32 --threads 8 --seed 12345 --cube 0.22
```

输出：

```text
results/linear_dirichlet_grid.vtk
```

ParaView 推荐 coloring：

```text
solution
exact
abs_error
is_valid
mean_steps
std_error
samples_used
```

预期：

- `solution` 与 `exact` 都应呈现平滑的线性场。
- `abs_error` 大部分区域较小。
- `is_valid = 0` 区域对应 PDE 域外或 Bunny 内部。
- `mean_steps` 在复杂边界附近通常更高。

### Adaptive sampling

```powershell
.\build\Release\wost.exe --mode adaptive --obj .\obj\Bunny.obj --queries 5000 --grid 32 --threads 8 --seed 12345 --cube 0.22
```

输出：

```text
results/benchmark_summary.csv
results/adaptive_sampling_grid.vtk
```

预期：

- `adaptive` 的 `mean_samples_used` 小于或接近 fixed 1024。
- `adaptive` 的 RMSE 接近 `adaptive_fixed`。
- 在 ParaView 中看 `samples_used`，应看到不同空间位置使用的样本数不同。

### Thread scaling

```powershell
.\build\Release\wost.exe --mode threads --obj .\obj\Bunny.obj --queries 5000 --threads 8 --seed 12345 --cube 0.22
```

输出：

```text
results/benchmark_summary.csv
```

CSV 中会出现：

```text
benchmark_name = thread_scaling
num_threads = 1, 2, 4, 8
```

预期：

- `num_threads` 增加时，`elapsed_seconds` 下降。
- `points_per_second` 和 `walks_per_second` 上升。
- speedup 不一定完美线性，但应该有明显并行收益。

### Geometry BVH vs brute-force

```powershell
.\build\Release\wost.exe --mode geometry --obj .\obj\Bunny.obj --queries 2000 --threads 8 --seed 12345 --cube 0.22
```

输出：

```text
results/geometry_benchmark.csv
```

该模式比较最近距离查询：

```text
tiny_bvh
brute_force
```

注意：如果 `queries * triangle_count` 太大，程序会自动跳过 brute-force，避免运行时间过长。对 Bunny 的 70580 faces，如果想强制得到 brute-force 数据，建议把 `--queries` 降低，例如：

```powershell
.\build\Release\wost.exe --mode geometry --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
```

预期：

- `tiny_bvh` 的 `queries_per_second` 明显高于 `brute_force`。
- 这可以支撑 tiny_bvh 后端带来几何查询吞吐量提升的结论。

## 5. Generate Plots

需要 Python 环境中安装 `matplotlib`。`pandas` 可选。

```powershell
python .\scripts\plot_benchmarks.py
```

生成：

```text
results/rmse_vs_walks.png
results/epsilon_tradeoff.png
results/adaptive_vs_fixed.png
results/thread_speedup.png
results/bvh_vs_bruteforce.png
```

如果提示缺少 matplotlib：

```powershell
python -m pip install matplotlib
```

如果想使用 pandas：

```powershell
python -m pip install pandas
```

## 6. Expected Final Output Files

CSV:

```text
results/benchmark_summary.csv
results/geometry_benchmark.csv
```

VTK:

```text
results/linear_dirichlet_pointcloud.vtk
results/linear_dirichlet_grid.vtk
results/adaptive_sampling_grid.vtk
```

Plots:

```text
results/rmse_vs_walks.png
results/epsilon_tradeoff.png
results/adaptive_vs_fixed.png
results/thread_speedup.png
results/bvh_vs_bruteforce.png
```

## 7. What These Results Support

完成以上 Bunny workflow 后，可以比较安全地在报告中写：

```text
We benchmarked the solver on a high-resolution Bunny mesh with 70,580 faces inside an AABB domain.
The linear Dirichlet benchmark provides an analytic ground truth.
RMSE follows the expected Monte Carlo O(1/sqrt(M)) convergence trend.
The epsilon sweep shows the expected tradeoff between boundary tolerance and mean walk length.
Structured VTK output visualizes solution, validity mask, standard error, mean steps and samples used in ParaView.
Adaptive sampling reduces or adapts per-point sample counts while preserving comparable error.
Thread sweep demonstrates OpenMP parallel scalability.
The geometry microbenchmark shows tiny_bvh has substantially higher distance-query throughput than brute-force traversal.
```

仍需谨慎：

```text
Do not claim million-triangle scalability unless a million-triangle OBJ is actually tested.
Do not claim perfect linear speedup unless thread_speedup.png supports it.
Do not claim quantitative sharp-feature boundary accuracy unless a near-boundary error metric is added.
```
