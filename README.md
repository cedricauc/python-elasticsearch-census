# MCP Server for Analyzing US Census Data with Elasticsearch

Welcome! This repository contains the source code for the building an MCP Server with Elasticsearch for analysing US census data.

This project provides a runnable implementation of a custom Model Context Protocol (MCP) server. Built with Python and the FastMCP framework, this server connects to an Elasticsearch index containing sample US population data.
## Prerequisites

Before you begin, ensure you have the following installed and running:

* **Python 3.10+**
* **Elasticsearch**: A cloud ID and API key for Elasticsearch
* **uv** : For managing Python packages.

## Getting Started

Follow these steps to set up your local environment and install the necessary dependencies.

### 1. Navigate to Your Project Directory

Open your terminal or command prompt and navigate to the project folder.
```shell
cd path/to/your/folder/python-elasticsearch-census
```

### 2. Initialize the Python Project

This step creates the `pyproject.toml` file, which `uv` uses to manage your project's dependencies.
```shell
uv init
```

### 3. Create and Activate a Virtual Environment

```shell
# Create the virtual environment
uv venv

# Activate the environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### 4. Install Dependencies

Install the necessary Python packages. 


## Environment Configuration

### Setting up the API Key

After creating the API key in Elasticsearch, you need to configure it in your environment:

```bash
# Export the API key and Cloud idd for the current session
export ES_API_KEY="your_encoded_api_key_here"
export ES_CLOUD_ID="your_encoded_cloud_id_here"

```

## Usage Instructions

With the environment set up, you can now run the solution.


### 1. Ingest the Sample Data

First, run the provided script to populate your Elasticsearch instance with the sample data. This script will create the index with the correct mapping and insert the 51 sample documents.
```shell
python ingest_data.py
```
You should see output confirming that the documents were ingested successfully.

### 2. Run the MCP Server

Second, run the provided script to start the mcp server. This script will allow Python APIs to interact with large language models (LLMs) by exposing tools, resources, and prompts.
```shell
python us_census_mcp.py
``` 


## US Census Demographic Report (2010)

Based on the **us-census** index containing 2010 Census data (SF1 and ACS datasets), here is a comprehensive demographic overview of the United States.

---

### National Summary

| Metric | Value |
|--------|-------|
| **Total Population** | 308,745,538 |
| **Average Median Age** | 37.5 years |
| **Average Median Home Value** | $204,108 |
| **Foreign Born Population** | 38,675,012 (12.5%) |

---

### Population by State (Top 10)

The most populous states are **California** (37.3M), **Texas** (25.1M), **New York** (19.4M), **Florida** (18.8M), and **Illinois** (12.8M).

---

### Median Home Values by State (Top 10)

**Hawaii** leads with the highest median home value at $537,400, followed by **California** ($458,500) and **District of Columbia** ($443,300). The lowest values are in **West Virginia** ($94,500) and **Mississippi** ($96,500).

---

### Age Demographics

**Oldest populations:**
- Maine (42.7 years)
- Vermont (41.5 years)
- West Virginia (41.3 years)

**Youngest populations:**
- Utah (29.2 years)
- Texas (33.6 years)
- Alaska & DC (33.8 years)

---

### Key Insights

- **Regional housing disparity**: Coastal states (Hawaii, California, Northeast) have median home values 3-5x higher than Southern and Midwestern states
- **Age distribution**: Northeastern states trend older, while Western and Southern states skew younger
- **Population concentration**: The top 10 states account for over 54% of the total US population
