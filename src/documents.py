import io
import fitz
from src.utils import generate_embedding
from src.gcputils import read_pdf_from_gcs, list_objects_in_bucket, upload_file_to_folder
import pymupdf4llm
from src.graphdb import get_image_text_short_by_chunk_name, create_and_return_chunk, create_consecutive_relationships, update_chunk


def split_pdf_to_chunks(driver, bucket, folder_name, file_body, extension, image_list):
    # Construct the GCS path
    source_blob_name = f"{folder_name}/{file_body}{extension}"

    # List objects in the bucket to verify the presence of the file
    objects = list_objects_in_bucket(bucket)
    if source_blob_name not in objects:
        raise FileNotFoundError(f"No such object: {bucket}/{source_blob_name}")

    # Read the PDF file from GCS
    pdf_bytes = read_pdf_from_gcs(bucket, source_blob_name)

    # Open the PDF file from bytes
    pdf_document = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    md_text = pymupdf4llm.to_markdown(doc=pdf_document, page_chunks=True)
    number_of_pages = len(md_text)

    # Create a dictionary to map page numbers to their respective image names
    page_images = {}
    for image_name, page_number in image_list:
        if page_number not in page_images:
            page_images[page_number] = []
        page_images[page_number].append(get_image_text_short_by_chunk_name(driver, image_name))

    for i in range(number_of_pages):
        prev_text = md_text[i-1]['text'][-1500:] if i > 0 else ""
        next_text = md_text[i+1]['text'][:1500] if i < number_of_pages-1 else ""
        chunk = prev_text 

        # Get the current page number (1-based index)
        current_page_number = i + 1

        # Append image names to the chunk if there are images on the current page
        if current_page_number in page_images:
            image_texts = "\n".join(page_images[current_page_number])
            chunk += f"\n\nImages on this page:\n{image_texts}"
        chunk += "\n\n" + md_text[i]['text'] + next_text

        create_and_return_chunk(driver, f"{file_body}{extension}", folder_name, status="new", element=i)
        embedding_string = generate_embedding(chunk)
        update_chunk(driver, f"{file_body}{extension}", chunk, embedding_string, element = i, chunk_type="text")
    create_consecutive_relationships(driver, folder_name, f"{file_body}{extension}")
  


def extract_images_from_pdf(bucket, folder_name, file_body, extension):
    # Construct the GCS path
    source_blob_name = f"{folder_name}/{file_body}{extension}"

    # List objects in the bucket to verify the presence of the file
    objects = list_objects_in_bucket(bucket)
    if source_blob_name not in objects:
        raise FileNotFoundError(f"No such object: {bucket}/{source_blob_name}")

    # Read the PDF file from GCS
    pdf_bytes = read_pdf_from_gcs(bucket, source_blob_name)

    # Open the PDF file from bytes
    pdf_document = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")

    images = []

    # Iterate through each page
    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        image_list = page.get_images(full=True)

        # Iterate through each image
        for image_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image_filename = f"{file_body}_image_{page_number+1}_{image_index+1}.{image_ext}"
            images.append((image_filename, page_number + 1))  # Include page number in the tuple
            # Save the image
            upload_file_to_folder(bucket, folder_name, image_bytes, image_filename, 'string')

    return images

