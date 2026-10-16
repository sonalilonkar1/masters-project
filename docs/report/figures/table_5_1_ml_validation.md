| Resource | Variant | Model | Selectable | Train rows | Val. rows | MAE | RMSE | R² | log1p RMSE | log1p R² |
|---|---|---|---|---|---|---|---|---|---|---|
| CPU | tuned | Decision Tree | yes | 1672 | 329 | 2.852 | 9.686 | -0.032 | 0.891 | 0.053 |
| CPU | tuned | Random Forest | yes | 1672 | 329 | 2.824 | 9.559 | -0.005 | 0.850 | 0.137 |
| CPU | tuned | XGBoost | yes | 1672 | 329 | 2.851 | 9.600 | -0.014 | 0.860 | 0.117 |
| CPU | starting | Decision Tree | no | 1672 | 329 | 3.017 | 9.808 | -0.058 | 0.981 | -0.149 |
| CPU | starting | Random Forest | no | 1672 | 329 | 2.879 | 9.575 | -0.009 | 0.866 | 0.106 |
| CPU | starting | XGBoost | no | 1672 | 329 | 2.963 | 9.637 | -0.022 | 0.905 | 0.022 |
| CPU | reference | Median reference | no | 1672 | 329 | 2.756 | 9.914 | -0.081 | 1.048 | -0.310 |
| Memory | tuned | Decision Tree | yes | 1649 | 329 | 0.488 | 1.313 | 0.024 | 0.421 | 0.033 |
| Memory | tuned | Random Forest | yes | 1649 | 329 | 0.454 | 1.255 | 0.107 | 0.387 | 0.185 |
| Memory | tuned | XGBoost | yes | 1649 | 329 | 0.528 | 1.306 | 0.034 | 0.439 | -0.051 |
| Memory | starting | Decision Tree | no | 1649 | 329 | 0.656 | 1.600 | -0.451 | 0.539 | -0.583 |
| Memory | starting | Random Forest | no | 1649 | 329 | 0.496 | 1.278 | 0.075 | 0.415 | 0.061 |
| Memory | starting | XGBoost | no | 1649 | 329 | 0.626 | 2.071 | -1.429 | 0.484 | -0.277 |
| Memory | reference | Median reference | no | 1649 | 329 | 0.425 | 1.393 | -0.099 | 0.472 | -0.215 |
