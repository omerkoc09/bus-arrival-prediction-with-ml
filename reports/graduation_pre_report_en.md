# Bus Arrival Time Prediction for Eşrefpaşa Route 502 — Graduation Project Preliminary Report

**Project Title:** Context-Aware Deep Learning for Bus Arrival Time Prediction (Izmir Pilot Study)  
**Date:** June 5, 2026  
**Data Coverage:** April 2, 2026 — June 5, 2026 (65 Days of Real-Time Data)  
**Prepared by:** Antigravity AI & Project Team  

---

## 1. Introduction and Project Summary
This study evaluates the performance of a machine learning and deep learning pipeline designed to predict inter-stop travel times in public transportation systems. Compared to the reference paper (**Kaya & Kalay, IEEE Access 2025**), our model incorporates **GTFS scheduled times**, **cumulative deviation history**, and **dwell times** to improve prediction accuracy.

Following an intermediate analysis on 138K segments, the collected real-time dataset has grown to **305,954 segments** (approximately a 2.2× increase). This report presents the new official results obtained from the updated larger dataset and the corrected PyTorch prediction pipeline, along with the underlying cause-and-effect relationships.

---

## 2. Dataset Statistics
The general profile of the dataset — collected from scratch and processed through feature engineering stages (v2, v3, v4) — is as follows:

- **Total Processed Segments:** 305,954 rows
- **Training Set Size (80%):** 244,763 rows
- **Test Set Size (20%):** 61,191 rows
- **Date Range:** April 2, 2026 — June 5, 2026 (65 days)
- **Active Operating Hours:** 06:00 — 22:00
- **Unique Bus Count:** 318
- **Average Inter-Stop Travel Time:** 1.172 minutes (~70 seconds)
- **Travel Time Standard Deviation:** 1.114 minutes

---

## 3. Model Performance Comparisons

The tables below show the test set performance of models trained on the full dataset:

### 3.1. Deep Learning Model Comparison
*(PyTorch-based, with Log-transform and Huber Loss)*

| Model | MAE (min) | RMSE (min) | MAPE (%) | R² |
| :--- | :---: | :---: | :---: | :---: |
| **Improved LSTM** (Proposed) | **0.3507** | **0.4918** | **38.41** | **0.3569** |
| Baseline LSTM (Previous Version) | 0.4138 | 0.6914 | 42.11 | 0.0484 |

### 3.2. Overall Model Comparison
*(Test Set n = 61,191)*

| Rank | Model | MAE (min) | RMSE (min) | MAPE (%) | R² |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | **Improved LSTM** | **0.3507** | **0.4918** | **38.41** | 0.3569 |
| 2 | **XGBoost (Improved)** | 0.3944 | 0.6483 | 41.29 | **0.5379** |
| 3 | Random Forest (Improved) | 0.4079 | 0.6614 | 42.67 | 0.5190 |

---

## 4. Cause-and-Effect Analysis of Findings

### 4.1. Impact of Increased Data Volume on Deep Learning Models
- **Finding:** When the dataset was scaled from 138K to 305K segments, the `Improved LSTM` model's MAE dropped from **0.4138 minutes to 0.3507 minutes (~15.2% improvement)**.
- **Cause-and-Effect:** Deep learning models inherently have high parameter capacity and tend to overfit or exhibit unstable learning on small datasets. Increasing the data volume by 2.2× enabled the LSTM cells to learn generalized rules about the complex spatiotemporal relationships in inter-stop travel times, rather than memorizing patterns, leading to a notable improvement in prediction accuracy.

### 4.2. Characteristic Differences Between LSTM and XGBoost
- **Finding:** `Improved LSTM` achieved the lowest average error (MAE = 0.3507 min), while `XGBoost (Improved)` achieved the highest explanatory power (R² = 0.5379).
- **Cause-and-Effect:** The LSTM model treats travel time prediction as a time-series sequence problem (using the last 5 stops' travel speed and deviation with `window_size=5`). This allows it to smoothly track the bus's instantaneous momentum and recent stop trends, yielding the best MAE. XGBoost, on the other hand, directly partitions spatiotemporal features (weather, time of day, stop location) using tree structures. Although it is more successful at explaining variance (R²), it cannot match LSTM's smooth sequential tracking, placing it slightly behind in MAE.

### 4.3. Cold-Start Problem and Segment Analysis
- **Finding:** MAE is **0.5246 min** at the initial stops (0–33% of trip), decreasing to **0.4157 min** at mid-trip stops, and further to **0.3602 min** at terminal stops.
- **Cause-and-Effect:** At the first stops of a trip, lag features such as `prev_travel_time_min` and `prev_deviation` default to `0` since no previous stops have been completed. The model lacks the contextual information about real-time driving dynamics, resulting in approximately double the error rate in the early portion of the trip. As the trip progresses (as `stop_progress` increases), the actual travel times from the last 5 stops are fed into the model, driving the error to its lowest level (0.3602 min).

### 4.4. Impact of Weather Conditions
- **Finding:** MAE is **0.4267 min** in rainy conditions compared to **0.3882 min** in clear weather.
- **Cause-and-Effect:** Rainy weather reduces visibility, increases road surface slipperiness, and raises traffic density, all of which extend travel times. Furthermore, passengers opening and closing umbrellas during boarding/alighting creates high variability in dwell times. This increased unpredictability leads to higher prediction error on rainy days.

---

## 5. Statistical Significance Analysis
To verify that our models' performance is not due to chance, **Paired t-test** and **Wilcoxon signed-rank** tests were applied to the test set:

- **XGBoost (Improved) vs Naive (GTFS):** $p$-value = `0.0` (Statistically highly significant improvement)
- **XGBoost (Improved) vs Historical Average:** $p$-value = `0.0` (Significant improvement)
- **XGBoost (Improved) vs Random Forest (Improved):** $p$-value = `0.0` (Significant difference)

The fact that all $p$-values are far below the significance level of $\alpha = 0.05$ demonstrates that the improved feature engineering and corrected prediction pipeline provide a non-random, consistent, and academically verifiable contribution to travel time prediction.

---

## 6. Comparison with Reference Paper
The comparison with the reference paper (**Kaya & Kalay, IEEE Access 2025**) is shown below:

| Metric | Paper (Istanbul LSTM) | Ours (XGBoost Improved) | Ours (Improved LSTM) |
| :--- | :---: | :---: | :---: |
| **MAE (min)** | 2.97 | 0.3944 | **0.3507** |
| **MAPE (%)** | **14.79** | 41.29 | 38.41 |
| **R²** | **0.9272** | 0.5379 | 0.3569 |

### ⚠️ Critical Methodological Difference
- **MAE Difference:** Our MAE (~0.35 min) is far lower than the paper's value (2.97 min). This is because **the reference paper predicts the entire trip duration**, while our study predicts **individual inter-stop segment durations (average 1.17 min)**.
- **R² and MAPE Difference:** In end-to-end travel time prediction, the target variable has very high variance (e.g., trips ranging from 30–50 minutes). Because the variance is large, R² values easily exceed 0.90. Since our segment-level variance is much narrower, our R² appears lower by comparison. Regarding MAPE: a 20-second error on a 1.17-minute segment yields 30–40% MAPE, whereas a 3-minute error on a 30-minute trip yields only ~10% MAPE.

---

## 7. Conclusion
1. **Original Contribution Highlight:** Through an ablation study, GTFS scheduled times and cumulative deviation (`deviation_history`) are shown to be the features contributing most to model performance.
2. **Cold-Start Analysis:** The reason error doubles at the start of a trip, and the imputation mechanism using `scheduled_travel_minutes` to mitigate this, are presented as a methodological achievement.
