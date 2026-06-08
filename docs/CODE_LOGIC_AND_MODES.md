# WoSt 代码逻辑与 Mode 导读

这份文档按 `main.cpp` 的执行顺序整理当前 C++ 代码，重点解释每个 `--mode` 的实现路径、作用、关键参数与输出文件。阅读顺序建议是：先理解整体 PDE/domain 与随机游走内核，再看 `main()` 如何分发 mode，最后逐个看 mode 做的实验。

## 1. 程序整体在求什么

程序实现的是 Walk on Spheres / Walk on Stars 风格的 Monte Carlo 求解器，用于在一个“双边界区域”内估计线性测试解：

```text
u(x, y, z) = x + y + z
```

计算域由两部分组成：

```text
domain = outer cube 内部 - inner OBJ mesh 内部
```

也就是说：

- 外边界是 `CubeOuterBoundary` 表示的轴对齐立方体。
- 内边界是 `WoStGeometryBackend` 从 OBJ 读入的三角网格。
- `WoStKernel::InDomain(x)` 判断 `x` 是否在外立方体内且不在内网格内。

边界条件目前围绕线性精确解构造：

- Dirichlet：内边界和外边界都给定 `g(p) = p.x + p.y + p.z`。
- Mixed Neumann：外边界仍是 Dirichlet；内边界改为 Neumann，法向导数 `h(p) = grad(u) dot n = (1,1,1) dot n`。
- 体源项 `source` 固定为 0，所以大多数 mode 实际是 Laplace 情形；接口保留 `SolvePoisson` 是为了兼容 Poisson 源项。

## 2. 关键数据结构

### `CliOptions`

`CliOptions` 保存所有命令行参数。重要字段如下：

- `mode`：选择运行哪个实验，默认 `all`。
- `objFile`：内边界 OBJ，默认 `./spot/spot_triangulated.obj`。
- `numQueryPoints`：随机 query 点数量，默认 20000。
- `gridRes`：规则网格每个轴的分辨率，默认 48。
- `numThreads`：OpenMP 线程数，0 表示用当前默认值。
- `seed`：全局随机种子，默认 12345。
- `cubeHalfExtent`：外立方体半边长，默认 1.0。
- `walks` / `epsilon` / `boundaryMode`：demo 和 case 类 mode 的核心参数。
- `minSamples` / `maxSamples` / `batchSize` / `targetRSE` / `rseEps`：优化实验中的自适应采样参数。
- `lazyRefineDistance` / `lazySuspiciousRatio`：lazy star refinement 的触发阈值。
- `traceOut` / `summaryOut` / `outPath` / `csvPath` / `pointsIn`：不同 mode 的输出路径。
- `useAntithetic`：是否使用反向方向配对的 antithetic sampling。

### `BoundarySetup`

`BoundarySetup` 把 PDE 边界与源项包装成一组 callback：

- `gInner`：内边界 Dirichlet 值。
- `gOuter`：外边界 Dirichlet 值。
- `isInnerNeumann`：判断内边界点是否属于 Neumann 区域。
- `hInner`：内边界 Neumann 法向导数。
- `source`：体源项。

`BoundaryFromMode("neumann")` 返回 mixed Neumann 问题；其他字符串默认返回纯 Dirichlet 问题。

### `WoStParams`

`WoStParams` 控制单个 query 点的随机游走：

- `numSamples`：固定采样时的 walk 数。
- `maxSteps`：每条 walk 的最大步数；Neumann 通常设为 2048，Dirichlet 通常为 512。
- `eps`：吸收半径，距离真实边界小于它时触发边界处理。
- `adaptiveSampling`：是否按标准误提前停止。
- `minSamples` / `maxSamples` / `batchSize`：自适应采样范围与检查频率。
- `targetStdErr`：绝对标准误停止阈值。
- `useRelativeStdErr` / `targetRSE` / `rseEps`：相对标准误停止规则。
- `useAntitheticSampling`：每次用方向 `d` 和 `-d` 配对，平均成一个 estimator。
- `useLazyStarRefinement`：是否先用快速近似距离，必要时再计算完整 star radius。
- `lazyRefineDistance` / `lazySuspiciousRatio`：决定什么时候从 fast 距离升级到 exact star radius。

### `WalkResult`

`SolvePoisson` 返回 `WalkResult`：

- `value`：Monte Carlo 估计值。
- `stdErr`：估计标准误。
- `sampleVariance`：walk estimator 的方差。
- `meanSteps`：平均步数。
- `samplesUsed`：实际使用样本数。
- `anyDiverged`：是否有 walk 达到 `maxSteps`。
- `starQueries` / `fastOnlyStarQueries` / `exactStarQueries`：几何查询统计，用于 lazy refinement 诊断。

## 3. 几何层：`WoStGeometryBackend`

`WoStGeometryBackend` 负责内边界网格的所有几何查询。

构造流程：

1. `LoadOBJ` 读取 OBJ 中的 `v` 和 `f`，支持三角面，也会把四边形拆成两个三角形。
2. `ComputeNormals` 为每个三角形计算单位法线。
3. 用 `tiny_bvh` 构建 BVH，加速 closest point 和 ray intersection。
4. `BuildSilhouetteEdges` 用半边邻接关系提取 silhouette edge。对 open boundary edge，会把它视作永远是 silhouette。
5. 如果编译环境支持 AVX-512，会额外构建 SoA 数据用于 silhouette SIMD 查询。

关键查询：

- `ClosestPoint(x, bp)`：用 BVH 找离 `x` 最近的三角形点，并返回边界点、法线、距离。
- `ClosestSilhouette(x, bp)`：遍历 silhouette edge，找从 `x` 看过去最近的 silhouette。
- `StarRadius(x, closestBoundary, closestSilhouette)`：返回 `min(closest boundary distance, closest silhouette distance)`。这就是 Walk on Stars 的安全半径。
- `FastStarRadius(x)`：快速返回 star radius 的标量版本。
- `FastBoundaryDistance(x)`：只算 BVH 最近三角形距离，不查 silhouette；用于 lazy refinement 的低成本近似。
- `IntersectRay(origin, dir, tMax, ...)`：判断当前 sphere/star 内沿方向 `dir` 是否撞到内边界。
- `IsInside(x)`：用 ray casting 统计穿越次数，奇数表示在内网格内部。

## 4. 外边界层：`CubeOuterBoundary`

外边界是一个 AABB：

- `ClosestPoint`：如果点在 cube 内，直接计算到 6 个面的最小距离；如果在外部，则 clamp 到 AABB。
- `FastStarRadius`：cube 是凸的，从内部看没有 silhouette，因此最近面距离就是 star radius。
- `IntersectRay`：用 slab method 做 Ray-AABB intersection。
- `IsInside`：简单坐标范围判断。

## 5. 求解核心：`WoStKernel::SolvePoisson`

`SolveLaplace` 只是调用 `SolvePoisson`，并把 source 设为 0。

`SolvePoisson` 的单条 walk 逻辑如下：

1. 从 query 点 `x0` 开始，累加量 `acc = 0`。
2. 每一步先计算外边界半径 `R_outer = outer_.FastStarRadius(x)`。
3. 对内边界先算 `fastInnerDist = inner_.FastBoundaryDistance(x)`。
4. 如果不使用 lazy refinement，或快速半径太小，或 inner/outer 距离比例可疑，则调用 `inner_.StarRadius` 得到精确 `R_inner`，同时记录 `exactStarQueries`。
5. 否则只使用 `fastInnerDist` 作为内边界半径，记录 `fastOnlyStarQueries`。
6. 当前可走半径 `R = min(R_inner, R_outer)`。
7. 如果距离实际边界小于 `eps`：
   - 外边界更近：取 `gOuter`，walk 结束。
   - 内边界更近且是 Neumann：加上 `hInner * jumpDist`，沿内边界法线跳出一小段继续 walk。
   - 内边界更近且是 Dirichlet：取 `gInner`，walk 结束。
8. 如果没有吸收，则随机采样单位球方向 `dir`。
9. 在半径 `R` 内做内边界 ray intersection：
   - 若击中 Dirichlet 内边界：加上 `gInner` 并结束。
   - 若击中 Neumann 内边界：按法向导数添加贡献，反射方向并继续。
   - 若未击中：走到 `x + R * dir`。
10. 每步还会加 Poisson 源项贡献：`acc -= (R*R/6) * f(x)`。当前测试里 `f=0`，所以该项为 0。
11. 如果超过 `maxSteps` 仍未结束，就选择当前点最近的内/外边界值作为 fallback，并标记 diverged。

多样本统计：

- 固定采样：跑 `numSamples` 条 walk。
- 自适应采样：最多 `maxSamples`，至少 `minSamples`，每 `batchSize` 检查一次标准误。
- 相对标准误模式：`stdErr / max(abs(mean), rseEps) < targetRSE` 时停止。
- Antithetic 模式：共享同一条方向 tape，分别跑方向 `d` 与 `-d`，把两条结果平均成一个 estimator。

## 6. `main()` 启动与调度顺序

`main()` 的逻辑非常直接：

1. 调 `ParseArgs` 解析命令行。
2. 调 `ResolveObjPath` 修正 OBJ 路径，兼容从 build 目录运行。
3. 如果启用 OpenMP 且指定 `--threads`，调用 `omp_set_num_threads`。
4. 检查 `mode` 是否属于允许列表。
5. 打印当前配置。
6. 构造几何：
   - `WoStGeometryBackend interior(opts.objFile)`
   - `CubeOuterBoundary exterior([-L,-L,-L], [L,L,L])`
   - `WoStKernel kernel(interior, exterior)`
7. 对少数单独 mode 先执行并立即返回：
   - `demo_point`
   - `bias_detector`
   - `variance_adaptive`
   - `points`
   - `point_bias`
   - `case`
8. 其余 mode 按固定顺序执行。`all` 会跑基础 benchmark；`optimization` 会跑优化实验组。

`all` 会执行：

```text
convergence -> epsilon -> grid -> adaptive -> neumann -> threads -> geometry
```

`optimization` 会执行：

```text
adaptive_compare -> antithetic -> lazy -> epsilon_extrapolation -> neumann_sanity
```

注意：代码中有 `RunOptimizationExperiments` 包装函数，但 `main()` 实际没有调用它，而是逐个调用各优化 mode。

## 7. 通用 benchmark 辅助函数

### `RunPointBenchmark`

大多数点采样 benchmark 都走这里。

流程：

1. 用 `GenerateQueryPoints` 在外 cube 中生成随机点。
2. 对每个点先调用 `kernel.InDomain`，跳过非计算域点。
3. 每个有效点设置独立 seed：`SeedFor(baseSeed, pointIndex, stream)`。
4. 调用 `kernel.SolvePoisson`。
5. 保存 `PointSolution`，其中 `exact = LinearExact(point)`。
6. 调 `AccumulateMetrics` 计算 RMSE、MAE、max error、mean std error、mean steps、吞吐率等。
7. 打印结果并 append 到 `results/benchmark_summary.csv`。
8. 如要求写点云，输出 VTK point cloud。

### `RunGridBenchmark`

规则网格版本：

1. 在 `[-L,L]^3` 上构造 `gridRes^3` 个点。
2. 对 domain 内点调用 `SolvePoisson`。
3. 写 `STRUCTURED_POINTS` VTK。
4. 同样 append 到 `results/benchmark_summary.csv`。

### `RunExperimentCase`

优化实验共用函数，输出到 `experiments/`：

1. 随机生成 query 点。
2. 对有效点求解。
3. 调 `AccumulateExperimentMetrics` 统计 RMSE、MAE、相对误差、样本数分布、star refinement 比例等。
4. append 到 `experiments/optimization_summary.csv`。
5. 第一轮 rep 通常还会 append 逐点数据到 `experiments/optimization_points.csv`。
6. 某些实验会额外写 VTK。

## 8. 各 mode 详解

### `convergence`

实现函数：`RunConvergence`

作用：测试固定 walk 数增加时，Monte Carlo 误差如何下降。

具体做法：

- 使用纯 Dirichlet 边界。
- 依次测试 `numSamples = 16, 64, 256, 1024`。
- 每组都调用 `RunPointBenchmark`，benchmark 名为 `convergence`。
- 当 `M == 256` 时额外写：
  - `results/linear_dirichlet_pointcloud.vtk`

主要输出：

- `results/benchmark_summary.csv`
- 可选点云 VTK

适合理解的问题：

- walk 数和 RMSE / std error 的关系。
- 单点平均步数与运行时间。

### `epsilon`

实现函数：`RunEpsilonSweep`

作用：测试吸收半径 `eps` 对误差和步数的影响。

具体做法：

- 使用纯 Dirichlet 边界。
- 固定 `numSamples = 256`。
- 依次测试 `eps = 1e-2, 1e-3, 1e-4, 1e-5`。
- 每组调用 `RunPointBenchmark`，benchmark 名为 `epsilon`。

主要输出：

- `results/benchmark_summary.csv`

适合理解的问题：

- `eps` 越小，边界偏差通常更低，但 walk 更长。
- `eps` 太大可能更快，但边界吸收误差更明显。

### `grid`

实现函数：`RunGrid`

作用：在规则三维网格上输出解场，方便可视化空间分布。

具体做法：

- 使用纯 Dirichlet 边界。
- 固定 `numSamples = 256`。
- 调 `RunGridBenchmark`，benchmark 名为 `linear_dirichlet_grid`。
- 网格范围是 `[-cubeHalfExtent, cubeHalfExtent]^3`。
- domain 外点写为 NaN 或 invalid mask。

主要输出：

- `results/benchmark_summary.csv`
- `results/linear_dirichlet_grid.vtk`

适合理解的问题：

- 解、误差、std error、mean steps 在空间上的分布。

### `adaptive`

实现函数：`RunAdaptive`

作用：比较固定采样与旧式绝对标准误自适应采样。

具体做法：

1. 先跑固定采样：
   - `numSamples = 1024`
   - benchmark 名 `adaptive_fixed`
2. 再跑自适应采样：
   - `adaptiveSampling = true`
   - `minSamples = 32`
   - `maxSamples = 1024`
   - `batchSize = 32`
   - `targetStdErr = 1e-3`
   - benchmark 名 `adaptive`
3. 最后在规则网格上跑 adaptive，benchmark 名 `adaptive_grid`。

主要输出：

- `results/benchmark_summary.csv`
- `results/adaptive_sampling_grid.vtk`

适合理解的问题：

- 自适应采样是否能减少平均 samples used。
- 在不同空间位置，采样数是否集中在高方差区域。

### `neumann`

实现函数：`RunNeumannBenchmark`

作用：测试内边界为 Neumann、外边界为 Dirichlet 的 mixed boundary 实现。

具体做法：

1. 构造 `MakeLinearInnerNeumannProblem`：
   - 内边界全部 Neumann。
   - 外边界 Dirichlet。
   - `h = (1,1,1) dot normal`。
2. 跑 Neumann convergence：
   - `numSamples = 16, 64, 256, 1024`
   - `maxSteps = 2048`
   - benchmark 名 `neumann_convergence`
   - `M == 256` 时写 `results/neumann_mixed_pointcloud.vtk`
3. 跑 Neumann epsilon sweep：
   - `eps = 1e-2, 1e-3, 1e-4, 1e-5`
   - `numSamples = 256`
   - benchmark 名 `neumann_epsilon`
4. 跑规则网格：
   - benchmark 名 `neumann_mixed_grid`
   - 写 `results/neumann_mixed_grid.vtk`

主要输出：

- `results/benchmark_summary.csv`
- `results/neumann_mixed_pointcloud.vtk`
- `results/neumann_mixed_grid.vtk`

适合理解的问题：

- Neumann 反射/跳出逻辑是否稳定。
- Neumann 下为什么需要更大的 `maxSteps`。

### `threads`

实现函数：`RunThreadScaling`

作用：测试 OpenMP 线程数扩展效果。

具体做法：

- 使用纯 Dirichlet 边界。
- 固定 `numSamples = 256`。
- 线程数从 1 开始按 2 倍增长直到 `--threads` 或当前最大线程数。
- 每个线程数调用 `omp_set_num_threads`。
- 调 `RunPointBenchmark`，benchmark 名 `thread_scaling`。

主要输出：

- `results/benchmark_summary.csv`

适合理解的问题：

- 点级并行的 scaling。
- `points_per_second` 和 `walks_per_second` 随线程数变化。

### `geometry`

实现函数：`RunGeometryBenchmark`

作用：只测试几何距离查询性能，不跑 PDE 随机游走。

具体做法：

- query 数取 `max(200, min(numQueryPoints, 5000))`。
- 先跑 `tiny_bvh` 后端：
  - 实际调用 `geometry.FastBoundaryDistance`
- 再判断 brute force 工作量：
  - 如果 `geometryQueries * triangleCount > 250000000`，跳过 brute force。
  - 否则跑 `BruteForceBoundaryDistance`。

主要输出：

- `results/geometry_benchmark.csv`

适合理解的问题：

- BVH 最近距离查询相比暴力三角形遍历的加速比。
- 几何层是否成为瓶颈。

### `case`

实现函数：`RunSingleCaseBenchmark`

作用：用命令行指定的 `--walks`、`--epsilon`、`--boundary` 跑一个单独 benchmark。

具体做法：

- `BoundaryFromMode(opts.boundaryMode)` 选择 Dirichlet 或 Neumann。
- `numSamples = opts.walks`。
- `eps = opts.epsilon`。
- Neumann 时 `maxSteps = 2048`，否则 512。
- benchmark 名：
  - `case_dirichlet`
  - `case_mixed_neumann`

主要输出：

- `results/benchmark_summary.csv`

适合理解的问题：

- 快速验证一组参数。
- 给脚本或配置文件提供统一 case 入口。

### `demo_point`

实现函数：`RunDemoPoint`

作用：对单个点求解，并输出前若干条 walk 的轨迹，用于演示和调试。

具体做法：

1. 检查 `--point X Y Z` 是否在 domain 内。
2. 用 `--boundary` 选择边界模式。
3. 用 `--walks`、`--epsilon`、`--seed` 求解一次。
4. 调 `TraceWalks` 记录最多 `--trace-walks` 条 walk 的事件。
5. 写 trace CSV 和 summary CSV。

trace 中事件类型包括：

- `start`
- `sphere_step`
- `dirichlet_hit`
- `neumann_reflect`
- `max_step`
- `end`

主要输出：

- 默认 `results/live_trace.csv`
- 默认 `results/live_demo_summary.csv`

适合理解的问题：

- 单条 walk 如何移动。
- Dirichlet 吸收和 Neumann 反射事件在轨迹里如何出现。

### `bias_detector`

实现函数：`RunBiasDetector`

作用：在规则网格上比较 `epsilon` 和 `epsilon/2` 的估计差异，用于发现可能的边界偏差区域。

具体做法：

- 使用 `--boundary` 指定 Dirichlet 或 Neumann。
- 对每个有效网格点跑两次：
  - `eps = opts.epsilon`
  - `eps = opts.epsilon * 0.5`
- 计算：
  - `bias = abs(value_eps - value_half)`
  - `normalizedBias = bias / (stdErr_eps + stdErr_half + 1e-6)`
  - `absErrEps`
  - `absErrHalf`
- 统计 mean/max/p95 bias，超过 `--bias-threshold` 的比例。

主要输出：

- 默认 `results/boundary_bias_detector.vtk`
- 默认 `results/boundary_bias_summary.csv`

适合理解的问题：

- 哪些空间区域对 `eps` 更敏感。
- 高 normalized bias 是否集中在边界附近或几何复杂区域。

### `variance_adaptive`

实现函数：`RunVarianceAdaptive`

作用：基于 pilot 方差估计，为每个点预测所需 samples，并与固定 samples 对照。

具体做法：

1. 生成同一批随机 query 点。
2. 跑固定采样 baseline：
   - `fixed_256`
   - `fixed_512`
   - `fixed_1024`
3. 跑方差驱动自适应：
   - 默认 tau：`0.003, 0.005, 0.008`
   - 如果 `--target-std-error` 不在默认列表，也额外加入。
4. 对 adaptive 方法：
   - 先用 `--pilot-samples` 跑 pilot。
   - 用 `ceil(sampleVariance / tau^2)` 预测样本数。
   - clamp 到 `[--min-samples, --max-samples]`。
   - 再用预测样本数正式求解。

主要输出：

- 默认 `results/variance_adaptive_points.csv`
- 默认 `results/variance_adaptive_summary.csv`
- 默认 `results/variance_adaptive_comparison.csv`

适合理解的问题：

- 每个点的方差是否能预测所需采样量。
- 在相近 RMSE 下，adaptive 是否降低 mean samples。

### `points`

实现函数：`RunPointListBenchmark`

作用：从外部 CSV 读取指定点列表，对这些点逐个求解。

输入要求：

- `--points-in path`
- CSV 必须包含列 `x,y,z`。

具体做法：

- 读取所有点。
- 用 `--boundary` 选择边界。
- `numSamples = --walks`。
- `eps = --epsilon`。
- 可选 `--antithetic`。
- 对每个点输出详细结果，包括是否 valid。

主要输出：

- 默认 `results/point_list_results.csv`，或 `--out` 指定路径。
- 如果 `--csv` 非空，会 append 一行 summary。

适合理解的问题：

- 对一组固定空间点重复实验。
- 与 Python 脚本或外部采样策略对接。

### `point_bias`

实现函数：`RunPointListBias`

作用：对外部 CSV 指定点列表做 `epsilon` vs `epsilon/2` 偏差诊断。

输入要求：

- `--points-in path`
- CSV 必须包含列 `x,y,z`。

具体做法：

- 与 `points` 类似读取点。
- 对每个有效点跑两次：
  - `eps = --epsilon`
  - `eps = --epsilon / 2`
- 写逐点 bias、normalized bias、两个 epsilon 下的误差、方差和步数。

主要输出：

- 默认 `results/point_bias.csv`，或 `--out` 指定路径。

适合理解的问题：

- 对可控点集做边界偏差诊断。
- 与 controlled geometry 实验配合。

### `adaptive_compare`

实现函数：`RunAdaptiveComparison`

作用：优化实验之一，比固定采样、绝对标准误自适应、相对标准误自适应。

具体做法：

- 使用纯 Dirichlet 边界。
- 重复 3 个 rep，每个 rep seed 不同。
- 每个 rep 跑：
  - `fixed`：固定 `numSamples = opts.maxSamples`
  - `old_absolute_stderr`：`adaptiveSampling = true`，`targetStdErr = 1e-3`
  - `relative_stderr`：`adaptiveSampling = true`，`useRelativeStdErr = true`
- 第一轮 rep 会写逐点数据。
- 第一轮 relative stderr 会写：
  - `experiments/adaptive_relative_points.vtk`

主要输出：

- `experiments/optimization_summary.csv`
- `experiments/optimization_points.csv`
- `experiments/adaptive_relative_points.vtk`

适合理解的问题：

- 绝对标准误与相对标准误的停止准则差异。
- 自适应采样对样本数分布的影响。

### `antithetic`

实现函数：`RunAntitheticComparison`

作用：比较普通采样和 antithetic sampling。

具体做法：

- 使用纯 Dirichlet 边界。
- 重复 3 个 rep。
- 每个 rep 跑：
  - `normal`
  - `antithetic`
- antithetic 内部通过共享方向 tape 跑 `d` 和 `-d`，再把两条 walk 平均。

主要输出：

- `experiments/optimization_summary.csv`
- `experiments/optimization_points.csv`

适合理解的问题：

- 反向方向配对是否降低 sample variance。
- antithetic 是否改变平均步数或运行成本。

### `lazy`

实现函数：`RunLazyRefinementComparison`

作用：比较完整精确 star radius 与 lazy star refinement。

具体做法：

- 使用纯 Dirichlet 边界。
- 重复 3 个 rep。
- 每个 rep 先跑：
  - `full_exact`：`useLazyStarRefinement = false`
- 再跑 lazy 阈值组：
  - `lazy_threshold_x1`
  - `lazy_threshold_x4`
  - `lazy_threshold_x16`
- 基准阈值为：
  - 如果指定 `--lazy-threshold`，用该值。
  - 否则用 `2 * BaseLinearParams().eps`。
- 第一轮 `lazy_threshold_x1` 写：
  - `experiments/lazy_refinement_points.vtk`

主要输出：

- `experiments/optimization_summary.csv`
- `experiments/optimization_points.csv`
- `experiments/lazy_refinement_points.vtk`

适合理解的问题：

- 跳过 silhouette exact refinement 能省多少几何查询。
- refinement ratio 与 RMSE 是否有明显 trade-off。

### `epsilon_extrapolation`

实现函数：`RunEpsilonExtrapolation`

作用：比较较大 epsilon 与 half epsilon 的结果，为后续 epsilon extrapolation / bias 分析提供数据。

具体做法：

- 使用纯 Dirichlet 边界。
- 重复 3 个 rep。
- 每个 rep 跑：
  - `epsilon`：`eps = 1e-2`
  - `epsilon_half`：`eps = 5e-3`

主要输出：

- `experiments/optimization_summary.csv`
- `experiments/optimization_points.csv`

适合理解的问题：

- 较大 epsilon 的边界偏差有多明显。
- half epsilon 是否显著降低误差。

### `neumann_sanity`

实现函数：`RunNeumannSanity`

作用：专门验证 Neumann 法线方向和 mixed boundary 逻辑。

具体做法：

1. 生成一个球 OBJ：
   - `experiments/generated/inner_sphere.obj`
   - 半径 0.35，32 slices，16 stacks。
2. 用该球作为内边界，外边界仍是 cube。
3. 对几个 probe 点调用 `sphere.ClosestPoint`。
4. 比较 mesh normal 与期望径向 normal 的 dot product。
5. 写 normal 诊断 CSV：
   - `experiments/neumann_normal_diagnostics.csv`
6. 用 mixed Neumann 边界跑 3 个 rep 的 benchmark：
   - experiment 名 `neumann_sanity`
   - method 名 `sphere_cube`

主要输出：

- `experiments/neumann_normal_diagnostics.csv`
- `experiments/optimization_summary.csv`
- `experiments/optimization_points.csv`
- `experiments/generated/inner_sphere.obj`

适合理解的问题：

- OBJ 面朝向是否与 Neumann 外法线约定一致。
- Neumann 求解在简单球几何上是否稳定。

### `optimization`

实现位置：`main()` 中的组合 mode

作用：一次运行所有优化实验。

实际执行顺序：

```text
adaptive_compare
antithetic
lazy
epsilon_extrapolation
neumann_sanity
```

主要输出：

- `experiments/optimization_summary.csv`
- `experiments/optimization_points.csv`
- 若干 VTK 和 normal diagnostic 文件。

注意：`optimization` 不会自动运行 `variance_adaptive`，因为 `variance_adaptive` 在 `main()` 中是一个提前返回的单独 mode。

### `all`

实现位置：`main()` 中的组合 mode

作用：一次运行基础 benchmark。

实际执行顺序：

```text
convergence
epsilon
grid
adaptive
neumann
threads
geometry
```

主要输出：

- `results/benchmark_summary.csv`
- `results/geometry_benchmark.csv`
- 多个 VTK 文件。

注意：`all` 不包含 `case`、`demo_point`、`bias_detector`、`variance_adaptive`、`points`、`point_bias`，也不包含 `optimization` 组。

## 9. 输出文件总览

`results/benchmark_summary.csv`：

- 基础 benchmark 汇总。
- 包括 RMSE、MAE、max error、mean std error、mean steps、吞吐率、diverged count 等。

`results/geometry_benchmark.csv`：

- 几何距离查询 benchmark。
- 比较 `tiny_bvh` 和可选 brute force。

`experiments/optimization_summary.csv`：

- 优化实验汇总。
- 额外包含 samples used 分布、sample variance、relative error、star query/refinement ratio。

`experiments/optimization_points.csv`：

- 优化实验逐点数据。
- 通常只在 rep 0 写，以控制文件大小。

VTK 文件：

- `WriteVTKPointCloud` 写 scattered point cloud。
- `WriteVTKStructuredPoints` 写规则网格。
- 可用 ParaView 查看 `solution`、`std_error`、`sample_variance`、`mean_steps`、`samples_used`、`abs_error` 等 scalar。

## 10. 常用命令示例

基础 Dirichlet 收敛：

```powershell
.\build\WoSt.exe --mode convergence --queries 20000 --obj .\spot\spot_triangulated.obj
```

单组参数快速测试：

```powershell
.\build\WoSt.exe --mode case --boundary dirichlet --walks 256 --epsilon 1e-4 --queries 5000
```

Mixed Neumann 测试：

```powershell
.\build\WoSt.exe --mode case --boundary neumann --walks 256 --epsilon 1e-4 --queries 5000
```

单点轨迹演示：

```powershell
.\build\WoSt.exe --mode demo_point --point 0.05 0.02 0.08 --walks 256 --trace-walks 8
```

边界偏差热力图：

```powershell
.\build\WoSt.exe --mode bias_detector --boundary dirichlet --grid 48 --walks 256 --epsilon 1e-4
```

外部点列表：

```powershell
.\build\WoSt.exe --mode points --points-in .\points.csv --out .\results\point_list_results.csv
```

优化实验组：

```powershell
.\build\WoSt.exe --mode optimization --queries 20000 --max-samples 1024 --min-samples 64
```

## 11. 快速读代码路线

如果想最快掌握代码细节，建议按这个顺序读：

1. `main.cpp` 顶部的 `CliOptions`、`BenchmarkMetrics`、`ExperimentMetrics`、`BoundarySetup`。
2. `MakeLinearDirichletProblem`、`MakeLinearInnerNeumannProblem`、`BoundaryFromMode`。
3. `src/utils.hpp` 中的 `WoStParams`、`WalkResult`、`PointSolution`、VTK writer。
4. `src/WoStGeometryBackend.hpp/.cpp` 的构造、`StarRadius`、`FastBoundaryDistance`、`IntersectRay`。
5. `src/CubeOuterBoundary.hpp/.cpp` 的 `FastStarRadius` 和 `ClosestPoint`。
6. `src/WoStKernel.cpp` 的 `SolvePoisson`，这是最核心的算法。
7. 回到 `main.cpp`，读 `RunPointBenchmark`、`RunGridBenchmark`、`RunExperimentCase` 三个通用执行器。
8. 最后按本文第 8 节逐个读 `Run*` mode。

掌握这个顺序后，代码的主线可以压缩成一句话：

```text
命令行选择 mode -> 构造内外边界几何 -> 生成 query 点或网格 -> 对 domain 内点调用 SolvePoisson -> 统计误差/性能 -> 写 CSV/VTK。
```
