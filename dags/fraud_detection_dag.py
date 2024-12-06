from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from datetime import datetime, timedelta
from utils.common import (
    logger, get_db_engine, get_s3_client, send_email,
    API_URL, S3_BUCKET, S3_PREFIX
)
import requests
import joblib
import importlib.util
import json
import os
import pandas as pd

# Configuration par défaut pour le DAG
default_args = {
    'owner': 'fraud_team',
    'depends_on_past': False,
    'email_on_failure': True,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

# Définition des fonctions Python pour les tâches
def load_dependencies(**context):
    """Charge le modèle et l'ETL depuis S3."""
    try:
        logger.info("Chargement des dépendances depuis S3...")
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
            logger.info(f"{key.capitalize()} chargé avec succès depuis {s3_path}.")

        return True
    except Exception as e:
        logger.error(f"Erreur lors du chargement des dépendances : {e}")
        raise

def fetch_api(**context):
    """Récupère les transactions depuis l'API."""
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        transactions = response.json()
        context['task_instance'].xcom_push(key='transactions', value=transactions)
        logger.info("Transactions récupérées depuis l'API avec succès.")
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'API : {e}")
        raise

def process_transaction(**context):
    """Traite et analyse une transaction pour détecter une fraude."""
    try:
        ti = context['task_instance']
        transactions = ti.xcom_pull(key='transactions')

        if not transactions:
            logger.warning("Aucune transaction à traiter.")
            return 'skip_processing'

        transactions = json.loads(transactions)
        df = pd.DataFrame(transactions['data'], columns=transactions['columns'])
        df = df.rename(columns={'current_time': 'trans_date_trans_time'})

        # Charger ETL et modèle
        etl_path = ti.xcom_pull(key='etl_path')
        model_path = ti.xcom_pull(key='model_path')

        spec = importlib.util.spec_from_file_location("etl", etl_path)
        etl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(etl)

        df_transformed = etl.transform_data(df)
        model = joblib.load(model_path)
        prediction = model.predict(df_transformed)[0]
        probability = model.predict_proba(df_transformed)[:, 1][0]

        logger.info(f"Prédiction : {'FRAUDE' if prediction else 'NORMAL'} avec probabilité {probability:.2%}.")
        ti.xcom_push(key='is_fraud', value=bool(prediction))
        ti.xcom_push(key='fraud_probability', value=probability)

        return 'notify_fraud' if prediction else 'notify_normal'
    except Exception as e:
        logger.error(f"Erreur lors du traitement des transactions : {e}")
        return 'skip_processing'

def send_transaction_email(**context):
    """Envoie une alerte par email selon le résultat."""
    try:
        ti = context['task_instance']
        is_fraud = ti.xcom_pull(key='is_fraud')
        probability = ti.xcom_pull(key='fraud_probability')

        subject = "🚨 ALERTE : FRAUDE DETECTÉE" if is_fraud else "✅ Transaction normale"
        body = f"Transaction {'frauduleuse' if is_fraud else 'normale'} détectée avec une probabilité de {probability:.2%}."

        send_email(subject=subject, body=body)
        logger.info(f"Email envoyé : {subject}.")
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email : {e}")

def store_transaction(**context):
    """Stocke les données en base."""
    try:
        ti = context['task_instance']
        transactions = ti.xcom_pull(key='transactions')
        is_fraud = ti.xcom_pull(key='is_fraud')

        if not transactions:
            logger.error("Aucune transaction à stocker.")
            return

        df = pd.DataFrame(json.loads(transactions)['data'], columns=json.loads(transactions)['columns'])
        df['is_fraud'] = is_fraud
        engine = get_db_engine()
        table = 'fraud_transactions' if is_fraud else 'normal_transactions'
        df.to_sql(table, engine, if_exists='append', index=False)
        logger.info(f"Transactions stockées dans {table}.")
    except Exception as e:
        logger.error(f"Erreur lors du stockage des transactions : {e}")
        raise

# Définition du DAG
with DAG(
    'fraud_detection_pipeline',
    default_args=default_args,
    description='Pipeline de détection de fraude en temps réel',
    schedule_interval='* * * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False
) as dag:
    
    load_deps = PythonOperator(
        task_id='load_dependencies',
        python_callable=load_dependencies,
    )

    fetch_api_task = PythonOperator(
        task_id='fetch_api',
        python_callable=fetch_api,
    )

    process_task = BranchPythonOperator(
        task_id='process_transaction',
        python_callable=process_transaction,
    )

    notify_fraud_task = PythonOperator(
        task_id='notify_fraud',
        python_callable=send_transaction_email,
    )

    notify_normal_task = PythonOperator(
        task_id='notify_normal',
        python_callable=send_transaction_email,
    )

    store_fraud_task = PythonOperator(
        task_id='store_fraud',
        python_callable=store_transaction,
    )

    store_normal_task = PythonOperator(
        task_id='store_normal',
        python_callable=store_transaction,
    )

    skip_task = PythonOperator(
        task_id='skip_processing',
        python_callable=lambda: logger.info("Pas de traitement nécessaire."),
    )

    # Orchestration des tâches
    load_deps >> fetch_api_task >> process_task
    process_task >> [notify_fraud_task, notify_normal_task, skip_task]
    notify_fraud_task >> store_fraud_task
    notify_normal_task >> store_normal_task
