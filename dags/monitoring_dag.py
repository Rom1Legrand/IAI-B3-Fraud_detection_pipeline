from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import requests
from utils.common import (
    logger, get_db_engine, get_s3_client, send_email,
    API_URL, S3_BUCKET, S3_PREFIX
)

def check_system_health(**context):
    """
    Vérifie l'état de santé des différents composants du système
    """
    logger.info("Starting system health check")
    status = {'api': False, 'database': False, 'storage': False}
    
    try:
        # Vérification API
        response = requests.get(API_URL, timeout=10)
        status['api'] = response.status_code == 200
        logger.info(f"API status: {'OK' if status['api'] else 'FAILED'}")
            
        # Vérification Base de données
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        status['database'] = True
        logger.info("Database connection: OK")
            
        # Vérification S3
        s3 = get_s3_client()
        s3.head_bucket(Bucket=S3_BUCKET)
        s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_PREFIX, MaxKeys=1)
        status['storage'] = True
        logger.info("S3 access: OK")
        
        # Génération du rapport
        body = f"""System Health Report

System Components:
-----------------
API: {'✅' if status['api'] else '❌'}
Database: {'✅' if status['database'] else '❌'}
Storage: {'✅' if status['storage'] else '❌'}

Configuration:
-------------
API URL: {API_URL}
S3 Path: s3://{S3_BUCKET}/{S3_PREFIX}

{'⚠️ Action required!' if not all(status.values()) else '✅ All systems operational'}
"""
        
        send_email(
            subject="System Health Report - Fraud Detection System",
            body=body
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise

default_args = {
    'owner': 'fraud_team',
    'depends_on_past': False,
    'email_on_failure': True,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    'fraud_monitoring',
    default_args=default_args,
    description='Daily system health monitoring',
    schedule_interval='0 0 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False
) as dag:

    health_check = PythonOperator(
        task_id='system_health_check',
        python_callable=check_system_health,
        provide_context=True
    )