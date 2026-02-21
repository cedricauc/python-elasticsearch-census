#!/usr/bin/env python3
"""
US census Data MCP Server
A Model Context Protocol server for querying US census data stored in Elasticsearch.

Author: Cedric Auclair
"""
import os
from typing import Any, Optional
import json
from datetime import datetime
from pydantic import BaseModel, field_validator, ValidationError
from mcp.server.fastmcp import FastMCP
from elasticsearch import AsyncElasticsearch
from contextlib import asynccontextmanager

# Initialize FastMCP server
mcp = FastMCP("us-census")

# Constants
ES_INDEX = "us-census"

# API key from environment variable or fallback for development
ES_API_KEY = os.getenv('ES_API_KEY')
ES_CLOUD_ID = os.getenv('ES_CLOUD_ID')

# Pydantic model for parameter validation
class QueryCensusDataParams(BaseModel):
    state: Optional[str] = None

    @field_validator("state")
    def validate_state(cls, value):
        if value is None:
            return value
        if not value.isdigit() or len(value) != 2:
            raise ValueError("State must be a 2‑digit FIPS code, e.g., '01' for Alabama")
        return value


@asynccontextmanager
async def get_es_client():
    """
    Context manager for Elasticsearch client.
    """
    client = AsyncElasticsearch(cloud_id=ES_CLOUD_ID, api_key=ES_API_KEY)
    try:
        yield client
    finally:
        await client.close()

# Elasticsearch helper function
async def query_elasticsearch(query: dict) -> dict[str, Any] | None:
    """
    Makes a request to Elasticsearch with proper error handling.
    """
    print(f"Sending query to Elasticsearch: {json.dumps(query)}")
    
    # Use context manager
    async with get_es_client() as client:
        try:
            response = await client.search(
                index=ES_INDEX,
                body=query
            )
            return response
        except Exception as e:
            print(f"Error querying Elasticsearch: {e}")
            return None


# Resources
@mcp.resource("census://states")
async def list_states() -> str:
    """List available states"""
    query = {
        "size": 0,
        "aggs": {
            "states": {
                "terms": {
                    "field": "state",
                    "size": 60
                }
            }
        }
    }

    data = await query_elasticsearch(query)
    if not data:
        return json.dumps({"error": "Unable to query Elasticsearch"}, indent=2)

    states = [b["key"] for b in data["aggregations"]["states"]["buckets"]]

    return json.dumps({"states": states}, indent=2)


@mcp.resource("census://summary")
async def census_summary() -> str:
    """
    Summary statistics (e.g., total population, median age...)
    """
    query = {
        "size": 0,
        "aggs": {
            "population_stats": {
                "stats": {"field": "P001001"}
            },
            "median_age_stats": {
                "stats": {"field": "P013001"}
            },
            "average_family_size_stats": {
                "stats": {"field": "P037001"}
            },
            "correctional_male_adults_facilities_stats": {
                "stats": {"field": "PCT021005"}
            },
            "median_home_value_stats": {
                "stats": {"field": "B25077_001E"}
            },
            "mean_household_income_stats": {
                "stats": {"field": "B19025_001E"}
            },
            "foreign_born_population_stats": {
                "stats": {"field": "B05002_013E"}
            }
        }
    }

    data = await query_elasticsearch(query)
    if not data:
        return json.dumps({"error": "Unable to query Elasticsearch"}, indent=2)

    return json.dumps(data["aggregations"], indent=2)


# Tools
@mcp.tool()
async def query_census_data(params: QueryCensusDataParams) -> str:
    """
    Query step data with customizable parameters
    
    Args:
        state: US state as 2‑digit FIPS code format
        min_population: integer format
        max_population: integer format
        geometry: JSON format
    """
    # Extract parameters from model
    filters = []

    if params.state:
        filters.append({"term": {"state": params.state}})

    if params.min_population:
        filters.append({"range": {"P001001": {"gte": params.min_population}}})

    if params.max_population:
        filters.append({"range": {"P001001": {"lte": params.max_population}}})

    if params.geometry: 
        filters.append({ 
            "geo_shape": { 
                "geometry": { 
                    "shape": params.geometry, 
                    "relation": "intersects" 
                } 
            } 
        })

    query = {
        "query": {"bool": {"must": filters}} if filters else {"match_all": {}},
        "size": 50
    }

    data = await query_elasticsearch(query)
    if not data:
        return json.dumps({"error": "Unable to query Elasticsearch"}, indent=2)

    results = [hit["_source"] for hit in data["hits"]["hits"]]

    return json.dumps({"results": results}, indent=2)


@mcp.tool()
async def get_total_population_by_state() -> str:
    """
    Return total population grouped by state.
    """
    query = {
        "size": 0,
        "aggs": {
            "states": {
                "terms": {
                    "field": "state",
                    "size": 60
                },
                "aggs": {
                    "total_population": {
                        "sum": {
                            "field": "P001001"
                        }
                    }
                }
            }
        }
    }

    data = await query_elasticsearch(query)
    if not data:
        return json.dumps({"error": "Unable to query Elasticsearch"}, indent=2)

    results = []
    for bucket in data["aggregations"]["states"]["buckets"]:
        results.append({
            "state": bucket["key"],
            "total_population": bucket["total_population"]["value"]
        })

    return json.dumps({
        "states": results,
        "count": len(results)
    }, indent=2)


@mcp.tool()
async def get_total_household_income_by_state() -> str:
    """
    Return total total household income grouped by state.
    """
    query = {
        "size": 0,
        "aggs": {
            "states": {
                "terms": {
                    "field": "state",
                    "size": 60
                },
                "aggs": {
                    "total_household_income_by_state": {
                        "sum": {
                            "field": "B19025_001E"
                        }
                    }
                }
            }
        }
    }

    data = await query_elasticsearch(query)
    if not data:
        return json.dumps({"error": "Unable to query Elasticsearch"}, indent=2)

    results = []
    for bucket in data["aggregations"]["states"]["buckets"]:
        results.append({
            "state": bucket["key"],
            "total_household_income_by_state": bucket["total_household_income_by_state"]["value"]
        })

    return json.dumps({
        "states": results,
        "count": len(results)
    }, indent=2)


@mcp.tool()
async def get_us_states_geojson() -> str:
    """
    Return a full GeoJSON FeatureCollection of US states,
    including geometry and population for choropleth mapping.
    """
    query = {
        "size": 60,
        "_source": ["state", "state_name", "P001001", "geometry"],
        "query": {"match_all": {}}
    }

    data = await query_elasticsearch(query)
    if not data:
        return json.dumps({"error": "Unable to query Elasticsearch"}, indent=2)

    features = []
    for hit in data["hits"]["hits"]:
        src = hit["_source"]

        features.append({
            "type": "Feature",
            "properties": {
                "state": src["state"],
                "state_name": src["state_name"],
                "population": src["P001001"]
            },
            "geometry": src["geometry"]
        })

    feature_collection = {
        "type": "FeatureCollection",
        "features": features
    }

    return json.dumps(feature_collection, indent=2)


# Prompts
@mcp.prompt()
def census_state_report(state: str = None) -> str:
    """
    Create a demographic report for a specific state
    """
    if state:
        return f"""Please analyze the Census data for state FIPS {state}. Provide:
1. Total population (P001001)
2. Median age (P013001)
3. Average family size (P037001)
4. Correctional facilities for male adults population (PCT021005)
5. Median home value (B25077_001E)
6. Mean household income (B19025_001E) 
7. Foreign-born population (B05002_013E)
8. Comparison with national averages
9. Notable demographic characteristics
10. A clear narrative summary of what stands out in this state's data"""
    else:
        return """Please analyze the national Census data. Provide:
1. Total U.S. population
2. States with highest and lowest population
3. Median age across all states
4. States with highest and lowest median age
5. Average family size across all states
6. States with highest and lowest average family size
7. Correctional facilities for male adults population across all states
8. States with highest and lowest correctional facilities for male adults population
9. Median home value across all states
10. States with highest and lowest median home value
11. Mean household income across all states
12. States with highest and lowest mean household income
13. Foreign-born population across all states
14. States with highest and lowest foreign-born population
15. Notable demographic patterns
16. A clear narrative summary of national trends"""


@mcp.prompt()
def census_trend_analysis(year_start: str, year_end: str) -> str:
    """
    Analyze demographic trends over a specific period
    """
    return f"""Analyze Census demographic trends between {year_start} and {year_end}.
Please include:
1. Population growth or decline by state
2. Changes in median age
3. States with the most significant demographic shifts
4. States with the most significant mean household income
5. States with the most significant foreign-born population
6. Regional patterns (e.g., South vs. Northeast)
7. A narrative explaining the major drivers of these changes"""


@mcp.prompt()
def census_state_comparison(state_a: str, state_b: str) -> str:
    """
    Compare demographic data between two states
    """
    return f"""Compare Census demographic data between state FIPS {state_a} and {state_b}:
1. Total population comparison
2. Median age comparison
3. Growth or decline trends
4. Notable demographic differences
5. A clear summary explaining how these two states differ demographically"""


# Main function to run the server
if __name__ == "__main__":
    mcp.run()