# Documentation Technique - FraudGuardian 🛡️ 
## Table des matières
1. [Introduction](#1-introduction)
2. [Architecture du système](#2-architecture-du-système)
3. [Flux de données](#3-flux-de-données)
4. [Composants clés](#4-composants-clés)

## 1. Introduction

### 1.1 Contexte
La détection de fraude en temps réel est un défi majeur dans le secteur financier. Cette solution propose un système complet qui analyse en continu les transactions pour détecter les activités frauduleuses.

### 1.2 Objectifs du système
- Analyse en temps réel (< 1 minute)
- Alertes immédiates
- Historisation des transactions
- Reporting quotidien

## 2. Architecture du système

### 2.1 Structure du projet
```plaintext
project/
├── dags/
│   ├── backup_dag.py
│   ├── fraud_detection_dag.py
│   ├── monitoring_dag.py
│   └── utils/
│       └── common.py
├── models/
│   ├── etl.py
│   └── model.py
├── streamlit/
│   └── app.py
└── docker/
    ├── docker-compose.yaml
    ├── Dockerfile
    ├── Dockerfile.mlflow
    └── Dockerfile.streamlit
```

### 2.2 Composants principaux

#### Utilitaires communs (common.py)
```python
# Exemple de notre common.py optimisé
import os
import logging
from functools import wraps

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def log_function_call(func):
    """Décorateur pour logger les appels de fonction"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Calling {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            raise
    return wrapper

@log_function_call
def get_s3_client():
    return boto3.client('s3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
    )
```

## 3. Flux de données

### 3.1 Module commun (common.py)
Le système utilise un module commun qui centralise les configurations et utilitaires :

```python
# Configuration des logs et variables d'environnement
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Décorateur pour le logging des fonctions
def log_function_call(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Calling {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            raise
    return wrapper
```

### 3.2 Pipeline principal (fraud_detection_dag.py)

1. **Chargement des dépendances**
```python
def load_dependencies(**context):
    """Charge le modèle et l'ETL depuis S3."""
    try:
        s3_client = get_s3_client()
        tmp_dir = '/tmp/fraud_detection'
        os.makedirs(tmp_dir, exist_ok=True)

        files = {
            'model': f"{S3_PREFIX}/models/random_forest_model.pkl",
            'etl': f"{S3_PREFIX}/etl/etl.py"
        }
        
        for key, s3_path in files.items():
            local_path = os.path.join(tmp_dir, os.path.basename(s3_path))
            s3_client.download_file(S3_BUCKET, s3_path, local_path)
            context['task_instance'].xcom_push(key=f"{key}_path", value=local_path)
```

2. **Traitement des transactions**
```python
def process_transaction(**context):
    """Traite et analyse une transaction pour détecter une fraude."""
    try:
        ti = context['task_instance']
        transactions = ti.xcom_pull(key='transactions')

        if not transactions:
            logger.warning("Aucune transaction à traiter.")
            return 'skip_processing'

        # Transformation et prédiction
        df = prepare_transaction_data(transactions)
        prediction = predict_fraud(df, ti)
        
        return 'notify_fraud' if prediction else 'notify_normal'
```

### 3.3 Sauvegarde des données (backup_dag.py)
```python
def perform_neon_backup(**context):
    """Sauvegarde des tables depuis Neon DB"""
    try:
        engine = get_db_engine()
        work_dir = '/opt/airflow/backups'
        os.makedirs(work_dir, exist_ok=True)
        
        # Vérification des données
        tables_data = get_tables_count(engine)
        
        # Création des backups
        backup_files = create_backup_files(engine, tables_data, work_dir)
        
        # Upload vers S3
        uploaded_files = upload_to_s3(backup_files)
        
        # Notification
        send_backup_notification(tables_data, uploaded_files)
```

## 4. Monitoring et Alertes

### 4.1 Health Check System (monitoring_dag.py)
```python
def check_system_health(**context):
    """Vérifie l'état de santé des composants"""
    status = {'api': False, 'database': False, 'storage': False}
    
    try:
        # Vérification API
        response = requests.get(API_URL, timeout=10)
        status['api'] = response.status_code == 200
            
        # Vérification Base de données
        with get_db_engine().connect() as conn:
            conn.execute("SELECT 1")
            status['database'] = True
            
        # Vérification S3
        s3 = get_s3_client()
        s3.head_bucket(Bucket=S3_BUCKET)
        status['storage'] = True
        
        send_health_report(status)
```

### 4.2 Système de notification
```python
@log_function_call
def send_email(subject: str, body: str, to_email: Optional[str] = None) -> bool:
    """
    Envoie un email avec gestion des erreurs
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = os.environ.get('EMAIL_USER')
        msg['To'] = to_email or os.environ.get('EMAIL_TO')
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(
            os.environ.get('SMTP_SERVER'),
            int(os.environ.get('SMTP_PORT'))
        ) as server:
            server.starttls()
            server.login(
                os.environ.get('EMAIL_USER'),
                os.environ.get('EMAIL_PASSWORD')
            )
            server.send_message(msg)
            return True
            
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False
```

## 5. Pipeline ML

### 5.1 Structure de dépendances
Le système utilise une architecture où le modèle et l'ETL sont stockés sur S3 et chargés dynamiquement :

```python
# Structure S3
fraud_detection_bucket/
├── models/
│   └── random_forest_model.pkl
└── etl/
    └── etl.py

# Chargement dynamique
def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

### 5.2 Transformation des données
Notre ETL est conçu pour un traitement en temps réel :

```python
def transform_data(dataset):
    """Transforme les données pour la détection de fraude"""
    data_reduc = dataset.copy()
    
    # Features temporelles
    data_reduc['trans_date_trans_time'] = pd.to_datetime(
        data_reduc['trans_date_trans_time']
    )
    data_reduc['month'] = data_reduc['trans_date_trans_time'].dt.month
    data_reduc['day_of_week'] = data_reduc['trans_date_trans_time'].dt.dayofweek + 1
    data_reduc['hour'] = data_reduc['trans_date_trans_time'].dt.hour
    
    # Calcul de la distance
    data_reduc['distance'] = data_reduc.apply(
        lambda row: geodesic(
            (row['lat'], row['long']),
            (row['merch_lat'], row['merch_long'])
        ).km,
        axis=1
    )
    
    return data_reduc
```

## 6. Stockage et Persistance

### 6.1 Stratégie de backup
Le système implémente une stratégie de backup mensuelle :

```python
def perform_backup(engine, table, work_dir):
    """Effectue le backup d'une table"""
    current_date = datetime.now().strftime('%Y%m')
    
    # Extraction des données
    df = pd.read_sql(f"SELECT * FROM {table}", engine)
    
    # Sauvegarde en CSV
    csv_file = os.path.join(work_dir, f"{table}_{current_date}.csv")
    df.to_csv(csv_file, index=False)
    
    return csv_file

def upload_to_s3(files):
    """Upload les fichiers vers S3"""
    s3_client = get_s3_client()
    uploaded = []
    
    for file in files:
        try:
            file_name = os.path.basename(file)
            s3_key = f"{S3_PREFIX}/backups/{current_date}/{file_name}"
            s3_client.upload_file(file, S3_BUCKET, s3_key)
            uploaded.append(s3_key)
        finally:
            os.remove(file)  # Nettoyage
            
    return uploaded
```

### 6.2 Gestion des transactions
Structure des tables pour les transactions :

```sql
-- Tables optimisées avec indices
CREATE TABLE fraud_transactions (
    transaction_id SERIAL PRIMARY KEY,
    cc_num BIGINT,
    merchant VARCHAR(255),
    category VARCHAR(100),
    amt DECIMAL(10, 2),
    trans_date_trans_time TIMESTAMP,
    is_fraud BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_fraud_trans_date 
ON fraud_transactions(trans_date_trans_time);

CREATE INDEX idx_fraud_trans_num 
ON fraud_transactions(trans_num);
```

## 7. Monitoring et Alertes

### 7.1 Monitoring système
Le système implémente plusieurs niveaux de monitoring :

```python
def check_system_health():
    """Vérifie l'état de santé global du système"""
    status = {
        'api': check_api_status(),
        'database': check_database_connectivity(),
        'storage': check_s3_access(),
    }
    
    report = generate_health_report(status)
    send_alert_if_needed(status)
    
    return status

def generate_health_report(status):
    """Génère un rapport de santé détaillé"""
    return f"""
    System Health Report
    -------------------
    API: {'✅' if status['api'] else '❌'}
    Database: {'✅' if status['database'] else '❌'}
    Storage: {'✅' if status['storage'] else '❌'}
    
    {'⚠️ Action required!' if not all(status.values()) else '✅ All systems operational'}
    """
```

### 7.2 Alertes et notifications
Système d'alertes multi-niveaux :

```python
def send_alert(transaction, is_fraud, probability):
    """Envoie une alerte selon le niveau de risque"""
    alert_level = get_alert_level(probability)
    template = get_alert_template(is_fraud)
    
    subject = {
        True: "🚨 ALERTE : FRAUDE DETECTÉE",
        False: "✅ Transaction normale"
    }[is_fraud]
    
    body = template.format(
        probability=f"{probability:.2%}",
        transaction_details=format_transaction(transaction)
    )
    
    send_email(subject=subject, body=body)
```