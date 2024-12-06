import pandas as pd
import numpy as np
from datetime import datetime
from geopy.distance import geodesic

def extract_data():
    dataset = pd.read_csv("https://frauddetectionproject2024.s3.eu-west-3.amazonaws.com/fraudTest.csv")
    return dataset

def transform_data(dataset):
    frauds = dataset[dataset['is_fraud'] == 1]
    non_frauds = dataset[dataset['is_fraud'] == 0]
    non_frauds_sampled = non_frauds.sample(n=50000, random_state=42)
    data_reduc = pd.concat([frauds, non_frauds_sampled])
    data_reduc['trans_date_trans_time'] = pd.to_datetime(data_reduc['trans_date_trans_time'])
    data_reduc['month'] = data_reduc['trans_date_trans_time'].dt.month
    data_reduc['day_of_week'] = data_reduc['trans_date_trans_time'].dt.dayofweek + 1
    data_reduc['hour'] = data_reduc['trans_date_trans_time'].dt.hour
    data_reduc['dob'] = pd.to_datetime(data_reduc['dob'])

    def calcule_age(born):
        today = datetime.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    
    data_reduc['age'] = data_reduc['dob'].apply(calcule_age)
    data_reduc['distance'] = data_reduc.apply(lambda row: geodesic((row['lat'], row['long']), (row['merch_lat'], row['merch_long'])).km, axis=1)
    
    return data_reduc

def load_data(data_reduc):
    data_reduc.to_csv('data_post_etl.csv', index=False)
    print("Données prétraitées et chargées avec succès.")

if __name__ == "__main__":
    dataset = extract_data()
    data_reduc = transform_data(dataset)
    load_data(data_reduc)
    print("Prétraitement et chargement des données terminés.")