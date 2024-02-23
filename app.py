# file stuff
import os
import sys
import zipfile
import requests
import tempfile
from io import BytesIO
import random
import string

#image generation stuff
from PIL import Image

# gradio / hf stuff
import gradio as gr
from openai import OpenAI
from dotenv import load_dotenv

# stats stuff
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi




load_dotenv()

openai_key = os.getenv("OPENAI_API_KEY")
pw_key = os.getenv("PW")

if openai_key == "<YOUR_OPENAI_API_KEY>":
    openai_key = ""

if pw_key == "<YOUR_PW>":
    pw_key = ""

if pw_key == "":
    sys.exit("Please Provide A Password in the Environment Variables")

if openai_key == "":
    sys.exit("Please Provide Your OpenAI API Key")

# Connect to MongoDB
uri = os.getenv("MONGO_URI")
mongo_client = MongoClient(uri, server_api=ServerApi('1'))

mongo_db = mongo_client.pdr
mongo_collection = mongo_db["images"]

# Send a ping to confirm a successful connection
try:
    mongo_client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# image_paths_global = []
# image_labels_global = []

def update_labels(show_labels):
    if show_labels:
        return [(path, label) for path, label in zip(image_paths_global, image_labels_global)]
    else:
        return [(path, "") for path in image_paths_global]  # Empty string as label to hide them

def generate_images_wrapper(prompts, pw, model, show_labels):
    global image_paths_global, image_labels_global
    image_paths, image_labels = generate_images(prompts, pw, model)
    image_paths_global = image_paths  # Store paths globally

    if show_labels:
        image_labels_global = image_labels  # Store labels globally if showing labels is enabled
    else:
        image_labels_global = [""] * len(image_labels)  # Use empty labels if showing labels is disabled

    # Modify the return statement to not use labels if show_labels is False
    image_data = [(path, label if show_labels else "") for path, label in zip(image_paths, image_labels)]

    return image_data  # Return image paths with or without labels based on the toggle

def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"Failed to download image from URL: {url}")

def zip_images(image_paths_and_labels):
    zip_file_path = tempfile.NamedTemporaryFile(delete=False, suffix='.zip').name
    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
        for image_url, _ in image_paths_and_labels:
            image_content = download_image(image_url)
            # Generate a random filename for the image
            random_filename = ''.join(random.choices(string.ascii_letters + string.digits, k=10)) + ".png"
            # Write the image content to the zip file with the random filename
            zipf.writestr(random_filename, image_content)
    return zip_file_path


def download_all_images():
    global image_paths_global, image_labels_global
    if not image_paths_global:
        raise gr.Error("No images to download.")
    image_paths_and_labels = list(zip(image_paths_global, image_labels_global))
    zip_path = zip_images(image_paths_and_labels)
    image_paths_global = []  # Reset the global variable
    image_labels_global = []  # Reset the global variable
    return zip_path

def generate_images(prompts, pw, model):
    # Check for a valid password
    if pw != os.getenv("PW"):
        raise gr.Error("Invalid password. Please try again.")

    image_paths = []  # Initialize a list to hold paths of generated images
    image_labels = []  # Initialize a list to hold labels of generated images
    users = []  # Initialize a list to hold user initials

    # Split the prompts string into individual prompts based on semicolon separation
    prompts_list = prompts.split(';')

    for entry in prompts_list:
        entry_parts = entry.split('-', 1)  # Split by the first dash found
        if len(entry_parts) != 2:
            raise gr.Error("Invalid prompt format. Please ensure it is in 'initials-prompt' format.")

        user_initials, text = entry_parts[0].strip(), entry_parts[1].strip()  # Extract user initials and the prompt
        users.append(user_initials)  # Append user initials to the list

        try:
            client = OpenAI(api_key=openai_key)
            response = client.images.generate(
                prompt=text,
                model=model, # dall-e-2 or dall-e-3
                quality="standard", # standard or hd
                size="512x512" if model == "dall-e-2" else "1024x1024", # varies for dalle-2 and dalle-3
                n=1, # Number of images to generate
            )

            image_url = response.data[0].url
            image_label = f"User: {user_initials}, Prompt: {text}"  # Creating a label for the image including user initials

            try:
                mongo_collection.insert_one({"user": user_initials, "text": text, "model": model, "image_url": image_url})
            except Exception as e:
                print(e)
                raise gr.Error("An error occurred while saving the prompt to the database.")

            # Append the image URL and label to their respective lists
            image_paths.append(image_url)
            image_labels.append(image_label)

        except Exception as error:
            print(str(error))
            raise gr.Error(f"An error occurred while generating the image for: {entry}")

    return image_paths, image_labels  # Return both image paths and labels

with gr.Blocks() as demo:
    gr.Markdown("# <center> Prompt de Resistance Image Generator</center>")
    gr.Markdown("**Instructions**: To use this service, please enter the password. Then generate an image from the prompt field below, then click the download arrow from the top right of the image to save it.")
    pw = gr.Textbox(label="Password", type="password",
                     placeholder="Enter the password to unlock the service")
    text = gr.Textbox(label="What do you want to create?",
                      placeholder="Enter your text and then click on the \"Image Generate\" button")

    model = gr.Dropdown(choices=["dall-e-2", "dall-e-3"], label="Model", value="dall-e-2")
    show_labels = gr.Checkbox(label="Show Image Labels", value=True)  # Default is to show labels
    btn = gr.Button("Generate Images")
    output_images = gr.Gallery(label="Image Outputs", show_label=True, columns=[3], rows=[1], object_fit="contain",
                                height="auto", allow_preview=False)

    text.submit(fn=generate_images_wrapper, inputs=[text, pw, model], outputs=output_images, api_name="generate_image")
    # btn.click(fn=generate_images_wrapper, inputs=[text, pw, model], outputs=output_images, api_name=False)
    btn.click(fn=generate_images_wrapper, inputs=[text, pw, model, show_labels], outputs=output_images, api_name=False)

    show_labels.change(fn=update_labels, inputs=[show_labels], outputs=[output_images])

    download_all_btn = gr.Button("Download All")
    download_link = gr.File(label="Download Zip")
    download_all_btn.click(fn=download_all_images, inputs=[], outputs=download_link)

demo.launch(share=False)