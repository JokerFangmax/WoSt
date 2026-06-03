# Results to Commands Mapping

本文档说明汇报实验文档中的结果分别由哪些命令生成。它适合用于答辩时解释数据来源，或后续复现实验。

## 1. Build

所有 C++ benchmark 结果均基于 Release build：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_cpp.ps1
```

可执行文件：

```text
build\Release\wost.exe
```

## 2. Bunny Dirichlet Accuracy Convergence

汇报位置：

```text
docs/BUNNY_BENCHMARK_REPORT.md
Section 6. 精度收敛结果
docs/BUNNY_RESULTS_SUMMARY.md
Accuracy Convergence
```

输出：

```text
results/benchmark_summary.csv
results/rmse_vs_walks.png
results/linear_dirichlet_pointcloud.vtk
```

生成命令：

```powershell
.\build\Release\wost.exe --mode convergence --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

对应 CSV rows：

```text
benchmark_name = convergence
walks_per_point = 16, 64, 256, 1024
```

汇报中使用的数据：

| Walks per point | RMSE |
|---:|---:|
| 16 | 0.03042 |
| 64 | 0.01570 |
| 256 | 0.00778 |
| 1024 | 0.00399 |

## 3. Bunny Dirichlet Epsilon Sweep

汇报位置：

```text
docs/BUNNY_BENCHMARK_REPORT.md
Section 7. Epsilon Sweep 结果
docs/BUNNY_RESULTS_SUMMARY.md
Epsilon Sweep
```

输出：

```text
results/benchmark_summary.csv
results/epsilon_tradeoff.png
```

生成命令：

```powershell
.\build\Release\wost.exe --mode epsilon --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

对应 CSV rows：

```text
benchmark_name = epsilon
epsilon = 1e-2, 1e-3, 1e-4, 1e-5
```

汇报中使用的数据：

| Epsilon | RMSE | Mean steps |
|---:|---:|---:|
| 1e-2 | 0.00857 | 6.24 |
| 1e-3 | 0.00806 | 13.79 |
| 1e-4 | 0.00781 | 21.39 |
| 1e-5 | 0.00765 | 28.83 |

## 4. Bunny Dirichlet Structured Grid VTK

汇报位置：

```text
docs/BUNNY_BENCHMARK_REPORT.md
Section 8. Structured VTK 可视化结果
docs/BUNNY_RESULTS_SUMMARY.md
Structured Grid Output
```

输出：

```text
results/linear_dirichlet_grid.vtk
results/benchmark_summary.csv
```

生成命令：

```powershell
.\build\Release\wost.exe --mode grid --obj .\obj\Bunny.obj --grid 16 --threads 8 --seed 12345 --cube 0.22
```

对应 CSV row：

```text
benchmark_name = linear_dirichlet_grid
num_query_points = 4096
valid_points = 4018
```

ParaView 字段：

```text
solution
is_valid
std_error
mean_steps
samples_used
exact
abs_error
```

## 5. Bunny Adaptive Sampling

汇报位置：

```text
docs/BUNNY_BENCHMARK_REPORT.md
Section 9. Adaptive Sampling 结果
docs/BUNNY_RESULTS_SUMMARY.md
Adaptive Sampling
```

输出：

```text
results/benchmark_summary.csv
results/adaptive_vs_fixed.png
results/adaptive_sampling_grid.vtk
```

生成命令：

```powershell
.\build\Release\wost.exe --mode adaptive --obj .\obj\Bunny.obj --queries 500 --grid 16 --threads 8 --seed 12345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

对应 CSV rows：

```text
benchmark_name = adaptive_fixed
benchmark_name = adaptive
benchmark_name = adaptive_grid
```

汇报中使用的数据：

| Mode | RMSE | Mean samples used | Runtime |
|---|---:|---:|---:|
| Fixed 1024 | 0.00398 | 1024.00 | 55.85 s |
| Adaptive | 0.00399 | 997.71 | 54.38 s |

Structured adaptive grid：

```text
RMSE = 0.00371
mean samples used = 689.90
```

## 6. Bunny OpenMP Thread Scaling

汇报位置：

```text
docs/BUNNY_BENCHMARK_REPORT.md
Section 10. OpenMP 多线程加速
docs/BUNNY_RESULTS_SUMMARY.md
Thread Scaling
```

输出：

```text
results/benchmark_summary.csv
results/thread_speedup.png
```

生成命令：

```powershell
.\build\Release\wost.exe --mode threads --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

对应 CSV rows：

```text
benchmark_name = thread_scaling
num_threads = 1, 2, 4, 8
```

汇报中使用的数据：

| Threads | Runtime | Speedup |
|---:|---:|---:|
| 1 | 83.44 s | 1.00x |
| 2 | 42.46 s | 1.97x |
| 4 | 23.84 s | 3.50x |
| 8 | 13.62 s | 6.13x |

## 7. Bunny tiny_bvh vs Brute Force

汇报位置：

```text
docs/BUNNY_BENCHMARK_REPORT.md
Section 11. tiny_bvh vs Brute Force 几何查询
docs/BUNNY_RESULTS_SUMMARY.md
BVH vs Brute Force Geometry Query
```

输出：

```text
results/geometry_benchmark.csv
results/bvh_vs_bruteforce.png
```

生成命令：

```powershell
.\build\Release\wost.exe --mode geometry --obj .\obj\Bunny.obj --queries 3000 --threads 8 --seed 12345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

说明：

```text
The earlier geometry run with --queries 2000 was used as a preliminary check.
The report uses the later --queries 3000 run.
```

对应 CSV rows：

```text
results/geometry_benchmark.csv
benchmark_name = geometry_distance
backend_name = tiny_bvh, brute_force
```

汇报中使用的数据：

| Backend | Queries/sec | Checksum |
|---|---:|---:|
| tiny_bvh | 794,428 | 471.342 |
| brute_force | 6,169 | 471.342 |

加速比：

```text
tiny_bvh / brute_force ≈ 129x
```

## 8. Mixed Neumann Boundary Convergence

汇报位置：

```text
docs/NEUMANN_BENCHMARK_REPORT.md
Section 6. Neumann Convergence 结果
```

输出：

```text
results/benchmark_summary.csv
results/neumann_rmse_vs_walks.png
results/neumann_mixed_pointcloud.vtk
```

生成命令：

```powershell
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

对应 CSV rows：

```text
benchmark_name = neumann_convergence
walks_per_point = 16, 64, 256, 1024
max_steps = 2048
```

汇报中使用的数据：

| Walks per point | RMSE |
|---:|---:|
| 16 | 0.04140 |
| 64 | 0.02497 |
| 256 | 0.01308 |
| 1024 | 0.01141 |

## 9. Mixed Neumann Boundary Epsilon Sweep

汇报位置：

```text
docs/NEUMANN_BENCHMARK_REPORT.md
Section 7. Neumann Epsilon Sweep 结果
```

输出：

```text
results/benchmark_summary.csv
results/neumann_epsilon_tradeoff.png
```

生成命令：

```powershell
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

对应 CSV rows：

```text
benchmark_name = neumann_epsilon
epsilon = 1e-2, 1e-3, 1e-4, 1e-5
max_steps = 2048
```

汇报中使用的数据：

| Epsilon | RMSE | Mean steps | Diverged points |
|---:|---:|---:|---:|
| 1e-2 | 0.15294 | 6.75 | 0 |
| 1e-3 | 0.02676 | 15.90 | 0 |
| 1e-4 | 0.01249 | 32.21 | 0 |
| 1e-5 | 0.01398 | 48.88 | 1 |

## 10. Mixed Neumann Structured Grid

汇报位置：

```text
docs/NEUMANN_BENCHMARK_REPORT.md
Section 8. Structured Grid VTK 结果
```

输出：

```text
results/neumann_mixed_grid.vtk
results/benchmark_summary.csv
```

生成命令：

```powershell
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
```

对应 CSV row：

```text
benchmark_name = neumann_mixed_grid
num_query_points = 512
valid_points = 508
walks_per_point = 256
epsilon = 1e-4
max_steps = 2048
```

汇报中使用的数据：

```text
RMSE = 0.01196
MAE = 0.00541
max_abs_error = 0.08391
mean_std_error = 0.00476
mean_steps = 19.62
diverged_count = 0
```

ParaView 字段：

```text
solution
is_valid
std_error
mean_steps
samples_used
exact
abs_error
```

## 11. Result Cleanup Command

Neumann 调参时运行过小规模 smoke tests。最终为了让 CSV 只保留正式 Neumann rows，使用过：

```powershell
$rows = Import-Csv results\benchmark_summary.csv; $filtered = $rows | Where-Object { if ($_.benchmark_name -like 'neumann*') { ($_.benchmark_name -eq 'neumann_mixed_grid' -and $_.num_query_points -eq '512') -or ($_.benchmark_name -ne 'neumann_mixed_grid' -and $_.num_query_points -eq '100') } else { $true } }; $filtered | Export-Csv results\benchmark_summary.csv -NoTypeInformation
```

清理后重新生成 plots：

```powershell
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

## 12. Files Used in Reports

The main report documents are:

```text
docs/BUNNY_BENCHMARK_REPORT.md
docs/BUNNY_RESULTS_SUMMARY.md
docs/NEUMANN_BENCHMARK_REPORT.md
```

The command reference documents are:

```text
docs/SESSION_COMMAND_LOG.md
docs/RESULTS_COMMAND_MAPPING.md
```

