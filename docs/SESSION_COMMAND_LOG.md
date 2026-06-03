# Session Command Log

本文档整理本 session 中执行过的主要终端指令。为了便于复现和汇报，按用途分组记录；其中包括构建、清理结果、运行 Dirichlet / Neumann / Bunny benchmark、生成 plots、检查结果与调试命令。

说明：

- 本文档重点记录会影响实验结果或验证结果的命令。
- 部分中间调试命令，例如 `Get-Content`、`Select-String`、`git status`，也按类别列出。
- 代码修改本身通过编辑器/patch 完成，不属于终端运行指令，因此不逐条列入。

## 1. 文件与项目检查

查看项目文件：

```powershell
Get-ChildItem -Force
rg --files
git status --short
```

读取主要源文件：

```powershell
Get-Content main.cpp
Get-Content src\WoStKernel.hpp
Get-Content src\WoStKernel.cpp
Get-Content src\utils.hpp
Get-Content CMakeLists.txt
Get-Content README.md
Get-Content src\WoStGeometryBackend.hpp
Get-Content src\CubeOuterBoundary.hpp
Get-Content src\CubeOuterBoundary.cpp
```

搜索关键函数和字段：

```powershell
Select-String -Path src\utils.hpp -Pattern "#include|struct WoStParams|struct WalkResult|finalise|struct PointSolution|struct GridPoint|mean_steps" -Context 0,8
Select-String -Path main.cpp -Pattern "struct CliOptions|AppendBenchmarkCsv|RunPointBenchmark|RunGridBenchmark|RunConvergence|RunAdaptive|int main"
Select-String -Path src\utils.hpp -Pattern "adaptiveSampling|samplesUsed|SCALARS samples_used"
Select-String -Path src\WoStKernel.cpp -Pattern "sampleLimit|adaptiveSampling|reflect\(|finalise"
Select-String -Path scripts\plot_benchmarks.py -Pattern "def plot_rmse|def plot_epsilon|def plot_adaptive|def main"
```

## 2. Build 命令

直接调用 CMake 失败，因为 shell PATH 中没有 `cmake`：

```powershell
cmake --build build --config Release -j
```

查看 build helper：

```powershell
Get-Content build_cpp.ps1
```

PowerShell 默认执行策略阻止脚本：

```powershell
.\build_cpp.ps1
```

最终使用执行策略 bypass 构建：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_cpp.ps1
```

该 build 命令在 session 中多次执行，用于验证新增 benchmark mode 和代码修改。

## 3. 创建目录

创建 scripts 目录：

```powershell
New-Item -ItemType Directory -Force scripts
```

创建 docs 目录：

```powershell
New-Item -ItemType Directory -Force docs
```

## 4. Dirichlet Benchmark Smoke Tests

小规模 convergence sanity check：

```powershell
.\build\Release\wost.exe --mode convergence --queries 20 --threads 2 --seed 7
```

小规模 grid sanity check：

```powershell
.\build\Release\wost.exe --mode grid --grid 4 --threads 2 --seed 7
```

小规模 adaptive sanity check：

```powershell
.\build\Release\wost.exe --mode adaptive --queries 20 --grid 4 --threads 2 --seed 7
```

尝试用全局 Python 生成 plots，但缺少 matplotlib：

```powershell
python scripts\plot_benchmarks.py
```

检查 `.venv` 中 matplotlib：

```powershell
if (Test-Path .venv\Scripts\python.exe) { .\.venv\Scripts\python.exe -c "import matplotlib; print(matplotlib.__version__)" } else { 'no venv python' }
Get-Content requirements.txt
```

使用 `.venv` 生成 plots：

```powershell
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

## 5. Bunny 模型检查

列出 OBJ 文件：

```powershell
Get-ChildItem obj
```

统计 Bunny face / vertex 数量：

```powershell
(Select-String -Path obj\Bunny.obj -Pattern '^f ').Count
(Select-String -Path obj\Bunny.obj -Pattern '^v ').Count
```

查看 Bunny OBJ 前几行：

```powershell
Get-Content obj\Bunny.obj | Select-Object -First 8
```

计算 Bunny bounds：

```powershell
@'
from pathlib import Path
mins=[float('inf')]*3
maxs=[float('-inf')]*3
for line in Path('obj/Bunny.obj').read_text().splitlines():
    if line.startswith('v '):
        vals=list(map(float,line.split()[1:4]))
        for i,v in enumerate(vals):
            mins[i]=min(mins[i],v); maxs[i]=max(maxs[i],v)
print('mins', mins)
print('maxs', maxs)
print('extent', [maxs[i]-mins[i] for i in range(3)])
'@ | python -
```

## 6. 清理与归档 results

多次使用该模式归档旧结果并创建干净 `results/`：

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'; if (Test-Path results) { Move-Item results "results_archive_$stamp" }; New-Item -ItemType Directory -Force results | Out-Null; Write-Output "Clean results ready. Previous results archived as results_archive_$stamp"
```

也曾使用过只归档旧 sanity 数据的变体：

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'; if (Test-Path results) { Move-Item results "results_archive_$stamp" }; New-Item -ItemType Directory -Force results | Out-Null; Write-Output "Created clean results/. Archived old results if present as results_archive_$stamp"
```

## 7. Bunny Dirichlet Benchmark 正式运行

最终 Dirichlet Bunny 结果使用：

```powershell
.\build\Release\wost.exe --mode convergence --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode epsilon --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode grid --obj .\obj\Bunny.obj --grid 16 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode adaptive --obj .\obj\Bunny.obj --queries 500 --grid 16 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode threads --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode geometry --obj .\obj\Bunny.obj --queries 2000 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode geometry --obj .\obj\Bunny.obj --queries 3000 --threads 8 --seed 12345 --cube 0.22
```

第二次 geometry run 使用 `queries=3000`，目的是让 tiny_bvh vs brute-force timing 更稳定。plot 使用同一 backend 的最新行。

生成 plots：

```powershell
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

## 8. Neumann Benchmark 调试与正式运行

小规模 Neumann smoke test，最初使用 `maxSteps=512`，用于确认法向符号和数值趋势：

```powershell
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 40 --grid 6 --threads 8 --seed 12345 --cube 0.22
```

将 Neumann benchmark 的 `maxSteps` 提高到 2048 后，再次小规模验证：

```powershell
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 20 --grid 5 --threads 8 --seed 22345 --cube 0.22
```

正式 Neumann benchmark：

```powershell
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
```

重新生成 plots：

```powershell
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

清理 benchmark_summary 中调参用的 Neumann smoke rows，只保留正式 Neumann rows：

```powershell
$rows = Import-Csv results\benchmark_summary.csv; $filtered = $rows | Where-Object { if ($_.benchmark_name -like 'neumann*') { ($_.benchmark_name -eq 'neumann_mixed_grid' -and $_.num_query_points -eq '512') -or ($_.benchmark_name -ne 'neumann_mixed_grid' -and $_.num_query_points -eq '100') } else { $true } }; $filtered | Export-Csv results\benchmark_summary.csv -NoTypeInformation
```

清理后再次生成 plots：

```powershell
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

## 9. 结果检查命令

列出 results 文件：

```powershell
Get-ChildItem results
Get-ChildItem results | Sort-Object Name
Get-ChildItem results | Sort-Object Name | Select-Object Name,Length
Get-ChildItem results | Where-Object {$_.Name -like 'neumann*'} | Sort-Object Name | Select-Object Name,Length
```

查看 CSV：

```powershell
Get-Content results\benchmark_summary.csv
Get-Content results\geometry_benchmark.csv
```

查看最新 benchmark rows：

```powershell
Import-Csv results\benchmark_summary.csv | Where-Object {$_.benchmark_name -like 'neumann*'} | Select-Object -Last 9 | Format-Table -AutoSize
Import-Csv results\benchmark_summary.csv | Where-Object {$_.benchmark_name -like 'neumann*'} | Select-Object -Last 9 benchmark_name,walks_per_point,epsilon,rmse,mae,max_abs_error,mean_std_error,mean_steps,diverged_count,elapsed_seconds,mean_samples_used | Format-List
Import-Csv results\benchmark_summary.csv | Where-Object {$_.benchmark_name -like 'neumann*'} | Select-Object benchmark_name,num_query_points,valid_points,walks_per_point,epsilon,max_steps,rmse,mean_steps,diverged_count | Format-Table -AutoSize
```

检查 VTK 字段：

```powershell
Select-String -Path results\linear_dirichlet_grid.vtk,results\adaptive_sampling_grid.vtk,results\linear_dirichlet_pointcloud.vtk -Pattern "POINTS|POINT_DATA|DIMENSIONS|SCALARS"
Select-String -Path results\neumann_mixed_grid.vtk,results\neumann_mixed_pointcloud.vtk -Pattern "POINTS|POINT_DATA|DIMENSIONS|SCALARS"
```

检查 Python 脚本语法：

```powershell
python -m py_compile scripts\plot_benchmarks.py
```

检查是否有残留 `wost.exe`：

```powershell
Get-Process -Name wost -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,CPU,WorkingSet64
Get-Process -Name wost -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,CPU
```

检查 git 状态：

```powershell
git status --short
git diff --check
```

## 10. 后台运行尝试与调试命令

曾尝试使用 `Start-Process` 后台运行 benchmark 并写日志，但在该环境中参数/工作目录处理不稳定，因此最终改为前台运行。

后台尝试示例：

```powershell
$exe=(Resolve-Path .\build\Release\wost.exe).Path; $p=Start-Process -FilePath $exe -ArgumentList @('--mode','convergence','--obj','.\obj\Bunny.obj','--queries','5000','--threads','8','--seed','12345') -RedirectStandardOutput 'results\run_convergence.log' -RedirectStandardError 'results\run_convergence.err' -PassThru -WindowStyle Hidden; Write-Output $p.Id
```

带 working directory 的后台尝试：

```powershell
$exe=(Resolve-Path .\build\Release\wost.exe).Path; $wd=(Resolve-Path .).Path; $out=(Join-Path $wd 'results\run_convergence.log'); $err=(Join-Path $wd 'results\run_convergence.err'); $p=Start-Process -FilePath $exe -WorkingDirectory $wd -ArgumentList @('--mode','convergence','--obj','.\obj\Bunny.obj','--queries','5000','--threads','8','--seed','12345') -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden; Write-Output $p.Id
```

后台轮询示例：

```powershell
Start-Sleep -Seconds 30; $pidToCheck=[int](Get-Content results\run_convergence.pid); $p=Get-Process -Id $pidToCheck -ErrorAction SilentlyContinue; if ($p) { Write-Output "RUNNING CPU=$([math]::Round($p.CPU,1)) WorkingSetMB=$([math]::Round($p.WorkingSet64/1MB,1))" } else { Write-Output 'DONE' }; Get-Content results\run_convergence.log -ErrorAction SilentlyContinue | Select-Object -Last 60
```

测试 PowerShell job：

```powershell
$job = Start-Job -ScriptBlock { Set-Location 'C:\THU\projects\WoSt_Final_project-1'; .\build\Release\wost.exe --mode convergence --obj .\obj\Bunny.obj --queries 2 --threads 2 --seed 12345 }; Wait-Job $job; Receive-Job $job | Select-Object -First 5; Remove-Job $job
```

测试临时 ps1 后台脚本：

```powershell
$script = @'
Set-Location 'C:\THU\projects\WoSt_Final_project-1'
.\build\Release\wost.exe --mode convergence --obj .\obj\Bunny.obj --queries 2 --threads 2 --seed 12345 *> results\test_script.log
exit $LASTEXITCODE
'@; Set-Content -Path results\test_script.ps1 -Value $script -Encoding ASCII; $p=Start-Process -FilePath powershell -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Resolve-Path results\test_script.ps1).Path) -PassThru -WindowStyle Hidden; Wait-Process -Id $p.Id; Get-Content results\test_script.log | Select-Object -First 5
```

由于后台方式不稳定，正式实验均采用前台命令完成。

## 11. Python 缓存恢复相关命令

语法检查生成/修改了 Python cache。曾尝试删除后发现该 `.pyc` 文件被 git 跟踪，于是恢复。

删除尝试：

```powershell
Remove-Item scripts\__pycache__\plot_benchmarks.cpython-313.pyc -ErrorAction SilentlyContinue; if ((Test-Path scripts\__pycache__) -and -not (Get-ChildItem scripts\__pycache__ -Force)) { Remove-Item scripts\__pycache__ -Force }
```

`git restore` 因 index lock 权限失败：

```powershell
git restore -- scripts/__pycache__/plot_benchmarks.cpython-313.pyc
New-Item -ItemType Directory -Force scripts\__pycache__ | Out-Null; git restore -- scripts/__pycache__/plot_benchmarks.cpython-313.pyc
```

最终用只读 `git show` 恢复：

```powershell
cmd /c "git show HEAD:scripts/__pycache__/plot_benchmarks.cpython-313.pyc > scripts\__pycache__\plot_benchmarks.cpython-313.pyc"
```

