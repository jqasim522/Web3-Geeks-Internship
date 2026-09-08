# Week 1 Adult Census Income — High-Income Household Prediction

## Project Objective
Predict whether a household's annual income exceeds $50K using U.S. Census attributes, so a
marketing team can target premium offers at households most likely to respond, instead of
contacting everyone. This matters because outreach costs money — a model that ranks households by
likely income lets the campaign control cost while still reaching the audience the offer is
designed for.

## Dataset Description
- **Source:** UCI Adult / Census Income dataset (1994 U.S. Census), loaded via
  `sklearn.datasets.fetch_openml('adult', version=2, as_frame=True)`.
- **Size:** 48,842 rows, 14 raw features + target.
- **Features:** `age`, `workclass`, `fnlwgt`, `education`, `education-num`, `marital-status`,
  `occupation`, `relationship`, `race`, `sex`, `capital-gain`, `capital-loss`, `hours-per-week`,
  `native-country`.

## Target Variable
`income_binary`: **1** if `income == '>50K'`, **0** if `income == '<=50K'`. Base rate: 23.93%
positive class in the full dataset.

## Feature Engineering
Eight row-wise features were engineered (no target leakage — each uses only current-row raw data):

| Feature | Type | Why |
|---|---|---|
| `age_bucket` | bucket | Income typically rises through the 30s–50s career peak, then plateaus. |
| `hours_bucket` | bucket | Part-time work strongly caps earnings. |
| `capital_gain_flag` | binary | Any investment income at all is a strong signal. *(Dropped from Day 4 onward — see below.)* |
| `capital_gain_log` | log-transform | Raw capital-gain is extremely right-skewed. |
| `higher_education` | binary | Bachelor's-or-higher is a well-known income threshold. |
| `education_x_hours` | interaction | Education likely pays off more combined with more hours. |
| `age_x_hours` | interaction | Career-stage and work intensity together may predict better than either alone. |
| `marital_married` | binary | `Married-civ-spouse` is the single strongest marital category for >50K. |

`capital_gain_flag` was **dropped starting Day 4**: it was found highly collinear with
`capital_gain_log` (both are exactly 0 when capital-gain is 0), producing a large, misleading
negative coefficient in Logistic Regression without adding real signal beyond
`capital_gain_log` alone.

## Preprocessing Steps
- **Numeric** (`age`, `fnlwgt`, `education-num`, `capital-gain`, `capital-loss`, `hours-per-week`,
  plus engineered numeric/interaction features): median imputation → `StandardScaler`.
- **Categorical** (`workclass`, `education`, `marital-status`, `occupation`, `relationship`,
  `race`, `sex`, `native-country`, plus engineered bucket features): most-frequent imputation →
  `OneHotEncoder(handle_unknown='ignore')`.
- **Binary engineered flags** (`higher_education`, `marital_married`): passed through unchanged.
- All of the above is wrapped in a single `sklearn.pipeline.Pipeline` (feature engineering via
  `FunctionTransformer` → `ColumnTransformer`), fit only on the training split — never on dev or
  test — so there is no leakage into any reported metric.

## Validation Strategy
Stratified 70% train / 10% dev / 20% held-out test split (`random_state=42`), fixed from Day 1
onward and reused identically through Day 5. `StratifiedKFold(n_splits=5, shuffle=True,
random_state=42)` was used for all cross-validated model comparisons and hyperparameter search.

## Models Tested
- **Day 1:** Majority-class baseline; rule-based baseline (`education-num >= 13`).
- **Day 2:** Logistic Regression, Decision Tree (single train/test split, no CV yet).
- **Day 3:** Logistic Regression, Random Forest, HistGradientBoosting — all 5-fold cross-validated
  with the full engineered feature set.
- **Day 4:** Logistic Regression and HistGradientBoosting, hyperparameter-tuned.

## Hyperparameter Tuning Approach
`RandomizedSearchCV` with `StratifiedKFold`, scoring `roc_auc`. **Note:** this project was built in
a single-CPU-core environment. A benchmark found Logistic Regression's `saga` solver with L1
penalty took ~80s for one fit vs. ~0.3s for `liblinear`, so `saga` was dropped (liblinear covers
both L1 and L2) and `n_iter`/`cv` were reduced from the initially-planned 50–100/5 to keep the
search runnable end-to-end (Logistic Regression: n_iter=30, cv=3; HistGradientBoosting: n_iter=15,
cv=3). This is documented as a compute-constraint decision, not a methodology shortcut — the search
spaces themselves (parameter ranges) were not narrowed.

## Best Parameters
- **Logistic Regression:** `penalty='l1'`, `C=0.541`, `solver='liblinear'`, `max_iter=2000` — CV ROC AUC 0.9111.
- **HistGradientBoosting:** `learning_rate=0.028`, `max_iter=200`, `max_depth=None`,
  `l2_regularization=0.0054`, `min_samples_leaf=20` — CV ROC AUC 0.9253.

## Selected Final Model
**HistGradientBoosting** (tuned), wrapped in `CalibratedClassifierCV(method='sigmoid', cv=5)`.
Calibration was kept because it improved the Brier score on the dev set (0.0865 → 0.0862).
HistGradientBoosting was chosen over Logistic Regression for higher ROC AUC (0.9253 vs 0.9111 in
tuned CV) with no meaningful overfitting (learning-curve train/validation gap of only 0.015).

## Classification Threshold
**0.40** (not the default 0.5), chosen by maximizing F1 on the dev set: precision 0.730, recall
0.746, F1 0.738 at 0.40 vs. precision 0.797, recall 0.656, F1 0.720 at 0.50. The lower threshold
trades some precision for a larger recall gain, which fits the marketing-outreach use case (a
missed high-income household is a larger opportunity cost than one wasted low-cost contact).

## Final Test Performance
Evaluated once on the untouched hold-out test set (n=9,769):

| Threshold | Accuracy | Precision | Recall | F1 | ROC AUC | PR AUC | Brier |
|---|---|---|---|---|---|---|---|
| 0.50 (default) | 0.8760 | 0.7930 | 0.6523 | 0.7158 | 0.9279 | 0.8302 | — |
| **0.40 (tuned, final)** | 0.8692 | 0.7253 | 0.7297 | 0.7275 | 0.9279 | 0.8302 | 0.0879 |

## Important Features
Permutation importance on the deployed pipeline (ROC AUC drop when shuffled), test set:
1. **`marital-status`** (0.1024) — by far the strongest driver.
2. **`capital-gain`** (0.0604) — strong but **non-monotonic**; see Known Limitations.
3. **`age`** (0.0414).
4. **`education-num`** (0.0352).
5. **`hours-per-week`** (0.0139).

## Known Limitations
- **Gender recall gap:** Female recall is 0.670 vs. 0.741 for Male on the test set — the model
  misses more genuinely high-income women than men. Permutation importance shows `sex` itself has
  low direct importance (ranked 10th of 14, 0.0010), meaning this gap is **mediated through
  correlated features** (`marital-status`, `occupation`, `hours-per-week` all differ by gender in
  this data) rather than the model reading `sex` directly — so simply dropping the `sex` column
  would likely **not** remove the disparity. This should be treated as a blocking issue for any
  real deployment without a dedicated fairness review.
- **Non-monotonic `capital-gain` behavior:** the model's response to `capital-gain` is not smooth.
  Specific dollar amounts (e.g., 7298, 15024, 99999) are heavily overrepresented in the >50K class
  in the original 1994 extract, while other specific amounts (e.g., 2174, 3325, 4650, 5013) are
  overrepresented in the <=50K class. The model learned these training-data-specific "signature"
  values rather than a smooth income relationship — an arbitrary `capital-gain` value that doesn't
  match a signature amount (e.g., $5,000) can land in a low-probability valley even when every other
  feature suggests a high-income profile. New data with different capital-gain patterns (a
  different year, a different country) could produce unreliable predictions on this feature.
- **Coarse `occupation` categories** likely blur real income variation within categories.
- **No tenure/experience feature** is available; a false-negative pattern (high hours, moderate
  education, missed by the model) suggests experience-driven income isn't well captured.
- **1994 data** — patterns (including the gender gap above) reflect that era and U.S. labor market;
  the model should not be assumed to generalize to current populations without revalidation.

## How to Reproduce Training
1. `pip install -r requirements.txt`
2. Run `ML_Foundations_Adult_Census.ipynb` (Day 1) through `ML_Foundations_Day4_Adult_Census.ipynb`
   in order — each recreates the identical `random_state=42` stratified 70/10/20 split and builds
   on the previous day's artifacts.
3. Day 4's last cells save `final_pipeline.pkl` via `joblib.dump()`.
4. `ML_Foundations_Day5_Adult_Census.ipynb` loads that artifact directly (no retraining) for final
   validation, error/subgroup analysis, interpretation, and inference testing.

## How to Run Inference
```python
import joblib
import pandas as pd

# The engineer_features function must be importable/defined before unpickling,
# since the saved pipeline references it (see the notebook for the exact definition).
pipeline = joblib.load('final_pipeline.pkl')

def predict_with_threshold(pipeline, X_new, threshold=0.40):
    probs = pipeline.predict_proba(X_new)[:, 1]
    preds = (probs >= threshold).astype(int)
    return preds, probs

# X_new: a DataFrame with the same raw columns as the original data.
# No manual preprocessing needed -- the pipeline handles feature engineering,
# imputation, scaling, and encoding internally.
preds, probs = predict_with_threshold(pipeline, X_new)
```

## Requirements
See [`requirements.txt`](./requirements.txt). Install with:
```
pip install -r requirements.txt
```
