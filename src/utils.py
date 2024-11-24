import json
import numpy as np
from vertexai.language_models import TextEmbeddingModel
import keys

EMBEDDING_MODEL = keys.EMBEDDING_MODEL
embedding_model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)

def generate_embedding(query_text):
    """Generates an embedding for the given query text using Vertex AI.
    Args:
        query_text (str): The text to be embedded.
    Returns:
        The embedding vector for the input text, or an empty list if the input text is empty.
    """
    # Return an empty list if there is no input string
    if not query_text:
        return []
    
    # Generate the embedding
    embeddings = embedding_model.get_embeddings([query_text])

    # Return the embedding vector for the input text
    return embeddings[0].values

def get_substring_before_keyword(input_string, keyword="(whose parent is"):
    # Split the string at the keyword
    parts = input_string.split(keyword)

    # Get the substring before the keyword
    if len(parts) > 1:
        substring_before_keyword = parts[0]
    else:
        # If the keyword is not found, use the entire string
        substring_before_keyword = input_string

    # Remove all empty spaces from the substring
    result = substring_before_keyword.replace(" ", "")

    return result

def compute_cosine_similarity(vec1, vec2):
    """
    Compute the cosine similarity between two vectors.

    Args:
        vec1 (list, np.ndarray, or str): The first input vector.
        vec2 (list, np.ndarray, or str): The second input vector.

    Returns:
        float: The cosine similarity between vec1 and vec2.
    """
    # Check if vec1 is a string and convert it to a list if needed
    if isinstance(vec1, str):
        try:
            vec1 = json.loads(vec1)
        except json.JSONDecodeError:
            raise ValueError("vec1 is a string but not a valid JSON list")

    # Check if vec2 is a string and convert it to a list if needed
    if isinstance(vec2, str):
        try:
            vec2 = json.loads(vec2)
        except json.JSONDecodeError:
            raise ValueError("vec2 is a string but not a valid JSON list")

    # Convert the lists to numpy arrays if they are not already
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)

    # Ensure the vectors are 1-dimensional
    if vec1.ndim != 1 or vec2.ndim != 1:
        raise ValueError("Both vectors must be 1-dimensional")

    # Compute cosine similarity using numpy
    dot_product = np.dot(vec1, vec2)
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)

    # Handle the case where one of the vectors is zero
    if norm_vec1 == 0 or norm_vec2 == 0:
        raise ValueError("One of the vectors is zero, cannot compute cosine similarity")

    cosine_similarity = dot_product / (norm_vec1 * norm_vec2)

    return cosine_similarity

    
def retrieve_relevant_documents(driver, query_embedding, top_k=5):
    lowest_score = 0
    with driver.session() as session:
        query = (
            "MATCH (c:Chunk) "
            "WHERE c.in_query = true AND c.element <> -1 "
            "RETURN c.name AS chunk_name, c.element AS element, c.embedding_string AS embedding_string"
        )
        result = session.run(query)
        similarities = []
        for record in result:
            chunk_name = record["chunk_name"]
            element = record["element"]
            embedding_string = record["embedding_string"]

            # Check if embedding_string is empty or invalid
            if not embedding_string:
                print(f"Procedure retrieve_relevant_documents: Skipping chunk {chunk_name} due to empty embedding_string")
                continue

            # Assuming embedding_string needs to be converted to a list or array
            try:
                # embedding = json.loads(embedding_string)  # Uncomment if needed
                similarity = compute_cosine_similarity(query_embedding, embedding_string)
                if similarity > 0.5:
                    similarities.append((chunk_name, element, similarity))
            except Exception as e:
                print(f"Procedure retrieve_relevant_documents: Error processing chunk {chunk_name}: {e}")
                continue

        # Sort by similarity in descending order
        similarities.sort(key=lambda x: x[2], reverse=True)

        # Select top_k unique combinations of chunk_name and element
        top_chunks = []
        seen_combinations = set()
        for chunk_name, element, similarity in similarities:
            if (chunk_name, element) not in seen_combinations:
                top_chunks.append((chunk_name, element, similarity))
                seen_combinations.add((chunk_name, element))
            if len(top_chunks) >= top_k:
                break

        if top_chunks:
            # Extract the highest score
            lowest_score = top_chunks[-1][2]   

        # Retrieve the corresponding documents
        documents = []
        chunk_names = []
        for chunk_name, element, similarity in top_chunks:
            doc_query = (
                "MATCH (c:Chunk {name: $chunk_name, element: $element}) "
                "RETURN c.text AS text"
            )
            doc_result = session.run(doc_query, chunk_name=chunk_name, element=element)
            for doc_record in doc_result:
                if doc_record:
                    documents.append(doc_record["text"])
                    chunk_names.append((chunk_name, element))
        return documents, lowest_score

def retrieve_relevant_images(driver, query_embedding, score, top_k=3):
    with driver.session() as session:
        query = (
            "MATCH (c:Chunk) "
            "WHERE c.in_query = true AND (c.element = -1 OR c.chunk_type = 'image') "
            "RETURN c.name AS chunk_name, c.element AS element, c.embedding_string AS embedding_string"
        )
        result = session.run(query)
        similarities = []
        for record in result:
            chunk_name = record["chunk_name"]
            element = record["element"]
            embedding_string = record["embedding_string"]

            # Check if embedding_string is empty or invalid
            if not embedding_string:
                print(f"Procedure retrieve_relevant_images: Skipping chunk {chunk_name} due to empty embedding_string")
                continue

            # Assuming embedding_string needs to be converted to a list or array
            try:
                # embedding = json.loads(embedding_string)  # Uncomment if needed
                similarity = compute_cosine_similarity(query_embedding, embedding_string)
                similarities.append((chunk_name, element, similarity))
            except Exception as e:
                print(f"Procedure retrieve_relevant_images: Error processing chunk {chunk_name}: {e}")
                continue

        # Sort by similarity in descending order
        similarities.sort(key=lambda x: x[2], reverse=True)

        # Select top_k unique combinations of chunk_name and element
        top_chunks = []
        seen_combinations = set()
        if score < 0.55:
            score = 0.55
        for chunk_name, element, similarity in similarities:
            if (chunk_name, element) not in seen_combinations and similarity >= score:
                top_chunks.append((chunk_name, element, similarity))
                seen_combinations.add((chunk_name, element))
            if len(top_chunks) >= top_k or similarity < score:
                break 

        # Retrieve the corresponding documents
        image_text = []
        chunk_names = []
        for chunk_name, element, similarity in top_chunks:
            doc_query = (
                "MATCH (c:Chunk {name: $chunk_name, element: $element}) "
                "RETURN c.text AS text"
            )
            doc_result = session.run(doc_query, chunk_name=chunk_name, element=element)
            for doc_record in doc_result:
                if doc_record:
                    image_text.append(doc_record["text"])
                    chunk_names.append((chunk_name))
        return image_text, chunk_names