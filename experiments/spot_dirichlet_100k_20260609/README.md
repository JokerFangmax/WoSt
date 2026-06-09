# Spot Dirichlet 100k Case

Single fixed-case WoSt run for the Spot mesh.

## Command

```powershell
C:\THU\projects\WoSt_Final_project-1\build\Release\wost.exe --mode case --obj C:\THU\projects\WoSt_Final_project-1\spot\spot_triangulated.obj --queries 100000 --threads 8 --seed 54321 --cube 1.1 --boundary dirichlet --walks 256 --epsilon 0.0001
```

## Final 100000-query result

- boundary: dirichlet
- walks per point: 256
- max steps per walk: 512
- valid points: 92986 / 100000
- elapsed seconds: 297.815
- points per second: 335.779
- walks per second: 79930.2
- RMSE: 0.0310285
- MAE: 0.0230644
- max abs error: 0.172586
- mean std error: 0.0288797
- mean steps: 25.8671
- diverged count: 0

The CSV also contains a 10-query smoke-test row before the final run row.
