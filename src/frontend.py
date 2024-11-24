import os
import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from src.graphdb import get_list_of_nodes, generate_unique_chunk_name, create_and_return_chunk, create_chunk_and_relationship, update_chunk, get_chunk_attributes
from datetime import datetime
from src.gcputils import create_folder, upload_file_to_folder, get_image_from_gcp
from src.documents import extract_images_from_pdf, split_pdf_to_chunks
from src.utils import get_substring_before_keyword, retrieve_relevant_documents, retrieve_relevant_images, generate_embedding
import keys

GEMINI_MODEL = keys.GEMINI_MODEL
GEMINI_IMAGE_MODEL = keys.GEMINI_IMAGE_MODEL
EMBEDDING_MODEL = keys.EMBEDDING_MODEL
GCP_BUCKET = keys.GCP_BUCKET
GOOGLE_API_KEY = keys.GOOGLE_API_KEY
FIRESTORE_URL = keys.FIRESTORE_URL
FIRESTORE_API_KEY = keys.FIRESTORE_API_KEY
GCP_PROJECT_ID = keys.GCP_PROJECT_ID
GCP_LOCATION = keys.GCP_LOCATION


vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
model = GenerativeModel(GEMINI_MODEL)
model_image = GenerativeModel(GEMINI_IMAGE_MODEL)

# Set up the page configuration
st.set_page_config(layout="wide")

def initialize_session_parameters():
    st.session_state.context = "init"
    st.session_state.temperature = 0.1
    st.session_state.max_tokens = 2048
    st.session_state.top_p = 1.0
    st.session_state.top_k = 32
    st.session_state.chunk_list = []
    st.session_state.selected_options_node = []
    st.session_state.chosen_id = ""
    st.session_state.chosen_id_prev = ""
    st.session_state.chunk_list = []
    st.session_state.files = "init"
    st.session_state.node_list = []
    st.session_state.document_names = []
    st.session_state.new_parent = []
    st.session_state.unique_id = ""


def sidebar_menus():
    st.sidebar.image("static/images/picture.png")
    st.sidebar.header("Application")

    # Main radio button for choosing the action
    chosen_id = st.sidebar.radio(
        "Choose what you want to do:",
        ("Chat with your Data", "Upload Files"),
        index=0
    )
    st.session_state.chosen_id = chosen_id

    # Handle "Chat with your Data" option
    if chosen_id == "Chat with your Data":
        if st.sidebar.button("Clear Chat history", type="primary"):
            st.session_state.pop("chat", None)

def create_relationships_for_chunks(driver, chunks, node_name):
    for chunk_name in chunks:
        create_chunk_and_relationship(driver, chunk_name, node_name)

def create_relationships(driver):

    with st.session_state.container.container():
        st.header("Upload Files to RAG", divider="rainbow")  
  
        if st.session_state.files == "link_all_files":
            st.markdown(f"Linking all files to parent.")
            st.markdown(f"Parent names which are available:")
            st.session_state.selected_option = st.radio("Select from existing parents:", st.session_state.node_list, index=0)
            if st.button('Select option', key='button4'):
                create_relationships_for_chunks(driver, st.session_state.document_names, get_substring_before_keyword(st.session_state.selected_option))
                st.session_state.files = "ready"
            new_parent = st.text_input(f"Or give a new parent name:", key="text_box")
            if new_parent:
                create_relationships_for_chunks(driver, st.session_state.document_names, new_parent)
                st.write(f"New parent created ")
                st.session_state.files = "ready"


def describe_image(image_file, file_extension, model):
    try:
        text_prompt = """Give overall headline for the image and one line description. Then read the text in the image and output the text in detail. If the image is a spreadsheet then output what you see in JSON format and extract table info from the image. If you are not able to extract JSON then output only text."""

        # Validate file extension
        if file_extension not in ['.png', '.jpg', '.jpeg']:
            raise ValueError("Unsupported file extension. Please use '.png', '.jpg', or '.jpeg'.")

        # Determine MIME type
        if file_extension == '.png':
            mime_type = "image/png"
        else:
            mime_type = "image/jpg"

        # Create image file part
        image_file = Part.from_uri(
            uri=image_file,
            mime_type=mime_type,
        )

        prompt = [text_prompt, image_file]
        generation_config = {
                "max_output_tokens" : st.session_state.max_tokens,
                "temperature" : st.session_state.temperature,
                "top_p" : st.session_state.top_p,
                "top_k" : st.session_state.top_k
            }
        # Generate content
        response = model_image.generate_content(prompt, generation_config=generation_config)
        return response.text

    except ValueError as ve:
        print(f"Procedure describe_image: ValueError: {ve}")
        return None
    except AttributeError as ae:
        print(f"Procedure describe_image: AttributeError: {ae}. Check if 'Part' and 'model' are correctly defined and used.")
        return None
    except Exception as e:
        print(f"Procedure describe_image: An error occurred: {e}")
        return None


def describe_image_short(image_file, file_extension, model):
    try:
        text_prompt = """Read the text of the image and create a one-sentence summary of the image's content."""

        # Validate file extension
        if file_extension not in ['.png', '.jpg', '.jpeg']:
            raise ValueError("Unsupported file extension. Please use '.png', '.jpg', or '.jpeg'.")

        # Determine MIME type
        if file_extension == '.png':
            mime_type = "image/png"
        else:
            mime_type = "image/jpg"

        # Create image file part
        image_file = Part.from_uri(
            uri=image_file,
            mime_type=mime_type,
        )

        prompt = [text_prompt, image_file]
        generation_config = {
                "max_output_tokens" : st.session_state.max_tokens,
                "temperature" : st.session_state.temperature,
                "top_p" : st.session_state.top_p,
                "top_k" : st.session_state.top_k
            }
        # Generate content
        response = model_image.generate_content(prompt, generation_config=generation_config)
        return response.text

    except ValueError as ve:
        print(f"Procedure describe_image_short: ValueError: {ve}")
        return None
    except Exception as e:
        print(f"Procedure describe_image_short: An error occurred: {e}")
        return None

def upload_files(driver):
    with st.session_state.container.container():
        st.header("Upload Files to RAG", divider="rainbow")       
        st.subheader("Here you can upload data and files")
        uploaded_files = st.file_uploader("Drag and drop files here", accept_multiple_files=True)
        if uploaded_files and st.button("Upload Files"):
            with st.spinner("Uploading files..."):
                now = datetime.now()
                timestamp = now.strftime("%Y%m%d%H%M%S")
                st.session_state.folder_name = f"fpl_bucket_{timestamp}"
                create_folder(GCP_BUCKET, st.session_state.folder_name)
                st.session_state.numb_of_files = len(uploaded_files)
                status_container = st.empty()
                st.session_state.document_names = []
                with status_container.container():
                    for file in uploaded_files:
                        file_name_body = os.path.splitext(file.name.lower())[0].strip()
                        file_extension = os.path.splitext(file.name.lower())[1].strip()
                        file_name = file_name_body + file_extension
                        # Upload the file to the folder
                        st.write(f"Uploading file {file_name}")
                        upload_file_to_folder(GCP_BUCKET, st.session_state.folder_name, file, file_name)
                        unique_chunk_name = generate_unique_chunk_name(driver, file_name_body, file_extension)
                        if unique_chunk_name != file_name:
                            st.write(f"The file with same name {file_name} already exists on the database. The file is renamed to {unique_chunk_name}")
                        chunk_name = create_and_return_chunk(driver, unique_chunk_name, st.session_state.folder_name, "new")
                        if file_extension in ('.png', '.jpg', '.jpeg'):
                            image_text = describe_image(f"gs://{GCP_BUCKET}/{st.session_state.folder_name}/{file_name}", file_extension, model)
                            embedding_string = generate_embedding(image_text)
                            update_chunk(driver, chunk_name, image_text, embedding_string)
                        elif file_extension in ('.pdf'):
                            image_list = extract_images_from_pdf(GCP_BUCKET, st.session_state.folder_name, file_name_body, file_extension) 
                            for image_name, page_number in image_list:
                                image_extension = os.path.splitext(image_name.lower())[1]
                                image_text = describe_image(f"gs://{GCP_BUCKET}/{st.session_state.folder_name}/{image_name}", image_extension, model)
                                image_text_short = describe_image_short(f"gs://{GCP_BUCKET}/{st.session_state.folder_name}/{image_name}", image_extension, model)
                                embedding_string = generate_embedding(image_text)
                                chunk_image_name = create_and_return_chunk(driver, image_name, st.session_state.folder_name, "new", element=-1)
                                update_chunk(driver, chunk_image_name, image_text, embedding_string, parent_chunk = chunk_name, element = -1, chunk_type="pdf_image", text_short=image_text_short)
                            split_pdf_to_chunks(driver, GCP_BUCKET, st.session_state.folder_name, file_name_body, file_extension, image_list)    
                        st.session_state.document_names.append(chunk_name)
                status_container.empty()
                st.session_state.files = "load_ready"

def streamlit_role(role):
  if role == "model":
    return "assistant"
  else:
    return role
  
def plot_images(driver, chunk_names):
    chunk_attributes = get_chunk_attributes(driver, chunk_names)
    for chunk in chunk_attributes:
        folder = chunk["folder"]
        name = chunk["name"]
        image = get_image_from_gcp(GCP_BUCKET, folder, name)
        st.image(image, caption=f"{folder}/{name}", width=300)

def role_to_streamlit(role):
    if role == 'user':
        return st.text
    elif role == 'model':
        return st.markdown
    elif role == 'image':
        return plot_images
    else:
        return st.write

def add_history_section(history, role, text):
    new_conversation = {
            "role": role,
            "text": text
        }
    history.append(new_conversation)
    return history

def remove_image_roles(data_list):
    """
    Removes all dictionary entries with the role 'images' from the list.

    :param data_list: List of dictionaries containing 'role' and 'text' keys.
    :return: A new list with 'images' roles removed.
    """
    return [entry for entry in data_list if entry.get('role') != 'image']

def show_chat(driver):

    # select chat window as Gemini
    st.header("Chat with your Data", divider="rainbow")       
    st.subheader("Here you can chat with your data and files")

    # chat page is opened first time or chat history has been cleared
    if "chat" not in st.session_state:
        sys_instructions = """You are an AI assistant and give good and precise answers to user's questions."""
        st.session_state.chat = model.start_chat(history = [])
 
    for message in st.session_state.chat.history:
        display_function = role_to_streamlit(message['role'])
        if message['role'] == 'image':
            display_function(driver, message['text'])
        else:
            with st.chat_message(streamlit_role(message['role'])):
                display_function(message['text']) 

        # chat with your documents, ask a question
    if prompt := st.chat_input("What would you like to know?"):
        st.chat_message("user").text(prompt)
                
        generation_config = {
                "max_output_tokens" : st.session_state.max_tokens,
                "temperature" : st.session_state.temperature,
                "top_p" : st.session_state.top_p,
                "top_k" : st.session_state.top_k
            }
        query_embedding = generate_embedding(prompt)
        documents, score = retrieve_relevant_documents(driver, query_embedding, top_k=5)
        image_text, chunk_names = retrieve_relevant_images(driver, query_embedding, score, top_k=3)
        documents_string = "\n".join(documents)
        documents_string += "\n".join(image_text)
        prompt_template = f"CONTEXT: {documents_string}\n\nCONVERSATION HISTORY: {remove_image_roles(st.session_state.chat.history)}\n\nQUESTION: {prompt}"
        response = model.generate_content(prompt_template,generation_config=generation_config)
                
    # Display the response
        with st.chat_message("assistant"):
            st.markdown(response.text)   
        plot_images(driver, chunk_names) 
        add_history_section(st.session_state.chat.history, "user", prompt)
        add_history_section(st.session_state.chat.history, "model", response.text)
        add_history_section(st.session_state.chat.history, "image", chunk_names)




# Main function to run the Streamlit app
def streamlit_ui(driver):

    if "context" not in st.session_state:
        initialize_session_parameters()
        st.session_state.container = st.empty()

    sidebar_menus()
    if st.session_state.chosen_id == "Chat with your Data":
        if st.session_state.chosen_id != st.session_state.chosen_id_prev:
            st.session_state.chunk_list = []
            st.session_state.chosen_id_prev = st.session_state.chosen_id
        show_chat(driver)
    elif st.session_state.chosen_id == "Upload Files":
        if st.session_state.chosen_id != st.session_state.chosen_id_prev:
            st.session_state.files = "load"
            st.session_state.node_list = get_list_of_nodes(driver)
            st.session_state.chosen_id_prev = st.session_state.chosen_id
        if st.session_state.files  == "load":
            upload_files(driver)
        if st.session_state.files == "load_ready":
            st.session_state.container.empty()
            if len(st.session_state.document_names) == 0:
                st.session_state.files = "ready"
            else:
                st.session_state.files = "link_all_files"
        if st.session_state.files == "link_all_files":
            create_relationships(driver)
        if st.session_state.files == "ready":
            st.session_state.files = "init"
            st.session_state.selected_option = "init"
            st.session_state.chunk_list = []
            st.session_state.container.empty()
            st.header("Upload Files to RAG", divider="rainbow") 
            st.write("Files have been processed.")
