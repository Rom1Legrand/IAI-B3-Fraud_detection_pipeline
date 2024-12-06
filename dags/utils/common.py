# dags/utils/common.py
import os
import logging
import boto3
from sqlalchemy import create_engine
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from functools import wraps
from typing import Optional, Any, Callable

# Configuration du logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration des variables d'environnement
API_URL = os.environ.get('FRAUD_API_URL', 'https://real-time-payments-api.herokuapp.com/current-transactions')
NEON_URL = os.environ.get('NEON_DATABASE_URL')
S3_BUCKET = os.environ.get('S3_BUCKET')
S3_PREFIX = 'fraud-detection-bucket'

def log_function_call(func: Callable) -> Callable:
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
    """Crée et retourne un client S3"""
    return boto3.client(
        's3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
    )

@log_function_call
def get_db_engine():
    """Crée et retourne une connexion à la base de données"""
    return create_engine(NEON_URL)

@log_function_call
def send_email(subject: str, body: str, to_email: Optional[str] = None) -> bool:
    """
    Envoie un email avec gestion des erreurs
    
    Args:
        subject: Sujet de l'email
        body: Corps de l'email
        to_email: Destinataire (optionnel)
        
    Returns:
        bool: True si l'envoi est réussi, False sinon
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = os.environ.get('EMAIL_USER')
        msg['To'] = to_email or os.environ.get('EMAIL_TO', 'xxxxx@gmail.com')
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(
            os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
            int(os.environ.get('SMTP_PORT', 587))
        ) as server:
            server.starttls()
            server.login(
                os.environ.get('EMAIL_USER'),
                os.environ.get('EMAIL_PASSWORD')
            )
            server.send_message(msg)
            logger.info(f"Email sent successfully: {subject}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

def check_environment() -> bool:
    """
    Vérifie que toutes les variables d'environnement nécessaires sont présentes
    
    Returns:
        bool: True si toutes les variables sont présentes, False sinon
    """
    required_vars = [
        'NEON_DATABASE_URL',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'S3_BUCKET',
        'EMAIL_USER',
        'EMAIL_PASSWORD'
    ]
    
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        return False
        
    logger.info("All required environment variables are present")
    return True