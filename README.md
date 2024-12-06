# FraudDetection 🛡️ - Real-Time Payment Protection System

## 📋 Overview
FraudDetection is an end-to-end fraud detection system that processes payment transactions in real-time and provides immediate alerts for suspicious activities. Built with modern data engineering practices, it combines machine learning, real-time processing, and automated monitoring to protect financial transactions.

## 🎯 Key Features
- **Real-time Transaction Processing** 🔄
  - Minute-by-minute transaction monitoring
  - Immediate fraud detection using Random Forest model
  - Instant email notifications for suspicious transactions

- **Automated Data Pipeline** 🔁
  - ETL process for transaction data
  - SMOTE handling for imbalanced datasets
  - Automated model deployment

- **Comprehensive Monitoring** 📊
  - System health checks
  - API status monitoring
  - Database connection verification
  - S3 storage validation

## 🤖 Detection Model

### Overview
- **Type**: Random Forest Classifier
- **Library**: scikit-learn
- **Imbalance Handling**: SMOTE (Synthetic Minority Over-sampling Technique)

### Features Used
- Temporal: hour, day of week, month
- Geographic: customer-merchant distance, location
- Transactional: amount, category, merchant
- Demographic: customer age, job

### Model Configuration
```python
RandomForestClassifier(
    n_estimators=100,      # Number of trees
    max_depth=10,          # Maximum depth
    min_samples_split=5,   # Minimum samples for split
    min_samples_leaf=2,    # Minimum samples per leaf
    class_weight='balanced' # Imbalance handling
)
```

### Performance
- Precision: ~0.95
- Recall: ~0.92
- F1 Score: ~0.93
- AUC-ROC: ~0.96

### Processing Pipeline
1. Missing values imputation
2. Numerical features standardization
3. Categorical features encoding
4. SMOTE application
5. Random Forest training

## 🏗️ Technical Architecture

### Services
- **Apache Airflow**: Workflow orchestration
  - Transaction processing DAG (every minute)
  - Backup DAG (monthly)
  - Monitoring DAG (daily)

- **MLflow**: ML model management
  - Model versioning
  - Experiment tracking
  - Model artifacts storage

- **Streamlit**: Data visualization
  - Real-time dashboard
  - Interactive data exploration
  - Performance metrics

## 🛠️ Detailed Installation Guide

### 1. Prerequisites
```plaintext
- Docker
- Python 3.9+
- AWS Account & S3 Bucket
- Neon Database Account
- Gmail Account (for SMTP)
```

### 2. Environment Configuration

#### Create .env file
```bash
# Airflow
AIRFLOW_UID=50000
AIRFLOW_USERNAME=admin

# Service Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
S3_BUCKET=your-bucket-name

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000
MLFLOW_DEFAULT_ARTIFACT_ROOT=s3://${S3_BUCKET}/mlflow/

# Airflow Configuration
AIRFLOW__CORE__EXECUTOR=CeleryExecutor
AIRFLOW__CORE__LOAD_EXAMPLES=false
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
```

#### Create .secrets file
```bash
# Database Credentials
NEON_DATABASE_URL=postgresql://user:password@your-neon-db-url/dbname?sslmode=require

# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key

# Email Credentials
EMAIL_USER=your.email@gmail.com
EMAIL_PASSWORD=your_app_specific_password

# Service Passwords
AIRFLOW_PASSWORD=admin
MLFLOW_TRACKING_PASSWORD=admin

# Airflow Database Connections
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://airflow:airflow@postgres/airflow
AIRFLOW__CELERY__BROKER_URL=redis://:@redis:6379/0
AIRFLOW__CORE__FERNET_KEY=''
```

#### DAG configuration common.py file
Don't forget to config the email recipient in "def send_email"

### 3. Database Setup

#### Access Neon Database
1. Create account on Neon (https://neon.tech)
2. Create new project
3. Get connection string
4. Connect using psql or your preferred database tool

#### Create Required Tables
```sql
-- Create fraud_transactions table
CREATE TABLE fraud_transactions (
    transaction_id SERIAL PRIMARY KEY,
    cc_num BIGINT,
    merchant VARCHAR(255),
    category VARCHAR(100),
    amt DECIMAL(10, 2),
    first VARCHAR(100),
    last VARCHAR(100),
    gender CHAR(1),
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip INTEGER,
    lat DECIMAL(10, 6),
    long DECIMAL(10, 6),
    city_pop INTEGER,
    job VARCHAR(255),
    dob DATE,
    trans_num VARCHAR(255) UNIQUE,
    merch_lat DECIMAL(10, 6),
    merch_long DECIMAL(10, 6),
    is_fraud BOOLEAN DEFAULT TRUE,
    trans_date_trans_time TIMESTAMP
);

-- Create normal_transactions table
CREATE TABLE normal_transactions (
    -- Same structure as fraud_transactions
    is_fraud BOOLEAN DEFAULT FALSE
);

-- Create indices
CREATE INDEX idx_normal_trans_date ON normal_transactions(trans_date_trans_time);
CREATE INDEX idx_fraud_trans_date ON fraud_transactions(trans_date_trans_time);
CREATE INDEX idx_normal_trans_num ON normal_transactions(trans_num);
CREATE INDEX idx_fraud_trans_num ON fraud_transactions(trans_num);

-- Create views
  -- recent_trasaction (last 24h)
CREATE OR REPLACE VIEW recent_transactions AS
SELECT 
    transaction_id,
    merchant,
    category,
    amt,
    city,
    state,
    is_fraud,
    trans_date_trans_time,
    NULL as distance,
    NULL as fraud_probability
FROM (
    SELECT * FROM normal_transactions
    UNION ALL
    SELECT * FROM fraud_transactions
) all_transactions
WHERE trans_date_trans_time >= NOW() - INTERVAL '24 hours'
ORDER BY trans_date_trans_time DESC;

  -- daily stats
CREATE OR REPLACE VIEW daily_stats AS
SELECT 
    DATE(trans_date_trans_time) as date,
    COUNT(*) as total_transactions,
    COUNT(CASE WHEN is_fraud THEN 1 END) as fraud_count,
    ROUND(AVG(amt), 2) as avg_amount,
    ROUND(SUM(amt), 2) as total_amount,
    ROUND(COUNT(CASE WHEN is_fraud THEN 1 END)::DECIMAL / COUNT(*) * 100, 2) as fraud_rate
FROM (
    SELECT * FROM normal_transactions
    UNION ALL
    SELECT * FROM fraud_transactions
) all_transactions
GROUP BY DATE(trans_date_trans_time)
ORDER BY DATE(trans_date_trans_time) DESC;
```

### 4. AWS S3 Setup

1. Create S3 Bucket
```bash
aws s3 mb s3://your-bucket-name
```

2. Create Required Directory Structure
```bash
fraud_detection_bucket/
├── etl/
│   └── etl.py
├── models/
│   └── random_forest_model.pkl
└── backups/
```

3. Upload Initial Files
```bash
# Upload ETL script
aws s3 cp models/etl.py s3://your-bucket-name/fraud_detection_bucket/etl/

# Upload model
aws s3 cp models/random_forest_model.pkl s3://your-bucket-name/fraud_detection_bucket/models/
```

### 5. Gmail Setup for SMTP

1. Enable 2-Step Verification in your Google Account
2. Generate App Password:
   - Go to Google Account Settings
   - Security > App Passwords
   - Select "Mail" and "Other"
   - Copy generated password to .secrets EMAIL_PASSWORD

### 6. Deploy Services

1. Build Docker images
```bash
docker-compose build
```

2. Start services
```bash
docker-compose up -d
```

3. Verify service status
```bash
docker-compose ps
```

## 📊 Accessing Services

- Airflow UI: http://localhost:8080
  - Username: admin
  - Password: admin

- MLflow UI: http://localhost:5000
  - Username: admin
  - Password: admin

- Streamlit Dashboard: http://localhost:8501

## 🔍 Monitoring

### System Health Checks
The monitoring_dag.py performs daily health checks on:
- API availability
- Database connectivity
- S3 access
- Model accessibility

### Performance Metrics
Access via Streamlit dashboard:
- Transaction volume
- Fraud detection rate
- Processing latency
- Model accuracy

## 🛟 Troubleshooting

### Common Issues

1. **Database Connection Errors**
```bash
# Check database connection
psql $NEON_DATABASE_URL
```

2. **S3 Access Issues**
```bash
# Verify AWS credentials
aws s3 ls s3://your-bucket-name
```

3. **Email Configuration**
- Verify app password is correct
- Check SMTP settings
- Test email connection

4. **Docker Issues**
```bash
# Check logs
docker-compose logs -f

# Restart services
docker-compose restart
```

## 🔐 Security Notes
- Keep .secrets file secure and never commit to version control
- Rotate credentials regularly
- Monitor access logs
- Use least privilege principle for AWS IAM

## 📝 License

