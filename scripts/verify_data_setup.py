import pandas as pd

FILE_PATH = "data/raw/clusterdata2019_kaggle_subset.csv"

def main():
    print(" Running smoke test...")

    try:
        df = pd.read_csv(FILE_PATH)
    except FileNotFoundError:
        print(f" File not found at {FILE_PATH}")
        return

    print(" File loaded successfully!\n")

    print(" Shape of dataset:")
    print(df.shape)

    print("\n Columns:")
    print(df.columns.tolist())

    print("\n Sample rows:")
    print(df.head(5))

if __name__ == "__main__":
    main()