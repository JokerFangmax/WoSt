# Final Report Provenance

| source file path | what it contains | where used in final report |
|---|---|---|
| experiments/rerun_cross_mesh_20260606/RERUN_SUMMARY.md | Narrative rerun summary with benchmark tables and figure references. | Used for final report structure and cross-mesh interpretation. |
| experiments/geometry_sensitive_analysis_20260606/GEOMETRY_SENSITIVE_REPORT.md | Geometry-sensitive pointwise analysis report. | Used for geometry predictor and boundary-proximity claims. |
| experiments/controlled_geometry_experiments_20260606/CONTROLLED_GEOMETRY_REPORT.md | Controlled distance-bin and epsilon-distance report. | Used for matched-bin and epsilon-distance claims. |
| experiments/rerun_cross_mesh_20260606/zombie_bunny_dirichlet/zombie_vs_wost_summary.csv | Bunny Dirichlet WoSt/Zombie RMSE-vs-walks and epsilon comparison. | Experiment 1 and Figure 1. |
| experiments/rerun_cross_mesh_20260606/zombie_spot_dirichlet/zombie_vs_wost_summary.csv | Spot Dirichlet WoSt/Zombie RMSE-vs-walks and epsilon comparison. | Experiment 1 and Figure 1. |
| experiments/rerun_cross_mesh_20260606/zombie_bunny_neumann/zombie_vs_wost_neumann_summary.csv | Bunny Mixed Neumann WoSt/Zombie convergence and epsilon sweep. | Experiments 2-3 and Figures 2-3. |
| experiments/rerun_cross_mesh_20260606/zombie_spot_neumann/zombie_vs_wost_neumann_summary.csv | Spot Mixed Neumann WoSt/Zombie convergence and epsilon sweep. | Experiments 2-3, Spot anomaly discussion, and Figures 2-3. |
| experiments/rerun_cross_mesh_20260606/wost_bunny/diagnostics/boundary_bias_summary.csv | Bunny epsilon-vs-half-epsilon boundary-bias indicator summary. | Experiment 3 and Figure 4. |
| experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/boundary_bias_summary.csv | Spot epsilon-vs-half-epsilon boundary-bias indicator summary. | Experiment 3 and Figure 4. |
| experiments/geometry_sensitive_analysis_20260606/geometry_correlations.csv | Pearson correlations between pointwise geometry proxies and error/bias/variance metrics. | Experiment 4 and claim-evidence table. |
| experiments/geometry_sensitive_analysis_20260606/geometry_binned_summaries.csv | Binned summaries by nearest-distance proxy and local geometry features. | Experiment 4 and Appendix. |
| experiments/geometry_sensitive_analysis_20260606/all_point_geometry_features.csv | Pointwise enriched features for Neumann, bias, and adaptive datasets. | Experiment 4 and provenance. |
| experiments/controlled_geometry_experiments_20260606/distance_controlled_neumann.csv | Per-query controlled-bin Neumann outputs. | Experiment 5 statistics and error-bar plots. |
| experiments/controlled_geometry_experiments_20260606/distance_controlled_bias.csv | Per-query controlled-bin epsilon sensitivity indicator outputs. | Experiment 5 statistics and error-bar plots. |
| experiments/controlled_geometry_experiments_20260606/epsilon_distance_sweep.csv | Epsilon x distance x walks sweep summary. | Experiment 3/5 heatmap interpretation. |
| experiments/controlled_geometry_experiments_20260606/distance_controlled_query_counts.csv | Feasible query counts by mesh and distance bin. | Experiment 5 limitations and missing Spot bin 4. |
| experiments/rerun_cross_mesh_20260606/wost_bunny/diagnostics/variance_adaptive_comparison.csv | Bunny variance-adaptive sampling comparison. | Diagnostic/optimization tools section. |
| experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/variance_adaptive_comparison.csv | Spot variance-adaptive sampling comparison. | Diagnostic/optimization tools section. |
| experiments/rerun_cross_mesh_20260606/wost_bunny/experiments/optimization_summary.csv | Bunny antithetic, lazy refinement, and other optimization diagnostics. | Diagnostic/optimization tools section and Figures 13-14. |
| experiments/rerun_cross_mesh_20260606/wost_spot/experiments/optimization_summary.csv | Spot antithetic, lazy refinement, and other optimization diagnostics. | Diagnostic/optimization tools section and Figures 13-14. |
| experiments/rerun_cross_mesh_20260606/wost_bunny/diagnostics/live_trace.csv | Bunny live random-walk trace data. | Live tracing diagnostic discussion. |
| experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/live_trace.csv | Spot live random-walk trace data. | Live tracing diagnostic discussion. |
| experiments/rerun_cross_mesh_20260606/command_log.txt | Exact commands used for the cross-mesh rerun. | Methods and provenance. |
| experiments/controlled_geometry_experiments_20260606/command_log.txt | Exact commands used for controlled geometry experiments. | Methods and provenance. |
| reports/final_assets/controlled_matched_bin_ratios.csv | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/controlled_matched_bin_statistics.csv | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig10a_bunny_adaptive_tradeoff.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig10b_spot_adaptive_tradeoff.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig11_spot_live_trace.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig12_bvh_vs_bruteforce_supporting.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig13_antithetic_variance_diagnostic.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig14_lazy_refinement_runtime.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig1_dirichlet_rmse_vs_walks.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig2_mixed_neumann_rmse_vs_walks.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig3_neumann_epsilon_sweep.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig4_boundary_bias_indicator_summary.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig5_strongest_geometry_correlations.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig5_top10_geometry_correlations.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig5b_pointwise_error_scatter.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig6_matched_bin_abs_error_ci.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig7_matched_bin_boundary_bias_ci.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig8_matched_bin_mean_steps.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig9a_bunny_epsilon_distance_rmse.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/fig9b_spot_epsilon_distance_rmse.png | Generated final-report figure/table asset. | Main report or poster section. |
| reports/final_assets/optimization_diagnostic_summary.csv | Generated final-report figure/table asset. | Main report or poster section. |
