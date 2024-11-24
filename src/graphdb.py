import keys

GCP_BUCKET = keys.GCP_BUCKET

# initialize graph database 
def initialize_grapdb(driver):
    # create constraint for nodes if already not exist
    with driver.session() as session:
        session.run("CREATE CONSTRAINT unique_node IF NOT EXISTS FOR (node:Node) REQUIRE node.nodename IS UNIQUE")

# Function to get nodes and their BELONGS_TO relationships if they exist
def get_nodes_and_relationships(driver):
    with driver.session() as session:
        query = """
        MATCH (n:Node)
        OPTIONAL MATCH (n)-[r:BELONGS_TO]->(m)
        RETURN n.name AS node, m.name AS related_node
        """
        result = session.run(query)
        return result.data()

def get_list_of_nodes(driver):
    # Open a session and execute the query
    node_list = []
    nodes_and_relationships = get_nodes_and_relationships(driver)
    for record in nodes_and_relationships:
        node = record['node']
        related_node = record['related_node']
        if related_node:
            node_name = f"{node} (whose parent is {related_node})"
        else:
            node_name = node
        node_list.append(node_name)
    return node_list
    
def create_and_return_chunk(driver, chunk_name, folder_name, status="new", element=0):
    with driver.session() as session:
        query = (
            "MERGE (c:Chunk {name: $chunk_name, folder: $folder_name, element: $element}) "
            "ON CREATE SET c.status = $status, c.in_query = True  "
            "RETURN c.name AS chunk_name"
        )
        result = session.run(query, chunk_name=chunk_name, status=status, element=element, folder_name=folder_name)
        record = result.single()
        return record["chunk_name"] if record else None
    
def create_consecutive_relationships(driver, folder_name, chunk_name):
    with driver.session() as session:
        # Retrieve all chunks in the specified folder with the specified name, sorted by the element property
        query = (
            "MATCH (c:Chunk {folder: $folder_name, name: $chunk_name}) "
            "RETURN c ORDER BY c.element"
        )
        result = session.run(query, folder_name=folder_name, chunk_name=chunk_name)

        # Collect all chunks
        chunks = [record["c"] for record in result]

        # Create relationships between consecutive chunks
        for i in range(len(chunks) - 1):
            chunk1 = chunks[i]
            chunk2 = chunks[i + 1]

            # Create a relationship from chunk1 to chunk2
            session.run(
                "MATCH (c1:Chunk {name: $chunk1_name, folder: $folder_name, element: $chunk1_element}), "
                "(c2:Chunk {name: $chunk2_name, folder: $folder_name, element: $chunk2_element}) "
                "MERGE (c1)-[:NEXT]->(c2)",
                chunk1_name=chunk1["name"], chunk2_name=chunk2["name"],
                folder_name=folder_name, chunk1_element=chunk1["element"], chunk2_element=chunk2["element"]
            )

            # Create a relationship from chunk2 to chunk1
            session.run(
                "MATCH (c1:Chunk {name: $chunk1_name, folder: $folder_name, element: $chunk1_element}), "
                "(c2:Chunk {name: $chunk2_name, folder: $folder_name, element: $chunk2_element}) "
                "MERGE (c2)-[:PREVIOUS]->(c1)",
                chunk1_name=chunk1["name"], chunk2_name=chunk2["name"],
                folder_name=folder_name, chunk1_element=chunk1["element"], chunk2_element=chunk2["element"]
            )

    
def update_chunk(driver, chunk_name, text, embedding_string, parent_chunk = "", element = 0, chunk_type="image", text_short=""):
    with driver.session() as session:
        query = (
            "MATCH (c:Chunk {name: $chunk_name, element: $element}) "
            "SET c.chunk_type = $chunk_type, c.text = $text, c.embedding_string = $embedding_string, c.text_short = $text_short "
            "RETURN c.name AS chunk_name"
        )
        result = session.run(query, element=element, chunk_name=chunk_name, chunk_type=chunk_type, text=text, embedding_string=embedding_string, text_short=text_short)
        if parent_chunk != "":
            create_relationship_query = (
                "MATCH (c:Chunk {name: $chunk_name}), (n:Chunk {name: $parent_chunk}) "
                "MERGE (c)-[:IMAGE_OF]->(n)"
            )
            session.run(create_relationship_query, chunk_name=chunk_name, parent_chunk=parent_chunk)
    
def check_chunk_exists(driver, chunk_name):
    with driver.session() as session:
        query = (
            "MATCH (c:Chunk {name: $chunk_name}) "
            "RETURN c"
        )
        result = session.run(query, chunk_name=chunk_name)
        record = result.single()
        return record[0] if record else None
    
def generate_unique_chunk_name(driver, file_name_body, file_extension):
    chunk_name = file_name_body + file_extension
    counter = 1
    while check_chunk_exists(driver, chunk_name) is not None:
        chunk_name = f"{file_name_body}_{counter}{file_extension}"
        counter += 1

    return chunk_name

def create_node(driver, node_name):
    with driver.session() as session:
        # Create the Node node if it doesn't exist
        create_node_query = (
            "MERGE (n:Node {name: $node_name}) "
            "ON CREATE SET n.in_query = True "
            "RETURN n"
        )
        session.run(create_node_query, node_name=node_name)   


def create_chunk_and_relationship(driver, chunk_name, node_name):
    with driver.session() as session:
        create_node(driver, node_name)
        # Create the relationship between Chunk and Node only if Chunk has element=0 or element=-1
        create_relationship_query = (
            "MATCH (c:Chunk {name: $chunk_name}), (n:Node {name: $node_name}) "
            "WHERE c.element IN [0, -1] "
            "MERGE (c)-[:PART_OF]->(n)"
        )
        session.run(create_relationship_query, chunk_name=chunk_name, node_name=node_name)
            
    
def get_image_text_short_by_chunk_name(driver, name, element=-1):
    try:
        with driver.session() as session:
            query = """
            MATCH (c:Chunk {name: $name, element: $element})
            RETURN c.text_short AS text_short
            """
            result = session.run(query, name=name, element=element)
            # Extract the text_short values from the result and join them into a single string
            return "\n".join(record["text_short"] for record in result)
    except Exception as e:
        print(f"Procedure get_image_text_short_by_chunk_name: An error occurred in get_image_text_short_by_chunk_name: {e}")
        return ""

def get_chunk_attributes(driver, chunk_names):
    with driver.session() as session:
        query = (
            "MATCH (c:Chunk) "
            "WHERE c.name IN $chunk_names "
            "RETURN c.name AS name, c.folder AS folder"
        )
        result = session.run(query, chunk_names=chunk_names)
        return [{"name": record["name"], "folder": record["folder"]} for record in result]