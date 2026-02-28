# ingest_data.py
# This Python script fetch data from US census API and ingests it into an Elasticsearch index.

import json
from typing import List
from elasticsearch import Elasticsearch, helpers
import os
import requests
import geopandas as gpd

# Constants
HOST = "https://api.census.gov/data" # US Census base URL
GET_SF1_VARS = ["NAME", "P001001", "P013001", "P037001", "PCT021005"] # API variable for Decennial Census
GET_ACS_VARS = ["NAME", "B25077_001E", "B19025_001E", "B05002_013E"] # API variable for ACS

GEOJSON_PATH = "cb_2024_us_state_500k.geojson" # Geojson path
SHP_PATH = "cb_2024_us_state_500k.shp" # Shp path

ES_INDEX = "us-census" # Index name

# API key from environment variable or fallback for development
ES_API_KEY = os.getenv('ES_API_KEY')
ES_CLOUD_ID = os.getenv('ES_CLOUD_ID')

# --- Index Mapping ---
INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "NAME": {"type": "text"}, # County/State name
            "state_name": {"type": "keyword"}, # County/State name
            "state": {"type": "keyword"}, # FIPS code
            "dataset": { "type": "keyword" }, # Dataset (sf1, acs)
            "year": {"type": "keyword"}, # Census year (e.g., "2010") 
            "P001001": {"type": "integer"}, # Total population
            "P013001": {"type": "float"}, # Median age
            "P037001": {"type": "float"}, # Average family size          
            "PCT021005": {"type": "integer"}, # Correctional facilities for Male adults
            "B25077_001E": {"type": "long"}, # Median home value 
            "B19025_001E": {"type": "long"}, # Mean household income (average) 
            "B05002_013E": {"type": "long"}, # Foreign-born population (immigrant)
            "geometry": { "type": "geo_shape" } # Polygon boundaries
        }
    },
    "settings": {
        "number_of_shards": 1,  
        "number_of_replicas": 0  
        
    }
}


def fetch_census_data(year: str, vars: List[str], dataset: str):
    """
    Fetches Census data for a given dataset, and year (e.g., '2000', 'dec/sf1' → '2000/dec/sf1').
    """
    base_url = "/".join([HOST, year, dataset])

    params = {
        "get": ",".join(vars),
        "for": "state:*"
    }

    response = requests.get(base_url, params=params)

    if response.status_code != 200:
        raise RuntimeError(f"Census API error: {response.text}")

    return response.json()


def create_es_client():
    """
    Creates and returns an Elasticsearch client.
    """
    print(f"Connecting to Elasticsearch at {ES_CLOUD_ID}...")
    try:
        client = Elasticsearch(
            cloud_id=ES_CLOUD_ID, 
            api_key=ES_API_KEY
        )
        if not client.ping():
            raise ConnectionError("Could not connect to Elasticsearch.")
        print("Connection successful!")
        return client
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def generate_actions(data, geojson, index_name):
    """
    Reads API and yields a generator of actions for the bulk API.
    """
    header = data[0]
    census_docs = {}

    for row in data[1:]:
        doc = dict(zip(header, row))

        fips = doc.get("state")
        if not fips: 
            continue

        for field in ["P001001", "P013001", "P037001", "PCT021005", "B25077_001E", "B19025_001E", "B05002_013E"]:
            if field in doc and doc[field].isdigit(): 
                doc[field] = int(doc[field])

        census_docs[fips] = doc

    for feature in geojson["features"]: 
        props = feature["properties"] 
        geom = feature["geometry"]
        fips = props.get("STATEFP")

        # Skip U.S. territories
        if fips in ['60', '66', '69', '72', '78']:
            continue

        if not fips: 
            print("Warning: missing FIPS in geometry:", props) 
            continue

        if fips not in census_docs: 
            print("Missing census data for state:", fips) 
            continue

        docs = census_docs[fips].copy() 
        # Add geometry + metadata
        docs["geometry"] = geom 
        docs["state"] = fips 
        docs["state_name"] = props.get("NAME") 
        docs["year"] = "2010"
        docs["dataset"] = "sf1_acs"

        yield {
            "_index": index_name,
            "_source": docs
        }


def ingest_data(client: Elasticsearch, year: str = "2010"):
    """
    Coordinates the ingestion process: deletes the old index, creates a new one, and ingests the data.
    """
    # 1. Delete the index if it already exists for a clean start.
    if client.indices.exists(index=ES_INDEX):
        print(f"Index '{ES_INDEX}' found. Deleting...")
        client.indices.delete(index=ES_INDEX)
        print("Index deleted.")

    # 2. Convert SHP → GeoJSON if needed 
    if not os.path.exists(GEOJSON_PATH): 
        print("GeoJSON not found. Converting shapefile...") 
        os.environ["SHAPE_RESTORE_SHX"] = "YES" 
        gdf = gpd.read_file(SHP_PATH) 
        gdf.to_file(GEOJSON_PATH, driver="GeoJSON") 

    # 3. Create the index with the correct mapping.
    print(f"Creating index '{ES_INDEX}' with the specified mapping...")
    client.indices.create(index=ES_INDEX, body=INDEX_MAPPING)
    print("Index created successfully.")

    # 4. Load GeoJSON, Fetch Census data and ingest using the Bulk API.
    try:
        print("Loading GeoJSON...")
        # Initialize with a valid empty GeoJSON structure 
        geojson = { 
            "type": "FeatureCollection", 
            "features": [] 
        } 
        try: 
            with open(GEOJSON_PATH, "r") as f: 
                geojson = json.load(f) 
        except FileNotFoundError: 
            print("GeoJSON file not found. Using empty FeatureCollection.") 
        except json.JSONDecodeError: 
            print("GeoJSON file is invalid. Using empty FeatureCollection.")

        print(f"Fetching Census data for {year}/dec/sf1...")
        sf1 = fetch_census_data(year, GET_SF1_VARS, "dec/sf1")

        print(f"Fetching ACS data for {year}/acs/acs5...")
        acs = fetch_census_data(year, GET_ACS_VARS, "acs/acs5")

        print("Merging datasets...")
        sf1_header = sf1[0] 
        acs_header = acs[0] 
        # Build lookup dictionary for ACS rows by state 
        acs_lookup = {row[-1]: row for row in acs[1:]} 
        # Build merged header (avoid repeating NAME and state) 
        merged_header = sf1_header[:-1] + acs_header[1:] 
        merged = [merged_header] 
        
        # Merge rows 
        for row in sf1[1:]: 
            state = row[-1] 
            if state in acs_lookup: 
                acs_row = acs_lookup[state] 
                merged_row = row[:-1] + acs_row[1:] 
                merged.append(merged_row)   

        print("Prepare actions for the bulk helper...")
        # Use the generator to prepare actions for the bulk helper
        actions = generate_actions(merged, geojson, ES_INDEX)
        # For streaming debug
        for ok, result in helpers.streaming_bulk(client, actions): 
            if not ok: 
                print(result) 
                break
        # Ingest the data using the bulk helper
        success, failed = helpers.bulk(client, actions)
        print(f"Ingestion complete. Documents successfully ingested: {success}")
        if failed:
            print(f"Failed to ingest documents: {len(failed)}")

    except Exception as e:
        print(f"An error occurred during file reading or ingestion: {e}")
        return
    
    # 5. Refresh and print the final document count.
    client.indices.refresh(index=ES_INDEX)
    count = client.count(index=ES_INDEX)['count']
    print(f"Final check: The index '{ES_INDEX}' now contains {count} documents.")


if __name__ == "__main__":
    es_client = create_es_client()
    if es_client:
        ingest_data(es_client)
