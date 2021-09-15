import argparse
import os
import requests
import tempfile
import numpy as np
import pandas as pd
import boto3

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

def merge_two_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z

BASE_DIR = "/opt/ml/processing"

columns_names = [
    "target_fg",
    "target_og",
    "ebc",
    "srm",
    "ph",
]
label_column = "ibu"

columns_dtype = {
    "target_fg": np.float64,
    "target_og": np.float64,
    "ebc": np.float64,
    "srm": np.float64,
    "ph": np.float64,
}
label_column_dtype = {"ibu": np.float64}

if __name__ == "__main__":
    logger.debug("Iniciando pŕé-processamento.")
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_name", type=str, required=True)
    parser.add_argument("--bucket_cleaned", type=str, required=True)
    parser.add_argument("--bucket_dataset", type=str, required=True)
    
    args = parser.parse_args()
    project_name = args.project_name
    bucket_cleaned = args.bucket_cleaned
    bucket_dataset = args.bucket_dataset
    
    logger.info(f"Baixando dataset do bucket: {bucket_dataset}")
    fn = f"{BASE_DIR}/data/dataset.csv"
    s3 = boto3.resource("s3")
    s3.Bucket(bucket_dataset).download_file(key, f"{BASE_DIR}/data/dataset.csv")

    logger.debug("Carregando dataset.")
    df = pd.read_csv(
        fn,
        header=None,
        names=columns_names + [label_column],
        dtype=merge_two_dicts(columns_dtype, label_column_dtype),
    )
    os.unlink(fn)

    df = df[columns_names + [label_column]]
    df = df.dropna(subset=[label_column])

    logger.debug("Criando transformers")
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler())
        ]
    )

    preprocess = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, columns_names),
        ]
    )
    
    logger.debug("Aplicando transformers")
    y = df.pop(label_column)
    X_pre = preprocess.fit_transform(df)
    y_pre = y.to_numpy().reshape(len(y), 1)
    X = np.concatenate((y_pre, X_pre), axis=1)

    logger.info("Separando datasets de treino, teste e validacao")
    np.random.shuffle(X)
    train, validation, test = np.split(X, [int(.7 * len(X)), int(.85 * len(X))])

    logger.info("Writing out datasets to %s.", BASE_DIR)
    pd.DataFrame(train).to_csv(f"{BASE_DIR}/train/train.csv", header=False, index=False)
    pd.DataFrame(validation).to_csv(
        f"{BASE_DIR}/validation/validation.csv", header=False, index=False
    )
    pd.DataFrame(test).to_csv(f"{BASE_DIR}/test/test.csv", header=False, index=False)
    
    logger.debug("Pŕé-processamento finalizado.")