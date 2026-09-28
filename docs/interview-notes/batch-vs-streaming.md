# Batch vs Streaming — Interview Notes

## Why use both?

The platform demonstrates two ingestion patterns because transaction systems commonly contain both historical/bulk data and continuously arriving operational events.

### Batch

Historical transactions are copied using Azure Data Factory.

```text
CSV → ADF → ADLS Bronze
```

ADF is appropriate because the historical source is file-based and can be processed as a scheduled or on-demand bulk ingestion workload.

### Streaming

The later transaction window is replayed through Azure Event Hubs.

```text
Producer → Event Hubs → Consumer → ADLS Bronze
```

Event Hubs acts as the streaming transport and buffer. It is not the analytical storage layer.

---

## Why was the streaming period later than the batch period?

The project uses a chronological split.

The batch workload represents historical data up to November 2020. The December 2020 window is replayed through Event Hubs.

This prevents the batch and streaming paths from processing the same chronological period intentionally.

This also became important for the machine-learning layer because the historical batch data could be used for training while the later streaming period could act as a future-like evaluation window.

```text
2019-01 → 2020-11
       ↓
Historical batch
       ↓
ML training

2020-12
       ↓
Streaming replay
       ↓
ML evaluation
```

This is preferable to randomly mixing all transactions before splitting because a chronological split better represents the question:

> "If the model learned from historical transactions, how does it perform on transactions that arrived later?"

---

## Why accelerated replay?

The dataset is historical rather than genuinely real-time.

An accelerated replay allows the platform to demonstrate the mechanics of event-driven ingestion without claiming that the source itself is a live transaction system.

This distinction is important in an interview:

> "I implemented a streaming ingestion pattern using historical data replay. I am demonstrating the architecture and processing mechanics, not claiming that the source is a live production transaction feed."

---

## event_time vs ingestion_time

`event_time` represents when the transaction occurred according to the source.

`ingestion_time` represents when the transaction entered the platform ingestion flow.

Keeping both timestamps is important because they answer different questions.

For example:

```text
event_time      = when the transaction happened
ingestion_time  = when the platform received it
```

The difference between them can later be used to investigate ingestion latency and late-arriving events.

This is also relevant to ML because model features should generally be based only on information that would have been available at prediction time. Mixing future information into historical features can introduce temporal leakage.

---

## What happened with Event Hubs throttling?

The first accelerated producer configuration sent events faster than the available Event Hubs throughput could sustain.

Azure returned a server-side throttling response.

The producer was subsequently designed to:

1. use bounded event batches,
2. pace successful sends,
3. retry transient failures,
4. use exponential backoff when a send fails.

This is preferable to simply assuming that a producer can send indefinitely at maximum speed.

### Interview point

This is a useful example of the difference between:

```text
"I can send messages."
```

and:

```text
"I have considered the operational behavior of the ingestion system."
```

In a production environment, the same issue would lead to consideration of throughput requirements, partition utilization, producer concurrency, retry policies, backpressure, capacity planning and monitoring.

---

## Why not simply increase Event Hubs capacity?

Increasing capacity is one possible operational response, but this portfolio project intentionally uses a small Standard namespace to control cost.

The producer therefore demonstrates application-level backpressure behavior as well.

In a larger production system, capacity planning, autoscaling strategy, partition utilization, producer concurrency, throughput requirements and cost would also be considered.

A good interview answer is:

> "I did not treat infrastructure scaling as the only solution. I also considered producer behavior because uncontrolled retries or unrestricted sending can simply move the bottleneck elsewhere."

---

# Data Quality and Processing Issues

## Why can duplicates occur?

The producer creates a deterministic `event_id` for each transaction.

If a producer is interrupted after successfully sending an event but before the sender knows the complete outcome, or if a replay starts from an approximate checkpoint, the same event can potentially be sent again.

This is why reliable ingestion cannot depend only on "send once" behavior.

Day 6 therefore introduces idempotent Bronze-to-Silver processing using `event_id`.

```text
Bronze
  ↓
Read events
  ↓
Validate schema
  ↓
Validate business rules
  ↓
Deduplicate by event_id
  ↓
Valid → Silver
Invalid → Quarantine
```

---

## Why have both quarantine and Silver?

A bad record should not necessarily stop the entire pipeline.

The processing layer separates:

```text
Valid records
    ↓
Silver
```

from:

```text
Invalid records
    ↓
Quarantine
```

This makes the pipeline more resilient and gives engineers a place to investigate rejected records.

For a production system, quarantine records would also normally have an explicit reason code or validation failure category so that data-quality problems can be monitored and remediated.

---

## What did the processing layer actually prove?

Day 5 primarily proved data movement:

```text
Batch ingestion works
Streaming ingestion works
Both reach Bronze
```

Day 6 adds data-processing controls:

```text
Bronze
  ↓
Schema validation
  ↓
Business validation
  ↓
Duplicate detection
  ↓
Quarantine
  ↓
Silver + Audit
```

This separation is useful in an interview because it demonstrates that ingestion and data quality are different concerns.

---

# Schema Differences Between Batch and Streaming

One practical issue discovered while preparing the ML datasets was that some columns did not have identical physical types between the batch and streaming datasets.

For example:

```text
Batch:
cc_num → integer
zip    → integer

Streaming:
cc_num → string
zip    → string
```

These columns were not required as ML features, so they were dropped rather than forcing an unnecessary type conversion.

### Interview lesson

Schema consistency matters when multiple ingestion paths feed the same downstream processing layer.

A production implementation could enforce an explicit canonical schema at the Bronze-to-Silver boundary rather than relying on whatever physical type happens to arrive from the source.

This is particularly important when integrating multiple source systems.

---

# Why not train the ML model on the entire dataset randomly?

The project deliberately does **not** randomly combine the batch and streaming data and then perform a random train/test split.

Instead:

```text
Historical batch
2019-01 → 2020-11
        ↓
Training

Later streaming period
2020-12
        ↓
Evaluation
```

This creates a time-aware evaluation.

The reasoning is that a fraud model deployed into production would normally make predictions on future transactions, not randomly shuffled historical transactions.

A random split can make the evaluation look cleaner while failing to represent the temporal nature of the prediction problem.

---

# What features were engineered for ML?

The model uses transaction, geographic and temporal features.

The main features are:

```text
amt
city_pop
lat
long
merch_lat
merch_long
transaction_hour
day_of_week
month
customer_age
distance_km
```

Some were directly available from the source, while others were engineered.

### Examples

`transaction_hour`:

```text
event_time → hour of transaction
```

`customer_age`:

```text
event_time - date_of_birth
```

`distance_km`:

```text
customer location
        ↓
merchant location
        ↓
Haversine distance
```

Feature engineering was performed consistently for both training and evaluation data.

---

# Why XGBoost?

XGBoost was selected as the primary supervised model because the problem is structured/tabular classification.

The target is:

```text
is_fraud
```

The model produces:

```text
fraud_probability
```

The model was configured with class weighting because fraud is highly imbalanced.

Training data contained:

```text
Non-fraud: 1,703,463
Fraud:         9,393
Fraud rate:    0.5484%
```

Therefore, simply optimizing for accuracy would be misleading.

---

# Why is accuracy not the main metric?

Fraud detection is a highly imbalanced classification problem.

If almost every transaction is legitimate, a model could obtain very high accuracy while detecting very few fraudulent transactions.

Therefore the project focuses on:

* Precision
* Recall
* PR-AUC
* ROC-AUC
* Confusion matrix
* Threshold trade-offs

The evaluated XGBoost model produced:

```text
ROC-AUC: 0.9826
PR-AUC:  0.3622
Precision: 0.0606
Recall:    0.8450
```

The important interview point is that **high ROC-AUC does not automatically mean that the model is operationally useful**.

The precision/recall trade-off must be considered in the context of the business process.

---

# Why was precision relatively low?

At the 0.50 threshold:

```text
True positives:  218
False positives: 3,380
False negatives: 40
True negatives:   135,900
```

The model catches a large proportion of the known fraud cases, but it also flags many legitimate transactions.

This is a common characteristic of highly imbalanced fraud detection.

It creates a business question rather than simply a technical question:

> "What level of false positives can the fraud operations team actually investigate?"

For example, a bank might have a very different acceptable threshold depending on whether the prediction triggers:

```text
soft review
additional authentication
temporary hold
automatic decline
```

The model threshold should therefore be selected together with the downstream business action.

---

# Why examine multiple thresholds?

The project explicitly tested:

```text
Threshold   Precision   Recall
0.30        0.0374      0.8992
0.50        0.0606      0.8450
0.70        0.0973      0.7713
```

Increasing the threshold reduces the number of transactions flagged but also reduces recall.

This demonstrates that the model probability and the operational decision threshold are separate concepts.

A useful interview phrase is:

> "The model produces a probability; the business process decides where to place the decision threshold."

---

# Why use Isolation Forest as well?

Isolation Forest is used as a **separate anomaly signal**, not as a replacement for the supervised fraud model.

The supervised model asks:

> "Does this transaction resemble known fraud patterns?"

Isolation Forest asks:

> "Does this transaction look unusual compared with the population?"

This distinction is important because an unusual transaction is not necessarily fraudulent.

The Isolation Forest was trained without using the fraud labels.

On the evaluation data:

```text
Diagnostic ROC-AUC: 0.8198
Diagnostic PR-AUC:  0.0125
```

The anomaly rate was approximately:

```text
11.74%
```

The anomalous group had a higher observed fraud rate than the normal group:

```text
Normal transactions:    0.0820%
Anomalous transactions: 0.9584%
```

The correct interpretation is that anomaly detection provides an additional signal for investigation. It should not automatically be interpreted as a second fraud classifier.

---

# Why use SHAP?

A fraud model should not be treated as a black box when analysts or risk teams need to understand its decisions.

SHAP was used to provide:

```text
Global explanations
        +
Individual transaction explanations
```

The strongest global contributors by mean absolute SHAP value were:

```text
amt
transaction_hour
month
customer_age
city_pop
...
```

For an individual high-probability transaction, SHAP can show which features pushed the prediction toward or away from fraud.

For example:

```text
amt              positive contribution
transaction_hour positive contribution
customer_age     positive contribution
month            negative contribution
```

This is more useful operationally than simply saying:

> "The model predicted fraud."

---

# Why is explainability important in a financial-risk context?

The model output may eventually influence a business action.

Therefore stakeholders may need to understand:

* why a transaction was flagged,
* which characteristics contributed to the prediction,
* whether the model behaves consistently,
* whether the features are appropriate,
* whether there are signs of data or model problems.

This is particularly relevant in regulated or highly controlled environments.

SHAP does not prove that a feature *caused* fraud. It explains how the feature contributed to the model's prediction.

---

# What was the ML drift analysis?

The project includes a lightweight offline comparison between the historical training population and the later evaluation population.

It compares:

* mean,
* median,
* standard deviation,
* percentage change,
* fraud rate.

For example, the observed fraud rate changed from:

```text
Training:   0.5484%
Evaluation: 0.1849%
```

This is a meaningful population difference worth investigating.

However, the project does **not** claim to implement production model monitoring.

It does not currently provide:

```text
automated drift alerts
automatic retraining
model registry
production endpoints
real-time monitoring
```

The correct interview description is:

> "I implemented offline drift diagnostics to compare the training and later evaluation populations. It is an analysis layer, not a production monitoring system."

---

# What went wrong or required troubleshooting?

## Event Hubs throttling

The accelerated producer initially exceeded the available throughput.

**Lesson:** streaming systems need pacing, retries and backpressure rather than unlimited sending.

---

## Duplicate events

The replay design demonstrated that events can be delivered more than once.

**Lesson:** downstream processing needs idempotency and deterministic event identifiers.

---

## Invalid records

Not every incoming record should automatically enter the trusted Silver layer.

**Lesson:** validation and quarantine should be part of the data-processing architecture.

---

## Different physical schemas

Batch and streaming data contained differences such as:

```text
cc_num: integer vs string
zip:    integer vs string
```

**Lesson:** downstream pipelines need a canonical schema and should not blindly assume that two ingestion paths produce identical physical types.

---

## ML class imbalance

Fraud represented only a small fraction of the transactions.

**Lesson:** accuracy alone is inappropriate; class weighting and precision/recall-oriented evaluation are necessary.

---

## Model threshold trade-off

A high-recall model can produce many false positives.

**Lesson:** model evaluation needs to connect technical metrics to operational consequences.

---

## High predicted probabilities were not always fraud

The top predicted transactions included both fraud and non-fraud cases.

**Lesson:** a model probability is a prediction, not ground truth.

This is an important distinction when explaining ML systems to business stakeholders.

---

# Big 4 / Consulting Interview Angle

For a Big 4 data engineering, analytics or AI interview, the technical implementation can be connected to broader delivery concerns.

## 1. Data quality

Be prepared to explain:

```text
How do you know the data is trustworthy?
```

Answer through:

* schema validation,
* business validation,
* duplicate detection,
* quarantine,
* audit information,
* row-count validation,
* fraud-distribution checks.

---

## 2. Data lineage

Be able to trace:

```text
Source
  ↓
ADF / Event Hubs
  ↓
Bronze
  ↓
Validation
  ↓
Silver
  ↓
ML features
  ↓
Model
  ↓
Gold outputs
```

A consultant should be able to explain not only the technology but also where a particular metric or prediction came from.

---

## 3. Reproducibility

The ML pipeline uses fixed configuration and random seeds where appropriate.

For example:

```text
random_state = 42
```

The feature engineering logic is shared between training and evaluation.

The model configuration and dependency versions are documented.

This makes the experiment reproducible rather than dependent on one interactive notebook session.

---

## 4. Auditability

The project keeps a distinction between:

```text
raw data
processed data
model outputs
explanations
diagnostics
```

This makes it easier to understand how an output was produced.

For enterprise environments, this concept extends into logging, lineage, access controls, model versioning and approval processes.

---

## 5. Scalability

A portfolio implementation may use relatively small infrastructure, but the architectural principles should still be scalable.

For example:

```text
Event Hubs
→ partitions

ADLS
→ distributed object storage

Bronze/Silver/Gold
→ separation of processing responsibilities

XGBoost
→ tabular ML workload
```

If transaction volume increased substantially, the design would require capacity planning, partition strategy, distributed processing and potentially a more scalable model-serving architecture.

---

## 6. Security

The project uses Azure identity-based access rather than embedding storage credentials directly into application code.

A production implementation would further consider:

* managed identities,
* least-privilege RBAC,
* secret management,
* network controls,
* encryption,
* environment separation,
* audit logging.

The important interview point is:

> "Security should be designed into the platform rather than added after the data pipeline is built."

---

## 7. Model risk

For an ML system that may influence financial-risk decisions, consider:

```text
Data quality
      ↓
Feature correctness
      ↓
Model performance
      ↓
Explainability
      ↓
Threshold selection
      ↓
Monitoring
      ↓
Human/business decision
```

The model should not automatically be treated as the final decision-maker.

The current project demonstrates the model, evaluation, threshold analysis and explainability layers, while leaving production model governance and automated monitoring outside the portfolio scope.

---

# A strong overall interview answer

If asked:

> "Walk me through the project."

A concise answer would be:

> "I built an Azure transaction-risk platform that demonstrates both batch and streaming ingestion. Historical transactions are loaded through Azure Data Factory, while a later historical period is replayed through Event Hubs to simulate an event-driven workload. Both paths land in ADLS Bronze, where I added validation, deduplication and quarantine processing before producing Silver data.
>
> For machine learning, I deliberately used a chronological split rather than randomly mixing the data. Historical transactions through November 2020 are used for training, while December 2020 is held out as a future-like evaluation period. I engineered temporal, customer and geographic features and trained an XGBoost fraud classifier, with class weighting because fraud is highly imbalanced.
>
> I evaluated ROC-AUC, PR-AUC, precision and recall and also tested different decision thresholds. I added Isolation Forest as a separate anomaly signal and used SHAP for model explainability. Finally, I compared the training and evaluation populations using lightweight offline drift diagnostics.
>
> The interesting part wasn't just getting the pipeline to work. I also had to deal with practical issues such as Event Hubs throttling, duplicate events, validation and schema differences. That helped me think about the platform in terms of reliability, data quality, scalability and auditability rather than just individual Azure services."

---

# Questions I should be ready for

### Architecture

* Why Azure Data Factory for batch?
* Why Event Hubs for streaming?
* Why not use Event Hubs for storage?
* Why Bronze/Silver/Gold?
* Why separate batch and streaming paths?
* How would this scale?
* How would you handle late-arriving events?

### Data engineering

* How do you deduplicate events?
* Why use `event_id`?
* What happens to invalid records?
* How do you handle schema evolution?
* What is the difference between event time and ingestion time?
* How would you monitor pipeline failures?
* How would you handle Event Hubs throttling?

### ML

* Why XGBoost?
* Why not accuracy?
* Why PR-AUC?
* Why use class weighting?
* Why use a chronological split?
* How did you engineer the features?
* How did you choose the threshold?
* Why use Isolation Forest?
* Why use SHAP?
* What does a SHAP value actually mean?
* What is the difference between feature importance and SHAP?
* How would you detect model drift?
* How would you retrain the model?
* How would you deploy the model?

### Consulting / Big 4

* How would you productionize this?
* What are the main risks?
* How would you control access?
* How would you make the pipeline auditable?
* How would you explain the model to a non-technical stakeholder?
* What would change if transaction volume increased 100×?
* What would you monitor after deployment?
* How would you distinguish a data-quality problem from a model-performance problem?
* How would you balance false positives against missed fraud?
* How would you work with risk, compliance and business teams?

## The key story to remember

```text
INGEST
Batch + Streaming
       ↓
RELIABILITY
Retry + Backpressure + Event IDs
       ↓
DATA QUALITY
Validation + Deduplication + Quarantine
       ↓
TRUSTED DATA
Silver
       ↓
ML
Feature Engineering
       ↓
XGBoost + Isolation Forest
       ↓
EXPLAINABILITY
SHAP
       ↓
EVALUATION
Precision + Recall + PR-AUC
       ↓
MONITORING
Offline Drift Diagnostics
```

The strongest interview narrative is therefore not:

> "I used a lot of Azure services."

It is:

> **"I built a data-to-ML pipeline and dealt with the reliability, data-quality, temporal-validation, class-imbalance and explainability issues that arise along the way."**
