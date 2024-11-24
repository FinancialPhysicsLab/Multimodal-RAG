from neo4j import GraphDatabase
from src.frontend import streamlit_ui
from src.graphdb import initialize_grapdb
import keys

NEO4J_URI = keys.NEO4J_URI
NEO4J_USERNAME = keys.NEO4J_USERNAME
NEO4J_PASSWORD = keys.NEO4J_PASSWORD

def app():
    """Main function to run the Streamlit app with Neo4j integration."""
    try:
        with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)) as driver:
            initialize_grapdb(driver)
            streamlit_ui(driver)
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")

if __name__ == "__main__":
    app()
